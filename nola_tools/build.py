import sys
import os
import json
import shutil
import glob
import subprocess
import platform
import time
import locale
from queue import Queue, Empty
from threading import Thread
from .repo import get_current_version
from .utils import config_file

ON_POSIX = 'posix' in sys.builtin_module_names

def supported_boards(repo_dir):
    for d in os.listdir(repo_dir):
        if os.path.isdir(os.path.join(repo_dir, d)) and d not in ['include', 'make', 'tools', '.git']:
            yield d

def run_process(command, env):
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               env=env,
                               close_fds=ON_POSIX)

    def enqueue(out, queue):
        for line in iter(out.readline, b''):
            queue.put(line)
        out.close()

    q_out = Queue()
    t_out = Thread(target=enqueue, args=(process.stdout, q_out))
    t_out.daemon = True
    t_out.start()
        
    q_err = Queue()
    t_err = Thread(target=enqueue, args=(process.stderr, q_err))
    t_err.daemon = True
    t_err.start()
        
    while True:
        try:
            line = q_out.get_nowait()
            if line:
                print(line.decode(locale.getpreferredencoding()).rstrip())
        except Empty:
            pass

        try:
            line = q_err.get_nowait()
            if line:
                print(line.decode(locale.getpreferredencoding()).rstrip())
        except Empty:
            pass

        ret_code = process.poll()
        if ret_code is not None:
            return ret_code

def build(config, board=None):
    if os.path.exists('Nol.A-project.json') == False:
        print("* Do 'build' under the Nol.A project directory.", file=sys.stderr)
        print("* If you want to start a new project, use 'new' command.", file=sys.stderr)
        return False

    project = config_file.load("Nol.A-project.json")

    if board is not None:
        project['board'] = board

    if 'libnola' in config:
        if config['libnola'].startswith('wsl://'):
            sep = config['libnola'][6:].find('/')
            dist = config['libnola'][6:6+sep]
            src_dir = config['libnola'][6+sep:]

            command = ['wsl', '-d', dist, 'python3', '-m', 'nola_tools.__init__', f"devmode={src_dir}"]
            with subprocess.Popen(command,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  env=os.environ,
                                  close_fds=ON_POSIX) as p:
                ret_code = p.wait()

            cwd = os.getcwd()
            cwd_wsl = "/mnt/" + cwd[0].lower() + cwd[2:].replace("\\", "/")
            print(cwd_wsl)
            
            command = ['wsl', '-d', dist, '--cd', cwd_wsl, 'python3', '-u', '-m', 'nola_tools.__init__', 'build']
        else:
            command = ['make', '-C', config['libnola'], f"TARGET={project['board']}", "SKIP_BUILD_TEST=1"]

        ret_code = run_process(command, os.environ)
 
        if config['libnola'].startswith('wsl://'):
            return ret_code
        
        if ret_code != 0:
            print(f"* Building libnola failed ({ret_code})", file=sys.stderr)
            return False
        
        repo_dir = os.path.join(config['libnola'], 'nola-sdk')
    else:
        repo_dir = os.path.join(os.path.expanduser('~'), '.nola', 'repo')

    return build_common(repo_dir, config, project)

def build_common(repo_dir, config, project, port=None):
    if project['board'] not in supported_boards(repo_dir):
        print(f"* The board '{project['board']}' not supported.", file=sys.stderr)
        boards = list(supported_boards())
        print(f"* Avilable boards: {boards}", file=sys.stderr)
        return False

    print(f"* Target board: {project['board']}")
    with open("Nol.A-project.json", 'w', encoding='utf-8') as f:
        json.dump(project, f, indent=4)

    current_version = get_current_version(repo_dir) + '(dev)' if 'libnola' in config else ''
    print(f"* Current version: {current_version}")

    build_dir = os.path.join('build', project['board'])
    if 'libnola' in config and os.path.exists(build_dir):
        # If in development mode, always clean before make.
        shutil.rmtree(build_dir)

    last_build_context = config_file.load(os.path.join(build_dir, 'build.json'))

    if 'ver' in last_build_context:
        print(f"* Last used library version: {last_build_context['ver']}")
        if last_build_context['ver'] != current_version and os.path.exists(build_dir):
            shutil.rmtree(build_dir)

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
    command_args.append(f"DEF={definitions}NOLA_VER_MAJOR={current_versions[0]} NOLA_VER_MINOR={current_versions[1]} NOLA_VER_PATCH={current_versions[2].split('(')[0]}")

    env = os.environ
    env['PWD'] = os.path.join(repo_dir, 'make')
    env['BOARD'] = project['board']
    env['PORT'] = 'None' if port is None else port

    ret_code = run_process(command_args, env)

    last_build_context['ver'] = current_version
    config_file.save(last_build_context, os.path.join(build_dir, 'build.json'))
    
    return ret_code == 0

def flash(config, interface=None):
    if os.path.exists('Nol.A-project.json') == False:
        print("* Do 'build' under the Nol.A project directory.", file=sys.stderr)
        print("* If you want to start a new project, use 'new' command.", file=sys.stderr)
        return False

    project = config_file.load("Nol.A-project.json")

    if project.get('board') is None:
        print("* No board is configured. If you want to start a new project, use 'new' command.", file=sys.stderr)
        return False

    build_dir = os.path.join('build', project['board'])
    if os.path.exists(build_dir) == False:
        print("* Do 'build' first.", file=sys.stderr)
        return False

    last_build_context = config_file.load(os.path.join(build_dir, 'build.json'))

    if interface is None:
        interface = last_build_context.get('interface')

    if interface is None:
        print("* No interface is specified. Use 'flash={interface name}'.", file=sys.stderr)
        return False

    repo_dir = os.path.join(os.path.expanduser('~'), '.nola', 'repo')

    success = build_common(repo_dir, config, project, interface)
    if success:
        last_build_context['interface'] = interface
        config_file.save(last_build_context, os.path.join(build_dir, 'build.json'))
    else:
        os.remove(os.path.join(build_dir, 'build.json'))
    return success
