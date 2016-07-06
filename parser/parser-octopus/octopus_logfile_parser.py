from nomadcore.simple_parser import mainFunction, SimpleMatcher as SM

from util import numpattern, i_num, f_num, e_num, word, integer, \
    parse_file_without_decorations


parserInfo = {
  "name": "logfile_parser_octopus",
  "version": "1.0"
}


logFileDescription = SM(
    name='root',
    weak=True,
    startReStr='',
    fixedStartValues={'program_name': 'octopus'},
    #sections=['section_run'],
    subFlags=SM.SubFlags.Sequenced,
    subMatchers=[
        SM(r'Version\s*:\s*%s' % word('program_version')),
        SM(r'Revision\s*:\s*%s' % integer('x_octopus_log_svn_revision')),
    ]
)

class OctopusLogFileParserContext(object):
    def startedParsing(self, name, parser):
        pass


def parse_logfile(meta_info_env, pew, fname):
    # XXX this is just a hack until we decide to do more
    maxlines = 100
    with open(fname) as fd:
        for i in range(maxlines):
            line = next(fd)
            if line.startswith('Version'):
                version = line.split()[-1]
                pew.addValue('program_version', version)
            elif line.startswith('Revision'):
                revision = line.split()[-1]
                #pew.addValue('x_octopus_log_svn_revision', revision)
                # WTF
            # XXX more info


#def parse_logfile(meta_info_env, pew, fname):
#    parse_file_without_decorations(pew, meta_info_env, logFileDescription,
#                                   parserInfo, OctopusLogFileParserContext(),
#                                   fname)
