# coding: utf-8

from __future__ import print_function, absolute_import, division, unicode_literals

"""
this is for writing the tox.ini file dynamically based on information
in __init__.py->_package_data

Need to be able to write two different versions, because vboxsf filesystems
do not allow hardlinking, and tox/virtualenv use that.

So a version with toxworkdir is written before actual testing and one with that
line commented out before commit.

Could put alternate `tox.ini`` in `/data1/DATA/tox/ruamel.yaml``, but that would
mean invocation with `tox -c` even after `dv --keep`.


If the 'dev' entry for the 'tox' entry has comma, the string is taken as-is and
a trailing comma is replaced. Otherwise the string is interpreted:

   dev='py37,py36' -> select python 3.7 and 3.6 as targets
   dev='py36,' -> only select Python 3.6 as target
   dev='py36' -> assertion error (based on the 'y')
   dev='*' -> all active python
   dev='32pjn' -> 3: latest released 3.X.Y, 2: latest released 2.7.X,
                  p: pypy, j: jython, n: narrow 2.7 build


if nested (e.g. ruamel.yaml.cmd, i.e. a package in a directory for which the parent directory
contains a package as well), the tox.ini has to be changed so it uses a .whl file for installation
otherwise the .pth shows up

"""

from ruamel.std.pathlib import Path
import shutil


VER2 = ['py27']
VER3 = ['py39', 'py38', 'py37', 'py36']


class ToxIni:
    def __init__(self, settings, work_dir='.', sub_packages=None, nested=False, test_dir='_test'):
        self._tox_settings = settings
        self._work_dir = work_dir
        self._sub_packages = sub_packages
        self._nested = nested
        self._path = Path('tox.ini')
        self._test_dir = test_dir if test_dir is None or hasattr(test_dir, 'open') else Path(test_dir)

    def envlist(self, spec=None, code_style=''):
        """takes the tox->dev entry from _package_data and generates settings for tox.ini 'envlist = '
        """
        if spec is None:
            spec = str(self._tox_settings['env'])
        if code_style == '':
            code_style = 'cs'  # pep8
        envlist = [] if code_style is None else [code_style]
        # env 3 -> latest 3, 2 -> latest 2, * all active, p -> pypy, j -> jython
        if ',' in spec:
            if spec[-1] == ',':
                spec = spec[:-1]
            envlist = [spec]
        else:
            assert 'y' not in spec, 'You probably want to put a comma in the tox.dev spec'
            if '*' in spec:
                # to get errors depending on major version differeces quicker
                envlist.extend([VER3[0]] + VER3[1:] + VER2[1:])  # removed VER2[0]
            if '3' in spec:
                envlist.append(VER3[0])
            if '2' in spec:
                envlist.append(VER2[0])
            if 'f' in spec:
                envlist.append('py35')
            if 'p' in spec:
                envlist.append('pypy')
            if 'n' in spec:
                narrow = True
                envlist.append(VER2[0] + 'm')
            if 'j' in spec:
                envlist.append('jython')
        return envlist

    def write(self, work_dir=True, touch_to_dot_tox=True):
        twd = ("" if work_dir else '# ') + 'toxworkdir'
        narrow = False
        with self._path.open('w') as fp:
            print('[tox]', file=fp)  # NOQA
            print(f'{twd} = {self._work_dir} ', file=fp)  # NOQA
            envlist = self.envlist()
            print('envlist: {}'.format(','.join(envlist)))
            print('envlist = {}'.format(','.join(envlist)), file=fp)
            print('\n[testenv]', file=fp)
            # print('install_command =', file=fp)
            # print('    pip install --upgrade pip', file=fp)   # this doesn't work install_command needs {packages} %-)
            print('install_command = pip install --disable-pip-version-check {opts} {packages}', file=fp)
            if self._nested:
                print('skip_install = True', file=fp)
            print('commands =', file=fp)
            # print('''    python -c "import sys, sysconfig; print('%s ucs-%s' % '''
            #       '''(sys.version.replace('\\n', ' '), sysconfig.get_config_var'''
            #       '''('Py_UNICODE_SIZE')))"''', file=fp)
            if self._nested:
                q = self._work_dir.name
                print('    python setup.py bdist_wheel -d {}/dist/'.format(self._work_dir), 
                      file=fp)
                print('    pip install --upgrade --find-links={}/dist/ {}'.format(self._work_dir, q), 
                      file=fp)
            if self._test_dir and self._test_dir.exists():
                print("    /bin/bash -c 'pytest _test/test_*.py'", file=fp)
            print('deps =', file=fp)
            # deps extra dependency packages for testing
            deps = ['pytest']
            if self._nested:
                deps.append('wheel')
            tdeps = self._tox_settings.get('deps', [])
            if isinstance(tdeps, str):
                deps.extend(tdeps.split())
            else:
                deps.extend(tdeps)
            for dep in deps:
                print('    {}'.format(dep), file=fp)
            if narrow:
                pyver = '/opt/python/2.7.15m'  # could be dynamic
                print(f'\n[testenv:py27m]\nbasepython = {pyver}/bin/python', file=fp)
            # [pytest]
            # norecursedirs = test/lib .tox
            deps = []
            flake8ver = self._tox_settings.get('flake8', {}).get('version', "")
            flake_py_ver = '3.8'
            if flake8ver:
                deps.append('flake8' + flake8ver)  # probably 2.5.5
            else:
                # bug-bear need flake8>3, so probably no version allowed
                deps.extend(['flake8', f'flake8-bugbear;python_version>="{flake_py_ver}"'])
            # pep8 for muscle-memory
            for cs in ['cs', 'pep8']:
                print('\n[testenv:{}]'.format(cs), file=fp)
                print(f'basepython = python{flake_py_ver}', file=fp)
                print('deps =', file=fp)
                for dep in deps:
                    print('    {}'.format(dep), file=fp)
                print('commands =', file=fp)
                subdirs = []
                # subdirs = [".tox", ".#*"]
                # fl8excl extra dirs for exclude
                if subdirs:
                    subdirs = ' --exclude "' + ','.join(subdirs) + '" '
                # print('    python -c "import os; print(os.getcwd())"', file=fp)
                print('    flake8 {}{{posargs}}'.format(subdirs), file=fp)
            print('\n[flake8]', file=fp)
            print('show-source = True', file=fp)
            print('max-line-length = 95', file=fp)
            # the following line was in tox.ini for pon E251 is space around keyword?
            # print('ignore = E251', file=fp)
            flake8_ignore = dict(
                W503='line break before binary operator',
                F405='undifined name ( from x import * )',
                E203='whitespace before ":"',
            )
            print('ignore = {}'.format(','.join(flake8_ignore.keys())), file=fp)
            excl = self._tox_settings.get('fl8excl', "")
            if excl and isinstance(excl, str):
                excl = ','.join(excl.split()) + ','
            elif excl:
                excl = ','.join(excl) + ','
            if self._sub_packages:
                subdirs.extend(self._sub_packages)
            print(
                'exclude = {}.hg,.git,.tox,dist,.cache,__pycache__,'
                'ruamel.zip2tar.egg-info'.format(excl),
                file=fp,
            )
            print('\n[pytest]', file=fp)
            print('filterwarnings =', file=fp)
            print('    error::DeprecationWarning', file=fp)
            print('    error::PendingDeprecationWarning', file=fp)
        if touch_to_dot_tox:
            import os
            dot_tox = self._work_dir if work_dir else Path(os.getcwd()) / '.tox'
            # print('##########################', dot_tox.is_dir(), dot_tox, self._path)
            # for key in sorted(os.environ):
            #     print(key, os.environ[key])
            if dot_tox.exists():
                shutil.copystat(str(dot_tox), str(self._path))
                
        if work_dir:
            self._path.copy(self._work_dir)  # for review purposes

    def prepare_commit(self):
        self.write(work_dir=False)
