#!/usr/bin/env python3
"""Experiment lifecycle management CLI.

This module provides CLI commands for managing experiments:
- Create new experiments
- Show experiment details
- List all experiments
- Remove experiments (soft delete)

Usage:
    bcllm_experiment.py --create-experiment <name>
    bcllm_experiment.py --experiment <name>
    bcllm_experiment.py --list-experiments
    bcllm_experiment.py --remove-experiment <name>

Exit Codes:
    0: Success
    1: Validation error (not found, collision, invalid input)
"""

import argparse
import hashlib
import json
import re
import sys
import uuid

from src_v2.cli.database import get_database_connection
from src_v2.db.repository import ExperimentRepository, SnapshotRepository, VariantRepository
from src_v2.db.models import Experiment, ModelVariant, QuestionSnapshot
from src_v2.validators.model_id_validator import validate_model_id


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for experiment commands.

    Returns:
        ArgumentParser configured with all experiment commands.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_experiment.py",
        description="Experiment lifecycle management",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--create-experiment",
        metavar="NAME",
        help="Create new experiment",
    )
    group.add_argument(
        "--experiment",
        metavar="NAME",
        help="Show experiment details",
    )
    group.add_argument(
        "--list-experiments",
        action="store_true",
        help="List all experiments",
    )
    group.add_argument(
        "--remove-experiment",
        metavar="NAME",
        help="Remove experiment (soft delete)",
    )

    parser.add_argument(
        "--output",
        choices=["console", "json", "csv", "markdown"],
        default="console",
        help="Output format",
    )

    # Optional flags for --create-experiment
    parser.add_argument(
        "--seed",
        metavar="SEED",
        help="Set experiment seed (AUTO, empty, or number)",
    )
    parser.add_argument(
        "--system_prompt",
        metavar="PROMPT",
        help="Custom system prompt",
    )
    parser.add_argument(
        "--user_prompt",
        metavar="PROMPT",
        help="Custom user prompt",
    )
    parser.add_argument(
        "--add-model",
        action="append",
        metavar="MODEL_ID",
        dest="add_models",
        help="Add model variant at creation time (can be used multiple times)",
    )
    parser.add_argument(
        "--add-questions",
        metavar="SPEC",
        help="Add questions at creation time (format: q1,q2,q3 or 1-10)",
    )
    parser.add_argument(
        "--retry-policy",
        metavar="POLICY",
        dest="retry_policy",
        help="Retry policy configuration",
    )

    return parser


def generate_seed(experiment_name: str) -> int:
    """Generate a deterministic seed based on experiment name.

    Args:
        experiment_name: Name of the experiment.

    Returns:
        A deterministic integer seed derived from experiment name.
    """
    hash_bytes = hashlib.sha256(experiment_name.encode('utf-8')).digest()
    seed = int.from_bytes(hash_bytes[:8], byteorder='big')
    return seed % (2**31)


def parse_seed_value(seed_arg: str, experiment_name: str) -> int | None:
    """Parse seed argument value.

    Args:
        seed_arg: Seed argument string (AUTO, empty, or number).
        experiment_name: Experiment name for AUTO generation.

    Returns:
        Integer seed value or None for empty/unset.

    Raises:
        ValueError: If seed format is invalid.
    """
    if not seed_arg or seed_arg.strip() == "":
        return None

    if seed_arg.upper() == "AUTO":
        return generate_seed(experiment_name)

    try:
        return int(seed_arg)
    except ValueError:
        raise ValueError(f"Invalid seed value: {seed_arg}. Use AUTO, empty, or a number.")


def handle_create_experiment(args, conn) -> int:
    """Handle --create-experiment command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    repo = ExperimentRepository(conn)
    name = args.create_experiment

    if not name or not name.strip():
        print("Error: Experiment name cannot be empty.", file=sys.stderr)
        return 1

    existing = repo.get_by_name(name)
    if existing:
        print(f"Error: Experiment already exists: {name}", file=sys.stderr)
        return 1

    system_prompt = args.system_prompt or "You are a helpful assistant."
    user_prompt = args.user_prompt or "Answer the following question."

    seed_value = None
    if args.seed is not None:
        try:
            seed_value = parse_seed_value(args.seed, name)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    config_json = "{}"
    config_hash = ""
    if args.retry_policy:
        config_json = json.dumps({"retry_policy": args.retry_policy})
        config_hash = hashlib.sha256(config_json.encode('utf-8')).hexdigest()

    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=name,
        description="",
        config_json=config_json,
        config_hash=config_hash,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    repo.save(experiment)
    print(f"✓ Experiment '{experiment.name}' created (ID: {experiment.experiment_id})")

    if args.add_models:
        exit_code = _add_models_at_creation(args.add_models, experiment, conn)
        if exit_code != 0:
            return exit_code

    if args.add_questions:
        exit_code = _add_questions_at_creation(args.add_questions, experiment, conn)
        if exit_code != 0:
            return exit_code

    return 0


def _add_models_at_creation(models: list[str], experiment: Experiment, conn) -> int:
    """Add model variants to experiment at creation time.

    Args:
        models: List of model IDs to add.
        experiment: Experiment to add models to.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    var_repo = VariantRepository(conn)

    for model_id in models:
        if not validate_model_id(model_id):
            print(f"Error: Invalid model ID format: {model_id}", file=sys.stderr)
            print("Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)", file=sys.stderr)
            return 1

        variant_signature = model_id.replace('/', '_')

        existing = var_repo.get_by_signature(experiment.experiment_id, variant_signature)
        if existing:
            print(f"Error: Variant '{variant_signature}' already exists in experiment '{experiment.name}'", file=sys.stderr)
            return 1

        variant = ModelVariant(
            variant_id=f"var_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            model_id=model_id,
            variant_signature=variant_signature,
            reasoning_mode="off",
            reasoning_effort=None,
            max_output_tokens=None,
            vision_enabled=False,
            structured_output=False,
            web_access_enabled=False,
        )

        var_repo.save(variant)
        print(f"  + Model '{variant.model_id}' added (ID: {variant.variant_id})")

    return 0


def _add_questions_at_creation(spec: str, experiment: Experiment, conn) -> int:
    """Add question snapshots to experiment at creation time.

    Args:
        spec: Question specification (comma-separated or range).
        experiment: Experiment to add questions to.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    snap_repo = SnapshotRepository(conn)

    question_ids = _parse_question_spec(spec)
    if isinstance(question_ids, str):
        print(f"Error: {question_ids}", file=sys.stderr)
        return 1

    added_count = 0
    skipped_count = 0

    for qid in question_ids:
        existing = snap_repo.get_by_experiment_and_question(experiment.experiment_id, qid)
        if existing:
            skipped_count += 1
            continue

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

    print(f"  + {added_count} question(s) added to '{experiment.name}'")
    if skipped_count > 0:
        print(f"    ({skipped_count} already existed)")

    return 0


def _parse_question_spec(spec: str) -> list[str] | str:
    """Parse question specification into list of question IDs.

    Formats supported:
    - Comma-separated: q1,q2,q3
    - Range: 1-10 or q1-q10
    - Mixed: q1,q2,5-10,q15

    Args:
        spec: Question specification string.

    Returns:
        List of normalized question IDs, or error message string.
    """
    question_ids = []

    for part in spec.split(','):
        part = part.strip()

        if not part:
            continue

        range_match = re.match(r'^(q?)(\d+)-(q?)(\d+)$', part, re.IGNORECASE)
        if range_match:
            prefix1, start, prefix2, end = range_match.groups()
            prefix = prefix1 or prefix2
            start_num = int(start)
            end_num = int(end)

            if start_num > end_num:
                return f"Invalid range: {start_num}-{end_num} (start > end)"

            for i in range(start_num, end_num + 1):
                question_ids.append(f"Q{i:02d}")
            continue

        single_match = re.match(r'^(q?)(\d+)$', part, re.IGNORECASE)
        if single_match:
            prefix, num = single_match.groups()
            question_ids.append(f"Q{int(num):02d}")
            continue

        return f"Invalid question spec: {part}"

    if not question_ids:
        return "No valid question IDs found in spec"

    return question_ids


def handle_show_experiment(args, conn) -> int:
    """Handle --experiment command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    repo = ExperimentRepository(conn)
    name = args.experiment
    experiment = repo.get_by_name(name)

    if not experiment:
        print(f"Error: Experiment not found: {name}", file=sys.stderr)
        return 1

    print(f"Experiment: {experiment.name}")
    print(f"  ID: {experiment.experiment_id}")
    print(f"  Description: {experiment.description or '(none)'}")
    print(f"  System Prompt: {experiment.system_prompt}")
    print(f"  User Prompt: {experiment.user_prompt}")
    print(f"  Active: {'Yes' if experiment.is_active else 'No'}")

    return 0


def handle_list_experiments(args, conn) -> int:
    """Handle --list-experiments command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    repo = ExperimentRepository(conn)
    experiments = repo.list_all(active_only=True)

    if not experiments:
        print("No experiments found.")
        return 0

    print(f"{'Name':<30} {'ID':<20} {'Active':<8}")
    print("-" * 60)
    for exp in experiments:
        status = "Yes" if exp.is_active else "No"
        print(f"{exp.name:<30} {exp.experiment_id:<20} {status:<8}")

    return 0


def handle_remove_experiment(args, conn) -> int:
    """Handle --remove-experiment command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    repo = ExperimentRepository(conn)
    name = args.remove_experiment
    experiment = repo.get_by_name(name)

    if not experiment:
        print(f"Error: Experiment not found: {name}", file=sys.stderr)
        return 1

    repo.deactivate(experiment.experiment_id)
    print(f"✓ Experiment '{experiment.name}' removed")
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
        if args.create_experiment:
            return handle_create_experiment(args, conn)
        elif args.experiment:
            return handle_show_experiment(args, conn)
        elif args.list_experiments:
            return handle_list_experiments(args, conn)
        elif args.remove_experiment:
            return handle_remove_experiment(args, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
