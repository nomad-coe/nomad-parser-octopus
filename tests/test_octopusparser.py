#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import pytest
import numpy as np

from nomad.datamodel import EntryArchive
from octopusparser import OctopusParser


def approx(value, abs=0, rel=1e-6):
    return pytest.approx(value, abs=abs, rel=rel)


@pytest.fixture(scope='module')
def parser():
    return OctopusParser()


def test_scf(parser):
    archive = EntryArchive()
    parser.parse('tests/data/Si_scf/stdout.txt', archive, None)

    sec_run = archive.section_run[0]
    assert sec_run.program_version == 'wolfi'
    assert sec_run.x_octopus_input_Spacing == approx(0.28345892)
    assert sec_run.x_octopus_parserlog_SpeciesProjectorSphereThreshold == 0.001

    sec_method = sec_run.section_method[0]
    assert sec_method.smearing_kind == 'empty'
    assert sec_method.electronic_structure_method == 'DFT'
    assert sec_method.section_XC_functionals[0].XC_functional_name == 'LDA_C_PZ_MOD'

    sec_system = sec_run.section_system[0]
    assert False not in sec_system.configuration_periodic_dimensions
    assert sec_system.atom_labels == ['Si', 'Si', 'Si', 'Si']
    assert sec_system.atom_positions[1][0].magnitude == approx(1.91979671e-10)

    sec_scc = sec_run.section_single_configuration_calculation[0]
    assert sec_scc.energy_total.magnitude == approx(-6.91625667e-17)
    assert sec_scc.energy_electrostatic.magnitude == approx(4.79087203e-18)
    assert np.count_nonzero(sec_scc.atom_forces_free_raw) == 0
    sec_eig = sec_scc.eigenvalues[0]
    assert np.shape(sec_eig.band_energies[17].value) == (8,)
    assert sec_eig.kpoints[11][2] == 0.25
    assert sec_eig.band_energies[4].value[6].magnitude == approx(5.26639723e-19)
    assert sec_eig.band_energies[16].occupations[1] == 2.0
    sec_scf = sec_scc.section_scf_iteration
    assert len(sec_scf) == 8
    assert sec_scf[3].energy_total_scf_iteration.magnitude == approx(-6.91495422e-17)
    assert sec_scf[7].time_scf_iteration.magnitude == 9.42


def test_spinpol(parser):
    archive = EntryArchive()
    parser.parse('tests/data/Fe_spinpol/stdout.txt', archive, None)

    assert archive.section_run[0].x_octopus_parserlog_SpinComponents == '2'
    assert archive.section_run[0].x_octopus_input_Units == 'ev_angstrom'
    assert archive.section_run[0].x_octopus_parserlog_PreconditionerFilterFactor == 0.6

    sec_scc = archive.section_run[0].section_single_configuration_calculation[0]
    assert sec_scc.energy_reference_fermi[0].magnitude == approx(7.39160185e-19)
    sec_eig = sec_scc.eigenvalues[0]
    assert np.shape(sec_eig.band_energies[19].value) == (20,)
    assert sec_eig.band_energies[15].value[4].magnitude == approx(-7.40576381e-18)
    assert sec_eig.kpoints[9][0] == 0.5
    assert sec_eig.band_energies[1].occupations[17] == 0.972222
    sec_scfs = sec_scc.section_scf_iteration
    assert sec_scfs[0].energy_total_scf_iteration.magnitude == approx(-1.02450582e-15)
    assert sec_scfs[5].energy_reference_fermi_iteration[0].magnitude == approx(7.85685151e-19)
    assert sec_scfs[8].time_scf_iteration.magnitude == 15.63


def test_geomopt(parser):
    # cannot find example
    pass


def test_td(parser):
    # cannot find example
    pass
