"""Module resolver - determines target module from raw argv."""
from typing import List, Optional
from .argv_utils import has_flag


# Module mapping: flag patterns to module names
_MODULE_MAP = {
    # Experiment module
    "--create-experiment": "bcllm_experiment",
    "--experiment": "bcllm_experiment",
    "--list-experiments": "bcllm_experiment",
    "--remove-experiment": "bcllm_experiment",
    
    # Model module
    "--add-model": "bcllm_model",
    "--list-models": "bcllm_model",
    "--remove-model": "bcllm_model",
    
    # Questions module
    "--add-questions": "bcllm_questions",
    "--questions": "bcllm_questions",
    "--list-questions": "bcllm_questions",
    "--remove-question": "bcllm_questions",
    
    # Run module
    "--add-run": "bcllm_run",
    "--create-run": "bcllm_run",
    "--list-runs": "bcllm_run",
    "--run": "bcllm_run",
    "--remove-run": "bcllm_run",
    
    # Execute module
    "--execute": "bcllm_execute",

    # Export module
    "--export": "bcllm_export",
    "--export-results": "bcllm_export",

    # Review module
    "--review-experiment": "bcllm_review",
    "--review-all": "bcllm_review",
    
    # Main module (help)
    "--help": "bcllm_main",
    "-h": "bcllm_main",
}


def resolve_module(argv: List[str]) -> Optional[str]:
    """Resolve module name from raw sys.argv.

    Args:
        argv: Raw command-line arguments (including script name at [0])

    Returns:
        Module name string (e.g., 'bcllm_experiment') or None if no valid module flag found

    Priority Rules:
        1. --help / -h always takes highest priority → 'bcllm_main'
        2. --export takes priority when present → 'bcllm_export'
        3. --execute takes priority when present → 'bcllm_execute'
        4. For other flags, specific action flags take priority over --experiment
        5. If no specific action flag, --experiment defaults to bcllm_experiment

    Important:
        - Operates on raw argv strings, not parsed argparse objects
        - Case-sensitive matching (only lowercase flags match)
        - Exact flag name matching required
        - Supports both space-separated (--flag value) and equals (--flag=value) notation

    Examples:
        >>> resolve_module(["bcllm", "--create-experiment", "my_exp"])
        'bcllm_experiment'

        >>> resolve_module(["bcllm", "--help", "--execute"])
        'bcllm_main'  # help takes priority

        >>> resolve_module(["bcllm", "--experiment", "my_exp", "--export"])
        'bcllm_export'  # export takes priority

        >>> resolve_module(["bcllm", "--experiment", "my_exp", "--add-run"])
        'bcllm_run'  # specific action flag takes priority over --experiment

        >>> resolve_module(["bcllm", "--add-model", "google/gemini"])
        'bcllm_model'

        >>> resolve_module(["bcllm"])
        None  # no valid module flag
    """
    # Skip script name (argv[0])
    args = argv[1:] if len(argv) > 0 else []

    # Check for help first (highest priority)
    if has_flag(args, "--help") or has_flag(args, "-h"):
        return "bcllm_main"

    # Check for export second (high priority for compound commands)
    if has_flag(args, "--export"):
        return "bcllm_export"

    # Check for execute third (high priority for compound commands)
    if has_flag(args, "--execute"):
        return "bcllm_execute"

    # Priority-based scanning for action flags
    # Specific action flags (--add-run, --add-model, etc.) take priority over --experiment
    # This allows commands like: bcllm --experiment my_exp --add-run
    
    # Define priority order for action flags (higher priority = checked first)
    # Flags that modify an experiment should take priority over --experiment itself
    PRIORITY_FLAGS = [
        # Run actions (highest priority after execute/export)
        "--add-run", "--create-run", "--list-runs", "--run", "--remove-run",
        # Model actions
        "--add-model", "--list-models", "--remove-model",
        # Question actions
        "--add-questions", "--questions", "--list-questions", "--remove-question",
        # Experiment structure actions
        "--create-experiment", "--remove-experiment",
        # Review actions
        "--review-experiment", "--review-all",
        # Export actions (already handled above, but included for completeness)
        "--export-results",
        # Finally, --experiment and --list-experiments (lowest priority)
        "--experiment", "--list-experiments",
    ]
    
    # Check flags in priority order
    for priority_flag in PRIORITY_FLAGS:
        if has_flag(args, priority_flag):
            if priority_flag in _MODULE_MAP:
                return _MODULE_MAP[priority_flag]
    
    # Fallback: left-to-right scanning for any other flags not in priority list
    for arg in args:
        flag = _extract_flag(arg)
        if flag in _MODULE_MAP:
            return _MODULE_MAP[flag]

    return None


def _extract_flag(arg: str) -> Optional[str]:
    """Extract flag name from argument.
    
    Handles:
    - Exact flag: --flag → --flag
    - Equals notation: --flag=value → --flag
    - Ignores: value (no leading --)
    
    Args:
        arg: Single argument string
        
    Returns:
        Flag name (e.g., "--experiment") or None if not a flag
    """
    if not arg.startswith("--"):
        return None
    
    # Split on = for equals notation
    if "=" in arg:
        return arg.split("=", 1)[0]
    
    return arg
