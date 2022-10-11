# coding: utf-8
# flake8: noqa
# cligen: 0.1.4, dd: 2021-08-17

import _ast
import argparse
import ast
import datetime
import importlib
import os
import pathlib
import sys

from . import __version__


class ConfigBase:
    def __init__(self, path=None, parser=None):
        self._parser = parser
        tmp_path = self.get_config_parm()
        if tmp_path:
            self._path = tmp_path
        elif isinstance(path, pathlib.Path):
            self._path = path
        elif path is not None:
            # path = self.get_config_parm()
            if '/' in path:
                self._path = pathlib.Path(path).expanduser()
            else:
                self._path = self.config_dir / path / (path.rsplit('.')[-1] + self.suffix)
        else:
            # could use sys.argv[0]
            raise NotImplementedError

    def set_defaults(self):
        self._data = self.load()  # NOQA
        self._set_section_defaults(self._parser, self._data['global'])
        if self._parser._subparsers is None:
            return
        assert isinstance(self._parser._subparsers, argparse._ArgumentGroup)
        progs = set()
        for sp in self._parser._subparsers._group_actions:
            if not isinstance(sp, argparse._SubParsersAction):
                continue
            for k in sp.choices:
                if k not in self._data:
                    continue
                subp_action = sp.choices[k]
                if subp_action.prog not in progs:
                    progs.add(subp_action.prog)
                    self._set_section_defaults(subp_action, self._data[k], glbl=False)
        #if self._save_defaults:
        #    self.parse_args()

    def _set_section_defaults(self, parser, section, glbl=True):
        assert isinstance(section, dict)
        defaults = {}
        for action in parser._get_optional_actions():
            if isinstance(action,
                          (argparse._HelpAction,
                           argparse._VersionAction,
                           # SubParsersAction._AliasesChoicesPseudoAction,
                           )):
                continue
            for x in action.option_strings:
                if not x.startswith('-'):
                    continue
                try:
                    # get value based on long-option (without --)
                    # store in .dest
                    v = section[x.lstrip('-')]
                    defaults[action.dest] = v
                except KeyError:  # not in config file
                    if not glbl:
                        try:
                            if self._data[glbl] is None:
                                raise KeyError
                            defaults[action.dest] = self[glbl][x.lstrip('-')]
                        except KeyError:  # not in config file
                            pass
                break  # only first --option
        parser.set_defaults(**defaults)


    def get_config_parm(self):
        # check if --config was given on commandline
        for idx, arg in enumerate(sys.argv[1:]):
            if arg.startswith('--config'):
                if len(arg) > 8 and arg[8] == '=':
                    return pathlib.Path(arg[9:])
                else:
                    try:
                        return pathlib.Path(sys.argv[idx + 2])
                    except IndexError:
                        print('--config needs an argument')
                        sys.exit(1)
        return None

    @property
    def config_dir(self):
        # https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
        attr = '_' + sys._getframe().f_code.co_name
        if not hasattr(self, attr):
            if sys.platform.startswith('win32'):
                d = os.environ['APPDATA']
            else:
                d = os.environ.get(
                    'XDG_CONFIG_HOME', os.path.join(os.environ['HOME'], '.config')
                )
            pd = pathlib.Path(d)
            setattr(self, attr, pd)
            return pd
        return getattr(self, attr)


class ConfigPON(ConfigBase):
    suffix = '.pon'

    def load(self):
        data = _loads(self._path.read_text())
        print('data', data)
        if 'glbl' in data and not 'global' in data:  # cannot have reserved word global in dict(global=....)
            data['global'] = data.pop('glbl')
        return data


# taken from pon.__init__.py
def _loads(node_or_string, dict_typ=dict, return_ast=False, file_name=None):
    """
    Safely evaluate an expression node or a string containing a Python
    expression.  The string or node provided may only consist of the following
    Python literal structures: strings, bytes, numbers, tuples, lists, dicts,
    sets, booleans, and None.
    """
    if sys.version_info < (3, 4):
        _safe_names = {'None': None, 'True': True, 'False': False}
    if isinstance(node_or_string, str):
        node_or_string = compile(
            node_or_string,
            '<string>' if file_name is None else file_name,
            'eval',
            _ast.PyCF_ONLY_AST,
        )
    if isinstance(node_or_string, _ast.Expression):
        node_or_string = node_or_string.body
    else:
        raise TypeError('only string or AST nodes supported')

    def _convert(node, expect_string=False):
        if isinstance(node, ast.Str):
            if sys.version_info < (3,):
                return node.s
            return node.s
        elif isinstance(node, ast.Bytes):
            return node.s
        if expect_string:
            pass
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, _ast.Tuple):
            return tuple(map(_convert, node.elts))
        elif isinstance(node, _ast.List):
            return list(map(_convert, node.elts))
        elif isinstance(node, _ast.Set):
            return set(map(_convert, node.elts))
        elif isinstance(node, _ast.Dict):
            return dict_typ(
                (_convert(k, expect_string=False), _convert(v))
                for k, v in zip(node.keys, node.values)
            )
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif sys.version_info < (3, 4) and isinstance(node, Name):
            if node.id in _safe_names:
                return _safe_names[node.id]
        elif (
            isinstance(node, _ast.UnaryOp)
            and isinstance(node.op, (_ast.UAdd, _ast.USub))
            and isinstance(node.operand, (ast.Num, _ast.UnaryOp, _ast.BinOp))
        ):
            operand = _convert(node.operand)
            if isinstance(node.op, _ast.UAdd):
                return +operand
            else:
                return -operand
        elif (
            isinstance(node, _ast.BinOp)
            and isinstance(node.op, (_ast.Add, _ast.Sub, _ast.Mult))
            and isinstance(node.right, (ast.Num, _ast.UnaryOp, _ast.BinOp))
            and isinstance(node.left, (ast.Num, _ast.UnaryOp, _ast.BinOp))
        ):
            left = _convert(node.left)
            right = _convert(node.right)
            if isinstance(node.op, _ast.Add):
                return left + right
            elif isinstance(node.op, _ast.Mult):
                return left * right
            else:
                return left - right
        elif isinstance(node, _ast.Call):
            func_id = getattr(node.func, 'id', None)
            if func_id == 'dict':
                return dict_typ((k.arg, _convert(k.value)) for k in node.keywords)
            elif func_id == 'set':
                return set(_convert(node.args[0]))
            elif func_id == 'date':
                return datetime.date(*[_convert(k) for k in node.args])
            elif func_id == 'datetime':
                return datetime.datetime(*[_convert(k) for k in node.args])
            elif func_id == 'dedent':
                return dedent(*[_convert(k) for k in node.args])
        elif isinstance(node, Name):
            return node.s
        err = SyntaxError('malformed node or string: ' + repr(node))
        err.filename = '<string>'
        err.lineno = node.lineno
        err.offset = node.col_offset
        err.text = repr(node)
        err.node = node
        raise err

    res = _convert(node_or_string)
    if not isinstance(res, dict_typ):
        raise SyntaxError('Top level must be dict not ' + repr(type(res)))
    if return_ast:
        return res, node_or_string
    return res



class CountAction(argparse.Action):
    """argparse action for counting up and down

    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action=CountAction, const=1,
            nargs=0)
    parser.add_argument('--quiet', '-q', action=CountAction, dest='verbose',
            const=-1, nargs=0)
    """

    def __call__(self, parser, namespace, values, option_string=None):
        if self.const is None:
            self.const = 1
        try:
            val = getattr(namespace, self.dest) + self.const
        except TypeError:  # probably None
            val = self.const
        setattr(namespace, self.dest, val)


class DateAction(argparse.Action):
    """argparse action for parsing dates with or without dashes

    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action=DateAction)
    """

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs != 1 and nargs not in [None, '?', '*']:
            raise ValueError('DateAction can only have one argument')
        default = kwargs.get('default')
        if isinstance(default, str):
            kwargs['default'] = self.special(default)
        super(DateAction, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # this is only called if the option is specified
        if values is None:
            return None
        s = values
        for c in './-_':
            s = s.replace(c, '')
        try:
            val = datetime.datetime.strptime(s, '%Y%m%d').date()
        except ValueError:
            val = self.special(s)
        #    val = self.const
        setattr(namespace, self.dest, val)

    def special(self, date_s):
        if isinstance(date_s, str):
            today = datetime.date.today()
            one_day = datetime.timedelta(days=1)
            if date_s == 'today':
                return today
            if date_s == 'yesterday':
                return today - one_day
            if date_s == 'tomorrow':
                return today + one_day
            raise ValueError


def main():
    parsers = []
    parsers.append(argparse.ArgumentParser())
    parsers[-1].add_argument('--verbose', '-v', nargs=0, dest='_gl_verbose', default=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--distbase', help='base directory for all distribution files (default: %(default)s)')
    parsers[-1].add_argument('--tarbase', help='base directory for all backup tar files (tar subcommand) (default: %(default)s)')
    parsers[-1].add_argument('--toxbase', help='base directory for all .tox directories (default: %(default)s)')
    parsers[-1].add_argument('--maintainer', metavar='MNT', help='maintainer information (e.g. Dockerfile, default: "%(default)s")')
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--date', dest='_gl_date', default='today', action=DateAction, metavar='DATE', help='update date README.rst to %(metavar)s (default: %(default)s)')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    parsers[-1].add_argument('--version', action='store_true', help='show program\'s version number and exit')
    subp = parsers[-1].add_subparsers()
    px = subp.add_parser('clean', help='clean up development directory')
    px.set_defaults(subparser_func='clean')
    parsers.append(px)
    parsers[-1].add_argument('args', nargs='*')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('dist', help='execute dist related commands')
    px.set_defaults(subparser_func='dist')
    parsers.append(px)
    parsers[-1].add_argument('--all', action='store_true', help='build sdist and wheels for all platforms')
    parsers[-1].add_argument('--sdist', '--src', '-s', action='store_true', help='build sdist')
    parsers[-1].add_argument('--linux', action='store_true', help='build linux wheels using manylinux')
    parsers[-1].add_argument('--macos', action='store_true', help='build macOS wheels')
    parsers[-1].add_argument('--windows', action='store_true', help='build windows wheels on appveyor')
    parsers[-1].add_argument('--kw', action='store_true', help='show keywords as calculated by setup.py')
    parsers[-1].add_argument('--full', action='store_true', help='show full path for dist files')
    parsers[-1].add_argument('--appveyor-check', action='store_true', help='show appveyor status')
    parsers[-1].add_argument('--appveyor-pull', action='store_true', help='pull manually started artifacts from appveyor')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('make', help='invoke make (with args), writes .Makefile.tmp')
    px.set_defaults(subparser_func='make')
    parsers.append(px)
    parsers[-1].add_argument('args', nargs='*')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('mypy', help='invoke mypy --strict')
    px.set_defaults(subparser_func='mypy')
    parsers.append(px)
    parsers[-1].add_argument('--edit', action='store_true', help='on error/note invoke editor on first line')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('push', help='create and push a new release')
    px.set_defaults(subparser_func='push')
    parsers.append(px)
    parsers[-1].add_argument('--changestest', action='store_true', help='test update of CHANGES')
    parsers[-1].add_argument('--reuse-message', '--re-use-message', action='store_true', help='reuse commit message')
    parsers[-1].add_argument('--commit-message', help='use commit message (no interaction)')
    parsers[-1].add_argument('--no-tox', action='store_true', help="don't run tox -r")
    parsers[-1].add_argument('--test-readme-message', help='==SUPPRESS==')
    parsers[-1].add_argument('-e', help='==SUPPRESS==')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('rtfd', help='execute Read the Docs related commands')
    px.set_defaults(subparser_func='rtfd')
    parsers.append(px)
    parsers[-1].add_argument('--build', action='store_true', help='trigger build')
    parsers[-1].add_argument('--admin', action='store_true', help='show admin page')
    parsers[-1].add_argument('--show', action='store_true', help='show documentation')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('readme', help='execute readme related commands')
    px.set_defaults(subparser_func='readme')
    parsers.append(px)
    parsers[-1].add_argument('--version', metavar='X.Y.Z', help='update version in README.rst to %(metavar)s')
    parsers[-1].add_argument('--date', action=DateAction, metavar='DATE', help='update date README.rst to %(metavar)s (default: %(default)s)')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('badge', help='create initial badges in _doc/_static')
    px.set_defaults(subparser_func='badge')
    parsers.append(px)
    parsers[-1].add_argument('--oitnb', action='store_true', help='write oitnb badge')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('tox', help='invoke tox (with args)')
    px.set_defaults(subparser_func='tox')
    parsers.append(px)
    parsers[-1].add_argument('-e', metavar='TARGETS', help='only test comma separated %(metavar)s')
    parsers[-1].add_argument('-E', action='store_true', help='show targets calculated from package_data')
    parsers[-1].add_argument('-r', action='store_true', help='force recreation of virtual environments by removign them first')
    parsers[-1].add_argument('-q', nargs=0, action=CountAction, const=1, help='decrease tox verbosity level')
    parsers[-1].add_argument('args', nargs='*')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('commit', help='commit files (excluding README.* and __init__.py)')
    px.set_defaults(subparser_func='commit')
    parsers.append(px)
    parsers[-1].add_argument('--all', action='store_true', help='commmit all changed files')
    parsers[-1].add_argument('args', nargs='*')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('version', help='execute version related commands')
    px.set_defaults(subparser_func='version')
    parsers.append(px)
    parsers[-1].add_argument('--badge', action='store_true', help='write version in PyPI badge')
    parsers[-1].add_argument('--dev', action='store_true', help='add "dev"')
    parsers[-1].add_argument('--no-dev', action='store_false', dest='dev', help='remove "dev"')
    parsers[-1].add_argument('--rm-dev', action='store_false', dest='dev', help='==SUPPRESS==')
    parsers[-1].add_argument('args', nargs='*')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('check', help='check sanity of the package (also done on push)')
    px.set_defaults(subparser_func='check')
    parsers.append(px)
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('check_setup', help='check setup.py)')
    px.set_defaults(subparser_func='check_setup')
    parsers.append(px)
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('walk', help='walk the development tree recursively and execute actions')
    px.set_defaults(subparser_func='walk')
    parsers.append(px)
    parsers[-1].add_argument('--check-init', action='store_true', help='check __init__.py files')
    parsers[-1].add_argument('--insert-pre-black', action='store_true', help='insert pre-black entry in __init__.py files')
    parsers[-1].add_argument('--check-hgignore', action='store_true', help='remove entries in .hgignore files that are in global ignore file, delete when emtpy')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('sfup', help='upload .tar.xz file to sourceforge')
    px.set_defaults(subparser_func='sfup')
    parsers.append(px)
    parsers[-1].add_argument('--version', help='tag to use, defaults to latest tag')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('bbup', help='upload .tar.xz file to bitbucket')
    px.set_defaults(subparser_func='bbup')
    parsers.append(px)
    parsers[-1].add_argument('--version', help='tag to use, defaults to latest tag')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('bbup0', help='upload a file to bitbucket')
    px.set_defaults(subparser_func='bbup0')
    parsers.append(px)
    parsers[-1].add_argument('--version')
    parsers[-1].add_argument('--user')
    parsers[-1].add_argument('--repo')
    parsers[-1].add_argument('--pypi')
    parsers[-1].add_argument('file')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('patchwheel', help='patch wheel file')
    px.set_defaults(subparser_func='patchwheel')
    parsers.append(px)
    parsers[-1].add_argument('--filenames', metavar='FN', action='append', nargs=2, help='rename the part of any filename matching first %(metavar)s argument to second (option can be given multiple times)')
    parsers[-1].add_argument('--wheelnames', metavar='WHL', action='append', nargs=2, help='rename the part of wheel name matching first %(metavar)s argument to second (option can be given multiple times)')
    parsers[-1].add_argument('--outdir', help='directory where to write the output .whl file (if not given --wheelnames not given, wheels will be updated in place)')
    parsers[-1].add_argument('file', nargs='+')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('tar', help='create/restore dated tar file of EVERYTHING, so you can test local commits')
    px.set_defaults(subparser_func='tar')
    parsers.append(px)
    parsers[-1].add_argument('--create', action='store_true', help='create dated tar file')
    parsers[-1].add_argument('--restore', action='store_true', help='restore latest dated tar file')
    parsers[-1].add_argument('--list', action='store_true', help='list all dated tar file')
    parsers[-1].add_argument('command', help='create, restore, list if empty)', nargs='?')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    px = subp.add_parser('exe', help='create executable in ~/bin')
    px.set_defaults(subparser_func='exe')
    parsers.append(px)
    parsers[-1].add_argument('--force', action='store_true', help='backup and create if already exists')
    parsers[-1].add_argument('--show', action='store_true', help='restore latest dated tar file')
    parsers[-1].add_argument('--verbose', '-v', nargs=0, help='increase verbosity level', action=CountAction, const=1)
    parsers[-1].add_argument('--detox', help='parallel tox with detox', action='store_true')
    parsers[-1].add_argument('--keep', help='keep temporary files', action='store_true')
    parsers[-1].add_argument('--test', action='store_true', help="create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI")
    parsers.pop()
    config = ConfigPON(path="develop", parser=parsers[0])
    config.set_defaults()
    if '--version' in sys.argv[1:]:
        if '-v' in sys.argv[1:] or '--verbose' in sys.argv[1:]:
            return list_versions(pkg_name='develop', version=None, pkgs=['ruamel.showoutput', 'python-hglib', 'repo', 'readme-renderer', 'configobj'])
        print(__version__)
        return
    args = parsers[0].parse_args()
    for gl in ['verbose', 'date']:
        if getattr(args, gl, None) is None:
            setattr(args, gl, getattr(args, '_gl_' + gl))
        delattr(args, '_gl_' + gl)
    cls = getattr(importlib.import_module("develop.develop"), "Develop")
    obj = cls(args, config=config)
    funcname = getattr(args, 'subparser_func', None)
    if funcname is None:
        parsers[0].parse_args('--help')
    fun = getattr(obj, args.subparser_func)
    return fun()

def list_versions(pkg_name, version, pkgs):
    version_data = [
        ('Python', '{v.major}.{v.minor}.{v.micro}'.format(v=sys.version_info)),
        (pkg_name, __version__ if version is None else version),
    ]
    for pkg in pkgs:
        try:
            version_data.append((pkg,  getattr(importlib.import_module(pkg), '__version__', '--')))
        except ModuleNotFoundError:
            version_data.append((pkg, 'NA'))
        except KeyError:
            pass
    longest = max([len(x[0]) for x in version_data]) + 1
    for pkg, ver in version_data:
        print('{:{}s} {}'.format(pkg + ':', longest, ver))


if __name__ == '__main__':
    sys.exit(main())
