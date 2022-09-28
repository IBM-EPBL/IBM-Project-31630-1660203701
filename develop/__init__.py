# coding: utf-8

from __future__ import print_function, absolute_import, division, unicode_literals

_package_data = dict(
    full_package_name='develop',
    version_info=(0, 2, 1),
    __version__='0.2.1',
    author='Anthon van der Neut',
    author_email='a.van.der.neut@ruamel.eu',
    description='tool to develop python packages',
    url='https://sourceforge.net/projects/ruamel-develop',
    # keywords="",
    entry_points='dv=develop.__main__:main',
    # entry_points=None,
    license='MIT',
    since=2017,
    python_requires='>=3.8',
    # status="α|β|stable",  # the package status on PyPI
    # data_files="",
    # universal=True,
    print_allowed=True,
    install_requires=[
            'ruamel.showoutput',
            'python-hglib',
            'repo',
            'readme-renderer',
            'configobj', # for hgrc
    ],
    tox=dict(
        env='3',
    ),
    pre_black=True,
)


version_info = _package_data['version_info']
__version__ = _package_data['__version__']


_cligen_data = """\
!Cli 0:
- !Instance develop.develop.Develop
- !Config pon
- !Opt [verbose, v, !Help increase verbosity level, !Action count, const: 1, nargs: 0, default: 0]
- !PSO [distbase, !Help 'base directory for all distribution files (default: %(default)s)']
- !PSO [tarbase, !Help 'base directory for all backup tar files (tar subcommand) (default: %(default)s)']
- !PSO [toxbase, !Help 'base directory for all .tox directories (default: %(default)s)']
- !PSO [maintainer, metavar: MNT, !Help 'maintainer information (e.g. Dockerfile, default: "%(default)s")']
- !Opt [detox, !Help parallel tox with detox, !Action store_true]
- !Opt [keep, !Help keep temporary files, !Action store_true]
- !PSO [date, !Action date, default: today, metavar: DATE, !Help 'update date README.rst to %(metavar)s (default: %(default)s)']
- !Opt [test, !Action store_true, !Help "create dated tar file of EVERYTHING, commit, but don't push commits, nor push to PyPI"]
- clean:
  - !Arg [args, nargs: '*']
  - !Help clean up development directory
- dist:
  - !Opt [all, !Action store_true, !Help build sdist and wheels for all platforms]
  - !Opt [sdist, src, s, !Action store_true, !Help build sdist]
  - !Opt [linux, !Action store_true, !Help build linux wheels using manylinux]
  - !Opt [macos, !Action store_true, !Help build macOS wheels]
  - !Opt [windows, !Action store_true, !Help build windows wheels on appveyor]
  - !Opt [kw, !Action store_true, !Help show keywords as calculated by setup.py]
  - !Opt [full, !Action store_true, !Help show full path for dist files]
  - !Opt [appveyor-check, !Action store_true, !Help show appveyor status]
  - !Opt [appveyor-pull, !Action store_true, !Help pull manually started artifacts from appveyor]
  - !Help execute dist related commands
- make:
  - !Arg [args, nargs: '*']
  - !Help invoke make (with args), writes .Makefile.tmp
- mypy:
  - !Opt [edit, !Action store_true, !Help on error/note invoke editor on first line]
  - !Help invoke mypy --strict
- push:
  - !Opt [changestest, !Action store_true, !Help test update of CHANGES]
  - !Opt [reuse-message, re-use-message, !Action store_true, !Help reuse commit message]
  - !Opt [commit-message, !Help use commit message (no interaction)]
  - !Opt [no-tox, !Action store_true, !Help don't run tox -r]
  - !Opt [test-readme-message, !Help ==SUPPRESS==]
  - !Opt [e, !Help ==SUPPRESS==]
  - !Help create and push a new release
- rtfd:
  - !Opt [build, !Action store_true, !Help trigger build]
  - !Opt [admin, !Action store_true, !Help show admin page]
  - !Opt [show, !Action store_true, !Help show documentation]
  - !Help execute Read the Docs related commands
- readme:
  - !Opt [version, metavar: X.Y.Z, !Help update version in README.rst to %(metavar)s]
  - !Opt [date, !Action date, default: today, metavar: DATE, !Help 'update date README.rst to %(metavar)s (default: %(default)s)']
  - !Help execute readme related commands
- badge:
  - !Opt [oitnb, !Action store_true, !Help write oitnb badge]
  - !Help create initial badges in _doc/_static
- tox:
  - !Opt [e, metavar: TARGETS, !Help only test comma separated %(metavar)s]
  - !Opt [E, !Action store_true, !Help show targets calculated from package_data]
  - !Opt [r, !Action store_true, !Help force recreation of virtual environments by removign them first]
  - !Opt [q, !Action count, const: 1, nargs: 0, default: 1, !Help decrease tox verbosity level]
  - !Arg [args, nargs: '*']
  - !Help invoke tox (with args)
- commit:
  - !Opt [all, !Action store_true, !Help commmit all changed files]
  - !Arg [args, nargs: '*']
  - !Help commit files (excluding README.* and __init__.py)
- version:
  - !Opt [badge, !Action store_true, !Help write version in PyPI badge]
  - !Opt [dev, !Action store_true, !Help add "dev", default: null]
  - !Opt [no-dev, !Action store_false, dest: dev, !Help remove "dev"]
  - !Opt [rm-dev, !Action store_false, dest: dev, !Help ==SUPPRESS==]
  - !Arg [args, nargs: '*']
  - !Help execute version related commands
- check:
  - !Help check sanity of the package (also done on push)
- check_setup:
  - !Help check setup.py)
- walk:
  - !Opt [check-init, !Action store_true, !Help check __init__.py files]
  - !Opt [insert-pre-black, !Action store_true, !Help insert pre-black entry in __init__.py files]
  - !Opt [check-hgignore, !Action store_true, !Help 'remove entries in .hgignore files that are in global ignore file, delete when emtpy']
  - !Help walk the development tree recursively and execute actions
- sfup:
  - !Opt [version, !Help 'tag to use, defaults to latest tag']
  - !Help upload .tar.xz file to sourceforge
- bbup:
  - !Opt [version, !Help 'tag to use, defaults to latest tag']
  - !Help upload .tar.xz file to bitbucket
- bbup0:
  - !Opt [version]
  - !Opt [user, default: ruamel]
  - !Opt [repo, default: yaml]
  - !Opt [pypi, default: ruamel.yaml]
  - !Arg [file]
  - !Help upload a file to bitbucket
- patchwheel:
  - !Opt [filenames, metavar: FN, !Action append, nargs: 2, !Help rename the part of any filename matching first %(metavar)s argument to second (option can be given multiple times)]
  - !Opt [wheelnames, metavar: WHL, !Action append, nargs: 2, !Help rename the part of wheel name matching first %(metavar)s argument to second (option can be given multiple times)]
  - !Opt [outdir, !Help 'directory where to write the output .whl file (if not given --wheelnames not given, wheels will be updated in place)']
  - !Arg [file, nargs: +]
  - !Help patch wheel file
- tar:
  - !Opt [create, !Action store_true, !Help create dated tar file]
  - !Opt [restore, !Action store_true, !Help restore latest dated tar file]
  - !Opt [list, !Action store_true, !Help list all dated tar file]
  - !Arg [command, !Help 'create, restore, list if empty)', nargs: '?']
  - !Help create/restore dated tar file of EVERYTHING, so you can test local commits
- exe:
  - !Opt [force, !Action store_true, !Help backup and create if already exists]
  - !Opt [show, !Action store_true, !Help restore latest dated tar file]
  - !Help create executable in ~/bin
"""
