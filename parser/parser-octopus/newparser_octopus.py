import os
import sys
from contextlib import contextmanager

import ase.calculators.octopus as aseoct

import setup_paths
from nomadcore.local_meta_info import loadJsonFile, InfoKindEl
from nomadcore.parser_backend import JsonParseEventsWriterBackend


metaInfoPath = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../../../nomad-meta-info/meta_info/nomad_meta_info/octopus.nomadmetainfo.json"))
metaInfoEnv, warnings = loadJsonFile(filePath = metaInfoPath, dependencyLoader = None, extraArgsHandling = InfoKindEl.ADD_EXTRA_ARGS, uri = None)

parserInfo = {
  "name": "parser_octopus",
  "version": "1.0"
}

def parse_exec_kwargs(exec_path):
    exec_kwargs = {}
    with open(exec_path) as fd:
        for line in fd:
            # Skip noise:
            if line.endswith('# default\n'):
                continue
            # Remove comment:
            line = line.split('#', 1)[0].strip()
            tokens = line.split('=')
            try:
                name, value = tokens
            except ValueError:
                continue # Not an assignment
            name = name.strip().lower()
            value = value.strip()
            assert name not in exec_kwargs, 'Multiply assigned: %s' % name
            exec_kwargs[name] = value
    return exec_kwargs


def normalize_names(names):
    return [name.lower() for name in names]

def parse(fname):
    pew = JsonParseEventsWriterBackend(metaInfoEnv)

    # this context manager shamelessly copied from GPAW parser
    @contextmanager
    def open_section(name):
        gid = pew.openSection(name)
        yield
        pew.closeSection(name, gid)

    with open_section('section_run'):
        pew.addValue('program_name', 'Octopus')

        staticdirname, _basefname = os.path.split(fname)
        dirname, _static = os.path.split(staticdirname)
        inp_path = os.path.join(dirname, 'inp')
        exec_path = os.path.join(dirname, 'exec', 'parser.log')

        # Some variables we can get from the input file, but they may
        # contain arithmetic and variable assignments.  The output of
        # the Octopus parser (exec/parser.log) is reduced to pure
        # numbers, so that is useful, except when the variable was a
        # name (such as an eigensolver).  In that case we should
        # definitely not rely on the number!  We will take some variables
        # from the exec/parser.log but most will just be verbatim from
        # the input file.
        exec_override_keywords = set(['radius', 'lsize', 'spacing'])

        exec_kwargs = parse_exec_kwargs(exec_path)

        with open(inp_path) as fd:
            names, values = aseoct.parse_input_file(fd)
        names = normalize_names(names)

        kwargs = {}
        for name, value in zip(names, values):
            kwargs[name] = value

        # Now override any relevant keywords:
        for name in exec_override_keywords:
            if name in kwargs:
                if name == 'lsize':
                    lsize = []
                    for i in range(3):
                        # (This is relatively horrible.  We are looking for
                        # lines like "Lsize (0, 0) = 5.0" or similar)
                        lsize_tmp = 'lsize (0, %d)' % i
                        assert lsize_tmp in exec_kwargs
                        lsize.append(exec_kwargs[lsize_tmp])
                    kwargs[name] = [lsize]
                    continue

                kwargs[name] = exec_kwargs[name]

        print
        for name in kwargs:
            print name, kwargs[name]
        print

if __name__ == '__main__':
    fname = sys.argv[1]
    parse(fname)
