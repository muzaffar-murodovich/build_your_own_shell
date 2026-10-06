"""Integratsiya testlari: pysh'ni haqiqiy jarayon sifatida ishga tushiring."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pysh(command, cwd, stdin=None):
    """`pysh -c BUYRUQ` ni bajaring. (stdout, stderr, exit kod) qaytaring."""
    result = subprocess.run(
        [sys.executable, "-m", "pysh", "-c", command],
        cwd=cwd, input=stdin, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(cwd), "PYTHONPATH": str(ROOT)},
    )
    return result.stdout, result.stderr, result.returncode


def test_echo_and_pipe(tmp_path):
    out, _, code = pysh("echo salom dunyo | tr a-z A-Z", tmp_path)
    assert out == "SALOM DUNYO\n"
    assert code == 0


def test_long_pipeline(tmp_path):
    out, _, _ = pysh("printf 'c\\nb\\na\\n' | sort | head -2 | tr -d '\\n'", tmp_path)
    assert out == "ab"


def test_redirects(tmp_path):
    pysh("echo bir > f.txt; echo ikki >> f.txt", tmp_path)
    assert (tmp_path / "f.txt").read_text() == "bir\nikki\n"
    out, _, _ = pysh("wc -l < f.txt", tmp_path)
    assert out.strip() == "2"


def test_builtin_redirect_restores_stdout(tmp_path):
    out, _, _ = pysh("pwd > p.txt; echo keyin", tmp_path)
    assert out == "keyin\n"
    assert (tmp_path / "p.txt").read_text().strip().endswith(tmp_path.name)


def test_stderr_redirects(tmp_path):
    _, err, _ = pysh("ls /yoq-papka 2> err.txt", tmp_path)
    assert err == ""
    assert (tmp_path / "err.txt").read_text()
    out, _, _ = pysh("ls /yoq-papka 2>&1 | wc -l", tmp_path)
    assert out.strip() == "1"


def test_and_or(tmp_path):
    out, _, _ = pysh("false && echo A || echo B; true || echo C && echo D", tmp_path)
    assert out == "B\nD\n"


def test_exit_status_variable(tmp_path):
    out, _, _ = pysh("false; echo $?; true; echo $?", tmp_path)
    assert out == "1\n0\n"


def test_command_not_found(tmp_path):
    _, err, code = pysh("yoq-buyruq", tmp_path)
    assert "topilmadi" in err
    assert code == 127


def test_cd_and_variables(tmp_path):
    (tmp_path / "sub").mkdir()
    out, _, _ = pysh("cd sub && pwd; X=5; export Y=6; echo $X$Y; unset X; echo [$X]", tmp_path)
    lines = out.splitlines()
    assert lines[0].endswith("/sub")
    assert lines[1:] == ["56", "[]"]


def test_env_reaches_child_process(tmp_path):
    out, _, _ = pysh("export SALOM=dunyo; printenv SALOM", tmp_path)
    assert out == "dunyo\n"


def test_exit_code(tmp_path):
    _, _, code = pysh("exit 42; echo yetmaydi", tmp_path)
    assert code == 42


def test_syntax_error_code(tmp_path):
    _, err, code = pysh("ls |", tmp_path)
    assert code == 2
    assert "kutilgan" in err


def test_script_file(tmp_path):
    script = tmp_path / "s.sh"
    script.write_text("#!/usr/bin/env pysh\n# izoh\necho skript\nexit 3\n")
    result = subprocess.run(
        [sys.executable, "-m", "pysh", str(script)],
        capture_output=True, text=True, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
    )
    assert result.stdout == "skript\n"
    assert result.returncode == 3


def test_stdin_mode(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "pysh"], input="echo bir\necho ikki\n",
        capture_output=True, text=True, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
    )
    assert result.stdout == "bir\nikki\n"
