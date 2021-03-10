#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD.
# See https://nomad-lab.eu for further info.
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
import numpy as np            # pylint: disable=unused-import
import typing                 # pylint: disable=unused-import
from nomad.metainfo import (  # pylint: disable=unused-import
    MSection, MCategory, Category, Package, Quantity, Section, SubSection, SectionProxy,
    Reference
)
from nomad.metainfo.legacy import LegacyDefinition

from nomad.datamodel.metainfo import public

m_package = Package(
    name='octopus_nomadmetainfo_json',
    description='None',
    a_legacy=LegacyDefinition(name='octopus.nomadmetainfo.json'))


class section_single_configuration_calculation(public.section_single_configuration_calculation):

    m_def = Section(validate=False, extends_base_section=True, a_legacy=LegacyDefinition(name='section_single_configuration_calculation'))

    x_octopus_info_energy_ion_ion = Quantity(
        type=np.dtype(np.float64),
        shape=[],
        unit='joule',
        description='''
        ion-ion interaction energy
        ''',
        a_legacy=LegacyDefinition(name='x_octopus_info_energy_ion_ion'))


class section_run(public.section_run):

    m_def = Section(validate=False, extends_base_section=True, a_legacy=LegacyDefinition(name='section_run'))

    x_octopus_info_scf_converged_iterations = Quantity(
        type=np.dtype(np.int32),
        shape=[],
        description='''
        number of scf iterations to converge calculation
        ''',
        a_legacy=LegacyDefinition(name='x_octopus_info_scf_converged_iterations'))

    x_octopus_log_svn_revision = Quantity(
        type=np.dtype(np.int32),
        shape=[],
        description='''
        octopus svn revision
        ''',
        a_legacy=LegacyDefinition(name='x_octopus_log_svn_revision'))


m_package.__init_metainfo__()
