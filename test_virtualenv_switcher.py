import collections
import configparser
import contextlib
import io
import mock
import os
import pytest
import subprocess

import virtualenv_switcher

# Test running mode:
# * `in` -- run the functions directly inside of the test process,
#   mock sys.argv, os.eniron, sys.stdout and sys.stderr.  Faster
#   but less realistic. This is how the tests run by default.
# * `sub` -- run the scripts in subprocess. Realistic but slower.
#   This mode can be activated by setting the `TEST_CALL_MODE`
#   environment variable to "sub". This is how Tox runs tests in
#   py35 environment.
CALL_MODE = os.environ.get('TEST_CALL_MODE', 'in')


@pytest.fixture
def homedir(tmpdir):
    return tmpdir.mkdir('home')


@pytest.fixture
def bindir(homedir):
    return homedir.mkdir('bin')


@pytest.fixture
def mock_venv(homedir):
    mock = homedir.mkdir('mock')
    venv = mock.mkdir('venv')
    bin = venv.mkdir('bin')
    activate = bin.join('activate')
    activate.write('foo')
    return venv


@pytest.fixture
def configfile(homedir):
    return homedir.join('.vs.conf')


@pytest.fixture
def getconfig(configfile):
    def loader():
        config = configparser.RawConfigParser()
        config.read(str(configfile))
        return config
    return loader


@pytest.fixture
def full_config(getconfig, configfile, bindir):
    config = getconfig()
    config.add_section('envs')
    config['envs']['foo'] = '/opt/foo'
    config['envs']['bar'] = '/usr/bar'
    config['envs']['baz'] = '/usr/baz'
    config['envs']['very-long-virtualenv-name'] = '/usr/qux'
    config.add_section('general')
    config['general']['path'] = str(bindir)
    with configfile.open('wt') as fp:
        config.write(fp)
    return config


@pytest.fixture
def runcmd(homedir, tmpdir):
    def _make_env():
        env = dict(os.environ)
        env['HOME'] = str(homedir)
        env['TMPDIR'] = str(tmpdir)
        return env

    def _print_ret(ret):
        print('RETCODE:', ret.returncode)
        print('STDOUT:', ret.stdout)
        print('STDERR:', ret.stderr)

    def run_sub(*cmd):
        print('Running:', cmd)
        ret = subprocess.run(cmd, env=_make_env(), universal_newlines=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _print_ret(ret)
        return ret

    def run_in(*cmd):
        print('Simulating:', cmd)
        Ret = collections.namedtuple('Ret', 'returncode stdout stderr')
        stdout = io.StringIO()
        stderr = io.StringIO()
        returncode = 0
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch('os.environ', new=_make_env()))
            stack.enter_context(mock.patch('sys.stdout', new=stdout))
            stack.enter_context(mock.patch('sys.stderr', new=stderr))
            stack.enter_context(mock.patch('sys.argv', new=list(cmd)))
            func_name = cmd[0].replace('-', '_')
            func = getattr(virtualenv_switcher, func_name)
            try:
                func()
            except SystemExit as exc:
                returncode = 1
                stderr.write('{}\n'.format(exc))
        ret = Ret(returncode, stdout.getvalue(), stderr.getvalue())
        _print_ret(ret)
        return ret

    return {'sub': run_sub, 'in': run_in}[CALL_MODE]


def test_create_config(runcmd, getconfig):
    ret = runcmd('vs-list')
    assert ret.returncode == 0
    config = getconfig()
    assert config['general'] == {}
    assert config['envs'] == {}
    assert config['exposed'] == {}


def test_add_bogus(runcmd, homedir):
    nonenv = homedir.mkdir('nonenv')
    ret = runcmd('vs-add', str(nonenv))
    assert ret.returncode == 1
    assert ret.stderr.startswith('No virtualenv')


def test_add_good(runcmd, getconfig, mock_venv):
    ret = runcmd('vs-add', str(mock_venv))
    assert ret.returncode == 0
    config = getconfig()
    assert config['envs']['mock'] == str(mock_venv)


def test_add_name(runcmd, getconfig, mock_venv):
    ret = runcmd('vs-add', str(mock_venv), 'foo')
    assert ret.returncode == 0
    config = getconfig()
    assert config['envs']['foo'] == str(mock_venv)


def test_add_duplicate(runcmd, mock_venv):
    runcmd('vs-add', str(mock_venv))
    ret = runcmd('vs-add', str(mock_venv))
    assert ret.returncode == 1
    assert ret.stderr.endswith('is already registered\n')


def test_add_duplicate_name(runcmd, full_config, mock_venv):
    ret = runcmd('vs-add', str(mock_venv), 'foo')
    assert ret.returncode == 0
    assert ret.stdout.endswith('as foo-1\n')


def test_list(runcmd, full_config):
    ret = runcmd('vs-list')
    assert ret.stdout == 'foo\nbar\nbaz\nvery-long-virtualenv-name\n'
    ret = runcmd('vs-list', '-f')
    assert ret.stdout == ('foo                  /opt/foo\n'
                          'bar                  /usr/bar\n'
                          'baz                  /usr/baz\n'
                          'very-long-virtualenv-name /usr/qux\n')


def test_del(runcmd, full_config, getconfig):
    runcmd('vs-del', 'fo')
    config = getconfig()
    assert 'foo' not in config['envs']


def test_complete(runcmd, full_config):
    ret = runcmd('vs-bash-complete', 'vs', '', 'vs')
    assert ret.stdout == 'foo\nbar\nbaz\nvery-long-virtualenv-name\n'
    ret = runcmd('vs-bash-complete', 'vs', 'b', 'vs')
    assert ret.stdout == 'bar\nbaz\n'
    ret = runcmd('vs-bash-complete', 'vs', 'f', 'vs')
    assert ret.stdout == 'foo\n'


def test_activate(runcmd, full_config):
    ret = runcmd('vs-bash-hook', 'foo')
    source, path = ret.stdout.strip().split()
    assert source == 'source'
    with open(path, 'rt') as fp:
        script = fp.read()
    assert 'source /opt/foo/bin/activate' in script
    assert 'rm ' + path in script


def test_activate_wrong(runcmd, full_config):
    ret = runcmd('vs-bash-hook', 'qux')
    assert ret.returncode == 1
    assert ret.stdout == ''
    assert ret.stderr == 'Unknown env: qux\n'


def test_activate_ambiguous(runcmd, full_config):
    ret = runcmd('vs-bash-hook', 'ba')
    assert ret.returncode == 1
    assert ret.stdout == ''
    assert ret.stderr == 'Ambiguous env name, possible matches: bar, baz\n'


def test_path_not_set(runcmd):
    ret = runcmd('vs-path')
    assert ret.returncode == 1
    assert ret.stderr == 'Path is not set\n'


def test_path(runcmd, full_config, bindir):
    ret = runcmd('vs-path')
    assert ret.stdout == str(bindir) + '\n'


def test_set_path(runcmd, getconfig, bindir):
    runcmd('vs-path', str(bindir))
    config = getconfig()
    assert config['general']['path'] == str(bindir)


def _mock_env(venv_path):
    venv_environ = dict(os.environ)
    if venv_path is None:
        del venv_environ['VIRTUAL_ENV']
    else:
        venv_environ['VIRTUAL_ENV'] = str(venv_path)
    return mock.patch('os.environ', venv_environ)


def test_expose(runcmd, getconfig, full_config, bindir, mock_venv):
    script = mock_venv.join('bin', 'foo')
    script.write('#!/bin/sh')
    script.chmod(int('777', base=8))
    runcmd('vs-add', str(mock_venv))
    config = getconfig()
    with _mock_env(mock_venv):
        runcmd('vs-expose', 'foo')
    exposed = bindir.join('foo')
    config = getconfig()
    assert config['exposed']['mock.foo'] == str(exposed)
    assert exposed.check(link=1)


def test_expose_noenv(runcmd, bindir):
    with _mock_env(None):
        ret = runcmd('vs-expose', 'foo')
    assert ret.returncode == 1
    assert ret.stderr.startswith('No virtualenv')


def test_expose_nocmd(runcmd, bindir, mock_venv):
    with _mock_env(mock_venv):
        ret = runcmd('vs-expose', 'foo')
    assert ret.returncode == 1
    assert ret.stderr.startswith('No foo command')


def test_expose_other_errors(runcmd, bindir, mock_venv):
    script = mock_venv.join('bin', 'foo')
    script.write('#!/bin/sh')
    with _mock_env(mock_venv):
        ret = runcmd('vs-expose', 'foo')
    assert ret.returncode == 1
    assert ret.stderr.endswith('is not executable\n')

    script.chmod(int('777', base=8))
    with _mock_env(mock_venv):
        ret = runcmd('vs-expose', 'foo')
    assert ret.returncode == 1
    assert ret.stderr.startswith('Current virtualenv is not registered')

    runcmd('vs-add', str(mock_venv))
    with _mock_env(mock_venv):
        ret = runcmd('vs-expose', 'foo')
    assert ret.returncode == 1
    assert ret.stderr.startswith('Path not configured')

    runcmd('vs-path', str(bindir))
    bindir.join('foo').write('')
    with _mock_env(mock_venv):
        ret = runcmd('vs-expose', 'foo')
    assert ret.returncode == 1
    assert ret.stderr.endswith('/foo already exists\n')
