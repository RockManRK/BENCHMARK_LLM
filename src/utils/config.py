"""Configuration module for benchmark_llm project.

This module provides settings management using pydantic-settings,
with environment variable validation and default values.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    This class defines all configuration options for the benchmark_llm project,
    with sensible defaults and environment variable validation.

    Attributes:
        openrouter_api_key: API key for OpenRouter API authentication.
        openrouter_base_url: Base URL for OpenRouter API endpoints.
        database_path: Path to SQLite database file.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file_path: Path to operational log file.
        default_iterations: Default number of test iterations per model.
        random_seed: Optional seed for reproducible randomization.

    Example:
        >>> settings = Settings()
        >>> print(settings.openrouter_base_url)
        'https://openrouter.ai/api/v1'
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenRouter API Configuration
    openrouter_api_key: str = Field(
        default="",
        description="API key for OpenRouter API authentication",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenRouter API endpoints",
    )

    # Database Configuration
    database_path: Path = Field(
        default=Path("./data/benchmark.db"),
        description="Path to SQLite database file",
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_file_path: Path = Field(
        default=Path("./logs/benchmark.log"),
        description="Path to operational log file",
    )

    # Test Configuration
    default_iterations: int = Field(
        default=1,
        ge=1,
        description="Default number of test iterations per model",
    )

    # Randomization
    random_seed: Optional[int] = Field(
        default=None,
        description="Optional seed for reproducible randomization",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate that log level is a valid logging level.

        Args:
            value: The log level string to validate.

        Returns:
            The validated log level in uppercase.

        Raises:
            ValueError: If the log level is not valid.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value_upper = value.upper()
        if value_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level: {value}. Must be one of {valid_levels}"
            )
        return value_upper

    @field_validator("random_seed")
    @classmethod
    def validate_random_seed(cls, value: Optional[int]) -> Optional[int]:
        """Validate that random seed is a valid integer if provided.

        Args:
            value: The random seed value to validate.

        Returns:
            The validated random seed or None.
        """
        if value is not None and value < 0:
            raise ValueError("Random seed must be a non-negative integer")
        return value

    @property
    def is_api_configured(self) -> bool:
        """Check if the OpenRouter API is properly configured.

        Returns:
            True if API key is set, False otherwise.
        """
        return bool(self.openrouter_api_key)

    def __init__(self) -> None:
        """Initialize settings and log configuration status."""
        super().__init__()
        self._log_configuration_status()

    def _log_configuration_status(self) -> None:
        """Log the current configuration status."""
        if not self.openrouter_api_key:
            logger.warning(
                "OpenRouter API key is not configured. "
                "Set OPENROUTER_API_KEY environment variable."
            )
        else:
            logger.info("OpenRouter API key is configured.")

        logger.info(f"Database path: {self.database_path}")
        logger.info(f"Log level: {self.log_level}")
        logger.info(f"Log file path: {self.log_file_path}")


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance.

    Creates a new Settings instance if one doesn't exist,
    otherwise returns the cached instance.

    Returns:
        The global Settings instance.

    Example:
        >>> settings = get_settings()
        >>> print(settings.openrouter_base_url)
        'https://openrouter.ai/api/v1'
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance.

    This is useful for testing purposes when you need to
    reload settings with different environment variables.
    """
    global _settings
    _settings = None
