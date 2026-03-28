"""Mode resolver - determines CLI mode from raw argv."""
from typing import List
from .mode import Mode
from .argv_utils import has_flag


def resolve_mode(argv: List[str]) -> Mode:
    """Determine CLI mode from raw sys.argv.
    
    Args:
        argv: Raw command-line arguments (e.g., sys.argv, including script name at [0])
        
    Returns:
        Mode enum value based on priority rules:
        - Mode.EXECUTE if --execute present
        - Mode.CREATE if --create-experiment present
        - Mode.MODIFY if --experiment present (without --create-experiment)
        - Mode.INVALID if no valid mode flags detected (empty or invalid input)
        
    Important:
        - Operates on raw argv strings, not parsed argparse objects
        - Case-sensitive matching (only lowercase flags match)
        - Exact flag name matching required (--execute, not -execute or --execute-now)
        - Supports both space-separated (--flag value) and equals (--flag=value) notation
        - Priority order: EXECUTE > CREATE > MODIFY > INVALID
        
    Examples:
        >>> resolve_mode(["bcllm", "--execute"])
        Mode.EXECUTE
        
        >>> resolve_mode(["bcllm", "--create-experiment", "my_exp"])
        Mode.CREATE
        
        >>> resolve_mode(["bcllm", "--experiment", "my_exp"])
        Mode.MODIFY
        
        >>> resolve_mode(["bcllm", "--list-experiments"])
        Mode.INVALID
    """
    args = argv[1:] if len(argv) > 0 else []

    if not args:
        return Mode.INVALID

    if has_flag(args, "--execute"):
        return Mode.EXECUTE

    if has_flag(args, "--create-experiment"):
        return Mode.CREATE

    if has_flag(args, "--experiment"):
        return Mode.MODIFY

    return Mode.INVALID
