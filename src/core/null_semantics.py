"""Null semantics for explicit CLI null handling.

This module provides the FORCE_SYSTEM_DEFAULT sentinel value to distinguish between:
- None: "not specified, use fallback"
- FORCE_SYSTEM_DEFAULT: "user explicitly passed system-default, skip .env fallback, omit from API request"

Example:
    >>> from src.core.null_semantics import FORCE_SYSTEM_DEFAULT
    >>> value = FORCE_SYSTEM_DEFAULT
    >>> value is FORCE_SYSTEM_DEFAULT
    True
"""

import argparse


class ForceSystemDefault:
    """Sentinel value representing explicit 'system-default' from CLI.

    When a user passes --flag system-default, the argument is set to FORCE_SYSTEM_DEFAULT
    to indicate: "use system default, skip .env fallback, omit from API request".

    This is a singleton pattern - all instances are identical.
    """

    _instance = None

    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return '<FORCE_SYSTEM_DEFAULT>'

    def __bool__(self) -> bool:
        """ForceSystemDefault is falsy (like None)."""
        return False

    def __eq__(self, other) -> bool:
        """All ForceSystemDefault instances are equal."""
        return isinstance(other, ForceSystemDefault)


# Singleton instance - use this everywhere
FORCE_SYSTEM_DEFAULT = ForceSystemDefault()


def nullable_int(value: str) -> int | None:
    """Parse int that accepts 'system-default' as FORCE_SYSTEM_DEFAULT.

    Args:
        value: String value from CLI

    Returns:
        int if valid integer, FORCE_SYSTEM_DEFAULT if 'system-default', raises ValueError otherwise

    Raises:
        argparse.ArgumentTypeError: If value is not a valid integer, 'system-default', or deprecated 'null'
    """
    if value.lower() == 'system-default':
        return FORCE_SYSTEM_DEFAULT
    if value.lower() == 'null':
        from argparse import ArgumentTypeError
        raise ArgumentTypeError(
            "The 'null' literal is deprecated. Use 'system-default' instead."
        )
    try:
        return int(value)
    except ValueError:
        from argparse import ArgumentTypeError
        raise ArgumentTypeError(f"invalid int value: {value!r}")


def nullable_float(value: str) -> float | None:
    """Parse float that accepts 'system-default' as FORCE_SYSTEM_DEFAULT.

    Args:
        value: String value from CLI

    Returns:
        float if valid float, FORCE_SYSTEM_DEFAULT if 'system-default', raises ValueError otherwise

    Raises:
        argparse.ArgumentTypeError: If value is not a valid float, 'system-default', or deprecated 'null'
    """
    if value.lower() == 'system-default':
        return FORCE_SYSTEM_DEFAULT
    if value.lower() == 'null':
        from argparse import ArgumentTypeError
        raise ArgumentTypeError(
            "The 'null' literal is deprecated. Use 'system-default' instead."
        )
    try:
        return float(value)
    except ValueError:
        from argparse import ArgumentTypeError
        raise ArgumentTypeError(f"invalid float value: {value!r}")


def nullable_str(value: str) -> str | None:
    """Parse string that accepts 'system-default' as FORCE_SYSTEM_DEFAULT.

    Args:
        value: String value from CLI

    Returns:
        str if valid string, FORCE_SYSTEM_DEFAULT if 'system-default'

    Raises:
        argparse.ArgumentTypeError: If value is deprecated 'null'

    Note: This is for string arguments that need FORCE_SYSTEM_DEFAULT support.
    Most string args don't need type= and will be normalized by normalize_nulls_explicit().
    
    Note: "none" is NOT treated as special — it's preserved as literal string.
    This is intentional because "none" is a valid reasoning_effort value.
    """
    if value.lower() == 'system-default':
        return FORCE_SYSTEM_DEFAULT
    if value.lower() == 'null':
        from argparse import ArgumentTypeError
        raise ArgumentTypeError(
            "The 'null' literal is deprecated. Use 'system-default' instead."
        )
    return value


def normalize_nulls_explicit(args, parser):
    """Normalize 'system-default' string values to FORCE_SYSTEM_DEFAULT.

    Iterates through parser actions to find nullable arguments:
    - default=None (optional arguments)
    - required=False (not mandatory)

    For each nullable argument:
    - If the value is 'system-default' (case-insensitive), converts to FORCE_SYSTEM_DEFAULT
    - If the value is 'null' (case-insensitive), raises ArgumentError with migration hint
    - The string 'none' is preserved as literal (intentional - valid reasoning_effort value)

    Args:
        args: Parsed argument namespace
        parser: ArgumentParser instance (used to inspect action metadata)

    Returns:
        Namespace with 'system-default' values converted to FORCE_SYSTEM_DEFAULT

    Raises:
        argparse.ArgumentError: If 'null' literal is used (deprecated)
    """
    for action in parser._actions:
        # Skip if not a nullable argument
        if not _is_nullable_arg(action):
            continue

        # Get current value
        value = getattr(args, action.dest, None)

        # Normalize 'system-default' to FORCE_SYSTEM_DEFAULT
        if isinstance(value, str) and value.lower() == 'system-default':
            setattr(args, action.dest, FORCE_SYSTEM_DEFAULT)
        # Reject deprecated 'null' literal with migration hint
        elif isinstance(value, str) and value.lower() == 'null':
            raise argparse.ArgumentError(
                action,
                "The 'null' literal is deprecated. Use 'system-default' instead."
            )

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
