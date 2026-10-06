"""Builtin (internal) commands.

A builtin is a command that the shell runs itself. It does not start a new process.

Why MUST `cd` be a builtin?
Each process has its own current directory.
If `cd` is a separate program, it changes only ITS OWN directory
and then stops immediately. The directory of the shell does not change.
`exit` and `export` are builtins for the same reason.

Each builtin function:
    - input:  the shell object and the arguments (without the command name).
    - output: the exit code (0 = success).
"""

import os
import shutil
from collections.abc import Callable
from typing import TYPE_CHECKING

from .errors import ShellExit, error

if TYPE_CHECKING:
    from .shell import Shell

BuiltinFunc = Callable[["Shell", list[str]], int]

# Name -> function. The @builtin decorator fills this dictionary.
BUILTINS: dict[str, BuiltinFunc] = {}


def builtin(name: str):
    """Register the function as a builtin."""
    def register(func: BuiltinFunc) -> BuiltinFunc:
        BUILTINS[name] = func
        return func
    return register


@builtin("cd")
def cd(shell: "Shell", args: list[str]) -> int:
    """cd [dir] — change the current directory. `cd -` goes back to the previous directory."""
    if len(args) > 1:
        error("cd: too many arguments")
        return 1

    target = args[0] if args else os.environ.get("HOME", "/")
    if target == "-":
        target = os.environ.get("OLDPWD", "")
        if not target:
            error("cd: OLDPWD not set")
            return 1
        print(target)

    old = os.getcwd()
    try:
        # The main work is here: ask the OS to change the directory of the shell process.
        os.chdir(target)
    except FileNotFoundError:
        error(f"cd: {target}: no such directory")
        return 1
    except NotADirectoryError:
        error(f"cd: {target}: not a directory")
        return 1
    except PermissionError:
        error(f"cd: {target}: permission denied")
        return 1

    os.environ["OLDPWD"] = old
    os.environ["PWD"] = os.getcwd()
    return 0


@builtin("pwd")
def pwd(shell: "Shell", args: list[str]) -> int:
    """pwd — show the current directory."""
    print(os.getcwd())
    return 0


@builtin("echo")
def echo(shell: "Shell", args: list[str]) -> int:
    """echo [-n] [text...] — print the text. -n: no newline at the end."""
    newline = True
    if args and args[0] == "-n":
        newline = False
        args = args[1:]
    print(" ".join(args), end="\n" if newline else "")
    return 0


@builtin("exit")
def exit_(shell: "Shell", args: list[str]) -> int:
    """exit [code] — stop the shell."""
    if not args:
        raise ShellExit(shell.last_status)
    try:
        raise ShellExit(int(args[0]))
    except ValueError:
        error(f"exit: {args[0]}: numeric argument required")
        raise ShellExit(2)


@builtin("export")
def export(shell: "Shell", args: list[str]) -> int:
    """export NAME=VALUE — set an environment variable. Without arguments: show all of them."""
    if not args:
        for name, value in sorted(os.environ.items()):
            print(f'export {name}="{value}"')
        return 0

    status = 0
    for arg in args:
        name, sep, value = arg.partition("=")
        if not name.isidentifier():
            error(f"export: '{arg}': not a valid identifier")
            status = 1
        elif sep:
            # Write to os.environ. Child processes inherit it.
            os.environ[name] = value
    return status


@builtin("unset")
def unset(shell: "Shell", args: list[str]) -> int:
    """unset NAME... — remove a variable."""
    for name in args:
        os.environ.pop(name, None)
    return 0


@builtin("history")
def history(shell: "Shell", args: list[str]) -> int:
    """history [-c] — show the command history. -c: clear the history."""
    if args == ["-c"]:
        shell.clear_history()
        return 0
    for number, line in enumerate(shell.history, start=1):
        print(f"{number:5}  {line}")
    return 0


@builtin("type")
def type_(shell: "Shell", args: list[str]) -> int:
    """type NAME... — show if a command is a builtin or a file."""
    status = 0
    for name in args:
        if name in BUILTINS:
            print(f"{name} is a shell builtin")
        elif path := shutil.which(name):
            print(f"{name} is {path}")
        else:
            error(f"type: {name}: not found")
            status = 1
    return status


@builtin("help")
def help_(shell: "Shell", args: list[str]) -> int:
    """help — show the help text."""
    print("pysh — a simple shell written in Python.\n")
    print("Builtin commands:")
    for func in BUILTINS.values():
        # The first line of the docstring is a short description.
        print(f"  {func.__doc__.splitlines()[0]}")
    print(
        "\nSyntax:\n"
        "  a | b          pipe: the output of a goes to the input of b\n"
        "  a > f, a >> f  write stdout to a file (>> appends)\n"
        "  a < f          read stdin from a file\n"
        "  a 2> f, 2>&1   send stderr to a file or to stdout\n"
        "  a && b         run b if a succeeds\n"
        "  a || b         run b if a fails\n"
        "  a ; b          run b after a\n"
        "  $VAR ${VAR} $? ~ *.py 'text' \"text\"  — expansion\n"
        "  NAME=value     set a variable"
    )
    return 0
