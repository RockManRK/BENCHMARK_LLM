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
    2: Usage error (bad/unrecognized argument, FORBIDDEN system-default value)

--add-model's single-action pipeline (argv -> parse/normalize/validate ->
AddModelRequest -> add_model_action -> AddModelResult) is used identically
by main() (standalone) and bcllm.py's composite --create-experiment flow —
see run_add_model()'s docstring and docs/status/known-issues.md ("same
action, same path" invariant) for why this exists: a prior version had
bcllm.py's composite flow re-parsing argv with a raw, un-normalized parser,
silently bypassing system-default handling and, on any argparse-level
usage error, skipping the composite flow's experiment rollback entirely.
"""

import argparse
import json
import sys
import uuid
from dataclasses import dataclass

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core.argv_utils import parse_args_normalized, has_flag, NonExitingArgumentParser, ParserExit
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT, ForceSystemDefault, parse_int_or_system_default, parse_float_or_system_default
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
        NonExitingArgumentParser configured with all model commands — see
        src/core/argv_utils.py for why this is NOT a plain
        argparse.ArgumentParser: --add-model can run inside bcllm.py's
        composite flow, where an uncontrolled sys.exit() (argparse's
        default for both --help and any usage error) would skip the
        composite flow's experiment rollback.
    """
    parser = NonExitingArgumentParser(
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

    # Model configuration options (all 11 model-level keys from contract)
    parser.add_argument(
        "--url",
        metavar="URL",
        help="BASE_URL - Model endpoint URL",
    )
    parser.add_argument(
        "--max-reasoning",
        type=parse_int_or_system_default,
        metavar="N",
        help="MODEL_MAX_TOKENS_REASONING - Maximum reasoning tokens",
    )
    parser.add_argument(
        "--max-tokens",
        type=parse_int_or_system_default,
        metavar="N",
        help="MODEL_MAX_TOKENS_TOTAL - Maximum total tokens",
    )
    parser.add_argument(
        "--reasoning",
        choices=["none", "minimal", "low", "medium", "high", "xhigh", "system-default"],
        help="MODEL_REASONING_EFFORT - Reasoning effort level",
    )
    parser.add_argument(
        "--repeat-penalty",
        type=parse_float_or_system_default,
        metavar="N",
        help="MODEL_REPEAT_PENALTY - Repetition penalty",
    )
    parser.add_argument(
        "--temperature",
        type=parse_float_or_system_default,
        metavar="N",
        help="MODEL_TEMPERATURE - Sampling temperature",
    )
    parser.add_argument(
        "--top-k",
        type=parse_int_or_system_default,
        metavar="N",
        help="MODEL_TOP_K - Top-K sampling",
    )
    parser.add_argument(
        "--top-p",
        type=parse_float_or_system_default,
        metavar="N",
        help="MODEL_TOP_P - Top-P sampling",
    )
    parser.add_argument(
        "--reasoning-tokens",
        type=parse_int_or_system_default,
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
    parser.add_argument(
        "--provider",
        type=str,
        metavar="PROVIDER_SLUG",
        help="OpenRouter provider slug (e.g., deepinfra/turbo)",
    )
    parser.add_argument(
        "--model-seed",
        type=parse_int_or_system_default,
        metavar="N",
        help="MODEL_SEED - Sent as the API request's 'seed' field for "
             "deterministic inference. Distinct from Randomization Seed "
             "(--randomization-seed on --add-run), which controls only "
             "answer-option shuffling and is never sent to the API.",
    )

    return parser


# Explicit opt-in classification for system-default recognition — see
# src/core/special_config_values.py::normalize_special_config_values and
# docs/contracts/system-default-semantics.md for the full SUPPORTED/
# FORBIDDEN/NOT_APPLICABLE contract this implements.
SYSTEM_DEFAULT_SUPPORTED = {
    'max_reasoning', 'max_tokens', 'reasoning', 'repeat_penalty',
    'temperature', 'top_k', 'top_p', 'reasoning_tokens',
    'vision', 'structured', 'provider', 'model_seed',
}
SYSTEM_DEFAULT_FORBIDDEN = {
    'experiment', 'url', 'add_model', 'remove_model',
}


@dataclass(frozen=True)
class AddModelRequest:
    """Structured input for add_model_action — built by run_add_model()
    from parsed+normalized CLI args, never argv or argparse.Namespace
    directly. Field names mirror the CLI dest names 1:1 so this can be
    passed straight into ConfigResolver.build_model_config_dict() (which
    reads fields via getattr, duck-typed — works on any object, not just
    argparse.Namespace)."""
    experiment: str
    add_model: str
    url: str | ForceSystemDefault | None = None
    max_reasoning: int | ForceSystemDefault | None = None
    max_tokens: int | ForceSystemDefault | None = None
    reasoning: str | ForceSystemDefault | None = None
    repeat_penalty: float | ForceSystemDefault | None = None
    temperature: float | ForceSystemDefault | None = None
    top_k: int | ForceSystemDefault | None = None
    top_p: float | ForceSystemDefault | None = None
    reasoning_tokens: int | ForceSystemDefault | None = None
    vision: str | ForceSystemDefault | None = None
    structured: str | ForceSystemDefault | None = None
    provider: str | ForceSystemDefault | None = None
    model_seed: int | ForceSystemDefault | None = None


@dataclass(frozen=True)
class AddModelResult:
    """Structured output from add_model_action.

    exit_code: 0 success, 1 operational/domain error (not found, duplicate,
        invalid value), 2 usage error (none originate inside the action
        today, but the field exists so a future validation can report one
        without changing the shape callers depend on).
    error: single error message (may contain embedded '\\n' for
        multi-line detail, matching the historical multi-print() messages)
        — None on success.
    """
    exit_code: int
    error: str | None = None
    variant_id: str | None = None
    variant_signature: str | None = None


def add_model_action(request: AddModelRequest, conn, *, commit: bool = True) -> AddModelResult:
    """The shared --add-model action: validation, config resolution,
    duplicate check, and the DB write. Pure — no argv/Namespace, no
    print(), no sys.exit(). Used identically by the standalone and
    composite adapters (see run_add_model).

    commit: whether the DB write commits immediately (default). The
        composite flow (bcllm.py) passes False to participate in its
        src.db.unit_of_work.UnitOfWork scope — see
        docs/status/composite-flow-unit-of-work-design.md. Model-ID/
        vision/structured validation and the variant-signature duplicate
        check happen before any write regardless of this flag."""
    from src.core.config_resolver import ConfigResolver

    if not validate_model_id(request.add_model):
        return AddModelResult(exit_code=1, error=(
            f"Invalid model ID format: {request.add_model}\n"
            "Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)"
        ))

    if request.vision is not None and not _validate_bool_value(request.vision):
        return AddModelResult(exit_code=1, error=(
            f"Invalid value for --vision: {request.vision}\n"
            "Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null\n"
            "Note: 'none' is NOT a valid value - it is treated as a literal string"
        ))

    if request.structured is not None and not _validate_bool_value(request.structured):
        return AddModelResult(exit_code=1, error=(
            f"Invalid value for --structured: {request.structured}\n"
            "Valid values: true, false, TRUE, FALSE, True, False, null, NULL, Null\n"
            "Note: 'none' is NOT a valid value - it is treated as a literal string"
        ))

    exp_repo = ExperimentRepository(conn)
    var_repo = VariantRepository(conn)

    experiment = exp_repo.get_by_name(request.experiment)
    if not experiment:
        return AddModelResult(exit_code=1, error=f"Experiment not found: {request.experiment}")

    resolver = ConfigResolver()
    resolver.load_env()

    config = resolver.build_model_config_dict(request, experiment)

    variant_signature = generate_variant_signature(request.add_model, config)

    existing = var_repo.get_by_signature(experiment.experiment_id, variant_signature)
    if existing:
        return AddModelResult(exit_code=1, error=(
            f"Variant '{variant_signature}' already exists in experiment '{request.experiment}'"
        ))

    variant = ModelVariant(
        variant_id=f"var_{uuid.uuid4().hex[:8]}",
        experiment_id=experiment.experiment_id,
        model_id=request.add_model,
        variant_signature=variant_signature,
        config=json.dumps(config),
    )

    var_repo.save(variant, commit=commit)
    return AddModelResult(exit_code=0, variant_id=variant.variant_id, variant_signature=variant_signature)


def parse_add_model_request(argv: list[str]) -> AddModelRequest:
    """Pure: argv -> parse/normalize/validate -> AddModelRequest. No
    database connection is opened and no I/O happens beyond argparse's
    own stdout/stderr usage-error output. Raises ParserExit(status) for
    any usage error (bad choice, FORBIDDEN system-default, unrecognized
    flag, --help) — the caller decides what to do with that exit status.

    Shared by run_add_model (standalone) and bcllm.py's composite flow,
    which calls this for every requested --add-* action BEFORE opening a
    database connection or acquiring the composite flow's transaction
    lock — see docs/status/composite-flow-unit-of-work-design.md point 3:
    pure syntactic parsing/validation must never wait on a lock.
    """
    parser = create_parser()
    try:
        args = parse_args_normalized(
            parser, argv,
            supported=SYSTEM_DEFAULT_SUPPORTED,
            forbidden=SYSTEM_DEFAULT_FORBIDDEN,
        )
    except (argparse.ArgumentError, ValueError) as e:
        parser.error(str(e))  # raises ParserExit(2, ...)

    return AddModelRequest(
        experiment=args.experiment,
        add_model=args.add_model,
        url=args.url,
        max_reasoning=args.max_reasoning,
        max_tokens=args.max_tokens,
        reasoning=args.reasoning,
        repeat_penalty=args.repeat_penalty,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
        reasoning_tokens=args.reasoning_tokens,
        vision=args.vision,
        structured=args.structured,
        provider=args.provider,
        model_seed=args.model_seed,
    )


def run_add_model(
    argv: list[str] | None = None, conn=None, *,
    commit: bool = True, request: AddModelRequest | None = None,
) -> int:
    """Single entry point for the --add-model action: parsing, system-
    default normalization/classification, request construction,
    dispatch to add_model_action, and result presentation (printing) —
    used identically by main() (standalone, real sys.argv) and
    bcllm.py's composite flow. Both go through this exact same code, so a
    fix here applies to both callers automatically — no divergent
    duplicate logic to keep in sync.

    Never lets argparse's own sys.exit() escape (create_parser() returns
    a NonExitingArgumentParser) — always returns an exit code.

    A usage error NEVER opens a database connection: when `conn` is not
    supplied, get_database_connection() is only called AFTER parsing
    succeeds, never before.

    Args:
        argv: Argument strings for THIS action only (no program name).
            Ignored if `request` is given directly.
        conn: An already-open connection to reuse — the composite flow
            passes its own, shared across multiple actions in one
            invocation, and this function does NOT close it. When None
            (standalone), this function opens (after a successful parse)
            and closes its own connection.
        commit: Passed straight to add_model_action — see its docstring.
        request: A pre-parsed AddModelRequest. When given, `argv` is
            ignored entirely and no parsing happens here — used by the
            composite flow, which pre-parses every requested action's
            argv (via parse_add_model_request) before ever opening a
            connection, then calls this function only for its DB-facing
            half (dispatch + printing), reusing this exact same code
            path rather than duplicating it.

    Returns:
        0 success, 1 operational/domain error, 2 usage error.
    """
    if request is None:
        try:
            request = parse_add_model_request(argv)
        except ParserExit as e:
            return e.status

    owns_conn = conn is None
    if owns_conn:
        conn = get_database_connection()
    try:
        result = add_model_action(request, conn, commit=commit)

        if result.exit_code == 0:
            print(f"✓ Model variant '{result.variant_signature}' added to experiment '{request.experiment}'")
        else:
            print(f"Error: {result.error}", file=sys.stderr)

        return result.exit_code
    finally:
        if owns_conn:
            conn.close()


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
        Exit code (0 for success, 1 for error, 2 for usage error).
    """
    _validate_expected_mode(mode)
    argv = sys.argv[1:]

    # --add-model delegates to the exact same single-action pipeline the
    # composite flow uses (see run_add_model's docstring) — peeked via
    # has_flag before parsing, mirroring how bcllm.py's composite flow
    # already decides which action to run. No conn passed: run_add_model
    # opens its own only after parsing succeeds.
    if has_flag(argv, '--add-model'):
        return run_add_model(argv)

    # --list-models / --remove-model have no composite-flow counterpart —
    # parsed and dispatched directly, same shape as before, just adapted
    # to NonExitingArgumentParser (parser.error()/--help now raise
    # ParserExit instead of calling sys.exit() themselves).
    parser = create_parser()
    try:
        try:
            args = parse_args_normalized(
                parser, argv,
                supported=SYSTEM_DEFAULT_SUPPORTED,
                forbidden=SYSTEM_DEFAULT_FORBIDDEN,
            )
        except (argparse.ArgumentError, ValueError) as e:
            parser.error(str(e))
    except ParserExit as e:
        if e.status != 0:
            return e.status
        return 0  # --help or other clean parser exit

    conn = get_database_connection()

    try:
        if args.list_models:
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
