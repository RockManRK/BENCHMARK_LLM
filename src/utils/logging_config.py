"""Logging configuration module for benchmark_llm.

This module implements the logging infrastructure following the system contract
"Logs are scientific data". It provides crash-safe, structured logging with
immediate flush on every write.

Key principles:
- No global logger state - logger instances are injected explicitly
- Immediate flush on every write - crash-safety
- Structured, machine-parseable format
- Context explicitness - all entries include explicit context
- Log retention via archiving, not deletion
- Environment-based configuration
"""

import logging
import os
from logging import LogRecord, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class FlushingRotatingFileHandler(RotatingFileHandler):
    """Rotating file handler that flushes after every write.
    
    This handler ensures crash-safety by flushing immediately after each
    log entry is written, preventing data loss in case of system failure.
    """
    
    def emit(self, record: LogRecord) -> None:
        """Emit a record with immediate flush.
        
        Args:
            record: The log record to emit.
        """
        super().emit(record)
        self.flush()


class FlushingStreamHandler(StreamHandler):
    """Stream handler that flushes after every write.
    
    This handler ensures crash-safety by flushing immediately after each
    log entry is written, preventing data loss in case of system failure.
    """
    
    def emit(self, record: LogRecord) -> None:
        """Emit a record with immediate flush.
        
        Args:
            record: The log record to emit.
        """
        super().emit(record)
        self.flush()


class LoggingConfig:
    """Configuration for logging system.
    
    This class encapsulates all configuration parameters for the logging
    system. It validates configuration values to ensure they are within
    acceptable ranges.
    
    Attributes:
        log_file_path: Path to the log file.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        max_bytes: Maximum size in bytes before rotation (default 10MB).
        backup_count: Number of backup files to retain (default 5).
        log_format: Format string for log entries.
    """
    
    VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DEFAULT_MAX_BYTES = 10 * 1024 * 1024
    DEFAULT_BACKUP_COUNT = 5
    
    def __init__(
        self,
        log_file_path: Path = Path("./logs/benchmark.log"),
        log_level: str = "INFO",
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        log_format: str = DEFAULT_LOG_FORMAT,
    ) -> None:
        """Initialize logging configuration.
        
        Args:
            log_file_path: Path to the log file. Defaults to ./logs/benchmark.log.
            log_level: Logging level. Defaults to INFO.
            max_bytes: Maximum file size before rotation. Defaults to 10MB.
            backup_count: Number of backup files to retain. Defaults to 5.
            log_format: Format string for log entries. Defaults to standard format.
        """
        self.log_file_path = log_file_path
        self.log_level = log_level.upper()
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.log_format = log_format
        
        self.validate()
    
    def validate(self) -> None:
        """Validate configuration parameters.
        
        Raises:
            ValueError: If any configuration parameter is invalid.
        """
        if self.log_level not in self.VALID_LOG_LEVELS:
            raise ValueError(
                f"Invalid log level '{self.log_level}'. "
                f"Valid levels are: {', '.join(self.VALID_LOG_LEVELS)}"
            )
        
        if self.max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        
        if self.backup_count < 0:
            raise ValueError("backup_count must be non-negative")


def _get_log_level_from_env() -> str:
    """Get log level from environment variable.
    
    Returns:
        Log level string from LOG_LEVEL env var, or 'INFO' if not set.
    """
    return os.environ.get("LOG_LEVEL", "INFO")


def _get_log_file_path_from_env() -> Path:
    """Get log file path from environment variable.
    
    Returns:
        Log file path from LOG_FILE_PATH env var, or default path if not set.
    """
    path_str = os.environ.get("LOG_FILE_PATH", "./logs/benchmark.log")
    return Path(path_str)


def setup_logging(config: Optional[LoggingConfig] = None) -> logging.Logger:
    """Set up logging system with dual-handler strategy.
    
    This function configures the root logger with two handlers:
    1. A rotating file handler that captures all DEBUG+ entries
    2. A stream handler that outputs INFO+ entries to console
    
    Both handlers use immediate flush for crash-safety.
    
    Args:
        config: Optional LoggingConfig instance. If not provided, configuration
                is read from environment variables.
    
    Returns:
        The configured root logger.
    """
    if config is None:
        config = LoggingConfig(
            log_file_path=_get_log_file_path_from_env(),
            log_level=_get_log_level_from_env(),
        )
    
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.log_level))
    
    logger.handlers.clear()
    
    log_file_path = config.log_file_path
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = FlushingRotatingFileHandler(
        filename=log_file_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(config.log_format))
    
    console_handler = FlushingStreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(config.log_format))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under 'benchmark_llm' namespace.
    
    This function creates or retrieves a child logger with the given name
    under the 'benchmark_llm' namespace. Child loggers inherit the
    configuration from the parent logger.
    
    Example:
        get_logger('core.execution_engine') returns a logger named
        'benchmark_llm.core.execution_engine'
    
    Args:
        name: The component name (e.g., 'core.execution_engine', 'api.client').
    
    Returns:
        A child logger under the 'benchmark_llm' namespace.
    """
    return logging.getLogger(f"benchmark_llm.{name}")


def get_structured_logger(name: str) -> logging.Logger:
    """Get a child logger under 'benchmark_llm' namespace for structured logging.
    
    This is an alias for get_logger() provided for backward compatibility
    and explicit structured logging use cases.
    
    Args:
        name: The component name (e.g., 'api', 'execution', 'startup').
    
    Returns:
        A child logger under the 'benchmark_llm' namespace.
    """
    return get_logger(name)
