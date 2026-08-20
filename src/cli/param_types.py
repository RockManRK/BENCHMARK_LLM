"""Typer-flavored equivalents of src/core/special_config_values.py's
parse_*_or_system_default parsers, sharing the same FORCE_SYSTEM_DEFAULT
sentinel and the same 'system-default'/deprecated-'null' behavior and
messages.

Not wired to any command yet (no CLI module has been migrated to Typer —
see the CLI migration plan, Fase 2/4). This exists as the shared special-
value-handling foundation the plan calls for, ready for Fase 4 to attach
to real Typer parameters via `typer.Option(..., callback=typer_int_or_system_default)`.

argparse's parse_*_or_system_default (src/core/special_config_values.py)
stay untouched — this module does not change their behavior, it mirrors it
for Typer's callback mechanism, which raises `typer.BadParameter` instead
of `argparse.ArgumentTypeError`/`ArgumentError` on invalid input.
"""

from __future__ import annotations

import typer

from src.core.special_config_values import FORCE_SYSTEM_DEFAULT, ForceSystemDefault

_DEPRECATED_NULL_MESSAGE = "The 'null' literal is deprecated. Use 'system-default' instead."


def typer_int_or_system_default(value: str | None) -> int | ForceSystemDefault | None:
    """Typer callback: parse int, accepting 'system-default'.

    Args:
        value: Raw string from Typer, or None if the option was not
            passed (Typer only invokes the callback with None when the
            parameter itself is optional with no default supplied).

    Returns:
        int if valid integer, FORCE_SYSTEM_DEFAULT if 'system-default',
        None if not passed.

    Raises:
        typer.BadParameter: If value is not a valid integer, or is the
            deprecated 'null' literal.
    """
    if value is None:
        return None
    if value.lower() == "system-default":
        return FORCE_SYSTEM_DEFAULT
    if value.lower() == "null":
        raise typer.BadParameter(_DEPRECATED_NULL_MESSAGE)
    try:
        return int(value)
    except ValueError:
        raise typer.BadParameter(f"invalid int value: {value!r}")


def typer_float_or_system_default(value: str | None) -> float | ForceSystemDefault | None:
    """Typer callback: parse float, accepting 'system-default'.

    Same contract as `typer_int_or_system_default`, for float-typed options.
    """
    if value is None:
        return None
    if value.lower() == "system-default":
        return FORCE_SYSTEM_DEFAULT
    if value.lower() == "null":
        raise typer.BadParameter(_DEPRECATED_NULL_MESSAGE)
    try:
        return float(value)
    except ValueError:
        raise typer.BadParameter(f"invalid float value: {value!r}")


def typer_str_or_system_default(value: str | None) -> str | ForceSystemDefault | None:
    """Typer callback: pass through a string, accepting 'system-default'.

    'none' is intentionally NOT special-cased — preserved as a literal
    string, matching src/core/special_config_values.py::parse_str_or_system_default
    (it is a valid `reasoning_effort` value).
    """
    if value is None:
        return None
    if value.lower() == "system-default":
        return FORCE_SYSTEM_DEFAULT
    if value.lower() == "null":
        raise typer.BadParameter(_DEPRECATED_NULL_MESSAGE)
    return value
