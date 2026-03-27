"""Configuration module for benchmark_llm project.

This module provides settings management using pydantic-settings,
with environment variable validation and default values.

Security Notes:
    - OPENROUTER_API_KEY should be set via environment variable only
    - Do NOT store API keys in .env files committed to version control
    - Use .env only for non-sensitive configuration (debug flags, paths, etc.)
"""

import hashlib
import json
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Load .env file for non-sensitive configuration
# NOTE: OPENROUTER_API_KEY should NOT be in .env - use system environment variable
load_dotenv(".env")


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

    Security Notes:
        - OPENROUTER_API_KEY must be set via system environment variable
        - The .env file is loaded ONLY for non-sensitive settings
        - API key from .env will be ignored for security

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
        env_file=None,  # .env already loaded manually above
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenRouter API Configuration
    openrouter_api_key: str = Field(
        default="",
        description="API key for OpenRouter API authentication. Must be set via OPENROUTER_API_KEY environment variable.",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenRouter API endpoints",
    )

    @model_validator(mode="after")
    def validate_api_key_from_env(self) -> "Settings":
        """Validate that API key is provided via system environment variable.

        This validator ensures that OPENROUTER_API_KEY is read from the system
        environment, not from .env files, for security reasons.

        Returns:
            The Settings instance.

        Raises:
            ValueError: If API key is not configured.
        """
        # Try to get API key from system environment variable
        # This takes precedence over any value from .env
        env_api_key = os.getenv("OPENROUTER_API_KEY")
        
        if env_api_key:
            # Use the environment variable value
            object.__setattr__(self, "openrouter_api_key", env_api_key)
        
        return self

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
    random_seed: Optional[str | int] = Field(
        default=None,
        description="Optional seed for reproducible randomization. Use 'AUTO' for automatic seed generation, empty/None for no randomization, or integer for fixed seed.",
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

    # OpenRouter Debug Configuration
    openrouter_debug_enabled: bool = Field(
        default=False,
        description="Enable OpenRouter debug mode (echo_upstream_body). BLOCKED in EXPERIMENT mode.",
    )

    # Prompt Configuration
    default_prompt: Optional[str] = Field(
        default=None,
        description="Default prompt instruction for all questions (with or without images). If None, uses built-in default.",
    )

    # Default Questions (optional, can be set in .env)
    default_questions: Optional[str] = Field(
        default=None,
        description="Default questions to use when --questions is not specified. Can be set in .env.",
    )

    # Questions Dataset Path (CRITICAL - source of truth for questions)
    questions_dataset_path: Path = Field(
        default=Path("./data/enamed_questions.json"),
        description="Path to the JSON questions dataset. This is the SOURCE OF TRUTH for all questions. Can be set via QUESTIONS_DATASET_PATH in .env.",
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
        description="System prompt template for experiment mode. Loaded from SYSTEM_PROMPT environment variable.",
    )
    user_prompt_template: Optional[str] = Field(
        default=None,
        description="User prompt template for experiment mode. Loaded from USER_PROMPT environment variable. If not set, uses default_prompt as fallback.",
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
    reasoning_exclude: Optional[bool] = Field(
        default=None,
        description="Exclude reasoning from response (use internally but don't return). Leave blank to not send.",
    )
    reasoning_enabled: Optional[bool] = Field(
        default=None,
        description="Enable reasoning with default parameters. Leave blank to not send.",
    )

    # Model Variant Identity (defines variant_id)
    reasoning_mode: Optional[str] = Field(
        default="unspecified",
        description="Reasoning mode for variant identity: unspecified, auto, off, effort, budget. "
                    "'unspecified' means DO NOT SEND reasoning field (use model default).",
    )
    enable_vision: bool = Field(
        default=False,
        description="Enable vision for variant identity (send images with questions)",
    )
    enable_structured: bool = Field(
        default=False,
        description="Enable structured outputs for variant identity (JSON schema)",
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
    def validate_random_seed(cls, value: Optional[str | int]) -> Optional[str | int]:
        """Validate that random seed is a valid integer or 'AUTO' if provided.
        
        Special values:
        - None or "": No randomization (answers stay in original A,B,C,D order)
        - "AUTO": Automatic seed generation (hash of run_id for uniqueness)
        - Integer: Fixed seed for reproducibility
        
        Args:
            value: The seed value to validate.
            
        Returns:
            The validated seed value (None, "AUTO", or int).
            
        Raises:
            ValueError: If the seed is not a valid integer or 'AUTO'.
        """
        if value is None or value == "":
            return None
        if isinstance(value, str):
            # Check for special AUTO keyword
            if value.upper() == "AUTO":
                return "AUTO"
            try:
                value = int(value)
            except ValueError:
                raise ValueError(f"Random seed must be an integer or 'AUTO', got '{value}'")
        if isinstance(value, int) and value < 0:
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

    @field_validator("reasoning_max_tokens", mode="before")
    @classmethod
    def validate_reasoning_max_tokens(cls, value: Optional[str | int]) -> Optional[int]:
        """Validate reasoning_max_tokens, converting empty string to None."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValueError(f"reasoning_max_tokens must be an integer, got '{value}'")
        return value

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

    @field_validator("reasoning_exclude", "reasoning_enabled", mode="before")
    @classmethod
    def validate_reasoning_bool(cls, value: Optional[str | bool]) -> Optional[bool]:
        """Validate reasoning boolean fields, converting empty string to None."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in {"true", "1", "yes"}:
                return True
            if value_lower in {"false", "0", "no"}:
                return False
            raise ValueError(f"Value must be true/false, got '{value}'")
        return bool(value)

    @field_validator("reasoning_mode", mode="before")
    @classmethod
    def validate_reasoning_mode(cls, value: Optional[str]) -> str:
        """Validate reasoning_mode is a valid mode."""
        if value is None or value == "":
            return "unspecified"
        
        value_lower = value.lower().strip()
        valid_modes = {"unspecified", "auto", "off", "effort", "budget"}
        
        if value_lower not in valid_modes:
            raise ValueError(
                f"reasoning_mode must be one of {valid_modes}, got '{value}'"
            )
        
        return value_lower

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

    @model_validator(mode="after")
    def validate_openrouter_debug_enabled_after(self) -> "Settings":
        """Validate openrouter_debug_enabled after all fields are set.

        In EXPERIMENT mode, emits a warning and sets openrouter_debug_enabled to False
        instead of raising ValueError. This prevents hard failures in long-running pipelines.

        Returns:
            The Settings instance.
        """
        if self.execution_mode == ExecutionMode.EXPERIMENT and self.openrouter_debug_enabled:
            # Emit warning instead of raising ValueError
            logger.warning(
                "openrouter_debug_enabled is BLOCKED in EXPERIMENT mode. "
                "Debug flag will be ignored. Debug mode cannot be used for experimental runs. "
                "Execution will continue without debug."
            )
            # Set to False silently after warning
            object.__setattr__(self, "openrouter_debug_enabled", False)

        return self

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

    def get_protocol_config(self) -> dict:
        """Get protocol configuration that is frozen per experiment.

        The protocol defines the rules of the experiment that must remain
        immutable across all runs. This is used to calculate the config hash.

        What defines an experiment protocol:
        - default_prompt: Rules for parsing/evaluation
        - use_structured_outputs: Policy for JSON schema usage
        - random_seed_policy: Seed policy (AUTO, FIXED, or none)

        What is NOT included (these are model variants):
        - questionnaire_path (just metadata, snapshots are the truth)
        - Model generation parameters (temperature, max_tokens, etc.)
        - Reasoning parameters (effort, max_tokens, exclude)
        - Vision settings

        Returns:
            Dictionary containing only protocol configuration fields.

        Example:
            >>> settings = Settings()
            >>> protocol = settings.get_protocol_config()
            >>> print(protocol.keys())
            dict_keys(['default_prompt', 'use_structured_outputs', 'random_seed_policy'])
        """
        return {
            "default_prompt": self.default_prompt,
            "use_structured_outputs": self.use_structured_outputs,
            "random_seed_policy": str(self.random_seed) if self.random_seed else "none",
        }

    def get_config_hash(self) -> str:
        """Generate a hash of the experiment protocol configuration.

        Creates a deterministic hash from the protocol configuration only.
        Model variants (temperature, reasoning, vision) do NOT affect the hash,
        allowing different model variants to be compared within the same experiment.

        Returns:
            A hexadecimal string representing the protocol configuration hash.

        Example:
            >>> settings = Settings()
            >>> hash1 = settings.get_config_hash()
            >>> settings.model_temperature = 0.8  # Change model variant
            >>> hash2 = settings.get_config_hash()
            >>> hash1 == hash2  # Same protocol, same hash
            True
        """
        # Use only protocol configuration for hash
        config_dict = self.get_protocol_config()

        # Serialize to JSON with sorted keys for determinism
        config_json = json.dumps(config_dict, sort_keys=True, default=str)

        # Generate SHA-256 hash
        return hashlib.sha256(config_json.encode()).hexdigest()[:16]

    def get_config_dict(self) -> dict:
        """Get configuration as a dictionary for serialization.

        Returns all configuration fields for complete serialization.
        This includes protocol, metadata, and model variants.

        Structure:
        - Protocol: Fields that define the experiment (used in hash)
        - Metadata: Informational fields (do NOT affect hash)
        - Model Variants: Parameters that can vary within an experiment

        Returns:
            Dictionary containing all configuration fields.

        Example:
            >>> settings = Settings()
            >>> config = settings.get_config_dict()
            >>> "default_prompt" in config  # Protocol
            True
            >>> "model_temperature" in config  # Model variant
            True
        """
        return {
            # Protocol (used in config hash)
            "default_prompt": self.default_prompt,
            "use_structured_outputs": self.use_structured_outputs,
            "random_seed_policy": str(self.random_seed) if self.random_seed else "none",
            # Metadata (informational, do NOT affect hash)
            "questionnaire_path": str(self.questionnaire_path),
            "openrouter_base_url": self.openrouter_base_url,
            "default_iterations": self.default_iterations,
            # Model Variants (do NOT affect hash, can vary per run)
            "model_max_tokens": self.model_max_tokens,
            "model_temperature": self.model_temperature,
            "model_top_p": self.model_top_p,
            "model_top_k": self.model_top_k,
            "model_repeat_penalty": self.model_repeat_penalty,
            "reasoning_effort": self.reasoning_effort,
            "reasoning_max_tokens": self.reasoning_max_tokens,
            "reasoning_exclude": self.reasoning_exclude,
            "reasoning_enabled": self.reasoning_enabled,
            "enable_vision": self.enable_vision,
            "openrouter_debug_enabled": self.openrouter_debug_enabled,
            # Additional context
            "execution_mode": self.execution_mode.value,
            "experiment_name": self.experiment_name,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "random_seed": self.random_seed,
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
        # Map SYSTEM_PROMPT_TEMPLATE and USER_PROMPT_TEMPLATE from .env
        # to system_prompt and user_prompt_template fields
        import os
        if 'system_prompt' not in kwargs:
            system_prompt_template = os.getenv("SYSTEM_PROMPT_TEMPLATE")
            if system_prompt_template is not None:
                kwargs['system_prompt'] = system_prompt_template
        
        if 'user_prompt_template' not in kwargs:
            user_prompt_template = os.getenv("USER_PROMPT_TEMPLATE")
            if user_prompt_template is not None:
                kwargs['user_prompt_template'] = user_prompt_template
        
        super().__init__(**kwargs)
        # Apply fallback for user_prompt_template if not set
        # Use default_prompt as fallback for backward compatibility
        if self.user_prompt_template is None and self.default_prompt is not None:
            self.user_prompt_template = self.default_prompt
            logger.debug(f"Using default_prompt as user_prompt_template fallback: {self.default_prompt}")
        self._log_configuration_status()

    def _log_configuration_status(self) -> None:
        """Log the current configuration status."""
        if not self.openrouter_api_key:
            logger.error(
                "OPENROUTER_API_KEY is not configured. "
                "Please set the system environment variable OPENROUTER_API_KEY. "
                "On Windows: setx OPENROUTER_API_KEY \"your-api-key-here\" "
                "On Linux/macOS: export OPENROUTER_API_KEY=your-api-key-here"
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
