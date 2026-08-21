#!/usr/bin/env python3
"""Question snapshot management CLI.

This module provides CLI commands for managing question snapshots within experiments:
- Add question snapshots to experiments (with range and filter support)
- List question snapshots in an experiment
- Remove question snapshots (soft delete)

Usage:
    bcllm_questions.py --experiment <name> --add-questions <spec>
    bcllm_questions.py --experiment <name> --add-questions <spec> --where status=valid
    bcllm_questions.py --experiment <name> --add-questions <spec> --exclude status=annulled
    bcllm_questions.py --experiment <name> --list-questions
    bcllm_questions.py --experiment <name> --remove-question <snapshot_id>

Exit Codes:
    0: Success
    1: Validation error (not found, invalid input, spec parsing error)
    2: Usage error (bad/unrecognized argument, FORBIDDEN system-default value,
       system-default combined with a concrete filter)

--add-questions's single-action pipeline (argv -> parse/normalize/validate
-> AddQuestionsRequest -> add_questions_action -> AddQuestionsResult) is
used identically by main() (standalone) and bcllm.py's composite
--create-experiment flow — see run_add_questions()'s docstring and
docs/status/known-issues.md ("same action, same path" invariant).
"""

import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core import QuestionLoader, build_question_snapshot_payload
from src.core.argv_utils import has_flag, ParserExit
from src.core.config_resolver import ConfigResolver
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT, ForceSystemDefault
from src.cli.commands.questions import parse_questions_argv
from src.db.models import QuestionSnapshot
from src.db.repository import ExperimentRepository, SnapshotRepository
from src.utils.logging_config import get_logger
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event


def _validate_expected_mode(mode: Mode) -> None:
    """Validate that received mode matches expected mode for this module.

    Args:
        mode: The CLI mode passed from dispatcher.

    Raises:
        SystemExit: If mode is invalid for this module.

    Note:
        Mode.INVALID is not accepted. It represents "no valid mode detected"
        and should be caught by dispatcher validation before reaching this module.
        Accepting Mode.INVALID here would mask dispatcher bugs.
    """
    # ACCEPT Mode.CREATE for composite flows (--create-experiment + --add-questions)
    # The orchestration layer (bcllm.py) creates the experiment before dispatching.
    # Mode.INVALID is explicitly excluded - it indicates a dispatcher resolution failure.
    VALID_MODES = [Mode.CREATE, Mode.MODIFY]

    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"This indicates a dispatcher bug. Please report this issue.",
            file=sys.stderr
        )
        sys.exit(1)


# Explicit opt-in classification for system-default recognition — see
# src/core/special_config_values.py::normalize_special_config_values and
# docs/contracts/system-default-semantics.md for the full SUPPORTED/
# FORBIDDEN/NOT_APPLICABLE contract this implements. Kept as module-level
# constants for cross-module consistency checks
# (tests/unit/cli/test_system_default_classification_consistency.py) —
# no longer consumed by parsing directly since the Typer conversion
# (marco 4A, 2026-08-20): src/cli/commands/questions.py's
# _questions_command declares the same classification via its per-option
# callbacks (typer_str_or_system_default for add_questions,
# typer_reject_special_values for experiment/remove_question/source_file)
# and the explicit typer_filter_list_or_system_default() call for
# where/exclude — see that module for the real, executed source of truth.
SYSTEM_DEFAULT_SUPPORTED = {
    'add_questions',
}
SYSTEM_DEFAULT_FORBIDDEN = {
    'experiment', 'remove_question', 'source_file',
}


def parse_filter(filter_str: str) -> tuple[str, str]:
    """Parse a filter string into field and value.

    Args:
        filter_str: Filter in format "field=value".

    Returns:
        Tuple of (field, value).

    Raises:
        ValueError: If filter format is invalid.
    """
    if '=' not in filter_str:
        raise ValueError(f"Invalid filter format: {filter_str} (expected field=value)")

    field_name, value = filter_str.split('=', 1)
    return field_name.strip(), value.strip()


def load_question_source(source_file: str | None = None) -> dict[str, dict]:
    """Load question source from JSON file.

    Args:
        source_file: Path to JSON file. If None, loads from
                     QUESTIONS_DATASET_PATH env var (via ConfigResolver).

    Returns:
        Dictionary mapping question_id to question data.

    Raises:
        FileNotFoundError: If dataset file not found.
        json.JSONDecodeError: If invalid JSON.
        ValueError: If dataset path not configured.

    Note:
        This method fails loudly — no silent fallbacks or placeholders.
    """
    resolver = ConfigResolver()
    env_dict = resolver.load_env()

    if source_file is None:
        source_file = env_dict.get('QUESTIONS_DATASET_PATH')
        if not source_file:
            raise ValueError(
                "QUESTIONS_DATASET_PATH not set in .env and no --source-file provided. "
                "Please configure the dataset path."
            )

    path = Path(source_file)
    if not path.is_absolute():
        path = Path.cwd() / path

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    questions_index = {}
    questions_list = data.get('questions', data) if isinstance(data, dict) else data

    for question in questions_list:
        qid = question.get('id') or question.get('question_id')
        if qid:
            questions_index[str(qid)] = question

    return questions_index


def _get_nested_field(obj: dict, field_path: str) -> str | None:
    """Get a nested field from a dictionary.

    Supports three access patterns:
    1. Direct field: obj['status']
    2. Dot notation: obj['meta']['status'] for field_path='meta.status'
    3. Recursive search: searches through nested dicts for field_path='status'

    Args:
        obj: Dictionary to search.
        field_path: Field path (e.g., "status" or "meta.status").

    Returns:
        Field value as string, or None if not found.
    """
    if '.' in field_path:
        parts = field_path.split('.')
        current = obj
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return str(current) if current is not None else None

    if field_path in obj:
        return str(obj[field_path]) if obj[field_path] is not None else None

    for key, value in obj.items():
        if key == field_path:
            return str(value) if value is not None else None
        if isinstance(value, dict):
            result = _get_nested_field(value, field_path)
            if result is not None:
                return result

    return None


def matches_filters(
    question: dict,
    include_filters: list[tuple[str, str]] | None = None,
    exclude_filters: list[tuple[str, str]] | None = None,
) -> bool:
    """Check if a question matches the given filters.

    Args:
        question: Question data dictionary.
        include_filters: List of (field, value) pairs for inclusion.
        exclude_filters: List of (field, value) pairs for exclusion.

    Returns:
        True if question passes all filters, False otherwise.
    """
    if exclude_filters:
        for field_name, value in exclude_filters:
            if _get_nested_field(question, field_name) == value:
                return False

    if include_filters:
        for field_name, value in include_filters:
            if _get_nested_field(question, field_name) != value:
                return False

    return True


def filter_questions(
    question_ids: list[str],
    questions_index: dict[str, dict],
    include_filters: list[tuple[str, str]] | None = None,
    exclude_filters: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Filter question IDs based on inclusion and exclusion criteria.

    Args:
        question_ids: List of question IDs to filter.
        questions_index: Dictionary mapping question_id to question data.
        include_filters: List of (field, value) pairs for inclusion.
        exclude_filters: List of (field, value) pairs for exclusion.

    Returns:
        Filtered list of question IDs.
    """
    filtered = []

    for qid in question_ids:
        if qid not in questions_index:
            continue

        question = questions_index[qid]
        if matches_filters(question, include_filters, exclude_filters):
            filtered.append(qid)

    return filtered


@dataclass(frozen=True)
class AddQuestionsRequest:
    """Structured input for add_questions_action — built by
    run_add_questions() from parsed+normalized+filter-list-normalized CLI
    args, never argv or argparse.Namespace directly."""
    experiment: str
    add_questions: str | ForceSystemDefault
    where: list[str] | ForceSystemDefault = field(default_factory=list)
    exclude: list[str] | ForceSystemDefault = field(default_factory=list)
    source_file: str | None = None


@dataclass(frozen=True)
class AddQuestionsResult:
    """Structured output from add_questions_action.

    exit_code: 0 success, 1 operational/domain error (not found, dataset
        error, invalid spec/filter), 2 usage error (none originate inside
        the action today — the contradiction/FORBIDDEN checks all happen
        earlier, in run_add_questions's parsing step — but the field
        exists for consistency with the other actions).
    messages: stdout lines, in order, exactly as the original
        print()-based handler produced them — including partial progress
        (e.g. "Added question Q001...") from before a later item fails,
        which the original did print before returning early.
    error: single stderr error message, if any.
    """
    exit_code: int
    messages: tuple[str, ...] = ()
    error: str | None = None
    added_count: int = 0
    skipped_count: int = 0


def add_questions_action(request: AddQuestionsRequest, conn, *, commit: bool = True) -> AddQuestionsResult:
    """The shared --add-questions action: dataset loading, spec/filter
    resolution, and the DB writes. Pure — no argv/Namespace, no print(),
    no sys.exit(). Used identically by the standalone and composite
    adapters (see run_add_questions).

    commit: whether each snapshot write commits immediately (default).
        The composite flow (bcllm.py) passes False to participate in its
        src.db.unit_of_work.UnitOfWork scope — see
        docs/status/composite-flow-unit-of-work-design.md."""
    messages: list[str] = []

    exp_repo = ExperimentRepository(conn)
    snap_repo = SnapshotRepository(conn)

    experiment = exp_repo.get_by_name(request.experiment)
    if not experiment:
        return AddQuestionsResult(exit_code=1, error=f"Experiment not found: {request.experiment}")

    loader = QuestionLoader()

    try:
        dataset_path = request.source_file
        if not dataset_path:
            resolver = ConfigResolver()
            env_dict = resolver.load_env()
            dataset_path = env_dict.get('QUESTIONS_DATASET_PATH')
            if not dataset_path:
                return AddQuestionsResult(exit_code=1, error=(
                    "QUESTIONS_DATASET_PATH not set in .env and no --source-file provided. "
                    "Please configure the dataset path."
                ))

        questions = loader.load_dataset(dataset_path)
        questions = loader.assign_internal_ids(questions)
    except FileNotFoundError as e:
        return AddQuestionsResult(exit_code=1, error=f"Question dataset not found: {e}")
    except json.JSONDecodeError as e:
        return AddQuestionsResult(exit_code=1, error=f"Invalid JSON in question dataset: {e}")
    except ValueError as e:
        return AddQuestionsResult(exit_code=1, error=str(e))

    question_ids: list[str] = []
    if request.add_questions is FORCE_SYSTEM_DEFAULT:
        # Explicit system-default -> select ALL available questions. No
        # .env fallback applies here (unlike the composite --create-experiment
        # path's DEFAULT_QUESTIONS) — the mutex group always requires an
        # explicit --add-questions value in this standalone flow, so there
        # is no "not specified" case to fall back from. See
        # docs/contracts/system-default-semantics.md.
        for q in questions:
            qid = q.get('source_id') or q.get('id') or str(q.get('internal_id', ''))
            if qid and qid not in question_ids:
                question_ids.append(qid)
    elif request.add_questions:
        spec = request.add_questions.strip()
        try:
            selected = loader.parse_question_spec(spec, questions)
            for q in selected:
                qid = q.get('source_id') or q.get('id') or str(q.get('internal_id', ''))
                if qid and qid not in question_ids:
                    question_ids.append(qid)
        except ValueError as e:
            return AddQuestionsResult(exit_code=1, error=(
                f"Invalid question specification: {e}\n"
                "Valid formats:\n"
                "  --questions \"1, 3, 5\"    (comma-separated, quote if spaces)\n"
                "  --questions \"1-10\"       (range)\n"
                "  --questions \"1, 3-5, Q10\" (mixed)"
            ))

    if not question_ids:
        return AddQuestionsResult(exit_code=1, error="No valid question IDs found in spec")

    questions_index = {q.get('source_id') or q.get('id'): q for q in questions}

    include_filters: list[tuple[str, str]] = []
    exclude_filters: list[tuple[str, str]] = []

    if request.where and request.where is not FORCE_SYSTEM_DEFAULT:
        for filter_str in request.where:
            try:
                include_filters.append(parse_filter(filter_str))
            except ValueError as e:
                return AddQuestionsResult(exit_code=1, error=str(e), messages=tuple(messages))

    if request.exclude and request.exclude is not FORCE_SYSTEM_DEFAULT:
        for filter_str in request.exclude:
            try:
                exclude_filters.append(parse_filter(filter_str))
            except ValueError as e:
                return AddQuestionsResult(exit_code=1, error=str(e), messages=tuple(messages))

    if include_filters or exclude_filters:
        original_count = len(question_ids)
        question_ids = filter_questions(question_ids, questions_index, include_filters, exclude_filters)
        filtered_count = original_count - len(question_ids)
        if filtered_count > 0:
            messages.append(f"  ({filtered_count} questions filtered out)")

    added_count = 0
    skipped_count = 0

    for qid in question_ids:
        existing = snap_repo.get_by_experiment_and_question(experiment.experiment_id, qid)
        if existing:
            skipped_count += 1
            messages.append(f"Question {qid} already exists (skipped)")
            continue

        if qid not in questions_index:
            return AddQuestionsResult(
                exit_code=1, error=f"Question ID not found: {qid}",
                messages=tuple(messages), added_count=added_count, skipped_count=skipped_count,
            )

        question_data = questions_index[qid]
        question_position = question_data.get('internal_id')

        if question_position is None:
            return AddQuestionsResult(
                exit_code=1, error=f"Question missing internal_id: {qid}",
                messages=tuple(messages), added_count=added_count, skipped_count=skipped_count,
            )

        payload = build_question_snapshot_payload(question_data)

        snapshot = QuestionSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            json_question_id=qid,
            question_position=question_position,
            question_payload=json.dumps(payload, ensure_ascii=False),
        )

        snap_repo.save(snapshot, commit=commit)
        added_count += 1
        messages.append(f"✓ Added question {qid} (position {question_position})")

    messages.append(f"\nSummary: {added_count} added, {skipped_count} skipped")

    return AddQuestionsResult(
        exit_code=0, messages=tuple(messages), added_count=added_count, skipped_count=skipped_count,
    )


def parse_add_questions_request(argv: list[str]) -> AddQuestionsRequest:
    """Pure: argv -> parse/normalize/validate (scalar system-default AND
    the list-aware --where/--exclude path) -> AddQuestionsRequest. No
    database connection is opened. Raises ParserExit(status) for any
    usage error.

    Shared by run_add_questions (standalone) and bcllm.py's composite
    flow, which calls this for every requested --add-* action BEFORE
    opening a database connection or acquiring the composite flow's
    transaction lock — see
    docs/status/composite-flow-unit-of-work-design.md point 3.
    """
    args = parse_questions_argv(argv)  # raises ParserExit for any usage error

    return AddQuestionsRequest(
        experiment=args.experiment,
        add_questions=args.add_questions,
        where=args.where,
        exclude=args.exclude,
        source_file=args.source_file,
    )


def run_add_questions(
    argv: list[str] | None = None, conn=None, *,
    commit: bool = True, request: AddQuestionsRequest | None = None,
) -> int:
    """Single entry point for the --add-questions action: parsing,
    system-default normalization/classification (scalar AND the list-
    aware --where/--exclude path), request construction, dispatch to
    add_questions_action, and result presentation (printing) — used
    identically by main() (standalone, real sys.argv) and bcllm.py's
    composite flow. Both go through this exact same code, so a fix here
    applies to both callers automatically — no divergent duplicate logic
    to keep in sync.

    Never lets a usage error's own SystemExit escape (parse_questions_argv
    invokes the Typer command with standalone_mode=False and translates
    any UsageError/--help into ParserExit) — always returns an exit code.

    A usage error NEVER opens a database connection: when `conn` is not
    supplied, get_database_connection() is only called AFTER parsing
    succeeds, never before.

    Args:
        argv: Argument strings for THIS action only (no program name).
            Ignored if `request` is given directly.
        conn: An already-open connection to reuse — the composite flow
            passes its own, shared across multiple actions in one
            invocation, and this function does NOT close it. When None
            (standalone), this function opens (after a successful parse)
            and closes its own connection.
        commit: Passed straight to add_questions_action — see its
            docstring.
        request: A pre-parsed AddQuestionsRequest. When given, `argv` is
            ignored entirely and no parsing happens here — used by the
            composite flow, which pre-parses every requested action's
            argv (via parse_add_questions_request) before ever opening a
            connection, then calls this function only for its DB-facing
            half (dispatch + printing), reusing this exact same code
            path rather than duplicating it.

    Returns:
        0 success, 1 operational/domain error, 2 usage error.
    """
    if request is None:
        try:
            request = parse_add_questions_request(argv)
        except ParserExit as e:
            return e.status

    owns_conn = conn is None
    if owns_conn:
        conn = get_database_connection()
    try:
        result = add_questions_action(request, conn, commit=commit)

        for line in result.messages:
            print(line)
        if result.exit_code != 0:
            print(f"Error: {result.error}", file=sys.stderr)
        else:
            emit_event(
                get_logger("cli.questions"), Event.QUESTIONS_ADDED,
                experiment=request.experiment,
                added_count=result.added_count, skipped_count=result.skipped_count,
            )

        return result.exit_code
    finally:
        if owns_conn:
            conn.close()


def handle_list_questions(experiment_name: str, conn) -> int:
    """Handle --list-questions command.

    Args:
        experiment_name: Experiment name.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    snap_repo = SnapshotRepository(conn)

    experiment = exp_repo.get_by_name(experiment_name)
    if not experiment:
        print(f"Error: Experiment not found: {experiment_name}", file=sys.stderr)
        return 1

    snapshots = snap_repo.list_by_experiment(experiment.experiment_id)

    if not snapshots:
        print(f"No questions in experiment '{experiment.name}'.")
        return 0

    print(f"Questions in experiment: {experiment.name}")
    print(f"{'ID':<15} {'Question ID':<15} {'Stem (truncated)':<50}")
    print("-" * 80)
    for s in snapshots:
        payload = json.loads(s.question_payload)
        stem = payload.get('stem', '')
        stem_display = stem[:47] + '...' if len(stem) > 50 else stem
        print(f"{s.snapshot_id:<15} {s.json_question_id:<15} {stem_display:<50}")

    return 0


def handle_remove_question(experiment_name: str, snapshot_id: str, conn) -> int:
    """Handle --remove-question command.

    Args:
        experiment_name: Experiment name.
        snapshot_id: Snapshot ID to remove.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    snap_repo = SnapshotRepository(conn)

    experiment = exp_repo.get_by_name(experiment_name)
    if not experiment:
        print(f"Error: Experiment not found: {experiment_name}", file=sys.stderr)
        return 1

    snapshot = snap_repo.get_by_id(snapshot_id)
    if not snapshot:
        print(f"Error: Snapshot not found: {snapshot_id}", file=sys.stderr)
        return 1

    if snapshot.experiment_id != experiment.experiment_id:
        print(f"Error: Snapshot '{snapshot_id}' is not in experiment '{experiment_name}'", file=sys.stderr)
        return 1

    snap_repo.delete(snapshot.snapshot_id)
    emit_event(
        get_logger("cli.questions"), Event.QUESTION_REMOVED,
        experiment=experiment.name, snapshot_id=snapshot.snapshot_id,
        question_id=snapshot.json_question_id,
    )
    print(f"✓ Question '{snapshot.json_question_id}' removed from '{experiment.name}'")
    return 0


def main(mode: Mode) -> int:
    """Main entry point.

    Args:
        mode: The CLI mode (CREATE, MODIFY, EXECUTE, INVALID).

    Returns:
        Exit code (0 for success, 1 for error, 2 for usage error).
    """
    _validate_expected_mode(mode)
    argv = sys.argv[1:]

    # --add-questions/--questions delegate to the exact same single-action
    # pipeline the composite flow uses (see run_add_questions's docstring)
    # — peeked via has_flag before parsing, mirroring how bcllm.py's
    # composite flow already decides which action to run.
    if has_flag(argv, '--add-questions') or has_flag(argv, '--questions'):
        return run_add_questions(argv)

    # --list-questions / --remove-question have no composite-flow
    # counterpart — parsed and dispatched directly via the Typer command
    # (src/cli/commands/questions.py), same shape as before.
    try:
        args = parse_questions_argv(argv)
    except ParserExit as e:
        if e.status != 0:
            return e.status
        return 0  # --help or other clean parser exit

    conn = get_database_connection()

    try:
        if args.list_questions:
            return handle_list_questions(args.experiment, conn)
        elif args.remove_question:
            return handle_remove_question(args.experiment, args.remove_question, conn)
        else:
            # Unreachable: parse_questions_argv's mutex-group check
            # already guarantees exactly one of
            # add_questions/list_questions/remove_question is set, and
            # add_questions was already handled by the early-return above
            # — kept only as a defensive fallback, matching the original
            # argparse version's equivalent branch.
            print("Error: no valid question action specified.", file=sys.stderr)
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
