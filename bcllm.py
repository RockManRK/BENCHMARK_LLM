#!/usr/bin/env python3
"""CLI entry point — dispatches exclusively to src."""
import os
import sys
from pathlib import Path

from src.core.mode import Mode
from src.core.mode_resolver import resolve_mode
from src.core.module_resolver import resolve_module
from src.core.mode_matrix import validate_mode_matrix, ModeMatrixError
from src.utils.logging_config import setup_logging, LoggingConfig


def route_to_v2(module_name: str, mode: Mode) -> int:
    """Route to src.cli module and return exit code.

    Args:
        module_name: Name of the v2 CLI module to route to.
        mode: The resolved CLI mode (CREATE, MODIFY, EXECUTE, EXPORT, INVALID).
              Passed to module main() for validation and execution.

    Returns:
        Exit code from the v2 module (0 for success, 1 for error).
    """
    from src.cli import (
        bcllm_experiment,
        bcllm_model,
        bcllm_questions,
        bcllm_run,
        bcllm_execute,
        bcllm_review,
        bcllm_export,
        bcllm_main,
    )

    if module_name == "bcllm_main":
        return bcllm_main.main(mode)
    elif module_name == "bcllm_experiment":
        return bcllm_experiment.main(mode)
    elif module_name == "bcllm_model":
        return bcllm_model.main(mode)
    elif module_name == "bcllm_questions":
        return bcllm_questions.main(mode)
    elif module_name == "bcllm_run":
        return bcllm_run.main(mode)
    elif module_name == "bcllm_execute":
        return bcllm_execute.main(mode)
    elif module_name == "bcllm_review":
        return bcllm_review.main(mode)
    elif module_name == "bcllm_export":
        return bcllm_export.main(mode)
    else:
        print(f"Error: Unknown v2 module: {module_name}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point — routes with explicit MODE × MODULE validation.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    mode = resolve_mode(sys.argv)
    module = resolve_module(sys.argv)

    if module is None:
        if "--help" in sys.argv or "-h" in sys.argv:
            module = "bcllm_main"
        else:
            print("Error: No valid command found. Use --help for usage.", file=sys.stderr)
            return 1

    log_config = LoggingConfig(
        log_file_path=Path(os.getenv("LOG_FILE_PATH", "./logs/benchmark.log")),
        log_level=os.getenv("LOG_LEVEL", "INFO")
    )
    logger = setup_logging(log_config)

    logger.info(f"APPLICATION_START | version=2.0 | mode={mode.value}")

    try:
        validate_mode_matrix(mode, module)
    except ModeMatrixError as e:
        print(str(e), file=sys.stderr)
        return 1

    logger.info(f"MODE_ROUTING | mode={mode.value} | matrix={module}")

    return route_to_v2(module, mode)


if __name__ == "__main__":
    sys.exit(main())
