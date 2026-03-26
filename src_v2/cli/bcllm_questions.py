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
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

from src_v2.cli.database import get_database_connection
from src_v2.core import QuestionLoader
from src_v2.core.config_resolver import ConfigResolver
from src_v2.db.models import QuestionSnapshot
from src_v2.db.repository import ExperimentRepository, SnapshotRepository


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for question commands.

    Returns:
        ArgumentParser configured with all question commands.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_questions.py",
        description="Question snapshot management",
    )

    parser.add_argument(
        "--experiment",
        required=True,
        metavar="NAME",
        help="Experiment name",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--add-questions",
        metavar="SPEC",
        dest="add_questions",
        help="Add questions. Format: \"1, 3, 5\" (comma-separated), \"1-10\" (range), or \"1, 3-5, Q010\" (mixed). Quote arguments with spaces.",
    )
    group.add_argument(
        "--questions",
        metavar="SPEC",
        dest="add_questions",
        help="Alias for --add-questions. Format: \"1, 3, 5\" or \"1-10\" or \"1, 3-5, Q010\". Quote arguments with spaces.",
    )
    group.add_argument(
        "--list-questions",
        action="store_true",
        help="List all questions in experiment",
    )
    group.add_argument(
        "--remove-question",
        metavar="SNAPSHOT_ID",
        help="Remove question snapshot (soft delete)",
    )

    parser.add_argument(
        "--where",
        metavar="FILTER",
        action="append",
        help="Include filter (format: field=value, e.g., status=valid or meta.status=valid)",
    )
    parser.add_argument(
        "--exclude",
        metavar="FILTER",
        action="append",
        help="Exclude filter (format: field=value, e.g., status=annulled)",
    )

    parser.add_argument(
        "--output",
        choices=["console", "json", "csv", "markdown"],
        default="console",
        help="Output format",
    )

    parser.add_argument(
        "--source-file",
        metavar="FILE",
        help="Source file for question payloads (default: .env or QUESTIONS_DATASET_PATH)",
    )

    return parser


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

    field, value = filter_str.split('=', 1)
    return field.strip(), value.strip()


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
        for field, value in exclude_filters:
            if _get_nested_field(question, field) == value:
                return False

    if include_filters:
        for field, value in include_filters:
            if _get_nested_field(question, field) != value:
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


def handle_add_questions(args, conn) -> int:
    """Handle --add-questions command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    snap_repo = SnapshotRepository(conn)

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    loader = QuestionLoader()

    try:
        dataset_path = args.source_file
        if not dataset_path:
            resolver = ConfigResolver()
            env_dict = resolver.load_env()
            dataset_path = env_dict.get('QUESTIONS_DATASET_PATH')
            if not dataset_path:
                print(
                    "Error: QUESTIONS_DATASET_PATH not set in .env and no --source-file provided. "
                    "Please configure the dataset path.",
                    file=sys.stderr
                )
                return 1

        questions = loader.load_dataset(dataset_path)
        questions = loader.assign_internal_ids(questions)
    except FileNotFoundError as e:
        print(f"Error: Question dataset not found: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in question dataset: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    question_ids = []
    if args.add_questions:
        spec = args.add_questions.strip()
        try:
            selected = loader.parse_question_spec(spec, questions)
            for q in selected:
                qid = q.get('source_id') or q.get('id') or str(q.get('internal_id', ''))
                if qid and qid not in question_ids:
                    question_ids.append(qid)
        except ValueError as e:
            print(f"Error: Invalid question specification: {e}", file=sys.stderr)
            print("Valid formats:", file=sys.stderr)
            print("  --questions \"1, 3, 5\"    (comma-separated, quote if spaces)", file=sys.stderr)
            print("  --questions \"1-10\"       (range)", file=sys.stderr)
            print("  --questions \"1, 3-5, Q10\" (mixed)", file=sys.stderr)
            return 1

    if not question_ids:
        print("Error: No valid question IDs found in spec", file=sys.stderr)
        return 1

    questions_index = {q.get('source_id') or q.get('id'): q for q in questions}

    include_filters = []
    exclude_filters = []

    if args.where:
        for filter_str in args.where:
            try:
                include_filters.append(parse_filter(filter_str))
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

    if args.exclude:
        for filter_str in args.exclude:
            try:
                exclude_filters.append(parse_filter(filter_str))
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

    if include_filters or exclude_filters:
        original_count = len(question_ids)
        question_ids = filter_questions(question_ids, questions_index, include_filters, exclude_filters)
        filtered_count = original_count - len(question_ids)
        if filtered_count > 0:
            print(f"  ({filtered_count} questions filtered out)")

    added_count = 0
    skipped_count = 0

    for qid in question_ids:
        existing = snap_repo.get_by_experiment_and_question(experiment.experiment_id, qid)
        if existing:
            skipped_count += 1
            print(f"Question {qid} already exists (skipped)")
            continue

        if qid not in questions_index:
            print(f"Error: Question ID not found: {qid}", file=sys.stderr)
            return 1

        question_data = questions_index[qid]
        question_position = question_data.get('internal_id')

        if question_position is None:
            print(f"Error: Question missing internal_id: {qid}", file=sys.stderr)
            return 1

        payload = {
            "stem": question_data.get("stem", ""),
            "options": list(question_data.get("options", {}).values()) if isinstance(question_data.get("options"), dict) else question_data.get("options", []),
            "answer_key": question_data.get("answer_key", ""),
            "meta": question_data.get("meta", {}),
        }

        snapshot = QuestionSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            json_question_id=qid,
            question_position=question_position,
            question_payload=json.dumps(payload, ensure_ascii=False),
        )

        snap_repo.save(snapshot)
        added_count += 1
        print(f"✓ Added question {qid} (position {question_position})")

    print(f"\nSummary: {added_count} added, {skipped_count} skipped")

    return 0


def handle_list_questions(args, conn) -> int:
    """Handle --list-questions command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    snap_repo = SnapshotRepository(conn)

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
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
        print(f"{s.snapshot_id:<15} {s.question_id:<15} {stem_display:<50}")

    return 0


def handle_remove_question(args, conn) -> int:
    """Handle --remove-question command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    snap_repo = SnapshotRepository(conn)

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    snapshot = snap_repo.get_by_id(args.remove_question)
    if not snapshot:
        print(f"Error: Snapshot not found: {args.remove_question}", file=sys.stderr)
        return 1

    if snapshot.experiment_id != experiment.experiment_id:
        print(f"Error: Snapshot '{args.remove_question}' is not in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    snap_repo.delete(snapshot.snapshot_id)
    print(f"✓ Question '{snapshot.question_id}' removed from '{experiment.name}'")
    return 0


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = create_parser()
    args = parser.parse_args()

    conn = get_database_connection()

    try:
        if args.add_questions:
            return handle_add_questions(args, conn)
        elif args.list_questions:
            return handle_list_questions(args, conn)
        elif args.remove_question:
            return handle_remove_question(args, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
