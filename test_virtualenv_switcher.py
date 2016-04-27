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
def config_with_envs(getconfig, configfile):
    config = getconfig()
    config.add_section('envs')
    config['envs']['foo'] = '/opt/foo'
    config['envs']['bar'] = '/usr/bar'
    config['envs']['baz'] = '/usr/baz'
    config['envs']['very-long-virtualenv-name'] = '/usr/qux'
    with configfile.open('wt') as fp:
        config.write(fp)
    return config


@pytest.fixture
def runcmd(homedir, tmpdir):
    env = dict(os.environ)
    env['HOME'] = str(homedir)
    env['TMPDIR'] = str(tmpdir)

    def _print_ret(ret):
        print('RETCODE:', ret.returncode)
        print('STDOUT:', ret.stdout)
        print('STDERR:', ret.stderr)

    def run_sub(*cmd):
        print('Running:', cmd)
        ret = subprocess.run(cmd, env=env, universal_newlines=True,
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
            stack.enter_context(mock.patch('os.environ', new=env))
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


def test_add_duplicate_name(runcmd, config_with_envs, mock_venv):
    ret = runcmd('vs-add', str(mock_venv), 'foo')
    assert ret.returncode == 0
    assert ret.stdout.endswith('as foo-1\n')


def test_list(runcmd, config_with_envs):
    ret = runcmd('vs-list')
    assert ret.stdout == 'foo\nbar\nbaz\nvery-long-virtualenv-name\n'
    ret = runcmd('vs-list', '-f')
    assert ret.stdout == ('foo                  /opt/foo\n'
                          'bar                  /usr/bar\n'
                          'baz                  /usr/baz\n'
                          'very-long-virtualenv-name /usr/qux\n')


def test_del(runcmd, config_with_envs, getconfig):
    runcmd('vs-del', 'fo')
    config = getconfig()
    assert 'foo' not in config['envs']


def test_complete(runcmd, config_with_envs):
    ret = runcmd('vs-bash-complete', 'vs', '', 'vs')
    assert ret.stdout == 'foo\nbar\nbaz\nvery-long-virtualenv-name\n'
    ret = runcmd('vs-bash-complete', 'vs', 'b', 'vs')
    assert ret.stdout == 'bar\nbaz\n'
    ret = runcmd('vs-bash-complete', 'vs', 'f', 'vs')
    assert ret.stdout == 'foo\n'


def test_activate(runcmd, config_with_envs):
    ret = runcmd('vs-bash-hook', 'foo')
    source, path = ret.stdout.strip().split()
    assert source == 'source'
    with open(path, 'rt') as fp:
        script = fp.read()
    assert 'source /opt/foo/bin/activate' in script
    assert 'rm ' + path in script


def test_activate_wrong(runcmd, config_with_envs):
    ret = runcmd('vs-bash-hook', 'qux')
    assert ret.returncode == 1
    assert ret.stdout == ''
    assert ret.stderr == 'Unknown env: qux\n'


def test_activate_ambiguous(runcmd, config_with_envs):
    ret = runcmd('vs-bash-hook', 'ba')
    assert ret.returncode == 1
    assert ret.stdout == ''
    assert ret.stderr == 'Ambiguous env name, possible matches: bar, baz\n'
