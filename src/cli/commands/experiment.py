"""Typer command definition for the `bcllm_experiment.py` CLI surface
(--create-experiment, --experiment, --list-experiments,
--remove-experiment, plus every model/question/config flag usable at
creation time) — CLI migration marco 4A (2026-08-20).

External syntax is unchanged: same flag names, types, choices, and
special values (system-default/null) as the argparse implementation it
replaces. Only the internal parsing mechanism is new. Not registered as a
public Typer subcommand tree — invoked programmatically by
`bcllm_experiment.py`'s `parse_experiment_argv()`, mirroring
`src/cli/commands/questions.py`'s pattern exactly (same fixes already
applied there: `--where`/`--exclude` normalized in the command body, not
via `callback=`, to avoid Typer's own post-callback list convertor — see
`param_types.py::typer_filter_list_or_system_default`'s docstring).

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
    typer_filter_list_or_system_default,
    typer_float_or_system_default,
    typer_int_or_system_default,
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


IntOrSD = int | ForceSystemDefault | None
FloatOrSD = float | ForceSystemDefault | None
StrOrSD = str | ForceSystemDefault | None


@dataclass(frozen=True)
class ExperimentParsedArgs:
    """Typed replacement for argparse.Namespace — field names mirror the
    original argparse dest names exactly."""

    create_experiment: str | None
    experiment: str | None
    list_experiments: bool
    remove_experiment: str | None
    output: str
    randomization_seed: StrOrSD
    system_prompt: StrOrSD
    user_prompt: StrOrSD
    url: str | None
    max_reasoning: IntOrSD
    max_tokens: IntOrSD
    reasoning: StrOrSD
    repeat_penalty: FloatOrSD
    model_seed: IntOrSD
    temperature: FloatOrSD
    top_k: IntOrSD
    top_p: FloatOrSD
    reasoning_tokens: IntOrSD
    vision: StrOrSD
    structured: StrOrSD
    add_model: list[str]
    add_questions: StrOrSD
    where: list[str] | ForceSystemDefault
    exclude: list[str] | ForceSystemDefault
    provider_lock: StrOrSD


def _experiment_command(
    create_experiment: str = typer.Option(
        None, "--create-experiment", callback=typer_reject_special_values, metavar="NAME",
        help="Create new experiment",
    ),
    experiment: str = typer.Option(
        None, "--experiment", callback=typer_reject_special_values, metavar="NAME",
        help="Show experiment details",
    ),
    list_experiments: bool = typer.Option(
        False, "--list-experiments", help="List all experiments",
    ),
    remove_experiment: str = typer.Option(
        None, "--remove-experiment", callback=typer_reject_special_values, metavar="NAME",
        help="Remove experiment (soft delete)",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.console, "--output", help="Output format",
    ),
    randomization_seed: str = typer.Option(
        None, "--randomization-seed", callback=typer_str_or_system_default, metavar="SEED",
        help="Set the experiment's default Randomization Seed (AUTO, empty, "
             "or number) — controls AnswerRandomizer only, never sent to the API",
    ),
    system_prompt: str = typer.Option(
        None, "--system-prompt", callback=typer_str_or_system_default, metavar="PROMPT",
        help="Custom system prompt (run default)",
    ),
    user_prompt: str = typer.Option(
        None, "--user-prompt", callback=typer_str_or_system_default, metavar="PROMPT",
        help="Custom user prompt (run default)",
    ),
    url: str = typer.Option(
        None, "--url", callback=typer_reject_special_values, metavar="URL",
        help="Base URL for model API (model default)",
    ),
    max_reasoning: str = typer.Option(
        None, "--max-reasoning", callback=typer_int_or_system_default, metavar="TOKENS",
        help="Max tokens for reasoning (model default)",
    ),
    max_tokens: str = typer.Option(
        None, "--max-tokens", callback=typer_int_or_system_default, metavar="TOKENS",
        help="Max total tokens (model default)",
    ),
    reasoning: str = typer.Option(
        None, "--reasoning", callback=typer_str_or_system_default, metavar="EFFORT",
        help="Reasoning effort level (model default)",
    ),
    repeat_penalty: str = typer.Option(
        None, "--repeat-penalty", callback=typer_float_or_system_default, metavar="VALUE",
        help="Repeat penalty (model default)",
    ),
    model_seed: str = typer.Option(
        None, "--model-seed", callback=typer_int_or_system_default, metavar="N",
        help="MODEL_SEED - Sent as the API request's 'seed' field for "
             "deterministic inference (model default). Distinct from "
             "--randomization-seed, which controls only answer-option "
             "shuffling and is never sent to the API.",
    ),
    temperature: str = typer.Option(
        None, "--temperature", callback=typer_float_or_system_default, metavar="VALUE",
        help="Temperature (model default)",
    ),
    top_k: str = typer.Option(
        None, "--top-k", callback=typer_int_or_system_default, metavar="VALUE",
        help="Top-K sampling (model default)",
    ),
    top_p: str = typer.Option(
        None, "--top-p", callback=typer_float_or_system_default, metavar="VALUE",
        help="Top-P sampling (model default)",
    ),
    reasoning_tokens: str = typer.Option(
        None, "--reasoning-tokens", callback=typer_int_or_system_default, metavar="TOKENS",
        help="Max tokens for reasoning (model default)",
    ),
    vision: str = typer.Option(
        None, "--vision", callback=typer_str_or_system_default, metavar="VALUE",
        help="Enable vision support. Valid values: true, false, null (case-insensitive). Default: false",
    ),
    structured: str = typer.Option(
        None, "--structured", callback=typer_str_or_system_default, metavar="VALUE",
        help="Enable structured outputs. Valid values: true, false, null (case-insensitive). Default: false",
    ),
    add_model: list[str] = typer.Option(
        None, "--add-model", metavar="MODEL_ID",
        help="Add model variant at creation time (can be used multiple times)",
    ),
    add_questions: str = typer.Option(
        None, "--add-questions", "--questions", callback=typer_str_or_system_default,
        metavar="SPEC",
        help='Add questions at creation time. Format: "1, 3, 5" (comma-separated), "1-10" (range), or "1, 3-5, Q010" (mixed).',
    ),
    where: list[str] = typer.Option(
        None, "--where", metavar="FILTER",
        help="Include filter for questions (format: field=value, e.g., status=valid)",
    ),
    exclude: list[str] = typer.Option(
        None, "--exclude", metavar="FILTER",
        help="Exclude filter for questions (format: field=value, e.g., status=annulled)",
    ),
    provider_lock: str = typer.Option(
        None, "--provider-lock", callback=typer_str_or_system_default, metavar="VALUE",
        help="Enable provider lock. Valid values: true, false, system-default (case-insensitive). Default: false",
    ),
) -> ExperimentParsedArgs:
    """The Typer command body. Returns an ExperimentParsedArgs on success.
    Only reached when per-option parsing/callbacks all succeeded; the
    cross-option mutex-group check below is the one usage-error class no
    single option's callback can express.

    `where`/`exclude` are NOT given a Click-level `callback=` for the same
    reason as commands/questions.py — see
    `typer_filter_list_or_system_default`'s docstring.
    """
    where_resolved = typer_filter_list_or_system_default(where)
    exclude_resolved = typer_filter_list_or_system_default(exclude)

    group_flags_given = sum([
        create_experiment is not None,
        experiment is not None,
        list_experiments,
        remove_experiment is not None,
    ])
    if group_flags_given == 0:
        raise typer.BadParameter(
            "one of the arguments --create-experiment --experiment "
            "--list-experiments --remove-experiment is required"
        )
    if group_flags_given > 1:
        raise typer.BadParameter(
            "--create-experiment, --experiment, --list-experiments, and "
            "--remove-experiment are mutually exclusive"
        )

    return ExperimentParsedArgs(
        create_experiment=create_experiment,
        experiment=experiment,
        list_experiments=list_experiments,
        remove_experiment=remove_experiment,
        output=output.value,
        randomization_seed=randomization_seed,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        url=url,
        max_reasoning=max_reasoning,
        max_tokens=max_tokens,
        reasoning=reasoning,
        repeat_penalty=repeat_penalty,
        model_seed=model_seed,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
        reasoning_tokens=reasoning_tokens,
        vision=vision,
        structured=structured,
        add_model=add_model or [],
        add_questions=add_questions,
        where=where_resolved,
        exclude=exclude_resolved,
        provider_lock=provider_lock,
    )


_app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
_app.command()(_experiment_command)
_command = typer.main.get_command(_app)


def parse_experiment_argv(argv: list[str]) -> ExperimentParsedArgs:
    """argv -> ExperimentParsedArgs, the ONE parsing entry point for this
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

    if not isinstance(result, ExperimentParsedArgs):
        # Click intercepted before the command body ran (e.g. --help) and
        # returned its own exit code directly instead of our dataclass.
        raise ParserExit(result if isinstance(result, int) else 0, None)

    return result
