# encoding: utf-8
 
import sys
from hglib.client import hgclient, cmdbuilder, b


def open(path=None, encoding=None, configs=None):
    '''starts a cmdserver for the given path (or for a repository found
    in the cwd). HGENCODING is set to the given encoding. configs is a
    list of key, value, similar to those passed to hg --config.
    '''
    return HgClient(path, encoding, configs)


# hglib is not handling ruamel.yaml.clib repo tags correctly
class HgClient(hgclient):

    def tags(self):
        """
        Return a list of repository tags as: (name, rev, node, islocal)
        """
        args = cmdbuilder(b('tags'), v=True)

        out = self.rawcommand(args)

        t = []
        for line in out.splitlines():
            taglocal = line.endswith(b(' local'))
            if taglocal:
                line = line[:-6]
            name, rev = line.rsplit(b(' '), 1)
            try:
                rev, node = rev.split(b(':'))
            except:
                print('rev', rev, file=sys.stdout)
                continue
                raise
            t.append((name.rstrip(), int(rev), node, taglocal))
        return t



