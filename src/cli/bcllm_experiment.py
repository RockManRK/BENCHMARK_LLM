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

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core import QuestionLoader
from src.core.config_resolver import ConfigResolver
from src.db.repository import ExperimentRepository, SnapshotRepository, VariantRepository
from src.db.models import Experiment, ModelVariant, QuestionSnapshot
from src.utils.variant_signature import generate_variant_signature
from src.validators.model_id_validator import validate_model_id
from src.cli.bcllm_questions import parse_filter, filter_questions


def _validate_expected_mode(mode: Mode) -> None:
    """Validate that received mode matches expected mode for this module.

    Args:
        mode: The CLI mode passed from dispatcher.

    Raises:
        SystemExit: If mode is invalid for this module.
    """
    VALID_MODES = [Mode.CREATE, Mode.MODIFY, Mode.INVALID]

    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"This indicates a dispatcher bug. Please report this issue.",
            file=sys.stderr
        )
        sys.exit(1)


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
        "--system-prompt",
        metavar="PROMPT",
        help="Custom system prompt (run default)",
    )
    parser.add_argument(
        "--user-prompt",
        metavar="PROMPT",
        help="Custom user prompt (run default)",
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        help="Base URL for model API (model default)",
    )
    parser.add_argument(
        "--max-reasoning",
        metavar="TOKENS",
        type=int,
        help="Max tokens for reasoning (model default)",
    )
    parser.add_argument(
        "--max-tokens",
        metavar="TOKENS",
        type=int,
        help="Max total tokens (model default)",
    )
    parser.add_argument(
        "--reasoning",
        metavar="EFFORT",
        help="Reasoning effort level (model default)",
    )
    parser.add_argument(
        "--repeat-penalty",
        metavar="VALUE",
        type=float,
        help="Repeat penalty (model default)",
    )
    parser.add_argument(
        "--temperature",
        metavar="VALUE",
        type=float,
        help="Temperature (model default)",
    )
    parser.add_argument(
        "--top-k",
        metavar="VALUE",
        type=int,
        help="Top-K sampling (model default)",
    )
    parser.add_argument(
        "--top-p",
        metavar="VALUE",
        type=float,
        help="Top-P sampling (model default)",
    )
    parser.add_argument(
        "--reasoning-tokens",
        type=int,
        metavar="TOKENS",
        help="Max tokens for reasoning (model default)",
    )
    parser.add_argument(
        "--vision",
        type=str,
        metavar="VALUE",
        help="Enable vision support. Valid values: true, false, NULL (case-insensitive). Default: false",
    )
    parser.add_argument(
        "--structured",
        type=str,
        metavar="VALUE",
        help="Enable structured outputs. Valid values: true, false, NULL (case-insensitive). Default: false",
    )
    parser.add_argument(
        "--add-model",
        action="append",
        metavar="MODEL_ID",
        help="Add model variant at creation time (can be used multiple times)",
    )
    parser.add_argument(
        "--add-questions",
        metavar="SPEC",
        help="Add questions at creation time. Format: \"1, 3, 5\" (comma-separated), \"1-10\" (range), or \"1, 3-5, Q010\" (mixed). Quote arguments with spaces.",
    )
    parser.add_argument(
        "--questions",
        dest="add_questions",  # True alias: populates args.add_questions
        metavar="SPEC",
        help="Alias for --add-questions. Format: \"1, 3, 5\" or \"1-10\" or \"1, 3-5, Q010\". Quote arguments with spaces.",
    )
    parser.add_argument(
        "--where",
        metavar="FILTER",
        action="append",
        help="Include filter for questions (format: field=value, e.g., status=valid)",
    )
    parser.add_argument(
        "--exclude",
        metavar="FILTER",
        action="append",
        help="Exclude filter for questions (format: field=value, e.g., status=annulled)",
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

    if args.vision is not None and not _validate_bool_value(args.vision):
        print(f"Error: Invalid value for --vision: {args.vision}", file=sys.stderr)
        print("Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null", file=sys.stderr)
        print("Example: --vision true", file=sys.stderr)
        return 1

    if args.structured is not None and not _validate_bool_value(args.structured):
        print(f"Error: Invalid value for --structured: {args.structured}", file=sys.stderr)
        print("Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null", file=sys.stderr)
        print("Example: --structured false", file=sys.stderr)
        return 1

    resolver = ConfigResolver()
    env_dict = resolver.load_env()

    config_dict = resolver.build_experiment_config_dict(args)

    config_json = json.dumps(config_dict, indent=None, separators=(',', ':'))
    config_hash = hashlib.sha256(config_json.encode('utf-8')).hexdigest()

    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=name,
        description="",
        config_json=config_json,
        config_hash=config_hash,
    )

    repo.save(experiment)
    print(f"✓ Experiment '{experiment.name}' created (ID: {experiment.experiment_id})")

    if args.add_model:
        exit_code = _add_models_at_creation(args.add_model, experiment, conn, resolver)
        if exit_code != 0:
            return exit_code

    exit_code = _create_question_snapshots(args, experiment, conn)
    if exit_code != 0:
        return exit_code

    return 0


def _validate_bool_value(value: str) -> bool:
    """Validate boolean CLI value.

    Args:
        value: String value to validate.

    Returns:
        True if valid (case-insensitive true/false/null), False otherwise.
    """
    if value is None:
        return True
    normalized = value.lower()
    return normalized in ('true', 'false', 'null')


def _add_models_at_creation(models: list[str], experiment: Experiment, conn, resolver: ConfigResolver) -> int:
    """Add model variants to experiment at creation time.

    Uses complete config from CLI > .env > NULL.

    Args:
        models: List of model IDs to add.
        experiment: Experiment to add models to.
        conn: Database connection.
        resolver: ConfigResolver instance.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    var_repo = VariantRepository(conn)

    for model_id in models:
        if not validate_model_id(model_id):
            print(f"Error: Invalid model ID format: {model_id}", file=sys.stderr)
            print("Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)", file=sys.stderr)
            return 1

        config = resolver.build_model_config_dict(type('Args', (), {'experiment': experiment})(), experiment)

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
        - If --add-questions NOT provided: check DEFAULT_QUESTIONS from .env
        - If neither provided: select ALL questions from dataset
        - Apply QUESTIONS_STATUS_ADD from .env for filtering (if --where not provided)
        - Apply QUESTIONS_STATUS_EXCLUDE from .env for filtering (if --exclude not provided)
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
            print(f"Error: Invalid question specification: {e}", file=sys.stderr)
            print("Valid formats:", file=sys.stderr)
            print("  --questions \"1, 3, 5\"    (comma-separated, quote if spaces)", file=sys.stderr)
            print("  --questions \"1-10\"       (range)", file=sys.stderr)
            print("  --questions \"1, 3-5, Q10\" (mixed)", file=sys.stderr)
            return 1
    else:
        default_questions = env_dict.get('DEFAULT_QUESTIONS')
        if default_questions:
            print(f"  Using DEFAULT_QUESTIONS from .env: {default_questions}")
            try:
                selected_questions = loader.parse_question_spec(default_questions, questions)
            except ValueError as e:
                print(f"Error: Invalid DEFAULT_QUESTIONS specification: {e}", file=sys.stderr)
                return 1
        else:
            selected_questions = questions

    include_filters = []
    exclude_filters = []

    if args.where:
        for filter_str in args.where:
            try:
                include_filters.append(parse_filter(filter_str))
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
    else:
        status_add = env_dict.get('QUESTIONS_STATUS_ADD')
        if status_add:
            try:
                include_filters.append(parse_filter(status_add))
            except ValueError as e:
                print(f"Error: Invalid QUESTIONS_STATUS_ADD filter: {e}", file=sys.stderr)
                return 1

    if args.exclude:
        for filter_str in args.exclude:
            try:
                exclude_filters.append(parse_filter(filter_str))
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
    else:
        status_exclude = env_dict.get('QUESTIONS_STATUS_EXCLUDE')
        if status_exclude:
            try:
                exclude_filters.append(parse_filter(status_exclude))
            except ValueError as e:
                print(f"Error: Invalid QUESTIONS_STATUS_EXCLUDE filter: {e}", file=sys.stderr)
                return 1

    if include_filters or exclude_filters:
        questions_index = {q.get('source_id') or q.get('id'): q for q in questions}
        original_ids = [q.get('source_id') or q.get('id') for q in selected_questions]
        filtered_ids = filter_questions(original_ids, questions_index, include_filters, exclude_filters)
        filtered_count = len(original_ids) - len(filtered_ids)

        if filtered_count > 0:
            print(f"  ({filtered_count} questions filtered out)")

        selected_questions = [q for q in selected_questions if (q.get('source_id') or q.get('id')) in filtered_ids]

    if not selected_questions:
        print("Warning: No questions selected for snapshotting.", file=sys.stderr)
        return 0

    snapshot_repo = SnapshotRepository(conn)
    created_count = 0
    skipped_count = 0

    for question in selected_questions:
        source_id = question.get('source_id') or question.get('id') or question.get('question_id', '')
        question_position = question.get('internal_id')

        if question_position is None:
            print(f"Error: Question missing internal_id: {source_id}", file=sys.stderr)
            return 1

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
            json_question_id=source_id,
            question_position=question_position,
            question_payload=json.dumps(payload),
        )

        snapshot_repo.save(snapshot)
        created_count += 1
        print(f"✓ Added question {source_id} (position {question_position})")

    if created_count > 0:
        print(f"\nSummary: {created_count} added")
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

    import json
    config = json.loads(experiment.config_json) if experiment.config_json else {}

    print(f"Experiment: {experiment.name}")
    print(f"  ID: {experiment.experiment_id}")
    print(f"  Description: {experiment.description or '(none)'}")
    print(f"  Config:")
    print(f"    seed: {config.get('RUN_RESPONSES_SEED', 'None')}")
    print(f"    system_prompt: {config.get('SYSTEM_PROMPT', 'None')}")
    print(f"    user_prompt: {config.get('USER_PROMPT', 'None')}")

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
    experiments = repo.list_all()

    if not experiments:
        print("No experiments found.")
        return 0

    print(f"{'Name':<30} {'ID':<20}")
    print("-" * 50)
    for exp in experiments:
        print(f"{exp.name:<30} {exp.experiment_id:<20}")

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

    repo.delete(experiment.experiment_id)
    print(f"✓ Experiment '{experiment.name}' removed")
    return 0


def main(mode: Mode) -> int:
    """Main entry point.
    
    Args:
        mode: The CLI mode (CREATE, MODIFY, EXECUTE, INVALID).
        
    Returns:
        Exit code (0 for success, 1 for error).
    """
    _validate_expected_mode(mode)
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
