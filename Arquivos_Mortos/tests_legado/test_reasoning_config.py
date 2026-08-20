"""Tests for reasoning configuration."""

import pytest
from src.utils.config import Settings


class TestReasoningConfig:
    """Test reasoning configuration."""

    def test_reasoning_effort_valid(self) -> None:
        """Test valid reasoning effort values."""
        valid_efforts = ["xhigh", "high", "medium", "low", "minimal", "none"]

        for effort in valid_efforts:
            settings = Settings(reasoning_effort=effort)
            assert settings.reasoning_effort == effort

    def test_reasoning_effort_case_insensitive(self) -> None:
        """Test reasoning effort is case-insensitive."""
        settings = Settings(reasoning_effort="HIGH")
        assert settings.reasoning_effort == "high"

        settings = Settings(reasoning_effort="MeDiUm")
        assert settings.reasoning_effort == "medium"

    def test_reasoning_effort_invalid(self) -> None:
        """Test invalid reasoning effort raises error."""
        with pytest.raises(ValueError, match="reasoning_effort must be one of"):
            Settings(reasoning_effort="invalid")

    def test_reasoning_effort_empty(self) -> None:
        """Test empty reasoning_effort returns None."""
        settings = Settings(reasoning_effort="")
        assert settings.reasoning_effort is None

    def test_reasoning_max_tokens(self) -> None:
        """Test reasoning_max_tokens configuration."""
        settings = Settings(reasoning_max_tokens=2000)
        assert settings.reasoning_max_tokens == 2000

        settings = Settings(reasoning_max_tokens=None)
        assert settings.reasoning_max_tokens is None

    def test_reasoning_exclude_default(self) -> None:
        """Test reasoning_exclude defaults to False."""
        settings = Settings()
        assert settings.reasoning_exclude is False

        settings = Settings(reasoning_exclude=True)
        assert settings.reasoning_exclude is True

    def test_reasoning_enabled_default(self) -> None:
        """Test reasoning_enabled defaults to False."""
        settings = Settings()
        assert settings.reasoning_enabled is False

        settings = Settings(reasoning_enabled=True)
        assert settings.reasoning_enabled is True
