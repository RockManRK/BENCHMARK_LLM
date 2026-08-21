"""Tests for src.utils.log_emitter — the single event-emission API
(Checkpoint C). Covers: severity floor (WARNING+ never suppressed by
profile), profile gating for INFO/DEBUG events, redaction applied
unconditionally, and that a logging failure never raises out of
emit_event (must never break execution)."""

import json
import logging

import pytest

from src.utils.log_emitter import emit_event, JSONL_LOGGER_NAME
from src.utils.log_events import Event


@pytest.fixture
def capturing_logger():
    """A real logging.Logger with an in-memory handler capturing records,
    isolated per test."""
    logger = logging.getLogger("test.emitter.human")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger.addHandler(_Capture())
    return logger, records


@pytest.fixture
def capturing_jsonl():
    """Captures whatever emit_event writes to the JSONL logger."""
    jsonl_logger = logging.getLogger(JSONL_LOGGER_NAME)
    jsonl_logger.handlers.clear()
    jsonl_logger.setLevel(logging.DEBUG)
    jsonl_logger.propagate = False
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    jsonl_logger.addHandler(_Capture())
    return records


class TestSeverityFloor:
    def test_warning_event_emitted_regardless_of_profile(
        self, capturing_logger, capturing_jsonl, monkeypatch
    ):
        monkeypatch.setenv("LOG_PROFILE", "MINIMAL")
        logger, records = capturing_logger
        # RETRY_ATTEMPT defaults to NORMAL in EVENT_PROFILE, well above MINIMAL
        emit_event(logger, Event.RETRY_ATTEMPT, level=logging.WARNING, attempt=1)
        assert len(records) == 1

    def test_error_event_emitted_regardless_of_profile(
        self, capturing_logger, capturing_jsonl, monkeypatch
    ):
        monkeypatch.setenv("LOG_PROFILE", "MINIMAL")
        logger, records = capturing_logger
        emit_event(logger, Event.API_ERROR, level=logging.ERROR, error_type="timeout")
        assert len(records) == 1

    def test_info_detailed_event_suppressed_at_minimal(
        self, capturing_logger, capturing_jsonl, monkeypatch
    ):
        monkeypatch.setenv("LOG_PROFILE", "MINIMAL")
        logger, records = capturing_logger
        emit_event(logger, Event.CONFIG_RESOLVED, level=logging.INFO, resolved={})
        assert len(records) == 0

    def test_info_detailed_event_emitted_at_detailed(
        self, capturing_logger, capturing_jsonl, monkeypatch
    ):
        monkeypatch.setenv("LOG_PROFILE", "DETAILED")
        logger, records = capturing_logger
        emit_event(logger, Event.CONFIG_RESOLVED, level=logging.INFO, resolved={})
        assert len(records) == 1


class TestProfileGating:
    @pytest.mark.parametrize(
        "profile,expect_emitted",
        [
            ("MINIMAL", False),
            ("NORMAL", True),
            ("DETAILED", True),
            ("TRACE", True),
        ],
    )
    def test_normal_tier_event_gating(
        self, capturing_logger, capturing_jsonl, monkeypatch, profile, expect_emitted
    ):
        monkeypatch.setenv("LOG_PROFILE", profile)
        logger, records = capturing_logger
        emit_event(logger, Event.ITEM_COMPLETE, level=logging.INFO, response_id="r1")
        assert (len(records) == 1) == expect_emitted

    def test_trace_only_event_suppressed_below_trace(
        self, capturing_logger, capturing_jsonl, monkeypatch
    ):
        monkeypatch.setenv("LOG_PROFILE", "DETAILED")
        logger, records = capturing_logger
        emit_event(logger, Event.REQUEST_PAYLOAD_TRACE, level=logging.DEBUG, payload={})
        assert len(records) == 0

    def test_trace_only_event_emitted_at_trace(
        self, capturing_logger, capturing_jsonl, monkeypatch
    ):
        monkeypatch.setenv("LOG_PROFILE", "TRACE")
        logger, records = capturing_logger
        emit_event(logger, Event.REQUEST_PAYLOAD_TRACE, level=logging.DEBUG, payload={})
        assert len(records) == 1

    def test_cumulative_normal_events_still_present_at_trace(
        self, capturing_logger, capturing_jsonl, monkeypatch
    ):
        monkeypatch.setenv("LOG_PROFILE", "TRACE")
        logger, records = capturing_logger
        emit_event(logger, Event.ITEM_COMPLETE, level=logging.INFO, response_id="r1")
        assert len(records) == 1


class TestRedactionApplied:
    def test_secret_field_redacted_in_human_line(self, capturing_logger, capturing_jsonl):
        logger, records = capturing_logger
        emit_event(logger, Event.API_REQUEST, level=logging.INFO, api_key="sk-abc123")
        message = records[0].getMessage()
        assert "sk-abc123" not in message

    def test_secret_field_redacted_in_jsonl_line(self, capturing_logger, capturing_jsonl):
        logger, records = capturing_logger
        emit_event(logger, Event.API_REQUEST, level=logging.INFO, api_key="sk-abc123")
        assert len(capturing_jsonl) == 1
        parsed = json.loads(capturing_jsonl[0])
        assert parsed["api_key"] != "sk-abc123"

    def test_caller_kwargs_dict_not_mutated(self, capturing_logger, capturing_jsonl):
        logger, records = capturing_logger
        original_fields = {"api_key": "sk-abc123", "model": "openai/gpt-4"}
        emit_event(logger, Event.API_REQUEST, level=logging.INFO, **original_fields)
        assert original_fields["api_key"] == "sk-abc123"  # caller's dict untouched


class TestJsonlEnvelope:
    def test_envelope_has_required_fields(self, capturing_logger, capturing_jsonl):
        logger, records = capturing_logger
        emit_event(
            logger, Event.ITEM_COMPLETE, level=logging.INFO,
            operation_id="op_abc123", run_id="run_1",
        )
        parsed = json.loads(capturing_jsonl[0])
        assert "timestamp" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["event_name"] == Event.ITEM_COMPLETE
        assert parsed["schema_version"] == 1
        assert parsed["operation_id"] == "op_abc123"
        assert parsed["run_id"] == "run_1"

    def test_operation_id_omitted_when_not_given(self, capturing_logger, capturing_jsonl):
        logger, records = capturing_logger
        emit_event(logger, Event.APPLICATION_START, level=logging.INFO)
        parsed = json.loads(capturing_jsonl[0])
        assert "operation_id" not in parsed

    def test_family_specific_fields_not_forced_null(self, capturing_logger, capturing_jsonl):
        logger, records = capturing_logger
        emit_event(logger, Event.RETRY_ATTEMPT, level=logging.INFO, attempt_number=2)
        parsed = json.loads(capturing_jsonl[0])
        assert "response_id" not in parsed  # irrelevant field never forced to null
        assert parsed["attempt_number"] == 2


class TestLoggingNeverBreaksExecution:
    def test_redaction_failure_does_not_raise(self, capturing_logger, capturing_jsonl, monkeypatch):
        """If something inside the emission path raises unexpectedly,
        emit_event must swallow it, never propagate to the caller."""
        import src.utils.log_emitter as emitter_module

        def _boom(obj):
            raise RuntimeError("simulated redaction failure")

        monkeypatch.setattr(emitter_module, "redact", _boom)
        logger, records = capturing_logger
        # Must not raise:
        emit_event(logger, Event.ITEM_COMPLETE, level=logging.INFO, response_id="r1")

    def test_jsonl_handler_failure_does_not_raise(self, capturing_logger, monkeypatch):
        import src.utils.log_emitter as emitter_module

        class _ExplodingLogger:
            def log(self, *a, **kw):
                raise OSError("disk full")

        monkeypatch.setattr(emitter_module, "_get_jsonl_logger", lambda: _ExplodingLogger())
        logger, records = capturing_logger
        # Must not raise, even though the JSONL logger explodes:
        emit_event(logger, Event.ITEM_COMPLETE, level=logging.INFO, response_id="r1")
        # The human-readable line, written before the JSONL explosion,
        # must have gone through successfully — a JSONL handler failure
        # must not retroactively lose the human-readable record either.
        # (A second record is the emitter's own best-effort
        # LOG_EMIT_FAILED fallback line — expected, not a bug.)
        messages = [r.getMessage() for r in records]
        assert any("ITEM_COMPLETE" in m for m in messages)
        assert any("LOG_EMIT_FAILED" in m for m in messages)
