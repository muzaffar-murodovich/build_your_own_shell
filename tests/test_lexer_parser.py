"""Unit tests for the lexer and the parser."""

import pytest

from pysh.errors import LexError, ParseError
from pysh.lexer import Token, tokenize
from pysh.parser import parse


def words(line):
    return [t.value for t in tokenize(line)]


def test_simple_words():
    assert words("ls   -l  /tmp") == ["ls", "-l", "/tmp"]


def test_operators_split_words():
    assert tokenize("ls|wc>f") == [
        Token("WORD", "ls"), Token("OP", "|"),
        Token("WORD", "wc"), Token("OP", ">"), Token("WORD", "f"),
    ]


def test_quotes_keep_spaces_raw():
    # The lexer does not remove quotes. This is the work of the expander.
    assert words("""echo "a b" 'c d'""") == ["echo", '"a b"', "'c d'"]


def test_two_redirect_only_at_word_start():
    assert words("echo a2>f") == ["echo", "a2", ">", "f"]
    assert words("ls 2>f") == ["ls", "2>", "f"]


def test_comment():
    assert words("ls # comment") == ["ls"]
    assert words("echo a#b") == ["echo", "a#b"]


def test_unclosed_quote():
    with pytest.raises(LexError):
        tokenize('echo "hello')


def test_parse_structure():
    tree = parse(tokenize("a && b | c > out; d"))
    ops = [op for op, _ in tree.items]
    assert ops == [None, "&&", ";"]
    pipeline = tree.items[1][1]
    assert [c.argv for c in pipeline.commands] == [["b"], ["c"]]
    assert pipeline.commands[1].redirects[0].target == "out"


@pytest.mark.parametrize("line", ["| ls", "ls |", "ls &&", "ls >", "ls ; ; ls"])
def test_syntax_errors(line):
    with pytest.raises(ParseError):
        parse(tokenize(line))
