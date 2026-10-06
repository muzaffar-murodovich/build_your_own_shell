"""Shell xatolari.

Barcha xatolar bitta joyda. Bu kodni o'qishni osonlashtiradi.
"""

import sys


class ShellError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato. Shell to'xtamaydi."""


class LexError(ShellError):
    """Lexer xatosi. Misol: qo'shtirnoq yopilmagan."""


class ParseError(ShellError):
    """Sintaksis xatosi. Misol: `ls |` (pipe'dan keyin buyruq yo'q)."""


class ShellExit(Exception):
    """`exit` buyrug'i shu signalni yuboradi. Shell to'xtaydi."""

    def __init__(self, code: int = 0):
        super().__init__(code)
        # Exit kod 0..255 oralig'ida bo'ladi (Unix qoidasi).
        self.code = code & 0xFF


def error(message: str) -> None:
    """Xato xabarini stderr'ga yozing."""
    print(f"pysh: {message}", file=sys.stderr)


def describe_os_error(exc: OSError) -> str:
    """OSError'dan qisqa va tushunarli xabar yasang."""
    if exc.filename:
        return f"{exc.filename}: {exc.strerror}"
    return exc.strerror or str(exc)
