import sys
import os
import shutil
import git
from functools import cmp_to_key

homedir = os.path.join(os.path.expanduser('~'), '.nola')
env = {
    "GIT_SSH_COMMAND": f"ssh -i {os.path.join(homedir, 'key')} -o IdentitiesOnly=yes -o StrictHostKeyChecking=no"
}

def clone(repo_dir, user):
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)

    try:
        if user is None:
            repo = git.Repo.clone_from("https://git.coxlab.kr/nola/libnola.git",
                                       repo_dir)
        else:
            repo = git.Repo.clone_from(f"ssh://git@git.coxlab.kr:40022/nola/libnola-{user}.git",
                                       repo_dir,
                                       env=env)
        return True
    except git.exc.GitCommandError:
        print(f"* Cloning repositry error", file=sys.stderr)
        return False

def get_versions(repo_dir):
    return get_current_version(repo_dir), get_available_versions(repo_dir)

def get_current_version(repo_dir):
    assert os.path.exists(repo_dir), "'login' is required."

    try:
        v = git.cmd.Git(repo_dir).describe('--tags', '--always', '--dirty', '--abbrev=7', '--long')
    except git.exc.GitCommandError as e:
        return None

    vparsed = {
        'describe': v
    }

    pos_dirty = v.rfind('-dirty')
    if pos_dirty >= 0:
        vparsed['dirty'] = True
        v = v[:pos_dirty]
    else:
        vparsed['dirty'] = False

    v = v.split('-')
    if len(v) == 1:
        vparsed['major'] = 0
        vparsed['minor'] = 0
        vparsed['patch'] = 0
        vparsed['commit'] = v[0]
    else:
        versions = v[0].split('.', maxsplit=3)
        vparsed['major'] = versions[0]
        vparsed['minor'] = versions[1] if len(versions) >= 2 else 0
        vparsed['patch'] = versions[2] if len(versions) >= 3 else 0
        vparsed['commit'] = v[2][1:]
        
    return vparsed

def get_available_versions(repo_dir):
    assert os.path.exists(repo_dir), "'login' is required."

    try:
        versions = git.Repo(repo_dir).tags
    except git.exc.GitCommandError as e:
        return []
    
    version_names = [v.name for v in versions]

    def is_valid(v_str):
        parts = v_str.lstrip('v').split('.')
        try:
            # Check if all parts can be converted to int
            for p in parts:
                int(p)
            return True
        except ValueError:
            return False

    valid_versions = [v for v in version_names if is_valid(v)]
    
    return list(reversed(sorted(valid_versions, key=cmp_to_key(cmp_version))))

def cmp_version(A, B):
    a = A.lstrip('v').split('.')
    b = B.lstrip('v').split('.')

    a = [int(p) for p in a]
    b = [int(p) for p in b]
    
    # Pad with 0s for versions with less than 3 components
    while len(a) < 3: a.append(0)
    while len(b) < 3: b.append(0)

    if a[0] == b[0]:
        if a[1] == b[1]:
            if a[2] == b[2]:
                return 0
            else:
                return 1 if a[2] > b[2] else -1
        else:
            return 1 if a[1] > b[1] else -1
    else:
        return 1 if a[0] > b[0] else -1

def checkout(repo_dir, version=None):
    assert os.path.exists(repo_dir), "'login' is required."

    repo = git.Repo(repo_dir)

    if version is not None:
        if version in [v.name for v in repo.tags]:
            print(f"* Checking out the version '{version}'...")
            repo.head.reset(f"refs/tags/{version}", working_tree=True)
            return True
        else:
            print(f"* The version '{version}' is not found.", file=sys.stderr)
            print(f"* Avilable versions: {get_available_versions(repo_dir)}")
            return False
    latest = get_available_versions(repo_dir)[0]

    print(f"* Checking out the latest version '{latest}'")
    repo.head.reset(f"refs/tags/{latest}", working_tree=True)
    return True
    
def update(repo_dir):
    assert os.path.exists(repo_dir), "'login' is required."

    repo = git.Repo(repo_dir)
    existing_versions = [t.name for t in repo.tags]
    
    result = git.Remote(repo, 'origin').fetch(env=env)
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
    
    return True
