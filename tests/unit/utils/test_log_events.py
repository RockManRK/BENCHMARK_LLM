"""Tests for src.utils.log_events — the centralized event vocabulary and
depth-profile tiers (Checkpoint C)."""

import pytest

from src.utils.log_events import Event, EVENT_PROFILE, LogProfile


class TestLogProfile:
    def test_cumulative_ordering(self):
        assert LogProfile.MINIMAL < LogProfile.NORMAL < LogProfile.DETAILED < LogProfile.TRACE

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("MINIMAL", LogProfile.MINIMAL),
            ("normal", LogProfile.NORMAL),
            ("Detailed", LogProfile.DETAILED),
            ("  TRACE  ", LogProfile.TRACE),
        ],
    )
    def test_from_str_case_and_whitespace_insensitive(self, raw, expected):
        assert LogProfile.from_str(raw) == expected

    def test_from_str_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid LOG_PROFILE"):
            LogProfile.from_str("VERBOSE")

    def test_from_str_none_raises(self):
        with pytest.raises(ValueError):
            LogProfile.from_str(None)


class TestEventVocabulary:
    def test_no_duplicate_event_name_values(self):
        """Every Event constant must have a unique string value — two
        different constants accidentally sharing a value would silently
        merge two distinct concepts in the JSONL stream."""
        names = [v for k, v in vars(Event).items() if not k.startswith("_")]
        assert len(names) == len(set(names)), "duplicate event_name value found"

    def test_all_event_names_are_lowercase_snake_case(self):
        names = [v for k, v in vars(Event).items() if not k.startswith("_")]
        for name in names:
            assert name == name.lower(), f"{name} is not lowercase"
            assert " " not in name, f"{name} contains a space"

    def test_command_lifecycle_events_are_minimal(self):
        assert EVENT_PROFILE[Event.COMMAND_START] == LogProfile.MINIMAL
        assert EVENT_PROFILE[Event.COMMAND_END] == LogProfile.MINIMAL
        assert EVENT_PROFILE[Event.COMMAND_INTERRUPTED] == LogProfile.MINIMAL

    def test_config_resolution_events_are_detailed(self):
        assert EVENT_PROFILE[Event.CONFIG_RESOLVED] == LogProfile.DETAILED
        assert EVENT_PROFILE[Event.INHERITANCE_DECISION] == LogProfile.DETAILED
        assert EVENT_PROFILE[Event.SYSTEM_DEFAULT_APPLIED] == LogProfile.DETAILED

    def test_trace_only_events_are_trace(self):
        assert EVENT_PROFILE[Event.REQUEST_PAYLOAD_TRACE] == LogProfile.TRACE
        assert EVENT_PROFILE[Event.UPSTREAM_ECHO_TRACE] == LogProfile.TRACE
        assert EVENT_PROFILE[Event.STREAM_CHUNK_TRACE] == LogProfile.TRACE

    def test_unmapped_event_defaults_handled_by_caller_not_here(self):
        """EVENT_PROFILE intentionally does not contain every Event constant
        (e.g. WARNING/ERROR-severity events like RETRY_EXHAUSTED bypass the
        profile gate entirely per the severity-floor rule) — this test just
        pins that RETRY_EXHAUSTED is deliberately absent, not forgotten."""
        assert Event.RETRY_EXHAUSTED not in EVENT_PROFILE
        assert Event.API_ERROR not in EVENT_PROFILE
