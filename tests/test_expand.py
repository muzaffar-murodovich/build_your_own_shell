"""Expander uchun unit testlar."""

from pysh.expand import expand_word

VARS = {"NAME": "Ali", "?": "3"}


def expand(raw):
    return expand_word(raw, lambda name: VARS.get(name, ""))


def test_variables():
    assert expand("$NAME") == ["Ali"]
    assert expand("${NAME}bek") == ["Alibek"]
    assert expand("$?") == ["3"]


def test_quotes():
    assert expand("'$NAME'") == ["$NAME"]
    assert expand('"salom $NAME"') == ["salom Ali"]
    assert expand(r'"a \"b\""') == ['a "b"']
    assert expand(r"a\ b") == ["a b"]


def test_empty_values():
    assert expand("$YOQ") == []      # Qo'shtirnoqsiz bo'sh so'z yo'qoladi.
    assert expand('""') == [""]      # Qo'shtirnoqli bo'sh so'z qoladi.


def test_tilde(monkeypatch):
    monkeypatch.setenv("HOME", "/home/ali")
    assert expand("~/code") == ["/home/ali/code"]
    assert expand("a~") == ["a~"]


def test_glob(tmp_path, monkeypatch):
    (tmp_path / "a.py").touch()
    (tmp_path / "b.py").touch()
    monkeypatch.chdir(tmp_path)
    assert expand("*.py") == ["a.py", "b.py"]
    assert expand("'*.py'") == ["*.py"]
    assert expand("*.yoq") == ["*.yoq"]
