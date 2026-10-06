r"""3-bosqich: Expander (so'zlarni ochish).

Expander xom so'zni haqiqiy argumentlarga aylantiradi:

    ~/code        ->  /Users/ali/code         (tilde)
    $HOME, ${HOME}->  /Users/ali              (o'zgaruvchi)
    $?            ->  0                       (oxirgi exit kod)
    'a $b'        ->  a $b                    (bitta qo'shtirnoq: hech narsa ochilmaydi)
    "a $HOME"     ->  a /Users/ali            (qo'sh qo'shtirnoq: $ ochiladi)
    a\ b          ->  a b                     (backslash)
    *.py          ->  main.py test.py         (glob)

Soddalashtirish: bash qo'shtirnoqsiz $VAR'ni bo'sh joy bo'yicha bo'ladi.
Biz bo'lmaymiz. Bu kodni ancha soddalashtiradi.
"""

import glob
import os
from collections.abc import Callable

from .errors import ShellError

# lookup(name) -> o'zgaruvchi qiymati. Shell bu funksiyani beradi.
Lookup = Callable[[str], str]


def expand_word(raw: str, lookup: Lookup) -> list[str]:
    """Bitta xom so'zni ochib, argumentlar ro'yxatini qaytaring.

    Natija 0, 1 yoki ko'p element bo'lishi mumkin:
      0 — so'z bo'sh o'zgaruvchi edi ($YOQ).
      1 — oddiy holat.
      N — glob bir nechta faylni topdi (*.py).
    """
    out: list[str] = []
    quoted = False     # So'zda qo'shtirnoq bormi?
    has_glob = False   # So'zda qo'shtirnoqsiz *, ? yoki [ bormi?
    i = 0
    n = len(raw)

    # Tilde faqat so'z boshida ochiladi: "~" yoki "~/...".
    if raw == "~" or raw.startswith("~/"):
        out.append(os.environ.get("HOME", "~"))
        i = 1

    while i < n:
        ch = raw[i]

        if ch == "'":
            # Bitta qo'shtirnoq: ichini o'zgartirmasdan oling.
            end = raw.index("'", i + 1)
            out.append(raw[i + 1:end])
            quoted = True
            i = end + 1

        elif ch == '"':
            # Qo'sh qo'shtirnoq: $ ochiladi, \" va \\ himoyalanadi.
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
            i += 1  # Yopuvchi " ni o'tkazing.

        elif ch == "\\":
            # Backslash: keyingi belgini o'zgartirmasdan oling.
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

    # Qo'shtirnoqsiz bo'sh so'z yo'qoladi. `echo $YOQ` -> argument yo'q.
    # Lekin `echo ""` bitta bo'sh argument beradi.
    if not word and not quoted:
        return []

    if has_glob:
        matches = sorted(glob.glob(word))
        # Hech narsa topilmasa, bash so'zni o'zgartirmaydi. Biz ham.
        if matches:
            return matches

    return [word]


def expand_words(raw_words: list[str], lookup: Lookup) -> list[str]:
    """Bir nechta so'zni oching va natijalarni birlashtiring."""
    result: list[str] = []
    for raw in raw_words:
        result.extend(expand_word(raw, lookup))
    return result


def expand_single(raw: str, lookup: Lookup) -> str:
    """Redirect fayl nomi uchun: natija aniq bitta so'z bo'lishi shart."""
    words = expand_word(raw, lookup)
    if len(words) != 1:
        raise ShellError(f"{raw}: noaniq redirect (ambiguous redirect)")
    return words[0]


def _read_variable(raw: str, i: int, lookup: Lookup) -> tuple[str, int]:
    """raw[i] == "$". O'zgaruvchini o'qing.

    Qaytaradi: (qiymat, o'zgaruvchidan keyingi indeks).
    """
    j = i + 1

    # ${NAME} shakli.
    if j < len(raw) and raw[j] == "{":
        end = raw.find("}", j)
        if end == -1:
            raise ShellError("'${' yopilmagan")
        return lookup(raw[j + 1:end]), end + 1

    # Maxsus o'zgaruvchilar: $? (exit kod), $$ (PID), $0 (shell nomi).
    if j < len(raw) and raw[j] in "?$0":
        return lookup(raw[j]), j + 1

    # Oddiy nom: harf, raqam va "_".
    k = j
    while k < len(raw) and (raw[k].isalnum() or raw[k] == "_"):
        k += 1

    # "$" dan keyin nom yo'q. "$" oddiy belgi bo'ladi.
    if k == j:
        return "$", j

    return lookup(raw[j:k]), k
