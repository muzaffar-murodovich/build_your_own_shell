"""4-bosqich: Executor (bajaruvchi).

Bu shell'ning yuragi. Bu yerda 4 ta asosiy Unix tizim chaqiruvi ishlaydi:

    fork()    — joriy jarayondan nusxa yarating (bola jarayon).
    exec()    — bola jarayon ichida boshqa dasturni ishga tushiring.
                Jarayon kodi butunlay almashadi. Qaytish yo'q.
    pipe()    — ikki uchli "quvur" yarating: biri yozadi, biri o'qiydi.
    dup2(a,b) — b fayl deskriptorini a ga yo'naltiring.

Fayl deskriptor (fd) — ochiq fayl raqami. Har jarayonda 3 tasi bor:
    0 = stdin (kirish), 1 = stdout (chiqish), 2 = stderr (xatolar).

`ls | wc -l` bajarilishi:

    shell ── pipe() ──> [o'qish uchi r]  [yozish uchi w]
      │
      ├─ fork() ─> bola 1: dup2(w, 1);  exec("ls")    # stdout -> quvur
      ├─ fork() ─> bola 2: dup2(r, 0);  exec("wc")    # stdin  <- quvur
      │
      └─ waitpid() ikkala bolani kutadi.
"""

import os
import re
import signal
import sys
from typing import TYPE_CHECKING

from .builtins import BUILTINS
from .errors import ShellError, ShellExit, describe_os_error, error
from .expand import Lookup, expand_single, expand_words
from .parser import Command, CommandList, Pipeline, Redirect

if TYPE_CHECKING:
    from .shell import Shell

# Redirect operatori -> (qaysi fd, fayl ochish bayroqlari).
_WRITE = os.O_WRONLY | os.O_CREAT
REDIRECT_TABLE = {
    "<":   (0, os.O_RDONLY),
    ">":   (1, _WRITE | os.O_TRUNC),   # TRUNC: faylni tozalang.
    ">>":  (1, _WRITE | os.O_APPEND),  # APPEND: oxiriga qo'shing.
    "2>":  (2, _WRITE | os.O_TRUNC),
    "2>>": (2, _WRITE | os.O_APPEND),
}

# NOM=qiymat ko'rinishidagi so'z.
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def apply_redirects(redirects: list[Redirect], lookup: Lookup) -> None:
    """Redirect'larni joriy jarayonga qo'llang (dup2 orqali)."""
    for redirect in redirects:
        if redirect.op == "2>&1":
            os.dup2(1, 2)  # stderr endi stdout boradigan joyga boradi.
            continue
        path = expand_single(redirect.target, lookup)
        target_fd, flags = REDIRECT_TABLE[redirect.op]
        fd = os.open(path, flags, 0o644)  # 0o644: rw-r--r-- huquqlari.
        os.dup2(fd, target_fd)
        os.close(fd)  # Nusxa bor. Asl fd endi kerak emas.


def exit_code_from_wait(status: int) -> int:
    """waitpid() natijasini exit kodga aylantiring.

    Jarayon signal bilan o'ldirilsa (masalan, Ctrl+C = SIGINT = 2),
    shell'lar 128 + signal raqamini qaytaradi: 128 + 2 = 130.
    """
    code = os.waitstatus_to_exitcode(status)
    return 128 - code if code < 0 else code


class Executor:
    def __init__(self, shell: "Shell"):
        self.shell = shell

    def run_list(self, command_list: CommandList) -> int:
        """`a && b || c ; d` kabi ro'yxatni bajaring."""
        status = self.shell.last_status
        for op, pipeline in command_list.items:
            # && : oldingisi xato bersa, o'tkazib yuboring.
            # || : oldingisi muvaffaqiyatli bo'lsa, o'tkazib yuboring.
            if op == "&&" and status != 0:
                continue
            if op == "||" and status == 0:
                continue
            status = self.run_pipeline(pipeline)
            # $? keyingi buyruqda yangi qiymatni ko'rsatsin.
            self.shell.last_status = status
            # Foydalanuvchi Ctrl+C bosdi: qatorning qolganini bajarmang (bash kabi).
            if status == 128 + signal.SIGINT:
                if self.shell.interactive:
                    print()  # "^C" dan keyin prompt yangi qatordan boshlansin.
                break
        return status

    def run_pipeline(self, pipeline: Pipeline) -> int:
        commands = pipeline.commands

        # Bitta builtin buyruq shell jarayonining O'ZIDA bajariladi.
        # Aks holda `cd` ishlamaydi (builtins.py izohiga qarang).
        if len(commands) == 1:
            command = commands[0]
            try:
                argv = expand_words(command.argv, self.shell.lookup_var)
            except ShellError as exc:
                error(str(exc))
                return 1

            # NOM=qiymat: o'zgaruvchi o'rnating.
            # Soddalashtirish: biz uni darhol muhitga (export) yozamiz.
            if len(argv) == 1 and ASSIGNMENT.match(argv[0]):
                name, _, value = argv[0].partition("=")
                os.environ[name] = value
                return 0

            if not argv or argv[0] in BUILTINS:
                return self._run_in_shell(argv, command.redirects)

        # Tashqi dastur yoki pipe: fork() kerak.
        return self._run_forked(commands)

    def _run_in_shell(self, argv: list[str], redirects: list[Redirect]) -> int:
        """Builtin'ni fork'siz bajaring.

        Muammo: `pwd > f.txt` redirect'i shell'ning o'z stdout'ini o'zgartiradi.
        Yechim: avval 0, 1, 2 fd'larning nusxasini saqlang.
        Builtin tugagach, ularni qayta tiklang.
        """
        sys.stdout.flush()
        sys.stderr.flush()
        saved = [os.dup(fd) for fd in (0, 1, 2)]
        try:
            apply_redirects(redirects, self.shell.lookup_var)
            if not argv:
                return 0  # Faqat redirect: `> bo'sh.txt` faylni yaratadi.
            return BUILTINS[argv[0]](self.shell, argv[1:])
        except ShellError as exc:
            error(str(exc))
            return 1
        except OSError as exc:
            error(describe_os_error(exc))
            return 1
        finally:
            # Python bufferini eski fd yopilishidan oldin yozing.
            sys.stdout.flush()
            sys.stderr.flush()
            for fd, copy in enumerate(saved):
                os.dup2(copy, fd)
                os.close(copy)

    def _run_forked(self, commands: list[Command]) -> int:
        """Har bir buyruq uchun fork() qiling va ularni pipe bilan ulang."""
        # Fork'dan oldin bufferni yozing. Aks holda bola jarayon
        # shell bufferidagi matnni ham nusxalaydi va ikki marta chiqaradi.
        sys.stdout.flush()
        sys.stderr.flush()

        # Ctrl+C bola jarayonni to'xtatsin, shell'ni emas.
        # Shuning uchun shell SIGINT'ni vaqtincha e'tiborsiz qoldiradi.
        old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        pids: list[int] = []
        prev_read: int | None = None  # Oldingi quvurning o'qish uchi.
        try:
            for index, command in enumerate(commands):
                is_last = index == len(commands) - 1
                read_end, write_end = (None, None) if is_last else os.pipe()

                pid = os.fork()
                if pid == 0:
                    # Bola jarayon. Bu funksiya hech qachon qaytmaydi.
                    self._child(command, stdin_fd=prev_read,
                                stdout_fd=write_end, unused_fd=read_end)

                # Ota jarayon (shell).
                pids.append(pid)
                # Bola fd'larni oldi. Shell'da ularni yoping.
                # Muhim: yozish uchi ochiq qolsa, o'quvchi hech qachon
                # EOF (fayl oxiri) ko'rmaydi va abadiy kutadi.
                if prev_read is not None:
                    os.close(prev_read)
                if write_end is not None:
                    os.close(write_end)
                prev_read = read_end

            # Hamma bolani kuting. Pipeline kodi = oxirgi buyruq kodi.
            status = 0
            for pid in pids:
                _, wait_status = os.waitpid(pid, 0)
                status = exit_code_from_wait(wait_status)
            return status
        finally:
            signal.signal(signal.SIGINT, old_handler)

    def _child(self, command: Command, stdin_fd: int | None,
               stdout_fd: int | None, unused_fd: int | None) -> None:
        """Bola jarayonda ishlaydi. Oxirida exec() yoki os._exit() bo'ladi."""
        code = 1
        try:
            # Bola Ctrl+C'ga oddiy reaksiya qilsin (to'xtasin).
            signal.signal(signal.SIGINT, signal.SIG_DFL)

            # Quvur uchlarini stdin/stdout'ga ulang.
            if unused_fd is not None:
                os.close(unused_fd)
            if stdin_fd is not None:
                os.dup2(stdin_fd, 0)
                os.close(stdin_fd)
            if stdout_fd is not None:
                os.dup2(stdout_fd, 1)
                os.close(stdout_fd)

            # Redirect'lar pipe'dan keyin qo'llanadi: `ls | wc > f` to'g'ri ishlaydi.
            apply_redirects(command.redirects, self.shell.lookup_var)

            argv = expand_words(command.argv, self.shell.lookup_var)
            if not argv:
                code = 0
            elif argv[0] in BUILTINS:
                # Pipe ichidagi builtin: `history | grep ls`.
                code = BUILTINS[argv[0]](self.shell, argv[1:])
            else:
                code = self._exec(argv)
        except ShellExit as exc:
            code = exc.code
        except ShellError as exc:
            error(str(exc))
        except OSError as exc:
            error(describe_os_error(exc))
        except BaseException:
            pass
        finally:
            # os._exit() Python tozalash kodini o'tkazib yuboradi.
            # Bola jarayon uchun bu to'g'ri: u shell'ning atexit'larini bajarmasin.
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except OSError:
                pass
            os._exit(code)

    @staticmethod
    def _exec(argv: list[str]) -> int:
        """Dasturni ishga tushiring. Muvaffaqiyatli bo'lsa, hech qachon qaytmaydi.

        execvp() dasturni PATH ichidagi papkalardan qidiradi.
        Topsa, joriy jarayon kodini o'sha dastur kodi bilan almashtiradi.
        """
        try:
            os.execvp(argv[0], argv)
        except FileNotFoundError:
            error(f"{argv[0]}: buyruq topilmadi")
            return 127  # Unix qoidasi: 127 = buyruq topilmadi.
        except PermissionError:
            error(f"{argv[0]}: ruxsat yo'q")
            return 126  # 126 = topildi, lekin bajarib bo'lmaydi.
        return 1  # Bu qatorga hech qachon yetib kelinmaydi.
