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

    if os.path.exists(key_file):
        os.remove(key_file)
    with open(key_file, 'w') as f:
        f.write("-----BEGIN OPENSSH PRIVATE KEY-----\n")
        f.write(token)
        f.write("\n-----END OPENSSH PRIVATE KEY-----\n")
    os.chmod(key_file, 0o400)

def get_latest_version(A, B):
    a = A.split('.')
    b = B.split('.')
    if a[0] == b[0]:
        if a[1] == b[1]:
            if a[2] == b[2]:
                return None
            else:
                return A if (a[2] > b[2]) else B
        else:
            return A if (a[1] > b[1]) else B
    else:
        return A if (a[0] > b[0]) else B
    
def checkout(version=None):
    repo = git.Repo(os.path.join(homedir, 'repo'))

    if version is not None:
        if version in [v.name for v in repo.tags]:
            print(f"* Checking out the version '{version}'...")
            repo.head.reset(f"refs/tags/{version}", working_tree=True)
            return True
        else:
            print(f"* The version '{version}' is not found.")
            return False
        
    latest = None
    for v in repo.tags:
        if latest is None:
            latest = v.name
        else:
            new_one = get_latest_version(latest, v.name)
            if new_one is not None:
                latest = new_one

    print(f"* Checking out the latest version '{latest}'")
    repo.head.reset(f"refs/tags/{latest}", working_tree=True)
    return True
    
def info():
    print(f"* Nol.A-SDK Command Line Interface v{__version__}")

    config = load_config()
    if config is None:
        user = None
    else:
        user = config['user']
    print(f"User: {user}")

    try:
        repo = git.Repo(os.path.join(homedir, 'repo'))

        current_version = repo.head.commit
        versions = []
        for v in repo.tags:
            versions.append(v.name)
            if repo.head.commit == v.commit:
                current_version = v.name
        print(f"Current version: {current_version}")
        print(f"Avilable versions: {versions}")
    except git.exc.NoSuchPathError:
        print(f"Library repository not found")

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
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)

    try:
        repo = git.Repo.clone_from(f"ssh://git@git.coxlab.kr:40022/nola/libnola-{user}.git",
                                   repo_dir,
                                   env={"GIT_SSH_COMMAND": f"ssh -i {os.path.join(homedir, 'key')} -o IdentitiesOnly=yes -o StrictHostKeyChecking=no"})
    except git.exc.GitCommandError:
        print(f"* Cloning repositry error")
        return False
    
    return checkout()


def logout():
    config_file = os.path.join(homedir, 'config.json')
    if os.path.isfile(config_file):
        os.remove(config_file)
    elif os.path.isdir(config_file):
        shutil.rmtree(config_file)

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

    return True
    
def update():
    repo = git.Repo(os.path.join(homedir, 'repo'))
    existing_versions = [t.name for t in repo.tags]
    
    result = git.Remote(repo, 'origin').fetch()
    if result[0].flags & git.remote.FetchInfo.ERROR != 0:
        print("* ERROR on update")

    if result[0].flags & git.remote.FetchInfo.REJECTED != 0:
        print("* REJECTED on update")

    if result[0].flags & git.remote.FetchInfo.NEW_TAG != 0:
        avilable_versions = [t.name for t in repo.tags]
        new_versions = []
        for a in avilable_versions:
            if a not in existing_versions:
                new_versions.append(a)
                
        print(f"* New version(s) avilable: {new_versions}")
        print(f"* Change the version by 'checkout' command")

    if result[0].flags & git.remote.FetchInfo.HEAD_UPTODATE:
        print("* Up to date")
    
def main():
    parser = argparse.ArgumentParser(description=f"Nol.A-SDK Command Line Interface version {__version__}")
    parser.add_argument('command', nargs='?', help='info, checkout[={version}], login={user}:{token}, logout, update')
    args = parser.parse_args()

    if args.command is None:
        print("* A command must be specified.", file=sys.stderr)
        parser.print_help()
        return 1
    elif args.command == "info":
        return info()
    elif args.command.startswith("checkout"):
        if len(args.command) < 9:
            print("* Checking out the latest version...")
            return checkout()
        elif args.command[8] != "=":
            print("* Use 'checkout=[version]' to specify the version", file=sys.stderr)
            parse.print_help()
            return 1
        else:
            return checkout(args.command[9:])
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
        return update()
    else:
        print("* Unknown command", file=sys.stderr)
        parser.print_help()
        return 1

if __name__ == '__main__':
    main()
