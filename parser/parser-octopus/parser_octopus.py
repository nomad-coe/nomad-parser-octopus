from __future__ import print_function
import os
import sys
from glob import glob
from contextlib import contextmanager

import numpy as np
import ase.calculators.octopus as aseoct

import setup_paths
from nomadcore.local_meta_info import loadJsonFile, InfoKindEl
from nomadcore.parser_backend import JsonParseEventsWriterBackend
from nomadcore.unit_conversion.unit_conversion import convert_unit, \
    register_userdefined_quantity

from octopus_info_parser import parse_infofile
from octopus_logfile_parser import parse_logfile

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


def normalize_names(names):
    return [name.lower() for name in names]


OCT_ENERGY_UNIT_NAME = 'usrOctEnergyUnit'
OCT_LENGTH_UNIT_NAME = 'usrOctLengthUnit'

metaInfoPath = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../../../nomad-meta-info/meta_info/nomad_meta_info/octopus.nomadmetainfo.json"))
metaInfoEnv, warnings = loadJsonFile(filePath=metaInfoPath,
                                     dependencyLoader=None,
                                     extraArgsHandling=InfoKindEl.ADD_EXTRA_ARGS,
                                     uri=None)

# Dictionary of all meta info:
metaInfoKinds = metaInfoEnv.infoKinds.copy()
all_metadata_names = list(metaInfoKinds.keys())
normalized2real = dict(zip(normalize_names(all_metadata_names), all_metadata_names))
# We need access to this information because we want/need to dynamically convert
# extracted metadata to its correct type.  Thus we need to know the type.
# Also since input is case insensitive, we need to convert normalized (lowercase)
# metadata names to their real names which are normally CamelCase.


parserInfo = {
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
                #print(name)
            # Octopus questionably writes this one twice
            #if name != 'speciesprojectorspherethreshold':
            exec_kwargs[name] = value
    return exec_kwargs


def read_input_file(path):
    with open(path) as fd:
        names, values = aseoct.parse_input_file(fd)
    names = normalize_names(names)

    kwargs = {}
    for name, value in zip(names, values):
        kwargs[name] = value
    return kwargs


def is_octopus_logfile(fname):
    fd = open(fname)
    for lineno in range(20):
        line = fd.next()
        if '|0) ~ (0) |' in line:  # Eyes from Octopus logo
            return True
    return False


def find_octopus_logfile(dirname):
    allfnames = glob('%s/*' % dirname)
    for fname in allfnames:
        if os.path.isfile(fname) and is_octopus_logfile(fname):
            return fname
    return None


def override_keywords(kwargs, parser_log_kwargs, fd):
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
        if name in kwargs:
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

            print('Keyword %s with value %s overridden by value '
                  '%s obtained from parser log'
                  % (name, kwargs[name], parser_log_kwargs[name]),
                  file=fd)

            outkwargs[name] = parser_log_kwargs[name]
    return outkwargs


def register_units(kwargs, fd):
    units = kwargs.get('units', 'atomic').lower()
    if units == 'atomic':
        length_unit = 'bohr'
        energy_unit = 'hartree'
    elif units == 'ev_angstrom':
        length_unit = 'angstrom'
        energy_unit = 'eV'
    else:
        raise ValueError('Unknown units: %s' % units)

    if 'unitsinput' in kwargs:
        raise ValueError('UnitsInput not supported')
    if 'unitsoutput' in kwargs:
        raise ValueError('UnitsOutput not supported')

    print('Set units: energy=%s, length=%s' % (energy_unit, length_unit),
          file=fd)
    register_userdefined_quantity(OCT_ENERGY_UNIT_NAME, energy_unit)
    register_userdefined_quantity(OCT_LENGTH_UNIT_NAME, length_unit)


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
        name, value = regularize_metadata_entry(normalized_name, kwargs[keyword])
        pew.addValue(name, value)


def parse(fname, fd):
    # fname refers to the static/info file.
    pew = JsonParseEventsWriterBackend(metaInfoEnv,
                                       fileOut=open('json-writer.log', 'w'))

    # this context manager shamelessly copied from GPAW parser
    # Where should Python code be put if it is used by multiple parsers?
    @contextmanager
    def open_section(name):
        gid = pew.openSection(name)
        yield
        pew.closeSection(name, gid)

    with open_section('section_run'):
        pew.addValue('program_name', 'Octopus')
        print(file=fd)

        staticdirname, _basefname = os.path.split(fname)
        dirname, _static = os.path.split(staticdirname)
        inp_path = os.path.join(dirname, 'inp')
        parser_log_path = os.path.join(dirname, 'exec', 'parser.log')

        print('Read Octopus keywords from input file %s' % inp_path,
              file=fd)
        kwargs = read_input_file(inp_path)
        register_octopus_keywords(pew, 'input', kwargs)

        print('Read processed Octopus keywords from octparse logfile %s'
              % parser_log_path, file=fd)
        parser_log_kwargs = read_parser_log(parser_log_path)
        register_octopus_keywords(pew, 'parserlog', parser_log_kwargs)

        print('Override certain keywords with processed keywords', file=fd)
        kwargs = override_keywords(kwargs, parser_log_kwargs, fd)

        register_units(kwargs, fd)

        print('Read as ASE calculator', file=fd)
        calc = aseoct.Octopus(dirname)
        atoms = calc.get_atoms()

        #with open_section('section_basis_set_cell_dependent'):
            # XXX FIXME spacing can very rarely be 3 numbers!
            # uuh there is no meaningful way to set grid spacing
        #    pass
        cubefiles = glob('staticdirname/*.cube')
        cubefiles.sort()

        nbands = calc.get_number_of_bands()
        nspins = calc.get_number_of_spins()
        nkpts = len(calc.get_k_point_weights())

        print('Parse info file using SimpleMatcher', file=fd)
        parse_infofile(metaInfoEnv, pew, fname)

        logfile = find_octopus_logfile(dirname)
        if logfile is None:
            print('No stdout logfile found', file=fd)
        else:
            print('Found stdout logfile %s' % logfile, file=fd)
            print('Parse logfile using SimpleMatcher', file=fd)
            parse_logfile(metaInfoEnv, pew, logfile)

        print('Add parsed values', file=fd)
        with open_section('section_system'):
            # The Atoms object will always have a cell, even if it was not
            # used in the Octopus calculation!  Thus, to be more honest,
            # we re-extract the cell at a level where we can distinguish:
            cell, _unused = aseoct.kwargs2cell(kwargs)
            if cell is not None:
                pew.addArrayValues('simulation_cell', cell)

            # XXX FIXME atoms can be labeled in ways not compatible with ASE.
            pew.addArrayValues('atom_labels',
                               np.array(atoms.get_chemical_symbols()))
            pew.addArrayValues('atom_positions',
                               convert_unit(atoms.get_positions(), 'angstrom'))
            pew.addArrayValues('configuration_periodic_dimensions',
                               np.array(atoms.pbc))
        with open_section('section_single_configuration_calculation'):
            with open_section('section_method'):
                pew.addValue('number_of_spin_channels', nspins)
                pew.addValue('total_charge',
                             float(parser_log_kwargs['excesscharge']))
                oct_theory_level = kwargs.get('theorylevel', 'dft')

                theory_levels = dict(#independent_particles='',
                                     #hartree='',
                                     #hartree_fock='',
                                     dft='DFT')
                                     #classical='',
                                     #rdmft='')
                # TODO how do we warn if we get an unexpected theory level?
                nomad_theory_level = theory_levels[oct_theory_level]

                pew.addValue('electronic_structure_method', 'DFT')

                # XXXXXXXXXXXX read XC functional from text output instead
                if oct_theory_level == 'dft':
                    ndim = int(kwargs.get('dimensions', 3))
                    assert ndim in range(1, 4), ndim
                    default_xc = ['lda_x_1d + lda_c_1d_csc',
                                  'lda_x_2d + lda_c_2d_amgb',
                                  'lda_x + lda_c_pz_mod'][ndim - 1]
                    xcfunctional = kwargs.get('xcfunctional', default_xc)
                    xcfunctional = ''.join(xcfunctional.split()).upper()
                    with open_section('section_XC_functionals'):
                        pew.addValue('XC_functional_name', xcfunctional)

                # Convergence parameters?

            with open_section('section_eigenvalues'):
                if kwargs.get('theorylevel', 'dft') == 'dft':
                    pew.addValue('eigenvalues_kind', 'normal')

                eig = np.zeros((nspins, nkpts, nbands))
                occ = np.zeros((nspins, nkpts, nbands))

                for s in range(nspins):
                    for k in range(nkpts):
                        eig[s, k, :] = calc.get_eigenvalues(kpt=k, spin=s)
                        occ[s, k, :] = calc.get_occupation_numbers(kpt=k,
                                                                   spin=s)
                pew.addArrayValues('eigenvalues_values',
                                   convert_unit(eig, 'eV'))
                pew.addArrayValues('eigenvalues_occupations', occ)


if __name__ == '__main__':
    fname = sys.argv[1]
    logfname = 'parse.log'
    with open(logfname, 'w') as fd:
        parse(fname, fd)
