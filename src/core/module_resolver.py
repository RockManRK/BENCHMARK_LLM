"""Module resolver - determines target module from raw argv.

This module implements the CLI Module Resolution Contract:
- Flags of action (--add-*, --execute, --list-*) have priority over context flags
- Context flags (--experiment, --create-experiment) never define the module
- Argument order must not affect resolution
- Composite flows (CREATE + ADD_*) are supported
"""
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

    # Provider module
    "--resolve-providers": "bcllm_provider",

    # Main module (help)
    "--help": "bcllm_main",
    "-h": "bcllm_main",
}

# Action flags that define the module (ADD_* actions)
ADD_ACTION_FLAGS = [
    "--add-model",
    "--add-questions",
    "--add-run",
]

# Context flags that establish scope but never define module
CONTEXT_FLAGS = [
    "--create-experiment",
    "--experiment",
]


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
        4. Action flags (--add-*, --list-*, --remove-*) define the module
        5. Context flags (--create-experiment, --experiment) never define module
        6. Argument order does NOT affect resolution

    Composite Flow Support:
        When --create-experiment is present with an --add-* action:
        - The action flag defines the module (e.g., --add-model → bcllm_model)
        - The orchestration layer (bcllm.py) creates the experiment first
        - The action module then operates on the created experiment

    Important:
        - Operates on raw argv strings, not parsed argparse objects
        - Case-sensitive matching (only lowercase flags match)
        - Exact flag name matching required
        - Supports both space-separated (--flag value) and equals (--flag=value) notation

    Examples:
        >>> resolve_module(["bcllm", "--create-experiment", "my_exp"])
        'bcllm_experiment'

        >>> resolve_module(["bcllm", "--create-experiment", "my_exp", "--add-model", "M"])
        'bcllm_model'  # Composite flow: action flag defines module

        >>> resolve_module(["bcllm", "--add-model", "M", "--create-experiment", "EXP"])
        'bcllm_model'  # Order does not matter

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

    # CRITICAL: Check for ADD_* action flags
    # These ALWAYS define the module, even when --create-experiment is present
    # This enables composite flows: CREATE + ADD_*
    
    # When multiple ADD_* flags are present, resolve to the LAST action in execution order
    # Execution order: model → questions → run (run must be last as it requires models + questions)
    add_flags_present = [flag for flag in ADD_ACTION_FLAGS if has_flag(args, flag)]
    
    if len(add_flags_present) > 1:
        # Multiple ADD_* flags - resolve to the last action in execution order
        # Execution order defined by ADD_ACTION_FLAGS list order
        # Last flag in the list that's present wins
        for action_flag in reversed(ADD_ACTION_FLAGS):
            if action_flag in add_flags_present:
                return _MODULE_MAP[action_flag]
    
    for action_flag in ADD_ACTION_FLAGS:
        if has_flag(args, action_flag):
            return _MODULE_MAP[action_flag]

    # Check for other action flags (list, remove, run, review, etc.)
    PRIORITY_FLAGS = [
        # Provider resolution (MODIFY operation - must check before --experiment)
        "--resolve-providers",
        # Run actions
        "--create-run", "--list-runs", "--run", "--remove-run",
        # Model actions (already handled ADD_MODEL above, but list/remove need this)
        "--list-models", "--remove-model",
        # Question actions (already handled ADD_QUESTIONS above)
        "--list-questions", "--remove-question",
        # Experiment structure actions
        "--create-experiment", "--remove-experiment",
        # Review actions
        "--review-experiment", "--review-all",
        # Export actions
        "--export-results",
        # Context flags (lowest priority - never define module when action is present)
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
