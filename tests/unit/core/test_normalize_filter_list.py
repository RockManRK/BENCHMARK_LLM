"""Unit tests for src/core/special_config_values.py::normalize_filter_list_or_system_default.

The list-aware counterpart to normalize_special_config_values, built for
--where/--exclude (action="append", registered SUPPORTED in
docs/contracts/system-default-semantics.md, implementation reserved for
CLI Typer migration Fase 4 marco 4A — see docs/status/known-issues.md).
"""

import pytest

from src.core.special_config_values import normalize_filter_list_or_system_default, FORCE_SYSTEM_DEFAULT


class TestNotProvided:
    def test_none_returns_empty_list(self):
        assert normalize_filter_list_or_system_default(None) == []

    def test_empty_list_returns_empty_list(self):
        assert normalize_filter_list_or_system_default([]) == []


class TestSystemDefaultAlone:
    @pytest.mark.parametrize("case", ["system-default", "SYSTEM-DEFAULT", "System-Default"])
    def test_single_system_default_becomes_sentinel(self, case):
        assert normalize_filter_list_or_system_default([case]) is FORCE_SYSTEM_DEFAULT


class TestConcreteFiltersPassThrough:
    def test_single_concrete_filter_unchanged(self):
        assert normalize_filter_list_or_system_default(["status=valid"]) == ["status=valid"]

    def test_multiple_concrete_filters_allowed_and_unchanged(self):
        """Repeating --where for multiple AND-combined conditions is
        deliberately allowed, never an error."""
        result = normalize_filter_list_or_system_default(["meta.status=valid", "meta.has_image=false"])
        assert result == ["meta.status=valid", "meta.has_image=false"]


class TestNullRejected:
    @pytest.mark.parametrize("case", ["null", "NULL", "Null"])
    def test_single_null_raises(self, case):
        with pytest.raises(ValueError, match="deprecated"):
            normalize_filter_list_or_system_default([case])


class TestContradictionRejected:
    def test_system_default_plus_concrete_filter_raises(self):
        with pytest.raises(ValueError, match="cannot be combined"):
            normalize_filter_list_or_system_default(["system-default", "status=valid"])

    def test_concrete_filter_plus_system_default_raises_regardless_of_order(self):
        with pytest.raises(ValueError, match="cannot be combined"):
            normalize_filter_list_or_system_default(["status=valid", "system-default"])

    def test_system_default_repeated_raises(self):
        """system-default appearing twice is also a contradiction — it must
        appear exactly once, alone."""
        with pytest.raises(ValueError, match="cannot be combined"):
            normalize_filter_list_or_system_default(["system-default", "system-default"])

    def test_system_default_case_insensitive_repeated_raises(self):
        with pytest.raises(ValueError, match="cannot be combined"):
            normalize_filter_list_or_system_default(["system-default", "SYSTEM-DEFAULT"])
