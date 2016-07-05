from nomadcore.simple_parser import mainFunction, runParser

OCT_ENERGY_UNIT_NAME = 'usrOctEnergyUnit'
f_num = r'[-+]?(\d*\.\d+|\d+\.\d*)'  # e.g.: 0.7 1. -.1
e_num = r'[-+]?\d*\.\d+[EeDd][-+]\d*' # e.g.: -7.642e-300
i_num = r'[-+\d]*'

def numpattern(id, unit=None, pattern=f_num):
    if unit is None:
        pat = r'(?P<%(id)s>%(pattern)s)'
    else:
        pat = r'(?P<%(id)s__%(unit)s>%(pattern)s)'
    return pat % dict(id=id, unit=unit, pattern=pattern)

def pat(meta, regex):
    return '(?P<%s>%s)' % (meta, regex)
def word(meta):
    return pat(meta, regex=r'\S*')
def integer(meta):
    return pat(meta, regex=i_num)
def floating(meta):
    return pat(meta, regex='%s|%s' % (f_num, e_num))


def parse_file_without_decorations(pew, meta_info_env, matchers,
                                   parser_info, supercontext, fname):
    """Run SimpleMatcher on a file printing only sequence of json."""

    # If we set outF, it only redirects some of the stuff.
    # It writes "[" followed by json followed by "]", to
    # different streams.  By redirecting one of them we can get only
    # the json.  Strange but true!
    class DevNull:
        def write(self, txt):
            pass

    # This is to prevent another header (nomad_parse_events_1_0 etc.)
    def parsefile(parser_builder, uri, path, backend, super_context):
        with open(path) as fd:
            runParser(parser_builder, backend, super_context, fd)

    mainFunction(matchers,
                 meta_info_env,
                 parser_info,
                 outF=DevNull(),  # Eats surrounding []
                 parseFile=parsefile,
                 cachingLevelForMetaName={},
                 superBackend=pew,
                 superContext=supercontext,
                 mainFile=fname)
