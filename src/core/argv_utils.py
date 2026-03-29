"""Command-line argument utilities for null normalization."""
import argparse
from .null_semantics import EXPLICIT_NULL, normalize_nulls_explicit


def has_flag(args: list[str], flag: str) -> bool:
    """Check if a flag is present in the argument list.

    Supports both space-separated (--flag value) and equals (--flag=value) notation.

    Args:
        args: List of argument strings (e.g., sys.argv[1:])
        flag: Flag to search for (e.g., "--execute")

    Returns:
        True if flag is present, False otherwise
    """
    for arg in args:
        if arg == flag or arg.startswith(f"{flag}="):
            return True
    return False


def parse_args_normalized(parser: argparse.ArgumentParser, argv=None) -> argparse.Namespace:
    """Parse arguments and normalize 'null' values to EXPLICIT_NULL.
    
    This function wraps parser.parse_args() to automatically normalize
    explicit 'null' string values to EXPLICIT_NULL for optional arguments.
    
    Args:
        parser: ArgumentParser instance
        argv: Command-line arguments (defaults to sys.argv[1:] if None)
        
    Returns:
        Parsed namespace with 'null' values converted to EXPLICIT_NULL
    """
    args = parser.parse_args(argv)
    return normalize_nulls_explicit(args, parser)


def normalize_nulls(args: argparse.Namespace, parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Normalize 'null' string values to EXPLICIT_NULL for optional string arguments.
    
    Iterates through parser actions to find nullable arguments:
    - default=None (optional arguments)
    - required=False (not mandatory)
    
    For each nullable argument, if the value is the string 'null' (case-insensitive),
    it is converted to EXPLICIT_NULL. The string 'none' is preserved as a literal.
    
    Args:
        args: Parsed argument namespace
        parser: ArgumentParser instance (used to inspect action metadata)
        
    Returns:
        Namespace with 'null' values converted to EXPLICIT_NULL
    """
    return normalize_nulls_explicit(args, parser)


def _is_nullable_arg(action: argparse.Action) -> bool:
    """Check if an argument is nullable (optional string with default=None).
    
    Args:
        action: argparse Action to check
        
    Returns:
        True if argument is nullable (default=None, required=False, value is string)
    """
    # Must be optional (not required)
    if action.required:
        return False
    
    # Must have default=None (explicitly optional)
    if action.default is not None:
        return False
    
    # Note: We don't check action.type here because:
    # 1. Some arguments may not have explicit type=str
    # 2. We check runtime value is string in normalize_nulls()
    # 3. This makes the function more flexible
    
    return True
