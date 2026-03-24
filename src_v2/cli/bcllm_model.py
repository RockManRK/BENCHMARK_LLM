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

    # Model configuration options (used with --add-model)
    parser.add_argument(
        "--variant-signature",
        metavar="SIG",
        help="Custom variant signature (default: auto-generated)",
    )
    parser.add_argument(
        "--reasoning",
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        default="none",
        help="Reasoning effort level (default: none)",
    )
    parser.add_argument(
        "--vision",
        type=str,
        choices=["true", "false"],
        default="false",
        help="Enable vision capabilities (true/false, default: false)",
    )
    parser.add_argument(
        "--structured-output",
        type=str,
        choices=["true", "false"],
        default="false",
        help="Enable structured output format (true/false, default: false)",
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
    # Validate model ID format
    if not validate_model_id(args.add_model):
        print(f"Error: Invalid model ID format: {args.add_model}", file=sys.stderr)
        print("Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)", file=sys.stderr)
        return 1

    exp_repo = ExperimentRepository(conn)
    var_repo = VariantRepository(conn)

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    # Build config dict from CLI flags
    # Only include non-default values to keep signatures clean
    config = {}

    # Only include reasoning_effort if not 'none'
    if args.reasoning != 'none':
        config['reasoning_effort'] = args.reasoning
        config['label'] = f"({args.reasoning})"

    # Only include vision if enabled (default is false)
    if args.vision.lower() == 'true':
        config['vision'] = True

    # Only include structured if enabled (default is false)
    if args.structured_output.lower() == 'true':
        config['structured'] = True

    # Generate signature (or use custom)
    if args.variant_signature:
        variant_signature = args.variant_signature
    else:
        variant_signature = generate_variant_signature(args.add_model, config)

    # Check for signature collision
    existing = var_repo.get_by_signature(experiment.experiment_id, variant_signature)
    if existing:
        print(f"Error: Variant '{variant_signature}' already exists in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    # Create variant with config
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

    variants = var_repo.list_by_experiment(experiment.experiment_id, active_only=True)

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

    var_repo.deactivate(variant.variant_id)
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
