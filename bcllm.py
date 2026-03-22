#!/usr/bin/env python3
"""CLI entry point — dispatches to src_v2 or legacy src."""
import sys


def route_to_v2(module_name: str) -> int:
    """Route to src_v2.cli module and return exit code.

    Args:
        module_name: Name of the v2 CLI module to route to.

    Returns:
        Exit code from the v2 module (0 for success, 1 for error).
    """
    from src_v2.cli import (
        bcllm_experiment,
        bcllm_model,
        bcllm_questions,
        bcllm_run,
        bcllm_execute,
        bcllm_review,
    )

    if module_name == "bcllm_experiment":
        return bcllm_experiment.main()
    elif module_name == "bcllm_model":
        return bcllm_model.main()
    elif module_name == "bcllm_questions":
        return bcllm_questions.main()
    elif module_name == "bcllm_run":
        return bcllm_run.main()
    elif module_name == "bcllm_execute":
        return bcllm_execute.main()
    elif module_name == "bcllm_review":
        return bcllm_review.main()
    else:
        print(f"Error: Unknown v2 module: {module_name}", file=sys.stderr)
        return 1


def determine_v2_command(argv: list[str]) -> str | None:
    """Determine which v2 command to route to based on argv.

    Args:
        argv: Command-line arguments (including script name).

    Returns:
        Module name (e.g., "bcllm_experiment") or None (use legacy).
    """
    args = argv[1:]

    # Check for review commands (highest priority)
    if "--review-experiment" in args or "--review-all" in args:
        return "bcllm_review"

    # Check for execute command first (highest priority)
    if "--execute" in args:
        return "bcllm_execute"

    # Check for model commands (require --experiment but take precedence)
    if "--add-model" in args or "--list-models" in args or "--remove-model" in args:
        return "bcllm_model"

    # Check for question commands
    if "--add-questions" in args or "--list-questions" in args or "--remove-question" in args:
        return "bcllm_questions"

    # Check for run commands
    if "--create-run" in args or "--list-runs" in args:
        return "bcllm_run"

    # Check for run show command (--run without --execute)
    if "--run" in args:
        return "bcllm_run"

    # Check for experiment commands (lowest priority v2 commands)
    if "--create-experiment" in args or "--experiment" in args or "--list-experiments" in args or "--remove-experiment" in args:
        return "bcllm_experiment"

    return None


def main() -> int:
    """Main entry point — routes to v2 or legacy.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    v2_module = determine_v2_command(sys.argv)

    if v2_module is not None:
        return route_to_v2(v2_module)
    else:
        from src.main import main as legacy_main
        return legacy_main()


if __name__ == "__main__":
    sys.exit(main())
