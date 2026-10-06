"""CLI — the command-line interface.

pysh works in 4 modes:

    pysh                   interactive mode (REPL)
    pysh -c "ls | wc -l"   run one command and exit
    pysh script.sh         run a script file
    echo "ls" | pysh       read the commands from stdin
"""

import argparse
import sys

from . import __version__
from .errors import ShellExit
from .shell import Shell, is_interactive_terminal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pysh",
        description="pysh — a simple Unix shell written in Python.",
        epilog="Example: pysh -c 'ls -l | grep py > result.txt'",
    )
    parser.add_argument(
        "-c", dest="command", metavar="COMMAND",
        help="run this command and exit",
    )
    parser.add_argument(
        "script", nargs="?",
        help="a script file to run",
    )
    parser.add_argument(
        "--version", action="version", version=f"pysh {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """The entry point. Returns the exit code."""
    args = build_parser().parse_args(argv)

    interactive = args.command is None and args.script is None and is_interactive_terminal()
    shell = Shell(interactive=interactive)

    try:
        if args.command is not None:
            # The -c value can have more than one line.
            return shell.run_lines(args.command.splitlines())
        if args.script is not None:
            return shell.run_file(args.script)
        if interactive:
            return shell.repl()
        return shell.run_lines(sys.stdin)
    except ShellExit as exc:
        # The `exit` command stops the shell in all modes.
        return exc.code
