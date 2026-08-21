"""Tests for the Checkpoint C additions to logging_config.py: LOG_PROFILE
config/validation and the JSONL sibling handler."""

import json
import logging
import os
from pathlib import Path

import pytest

from src.utils.log_emitter import JSONL_LOGGER_NAME, emit_event
from src.utils.log_events import Event
from src.utils.logging_config import (
    LoggingConfig,
    _get_log_profile_from_env,
    _jsonl_path_for,
    setup_logging,
)


class TestLogProfileConfig:
    def test_default_profile_is_normal(self, tmp_path: Path):
        config = LoggingConfig(log_file_path=tmp_path / "test.log")
        assert config.log_profile == "NORMAL"

    def test_custom_profile_accepted(self, tmp_path: Path):
        config = LoggingConfig(log_file_path=tmp_path / "test.log", log_profile="trace")
        assert config.log_profile == "TRACE"

    def test_invalid_profile_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="LOG_PROFILE"):
            LoggingConfig(log_file_path=tmp_path / "test.log", log_profile="VERBOSE")

    def test_env_var_read(self, monkeypatch):
        monkeypatch.setenv("LOG_PROFILE", "DETAILED")
        assert _get_log_profile_from_env() == "DETAILED"

    def test_env_var_defaults_to_normal_when_unset(self, monkeypatch):
        monkeypatch.delenv("LOG_PROFILE", raising=False)
        assert _get_log_profile_from_env() == "NORMAL"


class TestJsonlPathDerivation:
    def test_sibling_jsonl_path(self):
        assert _jsonl_path_for(Path("./logs/benchmark.log")) == Path("./logs/benchmark.jsonl")

    def test_same_directory(self, tmp_path: Path):
        log_path = tmp_path / "custom.log"
        jsonl_path = _jsonl_path_for(log_path)
        assert jsonl_path.parent == log_path.parent


class TestJsonlHandlerWiring:
    def test_setup_logging_creates_jsonl_file_on_emit(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = logging.getLogger("benchmark_llm.test_module")
        emit_event(logger, Event.COMMAND_START, command="add-model", operation_id="op_test123")

        jsonl_file = tmp_path / "test.jsonl"
        assert jsonl_file.exists()
        content = jsonl_file.read_text(encoding="utf-8").strip()
        assert content  # at least one line written
        line = json.loads(content.splitlines()[-1])
        assert line["event_name"] == Event.COMMAND_START
        assert line["operation_id"] == "op_test123"
        assert line["command"] == "add-model"
        assert line["schema_version"] == 1

    def test_jsonl_logger_does_not_propagate_to_root(self, tmp_path: Path):
        """A JSONL line must not also appear duplicated in the
        human-readable file/console via propagation."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        jsonl_logger = logging.getLogger(JSONL_LOGGER_NAME)
        assert jsonl_logger.propagate is False

    def test_human_file_unaffected_by_jsonl_wiring(self, tmp_path: Path):
        """Existing plain logger.info() calls (not through emit_event)
        still only produce the human-readable line — no behavior change."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = logging.getLogger("benchmark_llm.test_module")
        logger.info("PLAIN_EVENT | foo=bar")

        content = log_file.read_text(encoding="utf-8")
        assert "PLAIN_EVENT | foo=bar" in content

        jsonl_file = tmp_path / "test.jsonl"
        # The plain call never went through emit_event, so it must not
        # have produced a JSONL line.
        if jsonl_file.exists():
            assert jsonl_file.read_text(encoding="utf-8").strip() == ""
