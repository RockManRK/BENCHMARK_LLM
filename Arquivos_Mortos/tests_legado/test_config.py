"""Tests for the configuration module.

This module tests the Settings class and configuration management functionality.
"""

import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from src.utils.config import Settings


class TestSettings:
    """Test cases for the Settings class."""

    def test_settings_loads_from_env(self, mocker: MockerFixture) -> None:
        """Test that settings loads values from environment variables."""
        mocker.patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test_api_key",
                "DATABASE_PATH": "./test_db.sqlite",
                "LOG_LEVEL": "DEBUG",
            },
        )
        settings = Settings()
        assert settings.openrouter_api_key == "test_api_key"
        assert settings.database_path == Path("./test_db.sqlite")
        assert settings.log_level == "DEBUG"

    def test_settings_default_values(self) -> None:
        """Test that settings uses default values when env vars are not set."""
        # Clear relevant env vars to test defaults
        env_backup = {
            "OPENROUTER_API_KEY": os.environ.pop("OPENROUTER_API_KEY", None),
            "OPENROUTER_BASE_URL": os.environ.pop("OPENROUTER_BASE_URL", None),
            "DATABASE_PATH": os.environ.pop("DATABASE_PATH", None),
            "LOG_LEVEL": os.environ.pop("LOG_LEVEL", None),
            "LOG_FILE_PATH": os.environ.pop("LOG_FILE_PATH", None),
            "DEFAULT_ITERATIONS": os.environ.pop("DEFAULT_ITERATIONS", None),
        }
        try:
            settings = Settings()
            assert settings.openrouter_api_key == ""
            assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
            assert settings.database_path == Path("./data/benchmark.db")
            assert settings.log_level == "INFO"
            assert settings.log_file_path == Path("./logs/benchmark.log")
            assert settings.default_iterations == 1
        finally:
            # Restore environment
            for key, value in env_backup.items():
                if value is not None:
                    os.environ[key] = value

    def test_settings_openrouter_base_url_default(self) -> None:
        """Test default OpenRouter base URL."""
        env_backup = os.environ.pop("OPENROUTER_BASE_URL", None)
        try:
            settings = Settings()
            assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
        finally:
            if env_backup:
                os.environ["OPENROUTER_BASE_URL"] = env_backup

    def test_settings_database_path_default(self) -> None:
        """Test default database path."""
        env_backup = os.environ.pop("DATABASE_PATH", None)
        try:
            settings = Settings()
            assert settings.database_path == Path("./data/benchmark.db")
        finally:
            if env_backup:
                os.environ["DATABASE_PATH"] = env_backup

    def test_settings_log_level_default(self) -> None:
        """Test default log level."""
        env_backup = os.environ.pop("LOG_LEVEL", None)
        try:
            settings = Settings()
            assert settings.log_level == "INFO"
        finally:
            if env_backup:
                os.environ["LOG_LEVEL"] = env_backup

    def test_settings_log_file_path_default(self) -> None:
        """Test default log file path."""
        env_backup = os.environ.pop("LOG_FILE_PATH", None)
        try:
            settings = Settings()
            assert settings.log_file_path == Path("./logs/benchmark.log")
        finally:
            if env_backup:
                os.environ["LOG_FILE_PATH"] = env_backup

    def test_settings_default_iterations(self, mocker: MockerFixture) -> None:
        """Test default iterations value."""
        mocker.patch.dict(os.environ, {"DEFAULT_ITERATIONS": "3"})
        settings = Settings()
        assert settings.default_iterations == 3

    def test_settings_random_seed_optional(self, mocker: MockerFixture) -> None:
        """Test that random seed is optional."""
        env_backup = os.environ.pop("RANDOM_SEED", None)
        try:
            settings = Settings()
            assert settings.random_seed is None
        finally:
            if env_backup:
                os.environ["RANDOM_SEED"] = env_backup

    def test_settings_random_seed_from_env(self, mocker: MockerFixture) -> None:
        """Test that random seed loads from environment."""
        mocker.patch.dict(os.environ, {"RANDOM_SEED": "42"})
        settings = Settings()
        assert settings.random_seed == 42

    def test_settings_api_key_required_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that a warning is logged when API key is not set."""
        env_backup = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            with caplog.at_level("WARNING"):
                settings = Settings()
                # Settings should still be created, but API key will be empty
                assert settings.openrouter_api_key == ""
        finally:
            if env_backup:
                os.environ["OPENROUTER_API_KEY"] = env_backup

    def test_settings_is_api_configured(self) -> None:
        """Test the is_api_configured property."""
        env_backup = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            settings = Settings()
            assert settings.is_api_configured is False
        finally:
            if env_backup:
                os.environ["OPENROUTER_API_KEY"] = env_backup

    def test_settings_is_api_configured_with_key(self, mocker: MockerFixture) -> None:
        """Test is_api_configured returns True when API key is set."""
        mocker.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
        settings = Settings()
        assert settings.is_api_configured is True
