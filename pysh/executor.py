"""Stage 4: Executor.

This is the heart of the shell. Here, 4 main Unix system calls do the work:

    fork()    — make a copy of the current process (a child process).
    exec()    — start a different program inside the child process.
                The code of the process changes fully. There is no return.
    pipe()    — make a "pipe" with two ends: one end writes, one end reads.
    dup2(a,b) — make file descriptor b point to the same file as a.

A file descriptor (fd) is the number of an open file. Each process has 3 of them:
    0 = stdin (input), 1 = stdout (output), 2 = stderr (errors).

How `ls | wc -l` runs:

    shell ── pipe() ──> [read end r]  [write end w]
      │
      ├─ fork() ─> child 1: dup2(w, 1);  exec("ls")    # stdout -> pipe
      ├─ fork() ─> child 2: dup2(r, 0);  exec("wc")    # stdin  <- pipe
      │
      └─ waitpid() waits for the two children.
"""

import os
import re
import signal
import sys
from typing import TYPE_CHECKING

from .builtins import BUILTINS
from .errors import ShellError, ShellExit, describe_os_error, error
from .expand import Lookup, expand_single, expand_words
from .parser import Command, CommandList, Pipeline, Redirect

if TYPE_CHECKING:
    from .shell import Shell

# Redirect operator -> (which fd, flags to open the file).
_WRITE = os.O_WRONLY | os.O_CREAT
REDIRECT_TABLE = {
    "<":   (0, os.O_RDONLY),
    ">":   (1, _WRITE | os.O_TRUNC),   # TRUNC: make the file empty.
    ">>":  (1, _WRITE | os.O_APPEND),  # APPEND: add to the end.
    "2>":  (2, _WRITE | os.O_TRUNC),
    "2>>": (2, _WRITE | os.O_APPEND),
}

# A word in the form NAME=value.
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def apply_redirects(redirects: list[Redirect], lookup: Lookup) -> None:
    """Apply the redirects to the current process (with dup2)."""
    for redirect in redirects:
        if redirect.op == "2>&1":
            os.dup2(1, 2)  # Now stderr goes to the same place as stdout.
            continue
        path = expand_single(redirect.target, lookup)
        target_fd, flags = REDIRECT_TABLE[redirect.op]
        fd = os.open(path, flags, 0o644)  # 0o644: rw-r--r-- permissions.
        os.dup2(fd, target_fd)
        os.close(fd)  # We have a copy. We do not need the original fd.


def exit_code_from_wait(status: int) -> int:
    """Change the result of waitpid() into an exit code.

    If a signal kills the process (for example, Ctrl+C = SIGINT = 2),
    shells return 128 + the signal number: 128 + 2 = 130.
    """
    code = os.waitstatus_to_exitcode(status)
    return 128 - code if code < 0 else code


class Executor:
    def __init__(self, shell: "Shell"):
        self.shell = shell

    def run_list(self, command_list: CommandList) -> int:
        """Run a list like `a && b || c ; d`."""
        status = self.shell.last_status
        for op, pipeline in command_list.items:
            # && : if the previous one failed, skip.
            # || : if the previous one succeeded, skip.
            if op == "&&" and status != 0:
                continue
            if op == "||" and status == 0:
                continue
            status = self.run_pipeline(pipeline)
            # Make $? show the new value in the next command.
            self.shell.last_status = status
            # The user pushed Ctrl+C: do not run the rest of the line (as bash does).
            if status == 128 + signal.SIGINT:
                if self.shell.interactive:
                    print()  # Start the prompt on a new line after "^C".
                break
        return status

    def run_pipeline(self, pipeline: Pipeline) -> int:
        commands = pipeline.commands

        # One builtin command runs INSIDE the shell process.
        # If not, `cd` does not work (see the comment in builtins.py).
        if len(commands) == 1:
            command = commands[0]
            try:
                argv = expand_words(command.argv, self.shell.lookup_var)
            except ShellError as exc:
                error(str(exc))
                return 1

            # NAME=value: set a variable.
            # Simplification: we write it to the environment (export) immediately.
            if len(argv) == 1 and ASSIGNMENT.match(argv[0]):
                name, _, value = argv[0].partition("=")
                os.environ[name] = value
                return 0

            if not argv or argv[0] in BUILTINS:
                return self._run_in_shell(argv, command.redirects)

        # An external program or a pipe: we need fork().
        return self._run_forked(commands)

    def _run_in_shell(self, argv: list[str], redirects: list[Redirect]) -> int:
        """Run a builtin without fork.

        Problem: the redirect in `pwd > f.txt` changes the stdout of the shell itself.
        Solution: first, keep a copy of fds 0, 1 and 2.
        When the builtin stops, put them back.
        """
        sys.stdout.flush()
        sys.stderr.flush()
        saved = [os.dup(fd) for fd in (0, 1, 2)]
        try:
            apply_redirects(redirects, self.shell.lookup_var)
            if not argv:
                return 0  # Only a redirect: `> empty.txt` makes the file.
            return BUILTINS[argv[0]](self.shell, argv[1:])
        except ShellError as exc:
            error(str(exc))
            return 1
        except OSError as exc:
            error(describe_os_error(exc))
            return 1
        finally:
            # Write the Python buffer before the old fd comes back.
            sys.stdout.flush()
            sys.stderr.flush()
            for fd, copy in enumerate(saved):
                os.dup2(copy, fd)
                os.close(copy)

    def _run_forked(self, commands: list[Command]) -> int:
        """Do fork() for each command and connect them with pipes."""
        # Write the buffer before fork. If not, the child process also
        # copies the text in the shell buffer and prints it two times.
        sys.stdout.flush()
        sys.stderr.flush()

        # Ctrl+C must stop the child process, not the shell.
        # Thus the shell ignores SIGINT for a short time.
        old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        pids: list[int] = []
        prev_read: int | None = None  # The read end of the previous pipe.
        try:
            for index, command in enumerate(commands):
                is_last = index == len(commands) - 1
                read_end, write_end = (None, None) if is_last else os.pipe()

                pid = os.fork()
                if pid == 0:
                    # The child process. This function never returns.
                    self._child(command, stdin_fd=prev_read,
                                stdout_fd=write_end, unused_fd=read_end)

                # The parent process (the shell).
                pids.append(pid)
                # The child has the fds now. Close them in the shell.
                # Important: if the write end stays open, the reader
                # never sees EOF (end of file) and waits forever.
                if prev_read is not None:
                    os.close(prev_read)
                if write_end is not None:
                    os.close(write_end)
                prev_read = read_end

            # Wait for all children. The pipeline code = the code of the last command.
            status = 0
            for pid in pids:
                _, wait_status = os.waitpid(pid, 0)
                status = exit_code_from_wait(wait_status)
            return status
        finally:
            signal.signal(signal.SIGINT, old_handler)

    def _child(self, command: Command, stdin_fd: int | None,
               stdout_fd: int | None, unused_fd: int | None) -> None:
        """Runs in the child process. It ends with exec() or os._exit()."""
        code = 1
        try:
            # Let the child react to Ctrl+C in the usual way (stop).
            signal.signal(signal.SIGINT, signal.SIG_DFL)

            # Connect the pipe ends to stdin/stdout.
            if unused_fd is not None:
                os.close(unused_fd)
            if stdin_fd is not None:
                os.dup2(stdin_fd, 0)
                os.close(stdin_fd)
            if stdout_fd is not None:
                os.dup2(stdout_fd, 1)
                os.close(stdout_fd)

            # Apply the redirects after the pipe: then `ls | wc > f` works correctly.
            apply_redirects(command.redirects, self.shell.lookup_var)

            argv = expand_words(command.argv, self.shell.lookup_var)
            if not argv:
                code = 0
            elif argv[0] in BUILTINS:
                # A builtin inside a pipe: `history | grep ls`.
                code = BUILTINS[argv[0]](self.shell, argv[1:])
            else:
                code = self._exec(argv)
        except ShellExit as exc:
            code = exc.code
        except ShellError as exc:
            error(str(exc))
        except OSError as exc:
            error(describe_os_error(exc))
        except BaseException:
            pass
        finally:
            # os._exit() skips the Python clean-up code.
            # This is correct for a child process: it must not run the atexit handlers of the shell.
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except OSError:
                pass
            os._exit(code)

    @staticmethod
    def _exec(argv: list[str]) -> int:
        """Start the program. If it succeeds, it never returns.

        execvp() looks for the program in the directories of PATH.
        If it finds the program, it replaces the code of the current process with that program.
        """
        try:
            os.execvp(argv[0], argv)
        except FileNotFoundError:
            error(f"{argv[0]}: command not found")
            return 127  # Unix rule: 127 = command not found.
        except PermissionError:
            error(f"{argv[0]}: permission denied")
            return 126  # 126 = found, but it cannot run.
        return 1  # The code never gets to this line.
