"""Typer command definition for the `bcllm_execute.py` CLI surface
(--experiment, --run, --questions, --models, --retry-policy, --execute)
— CLI migration marco 4C, second slice (2026-08-21).

External syntax is unchanged for --experiment/--run/--retry-policy/
--execute. **--questions and --models are NOT unchanged** — this is a
deliberate, user-approved exception to the migration's usual "syntax
100% preserved" rule, made necessary by a real Typer/Click limitation:
the argparse original used `nargs="+"` (one flag occurrence, multiple
space-separated values: `--questions Q001 Q005 Q010`), which Click has
no equivalent for on an Option (confirmed directly — Click's `list[str]`
options only support the *repeated-flag* style, `--questions Q001
--questions Q005`, and reject extra bare tokens after the first value).
Presented to the user as a real design fork before implementing (not
decided unilaterally) — see docs/status/known-issues.md for the full
decision record.

**New canonical syntax (user decision, 2026-08-21):**
- `--questions` takes ONE comma-separated value selecting by 1-based
  POSITION in the dataset (`question_snapshots.question_position`), NOT
  the source dataset's own question ID (the old `Q001` format is REMOVED
  — no alias, no compatibility shim): `--questions 1,3,10-20`. Spaces
  around commas/hyphens are tolerated once the shell has delivered a
  single argument (`--questions "1, 3, 10-20"`, quoted per normal shell
  rules).
- `--models` takes ONE comma-separated value of literal variant
  identifiers, no numeric grammar applied: `--models model-a,model-b`.

Format validation (0, negative, inverted range, empty item, non-numeric
text for --questions; empty item for --models) happens HERE, at parse
time, as a usage error (exit 2) — mirroring `commands/run.py`'s
`--randomization-seed` FORMAT-check pattern (a check no single Click
callback can express, since it needs the whole string, not just
per-character validation). Whether a given position/variant ID actually
EXISTS in the target experiment is a separate, later, domain-level check
(exit 1) — unchanged responsibility split, still done in
`bcllm_execute.py::validate_filters` after a DB connection opens.

`--retry-policy` is deliberately left as a plain, unclassified
passthrough string — no callback, no format validation added here — its
own documented-vs-actual-behavior question is separately tracked and
undecided (`docs/status/known-issues.md`, "--retry-policy is documented
as removed but is still a live, functional CLI flag") and out of scope
for this slice.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import typer

from src.cli.param_types import typer_reject_special_values
from src.core.argv_utils import ParserExit

# Sanity ceiling on a single N-M range's expansion, independent of the
# actual dataset size (unknown at parse time — no DB connection yet).
# Protects against a typo like "1-999999999" hanging/allocating before
# any DB validation ever runs. Not a claimed real limit on dataset size,
# just a parse-time guard rail.
_MAX_QUESTIONS_RANGE_SPAN = 100_000


def _parse_positive_int(value: str, context: str) -> int:
    """Parse a single positive integer token from a --questions spec.

    Raises:
        ValueError: if `value` isn't a valid integer, or is <= 0.
    """
    try:
        parsed = int(value)
    except ValueError:
        raise ValueError(
            f"Invalid --questions specification: {context!r} is not a valid integer"
        ) from None
    if parsed <= 0:
        raise ValueError(
            f"Invalid --questions specification: {context!r} must be a "
            f"positive integer (got {parsed})"
        )
    return parsed


def parse_question_position_spec(spec: str) -> list[int]:
    """Parse --questions' position-based spec into a deduplicated,
    stable-ordered (first-occurrence) list of 1-based positions.

    Grammar (user decision, 2026-08-21 — see docs/status/known-issues.md):
    - positive integer: "1"
    - comma-separated list: "1,3,5"
    - inclusive range: "10-20"
    - combination: "1,3,10-20"
    - whitespace around commas/hyphens tolerated
    - duplicates removed, first-occurrence order preserved

    Selects by POSITION in the dataset (question_snapshots.question_position,
    1-based) — NOT the source dataset's own question_id (e.g. "Q001").
    That format is deliberately no longer accepted (no alias, no
    compatibility — confirmed via direct testing that the pre-conversion
    code accepted it as a literal, unvalidated passthrough string; no
    active normative contract requires preserving it, see known-issues.md).

    Raises:
        ValueError: for 0, negative numbers, an inverted range (start >
            end), an empty item (e.g. a stray comma), non-numeric text,
            or a single range spanning more than
            _MAX_QUESTIONS_RANGE_SPAN positions.
    """
    positions: list[int] = []
    seen: set[int] = set()

    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError(
                f"Invalid --questions specification: empty item in {spec!r} "
                "(check for a stray comma)"
            )

        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2:
                raise ValueError(f"Invalid --questions range: {part!r}")
            start_str, end_str = (b.strip() for b in bounds)
            start = _parse_positive_int(start_str, part)
            end = _parse_positive_int(end_str, part)
            if start > end:
                raise ValueError(f"Invalid --questions range: {part!r} (start > end)")
            if end - start + 1 > _MAX_QUESTIONS_RANGE_SPAN:
                raise ValueError(
                    f"Invalid --questions range: {part!r} spans more than "
                    f"{_MAX_QUESTIONS_RANGE_SPAN} positions"
                )
            for position in range(start, end + 1):
                if position not in seen:
                    seen.add(position)
                    positions.append(position)
        else:
            position = _parse_positive_int(part, part)
            if position not in seen:
                seen.add(position)
                positions.append(position)

    return positions


def parse_model_id_list(spec: str) -> list[str]:
    """Parse --models' comma-separated literal-identifier spec. Each item
    is a literal model_variant identifier — no numeric grammar applied
    (unlike --questions).

    Raises:
        ValueError: for an empty item (e.g. a stray comma).
    """
    items: list[str] = []
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError(
                f"Invalid --models specification: empty item in {spec!r} "
                "(check for a stray comma)"
            )
        items.append(part)
    return items


@dataclass(frozen=True)
class ExecuteParsedArgs:
    """Typed replacement for argparse.Namespace — field names mirror the
    original argparse dest names exactly. `questions`/`models` differ in
    SHAPE from the pre-conversion Namespace (resolved list[int]/list[str]
    here, vs. raw nargs="+" list[str] before) — see this module's
    docstring for why."""

    experiment: str
    run: str | None
    questions: list[int] | None
    models: list[str] | None
    retry_policy: str | None
    execute: bool


def _execute_command(
    experiment: str = typer.Option(
        ..., "--experiment", callback=typer_reject_special_values, metavar="NAME",
        help="Experiment name",
    ),
    run: str = typer.Option(
        None, "--run", callback=typer_reject_special_values, metavar="RUN_ID",
        help="Specific run ID to execute (default: all pending runs)",
    ),
    questions: str = typer.Option(
        None, "--questions", metavar="SPEC",
        help='Question positions to execute, 1-based, comma-separated '
             '(e.g. "1,3,10-20"). Selects by position in the dataset, not '
             'the source dataset\'s own question ID.',
    ),
    models: str = typer.Option(
        None, "--models", metavar="VAR_ID,...",
        help="Specific model variant IDs to execute, comma-separated "
             "(e.g. \"var_abc,var_xyz\")",
    ),
    retry_policy: str = typer.Option(
        None, "--retry-policy", metavar="CONFIG",
        help="Retry policy configuration (e.g., 'max_attempts=5,backoff=linear')",
    ),
    execute: bool = typer.Option(
        False, "--execute", help="Execute the run(s)",
    ),
) -> ExecuteParsedArgs:
    """The Typer command body. Returns an ExecuteParsedArgs on success —
    Click threads this return value back through `.main()`. Format
    validation for --questions/--models happens here (exit 2); DB-level
    existence validation stays in bcllm_execute.py::validate_filters
    (exit 1), unchanged responsibility split.
    """
    parsed_questions: list[int] | None = None
    if questions is not None:
        try:
            parsed_questions = parse_question_position_spec(questions)
        except ValueError as e:
            raise typer.BadParameter(str(e)) from None

    parsed_models: list[str] | None = None
    if models is not None:
        try:
            parsed_models = parse_model_id_list(models)
        except ValueError as e:
            raise typer.BadParameter(str(e)) from None

    return ExecuteParsedArgs(
        experiment=experiment,
        run=run,
        questions=parsed_questions,
        models=parsed_models,
        retry_policy=retry_policy,
        execute=execute,
    )


_app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
_app.command()(_execute_command)
_command = typer.main.get_command(_app)


def parse_execute_argv(argv: list[str]) -> ExecuteParsedArgs:
    """argv -> ExecuteParsedArgs, the ONE parsing entry point for this
    module's CLI surface — replaces `create_parser()` +
    `parser.parse_args()`. Raises ParserExit for any usage error or
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

    if not isinstance(result, ExecuteParsedArgs):
        # Click intercepted before the command body ran (e.g. --help) and
        # returned its own exit code directly instead of our dataclass.
        raise ParserExit(result if isinstance(result, int) else 0, None)

    return result
