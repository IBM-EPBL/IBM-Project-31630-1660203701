# coding: utf-8

import sys
from ruamel.ext.configobj import ConfigObj

from ruamel.std.pathlib import Path
from .revertablefile import RevertableFile, LineNotFound, MultipleLinesFound  # NOQA

hgrc_file_name = '.hg/hgrc'

# this doesn't need to have an __init__. Instantiate with e.g. hgi = HgIgnore(some_dir_path / dot_hgignore)


# this is a combination of configobj and revertable file

class HgRc(RevertableFile):
    def __init__(self, file_name=None):
        if file_name is None:
            path = Path(hgrc_file_name)
        self._data = None
        super().__init__(path)

    def __getitem__(self, section):
        return self.data[section]

    @property
    def data(self):
        if self._data is None:
            self.original_text  # make sure it is read for restoring
            self._data = ConfigObj(self.path)
        return self._data

    def write(self):
        raise NotImplementedError('needs testing')
        self._data.write(hgrc_file_name)

