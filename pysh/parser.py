"""Stage 2: Parser.

The parser builds a tree (AST) from the tokens.

Grammar (rules):

    command_list := pipeline ( (";" | "&&" | "||") pipeline )* [";"]
    pipeline     := command ( "|" command )*
    command      := ( WORD | redirect )+
    redirect     := (">" | ">>" | "<" | "2>" | "2>>") WORD
                  | "2>&1"

Example:  make && ls | wc -l > n.txt

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
    op: str                    # Example: ">"
    target: str | None = None  # The file name (raw). None for "2>&1".


@dataclass
class Command:
    """One simple command. Example: `grep -i py > out.txt`."""
    argv: list[str] = field(default_factory=list)  # Raw words.
    redirects: list[Redirect] = field(default_factory=list)


@dataclass
class Pipeline:
    """Commands that `|` connects. Example: `ls | sort | head`."""
    commands: list[Command]


@dataclass
class CommandList:
    """A sequence of pipelines.

    Each item: (operator, pipeline).
    The operator shows the connection to the previous pipeline.
    In the first item, the operator is None.
    """
    items: list[tuple[str | None, Pipeline]]


def parse(tokens: list[Token]) -> CommandList:
    """Build a CommandList from the tokens."""
    return _Parser(tokens).parse_list()


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # --- Helper methods ---

    def _peek(self) -> Token | None:
        """Return the current token. Do not move past it."""
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self) -> Token:
        """Return the current token and move to the next one."""
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _at_op(self, ops: set[str]) -> bool:
        token = self._peek()
        return token is not None and token.kind == "OP" and token.value in ops

    # --- Grammar rules ---

    def parse_list(self) -> CommandList:
        if not self.tokens:
            return CommandList([])

        items: list[tuple[str | None, Pipeline]] = [(None, self.parse_pipeline())]
        while self._peek() is not None:
            op = self._next().value  # parse_pipeline() stops only at LIST_OPS.
            if self._peek() is None:
                # A ";" at the end is permitted: `ls;`
                if op == ";":
                    break
                raise ParseError(f"command expected after '{op}'")
            items.append((op, self.parse_pipeline()))
        return CommandList(items)

    def parse_pipeline(self) -> Pipeline:
        commands = [self.parse_command()]
        while self._at_op({"|"}):
            self._next()
            if self._peek() is None:
                raise ParseError("command expected after '|'")
            commands.append(self.parse_command())
        return Pipeline(commands)

    def parse_command(self) -> Command:
        cmd = Command()
        # Collect words and redirects until you see LIST_OPS or "|".
        while self._peek() is not None and not self._at_op(LIST_OPS | {"|"}):
            token = self._next()
            if token.kind == "WORD":
                cmd.argv.append(token.value)
            elif token.value == "2>&1":
                cmd.redirects.append(Redirect("2>&1"))
            else:
                # A file name must come after a redirect operator.
                target = self._peek()
                if target is None or target.kind != "WORD":
                    raise ParseError(f"file name expected after '{token.value}'")
                cmd.redirects.append(Redirect(token.value, self._next().value))

        if not cmd.argv and not cmd.redirects:
            bad = self._peek()
            near = bad.value if bad else "end of line"
            raise ParseError(f"syntax error near '{near}'")
        return cmd
