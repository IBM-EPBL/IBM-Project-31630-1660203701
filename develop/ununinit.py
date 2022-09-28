# coding: utf-8

import os
import sys

from ruamel.std.pathlib import Path
from .revertablefile import RevertableFile, LineNotFound, MultipleLinesFound  # NOQA

ununinitpy = '__init__.py'

class  UnUnInit(RevertableFile):
    def update_versions(self, mmm=None, dev=None):
        # dev is tri-state 
        versions_changed = 0
        version = None
        for idx, line in enumerate(self.lines):
            if versions_changed > 1:
                break
            if line.startswith('    version_info='):
                pre, rest = line.split('(', 1)
                vals, post = rest.split(')', 1)
                version = []
                for v in vals.split(','):
                    try:
                        version.append(int(v))
                    except ValueError:
                        version.append(v.replace('\'', "").replace('"', "").strip())
                if mmm == 'major':
                    version[0] += 1
                    version[1] = 0
                    version[2] = 0
                elif mmm == 'minor':
                    version[1] += 1
                    version[2] = 0
                elif mmm == 'micro':
                    version[2] += 1
                elif mmm is None:
                    assert dev is not None
                else:
                    print('unknown version part', repr(mmm))
                    sys.exit(1)
                if dev is not None:
                    if dev:
                        version = version[:3] + ['dev', 0]
                    else:
                        version = version[:3]
                version_str = ', '.join([repr(x) for x in version]) 
                self.lines[idx] = f'{pre}({version_str}){post}'
                versions_changed += 1
            if line.startswith('    __version__='):
                uupre, rest = line.split('=', 1)
                rest = rest.lstrip()
                quote = rest[0]
                uupost=rest[1:].split(quote, 1)[1]
                assert version is not None
                uuv = '.'.join([str(x) for x in version])
                self.lines[idx] = f'{uupre}={quote}{uuv}{quote}{uupost}'
                versions_changed += 1
        else:
            print('not enough versions to change found', versions_changed)
            sys.exit(1)
        self.changed = True
        self._text = None


def version_list(s):
    if not isinstance(s, list):
        for c in ',.':
            if c in s:
                s = s.split(c)
                break
    version = []
    for vs in s:
        try:
            vs = vs.strip()
        except AttributeError:
            pass
        try:
            version.append(int(vs))
        except ValueError:
            if vs and vs[0] in '\'"':
                vs = vs[1:-1]
            version.append(vs)
    return version


def version_init_files(base_dir, show_subdirs=False):
    for root, directory_names, file_names in os.walk(base_dir):
        if not show_subdirs:
            directory_names[:] = []
        # always skip non-interesting subdirs (before doing a continue)
        for d in directory_names[:]:
            if d and d[0] == '.':  # .tox, .hg, .git, .cache, etc.
                directory_names.remove(d)
            elif d in ['build', 'dist']:
                directory_names.remove(d)
        if ununinitpy not in file_names:
            continue
        full_name = os.path.join(root, ununinitpy)
        res = extract_version(full_name)
        if res:
            yield res


version_indent = '    '
short_prefix = 'version_info'
string_prefix = '__version__'
prefixes = [
    (version_indent + short_prefix + '=(', ')', ', ', ""),  # NOQA PON tuple
    (version_indent + short_prefix + '=[', ']', ', ', 'PON list'),  # NOQA PON list
    (version_indent + '"' + short_prefix + '": (', ')', ', ', 'PON tuple {}'),  # NOQA PON list
    (version_indent + '"' + short_prefix + '": [', ']', ', ', 'PON'),  # NOQA JSON files
    (short_prefix + ' = (', ')', ', ', 'old'),  # NOQA old format
]


def extract_version(full_name):
    json = False
    found = False
    with open(full_name) as fp:
        for line in fp:
            if found:  # previous line was version_info
                if not comment: # PON tuple
                    if not line.startswith(version_indent + string_prefix):
                        comment = 'expected line with "{}"'.format(string_prefix)
                    else:
                        sv = line.split('=', 1)[1].lstrip() 
                        if not sv or sv[0] not in '\'"':
                            comment = 'no quote after = in "{}" line'.format(string_prefix)
                        else:
                            sv = sv[1:].split(sv[0])[0]
                            v = version_list(sv)
                            if v != version:
                                comment = '{}: {} != "{}"'.format(ununinitpy, version, sv)
                return full_name, version, comment
            if 'JSON' in line:
                json = True
            for prefix, end, split, comment in prefixes:
                if line.startswith(prefix):
                    version = version_list(line[len(prefix) :].split(end, 1)[0].split(split))
                    if json:
                        comment += '/JSON'
                    found = True
                    break
            else:
                if line.startswith(short_prefix):
                    print('prefix', short_prefix, line, end="")
                    print('warning: version_info formatting in:', full_name)


def set_dev_lines(dev, save=False, inc_micro=False):
    """update just two lines, leave rest as is"""
    initpy_path = Path(ununinitpy)
    orig_path = Path(ununinitpy + '.orig')
    if not orig_path.exists():
        initpy_path.copy(orig_path)
    lines = initpy_path.read_text().splitlines()
    prefix = prefixes[0]
    for idx, line in enumerate(lines):
        _version = '__version__='
        if line.startswith(prefix[0]):
            assert _version in lines[idx + 1]
            split_quote_char = lines[idx + 1].split(_version)[1][0]
            assert split_quote_char in '\'"'
            val, comment = line.split(prefix[0])[1].split(prefix[1], 1)
            val = val.split(', ')
            if ('dev' in val[-1]) == (bool(dev)):
                if dev:
                    print('dev already in version')
                else:
                    print('dev not in version')
                    return
                sys.exit(1)
            if dev:
                val.append(split_quote_char + "dev" + split_quote_char)
            else:
                val = val[:3]
            if inc_micro:
                val[2] = str(int(val[2]) + 1)
            # print(val)
            lines[idx] = '{}{}{}{}'.format(prefix[0], ', '.join(val), prefix[1], comment)
            c2 = lines[idx + 1].split(split_quote_char)
            c2[1] = '.'.join(val).replace(split_quote_char, "")
            lines[idx + 1] = split_quote_char.join(c2)
            break
    else:
        raise ValueError('version info not found')
    if False:
        print(lines[idx])
        print(lines[idx + 1])
    if save:
        initpy_path.write_text('\n'.join(lines) + '\n')


set_dev = set_dev_lines
