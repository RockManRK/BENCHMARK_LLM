"""Tests for the logging configuration module.

This module tests the logging configuration, including log file creation,
rotation, structured formatting, and log level handling.
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest
from pytest_mock import MockerFixture


class TestLoggingConfig:
    """Test cases for logging configuration module."""

    def test_logging_config_module_exists(self) -> None:
        """Test that logging_config module can be imported."""
        try:
            from src.utils.logging_config import LoggingConfig
            assert LoggingConfig is not None
        except ImportError as e:
            pytest.fail(f"Failed to import LoggingConfig: {e}")

    def test_logging_config_initialization(self, tmp_path: Path) -> None:
        """Test that LoggingConfig initializes with log file path."""
        from src.utils.logging_config import LoggingConfig

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)

        assert config.log_file_path == log_file

    def test_logging_config_default_values(self, tmp_path: Path) -> None:
        """Test LoggingConfig default values."""
        from src.utils.logging_config import LoggingConfig

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)

        assert config.log_level == "INFO"
        assert config.max_bytes == 10 * 1024 * 1024  # 10MB default
        assert config.backup_count == 5

    def test_logging_config_custom_values(self, tmp_path: Path) -> None:
        """Test LoggingConfig with custom values."""
        from src.utils.logging_config import LoggingConfig

        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            log_file_path=log_file,
            log_level="DEBUG",
            max_bytes=5 * 1024 * 1024,
            backup_count=3,
        )

        assert config.log_level == "DEBUG"
        assert config.max_bytes == 5 * 1024 * 1024
        assert config.backup_count == 3

    def test_setup_logging_creates_logger(self, tmp_path: Path) -> None:
        """Test that setup_logging creates a logger instance."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_setup_logging_creates_log_file(self, tmp_path: Path) -> None:
        """Test that setup_logging creates the log file."""
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        # Log file should be created when handler is set up
        assert log_file.exists()

    def test_setup_logging_configures_log_level(self, tmp_path: Path) -> None:
        """Test that setup_logging configures the correct log level."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file, log_level="DEBUG")
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        assert logger.level == logging.DEBUG

    def test_setup_logging_configures_info_level(self, tmp_path: Path) -> None:
        """Test that setup_logging configures INFO level correctly."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file, log_level="INFO")
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        assert logger.level == logging.INFO

    def test_setup_logging_configures_warning_level(self, tmp_path: Path) -> None:
        """Test that setup_logging configures WARNING level correctly."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file, log_level="WARNING")
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        assert logger.level == logging.WARNING

    def test_setup_logging_configures_error_level(self, tmp_path: Path) -> None:
        """Test that setup_logging configures ERROR level correctly."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file, log_level="ERROR")
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        assert logger.level == logging.ERROR

    def test_setup_logging_uses_rotating_file_handler(self, tmp_path: Path) -> None:
        """Test that setup_logging uses RotatingFileHandler."""
        import logging
        from logging.handlers import RotatingFileHandler

        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        # Check that at least one handler is a RotatingFileHandler
        handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(handlers) > 0

    def test_rotating_handler_configured_with_max_bytes(self, tmp_path: Path) -> None:
        """Test that RotatingFileHandler is configured with correct max_bytes."""
        import logging
        from logging.handlers import RotatingFileHandler

        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        custom_max_bytes = 5 * 1024 * 1024  # 5MB
        config = LoggingConfig(log_file_path=log_file, max_bytes=custom_max_bytes)
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(handlers) > 0
        assert handlers[0].maxBytes == custom_max_bytes

    def test_rotating_handler_configured_with_backup_count(self, tmp_path: Path) -> None:
        """Test that RotatingFileHandler is configured with correct backup_count."""
        import logging
        from logging.handlers import RotatingFileHandler

        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        custom_backup_count = 3
        config = LoggingConfig(
            log_file_path=log_file, backup_count=custom_backup_count
        )
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(handlers) > 0
        assert handlers[0].backupCount == custom_backup_count

    def test_log_format_includes_timestamp(self, tmp_path: Path) -> None:
        """Test that log format includes timestamp."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = logging.getLogger()
        logger.info("Test message")

        log_content = log_file.read_text()
        # Timestamp should be in format like 2026-03-04 10:30:45
        assert any(c.isdigit() for c in log_content)  # Contains digits for date/time

    def test_log_format_includes_level(self, tmp_path: Path) -> None:
        """Test that log format includes log level."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = logging.getLogger()
        logger.info("Test message")

        log_content = log_file.read_text()
        assert "INFO" in log_content

    def test_log_format_includes_logger_name(self, tmp_path: Path) -> None:
        """Test that log format includes logger name."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = logging.getLogger()
        logger.info("Test message")

        log_content = log_file.read_text()
        assert "benchmark_llm" in log_content or "root" in log_content

    def test_log_format_includes_message(self, tmp_path: Path) -> None:
        """Test that log format includes the log message."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = logging.getLogger()
        test_message = "Test message for verification"
        logger.info(test_message)

        log_content = log_file.read_text()
        assert test_message in log_content

    def test_log_format_structured(self, tmp_path: Path) -> None:
        """Test that log format is structured with all components."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = logging.getLogger()
        logger.info("Test message")

        log_content = log_file.read_text().strip()
        # Format should be: TIMESTAMP - LEVEL - LOGGER - MESSAGE
        parts = log_content.split(" - ")
        assert len(parts) >= 4  # At least timestamp, level, logger, message

    def test_multiple_log_levels(self, tmp_path: Path) -> None:
        """Test logging at different levels."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file, log_level="DEBUG")
        setup_logging(config)

        logger = logging.getLogger()
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        log_content = log_file.read_text()
        assert "DEBUG" in log_content
        assert "INFO" in log_content
        assert "WARNING" in log_content
        assert "ERROR" in log_content

    def test_log_level_filtering(self, tmp_path: Path) -> None:
        """Test that log level filtering works correctly."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file, log_level="WARNING")
        setup_logging(config)

        logger = logging.getLogger()
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        log_content = log_file.read_text()
        # DEBUG and INFO should be filtered out
        assert "Debug message" not in log_content
        assert "Info message" not in log_content
        # WARNING and ERROR should be present
        assert "Warning message" in log_content
        assert "Error message" in log_content

    def test_get_structured_logger(self, tmp_path: Path) -> None:
        """Test get_structured_logger function."""
        import logging
        
        from src.utils.logging_config import (
            LoggingConfig,
            setup_logging,
            get_structured_logger,
        )

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = get_structured_logger("test_component")
        assert logger is not None
        # Component logger is a child of root logger
        assert "test_component" in logger.name

    def test_structured_logger_inherits_configuration(self, tmp_path: Path) -> None:
        """Test that structured logger inherits parent configuration."""
        import logging
        
        from src.utils.logging_config import (
            LoggingConfig,
            setup_logging,
            get_structured_logger,
        )

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file, log_level="DEBUG")
        setup_logging(config)

        child_logger = get_structured_logger("api")

        # Child should inherit parent's effective level through logging hierarchy
        assert child_logger.getEffectiveLevel() == logging.DEBUG

    def test_log_api_request_format(self, tmp_path: Path) -> None:
        """Test logging API request with structured format."""
        from src.utils.logging_config import (
            LoggingConfig,
            setup_logging,
            get_structured_logger,
        )

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = get_structured_logger("api")
        logger.info("API_REQUEST | endpoint=/v1/chat/completions | model=gpt-4 | timestamp=2026-03-04T10:30:45")

        log_content = log_file.read_text()
        assert "API_REQUEST" in log_content
        assert "endpoint=/v1/chat/completions" in log_content
        assert "model=gpt-4" in log_content

    def test_log_api_response_format(self, tmp_path: Path) -> None:
        """Test logging API response with structured format."""
        from src.utils.logging_config import (
            LoggingConfig,
            setup_logging,
            get_structured_logger,
        )

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = get_structured_logger("api")
        logger.info(
            "API_RESPONSE | status=success | input_tokens=50 | response_tokens=20 | latency_ms=1200"
        )

        log_content = log_file.read_text()
        assert "API_RESPONSE" in log_content
        assert "status=success" in log_content
        assert "input_tokens=50" in log_content
        assert "response_tokens=20" in log_content
        assert "latency_ms=1200" in log_content

    def test_log_execution_progress_format(self, tmp_path: Path) -> None:
        """Test logging execution progress with structured format."""
        from src.utils.logging_config import (
            LoggingConfig,
            setup_logging,
            get_structured_logger,
        )

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        logger = get_structured_logger("execution")
        logger.info(
            "PROGRESS | run_id=run-001 | model=gpt-4 | iteration=1 | question=Q001 | total=100"
        )

        log_content = log_file.read_text()
        assert "PROGRESS" in log_content
        assert "run_id=run-001" in log_content
        assert "model=gpt-4" in log_content
        assert "iteration=1" in log_content

    def test_log_configuration_at_startup(self, tmp_path: Path) -> None:
        """Test logging configuration at startup."""
        from src.utils.logging_config import (
            LoggingConfig,
            setup_logging,
            get_structured_logger,
        )

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        logger = setup_logging(config)

        startup_logger = get_structured_logger("startup")
        startup_logger.info(
            "CONFIG | database_path=./data/benchmark.db | log_level=INFO | default_iterations=1"
        )

        log_content = log_file.read_text()
        assert "CONFIG" in log_content
        assert "database_path=" in log_content
        assert "log_level=INFO" in log_content


class TestLoggingConfigValidation:
    """Test cases for logging configuration validation."""

    def test_invalid_log_level_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid log level raises ValueError."""
        from src.utils.logging_config import LoggingConfig

        log_file = tmp_path / "test.log"

        with pytest.raises(ValueError, match="Invalid log level"):
            LoggingConfig(log_file_path=log_file, log_level="INVALID")

    def test_valid_log_levels(self, tmp_path: Path) -> None:
        """Test all valid log levels."""
        from src.utils.logging_config import LoggingConfig

        log_file = tmp_path / "test.log"
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            config = LoggingConfig(log_file_path=log_file, log_level=level)
            assert config.log_level == level

    def test_log_level_case_insensitive(self, tmp_path: Path) -> None:
        """Test that log level is case-insensitive."""
        from src.utils.logging_config import LoggingConfig

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file, log_level="debug")

        assert config.log_level == "DEBUG"

    def test_max_bytes_cannot_be_negative(self, tmp_path: Path) -> None:
        """Test that max_bytes cannot be negative."""
        from src.utils.logging_config import LoggingConfig

        log_file = tmp_path / "test.log"

        with pytest.raises(ValueError, match="max_bytes must be positive"):
            LoggingConfig(log_file_path=log_file, max_bytes=-1)

    def test_backup_count_cannot_be_negative(self, tmp_path: Path) -> None:
        """Test that backup_count cannot be negative."""
        from src.utils.logging_config import LoggingConfig

        log_file = tmp_path / "test.log"

        with pytest.raises(ValueError, match="backup_count must be non-negative"):
            LoggingConfig(log_file_path=log_file, backup_count=-1)


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_log_rotation(self, tmp_path: Path) -> None:
        """Test that log rotation works correctly."""
        import logging
        from logging.handlers import RotatingFileHandler

        from src.utils.logging_config import LoggingConfig, setup_logging

        # Create a very small max_bytes to trigger rotation quickly
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            log_file_path=log_file,
            max_bytes=100,  # Very small for testing
            backup_count=2,
        )
        setup_logging(config)

        # Get the root logger that was configured
        logger = logging.getLogger()
        
        # Write enough to trigger rotation
        for i in range(20):
            logger.info(f"This is a test message number {i} with some extra text to make it longer")

        # Check that backup files were created
        backup_files = list(tmp_path.glob("test.log.*"))
        assert len(backup_files) > 0

    def test_log_file_permissions(self, tmp_path: Path) -> None:
        """Test that log file has correct permissions."""
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        # File should be readable
        assert os.access(log_file, os.R_OK)
        # File should be writable
        assert os.access(log_file, os.W_OK)

    def test_concurrent_logging(self, tmp_path: Path) -> None:
        """Test that multiple loggers can write to the same file."""
        import logging
        
        from src.utils.logging_config import LoggingConfig, setup_logging

        log_file = tmp_path / "test.log"
        config = LoggingConfig(log_file_path=log_file)
        setup_logging(config)

        # Get root logger and create a child logger
        root_logger = logging.getLogger()
        child_logger = logging.getLogger("benchmark_llm.child")

        root_logger.info("Message from root logger")
        child_logger.info("Message from child logger")

        log_content = log_file.read_text()
        assert "Message from root logger" in log_content
        assert "Message from child logger" in log_content
