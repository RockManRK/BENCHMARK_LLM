"""Exit-code contract for the bcllm CLI.

Implements docs/contracts/interaction-contracts.md Section 2's exit-code
rule: 0 success, 1 domain/validation error, 2 usage error (already
handled automatically by argparse today and by Click/Typer after the
migration — not reimplemented here), 130 interrupted.

`run_command` is the one piece with concrete use starting at the first
migrated command (CLI migration plan Fase 4, marco 4A): today only
`bcllm_execute.main` catches `KeyboardInterrupt` and returns 130 (see
src/cli/bcllm_execute.py) — every other of the 8 CLI modules does not,
so a `Ctrl-C` there propagates as an uncaught traceback. Wrapping each
migrated command's entry point in `run_command` gives all of them the
same 130 convention this contract requires, instead of copying the
try/except by hand into each one.
"""

from __future__ import annotations

from typing import Callable

from src.cli.presentation.console import error_console

EXIT_SUCCESS = 0
EXIT_DOMAIN_ERROR = 1
EXIT_USAGE_ERROR = 2
EXIT_INTERRUPTED = 130


def run_command(command: Callable[[], int]) -> int:
    """Run a CLI command's body, enforcing the exit-code contract.

    Deliberately catches ONLY KeyboardInterrupt. EXIT_USAGE_ERROR (2) is
    never produced here and never will be: argparse today, and Click/Typer
    after the migration, both raise a usage error (SystemExit(2) via
    argparse's own parser.error(); typer.BadParameter/ClickException via
    Click's own Command.main()) from *argument parsing*, which happens
    before a command's body — and therefore before this function — is
    ever invoked. A `typer.BadParameter` raised by a parameter callback
    (e.g. src/cli/param_types.py's typer_int_or_system_default) is caught by
    Typer/Click's own dispatcher, not by this wrapper. Do NOT add a bare
    `except Exception` here — that would swallow a usage error that
    somehow propagated this far and misreport it as EXIT_DOMAIN_ERROR
    (1), corrupting the exit-code contract in
    docs/contracts/interaction-contracts.md Section 2.

    TEST OBLIGATION (tracked, not yet possible): once the first real
    Typer command exists (CLI migration plan Fase 4, marco 4A), add a
    test proving a bad argument on that command exits 2, not 1 — this
    function has no app to attach to yet, so it cannot be verified
    end-to-end today; test_presentation_foundation.py only proves this
    function itself never catches anything but KeyboardInterrupt.

    Args:
        command: A zero-argument callable that performs the command and
            returns its own exit code (0 or EXIT_DOMAIN_ERROR) on the
            normal path.

    Returns:
        The command's own exit code, or EXIT_INTERRUPTED (130) if a
        KeyboardInterrupt was raised during execution.
    """
    try:
        return command()
    except KeyboardInterrupt:
        error_console.print("\n[warning]Interrupted.[/warning]")
        return EXIT_INTERRUPTED
