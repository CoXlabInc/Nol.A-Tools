all = ('__version__')

from pbr.version import VersionInfo

# Check the PBR version module docs for other options than release_string()
__version__ = VersionInfo('nola_tools').release_string()

import argparse
import sys

def info():
    print("* This is info")
    # TODO Read Nol.A-project.json.
    return 0

def main():
    parser = argparse.ArgumentParser(description=f"Nol.A-SDK Command Line Interface version {__version__}")
    parser.add_argument('command', nargs='?', help='info')
    args = parser.parse_args()

    if args.command is None:
        print("* A command must be specified.", file=sys.stderr)
        parser.print_help()
        return 1
    elif args.command == "info":
        return info()
    else:
        print("* Unknown command", file=sys.stderr)
        parser.print_help()
        return 2

if __name__ == '__main__':
    main()
