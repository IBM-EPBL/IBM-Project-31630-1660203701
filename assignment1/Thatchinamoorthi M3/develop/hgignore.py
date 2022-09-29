# coding: utf-8

import sys

from ruamel.std.pathlib import Path
from .revertablefile import RevertableFile, LineNotFound, MultipleLinesFound  # NOQA

dot_hgignore = '.hgignore'

# this doesn't need to have an __init__. Instantiate with e.g. hgi = HgIgnore(some_dir_path / dot_hgignore)

class HgIgnore(RevertableFile):
    def remove_lines_already_in_global(self, global_hgignore, verbose=0):
        for line in global_hgignore.lines:
            if line and line[-1] == ' ':
               print('####################################')
                print('end-of-line space in', global_hgignore._file_name)
                print('  ', repr(line))
                print('####################################')
                break
        lines_to_delete = []
        content_found = False
        for idx, line in enumerate(self.lines):
            ls = line.strip()
            if not ls:
                continue  # an empty line
            if ls[0] == '#':  # comments
                continue
            if line[-1] == ' ':
                print('end-of-line spaces in line {} of {}'.format(idx, self._file_name))
            if line in global_hgignore.lines:
                lines_to_delete.insert(0, idx)  # get them in reverse order
                continue
            if ls[0] != '#':  # comments
                # print('line:', line)
                content_found = True
        if not content_found:
            if verbose > 0:
                print('no content found in {}, should delete it', self._file_name)
            return 2
        if not lines_to_delete:
            return 0
        self._text = None
        for idx in lines_to_delete:
            del self.lines[idx]
        if verbose > 0 and lines_to_delete:
            print(
                '  {}/{} lines deleted'.format(
                    len(lines_to_delete), len(lines_to_delete) + len(self.lines)
                )
            )
        return 1


class GlobalHgIgnore(RevertableFile):
    def __init__(self, file_name=None):
        if file_name is None:
            in_ui = False
            hgrc = Path('~/.hgrc').expanduser()
            for line in hgrc.open():
                if in_ui and line.startswith('['):
                    break
                if not in_ui:
                    if line.startswith('[ui]'):
                        in_ui = True
                    continue
                if '=' not in line:
                    continue
                key, val = [x.strip() for x in line.split('=', 1)]
                if key == 'ignore':
                    file_name = Path(val).expanduser()
                    # print('val', file_name)
            if file_name is None:
                print('hgrc', hgrc, 'has no hgignore entry in [ui]\n')
                sys.exit(1)
            RevertableFile.__init__(self, file_name)
