#!/usr/bin/env python3
"""Model variant management CLI.

This module provides CLI commands for managing model variants within experiments:
- Add model variants to experiments
- List model variants in an experiment
- Remove model variants (soft delete)

Usage:
    bcllm_model.py --experiment <name> --add-model <model_id>
    bcllm_model.py --experiment <name> --list-models
    bcllm_model.py --experiment <name> --remove-model <variant_id>

Exit Codes:
    0: Success
    1: Validation error (not found, collision, invalid input)
"""

import argparse
import json
import sys
import uuid

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core.argv_utils import parse_args_normalized
from src.core.null_semantics import FORCE_SYSTEM_DEFAULT
from src.db.models import ModelVariant
from src.db.repository import ExperimentRepository, VariantRepository
from src.utils.variant_signature import generate_variant_signature
from src.validators.model_id_validator import validate_model_id


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
    # ACCEPT Mode.CREATE for composite flows (--create-experiment + --add-model)
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


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for model commands.

    Returns:
        ArgumentParser configured with all model commands.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_model.py",
        description="Model variant management",
    )

    parser.add_argument(
        "--experiment",
        required=True,
        metavar="NAME",
        help="Experiment name",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--add-model",
        metavar="MODEL_ID",
        help="Add model variant (format: provider/model-name)",
    )
    group.add_argument(
        "--list-models",
        action="store_true",
        help="List all models in experiment",
    )
    group.add_argument(
        "--remove-model",
        metavar="VARIANT_ID",
        help="Remove model variant (soft delete)",
    )

    parser.add_argument(
        "--output",
        choices=["console", "json", "csv", "markdown"],
        default="console",
        help="Output format",
    )

    # Model configuration options (all 10 model-level keys from contract)
    parser.add_argument(
        "--url",
        metavar="URL",
        help="BASE_URL - Model endpoint URL",
    )
    parser.add_argument(
        "--max-reasoning",
        type=int,
        metavar="N",
        help="MODEL_MAX_TOKENS_REASONING - Maximum reasoning tokens",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        metavar="N",
        help="MODEL_MAX_TOKENS_TOTAL - Maximum total tokens",
    )
    parser.add_argument(
        "--reasoning",
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help="MODEL_REASONING_EFFORT - Reasoning effort level",
    )
    parser.add_argument(
        "--repeat-penalty",
        type=float,
        metavar="N",
        help="MODEL_REPEAT_PENALTY - Repetition penalty",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        metavar="N",
        help="MODEL_TEMPERATURE - Sampling temperature",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        metavar="N",
        help="MODEL_TOP_K - Top-K sampling",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        metavar="N",
        help="MODEL_TOP_P - Top-P sampling",
    )
    parser.add_argument(
        "--reasoning-tokens",
        type=int,
        metavar="N",
        help="MODEL_MAX_TOKENS_REASONING - Maximum reasoning tokens",
    )
    parser.add_argument(
        "--vision",
        type=str,
        metavar="VALUE",
        help="Enable vision. Valid values: true, false, null (case-insensitive). Default: false",
    )
    parser.add_argument(
        "--structured",
        type=str,
        metavar="VALUE",
        help="Enable structured outputs. Valid values: true, false, null (case-insensitive). Default: false",
    )

    return parser


def handle_add_model(args, conn) -> int:
    """Handle --add-model command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    from src.core.config_resolver import ConfigResolver

    if not validate_model_id(args.add_model):
        print(f"Error: Invalid model ID format: {args.add_model}", file=sys.stderr)
        print("Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)", file=sys.stderr)
        return 1

    if args.vision is not None and not _validate_bool_value(args.vision):
        print(f"Error: Invalid value for --vision: {args.vision}", file=sys.stderr)
        print("Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null", file=sys.stderr)
        print("Note: 'none' is NOT a valid value - it is treated as a literal string", file=sys.stderr)
        return 1

    if args.structured is not None and not _validate_bool_value(args.structured):
        print(f"Error: Invalid value for --structured: {args.structured}", file=sys.stderr)
        print("Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null", file=sys.stderr)
        print("Note: 'none' is NOT a valid value - it is treated as a literal string", file=sys.stderr)
        return 1

    # Validate mandatory field --url rejects 'system-default'
    if args.url is FORCE_SYSTEM_DEFAULT:
        print("Error: --url is a mandatory field and cannot be set to 'system-default'.", file=sys.stderr)
        print("Please provide a valid URL or omit the flag to use .env default.", file=sys.stderr)
        return 1

    exp_repo = ExperimentRepository(conn)
    var_repo = VariantRepository(conn)

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    resolver = ConfigResolver()
    resolver.load_env()

    config = resolver.build_model_config_dict(args, experiment)

    variant_signature = generate_variant_signature(args.add_model, config)

    existing = var_repo.get_by_signature(experiment.experiment_id, variant_signature)
    if existing:
        print(f"Error: Variant '{variant_signature}' already exists in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    variant = ModelVariant(
        variant_id=f"var_{uuid.uuid4().hex[:8]}",
        experiment_id=experiment.experiment_id,
        model_id=args.add_model,
        variant_signature=variant_signature,
        config=json.dumps(config),
    )

    var_repo.save(variant)
    print(f"✓ Model variant '{variant_signature}' added to experiment '{args.experiment}'")
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


def handle_list_models(args, conn) -> int:
    """Handle --list-models command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    var_repo = VariantRepository(conn)

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    variants = var_repo.list_by_experiment(experiment.experiment_id)

    if not variants:
        print(f"No models in experiment '{experiment.name}'.")
        return 0

    # Print table with config display
    print(f"Models in experiment: {experiment.name}")
    print(f"{'ID':<20} {'Model':<30} {'Signature':<40} {'Config':<50}")
    print("-" * 140)
    for v in variants:
        config = json.loads(v.config) if v.config else {}
        label = config.get('label', '')
        config_display = f"{v.variant_signature} {label}" if label else v.variant_signature
        print(f"{v.variant_id:<20} {v.model_id:<30} {config_display:<40} {v.config:<50}")

    return 0


def handle_remove_model(args, conn) -> int:
    """Handle --remove-model command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    var_repo = VariantRepository(conn)

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    # Check variant exists
    variant = var_repo.get_by_id(args.remove_model)
    if not variant:
        print(f"Error: Variant not found: {args.remove_model}", file=sys.stderr)
        return 1

    # Check variant belongs to experiment
    if variant.experiment_id != experiment.experiment_id:
        print(f"Error: Variant '{args.remove_model}' is not in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    var_repo.delete(variant.variant_id)
    print(f"✓ Model '{variant.model_id}' removed from '{experiment.name}'")
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
    args = parse_args_normalized(parser)

    conn = get_database_connection()

    try:
        if args.add_model:
            return handle_add_model(args, conn)
        elif args.list_models:
            return handle_list_models(args, conn)
        elif args.remove_model:
            return handle_remove_model(args, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
