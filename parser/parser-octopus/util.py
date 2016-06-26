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
