# coding: utf-8

from __future__ import print_function, absolute_import, division, unicode_literals


"""
Work with project README information: README.rst, CHANGES

The idea is that this information is only read once, but can be updated
and written multiple times.

Although these files are normally under revision control, they are not that big
and revert information (the original read file content) are kept and can be
written out.

"""

import sys
import subprocess
from ruamel.std.pathlib import Path
from .revertablefile import RevertableFile, LineNotFound, MultipleLinesFound


class ReadMe(RevertableFile):
    def __init__(self, file_name=None):
        # rename to prevent wrong README.X to be rendered on sourceforge
        old_ryd_path = Path('README.ryd')
        ryd_path = Path('_README.ryd')
        if file_name is None:
            if not ryd_path.exists() and old_ryd_path.exists():
                cmd = ['hg', 'mv', str(old_ryd_path), str(ryd_path)]
                res = subprocess.check_output(cmd)
            path = ryd_path
            if not path.exists():
                alt_path = Path('README.rst')
                if alt_path.exists():
                    path = alt_path
        else:
            path = Path(file_name)
        super().__init__(path)

    def newer(self, other_path):
        return other_path.stat().st_mtime > self.path.stat().st_mtime

    def find_single_line_starting_with(self, val, raise_on_error=True):
        res = []
        for idx, line in enumerate(self.lines):
            if line.startswith(val):
                res.append(idx)
        if len(res) == 1:
            return res[0]
        if not raise_on_error:
            return None
        if len(res) > 0:
            raise MultipleLinesFound(f'\n  too many lines found starting with [{val}]: {res}')
        assert len(res) == 0
        raise LineNotFound(f'no line found starting with [{val}]')

    def remove_newer_derivatives(self):
        """
        remove derivatives, but only when the file is newer, assuming that
        they have actually been derived
        """
        suffices = '.pdf .html'.split()
        if self.path.suffix == '.ryd':
            suffices.insert(0, '.rst')
        for suffix in suffices:
            other_path = self.path.with_suffix(suffix)
            if not other_path.exists():
                continue
            if self.newer(other_path):
                print(f'unlinking {other_path}')
                other_path.unlink()
            else:
                print(f'{other_path.name} is older than {self.path.name}, remove by hand')

    def remove_any_derivatives(self):
        """
        remove derivatives
        """
        print('readme rad', self.path)
        suffices = '.pdf .html'.split()
        if self.path.suffix == '.ryd':
            suffices.insert(0, '.rst')
        path = (self.path.parent / self.path.name[1:]) if self.path.stem.startswith('_') else self.path 
        for suffix in suffices:
            other_path = path.with_suffix(suffix)
            if not other_path.exists():
                continue
            print(f'unlinking {other_path}')
            other_path.unlink()

    def setup_checkable_path(self, generate=True):
        if self.path.suffix == '.rst':
            return self.path
        if self.path.suffix != '.ryd':
            raise NotImplementedError('suffix unknown ' + self.path.suffix)
        # ryd file convert if necessary
        rst_out = self.path.with_suffix('.rst')
        rst = Path('README.rst')
        if generate and not (rst.exists() and self.newer(rst)):
            print('ryd on', self.path)
            res = subprocess.check_output(['ryd', str(self.path), '--no-pdf'])
            if rst.exists():
                rst.unlink()
            rst_out.rename(rst)
        return rst

    # license and pypi version svg should be under _doc/_static

    def check_update_svg(self, repo, target, url, target_svg=None, path=None):
        line_found = False
        if target_svg is None:
            target_svg = f'.. image:: {repo}/ci/default/tree/_doc/_static/{target}.svg?format=raw'
        if path is True:
            path = Path(f'_doc/_static/{target}.svg')
        for idx, line in enumerate(self.lines):
            if not line.startswith('.. image::'):
                continue
            if f'_doc/_static/{target}.svg' not in line:
                continue
            line_found = True
            if line != target_svg:
                print(f'updating {target}.svg location')
                self.lines[idx] = target_svg
                self.changed = True
                self._text = None
                return True
        if not line_found:
            print(
                f'no {target}.svg reference in README\n',
                target_svg,
                f'\n     :target: {url}',
                sep=''
            )
        elif path and not path.exists():
            print('svg file', path, 'doesn\'t exist')
            return True
        return False

    def check_update_license_svg(self, repo):
        return self.check_update_svg(repo, target='license', url='https://opensource.org/licenses/MIT', path=True)

    def check_update_pypi_svg(self, repo, proj):
        return self.check_update_svg(repo, target='pypi', url=f'https://pypi.org/project/{proj}')

    def check_update_oitnb_svg(self):
        oitnb_svg = '.. image:: https://sourceforge.net/p/oitnb/code/ci/default/tree/_doc/_static/oitnb.svg?format=raw'
        for idx, line in enumerate(self.lines):
            if not line.startswith('.. image::'):
                continue
            if '_doc/_static/oitnb.svg' not in line:
                continue
            if line != oitnb_svg:
                print('updating oitnb.svg location')
                self.lines[idx] = oitnb_svg
                self.changed = True
                self._text = None
                return True
        return False

    def check_update_ryd_svg(self):
        ryd_svg = '.. image:: https://sourceforge.net/p/ryd/code/ci/default/tree/_doc/_static/ryd.svg?format=raw'
        for idx, line in enumerate(self.lines):
            if not line.startswith('.. image::'):
                continue
            if '_doc/_static/ryd.svg' not in line:
                continue
            if line != ryd_svg:
                print('updating ryd.svg location')
                self.lines[idx] = ryd_svg
                self.changed = True
                self._text = None
                return True
        return False


changes_file_name = 'CHANGES'

class Changes(RevertableFile):
    def __init__(self, file_name=None):
        if file_name is None:
            path = Path(changes_file_name)
        self._versions = None
        super().__init__(path)

    def check(self, version=None):
        res = True
        if not self.check_versions(version):
            res = False
        return res

    def check_versions(self, version=None):
        self._versions = versions = {}
        for line in self.original_text.splitlines():
            if not line or line[0] != '[':
                continue
            ver = tuple(int(x) for x in line[1:].split(']')[0].split(','))
            versions.setdefault(ver, [0])[0] += 1
        res = True
        for v in sorted(versions):
            if versions[v][0] > 1:
                print(v, versions[v][0])
                res = False
        if version is not None and tuple(version) in self._versions:
            print(f'{self._file_name} already contains version {version}')
            res = False
        return res

    # should add version that checks on self._versions
