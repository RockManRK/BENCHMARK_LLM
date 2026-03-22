#!/usr/bin/env python3
"""Question snapshot management CLI.

This module provides CLI commands for managing question snapshots within experiments:
- Add question snapshots to experiments
- List question snapshots in an experiment
- Remove question snapshots (soft delete)

Usage:
    bcllm_questions.py --experiment <name> --add-questions <spec>
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

from src_v2.cli.database import get_database_connection
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
        help="Add questions (format: q1,q2,q3 or 1-10 or mixed)",
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
        "--output",
        choices=["console", "json", "csv", "markdown"],
        default="console",
        help="Output format",
    )

    parser.add_argument(
        "--source-file",
        metavar="FILE",
        help="Source file for question payloads (default: .env)",
    )

    return parser


def parse_question_spec(spec: str) -> list[str]:
    """Parse question specification into list of question IDs.

    Formats supported:
    - Comma-separated: q1,q2,q3
    - Range: 1-10 or q1-q10
    - Mixed: q1,q2,5-10,q15

    Args:
        spec: Question specification string.

    Returns:
        List of normalized question IDs (e.g., ["Q01", "Q02", "Q03"]).

    Raises:
        ValueError: If spec contains invalid format.
    """
    question_ids = []

    for part in spec.split(','):
        part = part.strip()

        if not part:
            continue

        # Range: 1-10 or q1-q10 or Q1-Q10
        range_match = re.match(r'^(q?)(\d+)-(q?)(\d+)$', part, re.IGNORECASE)
        if range_match:
            prefix1, start, prefix2, end = range_match.groups()
            prefix = prefix1 or prefix2  # Use whichever prefix exists
            start_num = int(start)
            end_num = int(end)

            if start_num > end_num:
                raise ValueError(f"Invalid range: {start_num}-{end_num} (start > end)")

            for i in range(start_num, end_num + 1):
                question_ids.append(f"Q{i:02d}")
            continue

        # Single: q1 or Q001 or 1
        single_match = re.match(r'^(q?)(\d+)$', part, re.IGNORECASE)
        if single_match:
            prefix, num = single_match.groups()
            question_ids.append(f"Q{int(num):02d}")
            continue

        # Invalid format
        raise ValueError(f"Invalid question spec: {part}")

    if not question_ids:
        raise ValueError("No valid question IDs found in spec")

    return question_ids


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

    # Parse question spec
    try:
        question_ids = parse_question_spec(args.add_questions)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Expected formats: q1,q2,q3 | 1-10 | q1,q2,5-10", file=sys.stderr)
        return 1

    # Add snapshots with idempotency
    added_count = 0
    skipped_count = 0

    for qid in question_ids:
        # Check for idempotency (snapshot already exists)
        existing = snap_repo.get_by_experiment_and_question(experiment.experiment_id, qid)
        if existing:
            skipped_count += 1
            continue

        # Create snapshot with placeholder payload
        payload = {
            "stem": f"Question {qid} stem",
            "options": ["A", "B", "C", "D"],
            "answer_key": "B",
        }

        snapshot = QuestionSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            question_id=qid,
            question_payload=json.dumps(payload),
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
