# coding: utf-8

"""
develop (dv, dvm, dvt) is a wrapper around programs like hg,
make, tox, pytest, devpi, flask8, etc that creates "missing" files
from information in __init__.py, then runs the program and deletes
those "missing" files. It prevents clutter and single source
configuration.

It replaces several options that were only

- Makefile doesn't need to get version using "python setup.py --version", which is slow

ToDo:
- more intelligent pushing of dist files to other servers

"""

import io
import os
import subprocess
import sys
assert sys.version_info > (3, 8, 1)  # i.e running develop in up-to-date Python
import traceback
import time  # NOQA
from datetime import date
from datetime import datetime as date_time
from textwrap import dedent
from contextlib import ContextDecorator
from collections.abc import MutableMapping


from pon import PON
from ruamel.std.pathlib import Path, pushd, popd
from ruamel.showoutput import show_output
from .readme import ReadMe, Changes
from .hgrc import HgRc
from .toxini import ToxIni
from .ununinit import ununinitpy, UnUnInit, version_init_files, set_dev
from .hgignore import dot_hgignore, HgIgnore, GlobalHgIgnore

versions = {
    'py26': [9, date(2013, 10, 29)],
    'py27': [13, None],
    'py30': [1, date(2009, 2, 13)],
    'py31': [5, date(2012, 6, 30), 'https://www.python.org/dev/peps/pep-0375/#maintenance-releases', ],
    'py32': [6, date(2016, 2, 28), 'https://www.python.org/dev/peps/pep-0392/#lifespan'],
    'py33': [7, date(2017, 9, 30), 'https://www.python.org/dev/peps/pep-0398/#lifespan'],
    'py34': [10, date(2019, 3, 18), 'https://www.python.org/dev/peps/pep-0429/'],
    'py35': [7, None, 'https://www.python.org/dev/peps/pep-0478/'],
    'py36': [9, None, 'https://www.python.org/dev/peps/pep-0494/'],
    # 'py37': [5, None, 'https://www.python.org/dev/peps/pep-0494/'],
    # 'py38': [0, None, 'https://www.python.org/dev/peps/pep-/'],
}


mit_license = """\
 The MIT License (MIT)

 Copyright (c) {year} {fullname}

 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.
"""

PIP = '/opt/python/3/bin/pip'
if not os.path.exists(PIP):
    PIP = 'pip'


class TmpFiles(ContextDecorator):
    def __init__(
        self, parent, setup=True, license=True, tox=None, makefile=False, typed=False,
            sub_packages=None, docker=None, manifest=None, nested=False, keep=None,
    ):
        self._rm_after = []
        self.parent = parent
        self.setup = setup
        self.license = license
        self.tox = tox
        self.makefile = makefile
        self.typed = typed
        self._docker = docker
        self._manifest = manifest
        self.sub_packages = sub_packages
        self.nested = nested
        self.keep = parent._args.keep if keep is not None else keep
        self.pon = self.parent.pon  # trigger any check on pon
        self._tox_ini = None  # keep in case of .prepare_commit

    def __enter__(self):
        if self.setup:
            src = Path('~/.config/develop/dv_setup.py').expanduser()
            p = Path('setup.py')
            if not p.exists():
                src.copy(p)
                self._rm_after.append(p)
            elif p.stat().st_mtime < src.stat().st_mtime:
                print('\n>>> setup.py exists and is older than dv_setup.py. Remove? Touch? <<<\n',
                      file=sys.stderr)
            readme = self.parent._readme.setup_checkable_path(generate=False)
            if not readme.exists():
                readme = self.parent._readme.setup_checkable_path()
                self._rm_after.append(readme)
        if self.license:
            lic = self.pon.obj.get('license')
            if lic is None or 'MIT' in lic:
                plic = Path('LICENSE')
                start_year = self.pon.obj['since']  # has to be in __init__.py
                this_year = date.today().year
                if start_year != this_year:
                    year = '{}-{}'.format(start_year, this_year)
                else:
                    year = this_year
                plic.write_text(
                    mit_license.format(year=year, fullname='Anthon van der Neut, Ruamel bvba')
                )
                self._rm_after.append(plic)
        _tox = self.pon.obj.get('tox')
        if self.tox is not None and _tox is None:
            print('no tox specification in __init__.py')
        # print('tox:', _tox)
        if self.tox is not None and _tox is not None:
            # print('subpackages', self.sub_packages, 'nested:', self.nested)
            # sys.stdout.flush()
            self._tox_ini = ToxIni(_tox, work_dir=self.tox, sub_packages=self.sub_packages,
                                   nested=self.nested)
            self._tox_ini.write()
            self._rm_after.append(self._tox_ini._path)
        if self.makefile:
            fpn = self.pon.obj['full_package_name']
            util_name = fpn.rsplit('.', 1)[-1]
            version = self.pon.obj['__version__']
            versiond = version + '0' if version.endswith('.dev') else version
            m = Path('.Makefile.tmp')
            if False:
                mt = Path('Makefile.tmp')
                if m.exists() and not mt.exists():
                    m.rename(mt)
            with m.open('w') as fp:
                print(f'\nUTILNAME:={util_name}', file=fp)
                print(f'PKGNAME:={fpn}', file=fp)
                print(f'INSTPKGNAME:=--pkg {fpn}', file=fp)
                print(f'VERSION:={version}', file=fp)
                print(f'VERSIOND:={versiond}', file=fp)
                # print('\ninclude ~/.config/ruamel_util_new/Makefile.inc', file=fp)
                print('\ninclude ~/.config/develop/Makefile.inc', file=fp)
                # print('\nclean: clean_common', file=fp)  # replaced by dv clean
            self._rm_after.append(m)
        if self.typed:
            t = Path('py.typed')
            t.write_text("")
            self._rm_after.append(t)
        if self._docker is not None:
            self.write_docker(self._docker)
        if self._manifest is not None:
            t = Path('MANIFEST.in')
            if not self._manifest or self._manifest[-1] != '\n':
                self._manifest += '\n'
            t.write_text(self._manifest)
            self._rm_after.append(t)
        return self

    def __exit__(self, typ, value, traceback):
        if typ:
            print('typ', typ)
        if self.keep:
            return
        for p in self._rm_after:
            if not p.exists():
                print('file {} already removed'.format(p))
            else:
                p.unlink()
        bld = Path('build')
        if self.nested and bld.exists():
            bld.rmtree()

    def prepare_commit(self):
        """prepare any files for committing"""
        # only set if generated, not when available
        if os.path.exists('tox.ini') and self._tox_ini:
            self._tox_ini.prepare_commit()

    # following four lines can be added to upgrade auditwheel, thought this was a possible fix
    # while setting up ruamel.yaml.clib, but it wasn't, the .pth filename had to be deleted
    # from the RECORD file (solved in dv_setup.py -> InMemoryZipfile

    # RUN echo '/opt/_internal/cpython-3.6.5/bin/pip install -U auditwheel' >> /usr/bin/makewheel
    # RUN echo ''                                               >> /usr/bin/makewheel
    # RUN echo 'auditwheel --version'                           >> /usr/bin/makewheel
    # RUN echo ''                                               >> /usr/bin/makewheel

    docker_file_template = """\
    FROM {from}

    MAINTAINER {maintainer}

    RUN echo '[global]' > /etc/pip.conf
    RUN echo 'disable-pip-version-check = true' >> /etc/pip.conf

    RUN echo 'cd /src' > /usr/bin/makewheel
    RUN echo 'rm -f /tmp/*.whl'                               >> /usr/bin/makewheel
    RUN echo 'for PYVER in $*; do'                            >> /usr/bin/makewheel
    RUN echo '  for PYBIN in /opt/python/cp$PYVER*/bin/; do'  >> /usr/bin/makewheel
    RUN echo '     echo "$PYBIN"'                             >> /usr/bin/makewheel
    RUN echo '     ${{PYBIN}}/pip install -Uq pip'            >> /usr/bin/makewheel
    RUN echo '     ${{PYBIN}}/pip wheel . -w /tmp'            >> /usr/bin/makewheel
    RUN echo '  done'                                         >> /usr/bin/makewheel
    RUN echo 'done'                                           >> /usr/bin/makewheel
    RUN echo ''                                               >> /usr/bin/makewheel
    RUN echo 'for whl in /tmp/*.whl; do'                      >> /usr/bin/makewheel
    RUN echo '  echo processing "$whl"'                       >> /usr/bin/makewheel
    RUN echo '  auditwheel show "$whl"'                       >> /usr/bin/makewheel
    RUN echo '  auditwheel repair "$whl" -w /src/dist/'       >> /usr/bin/makewheel
    RUN echo 'done'                                           >> /usr/bin/makewheel
    RUN chmod 755 /usr/bin/makewheel

    CMD /usr/bin/makewheel {ml_versions_to_build}
    """  # NOQA

    docker_compose_file_template = """\
    version: '2'
    user-data:
      author: {maintainer}
      description: manylinux wheel build container for {full_package_name}
      env-defaults:
        PYDISTBASE: /tmp    # for building, normally set by `dv --distbase`
    services:
     {under_fpn}_manylinux1:
        container_name: {under_fpn}
        build: .
        volumes:
        - ${{PYDISTBASE}}/{full_package_name}:/src/dist
        - .:/src
    """  # NOQA

    def write_docker(self, d):
        t = Path('Dockerfile')
        self._rm_after.append(t)
        t.write_text(dedent(self.docker_file_template).format(**d))
        t = Path('docker-compose.yaml')
        self._rm_after.append(t)
        t.write_text(dedent(self.docker_compose_file_template).format(**d))

class DevelopError(Exception):
    pass


class Log:
    def __init__(self):
        pass

    def __enter__(self):
        print('__enter__')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print('__exit__')


PKG_DATA = '_package_data'


class Develop:
    def __init__(self, args, config):
        self._args = args
        self._config = config
        self.do_tag = True
        self.old_dist_dir = Path('dist')
        self.old_tox_dir = Path('.tox')
        # self.readme_path = Path('README.rst')
        # self._readme = ReadMe(self.readme_path)
        self._readme = ReadMe()
        self._changes = Changes()
        self._hgrc = HgRc()
        self.readme_path = self._readme.path
        self._readme.remove_any_derivatives()
        self._tox_cmd = 'detox' if self._args.detox else 'tox'
        if False:
            for line in self._readme.lines[12:20]:
                print('>', line)
            print('idx', self._readme.find_single_line_starting_with('  - add'))
        self.commit_message_file = Path('.hg/commit_message.txt')
        # self.docker_file = Path('Dockerfile')
        self._version = None
        self._version_s = None

    @property
    def docker_data(self):
        attr = '_' + sys._getframe().f_code.co_name
        if not hasattr(self, attr):
            d = None
            if self.pon.obj.get('ext_modules', False):
                fpn = self.pon.obj['full_package_name']
                d = {
                    'from': 'quay.io/pypa/manylinux1_x86_64:latest',
                    'ml_versions_to_build': '27 35 36 37 38 39',
                    'maintainer': self._args.maintainer,
                    'full_package_name': fpn,
                    'under_fpn': fpn.replace('.', '_')  # no dots in container name
                }
            setattr(self, attr, d)
        return getattr(self, attr)

    def repo_status(self):
        """check various stati related to versioning/packaging"""
        from repo.status import unclean_list, check_output

        if self._args.verbose > 0:
            print('check repo status', end=' ')
            sys.stdout.flush()
        ok = True
        # status of the repository
        lst = unclean_list()
        if lst:
            ok = False
            if self._args.verbose > 0:
                print('-> NOT ok')
            print('repo will not be clean after commit')
            for k in lst:
                print(' ', k)
        branch = check_output(['hg', 'branch']).strip()
        if branch != 'default':
            if self._args.verbose > 0:
                print('-> NOT ok')
            ok = False
            print('not on default branch [{}]'.format(branch))
        if False:
            # the following is not enough for a readme check, e.g on "`Anthon <>`__"
            cmd = [
                    '/opt/util/py38/bin/python',
                    'setup.py',
                    'check',
                    #'--strict',
                    #'--restructuredtext',
                    '--metadata',
                ]
            rant_rant = """

            In the build process that I use for generating Python package
            distributions, I check for errors in the README (ReST format) up
            front, using

            python setup.py check --strict --restructuredtext --metadata

            I run multiple of these kind of sanity checks, which all have to
            pass before even starting the rest of the process: running tests
            for multiple python version, committing, pushing the repository,
            and then generating sdist and wheel files and uploading those to
            PyPI (or the internal website). Each of these steps have to
            complete successfully before continuing, and once the sanity checks
            have passed they normally do.

            The previous command has started issuing a warning:

            > warning: Check: This command has been deprecated. Use `twine check` instead:
            https://packaging.python.org/guides/making-a-pypi-friendly-readme#validating-restructuredtext-markup

            And if you follow that link it indicates that you have to generate
            sdist and wheel files and then run `twine check` on the files in
            the dist directory.

            That is course unacceptable, as those are available far too late in
            the build process. Generating the wheel files can take over an hour
            for some of the packages with C extensions (being built using
            manylinux, a remote Apple Mac and Appveyor for the windows wheels).
            I cannot wait that long only to find out I made some formatting
            error in my README and then have to restart the process.

            The sdist generation is relatively quick (compared to the wheels),
            so I could generate that an extra time and run `twine check` before
            continuing with testing and the rest of the build process. I can
            also rerun the `twine check` on both the sdist and the ~20 wheel
            files that could have been generated. Or could just invoke
            `readme_renderer.rst` on the README myself and check the result.

            What errors could be found by `twine check` in the reStructuredText
            markup for the **wheels**, that would not be found on the **sdist**
            package, based on the same source?
            """

            # cmd = ['twine', 'check']
            res = check_output(cmd)
            print('res', repr(res))
            ress = res.replace("The project's long description is valid RST.", '')
            ress = ress.rstrip()
            print('ress', repr(ress))
            sys.exit(1)
            if not self._args.test and ress != 'running check':
                if self._args.verbose > 0:
                    print('-> NOT ok')
                print('running check: [{}]'.format(res))
                ok = False
        if ok and self._args.verbose > 0:
            print('-> ok')
        return ok

    def readme_check(self, version_bumped=None):
        from io import StringIO
        from readme_renderer import rst

        ok = True
        try:
            repo_ssh = self._hgrc['paths']['sourceforge']
        except FileNotFoundError:
            repo_ssh = None
        try:
            repo_url = 'https://sourceforge.net/p' + repo_ssh.split('.net/p', 1)[1]
        except:
            repo_url = None
        self._readme.check_update_oitnb_svg()
        self._readme.check_update_ryd_svg()
        if repo_url:
            self._readme.check_update_license_svg(repo_url)
            self._readme.check_update_pypi_svg(repo_url, self.pon.obj['full_package_name'])
        readme = self._readme.setup_checkable_path()
        if self._args.verbose > 0:
            print('checking {}'.format(readme), end=' ')
            sys.stdout.flush()
        warnings = StringIO()
        text = readme.read_text()
        for badge in '_doc/_static/license.svg _doc/_static/pypi.svg'.split():
            if badge in text:
                if not Path(badge).exists():
                    print(f'develop: badge {badge} not found')
                    ok = False
                # check if under revision control
        if '\n\nNEXT:' not in text and 'ChangeLog' in text:
            if ok:
                print('-> NOT ok')
            print('develop: NEXT: not found')
            ok = False
        out = rst.render(text, stream=warnings)
        if out is None:
            if ok:
                print('-> NOT ok')
            print(warnings.getvalue())
            ok = False
        if ok and self._args.verbose > 0:
            print('-> ok')
        return ok

    def build_check(self):
        ok = True
        file_name = Path('build')
        if self._args.verbose > 0:
            print('checking {}'.format(file_name), end=' ')
            sys.stdout.flush()
        if file_name.exists():
            if self._args.verbose > 0 and ok:
                print(f'-> NOT ok\n  {file_name} directory found, run "dv clean" first')
            ok = False
        if ok and self._args.verbose > 0:
            print('-> ok')
        return ok


    @property
    def pon(self):
        attr = '_' + sys._getframe().f_code.co_name
        if not hasattr(self, attr):
            pon = PON()
            try:
                with io.open(ununinitpy) as fp:
                    res = None
                    try:
                        res = pon.extract(fp, start=PKG_DATA)
                    except Exception as _e:
                        traceback.print_exc()
                    if res is None:
                        print(f'\nCould not extract {PKG_DATA} from {ununinitpy}')
                        sys.exit(-1)
                    else:
                        check_init_pon(ununinitpy, pon)
            except FileNotFoundError:
                d = os.getcwd()
                print(f'no {ununinitpy} found in {d}')
                sys.exit(-1)
            setattr(self, attr, pon)
        return getattr(self, attr)

    def tox(self):
        if self._args.E:
            _tox_ini = ToxIni(self.pon.obj.get('tox'))
            print('envlist = {}'.format(','.join(_tox_ini.envlist())))
            return
        tox_wd = self.check_tox_dir()
        with TmpFiles(
                self, tox=tox_wd,
                docker=self.docker_data,
                manifest=self.pon.obj.get('manifest', None),
                sub_packages=self.sub_packages, nested=self.nested,
                keep=self._args.keep,
        ):
            try:
                args = self._args.args
                cmd = [self._tox_cmd]
                if self._args.e:
                    cmd = ['tox']
                    args = ['-e', self._args.e] + args
                    # -q only for tox
                    if self._args.q:
                        args = ['-' + 'q' * self._args.q] + args
                if self._args.r:
                    args = ['-r'] + args
                res = show_output(cmd + args, show_command=True)
            except subprocess.CalledProcessError:
                return
            print('res:', res)

    def mypy(self):
        # we could have files in subdirectories that need inclusion, and
        # for that you have to walk the subtree, skip any sub-packages
        # base on their __init__.py:_package_data['nested']
        # for now (ruamel.yaml) solve as the Makefile did
        # MYPYSRC:=$(shell ls -1 *.py | grep -Ev "^(setup.py|.*_flymake.py)$$" | \
        #    sed 's|^|ruamel/yaml/|')
        # MYPYOPT:=--py2 --strict --follow-imports silent
        #
        # mypy:
        #       @echo 'mypy *.py'
        #       @cd ../.. ; mypy $(MYPYOPT) $(MYPYSRC)
        #       mypy $(MYPYOPT) $(MYPYSRC1)
        res = None
        options = ['--py2', '--strict', '--follow-imports', 'silent']
        options = ['--no-warn-unused-ignores', '--strict', '--follow-imports', 'silent']
        options = ['--strict', '--follow-imports', 'silent']
        fpn_split = self.pon.obj['full_package_name'].split('.')
        _root_dir = '/'.join(['..'] * len(fpn_split))
        pushd(_root_dir)
        pkg_path = Path('/'.join(fpn_split))
        files = []
        for path in pkg_path.glob('*.py'):
            if path.name.startswith('.#'):
                continue
            if path.name == 'setup.py':  # might not be there
                continue
            if path.stem.endswith('_flymake'):
                continue
            files.append(path)
            # print(' ', path)
        # print(len(files))
        return_code = 0
        try:
            res = show_output(['mypy'] + options + files, verbose=1, show_command='\\')
        except subprocess.CalledProcessError as e:
            for line in e.output.splitlines():
                if ': error:' in line or ': note:' in line:
                    file_name, line, _ = line.split(':', 2)
                    break
            # print(Path(file_name).resolve(), line)
            self.edit_one(Path(file_name).resolve(), line)
            return_code = e.returncode
        if res:
            print(res)
        popd()
        return return_code

    # ToDo: old review
    def edit_one(self, full_name=None, line=None, column=None):
        # from oruamel.misc.emacs import load_in_emacs, split_emacs_window
        editor = 'kakoune'
        # editor = 'vi'
        if editor == 'emacs':
            from ruamel.edit import Emacs
            # calling em does not work:
            # "emacs: standard input is not a tty"
            # cmd = ['/home/bin/em', '-nw']
            # Emacs(verbose=self._args.verbose).load((full_name, line, column))
            Emacs(verbose=2).load((full_name, line, column))
            return
        elif editor == 'vim':
            from ruamel.edit import Vi
            Vi(verbose=self._args.verbose).load((full_name, line, column))
            # cmd = ['/usr/bin/vi']
            # if line is not None:
            #     if column is not None:
            #         cmd.append("+call cursor({},{})".format(line, column))
            #     else:
            #         cmd.append("+{}".format(line))
            return
        elif editor == 'kakoune':
            from ruamel.edit import Kakoune
            Kakoune(verbose=self._args.verbose).load(full_name, line, column)
            return
        else:
            print('self._args.editor', editor)
            raise NotImplementedError
        if self._args.verbose > 0:
            print('full_name?', full_name)
        if isinstance(full_name, (str, Path)):
            cmd.append(str(full_name))
            # self.call(cmd)
            if callable(cmd[0]):
                cmd[0](cmd[1:])
        # elif isinstance(full_name, list):
        #    file_names = [self._tdm.get_full_name(x) for x in full_name]
        #    cmd.extend(file_names)
        #    self.call(cmd)



    def make(self):
        try:
            util_name = self.pon.get('util')
            if util_name:
                os.environ['OPTUTILNAME'] = util_name
        except KeyError:
            pass
        try:
            entry_points = self.pon.get('entry_points')  # NOQA
            obn = entry_points
            # 1)    entry_points='dv=develop.__main__:main',
            # 2)    entry_points=dict(
            #           console_scripts=['oitnb=oitnb.oitnb:main', 'omeld=oitnb.omeld:main'],
            #       ),

            if obn:
                if isinstance(obn, dict):
                    obn = obn[list(obn.keys())[0]]
                if isinstance(obn, list):
                    obn = obn[0]
                os.environ['OPTBINNAME'] = obn.split('=', 1)[0].strip()
        except KeyError:
            pass
        self.check_dist_dir()
        self.use_alternative('clean')
        with TmpFiles(self, makefile=True, sub_packages=self.sub_packages, typed=self.typed,
                      nested=self.nested, keep=self._args.keep):
            if self._args.args:
                try:
                    res = show_output(['make', '-f', '.Makefile.tmp'] + self._args.args)
                    res = None  # NOQA
                except subprocess.CalledProcessError:
                    sys.exit(0)

    def use_alternative(self, alternatives):
        if not isinstance(alternatives, list):
            alternatives = [alternatives]
        try:
            arg0 = self._args.args[0]
        except IndexError:
            return None
        if arg0 and arg0 in alternatives:
            print('Use:\n   dv {}\n.'.format(self._args.args[0]))
            sys.exit(1)
        return False

    def version(self):
        """
        this currently directly calls the various (package)version commands
        (-> direct dv replacement if available):

        show                show current version
        bump                bump version number if equal to latest on PyPI
        major               bump minor version number
        minor               bump minor version number
        micro               bump micro version number
        dev                 set/unset dev
        update              update to preferred __init__.py etc
        license             update license info
        status              check status of project
        push                check, commit, push, upload and bump if everything ok
        bitbucket           create/check bitbucket
        test                test package setup (conformity, pypi, bitbucket)

        "dvv" equals "dv version" use "dvv -- push --reuse --no-tox" to end commandline
        interpretation
        """
        if self._args.badge:
            return self.version_badge(force=True)
        if len(self._args.args) == 1 and self._args.args[0] in ['major', 'minor', 'micro']:
            uui = UnUnInit(ununinitpy)
            uui.update_versions(mmm=self._args.args[0], dev=self._args.dev)
            uui.write_if_changed()
            return 
        if self._args.dev is not None:
            uui = UnUnInit(ununinitpy)
            uui.update_versions(mmm=None, dev=self._args.dev)
            uui.write_if_changed()
            return
            # assert self._args.dev != self._args.rm_dev
            # return set_dev(self._args.dev, save=True)
        if self._args.args and self._args.args[0] == 'push':
            print('Use:\n   dv {}\n'.format(self._args.args[0]))
            # with TmpFiles(self, license=True, tox=True, makefile=True):
            #     self.do_version()
            return
        if self._args.args and 'dev' in self._args.args:
            print('Use:\n   dv version --dev\n')
            return
        print('>>>>>>>> really?', self._args)
        self.do_version()

    def version_badge(self, version=None, include_dev=False, force=False, text_badge='pypi'):
        """if not force just try to find, but don't error if you can't

        Need to test with firefox/chrome as eog does not use all .svg stuff (textwidth!)
        """
        badge = Path('_doc/_static/{}.svg'.format(text_badge))
        if force:
            assert badge.is_file()
        elif not badge.exists():
            return
        text = badge.read_text()
        if '{version}' in text:
            text = text.replace('{version}', '1.2.3')
        if version is None:
            with io.open(ununinitpy) as fp:
                pon = PON()
                pon.extract(fp, start=PKG_DATA)
                version = pon.obj.get('__version__')
                if not include_dev:
                    version = version.replace('.dev', "")
        split = text.split('</text>')
        old_version = None
        for idx, s in enumerate(split):
            if s.endswith('>' + text_badge):
                continue
            base, end = s.rsplit('>', 1)
            if not end.strip():
                continue
            # print('base end', repr(end))
            if old_version is None:
                old_version = end
            else:
                assert (
                    old_version == end
                ), f'different versions in {text_badge} badge: "{old_version}" and "{end}"'
            split[idx] = base + '>' + version
            if old_version and old_version == end:
                text = '</text>'.join(split)
                badge.write_text(text)
            else:
                print('no version to replace found')
        # Maybe also need to set the last two textlengths

        # print(text.replace('>', '>\n'))
        # print('--- done')

    def badge(self):
        from .badges import badges
        badges.write('mit')
        if self._args.oitnb:
            badges.write('oitnb')
        badges.write('version')
        print('run dv version --badge to update pypi version badge')

    def clean(self):
        cmds = [
            'rm -rf build .tox {}.egg-info/ _doc/*.pdf _doc/_build'.format(
                self.pon.obj['full_package_name']
            ),
            'find . -name "*.py[co]" -exec rm {} +',
            'find . -name "*~" -exec rm {} +',
            'find . -name "*.orig" -exec rm {} +',
            'find . -name "__pycache__" -print0  | xargs -r -0 rm -rf',
        ]
        for cmd in cmds:
            print(cmd)
            os.system(cmd)

    def rtfd(self):
        rtfdn = self.pon.obj['read_the_docs']
        if self._args.build:
            return self.build_rtfd_doc(rtfd_name=rtfdn)
        if self._args.show:
            return open_in_browser(f'https://{rtfdn}.readthedocs.io/en/latest/')
        if self._args.admin:
            return open_in_browser(f'https://readthedocs.org/projects/{rtfdn}/')
        print('rtfd --what?')

    def commit(self):
        excl = [] if self._args.all else ['--exclude', '__init__.py', '--exclude', 'README.*']
        cmd = ['hg', 'commit']
        cmd.extend(excl)
        os.system(' '.join(cmd))

    #####


    def environment_sane(self):
        """
        Here the environment is checked, try to run all possible checks instead
        of erroring out on the first one.

        Print commentary about what is wrong, use check('stage', test, optional_msg).
        At the end ok should be the empty list if everything is in order.
        """
        from .hglib import open as hg_open

        ok = []

        def stage_check(stage, result, msg=None):
            """if result is not True, append the string stage to ok and write
            msg if one is given. return inverse of result, i.e. check failed
            """
            # always flush (as auto needs that), message might be direclty printed by test
            if result:
                sys.stdout.flush()
                return False
            if msg is not None:
                print(msg)
                sys.stdout.flush()
            if stage not in ok:
                ok.append(stage)
            return True

        stage_check('print', self.print_check())
        stage_check('devpi_logged_in', self.devpi_logged_in())
        # get latest version from hg history? and check if __init__ has been updated.
        client = hg_open('.')
        committed_version = [0, 0, 0]
        for tag, _change, _hash, _local in client.tags():
            if tag == b'tip' or tag == b'appveyor/master':
                continue
            committed_version = [
                int(i) if i[0].isalnum() else i for i in tag.decode('utf-8').split('.')
            ]
            # tag = tag.decode('utf-8').split('.')
            print('committed_version', committed_version)
            break
        # check some pon stuff
        if 'python_requires' not in self.pon:
            print('add\n    python_requires=\'>=3.6\',\nto package data in __init__.py')
            ok.append('python_requires')
        # check latest version on pypi
        if False:
            # 2021-03-21 xmlrpc down:
            # "RuntimeError: PyPI's XMLRPC API is currently disabled due to unmanageable load and will be deprecated in the near future.
            # See https://status.python.org/ for more information."
            fpn = self.pon.obj['full_package_name']
            cmd = [PIP, '--disable-pip-version-check', 'search', fpn]
            res = subprocess.check_output(cmd).decode('utf-8')
            fpn += ' '
            for line in res.splitlines():
                if line.startswith(fpn):
                    pypi_version = [int(x) for x in line.split('(')[1].split(')')[0].split('.')]
                    if pypi_version and pypi_version > committed_version:
                        print('pypi version', pypi_version)
                        committed_version = pypi_version
                        break

        if False:
            print('ok:', ok)
            print(self._args.from_develop)
            print()
            return
        # should add the show_subdirs=True parameter?
        for idx, (file_name, version, comment) in enumerate(version_init_files('.')):
            if idx != 0:  # there can be only one
                print('more than one version_init_file {} found'.format(file_name))
                break
            stage_check('version', comment == "", comment)
            if self._args.verbose > 0:
                print('filename', file_name)
            print('version', version)
            stage_check('version', 'dev' in version, 'no "dev" in version')
            stage_check('version',  committed_version[0:3] < version[0:3], 'version not bumped')
        self._version = version[:3]
        self._version_s = '.'.join([str(t) for t in self._version])
        # if self._args.changestest:
        #    self.check_update_readme(version, testing=True)
        #    return
        stage_check('check_nested', self.check_nested())
        stage_check('readme', self.readme_check())
        if self._changes.exists():
            stage_check('changes', self._changes.check(self._version))
        stage_check('status', self.repo_status())
        stage_check('build', self.build_check())
        if ok != []:
            print('\nnot ok', ok)
            return False
        stage_check('flake_it', self.flake_it())
        if ok != []:
            print('\nnot ok', ok)
            return False
        return True

    def flake_it(self):
        # if not tox.ini -> don't run
        if not os.path.exists('tox.ini'):
            return True
        try:
            show_output(['flake8'])
        except Exception as e:
            return False
        return True

    def check_commit_message_file(self):
        """
        check if commit message exists, if not create it, edit and strip
        stripping is necessary because --logfile doesn't do this
        """
        try:
            text = self._args.commit_message
            if text:
                raise NotImplementedError
        except AttributeError:
            pass
        if self._args.reuse_message:
            if not self.commit_message_file.exists():
                print(
                    "reuse specified but {} doesn't exist. do:\n\n{}\n".format(
                        self.commit_message_file,
                        '    cp -i .hg/last-message.txt .hg/commit_message.txt',
                    )
                )
                return False
            return True
        try:
            self.commit_message_file.unlink()
        except OSError:
            pass
        old_env = os.environ.get('EDITOR')
        os.environ['EDITOR'] = 'ex'
        os.system('echo "wq {}" | hg commit 2>/dev/null'.format(self.commit_message_file))
        if old_env is None:
            del os.environ['EDITOR']
        else:
            os.environ['EDITOR'] = 'ex'
        # Now done in ~/.hgrc
        # txt = self.commit_message_file.read_text()
        # txt.replace('HG:', 'HG: Please close this issue if you can confirm it solves'
        #             ' the reported problem\n\n', 1)

        # self.commit_message_file.write_text(txt)
        # print('txt\n', txt)
        os.system('vi {}'.format(self.commit_message_file))
        text = ""
        with self.commit_message_file.open() as fp:
            for line in fp:
                if line.startswith('HG:'):
                    continue
                text += line
        text = text.strip()  # removes trailing empty lines
        if text == "":
            print('error: empty message file', self.commit_message_file)
            self.commit_message_file.unlink()
            return False
        text += '\n'
        self.commit_message_file.write_text(text)
        return True

    @property
    def nested(self):
        attr = '_' + sys._getframe().f_code.co_name
        if not hasattr(self, attr):
            setattr(self, attr, self.pon.obj.get('nested'))
        return getattr(self, attr)

    def check_nested(self):
        """check if there is a parent __init__.py file that is just for commits
        in that case `nested=True,` should be in the package data
        """
        if self._args.verbose > 0:
            print('checking if nested', end=' ')
        if self.nested:
            if self._args.verbose > 0:
                print('-> ok')
            return True
        parent_init_py = Path('..') / ununinitpy
        if '_package_data = dict' not in parent_init_py.read_text():
            if self._args.verbose > 0:
                print('-> ok')
            return True
        if self._args.verbose > 0:
            print('-> NOT ok')
        print(f'this is a nested package, but "nested=True" is not in {ununinitpy}')
        return False

    def devpi_logged_in(self):
        from repo.status import check_output

        if self._args.verbose > 0:
            print('check if logged in to devpi', end=' ')
        cmd = ['devpi', 'use']
        try:
            res = check_output(cmd)
        except subprocess.CalledProcessError as e:
            print(e.output.decode('utf-8'))
            print('while running', cmd)
            sys.exit(0)
        first_line = res.split('\n', 1)[0]
        if '(not logged in)' in first_line and 'logged in as' not in first_line:
            print('devpi not logged in (check crontab?):\n  ', first_line)
            return False
        if self._args.verbose > 0:
            print('-> ok')
        return True

    def check(self):
        self.check_dist_dir()
        tox_wd = self.check_tox_dir()
        self._args.test = False
        with TmpFiles(
            self, license=True, tox=tox_wd, makefile=True, sub_packages=self.sub_packages, 
                nested=self.nested
        ):
            if not self.environment_sane():
                print('environment is not sane')

    @property
    def typed(self):
        attr = '_' + sys._getframe().f_code.co_name
        if not hasattr(self, attr):
            setattr(self, attr, 'Typing :: Typed' in self.pon.obj.get('classifiers', []))
        return getattr(self, attr)

    def push(self):
        self.check_dist_dir()
        if Path('build').exists():
            print('build directory found, run "dv clean" first')
            return
        tox_wd = self.check_tox_dir()
        with TmpFiles(
            self, license=True, tox=tox_wd, makefile=True, typed=self.typed,
            docker=self.docker_data,
            manifest=self.pon.obj.get('manifest', None),
            sub_packages=self.sub_packages, nested=self.nested
        ) as tf:
            # --from-develop gradually suppresses actions implemented in version
            # taken over by develop
            if not self.environment_sane():
                print('environment is not sane')
                return
            dd = self._args.date
            if dd in ['TODAY', None]:
                dd = date.today()
            if not self.update_readme_and_changes_files(self._version, dd):
                print('update_readme_and_changes_files FAILED')
                return
            if not self.check_commit_message_file():
                print('check_commit_message_file')
                self._readme.revert()
                self._changes.revert()
                return
            uui = UnUnInit(ununinitpy)
            uui.update_versions(mmm=None, dev=False)
            uui.write_if_changed()
            # self._version has now been set
            # set_dev(False, save=True)
            if self.push_do_tox():
                set_dev(True, save=True)
                self._readme.revert()
                self._changes.revert()
                return
            tf.prepare_commit()  # changes e.g. tox file
            if self.push_do_commit():
                return
            if self.push_do_tag(self._version):
                return
            self.do_push_to_ruamel_eu()
            # upload
            self.do_push_to_sourceforge()
            # trigger rtd build

            # XXXXX
            # cmd = ['version', 'push', '--from-develop']
            # if self._args.reuse_message:
            #     cmd.append('--reuse-message')
            # print('calling package_version', cmd)
            # os.system(' '.join(cmd))
            # print('<<<<<<<<<<<<<<<<<<<')
            # return
            self.create_distributions()
            # self.build_rtfd_doc()
        print('>>>>')

    def do_push_to_sourceforge(self):
        cmd = ['hg', 'push', 'sourceforge', '--new-branch']
        try:
            print('pushing to sourceforge')
            show_output(cmd)
        except subprocess.CalledProcessError as e:
            try:
                output = e.output.decode('utf-8')
            except AttributeError:
                output = e.output
            print('output:\n', output)

    def do_push_to_bitbucket(self):
        cmd = [
            'ssh',
            '-x',
            '-a',
            'ruamel@localhost',
            'cd {}; hg push bitbucket --branch default'.format(os.getcwd()),
        ]
        try:
            print('pushing to bitbucket')
            show_output(cmd)
        except subprocess.CalledProcessError as e:
            try:
                output = e.output.decode('utf-8')
            except AttributeError:
                output = e.output
            print('output:\n', output)

    def do_push_to_ruamel_eu(self):
        cmd = ['hg', 'push', '--new-branch']
        try:
            print('pushing to ruamel')
            show_output(cmd)
        except subprocess.CalledProcessError as e:
            try:
                output = e.output.decode('utf-8')
            except AttributeError:
                output = e.output
            if 'there is no Mercurial repository here' in output:
                ssh_remote_mkdir()
                show_output(cmd)  # try again, don't catch errors
            else:
                print('output of hg push:\n', output)

    def rm_old_dist_dir(self):
        if self.old_dist_dir.exists():
            # manylinux1 currently creates this
            try:
                self.old_dist_dir.rmdir()
            except Exception:
                print('cannot remove "{}"'.format())

    def push_do_tox(self):
        """
        return False if ok
        """
        if not self._args.no_tox and os.path.exists('tox.ini'):
            cmd = [self._tox_cmd, '-r']
            if self._args.e:
                cmd = ['tox', '-r']
                cmd.extend(['-e', self._args.e])
            try:
                res = show_output(cmd, show_command=True)  # NOQA
            except subprocess.CalledProcessError as e:
                print('error running tox', str(e))
                return True
        return False

    def push_do_commit(self):
        """
        return False if ok
        """
        from repo.status import status_list

        lst = status_list()
        self.version_badge()
        if lst:  # there is something to commit, normally at least __init__.py
            # commit
            if self.commit_message_file.exists():
                try:
                    show_output(['hg', 'commit', '--logfile', self.commit_message_file])
                except subprocess.CalledProcessError as e:
                    print('error committing with message file', str(e))
                    return True
                self.commit_message_file.unlink()
            else:
                os.system('hg commit')
            # make sure commit happened
            lst = status_list()
            if lst:
                print('repo not clean after commit, aborting')
                for k in lst:
                    print(' ', k)
                return True
        return False

    def push_do_tag(self, version):
        from repo.status import check_output

        str_version = '.'.join([str(x) for x in version])
        res = check_output(['hg', 'tags'])
        if self.do_tag and '\n' + str_version not in res:
            # tag if not yet there
            check_output(['hg', 'tag', str_version])
            self.sourceforge_upload()  # upload latest tarball
            return False
        else:
            print('already tagged')
        return True
        # push to ruamel

    def do_version(self):
        # show_output(sys.argv[1:])
        cmd = 'version ' + ' '.join(self._args.args)
        # print('cmd:', cmd)
        os.system(cmd)  # so you can edit

    def readme(self):
        """
        update date and version in Readme as necessary.
        If there is a section NEXT: followed by bullit items, take that to be the changes
        for the new version.
        """
        dd = self._args.date
        if dd in ['TODAY', None]:
            dd = date.today()
        print(f'dd: {dd}')
        try:
            version = [str(t) for t in self._args.version.split('.')]
            print(f'version: {version}')
        except AttributeError:
            print('no new version provided')
            version = None
            self.readme_check()
            self._readme.write_if_changed()
            return
        self.update_readme_and_changes_files(version, dd)

    def update_readme_and_changes_files(self, version, dd):
        next_text = 'NEXT:'  # has to be an empty newline before NEXT:

        def extract_next(text):
            lines = text.splitlines()
            gather = None
            version_line = None
            date_line = None
            for idx, line in enumerate(lines):
                if version_line is None and line.startswith(':version:'):
                    version_line = idx
                if date_line is None and (
                    line.startswith(':updated:') or line.startswith(':date:')
                ):
                    date_line = idx
                if line.startswith(next_text):
                    gather = []
                    continue
                if gather is None:
                    continue
                if line and line[0] != ' ':
                    break
                gather.append(line)
            if gather is None:
                return False, None, None
            return '\n'.join(gather), version_line, date_line

        def first_word_with_following_spaces(line):
            space = False
            for idx, ch in enumerate(line):
                if space and not ch.isspace():
                    return line[:idx]
                if ch.isspace():
                    space = True
            raise Exception('no space found')

        # assert not self._readme.has_been_read()
        try:
            testing = self._args.test_readme_message
            print('testing', testing)
        except Exception:
            testing = False
        if testing:
            ver, testing = testing.split('|')
            self._readme.text = self._readme.text.replace(
                '\n' + ver, f'\nNEXT:\n  - {testing}\n\n{ver}'
            )
        line_with_next = self._readme.find_single_line_starting_with(
            next_text, raise_on_error=False
        )
        if self._changes.exists() and line_with_next is None:
            #  and '\n\n' + next_text not in text:
            print(f'no single {next_text} entry in README, but CHANGES exists')
            return False
        version_s = '.'.join([str(t) for t in version[:3]])
        new_version = '\n{} ({}):'.format(version_s, dd)
        # print(text[:2000])
        gather, version_line, date_line = extract_next(self._readme.text)
        if self._args.verbose > 1:
            print(
                'extracted:',
                gather,
                self._readme.lines[version_line],
                self._readme.lines[date_line],
                sep='\n',
            )
        assert gather is not None
        # update readme
        if gather:
            if self._args.verbose > 0:
                print('inserting version string', version_s)
            self._readme.text = self._readme.text.replace('\n' + next_text, new_version)
            self._readme.lines[version_line] = (
                first_word_with_following_spaces(self._readme.lines[version_line]) + version_s
            )
            self._readme.lines[date_line] = first_word_with_following_spaces(
                self._readme.lines[date_line]
            ) + str(dd)
            self._readme._text = None
            self._readme.changed = True
        self._readme.write_if_changed()
        if self._args.verbose > 1:
            print(
                'updated:',
                gather,
                self._readme.lines[version_line],
                self._readme.lines[date_line],
                sep='\n',
            )
        # update changes
        if self._changes.exists():
            # ch_text = changes.read_text()
            # version_int = [int(t) for t in version[:3]]
            # changes.write_text(f'{version_int}: {dd}\n{gather}\n{ch_text}')
            ch_text = self._changes.text
            version_int = [int(t) for t in version[:3]]
            self._changes.text = f'{version_int}: {dd}\n{gather}\n{ch_text}'
            self._changes.write()
        return True

    docker_file_template = """
    FROM quay.io/pypa/manylinux1_x86_64:{}

    MAINTAINER Anthon van der Neut <a.van.der.neut@ruamel.eu>

    RUN echo '[global]' > /etc/pip.conf
    RUN echo 'disable-pip-version-check = true' >> /etc/pip.conf

    RUN echo 'cd /src' > /usr/bin/makewheel
    RUN echo 'rm -f /tmp/*.whl'                               >> /usr/bin/makewheel
    RUN echo 'for PYVER in $*; do'                            >> /usr/bin/makewheel
    RUN echo '  for PYBIN in /opt/python/cp$PYVER*/bin/; do'  >> /usr/bin/makewheel
    RUN echo '     echo "$PYBIN"'                             >> /usr/bin/makewheel
    RUN echo '     ${{PYBIN}}/pip install -Uq pip'              >> /usr/bin/makewheel
    RUN echo '     ${{PYBIN}}/pip wheel . -w /tmp'              >> /usr/bin/makewheel
    RUN echo '  done'                                         >> /usr/bin/makewheel
    RUN echo 'done'                                           >> /usr/bin/makewheel
    RUN echo ''                                               >> /usr/bin/makewheel
    RUN echo 'for whl in /tmp/*.whl; do'                      >> /usr/bin/makewheel
    RUN echo '  echo processing "$whl"'                       >> /usr/bin/makewheel
    RUN echo '  auditwheel show "$whl"'                       >> /usr/bin/makewheel
    RUN echo '  auditwheel repair "$whl" -w /src/dist/'       >> /usr/bin/makewheel
    RUN echo 'done'                                           >> /usr/bin/makewheel
    RUN chmod 755 /usr/bin/makewheel


    CMD /usr/bin/makewheel {}

    # cp27-cp27m p27-cp27mu cp34-cp34m cp35-cp35m cp36-cp36m cp37-cp37m
    """  # NOQA

    def dist(self):
        s = l = m = w = a = False
        u = self.pon.obj.get('universal')
        py_req = self.pon.obj.get('python_requires')
        if self._args.all:
            if u:
                s = a = True
            elif py_req:
                s = a = True
            else:
                s = l = m = w = True
        else:
            s = self._args.sdist
            if s and u:
                a = True
            l = self._args.linux
            m = self._args.macos
            w = self._args.windows
        kw = self._args.kw
        return self.do_dist(do_sdist=s, do_linux=l, do_macos=m, do_windows=w, do_any=a, kw=kw)

    def create_distributions(self):
        wheels = self.pon.obj.get('wheels', {})
        l = wheels.get('linux')
        m = wheels.get('macos')
        w = wheels.get('windows')
        s = wheels.get('src', True)
        a = self.pon.obj.get('universal', self.pon.obj.get('python_requires', False))
        return self.do_dist(do_sdist=s, do_linux=l, do_macos=m, do_windows=w, do_any=a, keep=True)

    def do_dist(self, do_sdist=None, do_linux=None, do_macos=None, do_windows=None, do_any=None,
                kw=False, keep=None):
        from repo.status import check_output

        if keep is None:
            keep = self._args.keep
        appveyor_check = getattr(self._args, 'appveyor_check', False)
        # many_linux = {
        #     '27 35 36': '01a75168a06f',  # 201701
        #     '37': 'fbf76948b80e',  # 20180724
        #}
        # many_linux = {'27 35 36 37': 'latest'}
        # if self._args.rpath:
        #     return self.dist_rpath(self._args.rpath)
        if Path('build').exists():
            print('build directory found, run "dv clean" first')
            return
        tox_wd = self.check_tox_dir()
        dist_dir = self.check_dist_dir()
        old_build = None
        if getattr(self._args, 'appveyor_pull', False):
            self.pull_appveyor(dist_dir)
            return
        if do_windows or appveyor_check:
            try:
                res = self.check_appveyor(self.appv())
            except AttributeError:
                print(dedent("""
                   checking appveyor info failed should __init__.py have one of:
                      universal=True,,
                      python_requires='>=3',
                      python_requires='>=3.7',
                  """))
                sys.exit(1)
            old_build = res['nr']
            if appveyor_check:
                print(res)
                self.wait_appveyor(old_build)
                return
            assert 'running' not in res['status']
            # this assumes in .hg/hgrc:
            # appveyor = ssh://hg@bitbucket.org/appveyor-ruamel/....
            d = 'cd {}; hg push appveyor --branch default --force'.format(os.getcwd())
            if self.appv()[0] == 'appveyor':
                # create windows wheels
                try:
                    # show_output(['ssh', '-x', '-a', 'appveyor@localhost', d], verbose=1)
                    # the following assumes something like:
                    # appveyor = git+ssh://git@github.com:ruamel/yaml.clib.git
                    # in the .hg/hgrc
                    show_output(['hg', 'bookmark', '-r', 'default', 'master'], verbose=1)
                    show_output(['hg', 'push', 'appveyor'], verbose=1)
                except subprocess.CalledProcessError as e:
                    print('e', e)
                    pass
        with TmpFiles(
            self, license=True, tox=tox_wd, makefile=True, typed=self.typed,
            sub_packages=self.sub_packages,
            docker=self.docker_data,
            manifest=self.pon.obj.get('manifest', None),
            nested=True, # self.nested,
            keep=keep,
        ) as tmpfiles:
            if do_linux or do_sdist:
                if do_sdist:
                    cmd = [sys.executable, 'setup.py', 'sdist', '-d', dist_dir]
                    if kw:
                        cmd.append('--dump-kw')
                    show_output(cmd)
                if do_linux:
                    #for ml in sorted(many_linux):
                    #    self.docker_file.write_text(
                    #        dedent(self.docker_file_template).format(many_linux[ml], ml)
                    #    )
                    #    res = check_output(['dc', 'build'])  # NOQA
                    #    show_output(['dc', 'up'], verbose=True)
                    res = check_output(['dc', 'build'])  # NOQA
                    show_output(['dc', 'up'], verbose=True)
                    print('\033[0m')  # sometimes manylinux mixes up things wrt colors
                    self.rm_old_dist_dir()
                # self.dist_rpath('*')
            if do_any:
                u = self.pon.obj.get('universal')
                py_req = self.pon.obj.get('python_requires')
                if u:
                    cmd = [sys.executable, 'setup.py', 'bdist_wheel', '-d', dist_dir]
                    if kw:
                        cmd.append('--dump-kw')
                    show_output(cmd)
                elif py_req == '>=3':
                    cmd = [sys.executable, 'setup.py', 'bdist_wheel', '-d', dist_dir]
                    if kw:
                        cmd.append('--dump-kw')
                    show_output(cmd)
                elif py_req:  # should actually analyse value
                    for py in 'py36', 'py37', 'py38', 'py39':
                        cmd = [sys.executable, 'setup.py', 'bdist_wheel', '--python-tag', py, '-d', dist_dir]
                        if kw:
                            cmd.append('--dump-kw')
                        show_output(cmd)
                else:
                    print("")
                    sys.exit(1)
            if do_macos:
                # show_output(['ssh', 'builder@macos', 'cd tmp; /usr/local/bin/hg pull -u'])
                try:
                    show_output(['hg', 'push', '--remotecmd', '/usr/local/bin/hg', 'macos',
                                 '--branch', 'default', '--new-branch'])
                except Exception as e:
                    # if 'no changes found' not in e.stdout.decode('utf-8'):
                    if 'no changes found' not in e.stdout:
                        raise
                show_output(['ssh', 'builder@macos', 'cd tmp; /usr/local/bin/hg update'])
                # remove any previous data from tmp/dist and tmp/build
                show_output(
                    [
                        'ssh',
                        'builder@macos',
                        'rm -rf tmp/dist tmp/build; for i in 27 35 36 37 38 39; do source '
                        'py$i/bin/activate; cd ~/tmp; python setup.py bdist_wheel; '
                        'cd ~; deactivate; done',
                    ]
                )
                # print('dist', dist_dir)
                show_output(['scp', 'builder@macos:~/tmp/dist/*.whl', dist_dir], verbose=1)
                time.sleep(2)
            if do_windows:
                self.show_version()
                if self.appv()[0] == 'appveyor':
                    self.wait_appveyor(old_build)
                    self.pull_appveyor(dist_dir)
        self.show_version(full_path=getattr(self._args, 'full', False))

    def pull_appveyor(self, distdir):
        from ruamel.appveyor.artifacts.artifacts import Artifacts
        pushd(distdir)
        try:
            user, project = self.appveyor_data(self.appv())
            artifacts = Artifacts()
            # no pypi downloading
            artifacts.download(project=project, user=user, pypi=False, verbose=1)
        except Exception as e:
            raise
        finally:
            popd()

    def show_version(self, full_path=False):
        verdist = self.dist_versions(full_path=full_path)
        dist_dir = self.check_dist_dir()
        if not full_path:
            print('base directory:', dist_dir)
            prefix = ""
        else:
            prefix = str(dist_dir) + '/'
        count = 0
        for version in sorted(verdist, reverse=True):
            nr_pckgs = len(verdist[version])
            print(f'{version!s} [{nr_pckgs}]')
            for fn in sorted(verdist[version]):
                print(' {}{}'.format(prefix, fn.name))
            count += 1
            if count > 2:
                break
            # major, minor = get_mm(version)
            # if mm is None:
            #     mm = (major, minor)
            # elif mm[0] != major or mm[1] != minor:
            #     break
        print('+', len(verdist) - count)

    def appv(self):
        x = self.pon.obj.get('wheels', {}).get('windows')
        if not isinstance(x, MutableMapping):
            x = x.split(':')
        else:
            x = list(x)
        return x

    def wait_appveyor(self, old_build):
        start = time.time()
        while True:
            if time.time() - start > 15 * 60:
                break
            res = self.check_appveyor(self.appv())
            if old_build is not None:
                if res['nr'] == old_build:
                    print('\r{} {} {}'.format(int(time.time()), old_build, res['nr']),
                          end='   ')
                    time.sleep(60)
                    continue
            jobs = res['jobs']
            print('\r{} {}'.format(int(time.time()), '/'.join(
                [str(i) for i in jobs[:2]])), end='   ')
            if jobs[2] > 0:
                break
            if res['status'] == 'success':
                print()
                return True
            sys.stdout.flush()
            if jobs[0] + 1 < jobs[1]:
                time.sleep(60)
            else:
                time.sleep(10)
        return False

    def appveyor_data(self, info):
        assert info[0] == 'appveyor'
        user = None
        if len(info) > 2:
            user = info[1]
            pkg = info[2]
        elif len(info) > 1:
            pkg = info[1]
        else:
            fpn = self.pon.obj['full_package_name']
            pkg = fpn.split('.', 1)[-1]
        if pkg.startswith('ruamel.'):
            pkg = pkg.split('.', 1)[1]
        pkg = pkg.replace('.', '-')
        if user is None:
            user = 'AnthonvanderNeut'
        return user, pkg

    def check_appveyor(self, info):
        import requests
        import pprint

        user, pkg = self.appveyor_data(info)
        # print('user:', user)
        # print('pkg: ', pkg)
        url = f' https://ci.appveyor.com/api/projects/{user}/{pkg}'
        # print('url', url)
        # have to enable this to get id and token (RTFD: admin -> integrations)
        if True:
            r = requests.get(url)
            # with open('/var/tmp/yaml.json', 'w') as fp:
            #     fp.write(r.text)
            data = r.json()
        else:
            import json
            with open('/var/tmp/yaml.json') as fp:
                data = json.load(fp)
        if 'build' not in data:
            return dict(nr=-1, status=[])
        bld = data['build']
        # pprint.pprint(bld)
        # print('rtfd response', r)
        # print(bld['status'])
        # print(bld['buildNumber'])
        jobs = [0, 0, 0]
        for job in bld['jobs']:
            jobs[1] += 1
            if job['status'] == 'success':
                jobs[0] += 1
            elif job['status'] == 'failure' or 'cancel' in job['status']:
                # print(job['name'], job['status'])
                jobs[2] += 1
            # print(job['name'], job['status'])
        # status: success queued running
        res = dict(nr=bld['buildNumber'], status=bld['status'], jobs=jobs)
        return res

    def dist_versions(self, full_path=False):
        verdist = {}
        dist_dir = self.check_dist_dir()
        pkg = self.pon.obj['full_package_name']
        for fn in dist_dir.glob(pkg + '-*'):
            version = fn.stem[len(pkg) + 1 :]
            v = xversion(version)
            verdist.setdefault(v, []).append(fn)
        return verdist

    def dist_rpath(self, dist, verbose=0):
        """this was implemented when 3.6 would not build on the latest
        manylinux image, later found out to be caused by incomplete cleaning
        of a temporary directory, that persisted between runs
        """
        from tempfile import TemporaryDirectory

        dist = dist.replace('.', "")
        verdist = self.dist_versions()
        dist_dir = self.check_dist_dir()
        version = sorted(verdist, reverse=True)[0]
        for fn in sorted(verdist[version]):
            if dist == '*' or dist in fn.name:
                print(' ', fn.name)
                with TemporaryDirectory(prefix='develop_') as tmpdir:
                    os.chdir(tmpdir)
                    if verbose > 0:
                        print(tmpdir)
                    sys.stdout.flush()
                    unzip = ['unzip', dist_dir / fn.name]
                    res = subprocess.check_output(unzip).decode('utf-8')
                    # print(res)
                    for so_file in Path(tmpdir).glob('*.so'):
                        readelf = ['readelf', '-d', str(so_file)]
                        res = subprocess.check_output(readelf).decode('utf-8')
                        if verbose > 0:
                            print(res)
                        sys.stdout.flush()
                        if 'RPATH' in res:
                            print('found rpath in so:', so_file)
                            chrpath = ['chrpath', '-d', str(so_file)]
                            res = subprocess.check_output(chrpath).decode('utf-8')
                            print('chrpath', res)
                            res = subprocess.check_output(readelf).decode('utf-8')
                            if verbose > 0:
                                print(res)
                            assert 'RPATH' not in res
                            # so_out = dist_dir / (fn.name + '.new')
                            so_out = so_file
                            so_out.unlink()
                            zip = ['zip', '-rq9', str(so_out), '.']
                            print('zip', zip)
                            res = subprocess.check_output(
                                zip, stderr=subprocess.STDOUT
                            ).decode('utf-8')
                            print(res)
                            sys.stdout.flush()

                    sys.stdout.flush()
        # version = sorted(verdist, reverse=True)
        # print('ver', version)
        #    print(str(version))
        #    for fn in sorted(verdist[version]):
        #        print(" ", fn.name)

    def build_rtfd_doc(self, rtfd_name=None):
        import requests

        if rtfd_name is None:
            rtfd_name = self.pon.obj.get('rtfd')
            if rtfd_name is None:
                return
        # check for old style project info (before tokens)
        assert not isinstance(rtfd_name, int), 'rtfd needs to be project name'
        # from the name try to get the number and token from the develop config file
        # this is not stored in the __init__.py as that data should not be public
        data = self._config._config.get('rtfd', {}).get(rtfd_name)
        if not data:
            print('no "secret" rtfd info for {} in develop\'s config file')
            return
        url = 'https://readthedocs.org/api/v2/webhook/yaml/{id}/'.format(**data)
        print('url', url)
        # have to enable this to get id and token (RTFD: admin -> integrations)
        r = requests.post(url, data=dict(token=data['token'], branches='latest'))  # NOQA
        print('rtfd response', r)

    def check_dist_dir(self):
        if not self._args.distbase:
            print('you have to set --distbase')
            sys.exit(-1)
        try:
            pkg = self.pon.obj['full_package_name']
        except AttributeError as e:
            if self.pon is None:
                print(f'no _package_data in {ununinitpy}?')
            else:
                print('Attribute error', dir(e))
            sys.exit(-1)
        dist_dir = Path(self._args.distbase) / pkg
        if not dist_dir.exists():
            dist_dir.mkdir(parents=True)
            if self.old_dist_dir.exists():
                for fn in self.old_dist_dir.glob('*'):
                    fn.copy(dist_dir / fn.name)
                    fn.unlink()
                self.old_dist_dir.rmdir()
        else:
            if self.old_dist_dir.exists():
                print('cannot have both {} and {}'.format(dist_dir, self.old_dist_dir))
                sys.exit(-1)
        return dist_dir

    def check_tox_dir(self):
        """check if global directory for tox exists"""
        if not self._args.toxbase:
            print('you have to set --toxbase')
            sys.exit(-1)
        if not self.pon.obj.get('tox'):
            return None
        pkg = self.pon.obj['full_package_name']
        tox_dir = Path(self._args.toxbase) / pkg
        if self.old_tox_dir.exists():
            print('removing ', self.old_tox_dir)
            self.old_tox_dir.rmtree()
        if not tox_dir.exists():
            print('creating', tox_dir)
            tox_dir.mkdir(parents=True)
        return tox_dir

    def print_check(self):
        """check sources for debug print statements"""
        if self.pon.obj.get('print_allowed'):
            return True
        ps = ' print('
        cps = '#' + ps
        ok = True
        for path in self.source_file_paths():
            if ps in path.read_text():
                for idx, line in enumerate(path.open()):
                    xline = line.replace(cps, '')
                    if ps in xline:
                        print(f'{path}[{idx}]: {line}', end='')
                        ok = False
        if not ok:
            print('remove calls to print or add: print_allowed=True, to __init__.py')
        return ok

    def source_file_paths(self):
        for path in sorted(Path('.').glob('*.py')):
            if path.name == 'setup.py':
                continue
            if path.name.startswith('.#'):
                continue
            yield path
        # don't include the _test files, but do subdirs that do not
        # have a versioned init file
        # for path in sorted(Path('.').glob('_*/*.py')):
        #     yield path

    @property
    def sub_directory_pon(self):
        # list of subdirectories that have __init__.py and obtionally pon (if not -> None)
        attr = '_' + sys._getframe().f_code.co_name
        if not hasattr(self, attr):
            pons = {}
            for path in Path('.').glob('*/' + ununinitpy):
                try:
                    with io.open(path) as fp:
                        pon = PON()
                        if pon.extract(fp, start=PKG_DATA) is None:
                            pon = None
                        else:
                            check_init_pon(path, pon)
                except IOError:
                    pon = None
                pons[str(path.parent)] = pon
            setattr(self, attr, pons)
        return getattr(self, attr)

    @property
    def sub_packages(self):
        """return list of sub packages for a package (or empty list)
        this can be used to skip recursion into all subdirs that are
        packages of their own
        """
        ret_val = []
        for path in self.sub_directory_pon:
            pon = self.sub_directory_pon[path]
            if pon and pon.obj.get('nested'):
                ret_val.append(path)
        return ret_val

    # #     def test_commit_build_push(self, version, settings=None, testing=False):
    # #         """either raise an error (or don't catch), or return False to prevent
    # #         version number increment
    # #         settings are currently a subset of the __init__.py:_package_data structure
    # #         """
    ##
    # #         def confirm(x):
    # #             if sys.version_info < (3,):
    # #                 return raw_input(x)
    # #             return input(x)
    ##
    # #         def confirm_yes_no(x):
    # #             res = None
    # #             while res is None:
    # #                 resx = confirm(x)
    # #                 if resx:
    # #                     if resx in 'yY':
    # #                         res = True
    # #                     if resx in 'nN':
    # #                         res = False
    # #             return res
    ##
    # #         def distribution_files(name, version, windows_wheel=False, any_wheel=False,
    # #                                many_wheel=False):
    # #             from glob import glob
    # #             n = self.fpn if name is None else name
    # #             dn = os.environ['PYDISTBASE'] + '/' + n
    # #             v = u'.'.join([str(x) for x in version])
    # #             tgv = u'{}/{}-{}.tar.gz'.format(dn, n, v)
    # #             tbv = u'{}/{}-{}.tar.bz2'.format(dn, n, v)
    # #             txv = u'{}/{}-{}.tar.bz2'.format(dn, n, v)
    # #             av = u'{}/{}-{}-*-any.whl'.format(dn, n, v)
    # #             wv = u'{}/{}-{}-*-win*.whl'.format(dn, n, v)
    # #             mv = u'{}/{}-{}-*-manylinux*.whl'.format(dn, n, v)
    # #             ok = True
    # #             for tv in [tbv, tgv, txv]:  # most likely order
    # #                 ret_val = glob(tv)
    # #                 if len(ret_val) != 1:
    # #                     # print('matching ', repr(tv), ret_val)
    # #                     pass
    # #                 else:
    # #                     break
    # #             else:
    # #                 ok = False
    # #             if any_wheel:
    # #                 ret_val.extend(glob(av))
    # #                 if len(ret_val) <= 1:
    # #                     print('matching ', repr(wv), ret_val)
    # #                     ok = False
    # #             if windows_wheel:
    # #                 ret_val.extend(glob(wv))
    # #                 if len(ret_val) <= 1:
    # #                     print('matching ', repr(wv), ret_val)
    # #                     ok = False
    # #             if many_wheel:
    # #                 ret_val.extend(glob(mv))
    # #                 if len(ret_val) <= 1:
    # #                     print('matching ', repr(mv), ret_val)
    # #                     ok = False
    # #             if not ok:
    # #                 print('distribution_files not ok')
    # #                 sys.exit(0)
    # #             return ret_val
    ##
    # #         docker_compose_file = Path('docker-compose.yaml')
    # #         version = [x for x in version if x != u'dev']  # remove dev
    # #         if settings is None:
    # #             settings = {}
    # #         from repo.status import check_output, status_list
    # #         # run tox (optional incrementally?)
    # #         if self.do_tox:
    # #             cmd = ['tox']
    # #             # this was in order not to rebuild virtualenv if e.g. only flake8 failed
    # #             # if True or not getattr(self._args, 'reuse_message', False):
    # #             cmd.append('-r')
    # #             print('running', ' '.join(cmd))
    # #             try:
    # #                 res = show_output(cmd)
    # #             except subprocess.CalledProcessError as e:
    # #                 print('error running tox', e.message)
    # #                 return
    # #         lst = status_list()
    # #         if lst:  # there is something to commit, normally at least __init__.py
    # #             # commit
    # #             if self.commit_message_file.exists():
    # #                 try:
    # #                     show_output(['hg', 'commit', '--logfile',
    # #                                 self.commit_message_file])
    # #                 except subprocess.CalledProcessError as e:
    # #                     print('error committing with message file', e.message)
    # #                     return
    # #                 self.commit_message_file.unlink()
    # #             else:
    # #                 os.system('hg commit')
    # #             # make sure commit happened
    # #             lst = status_list()
    # #             if lst:
    # #                 print('repo not clean after commit, aborting')
    # #                 for k in lst:
    # #                     print(' ', k)
    # #                 return False
    # #         # XXXXX
    # #         str_version = u'.'.join([str(x) for x in version])
    # #         res = check_output(['hg', 'tags'])
    # #         if self.do_tag and u'\n' + str_version not in res:
    # #             # tag if not yet there
    # #             check_output(['hg', 'tag', str_version])
    # #         else:
    # #             print('already tagged')
    # #         # push to ruamel
    # #         try:
    # #             print('pushing')
    # #             check_output(['hg', 'push', '--new-branch'])
    # #         except subprocess.CalledProcessError as e:
    # #             if 'there is no Mercurial repository here' in e.output:
    # #                 ssh_remote_mkdir()
    # #                 check_output(['hg', 'push'])  # try again, don't catch errors
    # #             else:
    # #                 print('output of hg push:\n', e.output)
    # #         # create dist
    # #         show_output(['python', 'setup.py', 'sdist'], verbose=1)
    # #         if settings.get('universal'):
    # #             show_output(['python', 'setup.py', 'bdist_wheel'], verbose=1)
    # #             print('\nself nested', self.nested)
    # #             if self.nested:
    # #                 dist_dir = Path(os.environ['PYDISTBASE']) / self.fpn
    # #                 print('\nnested1', dist_dir)
    # #                 full_name = list(dist_dir.glob('{}-{}*.whl'.format(self.fpn,
    # #                                        str_version)))
    # #                 print('full_name', full_name)
    # #                 if len(full_name) != 1:
    # #                     print('should find one element')
    # #                     sys.exit(-1)
    # #                 full_name = full_name[0]
    # #                 with InMemoryZipFile(full_name) as imz:
    # #                     imz.delete_from_zip_file(self.fpn + '.*.pth')
    # #                 # self.press_enter_to_continue('fix wheel (remove nspkg.pth) \
    # #                           and press Enter')
    # #         if docker_compose_file.exists():
    # #             show_output(['/opt/util/docker-compose/bin/dcw', 'up'], verbose=1)
    # #         # track size changes, compared to previous run
    # #         # upload
    # #         if self.do_upload:
    # #             cmd = ['twine', 'upload']
    # #             cmd.extend(distribution_files(None, version,
    # #                                           windows_wheel=False,
    # #                                           any_wheel=settings.get('universal'),
    # #                                           many_wheel=docker_compose_file.exists(),
    # #                                           ))
    # #             show_output(cmd, verbose=1, stderr=subprocess.PIPE)
    # #         # 20170624 trying to upload a tar.bz2:
    # #         # Uploading ruamel.yaml-0.15.11.tar.bz2
    # #         # error HTTPError: 400 Client Error: Invalid file extension.
    # #         #    for url: https://upload.pypi.org/legacy/
    ##
    # #         # push to devpi? or to pypi using devpi
    # #         # "devpi upload" cleans out the dist directory and is therefore useless
    # #         # check_output(['devpi', 'upload', '--from-dir', 'dist', '--only-latest'])
    # #         # potentially push to other servers running devpi
    # #         # push to pypi, using twine
    # #         if False:
    # #             pass
    # #         # push to bitbucket
    # #         try:
    # #             show_output(['ssh', '-x', '-a', 'ruamel@localhost',
    # #                     'cd {}; hg push bitbucket --branch default'.format(os.getcwd())],
    # #                         verbose=1)
    # #             prj = settings.get('read_the_docs')
    # #             if prj is not None:
    # #                 trigger_rtd_build(prj)
    # #         except subprocess.CalledProcessError as e:
    # #             pass
    # #         return True

    def walk(self):
        tox_dir = '.tox'
        hg_dir = '.hg'
        skip_dirs = [
            tox_dir,
            hg_dir,
            '.cache',
            '.ruamel',
            '.repo',
            '__pycache__',
            '.pytest_cache',
        ]
        if self._args.check_init:
            skip_dirs.extend(['_test', 'build', 'dist'])
        # for x in Path('.').glob('**/__init__.py'):
        #    print(x)
        count = 0
        for root, directories, files in os.walk('.'):
            dirs_no_recurse = []
            # print('root', root)
            if root == './ruamel/util/new/templates':
                continue
            for d in directories:
                if d in skip_dirs or d.endswith('.egg-info'):
                    dirs_no_recurse.append(d)
            for d in dirs_no_recurse:
                if d in directories:
                    directories.remove(d)
            if self._args.check_init and '__init__.py' in files:
                if self.walk_check_init(Path(root)):
                    count += 1
            elif self._args.insert_pre_black and '__init__.py' in files:
                if self.insert_pre_black(Path(root)):
                    count += 1
            elif self._args.check_hgignore and dot_hgignore in files:
                if self.walk_check_hgignore(Path(root)):
                    count += 1
            # print(root)
        print('count:', count)

    def walk_check_hgignore(self, root):
        hgi = HgIgnore(root / dot_hgignore)
        print('hgignore file', str(hgi._file_name).replace(os.getcwd(), '.'))
        # print('############# global hgignore:')
        glob_hgi = GlobalHgIgnore()
        # print(glob_hgi.text)
        # print('############# .hgignore:')
        # print(hgi.text)
        # print('nr. of lines:', len(hgi.lines))
        res = hgi.remove_lines_already_in_global(glob_hgi, verbose=1)
        if res == 2:
            hgi._file_name.unlink()
        elif res == 1:
            # print(hgi.text)
            hgi._file_name.write_text(hgi.text)
            pass
        # print(hgi.text)
        # print('nr. of lines:', len(hgi.lines))
        return 1

    @staticmethod
    def display_name(size, dts, root):
        print('{:-6} {:%Y-%m-%d} {}'.format(size, dts, root))

    def has_package_data(self, init_py):
        st = init_py.stat()
        size = st.st_size
        if size == 0:
            return False
        dts = date_time.fromtimestamp(st.st_mtime)
        package_data = False
        for line in init_py.read_text().splitlines():
            if 'JSON' in line and not package_data:
                self.display_name(size, dts, init_py.parent)
                print('old JSON package information found, use packageversion to convert')
                sys.exit(1)
            if line.startswith('_package_data'):
                package_data = True
        if package_data:
            return True
        return False

    def walk_check_init(self, root):
        init_py = root / '__init__.py'
        if not self.has_package_data(init_py):
            return False
        pon = PON()
        with io.open(str(init_py)) as fp:
            pon.extract(fp, start=PKG_DATA)
            # check_init_pon(ununinitpy, pon)
        new_vers = pon.obj.get('__version__')
        convert_vers = '_convert_version' in init_py.read_text()
        if new_vers is None:
            bup = init_py.with_suffix('.py.orig2')
            if not bup.exists():
                init_py.copy(bup)
            self.add_string_version(init_py)
            return True
        if new_vers is None and convert_vers:
            print('check versioning', root)
        return True

    def add_string_version(self, path):
        vinf = '    version_info=('
        text = path.read_text()
        assert '    __version__=' not in text
        lines = text.splitlines()
        new_lines = []
        skipping = False
        for _idx, line in enumerate(lines):
            if line.startswith(vinf):
                new_lines.append(line)
                v = [x.strip() for x in line.split('(')[1].split(')')[0].split(',')]
                # text = "    __version__='{}',".format('.'.join(v)
                # text = '\n'.join(
                #    lines[:idx+1] +
                #    ["    __version__='{}',".format('.'.join(v))] +
                #    lines[idx:]
                # )
                new_lines.append("    __version__='{}',".format('.'.join(v)))
                continue
            if not skipping and '_convert_version' in line:
                skipping = True
                continue
            if line.startswith('del _convert_version'):
                skipping = False
                new_lines.append("version_info = _package_data['version_info']")
                new_lines.append("__version__ = _package_data['__version__']")
                continue
            if skipping:
                continue
            new_lines.append(line)
        text = '\n'.join(new_lines)
        # print(text)
        path.write_text('\n'.join(new_lines))

    def insert_pre_black(self, root):
        import shutil

        print(root)
        init_py = root / '__init__.py'
        if not self.has_package_data(init_py):
            return False
        pon = PON()
        try:
            with io.open(str(init_py)) as fp:
                pon.extract(fp, start=PKG_DATA)
            if not pon.obj.get('black') and not pon.obj.get('pre_black'):
                if True:
                    print('root', root)
                    pon.obj['pre_black'] = True
                    shutil.copy(str(init_py), str(init_py) + '.orig')
                    pon.update(str(init_py), start=PKG_DATA)
                    sys.exit(1)
                return True
        except Exception as e:
            print('root:', root)
            raise

    def black(self):
        import glob
        from itertools import chain

        _black = self.pon.obj.get('black', [])
        if not isinstance(_black, list):
            _black = _black.strip().split()
        print('self._args.files', self._args.files)
        args = list(
            chain.from_iterable(
                [
                    glob.glob(x)
                    for x in (self._args.files if self._args.files else ['*.py', '_test/*.py'])
                ]
            )
        )
        print('args', args)
        diff = ['--diff'] if self._args.diff else []
        cmd = ['black'] + _black + diff + args
        print('cmd:', cmd)
        show_output(cmd)

    def sourceforge_upload(self):
        # hg archive --rev 0.16.0 --prefix ruamel.yaml-0.16.0 --type tar - \
        #    | xz -9 > /tmp/ruamel.yaml-0.16.0.tar.xz
        import requests
        from repo.status import check_output
        from ruamel.repo.hgrc import HgRc
        from .logininfo import login_info

        hgrc = HgRc()
        version = hgrc.latest_tag()
        basedir = self.pon.obj['full_package_name']
        pv = f'{basedir}-{version}'
        sf_up_dir = Path('/data1/sourceforge/ruamel.dl.tagged.releases')
        outfile = sf_up_dir / f'{pv}.tar'
        xzfile = sf_up_dir / f'{pv}.tar.xz'
        res = check_output(['hg', 'archive', '--rev', version, '--prefix', pv, outfile])
        res = check_output(['xz', '-9f', outfile])
        print('temporary changing to', sf_up_dir, 'from', os.getcwd())
        pushd(sf_up_dir)
        cmd = ['rsync', '-e ssh', '-r', '--delete', '.',
               'anthon@frs.sourceforge.net:/home/frs/project/ruamel-dl-tagged-releases/']
        res = check_output(cmd)
        print('rsync')
        popd()

    def sfup(self):
        return self.sourceforge_upload()

    def bbup(self):
        # hg archive --rev 0.16.0 --prefix ruamel.yaml-0.16.0 --type tar - \
        #    | xz -9 > /tmp/ruamel.yaml-0.16.0.tar.xz
        import requests
        from repo.status import check_output
        from ruamel.repo.hgrc import HgRc
        from .logininfo import login_info

        hgrc = HgRc()
        user, slug = hgrc.get_user_repo_name('bitbucket')
        version = hgrc.latest_tag()
        basedir = self.pon.obj['full_package_name']
        pv = f'{basedir}-{version}'
        outfile = Path('/tmp') / f'{pv}.tar'
        xzfile = Path('/tmp') / f'{pv}.tar.xz'
        res = check_output(['hg', 'archive', '--rev', version, '--prefix', pv, outfile])
        res = check_output(['xz', '-9f', outfile])
        u, p = login_info(user)
        up_url = f'https://api.bitbucket.org/2.0/repositories/{u}/{slug}/downloads'
        print('up', up_url)
        files = dict(files=xzfile.open('rb'))
        r = requests.post(up_url, files=files, auth=(u, p))
        print('request result', r)
        xzfile.unlink()
        # print(version, user, slug, xzfile, xzfile.exists())
        # print('done')

    def bbup0(self):
        # dv bbup --user ruamel --pypi ruamel.yaml.clib --repo yaml.clib --version 0.1.0 file
        # should consider adding to .hgrc: [web]\nallow_archive = xz bz2 gz zip
        # and starting hg serve -p 8001 -a lo
        # then you can download the file for tag 0.16.0 at http://localhost:8001/archive/0.16.0.tar.bz2
        # even easier is to use hg archive -r 0.16.0 ruamel.yaml-0.16.0.tar or
        # hg archive --rev 0.16.0 --prefix ruamel.yaml-0.16.0 --type tar - \
        #    | xz -9 > /tmp/ruamel.yaml-0.16.0.tar.xz

        import tarfile
        import requests
        from ruamel.yaml import YAML
        from .logininfo import login_info

        version = self._args.version
        user = self._args.user if self._args.user else ""
        repo = self._args.repo
        basedir = self._args.pypi
        outfile = Path('/tmp') / f'{basedir}-{version}.tar.xz'
        u, p = login_info(user)
        if True:
            url = f'https://bitbucket.org/{u}/{repo}/get/{version}.tar.bz2'
            print('url', url)
            with requests.get(url, stream=True) as req:
                with tarfile.open(mode='r|*', fileobj=req.raw) as tar_in:
                    with tarfile.open(name=outfile, mode='w|xz') as tar_out:
                        member = tar_in.next()
                        idx = 0
                        while member is not None:
                            path = Path(f'{basedir}-{version}')
                            idx += 1
                            # if idx > 10:
                            #     break
                            path /= member.name.split('/', 1)[1]
                            outm = member
                            outm.name = str(path)
                            # print(idx, outm.name, member.size)
                            outb = tar_in.extractfile(member)
                            # print(len(outb.read()))
                            tar_out.addfile(outm, outb)
                            member = tar_in.next()
            up_url = f'https://api.bitbucket.org/2.0/repositories/{u}/{repo}/downloads'
            files = dict(files=outfile.open('rb'))
            r = requests.post(up_url, files=files, auth=(u, p))
            print('r', r)
            outfile.unlink()
        return

        fp = Path('~/Downloads/ruamel-yaml-af9628b0d047.tar.bz2').expanduser()
        buf = fp.open('rb')
        tar = tarfile.open(mode='r|*', fileobj=buf)
        member = tar.next()
        idx = 0
        while member is not None:
            idx += 1
            if idx > 10:
                break
            print(idx, member.name, member.size)
            outb = tar.extractfile(member)
            print(len(outb.read()))
            member = tar.next()
        return

        fn = Path(self._args.file)
        url = f'https://api.bitbucket.org/2.0/repositories/{u}/{repo}/downloads'
        print('u', url)
        files = dict(files=fn.open('rb'))
        r = requests.post(url, files=files, auth=(u, p))
        print('r', r, r.text)
        r = requests.get(url)
        print('r.list', r)
        yaml = YAML()
        yaml.dump(r.json(), sys.stdout)
        url2 = url + '/' + fn.name
        print('url2', url2)
        sys.stdout.flush()
        time.sleep(15)
        r = requests.delete(url2, auth=(u, p))
        print('r.delete', r, r.text)

    def update(self):
        pass


    def patchwheel(self):
        # print(self._args.filenames)
        # print(self._args.wheelnames)
        # print(self._args.file)
        for fn in self._args.file:
            self.patch_one_wheel(Path(fn), self._args.filenames, self._args.wheelnames, outdir=self._args.outdir)

    def patch_one_wheel(self, whl_name_in, file_name_patches=None, wheel_name_patches=None, outdir=None):
        # _patches should be list of pairs for replacing

        import zipfile
        from ruamel.std.zipfile import InMemoryZipFile

        if file_name_patches is None:
            file_name_patches = []
        if wheel_name_patches is None:
            wheel_name_patches = []
        assert whl_name_in.exists()
        outdir = whl_name_in.resolve().parent if outdir is None else Path(outdir).resolve().expanduser()
        name = whl_name_in.name
        for f, t in wheel_name_patches:
            name = name.replace(f, t)
        whl_name_out = outdir / name
        # print(whl_name_in, '\n ->', whl_name_out)
        with InMemoryZipFile(whl_name_out) as zfo:
            with zipfile.ZipFile(whl_name_in) as zfi:
                for il in zfi.infolist():
                    data = zfi.read(il.filename)
                    basename = il.filename.rsplit('/')[-1]
                    if basename == 'RECORD':
                        lines = data.decode('utf-8').splitlines(True)
                        for idx, line in enumerate(lines):
                            if '/WHEEL,sha' in line:
                                lines[idx] = line.split(',sha')[0] + ',,\n'
                                continue
                            ch_line = line
                            for f, t in file_name_patches:
                                ch_line = ch_line.replace(f, t)
                            if ch_line != line:
                                lines[idx] = ch_line
                        data = ''.join(lines)
                        print(data)
                    elif basename == 'WHEEL':
                        data = data.decode('utf-8')
                        for f, t in wheel_name_patches:
                            data = data.replace(f, t)  # this changes the Tag: line
                        print(data)
                    name = il.filename
                    for f, t in file_name_patches:
                        name = name.replace(f, t)
                    zfo.append(name, data)

    def tar(self):
        # can use 'dv tar xxx' and 'dv tar -xxx'
        def tarcmd(file_name):
            excl = ['--exclude=__pycache__']  # 
            for p in self.sub_packages:
                excl.append(f'--exclude=./{p}')
            # can use --use-compress-program=zstd or -Izstd if --zstd not yet supported
            cmd = ['tar', '--create', '--file', file_name, '--zstd'] + excl + ['.']
            # cmd = ['tar', '--create', '-v', '--file', '/dev/null', '--zstd'] + excl + ['.']
            return cmd
         
        safety_name = self.tar_dir / 'before_last_restore.tar.zst'
        if self._args.command:
            if self._args.create or self._args.list or self._args.restore:
                print('cannot have command and --list/--create/--restore')
                sys.exit(1)
        if self._args.restore or self._args.command == 'restore':
            print('restore', self.tar_dir)
            if not self.tar_dir.exists():
                print(f'no directory for dated tar files found ({self.tar_dir})')
                return
            # make safety backup
            res = show_output(tarcmd(safety_name), show_command=False)
            file_name = sorted(self.tar_dir.glob(f'{self.tar_dir.name}-*.tar*'))[-1]
            # extract
            cmd = ['tar', '--extract', '--file', file_name, '--zstd']
            res = show_output(cmd, show_command=True)
            print('restored:', file_name)
        elif self._args.create or self._args.command == 'create':
            print('create', self.tar_dir)
            if not self.tar_dir.exists():
                print(f'creating directory for dated tar files ({self.tar_dir})')
                self.tar_dir.mkdir(parents=True)
            # creation should know about subdirs to skip
            file_name = self.tar_dir / f'{self.tar_dir.name}-{date_time.now():%Y%m%d-%H%M%S}.tar.zst'
            print('file_name', file_name)
            res = show_output(tarcmd(file_name), show_command=True)
            # print('cmd', cmd)
            print('created:', file_name)
        elif self._args.list or self._args.command in ['list', None]:
            print('list', self.tar_dir)
            if not self.tar_dir.exists():
                print(f'no directory for dated tar files found ({self.tar_dir})')
                return
            for x in sorted(self.tar_dir.glob(f'{self.tar_dir.name}-*.tar*')):
                print(' ', x)
            if safety_name.exists():
                print('  safety from before restore exists')
        else:
            print('tar unknown command', self._args.command)
            sys.exit(1)

    @property
    def tar_dir(self):
        attr = '_' + sys._getframe().f_code.co_name
        if not hasattr(self, attr):
            if not self._args.tarbase:
                print('you have to set --tarbase')
                sys.exit(-1)
            try:
                pkg = self.pon.obj['full_package_name']
            except AttributeError as e:
                if self.pon is None:
                    print(f'no _package_data in {ununinitpy}?')
                else:
                    print('Attribute error', dir(e))
                sys.exit(-1)
            setattr(self, attr, Path(self._args.tarbase) / pkg)
        return getattr(self, attr)

    def exe(self):
        bin_dir = Path('~/bin/').expanduser()
        # for k, v in self.pon.obj.items():
        #     print(k, v)
        ep = self.pon.obj['entry_points']
        exe_name, rest = ep.split('=', 1)
        exe_path = bin_dir / exe_name
        if self._args.show:
            print(f'{exe_path=!s}, exists? {exe_path.exists()} {rest=}\n')
            if exe_path.exists():
                print(exe_path.read_text(), end='')
            return
        if exe_path.exists():
            if self._args.force:
                exe_path.rename(exe_path.with_suffix('.org'))
            else:
                print(f'{exe_path=!s}, exists, use --force to backup and create anyway')
                return
        mod_path, fun = rest.split(':')
        exe_path.write_text(dedent(f"""\
            #!/opt/util/py39/bin/python

            import sys

            from {mod_path} import {fun}

            sys.exit(main())
            """))
        exe_path.chmod(0o755)






########## class Develop ##########################


def x1version(version):
    from cmp_version import VersionString

    class MyVS(VersionString):
        def __hash__(self):
            return hash(str(self))

    dv = version.split('.tar', 1)[0]
    dv = dv.split('-cp', 1)[0]
    dv = dv.split('-py', 1)[0]
    dv = dv.replace('.dev0', '.a0')

    v = MyVS(dv)
    if 'xxdev' in version:
        print(v, repr(v))
    return v
    return
    from .version import Version

    version = version.replace('.dev0', '.a')
    v = Version(version)
    if 'alph' in version:
        print(v, repr(v))
    return v
    ret = []
    for n in version.replace('-', '.', 1).split('.'):
        try:
            ret.append('{:03d}'.format(int(n)))
        except ValueError:
            ret.append(n)
    return tuple(ret)


def xversion(version):
    # use verlib?
    # pip has semantic versioning as well, verlib does
    from pip._vendor.distlib.version import NormalizedVersion

    dv = version.split('.tar', 1)[0]
    dv = dv.split('-cp', 1)[0]
    dv = dv.split('-py', 1)[0]

    return NormalizedVersion(dv)
    # print(dir(v))
    # print(v._parts)


def check_init_pon(path, pon):
    irs = pon.obj.get('install_requires', [])
    if isinstance(irs, dict):
        if 'any' in irs:
            if len(irs) == 1:
                pon.obj['install_requires'] = irs['any']
                pon.update(path, start=PKG_DATA)
            else:
                raise NotImplementedError('install_requires should be a list, use \'xxx;python_version<"3.3"\'')
    ep = pon.obj.get('entry_points')
    if ep:
        for ir in irs:
            if ir.startswith('ruamel.std.argparse'):
                try:
                    v = ir.split('>=')[1]
                except Exception:
                    try:
                        v = ir.split('>')[1]
                    except Exception:
                        v = '0.1'
                v = tuple(map(int, v.split('.')))
                min_ver = (0, 8)
                if not v >= min_ver:
                    print(
                        'need at least version {} < {} in {} for ruamel.std.argparse'.format(
                            str(v), str(min_ver), path
                        )
                    )
                    sys.exit(1)
    # print('ep', ep)
    #        v = list(p.obj['version_info'])
    #        v[1] += 1 # update minor version
    #        v[2] = 0 # set micro version
    #        p.obj['version_info'] = tuple(v)
    #        p.update(file_name, start=s, typ=t)


def ssh_remote_mkdir():
    from repo.status import check_output
    from configobj import ConfigObj

    conf = ConfigObj(open('.hg/hgrc'))
    path = conf['paths']['default-push']
    ssh, rest = path.split('//', 1)
    user_host, path = rest.split('/', 1)

    cmd = ['ssh', user_host, 'mkdir -p {path} ; hg init {path}'.format(path=path)]
    res = check_output(cmd)
    print(res)


def open_in_browser(url, verbose=0):
    if verbose >= 0:
        print('url: ', url)
    os.system('chromium-browser ' + url)


# def get_mm(v):
#     return v._parts[1][0], v._parts[1][1]
