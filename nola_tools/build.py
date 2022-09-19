import sys
import os
import json
import shutil
import glob
import subprocess

from .repo import get_current_version

def supported_boards(repo_dir):
    for d in os.listdir(repo_dir):
        if os.path.isdir(os.path.join(repo_dir, d)) and d not in ['include', 'make', 'tools', '.git']:
            yield d

def build(config, board=None):
    if os.path.exists('Nol.A-project.json') == False:
        print("* Do 'build' under the Nol.A project directory.", file=sys.stderr)
        print("* If you want to start a new project, use 'new' command.", file=sys.stderr)
        return False

    with open("Nol.A-project.json") as f:
        project = json.load(f)

    if board is not None:
        project['board'] = board

    if 'libnola' in config:
        make_process = subprocess.Popen(['make', '-C', config['libnola'], f"TARGET={project['board']}", "SKIP_BUILD_TEST=1"],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        env=os.environ)
        os.set_blocking(make_process.stdout.fileno(), False)
        os.set_blocking(make_process.stderr.fileno(), False)
        while True:
            output = make_process.stdout.readline()
            if len(output) > 0:
                print(output.decode(), end='')
            error = make_process.stderr.readline()
            if len(error) > 0:
                print(error.decode(), end='', file=sys.stderr)
            ret_code = make_process.poll()
            if ret_code is not None:
                break

        if ret_code != 0:
            print(f"* Building libnola failed ({ret_code})", file=sys.stderr)
            return False
        
        repo_dir = os.path.join(config['libnola'], 'nola-sdk')
    else:
        repo_dir = os.path.join(os.path.expanduser('~'), '.nola', 'repo')
        
    if project['board'] not in supported_boards(repo_dir):
        print(f"* The board '{project['board']}' not supported.", file=sys.stderr)
        boards = list(supported_boards())
        print(f"* Avilable boards: {boards}", file=sys.stderr)
        return False

    print(f"* Target board: {project['board']}")
    with open("Nol.A-project.json", 'w', encoding='utf-8') as f:
        json.dump(project, f, indent=4)

    current_version = get_current_version(repo_dir)
    print(f"* Current version: {current_version} {'(dev)' if 'libnola' in config else ''}")

    build_dir = os.path.join('build', project['board'])
    if 'libnola' in config and os.path.exists(build_dir):
        # If in development mode, always clean before make.
        shutil.rmtree(build_dir)
        
    last_build_context_file = os.path.join(build_dir, 'build.json')
    if os.path.exists(last_build_context_file):
        with open(last_build_context_file) as f:
            last_build_context = json.load(f)
        if 'ver' in last_build_context:
            print(f"* Last used library version: {last_build_context['ver']}")
            if last_build_context['ver'] != current_version and os.path.exists(build_dir):
                shutil.rmtree(build_dir)

    # (Windows) make.exe exists?

    # (Windows) Hardware library development mode? -> not supported.

    # (Non Windows) Hardware library development mode?

    os.makedirs(build_dir, exist_ok=True)

    for srcfile in glob.glob(os.path.join(repo_dir, project['board'], '*.bin')):
        shutil.copy(srcfile, build_dir)

    for srcfile in glob.glob(os.path.join(repo_dir, project['board'], '*.hex')):
        shutil.copy(srcfile, build_dir)

    command_args = ['make', '--no-print-directory',
                    '-C', build_dir,
                    '-f', os.path.join(repo_dir, 'make', 'Makefile')]

    if 'options' in project:
        print(f"* Project options: {project['options']}")
        command_args += project['options'].split(' ')

    if 'def' in project:
        for d in project['def'].split(' '):
            d = d.split('=')
            if d[0] in ['NOLA_VER_MAJOR', 'NOLA_VER_MINOR', 'NOLA_VER_PATCH']:
                print(f"* User definition '{d[0]}' cannot be used.", file=sys.stderr)
                return False
        print(f"* User definitions: {project['def']}")
        definitions = project['def'] + ' '
    else:
        definitions = ''

    current_versions = current_version.split('.')
    command_args.append(f"DEF={definitions}NOLA_VER_MAJOR={current_versions[0]} NOLA_VER_MINOR={current_versions[1]} NOLA_VER_PATCH={current_versions[2]}")

    env = os.environ
    env['PWD'] = os.path.join(repo_dir, 'make')
    env['BOARD'] = project['board']
    env['PORT'] = 'None'
    
    make_process = subprocess.Popen(command_args,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    env=env)
    os.set_blocking(make_process.stdout.fileno(), False)
    os.set_blocking(make_process.stderr.fileno(), False)
    while True:
        output = make_process.stdout.readline()
        if len(output) > 0:
            print(output.decode(), end='')
        error = make_process.stderr.readline()
        if len(error) > 0:
            print(error.decode(), end='', file=sys.stderr)
        ret_code = make_process.poll()
        if ret_code is not None:
            break

    return True if ret_code == 0 else False
