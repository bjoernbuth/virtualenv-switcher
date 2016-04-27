# Virtualenv switcher commands.

import argparse
import configparser
import contextlib
import itertools
import os
import sys
import tempfile


@contextlib.contextmanager
def _config():
    """Read configuration, yield it out and then write it back if changed."""
    config_path = os.path.expanduser('~/.vs.conf')
    config = configparser.RawConfigParser()
    config.read(config_path)
    before = configparser.RawConfigParser()
    before.read_dict(config)

    if 'general' not in config:
        config.add_section('general')
    if 'envs' not in config:
        config.add_section('envs')
    if 'exposed' not in config:
        config.add_section('exposed')

    try:
        yield config
    finally:
        if config != before:
            with open(config_path, 'wt') as fp:
                config.write(fp)


def _match_env(config, name_prefix, target_path=None, strict=True):
    matches = []
    for name, path in config['envs'].items():
        if name.startswith(name_prefix) or path == target_path:
            matches.append((name, path))
    if not matches:
        if strict:
            sys.exit('Unknown env: {}'.format(name_prefix))
        else:
            return None
    if len(matches) > 1:
        if strict:
            sys.exit('Ambiguous env name, possible matches: {}'
                     .format(', '.join(m[0] for m in matches)))
    return matches[0]


def _activate_env(name, path, name_window=False):
    activate = os.path.join(path, 'bin', 'activate')
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        script = '''
            if [ -f {activate} ]
            then
                source {activate}
                if ! [ -z "${{_OLD_VIRTUAL_PS1+_}}" ]
                then
                    export PS1="[{name}] ${{_OLD_VIRTUAL_PS1}}"
                fi
            fi

            rm {tempfile}
            '''.format(name=name, activate=activate, tempfile=tf.name)
        if name_window:
            script += r'printf "\033k{}\033\\"'.format(name)
        tf.write(script.encode('utf-8'))
        print('source {}'.format(tf.name))


def vs_bash_hook():
    """Produce bash script to activate target virtualenv."""
    no_args = "If ran without arguments vs-bash-hook will redirect to vs-list."
    parser = argparse.ArgumentParser(description=vs_bash_hook.__doc__,
                                     epilog=no_args)
    parser.add_argument('--name-window', '-n', action='store_true',
                        help='Set terminal or tmux window name to the name '
                             ' of the virtualenv')
    parser.add_argument('name', nargs='?',
                        help='Full or partial virtualenv name')
    args = parser.parse_args()

    if not args.name:
        bin_path, _ = os.path.split(sys.argv[0])
        print(os.path.join(bin_path, 'vs-list'))
        return

    with _config() as config:
        name, path = _match_env(config, args.name)
        _activate_env(name, path, args.name_window)


def vs_bash_complete():
    """Complete the name of a virtualenv."""
    parser = argparse.ArgumentParser(description=vs_bash_complete.__doc__)
    parser.add_argument('command', help='Command')
    parser.add_argument('comparg', help='Argument that is being completed')
    parser.add_argument('prevarg', help='Previous argument')
    args = parser.parse_args()
    with _config() as config:
        for name in config['envs']:
            if name.startswith(args.comparg):
                print(name)


def _autoname(path):
    path, name = os.path.split(path)
    if name in ['env', 'venv', 'virtualenv', 'devenv'] and path:
        path, name = os.path.split(path)
    return name


def vs_add():
    """Add virtualenv to configuration."""
    parser = argparse.ArgumentParser(description=vs_add.__doc__)
    parser.add_argument('path', help='Path to the virtualenv')
    parser.add_argument('name', nargs='?', help='Name for the virtualenv')
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    if not os.path.exists(os.path.join(path, 'bin', 'activate')):
        sys.exit('No virtualenv at {}'.format(path))

    name = args.name or _autoname(path)

    with _config() as config:
        if _match_env(config, '\n impossible \n', path, strict=False):
            sys.exit('Virtualenv at {} is already registered'.format(path))
        if name in config['envs']:
            for i in itertools.count(1):
                name2 = '{}-{}'.format(name, i)
                if name2 not in config['envs']:
                    name = name2
                    break
        config['envs'][name] = path
        if name != args.name:
            print('Added {} as {}'.format(path, name))


def vs_del():
    """Delete virtualenv from configuration."""
    parser = argparse.ArgumentParser(vs_del.__doc__)
    parser.add_argument('virtualenv', help='Full or partial name or path '
                        'of target virtualenv (see vs-list).')
    args = parser.parse_args()

    path = os.path.abspath(args.virtualenv)
    if not os.path.exists(path):
        path = None

    with _config() as config:
        name, path = _match_env(config, args.virtualenv, path)
        del config['envs'][name]
        # TODO: Delete exposed commands?


def vs_list():
    """List all configured virtualenvs."""
    parser = argparse.ArgumentParser(vs_list.__doc__)
    parser.add_argument('--full', '-f', action='store_true',
                        help='Include path')
    args = parser.parse_args()

    with _config() as config:
        if args.full:
            max_name_len = max(len(name) for name in config['envs'])
            template = '{{:{}}} {{}}'.format(min(max_name_len, 20))
            for name, path in config['envs'].items():
                print(template.format(name, path))
        else:
            for name in config['envs']:
                print(name)


def vs_expose():
    """Symlink a command from a virtualenv to the scripts dir."""
    parser = argparse.ArgumentParser(vs_expose.__doc__)
    parser.add_argument('command', help='Command to expose')
    args = parser.parse_args()
    command = args.command

    env_path = os.environ.get('VIRTUAL_ENV', None)
    if env_path is None:
        sys.exit('No virtualenv activated')
    bin_path = os.path.join(env_path, 'bin')
    cmd_path = os.path.join(bin_path, command)
    if not os.path.exists(cmd_path):
        sys.exit('No {} command in {}'.format(command, bin_path))
    if not os.access(cmd_path, os.X_OK):
        sys.exit('{} is not executable'.format(cmd_path))

    with _config() as config:
        match = _match_env(config, '\n impossible \n', env_path, strict=False)
        if not match:
            sys.exit('Current virtualenv is not registered (use vs-add)')
        env_name, _ = match
        if 'path' not in config['general']:
            sys.exit('Path not configured (use vs-path)')
        exp_path = config['general']['path']
        alias_path = os.path.join(exp_path, command)
        if os.path.exists(alias_path):
            sys.exit('{} already exists'.format(alias_path))
        os.symlink(cmd_path, alias_path)
        config['exposed']['{}.{}'.format(env_name, command)] = alias_path


def vs_path():
    """Show and set the path to the directory where commands are exposed."""
    parser = argparse.ArgumentParser(vs_del.__doc__)
    parser.add_argument('path', nargs='?', help='Target path')
    args = parser.parse_args()
    with _config() as config:
        if args.path is None:
            if 'path' in config['general']:
                print(config['general']['path'])
            else:
                sys.exit('Path is not set')
        else:
            config['general']['path'] = args.path


def vs_install():
    """Display installation instructions."""
    parser = argparse.ArgumentParser(vs_install.__doc__)
    bin_dir, _ = os.path.split(sys.argv[0])
    bash_hook = os.path.join(bin_dir, 'vs-bash-hook')
    bash_complete = os.path.join(bin_dir, 'vs-bash-complete')
    print('''
# The following function and completion configurations are added by
# virtualenv switcher (located at {bin_dir}).
function vs {{
    # Remove -n below if you don't want Tmux integration.
    `{bash_hook} -n $1`
}}
alias vs-off=deactivate
complete -C {bash_complete} vs
complete -C {bash_complete} vs-del'''.format(**locals()))
