# Copyright 2015-2018 Ask Hjorth Larsen, Fawzi Mohamed, Ankit Kariryaa
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

#
# Main author and maintainer: Ask Hjorth Larsen <asklarsen@gmail.com>


from __future__ import print_function
import re
import os
import sys
from contextlib import contextmanager

import numpy as np
import logging
from ase.units import Bohr
from ase.io import read

# import setup_paths

from nomadcore.unit_conversion.unit_conversion import convert_unit

from octopusparser.aseoct import Octopus, parse_input_file

"""This is the Octopus parser.

It has to parse many files:
 * input file, 'inp' (ASE does this)
 * output file, 'static/info' (SimpleParser)
   - similar file or files for other calculation modes
 * anything written to stdout (this file could have any name) (SimpleParser)
   - program output can be cooking recipes ("parse *all* outputs")
 * geometry input file, if specified in 'inp'
   - ASE takes care of that
 * output density/potential/etc. if written to files
   - cube
   - xcrysden
   - xyz
   - other candidates: vtk, etsf

There are more output formats but they are non-standard, or for
debugging, not commonly used.  We will only implement support for
those if many uploaded calculations contain those formats.  I think it
is largely irrelevant.
"""

metaInfoEnv = None

def parse_infofile(meta_info_env, pew, fname):
    with open(fname) as fd:
        for line in fd:
            if line.startswith('SCF converged'):
                iterations = int(line.split()[-2])
                pew.addValue('x_octopus_info_scf_converged_iterations',
                             iterations)
                break
        for line in fd:  # Jump down to energies:
            if line.startswith('Energy ['):
                octunit = line.strip().split()[-1].strip('[]:')
                nomadunit = {'eV': 'eV', 'H': 'hartree'}[octunit]
                break

        names = {'Total': 'energy_total',
                 'Free': 'energy_free',
                 'Ion-ion': 'x_octopus_info_energy_ion_ion',
                 'Eigenvalues': 'energy_sum_eigenvalues',
                 'Hartree': 'energy_electrostatic',
                 'Exchange': 'energy_X',
                 'Correlation': 'energy_C',
                 'vanderWaals': 'energy_van_der_Waals',
                 '-TS': 'energy_correction_entropy',
                 'Kinetic': 'electronic_kinetic_energy'}

        for line in fd:
            if line.startswith('---'):
                continue
            tokens = line.split()
            if len(tokens) < 3:
                break

            if tokens[0] in names:
                pew.addValue(names[tokens[0]],
                             convert_unit(float(tokens[2]), nomadunit))


def parse_logfile(meta_info_env, pew, fname):
    maxlines = 100
    with open(fname) as fd:
        for i, line in enumerate(fd):
            if i > maxlines:
                break
            if line.startswith('Version'):
                version = line.split()[-1]
                pew.addValue('program_version', version)
            elif line.startswith('Revision'):
                revision = int(line.split()[-1])
                pew.addValue('x_octopus_log_svn_revision', revision)


def parse_gridinfo(metaInfoEnv, pew, fname):
    results = {}

    with open(fname) as fd:
        for line in fd:
            if '*** Grid ***' in line:
                break

        line = next(fd)

        while '***********************' not in line:
            if line.startswith('Simulation Box:'):
                line = next(fd)

                while line == '' or line[0].isspace():
                    m = re.match(r'\s*Type\s*=\s*(\S+)', line)
                    if m:
                        results['boxshape'] = m.group(1)
                    m = re.match(r'\s*Octopus will treat the system as periodic in (\S+) dim', line)
                    if m:
                        results['npbc'] = int(m.group(1))

                    m = re.match(r'\s*Lattice Vectors \[(\S+)\]', line)
                    if m:
                        results['unit'] = m.group(1)
                        cell = np.array([[float(x) for x in next(fd).split()] for _ in range(3)])
                        results['cell'] = cell

                    line = next(fd)

            if line.startswith('Main mesh:'):
                line = next(fd)
                while line == '' or line[0].isspace():
                    m = re.match(r'\s*Spacing\s*\[(\S+)\]\s*=\s*\(\s*(\S+?),\s*(\S+?),\s*(\S+?)\)', line)
                    if m:
                        results['unit'] = m.group(1)
                        results['spacing'] = np.array(m.group(2, 3, 4)).astype(float)

                    line = next(fd)
    return results


def parse_coordinates_from_parserlog(fname):
    results = {}

    def buildblock(block):
        imax = 1 + max(b[0] for b in block)
        jmax = 1 + max(b[1] for b in block)
        array = np.zeros((imax, jmax), object)
        for i, j, val in block:
            array[i, j] = val
        labels = np.array([val[1:-1] for val in array[:, 0].astype(str)])
        numbers = array[:, 1:4].astype(float)
        return labels, numbers

    with open(fname) as fd:
        blockname = None
        block = None
        for line in fd:
            line.split('#')[0].strip()

            m = re.match(r"Opened block '(Coordinates|ReducedCoordinates)'", line)
            if m:
                blockname = m.group(1)
                block = []
                continue

            m = re.match(r'Closed block', line)
            if m:
                if blockname is None:
                    continue  # This is some other block
                labels, numbers = buildblock(block)
                results['labels'] = labels
                if blockname == 'Coordinates':
                    results['coords'] = numbers
                else:
                    assert blockname == 'ReducedCoordinates'
                    results['rcoords'] = numbers

                blockname = None
                block = None
                continue

            if block is not None:
                # Example:   (0, 0) = "Ag"
                paren_expression = r'\s*\((\d+),\s*(\d+)\)\s*=\s*(.+)'
                m = re.match(paren_expression, line)
                if not m:
                    # Example:   Coordinates (0, 0) = "O"
                    m = re.match(r'\s*' + blockname + paren_expression, line)
                if not m:
                    # Example:  Coordinates[0][0] = "H"
                    m = re.match(r'\s*' + blockname + r'\s*\[(\d+)\]\[(\d+)\]\s*=\s*(.+)', line)

                assert m is not None
                i, j, val = m.group(1, 2, 3)
                block.append((int(i), int(j), val))

            for name in ['PDBCoordinates',
                         'XYZCoordinates',
                         'XSFCoordinates']:
                m = re.match(name + r'\s*=\s*"(.+?)"', line)
                if m:
                    assert block is None
                    results[name] = m.group(1)

            m = re.match('XSFCoordinatesAnimStep\s*=\s*(\d+)', line)
            if m:
                results['XSFCoordinatesAnimStep'] = int(m.group(1))

            for name in ['Units',
                         'UnitsInput']:
                m = re.match(r'\s*' + name + r'\s*=\s*(\S+)', line)
                if m:
                    results[name] = m.group(1)

    return results


def normalize_names(names):
    return [name.lower() for name in names]

# Dictionary of all meta info:
normalized2real = None


parser_info = {
  "name": "parser_octopus",
  "version": "1.0"
}

def read_parser_log(path):
    exec_kwargs = {}
    with open(path) as fd:
        for line in fd:
            # Remove comment:
            line = line.split('#', 1)[0].strip()
            tokens = line.split('=')
            try:
                name, value = tokens
            except ValueError:
                continue # Not an assignment
            name = name.strip().lower()
            value = value.strip()

            if ' ' in name:
                # Not a real name
                continue
            exec_kwargs[name] = value
    return exec_kwargs


def is_octopus_logfile(fname):
    try:
        with open(fname) as fd:
            for n, line in enumerate(fd):
                if n > 20:
                    break
                if '|0) ~ (0) |' in line:  # Eyes from Octopus logo
                    return True
    except UnicodeDecodeError:
        # ingnore files that cannot be decoded, there are not the files
        # we are looking for
        pass

    return False


def find_octopus_logfile(dirname):
    for fname in os.listdir(dirname):
        fname = os.path.join(dirname, fname)
        if os.path.isfile(fname) and is_octopus_logfile(fname):
            return fname
    return None


def override_keywords(kwargs, parser_log_kwargs):
    # Some variables we can get from the input file, but they may
    # contain arithmetic and variable assignments which cannot
    # just be parsed into a final value.  The output of the
    # Octopus parser (exec/parser.log) is reduced to pure numbers,
    # so that is useful, except when the variable was a name (such
    # as an eigensolver).  In that case we should definitely not
    # rely on the number!  We will take some variables from the
    # exec/parser.log but most will just be verbatim from the
    # input file whether they can be parsed or not.
    exec_override_keywords = set(['radius',
                                  #'lsize',
                                  'spacing'])

    outkwargs = kwargs.copy()

    # Now override any relevant keywords:
    for name in exec_override_keywords:
        if name in kwargs and name in parser_log_kwargs:
            if name == 'lsize':
                lsize = []
                for i in range(3):
                    # (This is relatively horrible.  We are looking for
                    # lines like "Lsize (0, 1) = 5.0" or similar)
                    lsize_tmp = 'lsize (0, %d)' % i
                    assert lsize_tmp in parser_log_kwargs
                    lsize.append(parser_log_kwargs[lsize_tmp])
                outkwargs[name] = [lsize]
                continue

            # print('Keyword %s with value %s overridden by value '
            #       '%s obtained from parser log'
            #       % (name, kwargs[name], parser_log_kwargs[name]),
            #       file=fd)
            logging.debug('Keyword %s with value %s overridden by value '
                '%s obtained from parser log'
                % (name, kwargs[name], parser_log_kwargs[name]))

            outkwargs[name] = parser_log_kwargs[name]
    return outkwargs


metadata_dtypes = {'b': bool,
                   'C': str,
                   'f': float}  # Integer?


# Convert (<normalized name>, <extracted string>) into
# (<real metadata name>, <value of correct type>)
def regularize_metadata_entry(normalized_name, value):
    realname = normalized2real[normalized_name]
    assert realname in metaInfoEnv, 'No such metadata: %s' % realname
    metainfo = metaInfoEnv[realname]
    dtype = metainfo['dtypeStr']
    converted_value = metadata_dtypes[dtype](value)
    return realname, converted_value


def register_octopus_keywords(pew, category, kwargs):
    skip = set(['mixingpreconditioner', 'mixinterval'])
    for keyword in kwargs:
        if keyword in skip:  # XXXX
            continue
        # How do we get the metadata type?
        normalized_name = 'x_octopus_%s_%s' % (category, keyword)
        val = kwargs[keyword]
        try:
            name, value = regularize_metadata_entry(normalized_name, val)
        except Exception:  # unknown normalized_name or cannot convert
            pass
            # We can't crash on unknown keywords because we must support
            # versions old and new alike.
            #
            # Some keywords (e.g. Spacing) specify float as type, but they
            # can actually be blocks.  (block is a type itself)
        else:
            pew.addValue(name, value)


def parse_without_class(fname, backend, parser_info):
    # fname refers to the static/info file.
    # Look for files before we create some of our own files for logging etc.:
    # fd = stdout # Print output to stdout
    absfname = os.path.abspath(fname)
    # staticdirname, _basefname = os.path.split(absfname)
    # dirname, _static = os.path.split(staticdirname)
    dirname = os.path.dirname(os.path.abspath(fname))
    # assert _static == 'static'
    inp_path = os.path.join(dirname, 'inp')
    parser_log_path = os.path.join(dirname, 'exec', 'parser.log')
    logfile = find_octopus_logfile(dirname)

    # pew.startedParsingSession(fname, parser_info)

    pew = backend
    pew.startedParsingSession(fname, parser_info)

    # this context manager shamelessly copied from GPAW parser
    # Where should Python code be put if it is used by multiple parsers?
    @contextmanager
    def open_section(name):
        gid = pew.openSection(name)
        yield gid
        pew.closeSection(name, gid)

    with open_section('section_run'):
        pew.addValue('program_name', 'Octopus')
        pew.addValue('program_basis_set_type', 'Real-space grid')

        # print(file=fd)
        # print('Read Octopus keywords from input file %s' % inp_path,
        #       file=fd)
        logging.debug('Read Octopus keywords from input file %s' % inp_path)

        with open(inp_path) as inp_fd:
            kwargs = parse_input_file(inp_fd)
        register_octopus_keywords(pew, 'input', kwargs)

        # print('Read processed Octopus keywords from octparse logfile %s'
        #       % parser_log_path, file=fd)
        logging.debug(
            'Read processed Octopus keywords from octparse logfile %s' % parser_log_path)

        parser_log_kwargs = read_parser_log(parser_log_path)
        register_octopus_keywords(pew, 'parserlog', parser_log_kwargs)

        # print('Override certain keywords with processed keywords', file=fd)
        kwargs = override_keywords(kwargs, parser_log_kwargs)

        # print('Read as ASE calculator', file=fd)
        calc = Octopus(dirname)

        with open_section('section_basis_set_cell_dependent') as basis_set_cell_dependent_gid:
            pew.addValue('basis_set_cell_dependent_kind', 'realspace_grids')
            # How does nomad want grid spacing?

        nbands = calc.get_number_of_bands()
        nspins = calc.get_number_of_spins()
        nkpts = len(calc.get_k_point_weights())

        if logfile is None:
            # print('No stdout logfile found', file=fd)
            logging.debug('No stdout logfile found')
        else:
            # print('Found stdout logfile %s' % logfile, file=fd)
            logging.debug('Found stdout logfile %s' % logfile)
            # print('Parse logfile %s' % logfile, file=fd)
            logging.debug('Parse logfile %s' % logfile)
            parse_logfile(metaInfoEnv, pew, logfile)

        # print('Add parsed values', file=fd)
        with open_section('section_system') as system_gid:
            gridinfo = parse_gridinfo(metaInfoEnv, pew, fname)
            cell_unit = gridinfo['unit']
            if 'cell' in gridinfo:
                cell = gridinfo['cell']
                if cell_unit == 'A':
                    cell /= Bohr  # cell guaranteed to be Bohr now
                else:
                    assert cell_unit == 'b'
                pew.addArrayValues('simulation_cell',
                                   convert_unit(cell, 'bohr'))

            # We will get the positions from the parser log.
            # It is the only "practical" way.
            coordinfo = parse_coordinates_from_parserlog(parser_log_path)
            atoms = None
            coords = None

            # Old versions allow this abomination.
            if kwargs.get('unitsinput', kwargs.get('units')) == 'ev_angstrom':
                input_units = 'angstrom'
            else:
                input_units = 'bohr'

            parent_dir, _ = os.path.split(fname)
            inpdir = parent_dir
            # try to read files from the same or parent directory
            while True:
                try:
                    if 'PDBCoordinates' in coordinfo:
                        atoms = read(os.path.join(inpdir, coordinfo['PDBCoordinates']), format='proteindatabank')
                    elif 'XYZCoordinates' in coordinfo:
                        atoms = read(os.path.join(inpdir, coordinfo['XYZCoordinates']), format='xyz')
                    elif 'XSFCoordinates' in coordinfo:
                        if 'XSFCoordinatesAnimStep' in coordinfo:
                            assert 0  # XXX read correct step.  Take 1-indexation into account
                        atoms = read(os.path.join(inpdir, coordinfo['XSFCoordinates']), format='xsf')
                    elif 'coords' in coordinfo:
                        coords = coordinfo['coords']
                        if input_units == 'angstrom':
                            coords /= Bohr
                    elif 'rcoords' in coordinfo:
                        # unit will be Bohr cf. handling of cell above
                        coords = np.dot(coordinfo['rcoords'], cell)
                except FileNotFoundError as e:
                    if inpdir == parent_dir:
                        inpdir, _ = os.path.split(inpdir)
                    else:
                        raise e
                else:
                    break

            if atoms is not None:
                coords = atoms.positions / Bohr

            assert coords is not None, 'Cannot find coordinates'
            labels = coordinfo.get('labels')
            if labels is None:
                labels = np.array(atoms.get_chemical_symbols())

            pbc = np.zeros(3)

            if 'npbc' in gridinfo:
                pbc = np.zeros(3, bool)
                pbc[:gridinfo['npbc']] = True
                pew.addArrayValues('configuration_periodic_dimensions', pbc)

            pew.addArrayValues('atom_labels', labels)
            pew.addArrayValues('atom_positions', convert_unit(coords, 'bohr'))

            # XXX FIXME atoms can be labeled in ways not compatible with ASE.
            #pew.addArrayValues('atom_labels',
            #                   np.array(atoms.get_chemical_symbols()))
            #pew.addArrayValues('atom_positions',
            #                   convert_unit(atoms.get_positions(), 'angstrom'))
            #pew.addArrayValues('configuration_periodic_dimensions',
            #                   np.array(atoms.pbc))

        with open_section('section_single_configuration_calculation'):
            pew.addValue('single_configuration_calculation_to_system_ref',
                         system_gid)
            # print('Parse info file %s' % fname, file=fd)
            logging.debug('Parse info file %s' % fname)
            parse_infofile(metaInfoEnv, pew, fname)

            with open_section('section_method') as method_gid:
                for basis_set_kind in ['density', 'wavefunction']:
                    with open_section('section_method_basis_set'):
                        pew.addValue('method_basis_set_kind', basis_set_kind)
                        pew.addValue('mapping_section_method_basis_set_cell_associated',
                                     basis_set_cell_dependent_gid)
                #smearing_width = float(kwargs.get('smearing', 0.0))
                #pew.addValue('smearing_width',
                #             convert_unit(smearing_width, ENERGY_UNIT))
                # XXX remember to get smearing width somehow
                smearing_func = kwargs.get('smearingfunction',
                                           'semiconducting')
                smearing_kinds = {'semiconducting': 'empty',
                                  'spline_smearing': 'gaussian',
                                  # Note: spline and Gaussian are only
                                  # nearly identical.  See:
                                  # oct-help --print SmearingFunction
                                  'fermi_dirac': 'fermi',
                                  'cold_smearing': 'marzari-vanderbilt',
                                  'methfessel_paxton': 'methfessel-paxton'}
                                  #'': 'tetrahedra',

                pew.addValue('smearing_kind',
                             smearing_kinds[smearing_func])

                pew.addValue('number_of_spin_channels', nspins)
                pew.addValue('total_charge',
                             float(parser_log_kwargs['excesscharge']))
                oct_theory_level = kwargs.get('theorylevel', 'dft')

                theory_levels = dict(independent_particles='independent_particles',  # not defined by Nomad
                                     hartree='Hartree',  # not defined by Nomad
                                     hartree_fock='DFT',  # nomad wants it that way
                                     dft='DFT',
                                     classical='Classical',  # Not defined by Nomad
                                     rdmft='RDMFT')  # Not defined by Nomad
                # TODO how do we warn if we get an unexpected theory level?
                # Currently: KeyError
                nomad_theory_level = theory_levels[oct_theory_level]

                pew.addValue('electronic_structure_method', nomad_theory_level)

                if oct_theory_level == 'dft':
                    ndim = int(kwargs.get('dimensions', 3))
                    assert ndim in range(1, 4), ndim
                    default_xc = ['lda_x_1d + lda_c_1d_csc',
                                  'lda_x_2d + lda_c_2d_amgb',
                                  'lda_x + lda_c_pz_mod'][ndim - 1]
                    xcfunctional = kwargs.get('xcfunctional', default_xc)
                    for functional in xcfunctional.split('+'):
                        functional = functional.strip().upper()
                        with open_section('section_XC_functionals'):
                            pew.addValue('XC_functional_name', functional)

                forces = calc.results.get('forces')
                if forces is not None:
                    pew.addArrayValues('atom_forces_free_raw',
                                       convert_unit(forces, 'eV'))
                # Convergence parameters?

            pew.addValue('single_configuration_to_calculation_method_ref',
                         method_gid)

            with open_section('section_eigenvalues'):
                if kwargs.get('theorylevel', 'dft') == 'dft':
                    pew.addValue('eigenvalues_kind', 'normal')

                kpts = calc.get_ibz_k_points()
                assert len(kpts) == nkpts
                pew.addValue('number_of_eigenvalues_kpoints', nkpts)

                eig = np.zeros((nspins, nkpts, nbands))
                occ = np.zeros((nspins, nkpts, nbands))

                for s in range(nspins):
                    for k in range(nkpts):
                        eig[s, k, :] = calc.get_eigenvalues(kpt=k, spin=s)
                        occ[s, k, :] = calc.get_occupation_numbers(kpt=k,
                                                                   spin=s)
                pew.addArrayValues('eigenvalues_kpoints', kpts)
                pew.addArrayValues('eigenvalues_values',
                                   convert_unit(eig, 'eV'))
                pew.addArrayValues('eigenvalues_occupation', occ)

    pew.finishedParsingSession('ParseSuccess', None)
    return backend


class OctopusParserWrapper():
    """ A proper class envolop for running this parser using Noamd-FAIRD infra. """
    def __init__(self, backend, **kwargs):
        self.backend_factory = backend

    def parse(self, mainfile):
        logging.info('octopus parser started')
        logging.getLogger('nomadcore').setLevel(logging.WARNING)
        backend = self.backend_factory("octopus.nomadmetainfo.json")

        # We need access to this information because we want/need to dynamically convert
        # extracted metadata to its correct type.  Thus we need to know the type.
        # Also since input is case insensitive, we need to convert normalized (lowercase)
        # metadata names to their real names which are normally CamelCase.
        global metaInfoEnv
        if metaInfoEnv is None:
            metaInfoEnv = backend.metaInfoEnv()
            metaInfoKinds = metaInfoEnv.infoKinds.copy()
            all_metadata_names = list(metaInfoKinds.keys())
            global normalized2real
            normalized2real = dict(zip(normalize_names(all_metadata_names), all_metadata_names))

        # Call the old parser without a class.
        parserInfo = parser_info
        backend = parse_without_class(mainfile, backend, parserInfo)
        return backend


if __name__ == '__main__':
    fname = sys.argv[1]
    logfname = 'parse.log'
    with open(logfname, 'w') as fd:
        parse(fname, fd)
