"""Unit tests for ConfigResolver.

Tests cover:
- resolve_prompt() with CLI, .env, and default values
- resolve_seed() with CLI, .env, AUTO, and None values
- load_env() behavior
- resolve_config_dict() integration
- _generate_seed_from_name() determinism
"""

import pytest

from src_v2.core.config_resolver import ConfigResolver


class TestResolvePrompt:
    """Test cases for the resolve_prompt method."""

    def test_cli_provided_returns_cli_value(self) -> None:
        """Test that CLI value is returned when provided."""
        resolver = ConfigResolver()
        resolver.env_dict = {"SYSTEM_PROMPT": "env_value"}

        result = resolver.resolve_prompt(
            cli_value="cli_value",
            env_key="SYSTEM_PROMPT",
            default="default_value"
        )

        assert result == "cli_value"

    def test_cli_missing_env_has_value_returns_env_value(self) -> None:
        """Test that .env value is returned when CLI is missing."""
        resolver = ConfigResolver()
        resolver.env_dict = {"SYSTEM_PROMPT": "env_value"}

        result = resolver.resolve_prompt(
            cli_value=None,
            env_key="SYSTEM_PROMPT",
            default="default_value"
        )

        assert result == "env_value"

    def test_cli_missing_env_missing_default_provided_returns_default(self) -> None:
        """Test that default is returned when CLI and .env are missing."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_prompt(
            cli_value=None,
            env_key="SYSTEM_PROMPT",
            default="default_value"
        )

        assert result == "default_value"

    def test_cli_missing_env_missing_no_default_returns_none(self) -> None:
        """Test that None is returned when nothing is provided."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_prompt(
            cli_value=None,
            env_key="SYSTEM_PROMPT",
            default=None
        )

        assert result is None

    def test_cli_empty_string_falls_through(self) -> None:
        """Test that empty CLI value falls through to .env."""
        resolver = ConfigResolver()
        resolver.env_dict = {"SYSTEM_PROMPT": "env_value"}

        result = resolver.resolve_prompt(
            cli_value="",
            env_key="SYSTEM_PROMPT",
            default="default_value"
        )

        assert result == "env_value"

    def test_cli_whitespace_only_falls_through(self) -> None:
        """Test that whitespace-only CLI value falls through to .env."""
        resolver = ConfigResolver()
        resolver.env_dict = {"SYSTEM_PROMPT": "env_value"}

        result = resolver.resolve_prompt(
            cli_value="   ",
            env_key="SYSTEM_PROMPT",
            default="default_value"
        )

        assert result == "env_value"

    def test_env_empty_string_falls_through_to_default(self) -> None:
        """Test that empty .env value falls through to default."""
        resolver = ConfigResolver()
        resolver.env_dict = {"SYSTEM_PROMPT": ""}

        result = resolver.resolve_prompt(
            cli_value=None,
            env_key="SYSTEM_PROMPT",
            default="default_value"
        )

        assert result == "default_value"

    def test_env_whitespace_only_falls_through_to_default(self) -> None:
        """Test that whitespace-only .env value falls through to default."""
        resolver = ConfigResolver()
        resolver.env_dict = {"SYSTEM_PROMPT": "   "}

        result = resolver.resolve_prompt(
            cli_value=None,
            env_key="SYSTEM_PROMPT",
            default="default_value"
        )

        assert result == "default_value"

    def test_cli_value_is_stripped(self) -> None:
        """Test that CLI value is stripped of whitespace."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_prompt(
            cli_value="  cli_value  ",
            env_key="SYSTEM_PROMPT",
            default=None
        )

        assert result == "cli_value"

    def test_env_value_is_stripped(self) -> None:
        """Test that .env value is stripped of whitespace."""
        resolver = ConfigResolver()
        resolver.env_dict = {"SYSTEM_PROMPT": "  env_value  "}

        result = resolver.resolve_prompt(
            cli_value=None,
            env_key="SYSTEM_PROMPT",
            default=None
        )

        assert result == "env_value"


class TestResolveSeed:
    """Test cases for the resolve_seed method."""

    def test_integer_value_returns_integer(self) -> None:
        """Test that integer seed value is returned."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_seed(
            cli_value="42",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result == 42

    def test_auto_from_cli_generates_deterministic_seed(self) -> None:
        """Test that AUTO from CLI generates deterministic seed."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_seed(
            cli_value="AUTO",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert isinstance(result, int)
        assert result > 0

    def test_auto_from_env_generates_deterministic_seed(self) -> None:
        """Test that AUTO from .env generates deterministic seed."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOM_SEED": "AUTO"}

        result = resolver.resolve_seed(
            cli_value=None,
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert isinstance(result, int)
        assert result > 0

    def test_cli_auto_takes_priority_over_env_integer(self) -> None:
        """Test that CLI AUTO takes priority over .env integer."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOM_SEED": "42"}

        result = resolver.resolve_seed(
            cli_value="AUTO",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert isinstance(result, int)
        assert result != 42

    def test_cli_integer_takes_priority_over_env_auto(self) -> None:
        """Test that CLI integer takes priority over .env AUTO."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOM_SEED": "AUTO"}

        result = resolver.resolve_seed(
            cli_value="42",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result == 42

    def test_none_returns_none(self) -> None:
        """Test that None CLI and missing .env returns None."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_seed(
            cli_value=None,
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result is None

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_seed(
            cli_value="",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result is None

    def test_whitespace_only_returns_none(self) -> None:
        """Test that whitespace-only string returns None."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_seed(
            cli_value="   ",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result is None

    def test_auto_case_insensitive(self) -> None:
        """Test that AUTO is case-insensitive."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result1 = resolver.resolve_seed(
            cli_value="AUTO",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        result2 = resolver.resolve_seed(
            cli_value="auto",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        result3 = resolver.resolve_seed(
            cli_value="Auto",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result1 == result2 == result3

    def test_different_experiment_names_produce_different_seeds(self) -> None:
        """Test that different experiment names produce different seeds."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result1 = resolver.resolve_seed(
            cli_value="AUTO",
            env_key="RANDOM_SEED",
            experiment_name="exp1"
        )

        result2 = resolver.resolve_seed(
            cli_value="AUTO",
            env_key="RANDOM_SEED",
            experiment_name="exp2"
        )

        assert result1 != result2


class TestLoadEnv:
    """Test cases for the load_env method."""

    def test_load_env_returns_empty_dict_if_file_not_exists(self) -> None:
        """Test that load_env returns empty dict if file doesn't exist."""
        resolver = ConfigResolver()

        result = resolver.load_env("nonexistent_file.env")

        assert result == {}
        assert resolver.env_dict == {}

    def test_load_env_populates_env_dict(self) -> None:
        """Test that load_env populates env_dict from .env file."""
        resolver = ConfigResolver()

        result = resolver.load_env()

        assert isinstance(result, dict)
        assert isinstance(resolver.env_dict, dict)


class TestResolveConfigDict:
    """Test cases for the resolve_config_dict method."""

    def test_full_resolution_with_all_sources(self) -> None:
        """Test resolution with mixed CLI and .env values."""
        resolver = ConfigResolver()
        resolver.env_dict = {
            "RANDOM_SEED": "42",
            "SYSTEM_PROMPT_TEMPLATE": "env_system",
            "USER_PROMPT_TEMPLATE": "env_user",
            "RETRY_POLICY": "env_retry"
        }

        class MockArgs:
            seed = "99"
            system_prompt = None
            user_prompt = "cli_user"
            retry_policy = None
            experiment_name = "test_exp"

        result = resolver.resolve_config_dict(MockArgs())

        assert result["seed"] == 99
        assert result["system_prompt"] == "env_system"
        assert result["user_prompt"] == "cli_user"
        assert result["retry_policy"] == "env_retry"

    def test_all_cli_values_take_priority(self) -> None:
        """Test that CLI values take priority over .env values."""
        resolver = ConfigResolver()
        resolver.env_dict = {
            "RANDOM_SEED": "42",
            "SYSTEM_PROMPT_TEMPLATE": "env_system",
            "USER_PROMPT_TEMPLATE": "env_user",
            "RETRY_POLICY": "env_retry"
        }

        class MockArgs:
            seed = "99"
            system_prompt = "cli_system"
            user_prompt = "cli_user"
            retry_policy = "cli_retry"
            experiment_name = "test_exp"

        result = resolver.resolve_config_dict(MockArgs())

        assert result["seed"] == 99
        assert result["system_prompt"] == "cli_system"
        assert result["user_prompt"] == "cli_user"
        assert result["retry_policy"] == "cli_retry"

    def test_all_env_values_used_when_cli_missing(self) -> None:
        """Test that .env values are used when CLI is missing."""
        resolver = ConfigResolver()
        resolver.env_dict = {
            "RANDOM_SEED": "42",
            "SYSTEM_PROMPT_TEMPLATE": "env_system",
            "USER_PROMPT_TEMPLATE": "env_user",
            "RETRY_POLICY": "env_retry"
        }

        class MockArgs:
            seed = None
            system_prompt = None
            user_prompt = None
            retry_policy = None
            experiment_name = "test_exp"

        result = resolver.resolve_config_dict(MockArgs())

        assert result["seed"] == 42
        assert result["system_prompt"] == "env_system"
        assert result["user_prompt"] == "env_user"
        assert result["retry_policy"] == "env_retry"

    def test_null_by_default_for_prompts(self) -> None:
        """Test that prompts are null-by-default when not provided.
        
        Keys with None values should NOT be included in the result dict.
        """
        resolver = ConfigResolver()
        resolver.env_dict = {}

        class MockArgs:
            seed = None
            system_prompt = None
            user_prompt = None
            retry_policy = None
            experiment_name = "test_exp"

        result = resolver.resolve_config_dict(MockArgs())

        assert "seed" not in result
        assert "system_prompt" not in result
        assert "user_prompt" not in result
        assert "retry_policy" not in result
        assert result == {}

    def test_auto_seed_from_env_with_experiment_name(self) -> None:
        """Test that AUTO seed generates deterministic value from experiment name."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOM_SEED": "AUTO"}

        class MockArgs:
            seed = None
            system_prompt = None
            user_prompt = None
            retry_policy = None
            experiment_name = "my_experiment"

        result1 = resolver.resolve_config_dict(MockArgs())
        result2 = resolver.resolve_config_dict(MockArgs())

        assert result1["seed"] == result2["seed"]
        assert isinstance(result1["seed"], int)
        assert result1["seed"] > 0


class TestGenerateSeedFromName:
    """Test cases for the _generate_seed_from_name helper method."""

    def test_same_name_produces_same_seed(self) -> None:
        """Test that the same experiment name always produces the same seed."""
        resolver = ConfigResolver()

        seed1 = resolver._generate_seed_from_name("test_experiment")
        seed2 = resolver._generate_seed_from_name("test_experiment")

        assert seed1 == seed2

    def test_different_names_produce_different_seeds(self) -> None:
        """Test that different experiment names produce different seeds."""
        resolver = ConfigResolver()

        seed1 = resolver._generate_seed_from_name("experiment_1")
        seed2 = resolver._generate_seed_from_name("experiment_2")

        assert seed1 != seed2

    def test_seed_is_positive_integer(self) -> None:
        """Test that generated seed is always a positive integer."""
        resolver = ConfigResolver()

        seed = resolver._generate_seed_from_name("any_experiment")

        assert isinstance(seed, int)
        assert seed > 0
        assert seed < (2 ** 31)
