"""Typer command definition for the `bcllm_provider.py` CLI surface
(--experiment, --resolve-providers) — CLI migration marco 4C, first slice
(2026-08-21).

External syntax is unchanged: same flag names, types, and special values
(system-default/null) as the argparse implementation it replaces. Only
the internal parsing mechanism is new. Not registered as a public Typer
subcommand tree — invoked programmatically by `bcllm_provider.py`'s
`parse_provider_argv()`, mirroring
`src/cli/commands/{questions,experiment,run,model}.py`'s established
pattern exactly.

This is the smallest of the two marco 4C modules (2 flags total, no
numeric/list-typed options) — no `--output` dead flag exists here either
(the argparse version never declared one).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import typer

from src.cli.param_types import typer_reject_special_values
from src.core.argv_utils import ParserExit


@dataclass(frozen=True)
class ProviderParsedArgs:
    """Typed replacement for argparse.Namespace — field names mirror the
    original argparse dest names exactly."""

    experiment: str
    resolve_providers: bool


def _provider_command(
    experiment: str = typer.Option(
        ..., "--experiment", callback=typer_reject_special_values, metavar="NAME",
        help="Experiment name",
    ),
    resolve_providers: bool = typer.Option(
        False, "--resolve-providers",
        help="Resolve providers for all variants with PROVIDER=null in the experiment",
    ),
) -> ProviderParsedArgs:
    """The Typer command body. Returns a ProviderParsedArgs on success —
    Click threads this return value back through `.main()`. No
    cross-option validation needed here (only 2 flags, one required
    scalar and one boolean — no mutex group, no list normalization)."""
    return ProviderParsedArgs(
        experiment=experiment,
        resolve_providers=resolve_providers,
    )


_app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
_app.command()(_provider_command)
_command = typer.main.get_command(_app)


def parse_provider_argv(argv: list[str]) -> ProviderParsedArgs:
    """argv -> ProviderParsedArgs, the ONE parsing entry point for this
    module's CLI surface — replaces `create_parser()` +
    `parse_args_normalized()`. Raises ParserExit for any usage error or
    `--help`, exactly matching NonExitingArgumentParser's contract: on a
    non-zero status the error has ALREADY been written to stderr by this
    function (via Click's own UsageError.show()) — callers must not print
    it again, only translate `.status` into their return code.
    """
    try:
        result = _command.main(args=argv, standalone_mode=False, prog_name="bcllm")
    except typer._click.exceptions.UsageError as e:
        e.show(file=sys.stderr)
        raise ParserExit(e.exit_code, str(e)) from None
    except typer._click.exceptions.Exit as e:
        raise ParserExit(e.exit_code if hasattr(e, "exit_code") else 0, None) from None

    if not isinstance(result, ProviderParsedArgs):
        # Click intercepted before the command body ran (e.g. --help) and
        # returned its own exit code directly instead of our dataclass.
        raise ParserExit(result if isinstance(result, int) else 0, None)

    return result
