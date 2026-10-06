"""2-bosqich: Parser.

Parser token'lardan daraxt (AST) quradi.

Grammatika (qoidalar):

    command_list := pipeline ( (";" | "&&" | "||") pipeline )* [";"]
    pipeline     := command ( "|" command )*
    command      := ( WORD | redirect )+
    redirect     := (">" | ">>" | "<" | "2>" | "2>>") WORD
                  | "2>&1"

Misol:  make && ls | wc -l > n.txt

    CommandList
    ├── (None, Pipeline[ make ])
    └── ("&&", Pipeline[ ls -> wc -l (> n.txt) ])
"""

from dataclasses import dataclass, field

from .errors import ParseError
from .lexer import Token

REDIRECT_OPS = {">", ">>", "<", "2>", "2>>", "2>&1"}
LIST_OPS = {";", "&&", "||"}


@dataclass
class Redirect:
    op: str                    # Misol: ">"
    target: str | None = None  # Fayl nomi (xom). "2>&1" uchun None.


@dataclass
class Command:
    """Bitta oddiy buyruq. Misol: `grep -i py > out.txt`."""
    argv: list[str] = field(default_factory=list)  # Xom so'zlar.
    redirects: list[Redirect] = field(default_factory=list)


@dataclass
class Pipeline:
    """`|` bilan ulangan buyruqlar. Misol: `ls | sort | head`."""
    commands: list[Command]


@dataclass
class CommandList:
    """Pipeline'lar ketma-ketligi.

    Har bir element: (operator, pipeline).
    Operator oldingi pipeline bilan bog'lanishni ko'rsatadi.
    Birinchi elementda operator None bo'ladi.
    """
    items: list[tuple[str | None, Pipeline]]


def parse(tokens: list[Token]) -> CommandList:
    """Token'lardan CommandList quring."""
    return _Parser(tokens).parse_list()


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # --- Yordamchi metodlar ---

    def _peek(self) -> Token | None:
        """Joriy token'ni qaytaring. Uni o'tkazib yubormang."""
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self) -> Token:
        """Joriy token'ni qaytaring va keyingisiga o'ting."""
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _at_op(self, ops: set[str]) -> bool:
        token = self._peek()
        return token is not None and token.kind == "OP" and token.value in ops

    # --- Grammatika qoidalari ---

    def parse_list(self) -> CommandList:
        if not self.tokens:
            return CommandList([])

        items: list[tuple[str | None, Pipeline]] = [(None, self.parse_pipeline())]
        while self._peek() is not None:
            op = self._next().value  # parse_pipeline() faqat LIST_OPS'da to'xtaydi.
            if self._peek() is None:
                # Oxiridagi ";" ruxsat etilgan: `ls;`
                if op == ";":
                    break
                raise ParseError(f"'{op}' dan keyin buyruq kutilgan")
            items.append((op, self.parse_pipeline()))
        return CommandList(items)

    def parse_pipeline(self) -> Pipeline:
        commands = [self.parse_command()]
        while self._at_op({"|"}):
            self._next()
            if self._peek() is None:
                raise ParseError("'|' dan keyin buyruq kutilgan")
            commands.append(self.parse_command())
        return Pipeline(commands)

    def parse_command(self) -> Command:
        cmd = Command()
        # LIST_OPS yoki "|" ko'rinmaguncha so'z va redirect'larni yig'ing.
        while self._peek() is not None and not self._at_op(LIST_OPS | {"|"}):
            token = self._next()
            if token.kind == "WORD":
                cmd.argv.append(token.value)
            elif token.value == "2>&1":
                cmd.redirects.append(Redirect("2>&1"))
            else:
                # Redirect operatoridan keyin fayl nomi bo'lishi shart.
                target = self._peek()
                if target is None or target.kind != "WORD":
                    raise ParseError(f"'{token.value}' dan keyin fayl nomi kutilgan")
                cmd.redirects.append(Redirect(token.value, self._next().value))

        if not cmd.argv and not cmd.redirects:
            bad = self._peek()
            near = bad.value if bad else "qator oxiri"
            raise ParseError(f"sintaksis xatosi: '{near}' yaqinida")
        return cmd
