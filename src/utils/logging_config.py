"""Logging configuration module for benchmark_llm project.

This module provides comprehensive logging configuration with support for:
- Rotating file handlers for operational logs
- Structured log formatting
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Hierarchical logger structure for different components

Example:
    >>> from src.utils.logging_config import LoggingConfig, setup_logging
    >>> from pathlib import Path
    >>>
    >>> config = LoggingConfig(log_file_path=Path("./logs/benchmark.log"))
    >>> logger = setup_logging(config)
    >>> logger.info("Application started")
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Module-level logger instance
_logger: Optional[logging.Logger] = None

# Default configuration values
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_LOGGER_NAME = "benchmark_llm"

# Structured log format
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """Set up logging configuration with rotating file handler.

    This function configures the root logger for the benchmark_llm application
    with a rotating file handler and structured formatting. It ensures that
    the log directory exists and creates the necessary handlers.

    Args:
        config: LoggingConfig instance containing logging configuration.

    Returns:
        Configured logger instance for the benchmark_llm application.

    Example:
        >>> config = LoggingConfig(log_file_path=Path("./logs/benchmark.log"))
        >>> logger = setup_logging(config)
        >>> logger.info("Logging initialized")
    """
    global _logger

    # Create logger
    logger = logging.getLogger(DEFAULT_LOGGER_NAME)
    logger.setLevel(getattr(logging, config.log_level))

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Ensure log directory exists
    config.log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create rotating file handler
    file_handler = RotatingFileHandler(
        config.log_file_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, config.log_level))

    # Create formatter with structured format
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    # Also add console handler for visibility
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.log_level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Store global reference
    _logger = logger

    return logger


def get_logger() -> logging.Logger:
    """Get the configured logger instance.

    Returns the global logger instance created by setup_logging.
    If logging hasn't been set up yet, returns a logger with default
    configuration.

    Returns:
        The configured logger instance.

    Example:
        >>> logger = get_logger()
        >>> logger.info("Application event")
    """
    global _logger
    if _logger is None:
        # Return a default logger if setup hasn't been called
        _logger = logging.getLogger(DEFAULT_LOGGER_NAME)
    return _logger


def get_structured_logger(component: str) -> logging.Logger:
    """Get a structured logger for a specific component.

    Creates a child logger under the benchmark_llm namespace for
    a specific component (e.g., 'api', 'database', 'execution').
    This enables hierarchical logging and component-specific filtering.

    Args:
        component: Name of the component (e.g., 'api', 'db', 'execution').

    Returns:
        A child logger instance for the specified component.

    Example:
        >>> api_logger = get_structured_logger('api')
        >>> api_logger.info('API request received')
        # Output: benchmark_llm.api - INFO - API request received
    """
    parent_logger = get_logger()
    return parent_logger.getChild(component)


def log_api_request(
    logger: logging.Logger,
    endpoint: str,
    model: str,
    timestamp: Optional[str] = None,
) -> None:
    """Log an API request with structured format.

    Args:
        logger: Logger instance to use.
        endpoint: API endpoint being called.
        model: Model being used for the request.
        timestamp: Optional timestamp string. If None, uses current time.

    Example:
        >>> logger = get_structured_logger('api')
        >>> log_api_request(logger, '/v1/chat/completions', 'gpt-4')
    """
    from datetime import datetime

    if timestamp is None:
        timestamp = datetime.now().isoformat()

    logger.info(
        f"API_REQUEST | endpoint={endpoint} | model={model} | timestamp={timestamp}"
    )


def log_api_response(
    logger: logging.Logger,
    status: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
) -> None:
    """Log an API response with structured format.

    Args:
        logger: Logger instance to use.
        status: Response status (success, error, etc.).
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens generated.
        latency_ms: Response latency in milliseconds.

    Example:
        >>> logger = get_structured_logger('api')
        >>> log_api_response(logger, 'success', 50, 20, 1200)
    """
    logger.info(
        f"API_RESPONSE | status={status} | "
        f"input_tokens={input_tokens} | output_tokens={output_tokens} | "
        f"latency_ms={latency_ms}"
    )


def log_execution_progress(
    logger: logging.Logger,
    run_id: str,
    model: str,
    iteration: int,
    question: str,
    total: int,
    current: int,
) -> None:
    """Log execution progress with structured format.

    Args:
        logger: Logger instance to use.
        run_id: Unique identifier for the run.
        model: Model being tested.
        iteration: Current iteration number.
        question: Current question ID.
        total: Total number of questions.
        current: Current question number.

    Example:
        >>> logger = get_structured_logger('execution')
        >>> log_execution_progress(logger, 'run-001', 'gpt-4', 1, 'Q001', 100, 1)
    """
    logger.info(
        f"PROGRESS | run_id={run_id} | model={model} | "
        f"iteration={iteration} | question={question} | "
        f"current={current}/{total}"
    )


def log_configuration_startup(
    logger: logging.Logger,
    database_path: str,
    log_level: str,
    default_iterations: int,
    **kwargs,
) -> None:
    """Log configuration at startup with structured format.

    Args:
        logger: Logger instance to use.
        database_path: Path to the database file.
        log_level: Configured log level.
        default_iterations: Default number of iterations.
        **kwargs: Additional configuration key-value pairs to log.

    Example:
        >>> logger = get_structured_logger('startup')
        >>> log_configuration_startup(
        ...     logger,
        ...     database_path='./data/benchmark.db',
        ...     log_level='INFO',
        ...     default_iterations=1
        ... )
    """
    config_parts = [
        f"CONFIG | database_path={database_path}",
        f"log_level={log_level}",
        f"default_iterations={default_iterations}",
    ]

    for key, value in kwargs.items():
        config_parts.append(f"{key}={value}")

    logger.info(" | ".join(config_parts))
