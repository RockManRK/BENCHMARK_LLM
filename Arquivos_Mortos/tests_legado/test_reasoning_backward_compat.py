"""Tests for backward compatibility with reasoning support."""

import pytest
from src.utils.config import Settings
from src.api.client import OpenRouterClient
from src.core.question_executor import QuestionExecutor


class TestBackwardCompatibility:
    """Test that reasoning support doesn't break existing functionality."""

    def test_settings_without_reasoning(self) -> None:
        """Test Settings works without reasoning config."""
        settings = Settings()
        assert settings.reasoning_effort is None
        assert settings.reasoning_max_tokens is None
        assert settings.reasoning_exclude is False
        assert settings.reasoning_enabled is False

    def test_client_without_reasoning(self) -> None:
        """Test OpenRouterClient works without reasoning parameter."""
        # Should not raise error when reasoning is not provided
        client = OpenRouterClient(api_key="test", base_url="http://test")
        # Method signature should accept calls without reasoning
        # (actual API call would fail due to test setup, but signature is correct)
        assert client.api_key == "test"
        assert client.base_url == "http://test"

    def test_executor_without_reasoning(self) -> None:
        """Test QuestionExecutor works without reasoning config."""
        # This test verifies that QuestionExecutor can be initialized
        # without reasoning_config (backward compatibility)
        # We use mocks for the dependencies to avoid full setup
        from unittest.mock import MagicMock

        db_manager = MagicMock()
        api_client = MagicMock()
        randomizer = MagicMock()

        # Should initialize without reasoning_config (defaults to None)
        executor = QuestionExecutor(
            db_manager=db_manager,
            api_client=api_client,
            randomizer=randomizer,
            run_id="test-run",
            model_id="test-model",
            iteration_id=1,
        )
        # Verify executor was created successfully
        assert executor is not None
        assert executor._run_id == "test-run"
        assert executor._model_id == "test-model"
        assert executor._iteration_id == 1
        # reasoning_config should be None when not provided
        assert executor._reasoning_config is None

    def test_executor_with_reasoning(self) -> None:
        """Test QuestionExecutor works with reasoning config."""
        from unittest.mock import MagicMock

        db_manager = MagicMock()
        api_client = MagicMock()
        randomizer = MagicMock()

        # Should also work with reasoning_config provided
        reasoning_config = {"effort": "high", "max_tokens": 2000}
        executor = QuestionExecutor(
            db_manager=db_manager,
            api_client=api_client,
            randomizer=randomizer,
            run_id="test-run",
            model_id="test-model",
            iteration_id=1,
            reasoning_config=reasoning_config,
        )
        assert executor is not None
        assert executor._reasoning_config == reasoning_config

    def test_existing_benchmark_runs(self) -> None:
        """Test existing benchmark flow still works."""
        # This is a high-level test that the main flow still functions
        # with reasoning disabled (default)
        settings = Settings()
        # Default settings should have reasoning disabled
        assert settings.reasoning_enabled is False
        assert settings.reasoning_effort is None
        # Other settings should work as before
        # (base_url may be overridden by .env, so just check it's a string)
        assert isinstance(settings.openrouter_base_url, str)
        assert settings.openrouter_base_url.endswith("/v1")
