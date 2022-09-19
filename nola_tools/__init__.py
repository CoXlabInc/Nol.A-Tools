all = ('__version__')

from pbr.version import VersionInfo

# Check the PBR version module docs for other options than release_string()
__version__ = VersionInfo('nola_tools').release_string()

import argparse
import sys
import os
import json
import shutil
import git

from .build import build
from .repo import clone, get_versions, get_current_version, checkout, update

homedir = os.path.join(os.path.expanduser('~'), '.nola')
os.makedirs(homedir, exist_ok=True)

# TODO Clone the public library.

def load_config():
    config_file = os.path.join(homedir, 'config.json')
    config = {}
    if os.path.exists(config_file):
        with open(config_file) as f:
            config = json.load(f)
    return config

def save_config(config):
    config_file = os.path.join(homedir, 'config.json')
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f)
        
def set_key(token):
    key_file = os.path.join(homedir, 'key')

    if os.path.exists(key_file):
        os.remove(key_file)
    with open(key_file, 'w') as f:
        f.write("-----BEGIN OPENSSH PRIVATE KEY-----\n")
        f.write(token)
        f.write("\n-----END OPENSSH PRIVATE KEY-----\n")
    os.chmod(key_file, 0o400)

def info():
    print(f"* Nol.A-SDK Command Line Interface v{__version__}")

    config = load_config()
    if 'user' in config:
        user = config['user']
    else:
        user = None
    print(f"User: {user}")

    current_version, versions = get_versions(os.path.join(homedir, 'repo'))
    print(f"Current version: {current_version}")
    print(f"Avilable versions: {versions}")

    if 'libnola' in config:
        print(f"libnola under development: {config['libnola']} ({get_current_version(os.path.join(config['libnola'], 'nola-sdk'))})")
    return 0

def login(user, token):
    #print(f"Login user:{user}, token:{token}")

    config = load_config()    
    config['user'] = user
    set_key(token)

    if clone(os.path.join(homedir, 'repo'), user):
        save_config(config)
        return checkout(os.path.join(homedir, 'repo'))
    else:
        return False

def logout():
    config = load_config()
    del config['user']
    save_config(config)

    key_file = os.path.join(homedir, 'key')
    if os.path.isfile(key_file):
        os.remove(key_file)
    elif os.path.isdir(key_file):
        shutil.rmtree(key_file)

    repo_dir = os.path.join(homedir, 'repo')
    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)
    elif os.path.isfile(repo_dir):
        os.remove(repo_dir)

    # TODO Clone the public library.
    
    return True

def devmode(path_to_libnola):
    config = load_config()
    if path_to_libnola == '':
        del config['libnola']
    else:
        config['libnola'] = os.path.expanduser(path_to_libnola)
    save_config(config)
    
def main():
    parser = argparse.ArgumentParser(description=f"Nol.A-SDK Command Line Interface version {__version__}")
    parser.add_argument('command', nargs='?', help='info, build[={board}], checkout[={version}], login={user}:{token}, logout, update, devmode={path to libnola source tree}')
    args = parser.parse_args()

    if args.command is None:
        print("* A command must be specified.", file=sys.stderr)
        parser.print_help()
        return 1
    elif args.command == "info":
        return info()
    elif args.command.startswith("build"):
        if len(args.command) < 6:
            return build(load_config())
        elif args.command[5] != "=":
            print("* Use 'build=[board name]' to change the board", file=sys.stderr)
            parse.print_help()
            return 1
        else:
            return build(load_config(), args.command[6:])
    elif args.command.startswith("checkout"):
        if len(args.command) < 9:
            print("* Checking out the latest version...")
            return checkout(os.path.join(homedir, 'repo'))
        elif args.command[8] != "=":
            print("* Use 'checkout=[version]' to specify the version", file=sys.stderr)
            parse.print_help()
            return 1
        else:
            return checkout(os.path.join(homedir, 'repo'), args.command[9:])
    elif args.command.startswith("login"):
        if len(args.command) < 6 or args.command[5] != "=":
            print("* 'login' command requires both user and token parameters", file=sys.stderr)
            parser.print_help()
            return 1
        params = args.command[6:].split(":", maxsplit=1)
        if len(params) != 2:
            print("* 'login' command requires both user and token parameters", file=sys.stderr)
            parser.print_help()
            return 1
        user = params[0]
        token = params[1]
        if login(user, token):
            print("* Logged in successfully.")
            return 0
        else:
            print("* Log-in failed. Please 'logout' to clean up.")
            return 1
    elif args.command == "logout":
        logout()
        print(f"* Logged out successfully.")

    elif args.command == "update":
        return update(os.path.join(homedir, 'repo'))
    elif args.command.startswith('devmode'):
        if len(args.command) < 8 or args.command[7] != "=":
            print(" * 'devmode' command requires libnola path", file=sys.stderr)
            parser.print_help()
            return 1
        devmode(args.command[8:])
    else:
        print("* Unknown command", file=sys.stderr)
        parser.print_help()
        return 1

if __name__ == '__main__':
    main()
