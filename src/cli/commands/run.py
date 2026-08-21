"""Typer command definition for the `bcllm_run.py` CLI surface
(--experiment, --add-run, --list-runs, --run, --remove-run,
--randomization-seed, --system-prompt, --user-prompt, --output) — CLI
migration marco 4B, first slice (2026-08-20).

External syntax is unchanged: same flag names, types, choices, and
special values (system-default/null) as the argparse implementation it
replaces. Only the internal parsing mechanism is new. Not registered as a
public Typer subcommand tree — invoked programmatically by
`bcllm_run.py`'s `parse_run_argv()`, mirroring
`src/cli/commands/{questions,experiment}.py`'s established pattern
exactly (including the same fixes already applied there: `--where`/
`--exclude`-shaped list options would need the function-body-not-callback
pattern too, but this module has none).

`--output` is parsed and validated (choices) for CLI compatibility only —
never read by any handler, matching the argparse version (a pre-existing,
documented dead flag, see docs/status/known-issues.md).
"""

from __future__ import annotations

import enum
import sys
from dataclasses import dataclass

import typer

from src.cli.param_types import (
    typer_reject_special_values,
    typer_str_or_system_default,
)
from src.core.argv_utils import ParserExit
from src.core.special_config_values import ForceSystemDefault


class OutputFormat(str, enum.Enum):
    console = "console"
    json = "json"
    csv = "csv"
    markdown = "markdown"


@dataclass(frozen=True)
class RunParsedArgs:
    """Typed replacement for argparse.Namespace — field names mirror the
    original argparse dest names exactly."""

    experiment: str
    add_run: bool
    list_runs: bool
    run: str | None
    remove_run: str | None
    randomization_seed: str | ForceSystemDefault | None
    system_prompt: str | ForceSystemDefault | None
    user_prompt: str | ForceSystemDefault | None
    output: str


def _run_command(
    experiment: str = typer.Option(
        ..., "--experiment", callback=typer_reject_special_values, metavar="NAME",
        help="Experiment name",
    ),
    add_run: bool = typer.Option(
        False, "--add-run", help="Create new run",
    ),
    list_runs: bool = typer.Option(
        False, "--list-runs", help="List all runs in experiment",
    ),
    run: str = typer.Option(
        None, "--run", callback=typer_reject_special_values, metavar="RUN_ID",
        help="Show run details",
    ),
    remove_run: str = typer.Option(
        None, "--remove-run", callback=typer_reject_special_values, metavar="RUN_ID",
        help="Remove run (soft delete)",
    ),
    randomization_seed: str = typer.Option(
        None, "--randomization-seed", callback=typer_str_or_system_default, metavar="N",
        help="Randomization Seed for answer option shuffling (AUTO, number, "
             "or empty for None) — controls AnswerRandomizer only, never sent to the API",
    ),
    system_prompt: str = typer.Option(
        None, "--system-prompt", callback=typer_str_or_system_default, metavar="PROMPT",
        help="Custom system prompt (inherits from experiment if not specified)",
    ),
    user_prompt: str = typer.Option(
        None, "--user-prompt", callback=typer_str_or_system_default, metavar="PROMPT",
        help="Custom user prompt (inherits from experiment if not specified)",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.console, "--output", help="Output format",
    ),
) -> RunParsedArgs:
    """The Typer command body. Returns a RunParsedArgs on success — Click
    threads this return value back through `.main()`. Only reached when
    per-option parsing/callbacks all succeeded; the cross-option
    mutex-group check and the randomization-seed FORMAT check below are
    the two usage-error classes no single option's callback can express
    on its own.
    """
    group_flags_given = sum([
        add_run,
        list_runs,
        run is not None,
        remove_run is not None,
    ])
    if group_flags_given == 0:
        raise typer.BadParameter(
            "one of the arguments --add-run --list-runs --run --remove-run is required"
        )
    if group_flags_given > 1:
        raise typer.BadParameter(
            "--add-run, --list-runs, --run, and --remove-run are mutually exclusive"
        )

    # Mirrors bcllm_run.py's original parse_add_run_request: FORMAT
    # validation of --randomization-seed (int/AUTO/empty vs. garbage) is
    # knowable from the string alone and is checked here, at parse time
    # — separate from ConfigResolver.build_run_config_dict's later, DB-
    # dependent resolution (AUTO generation, experiment-config
    # inheritance), which needs the experiment/connection and cannot run
    # this early.
    if isinstance(randomization_seed, str):
        from src.core.config_resolver import parse_randomization_seed_strict

        try:
            parse_randomization_seed_strict(randomization_seed)
        except ValueError as e:
            raise typer.BadParameter(str(e)) from None

    return RunParsedArgs(
        experiment=experiment,
        add_run=add_run,
        list_runs=list_runs,
        run=run,
        remove_run=remove_run,
        randomization_seed=randomization_seed,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output=output.value,
    )


_app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
_app.command()(_run_command)
_command = typer.main.get_command(_app)


def parse_run_argv(argv: list[str]) -> RunParsedArgs:
    """argv -> RunParsedArgs, the ONE parsing entry point for this
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

    if not isinstance(result, RunParsedArgs):
        # Click intercepted before the command body ran (e.g. --help) and
        # returned its own exit code directly instead of our dataclass.
        raise ParserExit(result if isinstance(result, int) else 0, None)

    return result
