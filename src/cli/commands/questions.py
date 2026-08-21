"""Typer command definition for the `bcllm_questions.py` CLI surface
(--experiment, --add-questions/--questions, --list-questions,
--remove-question, --where, --exclude, --output, --source-file) — CLI
migration marco 4A (2026-08-20).

External syntax is unchanged: same flag names, types, choices, and
special values (system-default/null) as the argparse implementation it
replaces. Only the internal parsing mechanism is new. Not registered as a
public Typer subcommand tree — invoked programmatically by
`bcllm_questions.py`'s `parse_questions_argv()`, mirroring how
`NonExitingArgumentParser`/`ParserExit` were used before (see
`src/core/argv_utils.py`). The mode/module dispatcher
(`src/core/mode_resolver.py`/`module_resolver.py`/`mode_matrix.py`) is
unchanged and still decides which module handles a given invocation.

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
class QuestionsParsedArgs:
    """Typed replacement for argparse.Namespace — field names mirror the
    original argparse dest names exactly, so call sites that used to read
    `args.experiment`/`args.add_questions`/etc. only need `args.` dropped,
    not renamed."""

    experiment: str
    add_questions: str | ForceSystemDefault | None
    list_questions: bool
    remove_question: str | None
    where: list[str] | ForceSystemDefault
    exclude: list[str] | ForceSystemDefault
    output: str
    source_file: str | None


def _questions_command(
    experiment: str = typer.Option(
        ..., "--experiment", callback=typer_reject_special_values, metavar="NAME",
        help="Experiment name",
    ),
    add_questions: str = typer.Option(
        None, "--add-questions", "--questions", callback=typer_str_or_system_default,
        metavar="SPEC",
        help='Add questions. Format: "1, 3, 5" (comma-separated), "1-10" (range), or "1, 3-5, Q010" (mixed).',
    ),
    list_questions: bool = typer.Option(
        False, "--list-questions", help="List all questions in experiment",
    ),
    remove_question: str = typer.Option(
        None, "--remove-question", callback=typer_reject_special_values, metavar="SNAPSHOT_ID",
        help="Remove question snapshot (soft delete)",
    ),
    where: list[str] = typer.Option(
        None, "--where", metavar="FILTER",
        help="Include filter (format: field=value, e.g., status=valid or meta.status=valid)",
    ),
    exclude: list[str] = typer.Option(
        None, "--exclude", metavar="FILTER",
        help="Exclude filter (format: field=value, e.g., status=annulled)",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.console, "--output", help="Output format",
    ),
    source_file: str = typer.Option(
        None, "--source-file", callback=typer_reject_special_values, metavar="FILE",
        help="Source file for question payloads (default: .env or QUESTIONS_DATASET_PATH)",
    ),
) -> QuestionsParsedArgs:
    """The Typer command body. Returns a QuestionsParsedArgs on success —
    Click threads this return value back through `.main()`. Only reached
    when per-option parsing/callbacks all succeeded; the cross-option
    mutex-group check below is the one usage-error class no single
    option's callback can express.

    `where`/`exclude` are deliberately NOT given a Click-level
    `callback=typer_filter_list_or_system_default` — Typer generates its
    own post-callback list convertor for any `list[str]`-typed parameter
    (`typer.main.generate_list_convertor`) that runs AFTER the Click
    callback and assumes the result is still list-shaped (it calls
    `len()` on it unconditionally and collapses an explicit `[]` back to
    `None`), which breaks the moment a callback returns the
    FORCE_SYSTEM_DEFAULT sentinel instead of a list. Applying the
    system-default/contradiction transformation here in the function body
    instead sidesteps that Typer-internals conflict entirely — the Click
    layer only ever sees/returns a plain `list[str] | None`.
    """
    where = typer_filter_list_or_system_default(where)
    exclude = typer_filter_list_or_system_default(exclude)

    group_flags_given = sum([
        add_questions is not None,
        list_questions,
        remove_question is not None,
    ])
    if group_flags_given == 0:
        raise typer.BadParameter(
            "one of the arguments --add-questions/--questions --list-questions "
            "--remove-question is required"
        )
    if group_flags_given > 1:
        raise typer.BadParameter(
            "--add-questions/--questions, --list-questions, and --remove-question "
            "are mutually exclusive"
        )

    return QuestionsParsedArgs(
        experiment=experiment,
        add_questions=add_questions,
        list_questions=list_questions,
        remove_question=remove_question,
        where=where,
        exclude=exclude,
        output=output.value,
        source_file=source_file,
    )


_app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
_app.command()(_questions_command)
_command = typer.main.get_command(_app)


def parse_questions_argv(argv: list[str]) -> QuestionsParsedArgs:
    """argv -> QuestionsParsedArgs, the ONE parsing entry point for this
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

    if not isinstance(result, QuestionsParsedArgs):
        # Click intercepted before the command body ran (e.g. --help) and
        # returned its own exit code directly instead of our dataclass.
        raise ParserExit(result if isinstance(result, int) else 0, None)

    return result
