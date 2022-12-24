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

from .utils import config_file
from .build import build, flash
from .repo import clone, get_versions, get_current_version, checkout, update

home_dir = os.path.join(os.path.expanduser('~'), '.nola')
os.makedirs(home_dir, exist_ok=True)

config_json = os.path.join(home_dir, 'config.json')
repo_dir = os.path.join(home_dir, 'repo')
key_file = os.path.join(home_dir, 'key')

# TODO Clone the public library.

def set_key(token):
    if os.path.exists(key_file):
        os.remove(key_file)
    with open(key_file, 'w') as f:
        f.write("-----BEGIN OPENSSH PRIVATE KEY-----\n")
        f.write(token)
        f.write("\n-----END OPENSSH PRIVATE KEY-----\n")
    os.chmod(key_file, 0o400)

def info():
    print(f"* Nol.A-SDK Command Line Interface v{__version__}")

    config = config_file.load(config_json)
    if 'user' in config:
        user = config['user']
    else:
        user = None
    print(f"User: {user}")

    current_version, versions = get_versions(repo_dir)
    print(f"Current version: {current_version}")
    print(f"Avilable versions: {versions}")

    if 'libnola' in config:
        print(f"libnola under development: {config['libnola']}")
    return 0

def login(user, token):
    #print(f"Login user:{user}, token:{token}")

    config = config_file.load(config_json)
    config['user'] = user
    set_key(token)

    if clone(repo_dir, user):
        config_file.save(config, config_json)
        return checkout(repo_dir)
    else:
        return False

def logout():
    config = config_file.load(config_json)
    del config['user']
    config_file.save(config, config_json)

    if os.path.isfile(key_file):
        os.remove(key_file)
    elif os.path.isdir(key_file):
        shutil.rmtree(key_file)

    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)
    elif os.path.isfile(repo_dir):
        os.remove(repo_dir)

    # TODO Clone the public library.
    
    return True

def devmode(path_to_libnola):
    config = config_file.load(config_json)
    if path_to_libnola == '':
        del config['libnola']
    else:
        config['libnola'] = os.path.expanduser(path_to_libnola)
    config_file.save(config, config_json)
    
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
            return build(config_file.load(config_json))
        elif args.command[5] == "=":
            return build(config_file.load(config_json), args.command[6:])
        else:
            print("* Use 'build=[board name]' to change the board", file=sys.stderr)
            parser.print_help()
            return 1
    elif args.command.startswith("flash"):
        if args.command == "flash":
            return flash(config_file.load(config_json))
        elif args.command[5] == "=":
            interface = args.command[6:]
            return flash(config_file.load(config_json), interface)
        else:
            print("* Use 'flash=[interface name]' to flash the board new image", file=sys.stderr)
            parse.print_help()
            return 1
    elif args.command.startswith("checkout"):
        if len(args.command) < 9:
            print("* Checking out the latest version...")
            return checkout(repo_dir)
        elif args.command[8] == "=":
            return checkout(repo_dir, args.command[9:])
        else:
            print("* Use 'checkout=[version]' to specify the version", file=sys.stderr)
            parse.print_help()
            return 1
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
        return update(repo_dir)
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
