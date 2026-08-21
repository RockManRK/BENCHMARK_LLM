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

Also mirrors two more pieces of src/core/special_config_values.py found
missing during the marco 4A equivalence check (2026-08-20):
- `normalize_filter_list_or_system_default` -> `typer_filter_list_or_system_default`,
  for `--where`/`--exclude`-shaped `List[str]` options.
- `normalize_special_config_values`'s FORBIDDEN branch -> `typer_reject_special_values`,
  for structural/identity string flags (e.g. `--experiment`, `--url`) that
  must explicitly reject 'system-default'/'null' rather than silently
  accepting the literal string or being left untouched.
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


_FORBIDDEN_SPECIAL_VALUE_MESSAGE = (
    "does not accept 'system-default' or 'null' — it identifies "
    "a specific value that must be provided explicitly."
)


def typer_reject_special_values(value: str | None) -> str | None:
    """Typer callback for FORBIDDEN string flags (identity/structural
    selectors like `--experiment`, `--url`, `--create-experiment`) —
    mirrors `special_config_values.normalize_special_config_values`'s
    FORBIDDEN branch. These flags are ordinary strings otherwise (no
    FORCE_SYSTEM_DEFAULT conversion happens for them, ever) — this
    callback's only job is to explicitly reject 'system-default'/'null'
    as a usage error, rather than silently accepting either as the
    literal identity value.

    Args:
        value: Raw string from Typer, or None if the option was not
            passed.

    Returns:
        The value unchanged if it isn't 'system-default'/'null'; None if
        not passed.

    Raises:
        typer.BadParameter: If value is (case-insensitively)
            'system-default' or 'null'.
    """
    if value is None:
        return None
    if value.lower() in ("system-default", "null"):
        raise typer.BadParameter(_FORBIDDEN_SPECIAL_VALUE_MESSAGE)
    return value


def typer_filter_list_or_system_default(
    values: list[str] | None,
) -> list[str] | ForceSystemDefault:
    """Mirrors `special_config_values.normalize_filter_list_or_system_default`
    for a `--where`/`--exclude`-shaped repeatable option: given the WHOLE
    accumulated list, decides whether it represents system-default, a
    contradiction, or concrete filters — the "does this list represent
    system-default" decision looks at every element together, exactly
    like the argparse version.

    **Call this from inside the Typer command body — do NOT pass it as
    `callback=` on a `list[str]`-typed `typer.Option`.** Typer generates
    its own post-callback list convertor for any `list[str]`-typed
    parameter (`typer.main.generate_list_convertor`) that runs AFTER a
    Click-level callback and assumes the result is still list-shaped (it
    unconditionally calls `len()` on it and collapses an explicit `[]`
    back to `None`) — that breaks the instant this function returns the
    `FORCE_SYSTEM_DEFAULT` sentinel instead of a list. Declare the option
    as a plain `list[str]` with no `callback=`, then call this function
    explicitly on the resulting list inside the command function (see
    `src/cli/commands/questions.py::_questions_command` for the pattern —
    found and fixed during marco 4A, 2026-08-20).

    Rules (identical to the argparse version — see its docstring for the
    full rationale): absent/empty -> `[]`; exactly one element,
    case-insensitively 'system-default' -> `FORCE_SYSTEM_DEFAULT`;
    exactly one element, case-insensitively 'null' -> rejected; more than
    one value where any element is 'system-default' -> rejected
    (contradiction — cannot combine with itself or a concrete filter);
    otherwise -> the list unchanged.

    Args:
        values: The raw accumulated list from Typer, or None/empty if
            never passed.

    Returns:
        `[]` if not provided, `FORCE_SYSTEM_DEFAULT` if explicitly
        cleared, or the original list of concrete filter strings.

    Raises:
        typer.BadParameter: for the deprecated 'null' literal, or
            'system-default' combined with any other value (including
            itself, repeated).
    """
    if not values:
        return []

    lowered = [v.lower() for v in values]

    if "system-default" in lowered:
        if len(values) > 1:
            raise typer.BadParameter(
                "'system-default' cannot be combined with a concrete filter "
                "(or repeated) — it means 'apply no filter', which "
                "contradicts specifying one. Pass it alone."
            )
        return FORCE_SYSTEM_DEFAULT

    if "null" in lowered:
        raise typer.BadParameter(_DEPRECATED_NULL_MESSAGE)

    return values
