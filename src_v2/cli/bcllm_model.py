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
import re
import sys
import uuid

from src_v2.cli.database import get_database_connection
from src_v2.db.models import ModelVariant
from src_v2.db.repository import ExperimentRepository, VariantRepository


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
        "--reasoning-mode",
        choices=["off", "auto", "effort", "budget"],
        default="off",
        help="Reasoning mode",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high", "xhigh"],
        default="low",
        help="Reasoning effort",
    )
    parser.add_argument(
        "--vision",
        action="store_true",
        help="Enable vision",
    )
    parser.add_argument(
        "--structured-output",
        action="store_true",
        help="Enable structured outputs",
    )

    return parser


def validate_model_id(model_id: str) -> bool:
    """Validate model ID format (provider/model-name).

    Args:
        model_id: Model identifier to validate.

    Returns:
        True if format is valid, False otherwise.
    """
    pattern = r'^[a-z0-9_-]+/[a-z0-9_-]+$'
    return bool(re.match(pattern, model_id, re.IGNORECASE))


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

    # Generate or use custom variant signature
    variant_signature = args.variant_signature or args.add_model.replace('/', '_')

    # Check for signature collision
    existing = var_repo.get_by_signature(experiment.experiment_id, variant_signature)
    if existing:
        print(f"Error: Variant '{variant_signature}' already exists in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    # Create variant
    variant = ModelVariant(
        variant_id=f"var_{uuid.uuid4().hex[:8]}",
        experiment_id=experiment.experiment_id,
        model_id=args.add_model,
        variant_signature=variant_signature,
        reasoning_mode=args.reasoning_mode,
        reasoning_effort=args.reasoning_effort if args.reasoning_mode == 'effort' else None,
        max_output_tokens=None,
        vision_enabled=args.vision,
        structured_output=args.structured_output,
        web_access_enabled=False,
    )

    var_repo.save(variant)
    print(f"✓ Model '{variant.model_id}' added to '{experiment.name}' (ID: {variant.variant_id})")
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

    # Print table
    print(f"Models in experiment: {experiment.name}")
    print(f"{'ID':<20} {'Model':<30} {'Mode':<10} {'Vision':<8} {'Structured':<12}")
    print("-" * 80)
    for v in variants:
        vision_str = 'Yes' if v.vision_enabled else 'No'
        structured_str = 'Yes' if v.structured_output else 'No'
        print(f"{v.variant_id:<20} {v.model_id:<30} {v.reasoning_mode:<10} {vision_str:<8} {structured_str:<12}")

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
