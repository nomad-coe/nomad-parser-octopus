from nomadcore.simple_parser import mainFunction, SimpleMatcher as SM

from util import numpattern, i_num, f_num, e_num, word, integer

parserInfo = {
  "name": "logfile_parser_octopus",
  "version": "1.0"
}



logFileDescription = SM(
    name='root',
    weak=True,
    startReStr='',
    fixedStartValues={'program_name': 'octopus'},
    sections=['section_run'],
    subFlags=SM.SubFlags.Sequenced,
    subMatchers=[
        SM(r'Version\s*:\s*%s' % word('program_version')),
        SM(r'Revision\s*:\s*%s' % integer('x_octopus_log_svn_revision')),
        #SM(r'Input: [SmearingFunction = %s]' % word(''))
        # Grr.  But we have to convert semi_conducting to some other word.
    ]
)

class OctopusLogFileParserContext(object):
    def startedParsing(self, name, parser):
        pass


def parse_logfile(metaInfoEnv, pew, fname):
    with open('logfile-parse.log', 'w') as fd:
        mainFunction(logFileDescription,
                     metaInfoEnv,
                     parserInfo,
                     outF=fd,
                     cachingLevelForMetaName={},
                     superBackend=pew,
                     superContext=OctopusLogFileParserContext(),
                     mainFile=fname)
        #for key in metaInfoEnv:
        #    print('key', key)
