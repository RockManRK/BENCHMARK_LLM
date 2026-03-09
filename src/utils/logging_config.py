"""Logging configuration module for benchmark_llm project.

This module provides comprehensive logging configuration with support for:
- Rotating file handlers for operational logs
- Structured log formatting
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Hierarchical logger structure for different components

## Logging Architecture

This module uses Python's standard logging hierarchy:

1. **Root Logger**: Configured by `setup_logging()` with file and console handlers
2. **Module Loggers**: Created with `logging.getLogger(__name__)` in each module
3. **Component Loggers**: Created with `get_structured_logger(component)` for helpers

All loggers inherit from the root logger, ensuring consistent output to both
file and console.

Example:
    >>> from src.utils.logging_config import LoggingConfig, setup_logging
    >>> from pathlib import Path
    >>>
    >>> config = LoggingConfig(log_file_path=Path("./logs/benchmark.log"))
    >>> setup_logging(config)
    >>> logger = logging.getLogger(__name__)
    >>> logger.info("Application started")
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Default configuration values
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5

# Structured log format
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class FlushingRotatingFileHandler(RotatingFileHandler):
    """A RotatingFileHandler that flushes after each write.

    This ensures log messages are written to disk immediately,
    preventing loss of logs in case of crashes or power failures.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record, then flush the stream.

        Args:
            record: The log record to emit.
        """
        super().emit(record)
        self.flush()


class FlushingStreamHandler(logging.StreamHandler):
    """A StreamHandler that flushes after each write.

    This ensures log messages are written immediately.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record, then flush the stream.

        Args:
            record: The log record to emit.
        """
        super().emit(record)
        self.flush()


class LoggingConfig:
    """Configuration class for logging setup.

    This class encapsulates all logging configuration parameters,
    providing sensible defaults and validation for log settings.

    Attributes:
        log_file_path: Path to the log file for operational logs.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        max_bytes: Maximum size in bytes before log rotation occurs.
        backup_count: Number of backup log files to keep.

    Example:
        >>> config = LoggingConfig(
        ...     log_file_path=Path("./logs/benchmark.log"),
        ...     log_level="DEBUG",
        ...     max_bytes=5 * 1024 * 1024,
        ...     backup_count=3
        ... )
        >>> print(config.log_level)
        DEBUG
    """

    def __init__(
        self,
        log_file_path: Path,
        log_level: str = DEFAULT_LOG_LEVEL,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
    ) -> None:
        """Initialize logging configuration.

        Args:
            log_file_path: Path to the log file for operational logs.
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                Defaults to INFO.
            max_bytes: Maximum size in bytes before log rotation occurs.
                Defaults to 10MB.
            backup_count: Number of backup log files to keep.
                Defaults to 5.

        Raises:
            ValueError: If log_level is invalid, max_bytes is not positive,
                or backup_count is negative.

        Example:
            >>> config = LoggingConfig(
            ...     log_file_path=Path("./logs/app.log"),
            ...     log_level="DEBUG"
            ... )
        """
        self.log_file_path = log_file_path
        self.log_level = self._validate_log_level(log_level)
        self.max_bytes = self._validate_max_bytes(max_bytes)
        self.backup_count = self._validate_backup_count(backup_count)

    def _validate_log_level(self, log_level: str) -> str:
        """Validate and normalize the log level.

        Args:
            log_level: The log level string to validate.

        Returns:
            The validated log level in uppercase.

        Raises:
            ValueError: If the log level is not valid.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        level_upper = log_level.upper()
        if level_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level: {log_level}. "
                f"Must be one of {valid_levels}"
            )
        return level_upper

    def _validate_max_bytes(self, max_bytes: int) -> int:
        """Validate the max_bytes parameter.

        Args:
            max_bytes: The maximum file size in bytes.

        Returns:
            The validated max_bytes value.

        Raises:
            ValueError: If max_bytes is not positive.
        """
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        return max_bytes

    def _validate_backup_count(self, backup_count: int) -> int:
        """Validate the backup_count parameter.

        Args:
            backup_count: The number of backup files to keep.

        Returns:
            The validated backup_count value.

        Raises:
            ValueError: If backup_count is negative.
        """
        if backup_count < 0:
            raise ValueError("backup_count must be non-negative")
        return backup_count

    def __repr__(self) -> str:
        """Return string representation of the configuration.

        Returns:
            String representation showing key configuration values.
        """
        return (
            f"LoggingConfig("
            f"log_file_path={self.log_file_path!r}, "
            f"log_level={self.log_level!r}, "
            f"max_bytes={self.max_bytes}, "
            f"backup_count={self.backup_count})"
        )


def setup_logging(config: LoggingConfig) -> None:
    """Set up logging configuration with rotating file handler.

    This function configures the root logger for the benchmark_llm application
    with a rotating file handler and structured formatting. It ensures that
    the log directory exists and creates the necessary handlers.

    All module loggers (created with logging.getLogger(__name__)) will
    automatically inherit this configuration through Python's logging hierarchy.

    Args:
        config: LoggingConfig instance containing logging configuration.

    Example:
        >>> config = LoggingConfig(log_file_path=Path("./logs/benchmark.log"))
        >>> setup_logging(config)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Logging initialized")
    """
    # Configure the ROOT logger to catch ALL loggers in the application
    # This ensures loggers like "src.main", "src.core.*", "benchmark_llm", etc.
    # all write to the same log file
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))

    # Clear any existing root handlers to avoid duplicates
    root_logger.handlers.clear()

    # Ensure log directory exists
    config.log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create rotating file handler with automatic flushing after each write
    # File handler: Logs EVERYTHING (DEBUG level)
    file_handler = FlushingRotatingFileHandler(
        config.log_file_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
        delay=False,  # Open file immediately
    )
    file_handler.setLevel(getattr(logging, config.log_level))

    # Create formatter with structured format
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(formatter)

    # Add handlers to ROOT logger only
    root_logger.addHandler(file_handler)

    # Also add console handler for visibility with automatic flushing
    # Console handler: Only shows IMPORTANT messages (INFO level minimum)
    # This prevents debug spam on the console while keeping file logs complete
    console_handler = FlushingStreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Only INFO and above on console
    console_handler.setFormatter(formatter)

    # Add console handler to ROOT logger
    root_logger.addHandler(console_handler)


def get_structured_logger(component: str) -> logging.Logger:
    """Get a structured logger for a specific component.

    Creates a child logger under the root logger namespace for
    a specific component (e.g., 'api', 'database', 'execution').
    This enables hierarchical logging and component-specific filtering.

    All component loggers inherit the handlers and configuration
    from the root logger set up by setup_logging().

    Args:
        component: Name of the component (e.g., 'api', 'db', 'execution').

    Returns:
        A child logger instance for the specified component.

    Example:
        >>> setup_logging(LoggingConfig(log_file_path=Path("./logs/benchmark.log")))
        >>> api_logger = get_structured_logger('api')
        >>> api_logger.info('API request received')
        # Output includes: benchmark_llm.api - INFO - API request received
    """
    root_logger = logging.getLogger()
    return root_logger.getChild(component)


def log_initialization_summary(
    logger: logging.Logger,
    execution_mode: str,
    experiment_name: Optional[str],
    persist_data: bool,
    config_frozen: bool,
    config_hash: Optional[str],
    seed: Optional[int],
    models: list[str],
    questions: list[str],
    system_prompt: Optional[str] = None,
) -> None:
    """Log a clear, unambiguous initialization summary.

    This function creates a standardized log header that eliminates
    any ambiguity about the execution context. When looking at this
    log months later, you should know exactly:
    - What mode was used
    - Whether data was saved
    - If configuration was frozen
    - Which experiment (if any)
    - What effective seed was used

    Args:
        logger: Logger instance to use.
        execution_mode: Execution mode (test, dev, experiment).
        experiment_name: Name of the experiment (or None).
        persist_data: Whether data will be persisted.
        config_frozen: Whether configuration is frozen.
        config_hash: Configuration hash (for experiment mode).
        seed: Random seed used.
        models: List of models being benchmarked.
        questions: List of questions being executed.
        system_prompt: System prompt used (for experiment mode).

    Example:
        >>> from src.utils.logging_config import get_structured_logger
        >>> logger = get_structured_logger('startup')
        >>> log_initialization_summary(
        ...     logger,
        ...     execution_mode="experiment",
        ...     experiment_name="gpt4_vs_claude3",
        ...     persist_data=True,
        ...     config_frozen=True,
        ...     config_hash="8f3a9c2e",
        ...     seed=42,
        ...     models=["openai/gpt-4", "anthropic/claude-3"],
        ...     questions=["Q001", "Q002", "Q003"]
        ... )
    """
    logger.info("=" * 60)
    logger.info("Benchmark LLM - Initialization")
    logger.info("=" * 60)
    logger.info(f"Execution mode      : {execution_mode.upper()} MODE")
    logger.info(f"Experiment          : {experiment_name or 'None'}")
    
    # Show explicit persistence details
    if execution_mode.lower() == "test":
        logger.info("Persist data        : YES (SQLite in-memory)")
        logger.info("Disk persistence    : NO (data lost after execution)")
    else:
        logger.info(f"Persist data        : {'YES' if persist_data else 'NO'}")
    
    if config_frozen:
        logger.info(f"Configuration       : FROZEN (config_hash={config_hash})")
        if system_prompt:
            logger.info(f"System prompt       : {system_prompt}")
    else:
        logger.info("Configuration       : MUTABLE (CLI/.env)")
    
    logger.info(f"Seed                : {seed if seed is not None else 'None'}")
    logger.info(f"Models              : {', '.join(models)}")
    
    # Format question range for readability
    if len(questions) <= 5:
        questions_str = ', '.join(questions)
    else:
        questions_str = f"{questions[0]}-{questions[-1]} ({len(questions)} questions)"
    logger.info(f"Questions           : {questions_str}")
    logger.info("=" * 60)


def flush_all_handlers(logger: logging.Logger) -> None:
    """Force flush all handlers attached to a logger.

    This ensures that log messages are written to disk immediately,
    which is critical for debugging and monitoring long-running processes.

    Args:
        logger: Logger instance to flush.

    Example:
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Important message")
        >>> flush_all_handlers(logger)  # Ensure message is written
    """
    for handler in logger.handlers:
        if hasattr(handler, 'flush') and callable(handler.flush):
            handler.flush()
        elif hasattr(handler, 'stream') and hasattr(handler.stream, 'flush'):
            handler.stream.flush()
