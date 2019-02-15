# Virtualenv Switcher

Python developers often end up with many virtualenvs scattered around the
hard drive. Some belong to a particular project, some are general,
some are created for a particular tool. Remembering the location of all
environments, typing their paths to activate them and distinguishing which
one is active now (for example if you happen to have `foo/venv` and `bar/venv`)
can get tedious. There must be a better way!

    $ vs-add ~/envs/numpy
    Added /home/foo/envs/numpy as numpy
    $ vs-add ~/envs/hg mercurial
    $ vs-list
    numpy      /home/foo/envs/numpy
    mercurial  /home/foo/envs/hg
    $ hg
    hg: command not found
    $ vs mer
    [mercurial] $ hg st
    abort: no repository found in ...
    [mercurial] $ vs-expose hg
    [mercuaial] $ vs-off
    $ hg
    abort: no repository found in ...

## Installation

Prerequisites: a virtualenv with Python 3.

This will install `virtualenv-switcher` using `pip` and append the `vs`
function and its completion configuration to your bash profile:

    (vs-env) $ pip install virtualenv-switcher
    (vs-env) $ vs-install >>~/.bashrc
    (vs-env) $ source ~/.bashrc

## Configuration

Virtualenv Switcher keeps the paths to all virtualenvs as well as the path
the directory where the commands are exposed in `~/.vs.conf`.
The file will be created if it doesn't exist. It can be edited by hand or
via the following commands:

* `vs-add` -- to add a virtualenv to the configuration,
* `vs-del` -- to delete virtualenv from the configuration,
* `vs-path` -- to configure the path for exposing the commands.

## Other features

* By default `vs-install` configures autocompletion of virtualenv names for
  `vs` and `vs-del`.
* When a virtualenv is activated its name becomes the name of the window in
  Tmux and some terminal emulators. This behavior can be disabled by editing
  the code that is added to the profile by `vs-install`.

## Alternatives

* [Virtualenvwrapper](https://virtualenvwrapper.readthedocs.org/en/latest/index.html)
  has some of the functionality of Virtualenv Switcher and quite a bit more on
  top.  The scope of two packages is different: Virtualenvwrapper is a more
  complete virtualenv management solution whereas this package just makes
  switching between the environments as easy as possible and does not force any
  decisions on the user.
