"""Special configuration values for explicit CLI system-default handling.

This module provides the FORCE_SYSTEM_DEFAULT sentinel value to distinguish between:
- None: "not specified, use fallback"
- FORCE_SYSTEM_DEFAULT: "user explicitly passed system-default, skip .env fallback, omit from API request"

Renamed 2026-08-19 from `null_semantics.py` (functions renamed from
`nullable_*`/`normalize_nulls_explicit`) — the old names implied this module
deals with "null", but it never produces a usable "null" value: the literal
`'null'` string is always rejected (deprecated, migration hint to
`'system-default'`). What this module actually recognizes and normalizes is
the `system-default` special value. See docs/status/known-issues.md and
docs/architecture/adr/ for the audit that motivated this rename — it is
deliberately NOT a mechanical find-and-replace: `None` (absence), the
`'none'` literal (a valid domain value for some flags, e.g. reasoning
effort — see `bcllm_model.py`'s `--reasoning` choices), and `'AUTO'` (a
completely separate concept, handled only in `config_resolver.py`'s
seed-specific resolution, never touching this module) are distinct states
this module does not — and must not — collapse together.

Eligibility for system-default recognition is explicit and opt-in (see
`normalize_special_config_values`), not inferred from argparse action
metadata (`default=None`/`required=False`). The previous heuristic-based
design silently normalized identity-selector and structural flags too
(`--run`, `--remove-run`, `--remove-experiment`, `--remove-model`, etc.),
causing them to become the falsy `FORCE_SYSTEM_DEFAULT` sentinel and vanish
from dispatch logic instead of being rejected or handled correctly — see
docs/status/known-issues.md's "'_is_nullable_arg's blanket sweep" entry
(now resolved by this module).

Example:
    >>> from src.core.special_config_values import FORCE_SYSTEM_DEFAULT
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

_DEPRECATED_NULL_MESSAGE = "The 'null' literal is deprecated. Use 'system-default' instead."


def parse_int_or_system_default(value: str) -> int | ForceSystemDefault:
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
        raise argparse.ArgumentTypeError(_DEPRECATED_NULL_MESSAGE)
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}")


def parse_float_or_system_default(value: str) -> float | ForceSystemDefault:
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
        raise argparse.ArgumentTypeError(_DEPRECATED_NULL_MESSAGE)
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid float value: {value!r}")


def parse_str_or_system_default(value: str) -> str | ForceSystemDefault:
    """Parse string that accepts 'system-default' as FORCE_SYSTEM_DEFAULT.

    Args:
        value: String value from CLI

    Returns:
        str if valid string, FORCE_SYSTEM_DEFAULT if 'system-default'

    Raises:
        argparse.ArgumentTypeError: If value is deprecated 'null'

    Note: "none" is NOT treated as special — it's preserved as literal string.
    This is intentional because "none" is a valid reasoning_effort value.
    """
    if value.lower() == 'system-default':
        return FORCE_SYSTEM_DEFAULT
    if value.lower() == 'null':
        raise argparse.ArgumentTypeError(_DEPRECATED_NULL_MESSAGE)
    return value


def normalize_special_config_values(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    supported: set[str] = frozenset(),
    forbidden: set[str] = frozenset(),
) -> argparse.Namespace:
    """Normalize 'system-default' string values, explicit opt-in only.

    Three-way classification (per dest name), matching
    docs/contracts/system-default-semantics.md:
    - **SUPPORTED** (`supported`): `system-default` has real, contract-defined
      semantics for this flag. `'system-default'` -> `FORCE_SYSTEM_DEFAULT`.
      Deprecated `'null'` is rejected with a migration hint.
    - **FORBIDDEN** (`forbidden`): the flag is recognized specifically so it
      can be explicitly rejected — `system-default` (or the deprecated
      `'null'`) as a value for this flag is a usage error, not a silently
      accepted or silently mis-dispatched one. Raises
      `argparse.ArgumentError` (callers should catch this and call
      `parser.error(str(e))`, matching the deprecated-'null' pattern already
      used at every CLI module's `main()` — this yields exit code 2, same as
      any other argparse usage error).
    - **Neither** (not in `supported` or `forbidden`): NOT_APPLICABLE. The
      value is left completely untouched — not inspected, not converted.
      This covers flags that aren't configuration values at all (identity
      selectors like model IDs, boolean store_true flags, list-typed flags
      not yet handled by this scalar mechanism).

    This replaces the previous heuristic (`_is_nullable_arg`: "any optional
    argument with default=None") which could not distinguish configuration
    values from identity/structural flags — see module docstring.

    Args:
        args: Parsed argument namespace
        parser: ArgumentParser instance (used to resolve action-by-dest for
            error messages)
        supported: dest names eligible for system-default with real semantics
        forbidden: dest names that must be explicitly rejected if given
            'system-default' (or deprecated 'null')

    Returns:
        Namespace with 'system-default' values converted to FORCE_SYSTEM_DEFAULT
        for supported dests.

    Raises:
        argparse.ArgumentError: If a supported dest has deprecated 'null', or
            if a forbidden dest has 'system-default' or 'null'.
    """
    actions_by_dest = {action.dest: action for action in parser._actions}

    for dest in supported:
        value = getattr(args, dest, None)
        if not isinstance(value, str):
            continue
        if value.lower() == 'system-default':
            setattr(args, dest, FORCE_SYSTEM_DEFAULT)
        elif value.lower() == 'null':
            action = actions_by_dest.get(dest)
            raise argparse.ArgumentError(action, _DEPRECATED_NULL_MESSAGE)

    for dest in forbidden:
        value = getattr(args, dest, None)
        if not isinstance(value, str):
            continue
        if value.lower() in ('system-default', 'null'):
            action = actions_by_dest.get(dest)
            raise argparse.ArgumentError(
                action,
                "does not accept 'system-default' or 'null' — it identifies "
                "a specific value that must be provided explicitly."
            )

    return args


def normalize_filter_list_or_system_default(
    values: list[str] | None,
) -> list[str] | ForceSystemDefault:
    """Normalize a repeatable filter-list flag (`--where`/`--exclude`,
    argparse `action="append"`), explicit opt-in only — the caller decides
    whether this flag is meant to support `system-default` at all by
    choosing to call this function.

    Unlike `normalize_special_config_values` (scalar values), this handles
    the list shape directly — Typer/Click invoke a callback with the WHOLE
    accumulated list at once for a `List[str]` option, not per-item, so
    the "does this list represent system-default" decision has to look at
    every element together, not any single one in isolation.

    Rules:
    - `None` or an empty list -> `[]` (flag not provided; caller applies
      its own not-provided fallback, e.g. an `.env` default, separately —
      this function only normalizes what the CLI flag itself said).
    - Exactly one value, case-insensitively `'system-default'` ->
      `FORCE_SYSTEM_DEFAULT` (apply no filter at all; bypasses whatever
      `.env` fallback the caller would otherwise use for "not provided").
    - Exactly one value, case-insensitively `'null'` -> raises `ValueError`
      (deprecated, migration hint — same message text as the scalar path).
    - More than one value where any element is `'system-default'`
      (repeated or combined with concrete `field=value` filters) ->
      raises `ValueError` — `system-default` must appear alone; combining
      it with a concrete filter (or itself) is a contradictory intent, not
      silently resolved by picking one.
    - Otherwise -> the list is returned unchanged (concrete `field=value`
      filters, however many — repeating the flag for multiple AND-combined
      conditions is deliberately allowed and never an error).

    Args:
        values: The raw list from `args.where`/`args.exclude` (argparse
            `action="append"` default is `None` if never passed).

    Returns:
        `[]` if not provided, `FORCE_SYSTEM_DEFAULT` if explicitly
        cleared, or the original list of concrete filter strings.

    Raises:
        ValueError: for the deprecated `'null'` literal, or `system-default`
            combined with any other value (including itself, repeated).
    """
    if not values:
        return []

    lowered = [v.lower() for v in values]

    if 'system-default' in lowered:
        if len(values) > 1:
            raise ValueError(
                "'system-default' cannot be combined with a concrete filter "
                "(or repeated) — it means 'apply no filter', which "
                "contradicts specifying one. Pass it alone."
            )
        return FORCE_SYSTEM_DEFAULT

    if 'null' in lowered:
        raise ValueError(_DEPRECATED_NULL_MESSAGE)

    return values
