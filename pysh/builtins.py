"""Builtin (ichki) buyruqlar.

Builtin — shell o'zi bajaradigan buyruq. U yangi jarayon (process) ochmaydi.

Nima uchun `cd` builtin bo'lishi SHART?
Har bir jarayonning o'z joriy papkasi bor.
Agar `cd` alohida dastur bo'lsa, u faqat O'Z papkasini o'zgartiradi
va darhol tugaydi. Shell papkasi o'zgarmaydi.
`exit` va `export` ham shu sababli builtin.

Har bir builtin funksiya:
    - kirish:  shell obyekti va argumentlar (buyruq nomisiz).
    - chiqish: exit kod (0 = muvaffaqiyat).
"""

import os
import shutil
from collections.abc import Callable
from typing import TYPE_CHECKING

from .errors import ShellExit, error

if TYPE_CHECKING:
    from .shell import Shell

BuiltinFunc = Callable[["Shell", list[str]], int]

# Nom -> funksiya. @builtin dekoratori bu lug'atni to'ldiradi.
BUILTINS: dict[str, BuiltinFunc] = {}


def builtin(name: str):
    """Funksiyani builtin sifatida ro'yxatdan o'tkazing."""
    def register(func: BuiltinFunc) -> BuiltinFunc:
        BUILTINS[name] = func
        return func
    return register


@builtin("cd")
def cd(shell: "Shell", args: list[str]) -> int:
    """cd [papka] — joriy papkani o'zgartiring. `cd -` oldingi papkaga qaytadi."""
    if len(args) > 1:
        error("cd: argumentlar juda ko'p")
        return 1

    target = args[0] if args else os.environ.get("HOME", "/")
    if target == "-":
        target = os.environ.get("OLDPWD", "")
        if not target:
            error("cd: OLDPWD o'rnatilmagan")
            return 1
        print(target)

    old = os.getcwd()
    try:
        # Asosiy ish shu yerda: OS'dan shell jarayoni papkasini o'zgartirishni so'rang.
        os.chdir(target)
    except FileNotFoundError:
        error(f"cd: {target}: bunday papka yo'q")
        return 1
    except NotADirectoryError:
        error(f"cd: {target}: papka emas")
        return 1
    except PermissionError:
        error(f"cd: {target}: ruxsat yo'q")
        return 1

    os.environ["OLDPWD"] = old
    os.environ["PWD"] = os.getcwd()
    return 0


@builtin("pwd")
def pwd(shell: "Shell", args: list[str]) -> int:
    """pwd — joriy papkani ko'rsating."""
    print(os.getcwd())
    return 0


@builtin("echo")
def echo(shell: "Shell", args: list[str]) -> int:
    """echo [-n] [matn...] — matnni chiqaring. -n: oxirida yangi qator yo'q."""
    newline = True
    if args and args[0] == "-n":
        newline = False
        args = args[1:]
    print(" ".join(args), end="\n" if newline else "")
    return 0


@builtin("exit")
def exit_(shell: "Shell", args: list[str]) -> int:
    """exit [kod] — shell'ni to'xtating."""
    if not args:
        raise ShellExit(shell.last_status)
    try:
        raise ShellExit(int(args[0]))
    except ValueError:
        error(f"exit: {args[0]}: raqam kerak")
        raise ShellExit(2)


@builtin("export")
def export(shell: "Shell", args: list[str]) -> int:
    """export NOM=QIYMAT — muhit o'zgaruvchisini o'rnating. Argumentsiz: hammasini ko'rsating."""
    if not args:
        for name, value in sorted(os.environ.items()):
            print(f'export {name}="{value}"')
        return 0

    status = 0
    for arg in args:
        name, sep, value = arg.partition("=")
        if not name.isidentifier():
            error(f"export: '{arg}': noto'g'ri nom")
            status = 1
        elif sep:
            # os.environ'ga yozing. Bola jarayonlar uni meros oladi.
            os.environ[name] = value
    return status


@builtin("unset")
def unset(shell: "Shell", args: list[str]) -> int:
    """unset NOM... — o'zgaruvchini o'chiring."""
    for name in args:
        os.environ.pop(name, None)
    return 0


@builtin("history")
def history(shell: "Shell", args: list[str]) -> int:
    """history [-c] — buyruqlar tarixini ko'rsating. -c: tarixni tozalang."""
    if args == ["-c"]:
        shell.clear_history()
        return 0
    for number, line in enumerate(shell.history, start=1):
        print(f"{number:5}  {line}")
    return 0


@builtin("type")
def type_(shell: "Shell", args: list[str]) -> int:
    """type NOM... — buyruq builtin'mi yoki fayl ekanini ko'rsating."""
    status = 0
    for name in args:
        if name in BUILTINS:
            print(f"{name} — shell builtin")
        elif path := shutil.which(name):
            print(f"{name} — {path}")
        else:
            error(f"type: {name}: topilmadi")
            status = 1
    return status


@builtin("help")
def help_(shell: "Shell", args: list[str]) -> int:
    """help — yordam matnini ko'rsating."""
    print("pysh — Python'da yozilgan oddiy shell.\n")
    print("Builtin buyruqlar:")
    for func in BUILTINS.values():
        # Docstring'ning birinchi qatori — qisqa tavsif.
        print(f"  {func.__doc__.splitlines()[0]}")
    print(
        "\nSintaksis:\n"
        "  a | b          pipe: a chiqishi b kirishiga boradi\n"
        "  a > f, a >> f  stdout'ni faylga yozing (>> qo'shadi)\n"
        "  a < f          stdin'ni fayldan oling\n"
        "  a 2> f, 2>&1   stderr'ni faylga yoki stdout'ga yo'naltiring\n"
        "  a && b         a muvaffaqiyatli bo'lsa, b ni bajaring\n"
        "  a || b         a xato bersa, b ni bajaring\n"
        "  a ; b          a dan keyin b ni bajaring\n"
        "  $VAR ${VAR} $? ~ *.py 'matn' \"matn\"  — ochish (expansion)\n"
        "  NOM=qiymat     o'zgaruvchi o'rnating"
    )
    return 0
