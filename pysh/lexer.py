"""1-bosqich: Lexer (tokenizer).

Lexer qatorni bo'laklarga (token) bo'ladi.

    Kirish:  ls -l | grep "my file" > out.txt
    Chiqish: WORD(ls) WORD(-l) OP(|) WORD(grep) WORD("my file") OP(>) WORD(out.txt)

Muhim: lexer qo'shtirnoqlarni OCHMAYDI va $VAR'ni ALMASHTIRMAYDI.
Lexer faqat so'z qayerda boshlanishini va tugashini topadi.
So'zlarni ochish ishini expand.py bajaradi.

Nima uchun ikki bosqich? `export A=1 && echo $A` buyrug'ini ko'ring.
$A qiymati `export` bajarilgandan KEYIN ma'lum bo'ladi.
Shuning uchun ochish (expand) bajarish vaqtida bo'ladi.
"""

from dataclasses import dataclass

from .errors import LexError

# Operatorlar ro'yxati. Uzun operatorlar birinchi turadi.
# Sabab: ">>" ni ikkita ">" deb o'qimaslik kerak.
OPERATORS = ("2>&1", "2>>", "&&", "||", ">>", "2>", ">", "<", "|", ";")


@dataclass(frozen=True)
class Token:
    kind: str   # "WORD" (so'z) yoki "OP" (operator)
    value: str  # So'zning xom matni (qo'shtirnoqlar bilan birga)


def tokenize(line: str) -> list[Token]:
    """Qatorni token'lar ro'yxatiga aylantiring."""
    tokens: list[Token] = []
    word: list[str] = []  # Joriy so'zning belgilari.
    i = 0

    def end_word() -> None:
        # Joriy so'zni tugating va ro'yxatga qo'shing.
        if word:
            tokens.append(Token("WORD", "".join(word)))
            word.clear()

    while i < len(line):
        ch = line[i]

        # 1) Bo'sh joy so'zni tugatadi.
        if ch.isspace():
            end_word()
            i += 1
            continue

        # 2) So'z boshidagi "#" izohni boshlaydi. Qatorning qolganini tashlang.
        if ch == "#" and not word:
            break

        # 3) Operator bormi? Bo'lsa, so'zni tugating va operatorni qo'shing.
        op = _match_operator(line, i, inside_word=bool(word))
        if op:
            end_word()
            tokens.append(Token("OP", op))
            i += len(op)
            continue

        if ch == "&":
            raise LexError("'&' (fon rejimi) hozircha qo'llab-quvvatlanmaydi")

        # 4) Qo'shtirnoq. Yopiladigan qo'shtirnoqgacha hammasini oling.
        #    Ichidagi bo'sh joy so'zni bo'lmaydi.
        if ch in "'\"":
            end = _find_closing_quote(line, i)
            word.append(line[i:end + 1])
            i = end + 1
            continue

        # 5) Backslash keyingi belgini himoya qiladi: \| oddiy belgi bo'ladi.
        if ch == "\\":
            word.append(line[i:i + 2])
            i += 2
            continue

        # 6) Oddiy belgi.
        word.append(ch)
        i += 1

    end_word()
    return tokens


def _match_operator(line: str, i: int, inside_word: bool) -> str | None:
    """`i` pozitsiyasida operator bo'lsa, uni qaytaring."""
    for op in OPERATORS:
        # "2>" faqat so'z boshida operator bo'ladi.
        # `echo a2>f` buyrug'ida "a2" so'z, ">" operator.
        if op.startswith("2") and inside_word:
            continue
        if line.startswith(op, i):
            return op
    return None


def _find_closing_quote(line: str, start: int) -> int:
    """Yopiladigan qo'shtirnoq indeksini toping."""
    quote = line[start]
    i = start + 1
    while i < len(line):
        # Qo'sh qo'shtirnoq ichida \" qo'shtirnoqni yopmaydi.
        if quote == '"' and line[i] == "\\":
            i += 2
            continue
        if line[i] == quote:
            return i
        i += 1
    raise LexError(f"qo'shtirnoq yopilmagan: {quote}")
