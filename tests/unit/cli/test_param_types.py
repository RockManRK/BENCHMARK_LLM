"""Equivalence verification between src/cli/param_types.py (Typer
callbacks) and src/core/special_config_values.py (argparse types), run
before marco 4A's actual Typer command conversion — per the user's
2026-08-20 checklist:

- int, including zero
- float
- string
- system-default -> FORCE_SYSTEM_DEFAULT
- null rejected
- invalid value -> exit code 2
- absence -> None
- filter lists
- system-default + concrete-value contradiction
- structural selectors never normalized

Two gaps were found and fixed during this check (not pre-existing in
param_types.py before 2026-08-20): no Typer equivalent of
`normalize_filter_list_or_system_default` (list-shaped --where/--exclude),
and no Typer equivalent of `normalize_special_config_values`'s FORBIDDEN
branch (structural/identity flags rejecting 'system-default'/'null'
explicitly). Both are exercised here.

Exit-code-2 is proven empirically via a real Typer app + CliRunner
invocation, not asserted from documentation/framework claims.
"""

from __future__ import annotations

import typer
from typer.testing import CliRunner

from src.core.special_config_values import FORCE_SYSTEM_DEFAULT
from src.cli.param_types import (
    typer_int_or_system_default,
    typer_float_or_system_default,
    typer_str_or_system_default,
    typer_reject_special_values,
    typer_filter_list_or_system_default,
)

runner = CliRunner()


class TestTyperIntOrSystemDefault:
    def test_plain_int(self):
        assert typer_int_or_system_default("42") == 42

    def test_zero_preserved_distinct_from_none_and_force_system_default(self):
        result = typer_int_or_system_default("0")
        assert result == 0
        assert result is not None
        assert result != FORCE_SYSTEM_DEFAULT

    def test_negative_int(self):
        assert typer_int_or_system_default("-7") == -7

    def test_system_default(self):
        assert typer_int_or_system_default("system-default") is FORCE_SYSTEM_DEFAULT
        assert typer_int_or_system_default("System-Default") is FORCE_SYSTEM_DEFAULT

    def test_null_rejected(self):
        try:
            typer_int_or_system_default("null")
            assert False, "expected typer.BadParameter"
        except typer.BadParameter as e:
            assert "deprecated" in str(e).lower()
            assert "system-default" in str(e).lower()

    def test_absence_is_none(self):
        assert typer_int_or_system_default(None) is None

    def test_invalid_value_raises_bad_parameter(self):
        try:
            typer_int_or_system_default("not-a-number")
            assert False, "expected typer.BadParameter"
        except typer.BadParameter:
            pass


class TestTyperFloatOrSystemDefault:
    def test_plain_float(self):
        assert typer_float_or_system_default("0.7") == 0.7

    def test_zero_float_preserved(self):
        result = typer_float_or_system_default("0.0")
        assert result == 0.0
        assert result is not None

    def test_system_default(self):
        assert typer_float_or_system_default("system-default") is FORCE_SYSTEM_DEFAULT

    def test_null_rejected(self):
        try:
            typer_float_or_system_default("null")
            assert False, "expected typer.BadParameter"
        except typer.BadParameter:
            pass

    def test_absence_is_none(self):
        assert typer_float_or_system_default(None) is None

    def test_invalid_value_raises_bad_parameter(self):
        try:
            typer_float_or_system_default("abc")
            assert False, "expected typer.BadParameter"
        except typer.BadParameter:
            pass


class TestTyperStrOrSystemDefault:
    def test_plain_string(self):
        assert typer_str_or_system_default("high") == "high"

    def test_none_literal_preserved_as_string_not_special_cased(self):
        # 'none' is a valid reasoning_effort value — must NOT be treated
        # as FORCE_SYSTEM_DEFAULT or rejected, matching the argparse version.
        assert typer_str_or_system_default("none") == "none"

    def test_system_default(self):
        assert typer_str_or_system_default("system-default") is FORCE_SYSTEM_DEFAULT

    def test_null_rejected(self):
        try:
            typer_str_or_system_default("null")
            assert False, "expected typer.BadParameter"
        except typer.BadParameter:
            pass

    def test_absence_is_none(self):
        assert typer_str_or_system_default(None) is None


class TestTyperRejectSpecialValues:
    """Structural/identity flags (--experiment, --url, --create-experiment,
    etc.) — FORBIDDEN classification: 'system-default'/'null' must be
    explicitly rejected, never silently normalized or accepted."""

    def test_ordinary_value_passes_through_unchanged(self):
        assert typer_reject_special_values("my_experiment") == "my_experiment"

    def test_absence_is_none(self):
        assert typer_reject_special_values(None) is None

    def test_system_default_rejected(self):
        try:
            typer_reject_special_values("system-default")
            assert False, "expected typer.BadParameter"
        except typer.BadParameter as e:
            assert "does not accept" in str(e)

    def test_system_default_case_insensitive_rejected(self):
        try:
            typer_reject_special_values("System-Default")
            assert False, "expected typer.BadParameter"
        except typer.BadParameter:
            pass

    def test_null_rejected(self):
        try:
            typer_reject_special_values("null")
            assert False, "expected typer.BadParameter"
        except typer.BadParameter:
            pass

    def test_structural_selector_never_normalized_to_force_system_default(self):
        """A structural flag never becomes FORCE_SYSTEM_DEFAULT — it's
        either the literal value passed, or a rejection. There is no
        third outcome, unlike SUPPORTED scalar flags."""
        result = typer_reject_special_values("my_experiment")
        assert result != FORCE_SYSTEM_DEFAULT
        assert result is not FORCE_SYSTEM_DEFAULT


class TestTyperFilterListOrSystemDefault:
    def test_absent_returns_empty_list(self):
        assert typer_filter_list_or_system_default(None) == []

    def test_empty_list_returns_empty_list(self):
        assert typer_filter_list_or_system_default([]) == []

    def test_single_system_default_returns_force_system_default(self):
        assert typer_filter_list_or_system_default(["system-default"]) is FORCE_SYSTEM_DEFAULT

    def test_single_system_default_case_insensitive(self):
        assert typer_filter_list_or_system_default(["System-Default"]) is FORCE_SYSTEM_DEFAULT

    def test_concrete_filters_returned_unchanged(self):
        values = ["status=valid", "difficulty=hard"]
        assert typer_filter_list_or_system_default(values) == values

    def test_single_concrete_filter_returned_unchanged(self):
        assert typer_filter_list_or_system_default(["status=valid"]) == ["status=valid"]

    def test_single_null_rejected(self):
        try:
            typer_filter_list_or_system_default(["null"])
            assert False, "expected typer.BadParameter"
        except typer.BadParameter:
            pass

    def test_system_default_combined_with_concrete_filter_is_contradiction(self):
        try:
            typer_filter_list_or_system_default(["system-default", "status=valid"])
            assert False, "expected typer.BadParameter"
        except typer.BadParameter as e:
            assert "contradicts" in str(e).lower() or "combined" in str(e).lower()

    def test_system_default_repeated_is_contradiction(self):
        try:
            typer_filter_list_or_system_default(["system-default", "system-default"])
            assert False, "expected typer.BadParameter"
        except typer.BadParameter:
            pass


class TestExitCodeTwoEmpiricallyViaRealTyperApp:
    """Proves typer.BadParameter -> exit code 2 with a REAL Typer app
    invocation (CliRunner), not an assumption from framework docs —
    covers every callback added/verified in this equivalence check."""

    def _make_app(self, captured: dict | None = None):
        app = typer.Typer()

        @app.command()
        def cmd(
            max_tokens: str = typer.Option(None, "--max-tokens", callback=typer_int_or_system_default),
            temperature: str = typer.Option(None, "--temperature", callback=typer_float_or_system_default),
            reasoning: str = typer.Option(None, "--reasoning", callback=typer_str_or_system_default),
            experiment: str = typer.Option(None, "--experiment", callback=typer_reject_special_values),
            # NOT callback=typer_filter_list_or_system_default — see that
            # function's docstring: Typer's own post-callback list
            # convertor for list[str]-typed options runs AFTER a Click
            # callback and assumes a list-shaped result, which breaks the
            # moment the callback returns FORCE_SYSTEM_DEFAULT instead of
            # a list (found during marco 4A, 2026-08-20, fixed by moving
            # the call into the command body instead).
            where: list[str] = typer.Option(None, "--where"),
        ):
            where_resolved = typer_filter_list_or_system_default(where)
            if captured is not None:
                captured["where"] = where_resolved
            typer.echo("ok")

        return app

    def test_invalid_int_exits_2(self):
        result = runner.invoke(self._make_app(), ["--max-tokens", "not-a-number"])
        assert result.exit_code == 2

    def test_deprecated_null_on_supported_int_exits_2(self):
        result = runner.invoke(self._make_app(), ["--max-tokens", "null"])
        assert result.exit_code == 2

    def test_invalid_float_exits_2(self):
        result = runner.invoke(self._make_app(), ["--temperature", "abc"])
        assert result.exit_code == 2

    def test_deprecated_null_on_supported_str_exits_2(self):
        result = runner.invoke(self._make_app(), ["--reasoning", "null"])
        assert result.exit_code == 2

    def test_system_default_on_forbidden_flag_exits_2(self):
        result = runner.invoke(self._make_app(), ["--experiment", "system-default"])
        assert result.exit_code == 2

    def test_null_on_forbidden_flag_exits_2(self):
        result = runner.invoke(self._make_app(), ["--experiment", "null"])
        assert result.exit_code == 2

    def test_system_default_combined_with_filter_exits_2(self):
        result = runner.invoke(
            self._make_app(),
            ["--where", "system-default", "--where", "status=valid"],
        )
        assert result.exit_code == 2

    def test_valid_invocation_exits_0(self):
        result = runner.invoke(
            self._make_app(),
            [
                "--max-tokens", "0",
                "--temperature", "system-default",
                "--reasoning", "none",
                "--experiment", "my_exp",
                "--where", "status=valid",
            ],
        )
        assert result.exit_code == 0
        assert "ok" in result.stdout

    def test_where_absent_resolves_to_empty_list_not_none(self):
        """Regression for the bug found during marco 4A (2026-08-20):
        Typer's internal list-convertor was silently collapsing an
        explicit [] back to None when where was declared with
        callback=typer_filter_list_or_system_default directly."""
        captured: dict = {}
        result = runner.invoke(self._make_app(captured), ["--max-tokens", "1"])
        assert result.exit_code == 0
        assert captured["where"] == []

    def test_where_system_default_alone_resolves_to_sentinel_not_crash(self):
        """Regression for the second half of the same bug: the old
        callback= usage crashed with TypeError: object of type
        'ForceSystemDefault' has no len() inside Typer's own internals."""
        captured: dict = {}
        result = runner.invoke(self._make_app(captured), ["--where", "system-default"])
        assert result.exit_code == 0
        assert captured["where"] is FORCE_SYSTEM_DEFAULT

    def test_zero_survives_real_typer_invocation_distinct_from_absence(self):
        """End-to-end proof that '0' doesn't collapse into 'not passed'
        anywhere in the Typer plumbing (Click has a history of falsy-value
        foot-guns) — checked via the command's own echoed value."""
        app = typer.Typer()
        captured = {}

        @app.command()
        def cmd(max_tokens: str = typer.Option(None, "--max-tokens", callback=typer_int_or_system_default)):
            captured["value"] = max_tokens

        result = runner.invoke(app, ["--max-tokens", "0"])
        assert result.exit_code == 0
        assert captured["value"] == 0
        assert captured["value"] is not None
