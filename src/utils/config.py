"""Configuration module for benchmark_llm project.

This module provides settings management using pydantic-settings,
with environment variable validation and default values.
"""

import hashlib
import json
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Execution mode for benchmark runs.

    Attributes:
        TEST: Test mode - no data persistence, in-memory DB.
        DEV: Development mode - data persistence, no experiment tracking.
        EXPERIMENT: Experiment mode - data persistence with frozen configuration.
    """

    TEST = "test"
    DEV = "dev"
    EXPERIMENT = "experiment"


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

    # Test mode configuration
    use_memory_db: bool = Field(
        default=False,
        description="Use in-memory database for testing (not persistent)",
    )

    # Randomization
    random_seed: Optional[int] = Field(
        default=None,
        description="Optional seed for reproducible randomization",
    )

    # Structured Outputs Configuration
    use_structured_outputs: bool = Field(
        default=False,
        description="Use structured outputs (JSON schema) if model supports it",
    )

    # Vision Support Configuration
    enable_vision: bool = Field(
        default=False,
        description="Enable vision support (send images with questions)",
    )

    # Prompt Configuration
    prompt_with_image: Optional[str] = Field(
        default=None,
        description="Custom prompt for questions with images (leave None for default)",
    )

    # Questionnaire Configuration
    questionnaire_path: Path = Field(
        default=Path("./data/enamed_questions.json"),
        description="Path to the JSON questionnaire file",
    )

    # Execution Mode Configuration
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.DEV,
        description="Execution mode: test, dev, or experiment",
    )
    experiment_name: Optional[str] = Field(
        default=None,
        description="Name of the experiment (required for experiment mode)",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="System prompt for experiment mode",
    )
    user_prompt_template: Optional[str] = Field(
        default=None,
        description="User prompt template for experiment mode",
    )

    # Model Generation Parameters (optional, None = use model defaults)
    model_max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens for model generation (leave None for model default)",
    )
    model_temperature: Optional[float] = Field(
        default=None,
        description="Temperature for model generation (leave None for model default)",
    )
    model_top_p: Optional[float] = Field(
        default=None,
        description="Top-p sampling parameter (leave None for model default)",
    )
    model_top_k: Optional[int] = Field(
        default=None,
        description="Top-k sampling parameter (leave None for model default)",
    )
    model_repeat_penalty: Optional[float] = Field(
        default=None,
        description="Repeat penalty parameter (leave None for model default)",
    )

    # Reasoning Configuration (OpenRouter standard)
    reasoning_effort: Optional[str] = Field(
        default=None,
        description="Reasoning effort level: xhigh, high, medium, low, minimal, none",
    )
    reasoning_max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens for reasoning",
    )
    reasoning_exclude: bool = Field(
        default=False,
        description="Exclude reasoning from response (use internally but don't return)",
    )
    reasoning_enabled: bool = Field(
        default=False,
        description="Enable reasoning with default parameters",
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

    @field_validator("random_seed", mode="before")
    @classmethod
    def validate_random_seed(cls, value: Optional[str | int]) -> Optional[int]:
        """Validate that random seed is a valid integer if provided."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValueError(f"Random seed must be an integer, got '{value}'")
        if value < 0:
            raise ValueError("Random seed must be a non-negative integer")
        return value

    @field_validator("model_max_tokens", mode="before")
    @classmethod
    def validate_model_max_tokens(cls, value: Optional[str | int]) -> Optional[int]:
        """Validate model_max_tokens, converting empty string to None."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValueError(f"model_max_tokens must be an integer, got '{value}'")
        return value

    @field_validator("model_temperature", "model_top_p", "model_top_k", "model_repeat_penalty", mode="before")
    @classmethod
    def validate_model_params(cls, value: Optional[str | int | float]) -> Optional[float | int]:
        """Validate model parameters, converting empty string to None."""
        if value is None or value == "":
            return None
        return value

    @field_validator("reasoning_effort", mode="before")
    @classmethod
    def validate_reasoning_effort(cls, value: Optional[str]) -> Optional[str]:
        """Validate reasoning_effort is a valid level."""
        if value is None or value == "":
            return None

        # Strip whitespace
        value = value.strip()

        valid_efforts = {"xhigh", "high", "medium", "low", "minimal", "none"}
        value_lower = value.lower()

        if value_lower not in valid_efforts:
            raise ValueError(
                f"reasoning_effort must be one of: {', '.join(sorted(valid_efforts))}, got '{value}'"
            )

        return value_lower

    @field_validator("execution_mode", mode="before")
    @classmethod
    def validate_execution_mode(cls, value: Optional[str | ExecutionMode]) -> ExecutionMode:
        """Validate execution_mode is a valid mode."""
        if value is None or value == "":
            return ExecutionMode.DEV
        
        if isinstance(value, ExecutionMode):
            return value
        
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in {"test", "dev", "experiment"}:
                return ExecutionMode(value_lower)
            raise ValueError(
                f"execution_mode must be one of: test, dev, experiment, got '{value}'"
            )
        
        return ExecutionMode.DEV

    @field_validator("experiment_name", mode="before")
    @classmethod
    def validate_experiment_name(cls, value: Optional[str], info) -> Optional[str]:
        """Validate experiment_name is provided when in experiment mode."""
        # Get the execution mode from values already processed
        if hasattr(info, 'data') and 'execution_mode' in info.data:
            mode = info.data['execution_mode']
        else:
            # Default to DEV if mode not yet determined
            mode = ExecutionMode.DEV
        
        if mode == ExecutionMode.EXPERIMENT and (value is None or value == ""):
            raise ValueError("experiment_name is required when execution_mode is 'experiment'")
        
        if value is None or value == "":
            return None
        
        return value.strip()

    @property
    def is_api_configured(self) -> bool:
        """Check if the OpenRouter API is properly configured.

        Returns:
            True if API key is set, False otherwise.
        """
        return bool(self.openrouter_api_key)

    @property
    def should_persist_data(self) -> bool:
        """Check if data should be persisted to database.

        Returns:
            False for TEST mode, True for DEV and EXPERIMENT modes.
        """
        return self.execution_mode != ExecutionMode.TEST

    @property
    def is_dev_mode(self) -> bool:
        """Check if running in development mode.

        Returns:
            True if execution_mode is DEV.
        """
        return self.execution_mode == ExecutionMode.DEV

    @property
    def is_experiment_mode(self) -> bool:
        """Check if running in experiment mode.

        Returns:
            True if execution_mode is EXPERIMENT.
        """
        return self.execution_mode == ExecutionMode.EXPERIMENT

    @property
    def is_test_mode(self) -> bool:
        """Check if running in test mode.

        Returns:
            True if execution_mode is TEST.
        """
        return self.execution_mode == ExecutionMode.TEST

    @property
    def is_config_frozen(self) -> bool:
        """Check if configuration is frozen (immutable).

        Returns:
            True for EXPERIMENT mode, False otherwise.
        """
        return self.execution_mode == ExecutionMode.EXPERIMENT

    def get_config_hash(self) -> str:
        """Generate a hash of the current configuration.

        Creates a deterministic hash from all relevant configuration
        parameters for experiment tracking and reproducibility.

        Returns:
            A hexadecimal string representing the configuration hash.
        """
        # Create a dict with all config fields that affect the experiment
        config_dict = {
            "execution_mode": self.execution_mode.value,
            "experiment_name": self.experiment_name,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "model_max_tokens": self.model_max_tokens,
            "model_temperature": self.model_temperature,
            "model_top_p": self.model_top_p,
            "model_top_k": self.model_top_k,
            "model_repeat_penalty": self.model_repeat_penalty,
            "reasoning_effort": self.reasoning_effort,
            "reasoning_max_tokens": self.reasoning_max_tokens,
            "reasoning_exclude": self.reasoning_exclude,
            "reasoning_enabled": self.reasoning_enabled,
            "use_structured_outputs": self.use_structured_outputs,
            "enable_vision": self.enable_vision,
            "prompt_with_image": self.prompt_with_image,
        }
        
        # Serialize to JSON with sorted keys for determinism
        config_json = json.dumps(config_dict, sort_keys=True, default=str)
        
        # Generate SHA-256 hash
        return hashlib.sha256(config_json.encode()).hexdigest()[:16]

    def get_config_dict(self) -> dict:
        """Get configuration as a dictionary for serialization.

        Returns:
            Dictionary containing all relevant configuration fields.
        """
        return {
            "execution_mode": self.execution_mode.value,
            "experiment_name": self.experiment_name,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "model_max_tokens": self.model_max_tokens,
            "model_temperature": self.model_temperature,
            "model_top_p": self.model_top_p,
            "model_top_k": self.model_top_k,
            "model_repeat_penalty": self.model_repeat_penalty,
            "reasoning_effort": self.reasoning_effort,
            "reasoning_max_tokens": self.reasoning_max_tokens,
            "reasoning_exclude": self.reasoning_exclude,
            "reasoning_enabled": self.reasoning_enabled,
            "use_structured_outputs": self.use_structured_outputs,
            "enable_vision": self.enable_vision,
            "prompt_with_image": self.prompt_with_image,
            "openrouter_base_url": self.openrouter_base_url,
            "default_iterations": self.default_iterations,
            "random_seed": self.random_seed,
            "questionnaire_path": str(self.questionnaire_path),
        }

    def get_generation_params(self) -> dict[str, tuple[str, any]]:
        """Get current generation parameter values with their source names.

        Returns:
            Dictionary mapping CLI parameter names to (setting_name, current_value) tuples.

        Example:
            >>> settings = Settings()
            >>> params = settings.get_generation_params()
            >>> print(params)
            {'temperature': ('model_temperature', 0.7), 'max_tokens': ('model_max_tokens', 2048)}
        """
        return {
            "temperature": ("model_temperature", self.model_temperature),
            "max_tokens": ("model_max_tokens", self.model_max_tokens),
            "top_p": ("model_top_p", self.model_top_p),
            "top_k": ("model_top_k", self.model_top_k),
            "repeat_penalty": ("model_repeat_penalty", self.model_repeat_penalty),
        }

    def __init__(self, **kwargs) -> None:
        """Initialize settings and log configuration status.

        Args:
            **kwargs: Optional keyword arguments to override settings.
        """
        super().__init__(**kwargs)
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
        logger.info(f"Execution mode: {self.execution_mode.value}")
        
        if self.is_experiment_mode:
            logger.info(f"Experiment name: {self.experiment_name}")
            logger.info(f"Configuration frozen: YES (hash={self.get_config_hash()})")
        else:
            logger.info("Configuration frozen: NO (mutable)")


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
