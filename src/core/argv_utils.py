"""Command-line argument utilities for special-config-value normalization
and process-exit control.

See docs/architecture/adr/ (single-action-pipeline note) and
docs/status/known-issues.md for why NonExitingArgumentParser/ParserExit
exist: argparse.ArgumentParser.exit() (called both by error() and by the
built-in --help action) calls sys.exit() directly, unconditionally. When a
parse happens deep inside bcllm.py's composite --create-experiment + --add-*
flow, an uncontrolled sys.exit() unwinds past the composite flow's rollback
logic, leaving a just-created experiment permanently un-rolled-back on a
plain usage error. Overriding only error() (an earlier, incomplete version
of this fix) does not close this gap, because --help's _HelpAction calls
parser.exit() directly, bypassing error() entirely.
"""
import argparse
import sys
from .special_config_values import FORCE_SYSTEM_DEFAULT, normalize_special_config_values


def has_flag(args: list[str], flag: str) -> bool:
    """Check if a flag is present in the argument list.

    Supports both space-separated (--flag value) and equals (--flag=value) notation.

    Args:
        args: List of argument strings (e.g., sys.argv[1:])
        flag: Flag to search for (e.g., "--execute")

    Returns:
        True if flag is present, False otherwise
    """
    for arg in args:
        if arg == flag or arg.startswith(f"{flag}="):
            return True
    return False


class ParserExit(Exception):
    """Raised by NonExitingArgumentParser.exit() instead of calling
    sys.exit(). Carries the exact status argparse itself decided:

    - status=0: normal exit with no error — the only real-world case is
      --help (_HelpAction calls parser.exit() directly after print_help(),
      no message).
    - status=2: a usage error — reached via error() (missing/invalid
      argument, unrecognized flag, mutually-exclusive-group violation,
      etc.), which itself calls self.exit(2, "prog: error: ...\\n").

    `message`, when present, has ALREADY been written to stderr by the
    time this is raised (exit() prints it via self._print_message() before
    raising, matching argparse's own behavior) — callers must NOT print it
    again, only translate `.status` into the process's real exit code (or
    propagate it as their own return value, so a caller further up — e.g.
    bcllm.py's composite-flow rollback — still gets a chance to run before
    the process actually terminates).
    """

    def __init__(self, status: int, message: str | None = None):
        self.status = status
        self.message = message
        super().__init__(message or f"parser exit status={status}")


class NonExitingArgumentParser(argparse.ArgumentParser):
    """argparse.ArgumentParser whose exit() raises ParserExit instead of
    calling sys.exit(). This controls BOTH of argparse's process-exit
    paths in one place:

    - error() (missing required args, invalid choices/types, mutually
      exclusive group violations, ...) — error() itself is NOT overridden;
      it still runs its normal print_usage()/message-formatting logic
      unchanged, then calls self.exit(2, ...) — which now raises instead
      of exiting. Reproduces argparse's exact stderr output.
    - --help / any other direct parser.exit() call (status=0, no message)
      — the built-in _HelpAction calls parser.exit() directly, bypassing
      error() entirely, which is exactly what overriding only error()
      (an earlier, incomplete version of this fix) missed.

    Use this instead of argparse.ArgumentParser for any module whose
    action(s) can run inside bcllm.py's composite flow (currently
    --add-model, --add-questions, --add-run) — see each module's
    run_add_*() adapter, which is the only place that should ever catch
    ParserExit.
    """

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._print_message(message, sys.stderr)
        raise ParserExit(status, message)


def parse_args_normalized(
    parser: argparse.ArgumentParser,
    argv=None,
    supported: set[str] = frozenset(),
    forbidden: set[str] = frozenset(),
) -> argparse.Namespace:
    """Parse arguments and normalize special config values, explicit opt-in only.

    Wraps `parser.parse_args()` then `normalize_special_config_values()` —
    see that function's docstring (src/core/special_config_values.py) for
    the full SUPPORTED/FORBIDDEN/(neither = not applicable) contract.
    Callers that pass neither `supported` nor `forbidden` get a pure parse
    with zero normalization (matches modules with no special-value flags,
    e.g. bcllm_provider.py).

    Args:
        parser: ArgumentParser instance
        argv: Command-line arguments (defaults to sys.argv[1:] if None)
        supported: dest names where 'system-default' has real semantics
        forbidden: dest names where 'system-default'/'null' must be
            explicitly rejected (identity selectors, structural flags)

    Returns:
        Parsed namespace with special config values normalized per the
        supported/forbidden classification.

    Raises:
        argparse.ArgumentError: If a supported dest has the deprecated
            'null' literal, or a forbidden dest has 'system-default' or
            'null'. Deliberately propagates as a raw exception rather than
            calling `parser.error()` itself — this function is also called
            directly/unit-tested expecting `ArgumentError` (see
            tests/integration/test_cli_special_config_values.py,
            tests/unit/core/test_special_config_values_normalization.py).
            Modules whose actions can run inside the composite flow
            (bcllm_model.py, bcllm_questions.py, bcllm_run.py) catch this
            in their run_add_*() adapter and translate it into a return
            code via parser.error() (see NonExitingArgumentParser) instead
            of letting it propagate as a traceback; other modules' main()
            call sites catch-and-parser.error() it directly.
        ParserExit: If `parser` is a NonExitingArgumentParser and argparse
            itself would have exited (usage error, --help, ...).
    """
    args = parser.parse_args(argv)
    return normalize_special_config_values(args, parser, supported, forbidden)
