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

import hashlib
import json
import sys
import uuid

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core import QuestionLoader, build_question_snapshot_payload
from src.core.config_resolver import ConfigResolver
from src.core.argv_utils import ParserExit
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT
from src.cli.commands.experiment import parse_experiment_argv, ExperimentParsedArgs
from src.db.repository import ExperimentRepository, SnapshotRepository, VariantRepository
from src.db.models import Experiment, ModelVariant, QuestionSnapshot
from src.utils.variant_signature import generate_variant_signature
from src.validators.model_id_validator import validate_model_id
from src.cli.bcllm_questions import parse_filter, filter_questions
from src.utils.logging_config import get_logger
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event


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


# Explicit opt-in classification for system-default recognition — see
# src/core/special_config_values.py::normalize_special_config_values and
# docs/contracts/system-default-semantics.md for the full SUPPORTED/
# FORBIDDEN/NOT_APPLICABLE contract this implements. Kept as module-level
# constants for cross-module consistency checks
# (tests/unit/cli/test_system_default_classification_consistency.py) —
# no longer consumed by parsing directly since the Typer conversion
# (marco 4A, 2026-08-20): src/cli/commands/experiment.py's
# _experiment_command declares the same classification via its per-option
# callbacks and the explicit typer_filter_list_or_system_default() call
# for where/exclude — see that module for the real, executed source of
# truth.
SYSTEM_DEFAULT_SUPPORTED = {
    'randomization_seed', 'system_prompt', 'user_prompt',
    'max_reasoning', 'max_tokens', 'reasoning', 'repeat_penalty',
    'model_seed', 'temperature', 'top_k', 'top_p', 'reasoning_tokens',
    'vision', 'structured', 'add_questions', 'provider_lock',
}
SYSTEM_DEFAULT_FORBIDDEN = {
    'create_experiment', 'experiment', 'remove_experiment', 'url',
}


def _create_experiment_with_config(
    name: str, args: ExperimentParsedArgs, conn, logger, *, commit: bool = True,
) -> Experiment:
    """Create experiment with resolved configuration from ConfigResolver.

    This is the canonical experiment creation path used by both standalone
    (--create-experiment) and composite (--create-experiment --add-model) flows.

    This function:
    - Uses ConfigResolver to build experiment config (ensures .env defaults are applied)
    - Generates experiment_id with 'exp_' prefix
    - Saves experiment via ExperimentRepository
    - Returns the created Experiment object
    - Respects docs/contracts/system-default-semantics.md (FORCE_SYSTEM_DEFAULT handling)

    Args:
        name: Experiment name.
        args: Parsed CLI arguments with configuration values.
        conn: Database connection.
        logger: Logger instance for audit logging.
        commit: Whether to commit immediately (default). The composite
            flow (bcllm.py::_handle_composite_flow) passes False to
            participate in its src.db.unit_of_work.UnitOfWork scope — see
            docs/status/composite-flow-unit-of-work-design.md.

    Returns:
        Created Experiment object with experiment_id, name, and config_json.

    Raises:
        ValueError: If experiment name is empty or already exists.
    """
    repo = ExperimentRepository(conn)
    
    # Check for existing experiment
    existing = repo.get_by_name(name)
    if existing:
        logger.error(f"EXPERIMENT_CREATE | name={name} | error=Already exists")
        raise ValueError(f"Experiment already exists: {name}")
    
    logger.info(f"EXPERIMENT_CREATE | name={name}")
    
    # Use ConfigResolver to build complete experiment config
    # This ensures .env defaults are applied following CLI > .env > NULL priority
    resolver = ConfigResolver()
    env_dict = resolver.load_env()
    config_dict = resolver.build_experiment_config_dict(args)
    
    # Serialize config to JSON (compact format)
    config_json = json.dumps(config_dict, indent=None, separators=(',', ':'))
    
    # Generate config hash for integrity checking
    config_hash = hashlib.sha256(config_json.encode('utf-8')).hexdigest()
    
    # Create experiment with exp_ prefix ID
    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=name,
        description="",
        config_json=config_json,
        config_hash=config_hash,
    )
    
    # Save to database
    repo.save(experiment, commit=commit)

    emit_event(
        logger, Event.EXPERIMENT_CREATED,
        name=name, experiment_id=experiment.experiment_id,
    )

    return experiment


def handle_create_experiment(args, conn) -> int:
    """Handle --create-experiment command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    logger = get_logger('cli.experiment')
    name = args.create_experiment

    if not name or not name.strip():
        print("Error: Experiment name cannot be empty.", file=sys.stderr)
        return 1

    # Validate boolean CLI values before creation
    if args.vision is not None and not _validate_bool_value(args.vision):
        print(f"Error: Invalid value for --vision: {args.vision}", file=sys.stderr)
        print("Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null", file=sys.stderr)
        print("Note: 'none' is NOT a valid value - it is treated as a literal string", file=sys.stderr)
        print("Example: --vision true", file=sys.stderr)
        return 1

    if args.structured is not None and not _validate_bool_value(args.structured):
        print(f"Error: Invalid value for --structured: {args.structured}", file=sys.stderr)
        print("Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null", file=sys.stderr)
        print("Note: 'none' is NOT a valid value - it is treated as a literal string", file=sys.stderr)
        print("Example: --structured false", file=sys.stderr)
        return 1

    if args.provider_lock is not None and not _validate_bool_value(args.provider_lock):
        print(f"Error: Invalid value for --provider-lock: {args.provider_lock}", file=sys.stderr)
        print("Valid values: true, false, system-default (case-insensitive)", file=sys.stderr)
        return 1

    # Use canonical experiment creation function
    try:
        experiment = _create_experiment_with_config(name, args, conn, logger)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    print(f"✓ Experiment '{experiment.name}' created (ID: {experiment.experiment_id})")

    # Add models at creation time if specified
    if args.add_model:
        resolver = ConfigResolver()
        resolver.load_env()
        exit_code = _add_models_at_creation(args, experiment, conn, resolver)
        if exit_code != 0:
            return exit_code

    # Create question snapshots
    exit_code = _create_question_snapshots(args, experiment, conn)
    if exit_code != 0:
        return exit_code

    return 0


def _validate_bool_value(value: str | type[FORCE_SYSTEM_DEFAULT]) -> bool:
    """Validate boolean CLI value.

    Args:
        value: CLI value (may be FORCE_SYSTEM_DEFAULT for 'null' input)

    Returns:
        True if value is valid boolean ('true' or 'false'), False otherwise.

    Note:
        - 'null' (FORCE_SYSTEM_DEFAULT) is NOT a valid boolean - it represents explicit absence
        - 'none' is treated as literal string, not as None
        - Absent flag (None) is OK - will use default
    """
    if value is FORCE_SYSTEM_DEFAULT:
        return True  # 'null' is valid - represents explicit absence (will be normalized to None)
    if value is None:
        return True  # Absent flag is OK (will use default)
    if isinstance(value, str):
        return value.lower() in ('true', 'false')
    return False


def _add_models_at_creation(args, experiment: Experiment, conn, resolver: ConfigResolver) -> int:
    """Add model variants to experiment at creation time.

    Uses complete config from CLI > .env > NULL.

    Args:
        args: Parsed command-line arguments from bcllm_experiment.py's own
            parser (the same Namespace handle_create_experiment received —
            carries --reasoning/--max-tokens/--temperature/etc. alongside
            --add-model). Until 2026-08-18 this function instead received
            only `args.add_model` and built a fabricated stand-in object
            (`type('Args', (), {'experiment': experiment})()`) with no
            model-level attributes at all, so every CLI flag other than
            the model ID itself was silently discarded for any model
            added via `--create-experiment ... --add-model X --reasoning
            high` in a single command. See docs/status/known-issues.md.
        experiment: Experiment to add models to.
        conn: Database connection.
        resolver: ConfigResolver instance.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    var_repo = VariantRepository(conn)

    for model_id in args.add_model:
        if not validate_model_id(model_id):
            print(f"Error: Invalid model ID format: {model_id}", file=sys.stderr)
            print("Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)", file=sys.stderr)
            return 1

        config = resolver.build_model_config_dict(args, experiment)

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
        emit_event(
            get_logger('cli.experiment'), Event.MODEL_ADDED,
            experiment=experiment.name, model_id=model_id, variant_signature=variant_signature,
        )
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
        - If --add-questions null (FORCE_SYSTEM_DEFAULT): use ALL questions from dataset (no .env fallback)
        - If --add-questions provided with value: use specified questions
        - If --add-questions NOT provided (None): check DEFAULT_QUESTIONS from .env
        - If neither provided: select ALL questions from dataset
        - Apply QUESTIONS_STATUS_ADD from .env for filtering (if --where not provided)
        - Apply QUESTIONS_STATUS_EXCLUDE from .env for filtering (if --exclude not provided)
        - Fails loudly if dataset invalid (no placeholders)
    """
    resolver = ConfigResolver()
    env_dict = resolver.load_env()

    dataset_path = env_dict.get('QUESTIONS_DATASET_PATH')
    
    # Validate mandatory field --dataset-path rejects 'system-default'
    # Note: dataset-path is configured via .env, not CLI flag
    # If user sets QUESTIONS_DATASET_PATH=system-default in .env, it will be FORCE_SYSTEM_DEFAULT
    if dataset_path is FORCE_SYSTEM_DEFAULT:
        print(
            "Error: QUESTIONS_DATASET_PATH in .env cannot be set to 'system-default'.",
            file=sys.stderr
        )
        print("Please provide a valid dataset path.", file=sys.stderr)
        return 1
    
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

    # Check if add_questions was explicitly set (even if FORCE_SYSTEM_DEFAULT)
    add_questions_value = getattr(args, 'add_questions', None)

    if add_questions_value is FORCE_SYSTEM_DEFAULT:
        # User explicitly passed --add-questions null → use ALL questions (no filter)
        selected_questions = questions
    elif add_questions_value is not None:
        # User provided a value → use it
        try:
            selected_questions = loader.parse_question_spec(add_questions_value, questions)
        except ValueError as e:
            print(f"Error: Invalid question specification: {e}", file=sys.stderr)
            print("Valid formats:", file=sys.stderr)
            print("  --questions \"1, 3, 5\"    (comma-separated, quote if spaces)", file=sys.stderr)
            print("  --questions \"1-10\"       (range)", file=sys.stderr)
            print("  --questions \"1, 3-5, Q10\" (mixed)", file=sys.stderr)
            return 1
    else:
        # Not specified → fallback to DEFAULT_QUESTIONS from .env
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

    # args.where/args.exclude were already normalized (system-default ->
    # FORCE_SYSTEM_DEFAULT, contradiction/deprecated-null rejected) in
    # main() before this function was ever reached — see
    # normalize_filter_list_or_system_default. FORCE_SYSTEM_DEFAULT is
    # explicitly checked FIRST because it's falsy, same as "not provided"
    # ([]) — the two must NOT collapse to the same branch here: only the
    # "not provided" case should fall back to .env (bootstrap semantics).
    if args.where is FORCE_SYSTEM_DEFAULT:
        include_filters = []
    elif args.where:
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

    if args.exclude is FORCE_SYSTEM_DEFAULT:
        exclude_filters = []
    elif args.exclude:
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

        payload = build_question_snapshot_payload(question)

        snapshot = QuestionSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            json_question_id=source_id,
            question_position=question_position,
            question_payload=json.dumps(payload, ensure_ascii=False),
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
    logger = get_logger('cli.experiment')
    repo = ExperimentRepository(conn)
    name = args.experiment
    experiment = repo.get_by_name(name)

    if not experiment:
        logger.error(f"EXPERIMENT_SHOW | name={name} | error=Not found")
        print(f"Error: Experiment not found: {name}", file=sys.stderr)
        return 1

    import json
    config = json.loads(experiment.config_json) if experiment.config_json else {}

    logger.debug(f"EXPERIMENT_SHOW | name={name} | experiment_id={experiment.experiment_id}")
    print(f"Experiment: {experiment.name}")
    print(f"  ID: {experiment.experiment_id}")
    print(f"  Description: {experiment.description or '(none)'}")
    print(f"  Config:")
    print(f"    randomization_seed: {config.get('RANDOMIZATION_SEED', 'None')}")
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
    logger = get_logger('cli.experiment')
    repo = ExperimentRepository(conn)
    experiments = repo.list_all()

    if not experiments:
        logger.debug("EXPERIMENT_LIST | count=0")
        print("No experiments found.")
        return 0

    logger.debug(f"EXPERIMENT_LIST | count={len(experiments)}")
    print(f"{'Name':<30} {'ID':<20}")
    print("-" * 50)
    for exp in experiments:
        print(f"{exp.name:<30} {exp.experiment_id:<20}")

    return 0


def handle_remove_experiment(args, conn) -> int:
    """Handle --remove-experiment command.

    Deliberately disabled (returns 1, touches nothing) pending a product
    decision on how experiment removal should behave. The underlying
    implementation is ExperimentRepository.delete(), a hard delete that
    (per src/db/schema.py's ON DELETE CASCADE) also removes every
    question_snapshots, model_variants, and runs row for the experiment —
    with no soft-delete mechanism anywhere in the schema. That is in
    direct tension with docs/contracts/immutability.md ("Question
    Snapshots ... Cannot be deleted") and docs/contracts/
    configuration-hierarchy.md ("Model variant configuration is frozen at
    creation"). Command was previously unreachable entirely (a routing
    bug sent it, and --list-experiments/--help/--review-*, to a
    Mode.INVALID matrix entry that didn't exist); fixing that routing bug
    made this reachable for the first time and surfaced the conflict —
    disabled here rather than shipped, until there's an explicit decision
    on the right removal semantics. See docs/status/known-issues.md.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        1, always. No database access.
    """
    emit_event(
        get_logger('cli.experiment'), Event.MUTATION_REFUSED,
        experiment=args.remove_experiment, reason="remove_experiment_disabled",
    )
    print(
        "Error: --remove-experiment is currently disabled.\n"
        "Removing an experiment would hard-delete its question snapshots, "
        "model variants, and runs, which conflicts with this project's "
        "immutability contract (docs/contracts/immutability.md) and "
        "configuration-hierarchy contract (docs/contracts/configuration-hierarchy.md). "
        "See docs/status/known-issues.md for details; this will be revisited "
        "in a future planning pass.",
        file=sys.stderr,
    )
    return 1


def handle_modify_provider_lock(args, conn) -> int:
    """Handle --provider-lock on an existing experiment.

    Deliberately disabled (returns 1, touches nothing) — direct user
    decision, 2026-08-18 (Fase 3, item 8): rewriting `config_json`/
    `config_hash` of an already-created experiment (even for a single
    field like PROVIDER_LOCK) contradicts docs/contracts/immutability.md
    ("Once an entity ... is created, its configuration is frozen") and
    docs/contracts/configuration-hierarchy.md. This was the only "update
    experiment" mutation path anywhere in the system; removing it, not
    formalizing it as an exception, was the explicit call — the user's
    own words: "Provider-lock poder ser alterado no config_json é
    provavelmente uma falha minha... Mantendo a imutabilidade definida do
    sistema." Mirrors handle_remove_experiment's disabled-command
    convention exactly. See docs/status/known-issues.md.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        1, always. No database access.
    """
    emit_event(
        get_logger('cli.experiment'), Event.MUTATION_REFUSED,
        experiment=args.experiment, reason="provider_lock_modify_disabled",
    )
    print(
        "Error: --provider-lock on an existing --experiment is currently disabled.\n"
        "Modifying PROVIDER_LOCK after creation would rewrite the experiment's "
        "frozen config_json/config_hash, which conflicts with this project's "
        "immutability contract (docs/contracts/immutability.md). Set --provider-lock "
        "at --create-experiment time instead; to change it for an existing "
        "experiment, create a new one. See docs/status/known-issues.md for details.",
        file=sys.stderr,
    )
    return 1


def main(mode: Mode) -> int:
    """Main entry point.

    Args:
        mode: The CLI mode (CREATE, MODIFY, EXECUTE, INVALID).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    _validate_expected_mode(mode)
    try:
        args = parse_experiment_argv(sys.argv[1:])
    except ParserExit as e:
        return e.status

    conn = get_database_connection()

    try:
        if args.create_experiment:
            return handle_create_experiment(args, conn)
        elif args.experiment:
            # Check if this is a modify operation with --provider-lock
            if args.provider_lock is not None:
                return handle_modify_provider_lock(args, conn)
            return handle_show_experiment(args, conn)
        elif args.list_experiments:
            return handle_list_experiments(args, conn)
        elif args.remove_experiment:
            return handle_remove_experiment(args, conn)
        else:
            # Unreachable: parse_experiment_argv's mutex-group check
            # already guarantees exactly one of create_experiment/
            # experiment/list_experiments/remove_experiment is set — kept
            # only as a defensive fallback, matching the original
            # argparse version's equivalent branch.
            print("Error: no valid experiment action specified.", file=sys.stderr)
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
