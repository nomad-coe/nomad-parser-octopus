import logging
import setup_paths
from nomadcore.simple_parser import mainFunction, SimpleMatcher as SM
from nomadcore.local_meta_info import loadJsonFile, InfoKindEl
from nomadcore.unit_conversion.unit_conversion \
    import register_userdefined_quantity
import os, sys, json


OCT_ENERGY_UNIT_NAME = 'usrOctEnergyUnit'


f_num = r'[-+]?\d*\.\d*'
e_num = r'[-+\d.EeDd]*'
i_num = r'[-+\d]*'


def numpattern(id, unit=None, pattern=f_num):
    if unit is None:
        pat = r'(?P<%(id)s>%(pattern)s)'
    else:
        pat = r'(?P<%(id)s__%(unit)s>%(pattern)s)'
    return pat % dict(id=id, unit=unit, pattern=pattern)


# Match lines like: "      Total    =     -7.05183\n"
def oct_energy_sm(octname, nomadname):
    pattern = (r'\s*%(octname)s\s*=\s*%(pattern)s'
               % dict(octname=octname,
                      pattern=numpattern(nomadname,
                                         unit='hartree'))) # XXXXXXXXXXXX
    #print 'oct energy sm', pattern
    return SM(pattern,
              name=octname)

def adhoc_register_octopus_energy_unit(parser):

    #print 'GRRRRRRRRRRRRRRRRRRR'
    line = parser.fIn.readline()
    unit = line.rsplit('[', 2)[1].split(']', 2)[0]
    if unit == 'H':
        oct_energy_unit = 'hartree'
    else:
        assert unit == 'eV'
        oct_energy_unit = 'eV'
    register_userdefined_quantity(OCT_ENERGY_UNIT_NAME, oct_energy_unit)


sm_get_oct_energy_unit = SM(r'Eigenvalues\s*\[(H|eV)\]',
                            forwardMatch=True,
                            weak=True,
                            name='define_energy_unit',
                            adHoc=adhoc_register_octopus_energy_unit,
                            required=True)


sm_eig_occ = SM(r'\s*#st\s*Spin\s*Eigenvalue\s*Occupation',
                name='eig_occ_columns',
                sections=['section_eigenvalues'],
                required=True,
                subMatchers=[ # TODO spin directions
                    SM(r'\s*\d+\s*..\s*%(eig)s\s*%(occ)s'
                       % dict(eig=numpattern('eigenvalues_values',
                                             OCT_ENERGY_UNIT_NAME),
                              occ=numpattern('eigenvalues_occupation')),
                       required=True,
                       repeats=True,
                       name='eig_occ_line'),
                    SM(r'\s*', name='whitespace')
                ])


sm_energy = SM(r'Energy \[(H|eV)\]:', required=True, name='energy_header',
               subMatchers=[
                   oct_energy_sm('Total', 'energy_total'),
                   oct_energy_sm('Free', 'energy_free'),
                   oct_energy_sm('Eigenvalues', 'energy_sum_eigenvalues'),
                   oct_energy_sm('Hartree', 'energy_electrostatic'),
                   oct_energy_sm('Exchange', 'energy_X'),
                   oct_energy_sm('Correlation', 'energy_C'),
                   oct_energy_sm('vanderWaals', 'energy_van_der_Waals'),
                   oct_energy_sm('-TS', 'energy_correction_entropy'),
                   oct_energy_sm('Kinetic', 'electronic_kinetic_energy')
               ])


mainFileDescription = SM(
    name='root',
    weak=True,
    startReStr='',
    fixedStartValues={'program_name': 'octopus'},
    sections=['section_single_configuration_calculation'],
    subFlags=SM.SubFlags.Sequenced,
    subMatchers=[
        sm_get_oct_energy_unit,
        sm_eig_occ,
        sm_energy,
    ])

# loading metadata from nomad-meta-info/meta_info/nomad_meta_info/octopus.nomadmetainfo.json
metaInfoPath = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../../../nomad-meta-info/meta_info/nomad_meta_info/octopus.nomadmetainfo.json"))
metaInfoEnv, warnings = loadJsonFile(filePath = metaInfoPath, dependencyLoader = None, extraArgsHandling = InfoKindEl.ADD_EXTRA_ARGS, uri = None)

parserInfo = {
  "name": "parser_octopus",
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
        #backend.addValue("", self.scfIterNr)
        logging.getLogger("nomadcore.parsing").info("closing section_single_configuration_calculation gIndex %d %s", gIndex, section.simpleValues)
        self.scfIterNr = 0

    def onClose_section_scf_iteration(self, backend, gIndex, section):
        """trigger called when section_scf_iteration is closed"""
        logging.getLogger("nomadcore.parsing").info("closing section_scf_iteration bla gIndex %d %s", gIndex, section.simpleValues)
        self.scfIterNr += 1

# which values to cache or forward (mapping meta name -> CachingLevel)
cachingLevelForMetaName = {}

if __name__ == "__main__":
    mainFunction(mainFileDescription, metaInfoEnv, parserInfo,
                 cachingLevelForMetaName = cachingLevelForMetaName,
                 superContext = OctopusParserContext())
