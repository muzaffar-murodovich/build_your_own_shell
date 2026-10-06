"""CLI — buyruq qatori interfeysi.

pysh 4 xil rejimda ishlaydi:

    pysh                   interaktiv rejim (REPL)
    pysh -c "ls | wc -l"   bitta buyruqni bajaring va chiqing
    pysh script.sh         skript faylini bajaring
    echo "ls" | pysh       stdin'dan buyruqlarni o'qing
"""

import argparse
import sys

from . import __version__
from .errors import ShellExit
from .shell import Shell, is_interactive_terminal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pysh",
        description="pysh — Python'da yozilgan oddiy Unix shell.",
        epilog="Misol: pysh -c 'ls -l | grep py > natija.txt'",
    )
    parser.add_argument(
        "-c", dest="command", metavar="BUYRUQ",
        help="bu buyruqni bajaring va chiqing",
    )
    parser.add_argument(
        "script", nargs="?",
        help="bajarish uchun skript fayli",
    )
    parser.add_argument(
        "--version", action="version", version=f"pysh {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Kirish nuqtasi. Exit kodni qaytaradi."""
    args = build_parser().parse_args(argv)

    interactive = args.command is None and args.script is None and is_interactive_terminal()
    shell = Shell(interactive=interactive)

    try:
        if args.command is not None:
            # -c qiymatida bir nechta qator bo'lishi mumkin.
            return shell.run_lines(args.command.splitlines())
        if args.script is not None:
            return shell.run_file(args.script)
        if interactive:
            return shell.repl()
        return shell.run_lines(sys.stdin)
    except ShellExit as exc:
        # `exit` buyrug'i istalgan rejimda shell'ni to'xtatadi.
        return exc.code
