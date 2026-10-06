r"""Stage 3: Expander (word expansion).

The expander changes a raw word into real arguments:

    ~/code        ->  /Users/ali/code         (tilde)
    $HOME, ${HOME}->  /Users/ali              (variable)
    $?            ->  0                       (last exit code)
    'a $b'        ->  a $b                    (single quotes: nothing expands)
    "a $HOME"     ->  a /Users/ali            (double quotes: $ expands)
    a\ b          ->  a b                     (backslash)
    *.py          ->  main.py test.py         (glob)

Simplification: bash splits an unquoted $VAR on spaces.
We do not split it. This makes the code much simpler.
"""

import glob
import os
from collections.abc import Callable

from .errors import ShellError

# lookup(name) -> the value of the variable. The shell gives this function.
Lookup = Callable[[str], str]


def expand_word(raw: str, lookup: Lookup) -> list[str]:
    """Expand one raw word and return a list of arguments.

    The result can have 0, 1 or more items:
      0 — the word was an empty variable ($NONE).
      1 — the usual case.
      N — the glob found more than one file (*.py).
    """
    out: list[str] = []
    quoted = False     # Does the word have quotes?
    has_glob = False   # Does the word have an unquoted *, ? or [?
    i = 0
    n = len(raw)

    # The tilde expands only at the start of a word: "~" or "~/...".
    if raw == "~" or raw.startswith("~/"):
        out.append(os.environ.get("HOME", "~"))
        i = 1

    while i < n:
        ch = raw[i]

        if ch == "'":
            # Single quotes: take the text without changes.
            end = raw.index("'", i + 1)
            out.append(raw[i + 1:end])
            quoted = True
            i = end + 1

        elif ch == '"':
            # Double quotes: $ expands, \" and \\ are protected.
            quoted = True
            i += 1
            while i < n and raw[i] != '"':
                if raw[i] == "\\" and i + 1 < n and raw[i + 1] in '"\\$':
                    out.append(raw[i + 1])
                    i += 2
                elif raw[i] == "$":
                    value, i = _read_variable(raw, i, lookup)
                    out.append(value)
                else:
                    out.append(raw[i])
                    i += 1
            i += 1  # Move past the closing ".

        elif ch == "\\":
            # Backslash: take the next character without changes.
            if i + 1 < n:
                out.append(raw[i + 1])
            i += 2

        elif ch == "$":
            value, i = _read_variable(raw, i, lookup)
            out.append(value)

        else:
            if ch in "*?[":
                has_glob = True
            out.append(ch)
            i += 1

    word = "".join(out)

    # An empty unquoted word disappears. `echo $NONE` -> no argument.
    # But `echo ""` gives one empty argument.
    if not word and not quoted:
        return []

    if has_glob:
        matches = sorted(glob.glob(word))
        # If there is no match, bash keeps the word without changes. We do the same.
        if matches:
            return matches

    return [word]


def expand_words(raw_words: list[str], lookup: Lookup) -> list[str]:
    """Expand more than one word and join the results."""
    result: list[str] = []
    for raw in raw_words:
        result.extend(expand_word(raw, lookup))
    return result


def expand_single(raw: str, lookup: Lookup) -> str:
    """For a redirect file name: the result must be exactly one word."""
    words = expand_word(raw, lookup)
    if len(words) != 1:
        raise ShellError(f"{raw}: ambiguous redirect")
    return words[0]


def _read_variable(raw: str, i: int, lookup: Lookup) -> tuple[str, int]:
    """raw[i] == "$". Read the variable.

    Returns: (value, the index after the variable).
    """
    j = i + 1

    # The ${NAME} form.
    if j < len(raw) and raw[j] == "{":
        end = raw.find("}", j)
        if end == -1:
            raise ShellError("unclosed '${'")
        return lookup(raw[j + 1:end]), end + 1

    # Special variables: $? (exit code), $$ (PID), $0 (shell name).
    if j < len(raw) and raw[j] in "?$0":
        return lookup(raw[j]), j + 1

    # A usual name: letters, digits and "_".
    k = j
    while k < len(raw) and (raw[k].isalnum() or raw[k] == "_"):
        k += 1

    # There is no name after "$". The "$" is a usual character.
    if k == j:
        return "$", j

    return lookup(raw[j:k]), k
