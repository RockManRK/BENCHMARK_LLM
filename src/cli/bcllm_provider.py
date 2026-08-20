#!/usr/bin/env python3
"""Provider resolution CLI module.

This module provides the --resolve-providers command that resolves PROVIDER
for all model variants in an experiment that have PROVIDER = null in their config.

Usage:
    bcllm --experiment <name> --resolve-providers

Exit Codes:
    0: Success (all providers resolved or no resolution needed)
    1: Error (experiment not found, API key missing, or resolution failed)

The command is idempotent — running multiple times is safe and will skip
already-resolved variants.
"""

import argparse
import json
import os
import sys

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core.argv_utils import parse_args_normalized
from src.db.repository import ExperimentRepository, VariantRepository
from src.api.provider_resolver import ProviderResolver


def _validate_expected_mode(mode: Mode) -> None:
    """Validate that received mode matches expected mode for this module.

    Args:
        mode: The CLI mode passed from dispatcher.

    Raises:
        SystemExit: If mode is invalid for this module.
    """
    VALID_MODES = [Mode.MODIFY]

    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"--resolve-providers is a MODIFY operation.",
            file=sys.stderr
        )
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for --resolve-providers command.

    Returns:
        ArgumentParser configured with resolve-providers command.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_provider.py",
        description="Provider resolution for model variants",
    )

    parser.add_argument(
        "--experiment",
        required=True,
        metavar="NAME",
        help="Experiment name",
    )

    parser.add_argument(
        "--resolve-providers",
        action="store_true",
        help="Resolve providers for all variants with PROVIDER=null in the experiment",
    )

    return parser


# Explicit opt-in classification for system-default recognition — see
# src/core/special_config_values.py::normalize_special_config_values and
# docs/contracts/system-default-semantics.md for the full SUPPORTED/
# FORBIDDEN/NOT_APPLICABLE contract this implements. --resolve-providers
# is a boolean flag (NOT_APPLICABLE); --experiment is FORBIDDEN for
# consistency with every other module's identity-selector flags — see
# docs/status/known-issues.md (Essence Guardian finding, 2026-08-19).
SYSTEM_DEFAULT_FORBIDDEN = {
    'experiment',
}


def handle_resolve_providers(args, conn) -> int:
    """Resolve providers for all variants with PROVIDER=null in the experiment.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    var_repo = VariantRepository(conn)

    # Load experiment by name
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    # Get strategy from experiment config
    exp_config = json.loads(experiment.config_json) if experiment.config_json else {}
    strategy = exp_config.get("PROVIDER_SELECTION_STRATEGY", "first")

    # Check AUTO_PROVIDER_LOCK
    provider_lock = exp_config.get("PROVIDER_LOCK", False)
    if not provider_lock:
        print(
            f"Warning: PROVIDER_LOCK is not enabled for experiment '{args.experiment}'.",
            file=sys.stderr
        )
        print(
            "Providers will be resolved but not required for execution.",
            file=sys.stderr
        )

    # Get all model variants for experiment
    variants = var_repo.list_by_experiment(experiment.experiment_id)

    if not variants:
        print(f"No model variants found in experiment '{args.experiment}'.")
        return 0

    # Initialize API key from environment
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set in environment", file=sys.stderr)
        return 1

    resolver = ProviderResolver(api_key)

    report = {"resolved": [], "skipped": [], "failed": []}

    for variant in variants:
        config = json.loads(variant.config) if variant.config else {}

        # Skip if PROVIDER already set (idempotency)
        if config.get("PROVIDER") is not None:
            report["skipped"].append({
                "variant_id": variant.variant_id,
                "model_id": variant.model_id,
                "reason": "already_resolved",
            })
            continue

        # Resolve provider
        try:
            resolution = resolver.resolve(variant.model_id, strategy)

            # Update config with resolved provider
            config["PROVIDER"] = resolution.provider_slug
            variant.config = json.dumps(config)
            var_repo.save(variant)

            report["resolved"].append({
                "variant_id": variant.variant_id,
                "model_id": variant.model_id,
                "provider": resolution.provider_slug,
                "strategy": resolution.strategy_applied,
                "was_fallback": resolution.was_fallback,
            })

            if resolution.was_fallback and resolution.warning:
                print(f"Warning: {resolution.warning}", file=sys.stderr)

        except Exception as e:
            report["failed"].append({
                "variant_id": variant.variant_id,
                "model_id": variant.model_id,
                "reason": str(e),
            })

    resolver.close()

    # Print summary report
    print(f"\nProvider Resolution Report for experiment '{args.experiment}':")
    print(f"  Resolved: {len(report['resolved'])}")
    print(f"  Skipped:  {len(report['skipped'])}")
    print(f"  Failed:   {len(report['failed'])}")

    if report["resolved"]:
        print("\nResolved providers:")
        for r in report["resolved"]:
            fallback_note = " (fallback)" if r["was_fallback"] else ""
            print(f"  {r['model_id']} -> {r['provider']} (via {r['strategy']}{fallback_note})")

    if report["failed"]:
        print("\nFailed:")
        for f in report["failed"]:
            print(f"  {f['model_id']}: {f['reason']}")

    return 0 if len(report["failed"]) == 0 else 1


def main(mode: Mode) -> int:
    """Main entry point.

    Args:
        mode: The CLI mode (MODIFY, INVALID).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    _validate_expected_mode(mode)
    parser = create_parser()
    try:
        args = parse_args_normalized(parser, forbidden=SYSTEM_DEFAULT_FORBIDDEN)
    except argparse.ArgumentError as e:
        # See src/cli/bcllm_model.py::main for why this is caught here
        # rather than inside parse_args_normalized itself.
        parser.error(str(e))

    conn = get_database_connection()

    try:
        if args.resolve_providers:
            return handle_resolve_providers(args, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
