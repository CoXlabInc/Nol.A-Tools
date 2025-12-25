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
import platform

from .utils import config_file
from .build import build, clean, supported_boards
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
    print(f"* User: {user}")

    if os.path.exists(repo_dir) == False:
        print(f"* 'login' is required.", file=sys.stderr)
        return 1
    
    current_version, versions = get_versions(repo_dir)
    print(f"* Current version: {current_version}")
    print(f"* Avilable versions: {versions}")

    boards = list(supported_boards(repo_dir))
    print(f"* Avilable boards: {boards}", file=sys.stderr)

    if 'libnola' in config:
        print(f"* libnola under development: {config['libnola']}")
    return 0

def login(user, token):
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
    if 'user' in config.keys():
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

def get_path(key=None):
    config = config_file.load(config_json)
    paths = config.get('path')
    if type(paths) is dict:
        if key is None:
            for k in paths.keys():
                print(f"{k}: {paths[k]}")
        else:
            print(paths.get(key))

def set_path(key, path):
    config = config_file.load(config_json)
    paths = config.get('path')
    if type(paths) is not dict:
        paths = {}
    if path == "":
        if key in paths.keys():
            del paths[key]
    else:
        paths[key] = path
    config['path'] = paths
    config_file.save(config, config_json)

def devmode(path_to_libnola=None):
    config = config_file.load(config_json)
    if path_to_libnola is None:
        return config.get('libnola')
    elif path_to_libnola == '':
        if 'libnola' in config.keys():
            del config['libnola']
    else:
        config['libnola'] = os.path.expanduser(path_to_libnola)
    config_file.save(config, config_json)
    return config.get('libnola')
    
def main():
    config = config_file.load(config_json)
    if config.get('user') is None and os.path.exists(repo_dir) == False:
        print("* Cloning common library...")
        clone(repo_dir, None)

    parser = argparse.ArgumentParser(description=f"Nol.A-SDK Command Line Interface version {__version__}")
    parser.add_argument('command', nargs='?', help='info\nbuild[={board}], checkout[={version}], login={user}:{token}, logout, update, path={key}:{value}, devmode={path to libnola source tree}')
    args = parser.parse_args()

    if args.command is None:
        print("* A command must be specified.", file=sys.stderr)
        parser.print_help()
        return 1
    elif args.command == "info":
        return info()
    elif args.command.startswith("build"):
        if len(args.command) < 6:
            return 0 if build(config_file.load(config_json)) else 1
        elif args.command[5] == "=":
            return 0 if build(config_file.load(config_json), args.command[6:]) else 1
        else:
            print("* Use 'build=[board name]' to change the board", file=sys.stderr)
            parser.print_help()
            return 1
    elif args.command.startswith("flash"):
        if args.command == "flash":
            return 0 if build(config_file.load(config_json), board=None, interface='LAST') else 1
        elif args.command[5] == "=":
            return 0 if build(config_file.load(config_json), board=None, interface=args.command[6:]) else 1
        else:
            print("* Use 'flash=[interface name]' to flash the board new image", file=sys.stderr)
            parse.print_help()
            return 1
    elif args.command == 'clean':
        return 0 if clean() else 1
    elif args.command.startswith("checkout"):
        if len(args.command) < 9:
            print("* Checking out the latest version...")
            return 0 if checkout(repo_dir) else 1
        elif args.command[8] == "=":
            return 0 if checkout(repo_dir, args.command[9:]) else 1
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
        if logout():
            print(f"* Logged out successfully.")
            return 0
        else:
            print(f"* Logout failed.", file=sys.stderr)
            return 1

    elif args.command == "update":
        return 0 if update(repo_dir) else 1

    elif args.command.startswith("path"):
        def print_path_help():
            print("* 'path' shows all set paths.", file=sys.stderr)
            print("* 'path={key}' shows the path of the 'key'.", file=sys.stderr)
            print("* 'path={key}:{value}' set the path of the 'key'.", file=sys.stderr)
            print("* 'path={key}:' removes the path of the 'key'.", file=sys.stderr)
            
        if args.command == "path":
            get_path()
            return 0
        elif len(args.command) > 4 and args.command[4] == "=":
            path_args = args.command[5:].split(':', 1)
            if len(path_args) == 2 and path_args[0] != '?':
                set_path(path_args[0], path_args[1])
            elif path_args[0] != '?':
                get_path(path_args[0])
            else:
                print_path_help()
                return 1
            return 0
        else:
            print_path_help()
            return 1

    elif args.command == "doc":
        if platform.system() == 'Darwin':
            open_cmd = 'open'
        elif platform.system() == 'Linux':
            open_cmd = 'xdg-open'
        elif platform.system() == 'Windows':
            open_cmd = 'start'
        else:
            print(f"* Unsupported platform: {platform.system()}", file=sys.stderr)
            return 1

        config = config_file.load(config_json)
        if 'libnola' in config:
            doc_file = os.path.join(config['libnola'], 'nola-sdk', 'doc', 'html', 'index.html')
        else:
            doc_file = os.path.join(repo_dir, 'doc', 'html', 'index.html')
        
        if os.path.exists(doc_file):
            return os.system(f"{open_cmd} {doc_file}")
        else:
            print(f"* The doc file ({doc_file}) is not found.", file=sys.stderr)
            return 1

    elif args.command.startswith('devmode'):
        def print_devmode_help():
            print("* 'devmode' shows the libnola source path to build.", file=sys.stderr)
            print("* 'devmode={path}' set the libnola source path.", file=sys.stderr)
            print("* 'devmode=' removes the libnola source path.", file=sys.stderr)

        if args.command == 'devmode':
            path = devmode(None)
            if path is not None:
                print(path)
            return 0
        elif len(args.command) > 7 and args.command[7] == "=":
            new_path = args.command[8:]
            if new_path != '?':
                print(devmode(new_path))
                return 0
            else:
                print_devmode_help()
                return 1
        else:
            print_devmode_help()
            return 1
    else:
        print("* Unknown command", file=sys.stderr)
        parser.print_help()
        return 1

if __name__ == '__main__':
    main()
