"""Unit tests for src/core/special_config_values.py::normalize_special_config_values.

Renamed 2026-08-19 from test_null_normalization.py, testing the redesigned
function directly (was normalize_nulls_explicit, exposed via argv_utils.py's
now-deleted normalize_nulls/_is_nullable_arg duplicates — see
docs/status/known-issues.md).

Old behavior (deleted): ANY argparse action with default=None and
required=False was treated as eligible for system-default normalization —
a heuristic that could not distinguish configuration values from identity/
structural flags, and silently mis-normalized things like --run,
--remove-run, --create-experiment (see the "blanket sweep" bug entry in
known-issues.md).

New behavior (this file): eligibility is explicit and opt-in via two sets
of dest names passed by the caller — `supported` (system-default has real
semantics) and `forbidden` (system-default/null must be explicitly
rejected). A dest in neither set is never inspected, regardless of its
argparse default/required metadata.

Normalization rules for SUPPORTED dests:
1. 'system-default' (case-insensitive) -> FORCE_SYSTEM_DEFAULT
2. 'null' (case-insensitive) -> raises ArgumentError with migration hint
3. 'none' (any case) -> preserved as literal string
4. Non-string values (int, bool, None, list) -> untouched

Normalization rules for FORBIDDEN dests:
1. 'system-default' or 'null' (case-insensitive) -> raises ArgumentError
2. Any other value, including a normal identifier -> untouched
"""

import argparse
import pytest
from src.core.special_config_values import normalize_special_config_values, FORCE_SYSTEM_DEFAULT


@pytest.fixture
def parser() -> argparse.ArgumentParser:
    """A parser with a mix of dest kinds — classification is entirely
    driven by the `supported`/`forbidden` sets passed to each test, not by
    any argparse metadata (default=None/required=False no longer matters)."""
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=str, default=None, required=False)
    p.add_argument("--vision", type=str, default=None, required=False)
    p.add_argument("--run", type=str, default=None, required=False)
    p.add_argument("--experiment", type=str, required=True)
    p.add_argument("--output", type=str, default="console", required=False)
    p.add_argument("--count", type=int, default=0)
    p.add_argument("--tags", action="append", default=None, required=False)
    return p


# =============================================================================
# Part 1: SUPPORTED — 'system-default' -> FORCE_SYSTEM_DEFAULT
# =============================================================================

class TestSupportedSystemDefaultNormalization:
    @pytest.mark.parametrize("case", ["system-default", "SYSTEM-DEFAULT", "System-Default", "SyStEm-DeFaUlT"])
    def test_case_insensitive_system_default(self, parser, case):
        args = argparse.Namespace(seed=case, vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"})
        assert result.seed is FORCE_SYSTEM_DEFAULT

    def test_multiple_supported_dests_all_normalized(self, parser):
        args = argparse.Namespace(seed="system-default", vision="SYSTEM-DEFAULT", run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed", "vision"})
        assert result.seed is FORCE_SYSTEM_DEFAULT
        assert result.vision is FORCE_SYSTEM_DEFAULT

    def test_idempotent(self, parser):
        args = argparse.Namespace(seed="system-default", vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result1 = normalize_special_config_values(args, parser, supported={"seed"})
        result2 = normalize_special_config_values(result1, parser, supported={"seed"})
        assert result2.seed is FORCE_SYSTEM_DEFAULT


class TestSupportedNonePreservedLiteral:
    @pytest.mark.parametrize("case", ["none", "NONE", "None", "NoNe"])
    def test_none_preserved(self, parser, case):
        """'none' is a valid literal value (e.g. reasoning_effort) — never special-cased."""
        args = argparse.Namespace(seed=case, vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"})
        assert result.seed == case


class TestSupportedNullRejected:
    @pytest.mark.parametrize("case", ["null", "NULL", "Null", "nUlL"])
    def test_null_raises_argument_error(self, parser, case):
        args = argparse.Namespace(seed=case, vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            normalize_special_config_values(args, parser, supported={"seed"})


class TestSupportedNonMatchingValuesUntouched:
    def test_empty_string_not_normalized(self, parser):
        args = argparse.Namespace(seed="", vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"})
        assert result.seed == ""

    def test_whitespace_string_not_normalized(self, parser):
        args = argparse.Namespace(seed=" system-default ", vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"})
        assert result.seed == " system-default "

    def test_extra_characters_not_normalized(self, parser):
        args = argparse.Namespace(seed="system-defaults", vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"})
        assert result.seed == "system-defaults"

    def test_unicode_lookalike_not_normalized(self, parser):
        args = argparse.Namespace(seed="ѕуѕтєм-δεƒαυℓт", vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"})
        assert result.seed == "ѕуѕтєм-δεƒαυℓт"

    @pytest.mark.parametrize("value", [42, 0, True, False, None, 3.14])
    def test_non_string_values_untouched(self, parser, value):
        args = argparse.Namespace(seed=value, vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"})
        assert result.seed == value or result.seed is value

    def test_list_value_untouched_even_containing_system_default(self, parser):
        """Append-action values are lists — never inspected, regardless of registration."""
        args = argparse.Namespace(seed=None, vision=None, run=None, experiment="x", output="console", count=0, tags=["system-default", "system-default"])
        result = normalize_special_config_values(args, parser, supported={"tags"})
        assert result.tags == ["system-default", "system-default"]


# =============================================================================
# Part 2: FORBIDDEN — 'system-default'/'null' explicitly rejected
# =============================================================================

class TestForbiddenRejectsSystemDefaultAndNull:
    @pytest.mark.parametrize("case", ["system-default", "SYSTEM-DEFAULT", "null", "NULL"])
    def test_forbidden_dest_rejects(self, parser, case):
        args = argparse.Namespace(seed=None, vision=None, run=case, experiment="x", output="console", count=0, tags=None)
        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            normalize_special_config_values(args, parser, forbidden={"run"})

    def test_forbidden_dest_ordinary_value_untouched(self, parser):
        args = argparse.Namespace(seed=None, vision=None, run="run_abc123", experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, forbidden={"run"})
        assert result.run == "run_abc123"

    def test_forbidden_dest_none_value_untouched(self, parser):
        args = argparse.Namespace(seed=None, vision=None, run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, forbidden={"run"})
        assert result.run is None

    def test_forbidden_and_supported_evaluated_independently(self, parser):
        args = argparse.Namespace(seed="system-default", vision=None, run="system-default", experiment="x", output="console", count=0, tags=None)
        supported_result_raised = False
        try:
            normalize_special_config_values(args, parser, supported={"seed"}, forbidden={"run"})
        except argparse.ArgumentError:
            supported_result_raised = True
        assert supported_result_raised, "forbidden dest 'run' must still raise even though 'seed' is legitimately supported"


# =============================================================================
# Part 3: Not in either set — never inspected (the fix for the old
# default=None/required=False heuristic)
# =============================================================================

class TestUnregisteredDestNeverInspected:
    def test_unregistered_dest_with_system_default_untouched(self, parser):
        """Regression: under the OLD heuristic, --experiment (default=None
        if optional elsewhere) or any unregistered optional dest would have
        been silently normalized. Now it is simply never looked at."""
        args = argparse.Namespace(seed=None, vision="system-default", run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"}, forbidden={"run"})
        assert result.vision == "system-default"

    def test_unregistered_dest_with_null_not_rejected(self, parser):
        args = argparse.Namespace(seed=None, vision="null", run=None, experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"}, forbidden={"run"})
        assert result.vision == "null"

    def test_no_sets_passed_pure_parse_no_normalization(self, parser):
        args = argparse.Namespace(seed="system-default", vision=None, run="system-default", experiment="x", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser)
        assert result.seed == "system-default"
        assert result.run == "system-default"

    def test_required_dest_with_default_value_provided_untouched(self, parser):
        """--experiment is required=True — under the OLD heuristic it was
        already correctly excluded; confirm it stays excluded here too
        when simply not registered."""
        args = argparse.Namespace(seed=None, vision=None, run=None, experiment="system-default", output="console", count=0, tags=None)
        result = normalize_special_config_values(args, parser, supported={"seed"}, forbidden={"run"})
        assert result.experiment == "system-default"
