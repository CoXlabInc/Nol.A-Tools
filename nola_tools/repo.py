import sys
import os
import shutil
import git

homedir = os.path.join(os.path.expanduser('~'), '.nola')

def clone(repo_dir, user):
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)

    try:
        repo = git.Repo.clone_from(f"ssh://git@git.coxlab.kr:40022/nola/libnola-{user}.git",
                                   repo_dir,
                                   env={"GIT_SSH_COMMAND": f"ssh -i {os.path.join(homedir, 'key')} -o IdentitiesOnly=yes -o StrictHostKeyChecking=no"})
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
    return [v.name for v in versions]

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
    
def update(repo_dir):
    assert os.path.exists(repo_dir), "'login' is required."

    repo = git.Repo(repo_dir)
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
    
