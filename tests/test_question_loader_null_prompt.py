"""Unit tests for ConfigResolver null prompt handling.

This module tests the behavior when SYSTEM_PROMPT and USER_PROMPT
keys are completely absent from environment.

Expected behavior:
- resolve_prompt() returns None (not empty string, not error)
- Null-by-default for prompts (no fallback strings)

Tests target >80% coverage for prompt resolution edge cases.
"""

import pytest

from src.core.config_resolver import ConfigResolver


class TestNullPromptHandling:
    """Test cases for prompt resolution when keys are absent."""

    @pytest.fixture
    def resolver(self) -> ConfigResolver:
        """Create ConfigResolver instance."""
        return ConfigResolver()

    @pytest.fixture(autouse=True)
    def clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clean environment before each test."""
        for key in ['SYSTEM_PROMPT', 'USER_PROMPT']:
            monkeypatch.delenv(key, raising=False)

    def test_system_prompt_absent_returns_none(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that absent SYSTEM_PROMPT key returns None."""
        # Simulate .env without SYSTEM_PROMPT
        monkeypatch.setenv('OTHER_KEY', 'value')
        monkeypatch.delenv('SYSTEM_PROMPT', raising=False)
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value=None, env_key="SYSTEM_PROMPT", default=None)

        assert result is None

    def test_user_prompt_absent_returns_none(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that absent USER_PROMPT key returns None."""
        # Simulate .env without USER_PROMPT
        monkeypatch.setenv('OTHER_KEY', 'value')
        monkeypatch.delenv('USER_PROMPT', raising=False)
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value=None, env_key="USER_PROMPT", default=None)

        assert result is None

    def test_both_prompts_absent_returns_none(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that both prompts absent returns None for both."""
        # Simulate .env without prompt keys
        monkeypatch.setenv('OTHER_KEY', 'value')
        monkeypatch.delenv('SYSTEM_PROMPT', raising=False)
        monkeypatch.delenv('USER_PROMPT', raising=False)
        
        resolver.load_env()

        system_result = resolver.resolve_prompt(cli_value=None, env_key="SYSTEM_PROMPT", default=None)
        user_result = resolver.resolve_prompt(cli_value=None, env_key="USER_PROMPT", default=None)

        assert system_result is None
        assert user_result is None

    def test_empty_env_file_returns_none(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment without prompt keys returns None."""
        # Clean all relevant env vars
        for key in ['SYSTEM_PROMPT', 'USER_PROMPT']:
            monkeypatch.delenv(key, raising=False)
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value=None, env_key="SYSTEM_PROMPT", default=None)

        assert result is None

    def test_nonexistent_env_file_returns_none(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment without prompt keys returns None."""
        for key in ['SYSTEM_PROMPT', 'USER_PROMPT']:
            monkeypatch.delenv(key, raising=False)
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value=None, env_key="SYSTEM_PROMPT", default=None)

        assert result is None

    def test_cli_value_takes_precedence_over_absent_env(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that CLI value is used when env key is absent."""
        monkeypatch.delenv('SYSTEM_PROMPT', raising=False)
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value="CLI prompt", env_key="SYSTEM_PROMPT", default=None)

        assert result == "CLI prompt"

    def test_default_used_when_cli_and_env_absent(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default is used when both CLI and env are absent."""
        monkeypatch.delenv('SYSTEM_PROMPT', raising=False)
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value=None, env_key="SYSTEM_PROMPT", default="Default prompt")

        assert result == "Default prompt"

    def test_empty_string_env_treated_as_absent(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that empty string env value is treated as absent."""
        monkeypatch.setenv('SYSTEM_PROMPT', '')
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value=None, env_key="SYSTEM_PROMPT", default=None)

        assert result is None

    def test_whitespace_only_env_treated_as_absent(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that whitespace-only env value is treated as absent."""
        monkeypatch.setenv('SYSTEM_PROMPT', '   ')
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value=None, env_key="SYSTEM_PROMPT", default=None)

        assert result is None

    def test_env_with_value_returns_value(self, resolver: ConfigResolver, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that env with value returns the value."""
        monkeypatch.setenv('SYSTEM_PROMPT', 'Test prompt from env')
        
        resolver.load_env()

        result = resolver.resolve_prompt(cli_value=None, env_key="SYSTEM_PROMPT", default=None)

        assert result == "Test prompt from env"


class TestNullPromptIntegration:
    """Integration tests for null prompt handling in experiment context."""

    def test_build_experiment_config_with_null_prompts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test building experiment config when prompts are null."""
        # Remove prompt keys from environment
        monkeypatch.delenv('SYSTEM_PROMPT', raising=False)
        monkeypatch.delenv('USER_PROMPT', raising=False)
        
        from argparse import Namespace
        from src.core.config_resolver import ConfigResolver

        resolver = ConfigResolver()
        resolver.load_env()

        cli_args = Namespace(
            system_prompt=None,
            user_prompt=None,
            seed=None,
            create_experiment="test-exp"
        )

        config = resolver.build_experiment_config_dict(cli_args)

        assert config.get("SYSTEM_PROMPT") is None
        assert config.get("USER_PROMPT") is None

    def test_build_experiment_config_cli_overrides_null_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that CLI prompts override when env has null prompts."""
        monkeypatch.delenv('SYSTEM_PROMPT', raising=False)
        monkeypatch.delenv('USER_PROMPT', raising=False)
        
        from argparse import Namespace
        from src.core.config_resolver import ConfigResolver

        resolver = ConfigResolver()
        resolver.load_env()

        cli_args = Namespace(
            system_prompt="CLI System Prompt",
            user_prompt="CLI User Prompt",
            seed=None,
            create_experiment="test-exp"
        )

        config = resolver.build_experiment_config_dict(cli_args)

        assert config.get("SYSTEM_PROMPT") == "CLI System Prompt"
        assert config.get("USER_PROMPT") == "CLI User Prompt"
