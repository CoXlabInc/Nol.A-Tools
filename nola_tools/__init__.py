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

homedir = os.path.join(os.path.expanduser('~'), '.nola')
os.makedirs(homedir, exist_ok=True)

def load_config():
    config_file = os.path.join(homedir, 'config.json')
    config = None
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

    os.remove(key_file)
    with open(key_file, 'w') as f:
        f.write("-----BEGIN OPENSSH PRIVATE KEY-----\n")
        f.write(token)
        f.write("\n-----END OPENSSH PRIVATE KEY-----\n")
    os.chmod(key_file, 0o400)
        
def info():
    print("* This is info")

    config = load_config()

    # TODO Read Nol.A-project.json.
    return 0

def login(user, token):
    #print(f"Login user:{user}, token:{token}")

    config = load_config()
    if config is None:
        config = {}
    
    config['user'] = user
    save_config(config)
    set_key(token)

    repo_dir = os.path.join(homedir, 'repo')
    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)
    elif os.path.isfile(repo_dir):
        os.remove(repo_dir)
    
    repo = git.Repo.clone_from('https://github.com/CoXlabInc/Nol.A-Tools.git', repo_dir)
    if repo is not None:
        return True
    else:
        return False
    
def main():
    parser = argparse.ArgumentParser(description=f"Nol.A-SDK Command Line Interface version {__version__}")
    parser.add_argument('command', nargs='?', help='info, login={user}:{token}')
    args = parser.parse_args()

    if args.command is None:
        print("* A command must be specified.", file=sys.stderr)
        parser.print_help()
        return 1
    elif args.command == "info":
        return info()
    elif args.command.startswith("login"):
        if args.command[5] != "=":
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
        print("* Unknown command", file=sys.stderr)
        parser.print_help()
        return 1

if __name__ == '__main__':
    main()
