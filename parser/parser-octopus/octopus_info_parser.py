from __future__ import print_function
from builtins import object
import logging
import setup_paths
from nomadcore.simple_parser import SimpleMatcher as SM
from nomadcore.local_meta_info import loadJsonFile, InfoKindEl
from nomadcore.unit_conversion.unit_conversion \
    import register_userdefined_quantity
import os, sys, json

from util import OCT_ENERGY_UNIT_NAME, f_num, i_num, numpattern, integer,\
    parse_file_without_decorations

# Match lines like: "      Total    =     -7.05183\n"
def oct_energy_sm(octname, nomadname):
    pattern = (r'\s*%(octname)s\s*=\s*%(pattern)s'
               % dict(octname=octname,
                      pattern=numpattern(nomadname,
                                         unit=OCT_ENERGY_UNIT_NAME)))
    #print 'oct energy sm', pattern
    return SM(pattern,
              name=octname)


sm_scfconv = SM(r'SCF converged in\s*%s\s*iterations'
                % integer('x_octopus_info_scf_converged_iterations'),
                sections=['section_run'])
sm_energy = SM(r'Energy \[(H|eV)\]:', required=True, name='energy_header',
               subMatchers=[
                   oct_energy_sm('Total', 'energy_total'),
                   oct_energy_sm('Free', 'energy_free'),
                   oct_energy_sm('Ion-ion', 'x_octopus_info_energy_ion_ion'),
                   oct_energy_sm('Eigenvalues', 'energy_sum_eigenvalues'),
                   oct_energy_sm('Hartree', 'energy_electrostatic'),
                   #oct_energy_sm(r'Int\[n.v_xc\]', ''),
                   oct_energy_sm('Exchange', 'energy_X'),
                   oct_energy_sm('Correlation', 'energy_C'),
                   oct_energy_sm('vanderWaals', 'energy_van_der_Waals'),
                   oct_energy_sm('-TS', 'energy_correction_entropy'),
                   oct_energy_sm('Kinetic', 'electronic_kinetic_energy')
               ])


infoFileDescription = SM(
    name='root',
    weak=True,
    startReStr='',
    fixedStartValues={'program_name': 'octopus'},
    sections=['section_single_configuration_calculation'],
    subFlags=SM.SubFlags.Sequenced,
    subMatchers=[
        sm_scfconv,
        sm_energy,
    ])

parserInfo = {
  "name": "info_parser_octopus",
  "version": "1.0"
}

class OctopusParserContext(object):
    """main place to keep the parser status, open ancillary files,..."""
    def __init__(self):
        self.scfIterNr = 0

    # just examples, you probably want to remove the following two triggers
    def startedParsing(self, name, parser):
        pass

    def onClose_section_single_configuration_calculation(self, backend, gIndex, section):
        """trigger called when section_single_configuration_calculation is closed"""
        pass
        #backend.addValue("", self.scfIterNr)
        #logging.getLogger("nomadcore.parsing").info("closing section_single_configuration_calculation gIndex %d %s", gIndex, section.simpleValues)
        #self.scfIterNr = 0

    def onClose_section_scf_iteration(self, backend, gIndex, section):
        """trigger called when section_scf_iteration is closed"""
        pass
        #logging.getLogger("nomadcore.parsing").info("closing section_scf_iteration bla gIndex %d %s", gIndex, section.simpleValues)
        #self.scfIterNr += 1

def parse_infofile(meta_info_env, pew, fname):
    parse_file_without_decorations(pew, meta_info_env, infoFileDescription,
                                   parserInfo, OctopusParserContext(), fname)
