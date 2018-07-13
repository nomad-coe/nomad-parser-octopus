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

# coding = utf-8

"""This module is written by

  Ask Hjorth Larsen <asklarsen@gmail.com>
  Carlos de Armas
"""

import os
import re
from subprocess import Popen, PIPE

import numpy as np

from ase import Atoms
from ase.calculators.calculator import FileIOCalculator
from ase.data import atomic_numbers
from ase.io import read
from ase.io.xsf import read_xsf
from ase.units import Bohr, Angstrom, Hartree, eV, Debye


def read_eigenvalues_file(fd):
    unit = None

    for line in fd:
        m = re.match('Eigenvalues\s*\[(.+?)\]', line)
        if m is not None:
            unit = m.group(1)
            break
    line = next(fd)
    assert line.strip().startswith('#st'), line

    kpts = []
    eigs = []
    occs = []

    for line in fd:
        m = re.match(r'#k.*?\(\s*(.+?),\s*(.+?),\s*(.+?)\)', line)
        if m:
            k = m.group(1, 2, 3)
            kpts.append(np.array(k, float))
            eigs.append({})
            occs.append({})
        else:
            m = re.match(r'\s*\d+\s*(\S+)\s*(\S+)\s*(\S+)', line)
            assert m is not None
            spin, eig, occ = m.group(1, 2, 3)
            eigs[-1].setdefault(spin, []).append(float(eig))
            occs[-1].setdefault(spin, []).append(float(occ))


    nkpts = len(kpts)
    nspins = len(eigs[0])
    nbands = len(eigs[0][spin])

    kptsarr = np.array(kpts, float)
    eigsarr = np.empty((nkpts, nspins, nbands))
    occsarr = np.empty((nkpts, nspins, nbands))

    arrs = [eigsarr, occsarr]

    for arr in arrs:
        arr.fill(np.nan)

    for k in range(nkpts):
        for arr, lst in [(eigsarr, eigs), (occsarr, occs)]:
            arr[k, :, :] = [lst[k][spin] for spin
                            in (['--'] if nspins == 1 else ['up', 'dn'])]

    for arr in arrs:
        assert not np.isnan(arr).any()

    eigsarr *= {'H': Hartree, 'eV': eV}[unit]
    return kptsarr, eigsarr, occsarr


class OctopusIOError(IOError):
    pass  # Cannot find output files


def unpad(pbc, arr):
    # Return non-padded array from padded array.
    # This means removing the last element along all periodic directions.
    if pbc[0]:
        assert np.all(arr[0, :, :] == arr[-1, :, :])
        arr = arr[0:-1, :, :]
    if pbc[1]:
        assert np.all(arr[:, 0, :] == arr[:, -1, :])
        arr = arr[:, 0:-1, :]
    if pbc[2]:
        assert np.all(arr[:, :, 0] == arr[:, :, -1])
        arr = arr[:, :, 0:-1]
    return np.ascontiguousarray(arr)


# Parse value as written in input file *or* something that one would be
# passing to the ASE interface, i.e., this might already be a boolean
def octbool2bool(value):
    value = value.lower()
    if isinstance(value, int):
        return bool(value)
    if value in ['true', 't', 'yes', '1']:
        return True
    elif value in ['no', 'f', 'false', '0']:
        return False
    else:
        raise ValueError('Failed to interpret "%s" as a boolean.' % value)


def list2block(name, rows):
    """Construct 'block' of Octopus input.

    convert a list of rows to a string with the format x | x | ....
    for the octopus input file"""
    lines = []
    lines.append('%' + name)
    for row in rows:
        lines.append(' ' + ' | '.join(str(obj) for obj in row))
    lines.append('%')
    return lines


def normalize_keywords(kwargs):
    """Reduce keywords to unambiguous form (lowercase)."""
    newkwargs = {}
    for arg, value in kwargs.items():
        lkey = arg.lower()
        newkwargs[lkey] = value
    return newkwargs


def get_octopus_keywords():
    """Get dict mapping all normalized keywords to pretty keywords."""
    proc = Popen(['oct-help', '--search', ''], stdout=PIPE)
    keywords = proc.stdout.read().decode().split()
    return normalize_keywords(dict(zip(keywords, keywords)))


def input_line_iter(lines):
    """Convenient iterator for parsing input files 'cleanly'.

    Discards comments etc."""
    for line in lines:
        line = line.split('#')[0].strip()
        if not line or line.isspace():
            continue
        line = line.strip()
        yield line


def block2list(namespace, lines, header=None):
    """Parse lines of block and return list of lists of strings."""
    lines = iter(lines)
    block = []
    if header is None:
        header = next(lines)
    assert header.startswith('%'), header
    name = header[1:].strip().lower()
    for line in lines:
        if line.startswith('%'):  # Could also say line == '%' most likely.
            break
        tokens = [namespace.evaluate(token)
                  for token in line.strip().split('|')]
        # XXX will fail for string literals containing '|'
        block.append(tokens)
    return name, block

class OctNamespace:
    def __init__(self):
        self.names = {}
        self.consts = {'pi': np.pi,
                       'angstrom': 1. / Bohr,
                       'ev': 1. / Hartree,
                       'yes': True,
                       'no': False,
                       't': True,
                       'f': False,
                       'i': 1j,  # This will probably cause trouble
                       'true': True,
                       'false': False}

    def evaluate(self, value):
        orig = value
        value = value.strip()

        for char in '"', "'":  # String literal
            if value.startswith(char):
                assert value.endswith(char)
                return value

        value = value.lower()

        if value in self.consts:  # boolean or other constant
            return self.consts[value]

        if value in self.names:  # existing variable
            return self.names[value]

        try:  # literal integer
            v = int(value)
        except ValueError:
            pass
        else:
            if v == float(v):
                return v

        try:  # literal float
            return float(value)
        except ValueError:
            pass

        if ('*' in value or '/' in value
            and not any(char in value for char in '()+')):
            floatvalue = 1.0
            op = '*'
            for token in re.split(r'([\*/])', value):
                if token in '*/':
                    op = token
                    continue

                v = self.evaluate(token)

                try:
                    v = float(v)
                except TypeError:
                    try:
                        v = complex(v)
                    except ValueError:
                        break
                except ValueError:
                    break  # Cannot evaluate expression
                else:
                    if op == '*':
                        floatvalue *= v
                    else:
                        assert op == '/', op
                        floatvalue /= v
            else:  # Loop completed successfully
                return floatvalue
        return value  # unknown name, or complex arithmetic expression

    def add(self, name, value):
        value = self.evaluate(value)
        self.names[name.lower().strip()] = value


def parse_input_file(fd):
    namespace = OctNamespace()
    lines = input_line_iter(fd)
    blocks = {}
    while True:
        try:
            line = next(lines)
        except StopIteration:
            break
        else:
            if line.startswith('%'):
                name, value = block2list(namespace, lines, header=line)
                blocks[name] = value
            else:
                tokens = line.split('=', 1)
                assert len(tokens) == 2, tokens
                name, value = tokens
                namespace.add(name, value)

    namespace.names.update(blocks)
    return namespace.names


def read_static_info_kpoints(fd):
    for line in fd:
        if line.startswith('List of k-points'):
            break

    tokens = next(fd).split()
    assert tokens == ['ik', 'k_x', 'k_y', 'k_z', 'Weight']
    bar = next(fd)
    assert bar.startswith('---')

    kpts = []
    weights = []

    for line in fd:
        # Format:        index   kx      ky      kz     weight
        m = re.match(r'\s*\d+\s*(\S+)\s*(\S+)\s*(\S+)\s*(\S+)', line)
        if m is None:
            break
        kxyz = m.group(1, 2, 3)
        weight = m.group(4)
        kpts.append(kxyz)
        weights.append(weight)

    ibz_k_points = np.array(kpts, float)
    k_point_weights = np.array(weights, float)
    return dict(ibz_k_points=ibz_k_points, k_point_weights=k_point_weights)


def read_static_info_eigenvalues(fd, energy_unit):

    values_sknx = {}

    nbands = 0
    for line in fd:
        line = line.strip()
        if line.startswith('#'):
            continue
        if not line[:1].isdigit():
            break

        tokens = line.split()
        nbands = max(nbands, int(tokens[0]))
        energy = float(tokens[2]) * energy_unit
        occupation = float(tokens[3])
        values_sknx.setdefault(tokens[1], []).append((energy, occupation))

    nspins = len(values_sknx)
    if nspins == 1:
        val = [values_sknx['--']]
    else:
        val = [values_sknx['up'], values_sknx['dn']]
    val = np.array(val).astype(float)
    nkpts, remainder = divmod(len(val[0]), nbands)
    assert remainder == 0

    eps_skn = val[:, :, 0].reshape(nspins, nkpts, nbands)
    occ_skn = val[:, :, 1].reshape(nspins, nkpts, nbands)
    eps_skn = eps_skn.transpose(1, 0, 2).copy()
    occ_skn = occ_skn.transpose(1, 0, 2).copy()
    assert eps_skn.flags.contiguous
    return dict(nspins=nspins,
                nkpts=nkpts,
                nbands=nbands,
                eigenvalues=eps_skn,
                occupations=occ_skn)


def read_static_info_energy(fd, energy_unit):
    def get(name):
        for line in fd:
            if line.strip().startswith(name):
                return float(line.split('=')[-1].strip()) * energy_unit
    return dict(energy=get('Total'), free_energy=get('Free'))


def read_static_info(fd):
    results = {}

    def get_energy_unit(line):  # Convert "title [unit]": ---> unit
        return {'[eV]': eV, '[H]': Hartree}[line.split()[1].rstrip(':')]

    for line in fd:
        if line.strip('*').strip().startswith('Brillouin zone'):
            results.update(read_static_info_kpoints(fd))
        elif line.startswith('Eigenvalues ['):
            unit = get_energy_unit(line)
            results.update(read_static_info_eigenvalues(fd, unit))
        elif line.startswith('Energy ['):
            unit = get_energy_unit(line)
            results.update(read_static_info_energy(fd, unit))
        elif line.startswith('Total Magnetic Moment'):
            if 0:
                line = next(fd)
                values = line.split()
                results['magmom'] = float(values[-1])

                line = next(fd)
                assert line.startswith('Local Magnetic Moments')
                line = next(fd)
                assert line.split() == ['Ion', 'mz']
                # Reading  Local Magnetic Moments
                mag_moment = []
                for line in fd:
                    if line == '\n':
                        break  # there is no more thing to search for
                    line = line.replace('\n', ' ')
                    values = line.split()
                    mag_moment.append(float(values[-1]))

                results['magmoms'] = np.array(mag_moment)
        elif line.startswith('Dipole'):
            assert line.split()[-1] == '[Debye]'
            dipole = [float(next(fd).split()[-1]) for i in range(3)]
            results['dipole'] = np.array(dipole) * Debye
        elif line.startswith('Forces'):
            forceunitspec = line.split()[-1]
            forceunit = {'[eV/A]': eV / Angstrom,
                         '[H/b]': Hartree / Bohr}[forceunitspec]
            forces = []
            line = next(fd)
            assert line.strip().startswith('Ion')
            for line in fd:
                if line.strip().startswith('---'):
                    break
                tokens = line.split()[-3:]
                forces.append([float(f) for f in tokens])
            results['forces'] = np.array(forces) * forceunit
        elif line.startswith('Fermi'):
            tokens = line.split()
            unit = {'eV': eV, 'H': Hartree}[tokens[-1]]
            eFermi = float(tokens[-2]) * unit
            results['efermi'] = eFermi

    if 'ibz_k_points' not in results:
        results['ibz_k_points'] = np.zeros((1, 3))
        results['k_point_weights'] = np.ones(1)
    if 'efermi' not in results:
        # Find HOMO level.  Note: This could be a very bad
        # implementation with fractional occupations if the Fermi
        # level was not found otherwise.
        all_energies = results['eigenvalues'].ravel()
        all_occupations = results['occupations'].ravel()
        args = np.argsort(all_energies)
        for arg in args[::-1]:
            if all_occupations[arg] > 0.1:
                break
        eFermi = all_energies[arg]
        results['efermi'] = eFermi

    return results


class Octopus(FileIOCalculator):
    def __init__(self, restart):
        self.kwargs = {}

        FileIOCalculator.__init__(self, restart=restart, label=restart)
        # The above call triggers set() so we can update self.kwargs.

    def set_label(self, label):
        # Octopus does not support arbitrary namings of all the output files.
        # But we can decide that we always dump everything in a directory.
        if not label.endswith('/'):
            label += '/'
        FileIOCalculator.set_label(self, label)

    def set(self, **kwargs):
        """Set octopus input file parameters."""
        kwargs = normalize_keywords(kwargs)

        changes = FileIOCalculator.set(self, **kwargs)
        if changes:
            self.results.clear()
        self.kwargs.update(kwargs)
        # XXX should use 'Parameters' but don't know how

    def get_xc_functional(self):
        """Return the XC-functional identifier.
            'LDA', 'PBE', ..."""
        return self.kwargs.get('xcfunctional', 'LDA')

    def get_fermi_level(self):
        return self.results['efermi']

    def get_dipole_moment(self, atoms=None):
        if 'dipole' not in self.results:
            msg = ('Dipole moment not calculated.\n'
                   'You may wish to use SCFCalculateDipole=True')
            raise OctopusIOError(msg)
        return self.results['dipole']

    def _read_array(self, fname, outputkeyword=None):
        path = self._getpath('static/%s' % fname)
        if not os.path.exists(path):
            msg = 'Path not found: %s' % path
            if outputkeyword is not None:
                msg += ('\nIt appears that the %s has not been saved.\n'
                        'Be sure to specify Output=\'%s\' in the input.'
                        % (outputkeyword, outputkeyword))
            raise OctopusIOError(msg)
        # If this causes an error now that the file exists, things are
        # messed up.  Then it is better that the error propagates as normal
        return read_xsf(path, read_data=True)

    def read_vn(self, basefname, keywordname):
        static_dir = self._getpath('static')
        assert os.path.isdir(static_dir)

        if self.get_spin_polarized():
            spin1, _atoms = self._read_array('%s-sp1.xsf' % basefname,
                                             keywordname)
            spin2, _atoms = self._read_array('%s-sp2.xsf' % basefname,
                                             keywordname)
            array = np.array([spin1, spin2])  # shape 2, nx, ny, nz
        else:
            array, _atoms = self._read_array('%s.xsf' % basefname, keywordname)
            array = array[None]  # shape 1, nx, ny, nx
        assert len(array.shape) == 4
        return array

    def _unpad_periodic(self, array):
        return unpad(self.get_atoms().pbc, array)

    def _pad_unperiodic(self, array):
        pbc = self.get_atoms().pbc
        orig_shape = array.shape
        newshape = [orig_shape[c] + (0 if pbc[c] else 1) for c in range(3)]
        out = np.zeros(newshape, dtype=array.dtype)
        nx, ny, nz = orig_shape
        out[:nx, :ny, :nz] = array
        return out

    def _pad_correctly(self, array, pad):
        array = self._unpad_periodic(array)
        if pad:
            array = self._pad_unperiodic(array)
        return array

    def get_pseudo_density(self, spin=None, pad=True):
        """Return pseudo-density array.

        If *spin* is not given, then the total density is returned.
        Otherwise, the spin up or down density is returned (spin=0 or
        1)."""
        if 'density_sg' not in self.results:
            self.results['density_sg'] = self.read_vn('density', 'density')
        density_sg = self.results['density_sg']
        if spin is None:
            density_g = density_sg.sum(axis=0)
        else:
            assert spin == 0 or (spin == 1 and len(density_sg) == 2)
            density_g = density_sg[spin]
        return self._pad_correctly(density_g, pad)

    def get_effective_potential(self, spin=0, pad=True):
        if spin is None:  # Annoying case because it works as an index!
            raise ValueError('spin=None')
        if 'potential_sg' not in self.results:
            self.results['potential_sg'] = self.read_vn('vks', 'potential')
        array = self.results['potential_sg'][spin]
        return self._pad_correctly(array, pad)

    def get_pseudo_wave_function(self, band=0, kpt=0, spin=0, broadcast=True,
                                 pad=True):
        """Return pseudo-wave-function array."""
        assert band < self.get_number_of_bands()

        ibz_k_pts = self.get_ibz_k_points()

        forcecomplex = self.kwargs.get('forcecomplex')
        if forcecomplex is not None:
            forcecomplex = octbool2bool(forcecomplex)
        if len(ibz_k_pts) > 1 or ibz_k_pts.any() or forcecomplex:
            dtype = complex
        else:
            dtype = float  # Might there be more issues that determine dtype?

        if self.get_spin_polarized():
            kpt_index = 2 * kpt + spin  # XXX this is *probably* correct
        else:
            kpt_index = kpt

        # The ASE convention is that kpts and bands start from 0,
        # whereas in Octopus they start from 1.  So always add 1
        # when looking for filenames.
        kpt_index += 1
        band_index = band + 1

        tokens = ['wf']
        if len(ibz_k_pts) > 1 or self.get_spin_polarized():
            tokens.append('-k%03d' % kpt_index)
        tokens.append('-st%04d' % band_index)
        name = ''.join(tokens)

        if dtype == float:
            array, _atoms = self._read_array('%s.xsf' % name, 'wfs')
        else:
            array_real, _atoms = self._read_array('%s.real.xsf' % name, 'wfs')
            array_imag, _atoms = self._read_array('%s.imag.xsf' % name, 'wfs')
            array = array_real + 1j * array_imag

        return self._pad_correctly(array, pad)

    def get_number_of_spins(self):
        """Return the number of spins in the calculation.
           Spin-paired calculations: 1, spin-polarized calculation: 2."""
        return 2 if self.get_spin_polarized() else 1

    def get_spin_polarized(self):
        """Is it a spin-polarized calculation?"""

        sc = self.kwargs.get('spincomponents')
        if sc is None or sc == 'unpolarized' or sc == 'spinors':
            return False
        elif sc == 'spin_polarized' or sc == 'polarized':
            return True
        #else:
        #    raise NotImplementedError('SpinComponents keyword %s' % sc)

    def get_ibz_k_points(self):
        """Return k-points in the irreducible part of the Brillouin zone.
        The coordinates are relative to reciprocal latice vectors."""
        return self.results['ibz_k_points']

    def get_k_point_weights(self):
        return self.results['k_point_weights']

    def get_number_of_bands(self):
        return self.results['nbands']

    def get_magnetic_moments(self, atoms=None):
        if self.results['nspins'] == 1:
            return np.zeros(len(self.atoms))
        return self.results['magmoms'].copy()

    def get_magnetic_moment(self, atoms=None):
        if self.results['nspins'] == 1:
            return 0.0
        return self.results['magmom']

    def get_occupation_numbers(self, kpt=0, spin=0):
        return self.results['occupations'][kpt, spin].copy()

    def get_eigenvalues(self, kpt=0, spin=0):
        return self.results['eigenvalues'][kpt, spin].copy()

    def _getpath(self, path, check=False):
        path = os.path.join(self.directory, path)
        if check:
            if not os.path.exists(path):
                raise OctopusIOError('No such file or directory: %s' % path)
        return path

    def read_results(self):
        """Read octopus output files and extract data."""
        fd = open(self._getpath('static/info', check=True))
        self.results.update(read_static_info(fd))

        # If the eigenvalues file exists, we get the eigs/occs from that one.
        # This probably means someone ran Octopus in 'unocc' mode to
        # get eigenvalues (e.g. for band structures), and the values in
        # static/info will be the old (selfconsistent) ones.
        try:
            eigpath = self._getpath('static/eigenvalues', check=True)
        except OctopusIOError:
            pass
        else:
            with open(eigpath) as fd:
                kpts, eigs, occs = read_eigenvalues_file(fd)
                kpt_weights = np.ones(len(kpts))  # XXX ?  Or 1 / len(kpts) ?
            self.results.update(eigenvalues=eigs, occupations=occs,
                                ibz_k_points=kpts,
                                k_point_weights=kpt_weights)

    def read(self, label):
        # XXX label of restart file may not be the same as actual label!
        # This makes things rather tricky.  We first set the label to
        # that of the restart file and arbitrarily expect the remaining code
        # to rectify any consequent inconsistencies.
        self.set_label(label)

        FileIOCalculator.read(self, label)
        inp_path = self._getpath('inp')
        fd = open(inp_path)
        kwargs = parse_input_file(fd)

        #self.atoms, kwargs = kwargs2atoms(kwargs)
        self.kwargs.update(kwargs)

        fd.close()
        self.read_results()
