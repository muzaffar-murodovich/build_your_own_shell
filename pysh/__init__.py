"""pysh — Python'da yozilgan oddiy Unix shell.

Shell 4 bosqichda ishlaydi:

    1. lexer.py    — qatorni token'larga bo'ladi.
    2. parser.py   — token'lardan daraxt (AST) quradi.
    3. expand.py   — $VAR, ~, *.py, qo'shtirnoqlarni ochadi.
    4. executor.py — buyruqni bajaradi (fork + exec).

shell.py bu bosqichlarni birlashtiradi.
cli.py — buyruq qatori interfeysi (CLI).
"""

__version__ = "0.1.0"
