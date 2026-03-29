"""Null semantics for explicit CLI null handling.

This module provides the EXPLICIT_NULL sentinel value to distinguish between:
- None: "not specified, use fallback"  
- EXPLICIT_NULL: "explicitly null, DO NOT use fallback"

Example:
    >>> from src.core.null_semantics import EXPLICIT_NULL
    >>> value = EXPLICIT_NULL
    >>> value is EXPLICIT_NULL
    True
"""


class ExplicitNull:
    """Sentinel value representing explicit 'null' from CLI.
    
    When a user passes --flag null, the argument is set to EXPLICIT_NULL
    to indicate intentional null (no fallback) vs. None (use fallback).
    
    This is a singleton pattern - all instances are identical.
    """
    
    _instance = None
    
    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __repr__(self) -> str:
        return '<EXPLICIT_NULL>'
    
    def __bool__(self) -> bool:
        """ExplicitNull is falsy (like None)."""
        return False
    
    def __eq__(self, other) -> bool:
        """All ExplicitNull instances are equal."""
        return isinstance(other, ExplicitNull)


# Singleton instance - use this everywhere
EXPLICIT_NULL = ExplicitNull()


def nullable_int(value: str) -> int | None:
    """Parse int that accepts 'null' as EXPLICIT_NULL.
    
    Args:
        value: String value from CLI
        
    Returns:
        int if valid integer, EXPLICIT_NULL if 'null', raises ValueError otherwise
        
    Raises:
        argparse.ArgumentTypeError: If value is not a valid integer or 'null'
    """
    if value.lower() == 'null':
        return EXPLICIT_NULL
    try:
        return int(value)
    except ValueError:
        from argparse import ArgumentTypeError
        raise ArgumentTypeError(f"invalid int value: {value!r}")


def nullable_float(value: str) -> float | None:
    """Parse float that accepts 'null' as EXPLICIT_NULL.
    
    Args:
        value: String value from CLI
        
    Returns:
        float if valid float, EXPLICIT_NULL if 'null', raises ValueError otherwise
        
    Raises:
        argparse.ArgumentTypeError: If value is not a valid float or 'null'
    """
    if value.lower() == 'null':
        return EXPLICIT_NULL
    try:
        return float(value)
    except ValueError:
        from argparse import ArgumentTypeError
        raise ArgumentTypeError(f"invalid float value: {value!r}")


def nullable_str(value: str) -> str | None:
    """Parse string that accepts 'null' as EXPLICIT_NULL.
    
    Args:
        value: String value from CLI
        
    Returns:
        str if valid string, EXPLICIT_NULL if 'null'
        
    Note: This is for string arguments that need EXPLICIT_NULL support.
    Most string args don't need type= and will be normalized by normalize_nulls_explicit().
    """
    if value.lower() == 'null':
        return EXPLICIT_NULL
    return value


def normalize_nulls_explicit(args, parser):
    """Normalize 'null' string values to EXPLICIT_NULL.
    
    Iterates through parser actions to find nullable arguments:
    - default=None (optional arguments)
    - required=False (not mandatory)
    
    For each nullable argument, if the value is the string 'null' (case-insensitive),
    it is converted to EXPLICIT_NULL. The string 'none' is preserved as literal.
    
    Args:
        args: Parsed argument namespace
        parser: ArgumentParser instance (used to inspect action metadata)
        
    Returns:
        Namespace with 'null' values converted to EXPLICIT_NULL
    """
    for action in parser._actions:
        # Skip if not a nullable argument
        if not _is_nullable_arg(action):
            continue
        
        # Get current value
        value = getattr(args, action.dest, None)
        
        # Normalize only if value is a string equal to 'null'
        if isinstance(value, str) and value.lower() == 'null':
            setattr(args, action.dest, EXPLICIT_NULL)
    
    return args


def _is_nullable_arg(action) -> bool:
    """Check if an argument is nullable (optional with default=None).
    
    Args:
        action: argparse Action to check
        
    Returns:
        True if argument is nullable (default=None, required=False)
    """
    # Must be optional (not required)
    if action.required:
        return False
    
    # Must have default=None (explicitly optional)
    if action.default is not None:
        return False
    
    return True
