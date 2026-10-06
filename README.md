# pysh — our own shell (Build Your Own X)

A simple Unix shell written in Python. It has no external dependencies.
It uses the same system calls as real shells (bash, zsh):
`fork`, `exec`, `pipe`, `dup2`, `waitpid`.

## Install and run

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

.venv/bin/pysh                         # interactive mode
.venv/bin/pysh -c 'ls | wc -l'         # one command
.venv/bin/pysh script.sh               # a script file
echo 'echo hello' | .venv/bin/pysh     # from stdin

.venv/bin/pytest                       # tests
```

## Features

| Feature              | Example                                  |
|----------------------|------------------------------------------|
| External programs    | `ls -la`, `git status`                   |
| Pipes                | `cat f.txt \| grep py \| sort`           |
| Redirects            | `> f`, `>> f`, `< f`, `2> f`, `2>&1`     |
| Conditional run      | `make && ./app \|\| echo failed`, `a ; b` |
| Variables            | `$HOME`, `${USER}`, `$?`, `$$`, `X=1`    |
| Quotes               | `'literal $text'`, `"expands $HOME"`, `\ ` |
| Tilde and glob       | `~/code`, `*.py`                         |
| Builtins             | `cd`, `pwd`, `echo`, `exit`, `export`, `unset`, `history`, `type`, `help` |
| Interactive features | ↑ ↓ history, Tab completion, Ctrl+C, Ctrl+D, colored prompt |

## How it works

```
"ls -l | wc -l > n.txt"
        │
        ▼
 1. lexer.py     →  [ls] [-l] (|) [wc] [-l] (>) [n.txt]       tokens
        │
        ▼
 2. parser.py    →  Pipeline[ ls -l ,  wc -l (> n.txt) ]       tree (AST)
        │
        ▼
 3. expand.py    →  expands $VAR, ~, *.py and quotes           (at run time)
        │
        ▼
 4. executor.py  →  pipe() + fork() + dup2() + exec() + waitpid()
```

Read the code in this sequence: `lexer.py` → `parser.py` → `expand.py` →
`executor.py` → `shell.py` → `cli.py`.

## Intentional simplifications

- No background jobs (`&`) and no job control (`fg`, `bg`, Ctrl+Z).
- No command substitution `$(...)` and no arithmetic `$((...))`.
- No `if`, `for`, `while` or functions.
- An unquoted `$VAR` is not split on spaces.
- `X=1` is exported immediately. In bash, it is only a shell variable.

These are good exercises for the next steps.
