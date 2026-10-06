"""Shell: barcha bosqichlarni birlashtiradi.

Asosiy sikl — REPL (Read-Eval-Print Loop):

    1. READ  — foydalanuvchidan qator o'qing.
    2. EVAL  — lexer -> parser -> executor.
    3. PRINT — natija ekranga chiqadi (dasturlar o'zi chiqaradi).
    4. LOOP  — 1-qadamga qayting.
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
    # readline: strelka tugmalari, tarix (↑ ↓) va Tab bilan to'ldirish.
    import readline
except ImportError:  # Windows'da readline yo'q.
    readline = None

HISTORY_FILE = os.path.expanduser("~/.pysh_history")
HISTORY_LIMIT = 1000


class Shell:
    def __init__(self, interactive: bool = False):
        self.interactive = interactive
        self.last_status = 0          # $? qiymati.
        self.history: list[str] = []  # `history` buyrug'i uchun.
        self.executor = Executor(self)
        self._path_commands: list[str] | None = None  # Tab uchun kesh.

    # ------------------------------------------------------------------
    # Asosiy API
    # ------------------------------------------------------------------

    def lookup_var(self, name: str) -> str:
        """O'zgaruvchi qiymatini qaytaring. Expander bu funksiyani chaqiradi."""
        if name == "?":
            return str(self.last_status)
        if name == "$":
            return str(os.getpid())
        if name == "0":
            return "pysh"
        return os.environ.get(name, "")

    def run_line(self, line: str) -> int:
        """Bitta qatorni bajaring va exit kodni qaytaring."""
        try:
            tokens = tokenize(line)   # 1-bosqich
            tree = parse(tokens)      # 2-bosqich
        except ShellError as exc:
            error(str(exc))
            self.last_status = 2      # 2 = sintaksis xatosi (bash qoidasi).
            return self.last_status

        if not tree.items:
            return self.last_status   # Bo'sh qator yoki faqat izoh.

        # 3 va 4-bosqichlar executor ichida.
        self.last_status = self.executor.run_list(tree)
        return self.last_status

    def run_lines(self, lines: Iterable[str]) -> int:
        """Ko'p qatorni ketma-ket bajaring (skript yoki stdin)."""
        for line in lines:
            self.run_line(line.rstrip("\n"))
        return self.last_status

    def run_file(self, path: str) -> int:
        """Skript faylini bajaring. `#!` qatori izoh sifatida o'tkaziladi."""
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
    # Interaktiv rejim (REPL)
    # ------------------------------------------------------------------

    def repl(self) -> int:
        """Interaktiv siklni ishga tushiring. ShellExit uni to'xtatadi."""
        self._setup_readline()
        print(f"pysh {__version__}. Yordam: help. Chiqish: exit yoki Ctrl+D.")
        try:
            while True:
                try:
                    line = input(self._prompt())
                except EOFError:       # Ctrl+D
                    print()
                    break
                except KeyboardInterrupt:  # Ctrl+C: qatorni bekor qiling.
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
        """Taklif satrini yasang. Misol: pysh:~/code$"""
        cwd = os.getcwd()
        home = os.environ.get("HOME", "")
        if home and (cwd == home or cwd.startswith(home + os.sep)):
            cwd = "~" + cwd[len(home):]

        if os.environ.get("NO_COLOR"):
            return f"pysh:{cwd}$ "

        # \001 va \002 readline'ga aytadi: "bu belgilar ekranda joy egallamaydi".
        # Ularsiz uzun qatorlarda kursor noto'g'ri joyga o'tadi.
        def color(code: str, text: str) -> str:
            return f"\001\033[{code}m\002{text}\001\033[0m\002"

        # Oxirgi buyruq xato bersa, "$" qizil bo'ladi.
        sign = color("31", "$") if self.last_status else "$"
        return f"{color('1;32', 'pysh')}:{color('1;34', cwd)}{sign} "

    def _setup_readline(self) -> None:
        if not readline:
            return
        try:
            readline.read_history_file(HISTORY_FILE)
        except OSError:
            pass  # Birinchi ishga tushirish: fayl hali yo'q.
        readline.set_history_length(HISTORY_LIMIT)
        self.history = [
            readline.get_history_item(i)
            for i in range(1, readline.get_current_history_length() + 1)
        ]

        readline.set_completer(self._complete)
        readline.set_completer_delims(" \t\n;|&<>")
        # macOS Python ko'pincha GNU readline o'rniga libedit ishlatadi.
        # Ularda Tab tugmasini sozlash buyrug'i har xil.
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
        """Tab bosilganda readline bu funksiyani chaqiradi.

        state=0, 1, 2... — readline variantlarni bittadan so'raydi.
        Variant tugasa, None qaytaring.
        """
        if state == 0:
            before = readline.get_line_buffer()[:readline.get_begidx()]
            # Birinchi so'z (yoki | ; && dan keyingi so'z) — buyruq nomi.
            if not before.strip() or before.rstrip()[-1] in "|;&":
                self._matches = [c for c in self._all_commands() if c.startswith(text)]
            else:
                self._matches = self._complete_path(text)
        return self._matches[state] if state < len(self._matches) else None

    def _all_commands(self) -> list[str]:
        """Builtin'lar va PATH ichidagi barcha dasturlar."""
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
        """Fayl va papka nomlarini to'ldiring. Papkaga "/" qo'shing."""
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
    """stdin va stdout terminalmi? Unda REPL'ni ishga tushiring."""
    return sys.stdin.isatty() and sys.stdout.isatty()
