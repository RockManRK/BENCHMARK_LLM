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
import sys
import uuid

from src_v2.cli.database import get_database_connection
from src_v2.core import QuestionLoader
from src_v2.core.config_resolver import ConfigResolver
from src_v2.db.repository import ExperimentRepository, SnapshotRepository, VariantRepository
from src_v2.db.models import Experiment, ModelVariant, QuestionSnapshot
from src_v2.utils.variant_signature import generate_variant_signature
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

    resolver = ConfigResolver()
    env_dict = resolver.load_env()

    system_prompt = resolver.resolve_prompt(
        cli_value=args.system_prompt,
        env_key="SYSTEM_PROMPT_TEMPLATE",
        default=None
    )
    user_prompt = resolver.resolve_prompt(
        cli_value=args.user_prompt,
        env_key="USER_PROMPT_TEMPLATE",
        default=None
    )

    seed_value = resolver.resolve_seed(
        cli_value=args.seed,
        env_key="RANDOM_SEED",
        experiment_name=name
    )

    config_dict = resolver.resolve_config_dict(
        cli_args=args,
        env_dict=env_dict
    )

    config_json = json.dumps(config_dict, indent=None, separators=(',', ':'))
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

    exit_code = _create_question_snapshots(args, experiment, conn)
    if exit_code != 0:
        return exit_code

    return 0


def _add_models_at_creation(models: list[str], experiment: Experiment, conn) -> int:
    """Add model variants to experiment at creation time.
    
    Uses default config (reasoning=none, vision=false, structured=false).
    For custom configs, use --add-model after experiment creation.

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

        # Build default config (minimal - no non-default values)
        config = {}
        
        # Generate signature
        variant_signature = generate_variant_signature(model_id, config)

        existing = var_repo.get_by_signature(experiment.experiment_id, variant_signature)
        if existing:
            print(f"Error: Variant '{variant_signature}' already exists in experiment '{experiment.name}'", file=sys.stderr)
            return 1

        variant = ModelVariant(
            variant_id=f"var_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            model_id=model_id,
            variant_signature=variant_signature,
            config=json.dumps(config),
        )

        var_repo.save(variant)
        print(f"✓ Model variant '{variant_signature}' added")

    return 0


def _create_question_snapshots(args, experiment: Experiment, conn) -> int:
    """Create question snapshots for experiment.

    Args:
        args: Parsed CLI arguments.
        experiment: Experiment to create snapshots for.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).

    Behavior:
        - If --add-questions provided: use specified questions
        - If --add-questions NOT provided: select ALL questions from dataset
        - Fails loudly if dataset invalid (no placeholders)
    """
    resolver = ConfigResolver()
    env_dict = resolver.load_env()

    dataset_path = env_dict.get('QUESTIONS_DATASET_PATH')
    if not dataset_path:
        print(
            "Error: QUESTIONS_DATASET_PATH not set in .env. "
            "Please configure the dataset path.",
            file=sys.stderr
        )
        return 1

    try:
        loader = QuestionLoader()
        questions = loader.load_dataset(dataset_path)
        questions = loader.assign_internal_ids(questions)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"Error loading question dataset: {e}", file=sys.stderr)
        return 1

    if args.add_questions:
        try:
            selected_questions = loader.parse_question_spec(args.add_questions, questions)
        except ValueError as e:
            print(f"Error parsing question spec: {e}", file=sys.stderr)
            return 1
    else:
        selected_questions = questions

    if not selected_questions:
        print("Warning: No questions selected for snapshotting.", file=sys.stderr)
        return 0

    snapshot_repo = SnapshotRepository(conn)
    created_count = 0
    skipped_count = 0

    for question in selected_questions:
        source_id = question.get('source_id') or question.get('id') or question.get('question_id', '')

        existing = snapshot_repo.get_by_experiment_and_question(experiment.experiment_id, source_id)
        if existing:
            skipped_count += 1
            continue

        payload = {
            'stem': question.get('stem', ''),
            'options': question.get('options', []),
            'answer_key': question.get('answer_key', ''),
            'meta': {k: v for k, v in question.items() if k not in ('stem', 'options', 'answer_key', 'id', 'source_id', 'question_id', 'internal_id')},
            'internal_id': question.get('internal_id'),
            'source_id': source_id,
        }

        snapshot = QuestionSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            question_id=source_id,
            question_payload=json.dumps(payload),
        )

        snapshot_repo.save(snapshot)
        created_count += 1

    if created_count > 0:
        print(f"✓ Created {created_count} question snapshot(s)")
    if skipped_count > 0:
        print(f"  Skipped {skipped_count} existing snapshot(s)")

    return 0


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
