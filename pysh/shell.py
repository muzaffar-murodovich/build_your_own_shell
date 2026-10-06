"""Shell: connects all the stages.

The main loop is a REPL (Read-Eval-Print Loop):

    1. READ  — read a line from the user.
    2. EVAL  — lexer -> parser -> executor.
    3. PRINT — the result goes to the screen (the programs print it themselves).
    4. LOOP  — go back to step 1.
"""

import os
import sys
from collections.abc import Iterable

from . import __version__
from .builtins import BUILTINS
from .errors import ShellError, error
from .executor import Executor
from .lexer import tokenize
from .parser import parse

try:
    # readline: arrow keys, history (↑ ↓) and Tab completion.
    import readline
except ImportError:  # Windows does not have readline.
    readline = None

HISTORY_FILE = os.path.expanduser("~/.pysh_history")
HISTORY_LIMIT = 1000


class Shell:
    def __init__(self, interactive: bool = False):
        self.interactive = interactive
        self.last_status = 0          # The value of $?.
        self.history: list[str] = []  # For the `history` command.
        self.executor = Executor(self)
        self._path_commands: list[str] | None = None  # A cache for Tab.

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def lookup_var(self, name: str) -> str:
        """Return the value of a variable. The expander calls this function."""
        if name == "?":
            return str(self.last_status)
        if name == "$":
            return str(os.getpid())
        if name == "0":
            return "pysh"
        return os.environ.get(name, "")

    def run_line(self, line: str) -> int:
        """Run one line and return the exit code."""
        try:
            tokens = tokenize(line)   # Stage 1
            tree = parse(tokens)      # Stage 2
        except ShellError as exc:
            error(str(exc))
            self.last_status = 2      # 2 = syntax error (bash rule).
            return self.last_status

        if not tree.items:
            return self.last_status   # An empty line or only a comment.

        # Stages 3 and 4 are inside the executor.
        self.last_status = self.executor.run_list(tree)
        return self.last_status

    def run_lines(self, lines: Iterable[str]) -> int:
        """Run many lines one after the other (a script or stdin)."""
        for line in lines:
            self.run_line(line.rstrip("\n"))
        return self.last_status

    def run_file(self, path: str) -> int:
        """Run a script file. The lexer skips the `#!` line as a comment."""
        try:
            with open(path, encoding="utf-8") as file:
                return self.run_lines(file)
        except OSError as exc:
            error(f"{path}: {exc.strerror}")
            return 127

    def clear_history(self) -> None:
        self.history.clear()
        if readline:
            readline.clear_history()

    # ------------------------------------------------------------------
    # Interactive mode (REPL)
    # ------------------------------------------------------------------

    def repl(self) -> int:
        """Start the interactive loop. ShellExit stops it."""
        self._setup_readline()
        print(f"pysh {__version__}. Type help for help. Type exit or press Ctrl+D to quit.")
        try:
            while True:
                try:
                    line = input(self._prompt())
                except EOFError:       # Ctrl+D
                    print()
                    break
                except KeyboardInterrupt:  # Ctrl+C: cancel the line.
                    print()
                    self.last_status = 130
                    continue

                if line.strip():
                    self.history.append(line)
                self.run_line(line)
        finally:
            self._save_history()
        return self.last_status

    def _prompt(self) -> str:
        """Make the prompt. Example: pysh:~/code$"""
        cwd = os.getcwd()
        home = os.environ.get("HOME", "")
        if home and (cwd == home or cwd.startswith(home + os.sep)):
            cwd = "~" + cwd[len(home):]

        if os.environ.get("NO_COLOR"):
            return f"pysh:{cwd}$ "

        # \001 and \002 tell readline: "these characters use no space on the screen".
        # Without them, the cursor moves to an incorrect position on long lines.
        def color(code: str, text: str) -> str:
            return f"\001\033[{code}m\002{text}\001\033[0m\002"

        # If the last command failed, the "$" is red.
        sign = color("31", "$") if self.last_status else "$"
        return f"{color('1;32', 'pysh')}:{color('1;34', cwd)}{sign} "

    def _setup_readline(self) -> None:
        if not readline:
            return
        try:
            readline.read_history_file(HISTORY_FILE)
        except OSError:
            pass  # First start: the file does not exist yet.
        readline.set_history_length(HISTORY_LIMIT)
        self.history = [
            readline.get_history_item(i)
            for i in range(1, readline.get_current_history_length() + 1)
        ]

        readline.set_completer(self._complete)
        readline.set_completer_delims(" \t\n;|&<>")
        # On macOS, Python frequently uses libedit, not GNU readline.
        # They use different commands to set the Tab key.
        if "libedit" in (readline.__doc__ or ""):
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")

    def _save_history(self) -> None:
        if readline:
            try:
                readline.write_history_file(HISTORY_FILE)
            except OSError:
                pass

    def _complete(self, text: str, state: int) -> str | None:
        """When you push Tab, readline calls this function.

        state=0, 1, 2... — readline asks for the options one at a time.
        When there are no more options, return None.
        """
        if state == 0:
            before = readline.get_line_buffer()[:readline.get_begidx()]
            # The first word (or the word after | ; &&) is a command name.
            if not before.strip() or before.rstrip()[-1] in "|;&":
                self._matches = [c for c in self._all_commands() if c.startswith(text)]
            else:
                self._matches = self._complete_path(text)
        return self._matches[state] if state < len(self._matches) else None

    def _all_commands(self) -> list[str]:
        """The builtins and all programs in PATH."""
        if self._path_commands is None:
            names = set(BUILTINS)
            for folder in os.environ.get("PATH", "").split(os.pathsep):
                try:
                    names.update(os.listdir(folder))
                except OSError:
                    continue
            self._path_commands = sorted(names)
        return self._path_commands

    @staticmethod
    def _complete_path(text: str) -> list[str]:
        """Complete file and directory names. Add "/" to a directory."""
        folder, prefix = os.path.split(text)
        real_folder = os.path.expanduser(folder) or "."
        try:
            entries = os.listdir(real_folder)
        except OSError:
            return []
        result = []
        for name in sorted(entries):
            if name.startswith(prefix):
                full = os.path.join(folder, name)
                if os.path.isdir(os.path.join(real_folder, name)):
                    full += "/"
                result.append(full)
        return result


def is_interactive_terminal() -> bool:
    """Are stdin and stdout a terminal? If yes, start the REPL."""
    return sys.stdin.isatty() and sys.stdout.isatty()
