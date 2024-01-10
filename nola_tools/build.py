import sys
import os
import json
import shutil
import glob
import subprocess
import platform
import time
import locale
from pbr.version import VersionInfo
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
                try:
                    print(line.decode(locale.getpreferredencoding()).rstrip())
                except UnicodeDecodeError:
                    print(line)
        except Empty:
            pass

        try:
            line = q_err.get_nowait()
            if line:
                try:
                    print(line.decode(locale.getpreferredencoding()).rstrip())
                except UnicodeDecodeError:
                    print(line)
        except Empty:
            pass

        ret_code = process.poll()
        if ret_code is not None:
            return ret_code

def build(config, board=None, interface=None):
    if os.path.exists('Nol.A-project.json') == False:
        print("* The Nol.A project file is not found.", file=sys.stderr)
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

    if project['board'] not in supported_boards(repo_dir):
        print(f"* The board '{project['board']}' not supported.", file=sys.stderr)
        boards = list(supported_boards(repo_dir))
        print(f"* Avilable boards: {boards}", file=sys.stderr)
        return False

    print(f"* Target board: {project['board']}")
    with open("Nol.A-project.json", 'w', encoding='utf-8') as f:
        json.dump(project, f, indent=4)

    project_version = get_current_version('.')
    if project_version is None:
        print(f"* Project version: unknown")
    else:
        print(f"* Project version: {project_version['describe']}")
    
    libnola_version = get_current_version(repo_dir)
    print(f"* libnola version: {libnola_version['describe']}{' (dev)' if 'libnola' in config else ''}")

    build_dir = os.path.join('build', project['board'])
    if 'libnola' in config and os.path.exists(build_dir):
        # If in development mode, always clean before make.
        shutil.rmtree(build_dir)

    last_build_context = config_file.load(os.path.join(build_dir, 'build.json'))

    if 'ver' in last_build_context:
        print(f"* Last used library version: {last_build_context['ver']}")
        if last_build_context['ver'] != libnola_version and os.path.exists(build_dir):
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
            if d[0] in ['NOLA_VER_MAJOR',
                        'NOLA_VER_MINOR',
                        'NOLA_VER_PATCH',
                        'NOLA_VER_COMMIT',
                        'NOLA_VER_DIRTY',
                        'PROJ_VER_MAJOR',
                        'PROJ_VER_MINOR',
                        'PROJ_VER_PATCH',
                        'PROJ_VER_COMMIT',
                        'PROJ_VER_DIRTY']:
                print(f"* User definition '{d[0]}' cannot be used.", file=sys.stderr)
                return False
        print(f"* User definitions: {project['def']}")
        definitions = project['def'] + ' '
    else:
        definitions = ''

    d = "DEF=" + definitions
    d += f" NOLA_VER_MAJOR={libnola_version['major']}"
    d += f" NOLA_VER_MINOR={libnola_version['minor']}"
    d += f" NOLA_VER_PATCH={libnola_version['patch']}"
    d += f" NOLA_VER_COMMIT=0x{libnola_version['commit']}"
    d += f" NOLA_VER_DIRTY={1 if libnola_version['dirty'] else 0}"

    if project_version is not None:
        d += f" PROJ_VER_MAJOR={project_version['major']}"
        d += f" PROJ_VER_MINOR={project_version['minor']}"
        d += f" PROJ_VER_PATCH={project_version['patch']}"
        d += f" PROJ_VER_COMMIT=0x{project_version['commit']}"
        d += f" PROJ_VER_DIRTY={1 if project_version['dirty'] else 0}"
        
    command_args.append(d)

    if interface is not None and interface.upper() == 'LAST':
        interface = last_build_context.get('interface')
    
    print(f"* Flash interface: {interface}")

    env = os.environ
    env['PWD'] = os.path.join(repo_dir, 'make')
    env['BOARD'] = project['board']
    if interface is not None:
        env['PORT'] = str(interface)
    env['NOLA_CLI'] = VersionInfo('nola_tools').release_string()

    paths = config.get('path')
    if type(paths) is dict:
        if paths.get('stm32cube') is not None:
            env['PATH_STM32CUBE'] = paths.get('stm32cube')
        if paths.get('jlink') is not None:
            env['PATH_JLINK'] = paths.get('jlink')

    ret_code = run_process(command_args, env)

    last_build_context['ver'] = libnola_version
    if interface is not None:
        last_build_context['interface'] = interface
    config_file.save(last_build_context, os.path.join(build_dir, 'build.json'))
    
    return ret_code == 0

def clean():
    if os.path.exists('Nol.A-project.json') == False:
        print("* The Nol.A project file is not found.", file=sys.stderr)
        print("* If you want to start a new project, use 'new' command.", file=sys.stderr)
        return False

    if os.path.exists('build') == True:
        shutil.rmtree('build')
    
    return True
