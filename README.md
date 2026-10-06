# pysh — o'z Shell'imiz (Build Your Own X)

Python'da yozilgan oddiy Unix shell. Tashqi kutubxona yo'q.
Haqiqiy shell'lar (bash, zsh) ishlatadigan tizim chaqiruvlari ishlatiladi:
`fork`, `exec`, `pipe`, `dup2`, `waitpid`.

## O'rnatish va ishga tushirish

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

.venv/bin/pysh                         # interaktiv rejim
.venv/bin/pysh -c 'ls | wc -l'         # bitta buyruq
.venv/bin/pysh script.sh               # skript fayl
echo 'echo salom' | .venv/bin/pysh     # stdin'dan

.venv/bin/pytest                       # testlar
```

## Nima ishlaydi

| Imkoniyat          | Misol                                    |
|--------------------|------------------------------------------|
| Tashqi dasturlar   | `ls -la`, `git status`                   |
| Pipe               | `cat f.txt \| grep py \| sort`           |
| Redirect           | `> f`, `>> f`, `< f`, `2> f`, `2>&1`     |
| Shartli bajarish   | `make && ./app \|\| echo xato`, `a ; b`  |
| O'zgaruvchilar     | `$HOME`, `${USER}`, `$?`, `$$`, `X=1`    |
| Qo'shtirnoqlar     | `'oddiy $matn'`, `"ochiladi $HOME"`, `\ ` |
| Tilde va glob      | `~/code`, `*.py`                         |
| Builtin'lar        | `cd`, `pwd`, `echo`, `exit`, `export`, `unset`, `history`, `type`, `help` |
| Interaktiv qulaylik| ↑ ↓ tarix, Tab bilan to'ldirish, Ctrl+C, Ctrl+D, rangli prompt |

## Qanday ishlaydi

```
"ls -l | wc -l > n.txt"
        │
        ▼
 1. lexer.py     →  [ls] [-l] (|) [wc] [-l] (>) [n.txt]       token'lar
        │
        ▼
 2. parser.py    →  Pipeline[ ls -l ,  wc -l (> n.txt) ]       daraxt (AST)
        │
        ▼
 3. expand.py    →  $VAR, ~, *.py, qo'shtirnoqlarni ochish     (bajarish vaqtida)
        │
        ▼
 4. executor.py  →  pipe() + fork() + dup2() + exec() + waitpid()
```

O'qishni shu tartibda boshlang: `lexer.py` → `parser.py` → `expand.py` →
`executor.py` → `shell.py` → `cli.py`.

## Ataylab soddalashtirilgan joylar

- Fon rejimi (`&`), job control (`fg`, `bg`, Ctrl+Z) yo'q.
- `$(...)` (command substitution) va `$((...))` (arifmetika) yo'q.
- `if`, `for`, `while`, funksiyalar yo'q.
- Qo'shtirnoqsiz `$VAR` bo'sh joy bo'yicha bo'linmaydi.
- `X=1` darhol `export` qilinadi. Bash'da u faqat shell o'zgaruvchisi bo'ladi.

Bular keyingi qadamlar uchun yaxshi mashqlar.
