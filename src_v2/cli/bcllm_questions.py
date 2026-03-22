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
import re
import sys
import uuid
from pathlib import Path

from src_v2.cli.database import get_database_connection
from src_v2.db.models import QuestionSnapshot
from src_v2.db.repository import ExperimentRepository, SnapshotRepository


DEFAULT_QUESTIONS_DATASET_PATH = "data/enamed_questions.json"


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
        nargs="*",
        help="Add questions (format: Q001 Q005 Q010 | Q001-Q020 | 1-50 | mixed)",
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


def parse_question_spec(spec: str) -> list[str]:
    """Parse question specification into list of question IDs.

    Formats supported:
    - Comma-separated: q1,q2,q3
    - Range: 1-10 or q1-q10 or Q001-Q010
    - Mixed: q1,q2,5-10,q15
    - Space-separated individual: Q001 Q005 Q010

    Args:
        spec: Question specification string.

    Returns:
        List of normalized question IDs (e.g., ["Q001", "Q002", "Q003"]).

    Raises:
        ValueError: If spec contains invalid format.
    """
    question_ids = []

    # Split by comma first (handles q1,q2,5-10 format)
    for part in spec.split(','):
        part = part.strip()

        if not part:
            continue

        # Range: 1-10 or q1-q10 or Q001-Q010
        range_match = re.match(r'^(q?)(\d+)-(q?)(\d+)$', part, re.IGNORECASE)
        if range_match:
            prefix1, start, prefix2, end = range_match.groups()
            prefix = prefix1 or prefix2  # Use whichever prefix exists
            start_num = int(start)
            end_num = int(end)

            if start_num > end_num:
                raise ValueError(f"Invalid range: {start_num}-{end_num} (start > end)")

            for i in range(start_num, end_num + 1):
                question_ids.append(f"Q{i:03d}")
            continue

        # Single: q1 or Q001 or 1
        single_match = re.match(r'^(q?)(\d+)$', part, re.IGNORECASE)
        if single_match:
            prefix, num = single_match.groups()
            question_ids.append(f"Q{int(num):03d}")
            continue

        # Invalid format
        raise ValueError(f"Invalid question spec: {part}")

    if not question_ids:
        raise ValueError("No valid question IDs found in spec")

    return question_ids


def parse_question_specs(specs: list[str]) -> list[str]:
    """Parse multiple question specifications into a unified list of question IDs.

    Handles both individual question IDs and ranges from command-line args.

    Args:
        specs: List of question specifications from command line.

    Returns:
        Unified list of normalized question IDs.

    Raises:
        ValueError: If any spec is invalid.
    """
    all_question_ids = []

    for spec in specs:
        # Each spec can be a single ID or a range
        question_ids = parse_question_spec(spec)
        all_question_ids.extend(question_ids)

    # Remove duplicates while preserving order
    seen = set()
    unique_ids = []
    for qid in all_question_ids:
        if qid not in seen:
            seen.add(qid)
            unique_ids.append(qid)

    return unique_ids


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
        source_file: Path to JSON file. If None, uses DEFAULT_QUESTIONS_DATASET_PATH
                     or QUESTIONS_DATASET_PATH from environment.

    Returns:
        Dictionary mapping question_id to question data.

    Raises:
        FileNotFoundError: If source file doesn't exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    if source_file is None:
        # Try environment variable first
        import os
        source_file = os.environ.get('QUESTIONS_DATASET_PATH', DEFAULT_QUESTIONS_DATASET_PATH)

    path = Path(source_file)
    if not path.is_absolute():
        # Resolve relative to current working directory
        path = Path.cwd() / path

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Build index of questions by ID
    questions_index = {}
    for question in data.get('questions', []):
        questions_index[question['id']] = question

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
    # If field_path contains a dot, use explicit nested access
    if '.' in field_path:
        parts = field_path.split('.')
        current = obj
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return str(current) if current is not None else None

    # Try direct access first
    if field_path in obj:
        return str(obj[field_path]) if obj[field_path] is not None else None

    # Recursive search through nested dictionaries
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
    # Check exclusion filters first (any match = exclude)
    if exclude_filters:
        for field, value in exclude_filters:
            if _get_nested_field(question, field) == value:
                return False

    # Check inclusion filters (all must match)
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
            # Question not in source - skip silently (might be a typo or deleted)
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

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    # Parse question specs
    try:
        question_ids = parse_question_specs(args.add_questions)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Expected formats: Q001 Q005 Q010 | Q001-Q020 | 1-50 | mixed", file=sys.stderr)
        return 1

    # Parse filters
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

    # Load question source if filters are specified
    questions_index = {}
    if include_filters or exclude_filters:
        try:
            questions_index = load_question_source(args.source_file)
        except FileNotFoundError as e:
            print(f"Error: Question source file not found: {e}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in question source file: {e}", file=sys.stderr)
            return 1

    # Apply filters if specified
    if include_filters or exclude_filters:
        original_count = len(question_ids)
        question_ids = filter_questions(question_ids, questions_index, include_filters, exclude_filters)
        filtered_count = original_count - len(question_ids)
        if filtered_count > 0:
            print(f"  ({filtered_count} questions filtered out)")

    # Add snapshots with idempotency
    added_count = 0
    skipped_count = 0

    for qid in question_ids:
        # Check for idempotency (snapshot already exists)
        existing = snap_repo.get_by_experiment_and_question(experiment.experiment_id, qid)
        if existing:
            skipped_count += 1
            continue

        # Get question payload from source if available, otherwise use placeholder
        if qid in questions_index:
            question_data = questions_index[qid]
            payload = {
                "stem": question_data.get("stem", ""),
                "options": list(question_data.get("options", {}).values()),
                "answer_key": question_data.get("answer_key", ""),
                "meta": question_data.get("meta", {}),
            }
        else:
            # Fallback for questions not in source (shouldn't happen normally)
            payload = {
                "stem": f"Question {qid} stem",
                "options": ["A", "B", "C", "D"],
                "answer_key": "B",
                "meta": {},
            }

        snapshot = QuestionSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            question_id=qid,
            question_payload=json.dumps(payload, ensure_ascii=False),
        )

        snap_repo.save(snapshot)
        added_count += 1

    print(f"✓ {added_count} question(s) added to '{experiment.name}'")
    if skipped_count > 0:
        print(f"  ({skipped_count} already existed)")

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

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    snapshots = snap_repo.list_by_experiment(experiment.experiment_id, active_only=True)

    if not snapshots:
        print(f"No questions in experiment '{experiment.name}'.")
        return 0

    # Print table
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

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    # Check snapshot exists
    snapshot = snap_repo.get_by_id(args.remove_question)
    if not snapshot:
        print(f"Error: Snapshot not found: {args.remove_question}", file=sys.stderr)
        return 1

    # Check snapshot belongs to experiment
    if snapshot.experiment_id != experiment.experiment_id:
        print(f"Error: Snapshot '{args.remove_question}' is not in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    snap_repo.deactivate(snapshot.snapshot_id)
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
