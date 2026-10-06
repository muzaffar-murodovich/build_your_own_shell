"""pysh — a simple Unix shell written in Python.

The shell works in 4 stages:

    1. lexer.py    — splits a line into tokens.
    2. parser.py   — builds a tree (AST) from the tokens.
    3. expand.py   — expands $VAR, ~, *.py and quotes.
    4. executor.py — runs the commands (fork + exec).

shell.py connects these stages.
cli.py is the command-line interface (CLI).
"""

__version__ = "0.1.0"
