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

from src_v2.cli.database import get_database_connection
from src_v2.db.models import ModelVariant
from src_v2.db.repository import ExperimentRepository, VariantRepository
from src_v2.utils.variant_signature import generate_variant_signature
from src_v2.validators.model_id_validator import validate_model_id


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
        dest="max_reasoning",
        help="MODEL_MAX_TOKENS_REASONING - Maximum reasoning tokens",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        metavar="N",
        dest="max_tokens",
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
        dest="repeat_penalty",
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
        dest="top_k",
        help="MODEL_TOP_K - Top-K sampling",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        metavar="N",
        dest="top_p",
        help="MODEL_TOP_P - Top-P sampling",
    )
    parser.add_argument(
        "--reasoning-tokens",
        type=int,
        metavar="N",
        dest="reasoning_tokens",
        help="MODEL_MAX_TOKENS_REASONING - Maximum reasoning tokens",
    )
    parser.add_argument(
        "--vision",
        type=str,
        metavar="VALUE",
        help="MODEL_VISION - Enable vision (true/false/NULL)",
    )
    parser.add_argument(
        "--structured",
        type=str,
        metavar="VALUE",
        help="STRUCTURED_OUTPUTS - Enable structured output (true/false/NULL)",
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
    from src_v2.core.config_resolver import ConfigResolver

    if not validate_model_id(args.add_model):
        print(f"Error: Invalid model ID format: {args.add_model}", file=sys.stderr)
        print("Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)", file=sys.stderr)
        return 1

    if args.vision is not None and not _validate_bool_value(args.vision):
        print(f"Error: Invalid value for --vision: {args.vision}", file=sys.stderr)
        print("Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null", file=sys.stderr)
        return 1

    if args.structured is not None and not _validate_bool_value(args.structured):
        print(f"Error: Invalid value for --structured: {args.structured}", file=sys.stderr)
        print("Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null", file=sys.stderr)
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


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = create_parser()
    args = parser.parse_args()

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
