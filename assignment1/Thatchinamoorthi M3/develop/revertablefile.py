# coding: utf-8

from __future__ import print_function, absolute_import, division, unicode_literals

"""
Base class for working with text files on a line by line basis **and** global basis.

If you change the lines, set ._text to None, and .text will be re-generated from the .lines
on next access

If you change text, .lines is set to None automatically, and .lines will be re-generated
from the .text on next access

The original_text is kept
"""

from ruamel.std.pathlib import Path


class LineNotFound(Exception):
    pass


class MultipleLinesFound(Exception):
    pass


class RevertableFile:
    def __init__(self, file_name):
        try:
            self._file_name = file_name.resolve()
        except AttributeError:
            self._file_name = Path(file_name).resolve()
        self._original_text = None
        self._changed = False
        # next two not always used in subclass, e.g. hgrc which works through ConfigObje
        self._lines = None
        self._text = None

    @property
    def lines(self):
        if self._lines is None:
            self._lines = self.text.splitlines()
        return self._lines

    @property
    def text(self):
        if self._text is not None:
            return self._text
        if self._lines is not None:
            self._text = '\n'.join(self._lines) + '\n'  # EOF newline
            return self._text
        self._text = self.original_text
        return self._text

    @text.setter
    def text(self, val):
        # make sure the original is read in
        tmp = self.original_text  # NOQA
        self._text = val
        self._lines = None

    @property
    def changed(self):
        return self._changed

    @changed.setter
    def changed(self, val):
        self._changed = val

    @property
    def original_text(self):
        if not self.has_been_read():
            self._original_text = self._file_name.read_text()
        return self._original_text

    def has_been_read(self):
        return self._original_text is not None

    @property
    def path(self):
        return self._file_name

    def write(self):
        self._file_name.write_text(self.text)
        self._lines = None

    def write_if_changed(self):
        if self.changed:
            self._file_name.write_text(self.text)
            self.changed = False
        self._lines = None

    def revert(self):
        if not self._file_name.exists():
            return
        assert self.has_been_read()
        self._file_name.write_text(self.original_text)

    def exists(self):
        return self._file_name.exists()
