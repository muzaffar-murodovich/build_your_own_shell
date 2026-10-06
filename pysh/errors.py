"""Shell errors.

All errors are in one place. This makes the code easier to read.
"""

import sys


class ShellError(Exception):
    """An error to show to the user. The shell does not stop."""


class LexError(ShellError):
    """A lexer error. Example: a quote is not closed."""


class ParseError(ShellError):
    """A syntax error. Example: `ls |` (no command after the pipe)."""


class ShellExit(Exception):
    """The `exit` command sends this signal. The shell stops."""

    def __init__(self, code: int = 0):
        super().__init__(code)
        # An exit code is in the range 0..255 (Unix rule).
        self.code = code & 0xFF


def error(message: str) -> None:
    """Write an error message to stderr."""
    print(f"pysh: {message}", file=sys.stderr)


def describe_os_error(exc: OSError) -> str:
    """Make a short and clear message from an OSError."""
    if exc.filename:
        return f"{exc.filename}: {exc.strerror}"
    return exc.strerror or str(exc)
