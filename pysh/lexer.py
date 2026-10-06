"""Stage 1: Lexer (tokenizer).

The lexer splits a line into parts (tokens).

    Input:  ls -l | grep "my file" > out.txt
    Output: WORD(ls) WORD(-l) OP(|) WORD(grep) WORD("my file") OP(>) WORD(out.txt)

Important: the lexer does NOT remove quotes and does NOT replace $VAR.
The lexer only finds where a word starts and where it stops.
expand.py does the expansion of words.

Why two stages? Look at the command `export A=1 && echo $A`.
The value of $A is known only AFTER `export` runs.
Thus the expansion occurs at run time.
"""

from dataclasses import dataclass

from .errors import LexError

# The list of operators. Long operators come first.
# Reason: the lexer must not read ">>" as two ">".
OPERATORS = ("2>&1", "2>>", "&&", "||", ">>", "2>", ">", "<", "|", ";")


@dataclass(frozen=True)
class Token:
    kind: str   # "WORD" or "OP" (operator)
    value: str  # The raw text of the word (with its quotes)


def tokenize(line: str) -> list[Token]:
    """Change a line into a list of tokens."""
    tokens: list[Token] = []
    word: list[str] = []  # The characters of the current word.
    i = 0

    def end_word() -> None:
        # Stop the current word and add it to the list.
        if word:
            tokens.append(Token("WORD", "".join(word)))
            word.clear()

    while i < len(line):
        ch = line[i]

        # 1) A space stops the word.
        if ch.isspace():
            end_word()
            i += 1
            continue

        # 2) A "#" at the start of a word starts a comment. Ignore the rest of the line.
        if ch == "#" and not word:
            break

        # 3) Is there an operator? If yes, stop the word and add the operator.
        op = _match_operator(line, i, inside_word=bool(word))
        if op:
            end_word()
            tokens.append(Token("OP", op))
            i += len(op)
            continue

        if ch == "&":
            raise LexError("'&' (background jobs) is not supported yet")

        # 4) A quote. Take all characters up to the closing quote.
        #    A space inside quotes does not split the word.
        if ch in "'\"":
            end = _find_closing_quote(line, i)
            word.append(line[i:end + 1])
            i = end + 1
            continue

        # 5) A backslash protects the next character: \| becomes a usual character.
        if ch == "\\":
            word.append(line[i:i + 2])
            i += 2
            continue

        # 6) A usual character.
        word.append(ch)
        i += 1

    end_word()
    return tokens


def _match_operator(line: str, i: int, inside_word: bool) -> str | None:
    """If there is an operator at position `i`, return it."""
    for op in OPERATORS:
        # "2>" is an operator only at the start of a word.
        # In `echo a2>f`, "a2" is a word and ">" is the operator.
        if op.startswith("2") and inside_word:
            continue
        if line.startswith(op, i):
            return op
    return None


def _find_closing_quote(line: str, start: int) -> int:
    """Find the index of the closing quote."""
    quote = line[start]
    i = start + 1
    while i < len(line):
        # Inside double quotes, \" does not close the quote.
        if quote == '"' and line[i] == "\\":
            i += 2
            continue
        if line[i] == quote:
            return i
        i += 1
    raise LexError(f"unclosed quote: {quote}")
