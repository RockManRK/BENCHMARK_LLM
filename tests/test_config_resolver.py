"""Unit tests for ConfigResolver.

Tests cover:
- resolve_prompt() with CLI, .env, and default values
- resolve_seed() with CLI, .env, AUTO, and None values
- load_env() behavior
- resolve_config_dict() integration
- _generate_seed_from_name() determinism
"""

import pytest

from src.core.config_resolver import ConfigResolver


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
    """Test cases for the resolve_seed method (EXPERIMENT level - does NOT resolve AUTO)."""

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

    def test_auto_from_cli_returns_auto_string(self) -> None:
        """Test that AUTO from CLI returns 'AUTO' string (NOT resolved at experiment level)."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_seed(
            cli_value="AUTO",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result == "AUTO"

    def test_auto_from_env_returns_auto_string(self) -> None:
        """Test that AUTO from .env returns 'AUTO' string (NOT resolved at experiment level)."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOM_SEED": "AUTO"}

        result = resolver.resolve_seed(
            cli_value=None,
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result == "AUTO"

    def test_cli_auto_takes_priority_over_env_integer(self) -> None:
        """Test that CLI AUTO takes priority over .env integer."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOM_SEED": "42"}

        result = resolver.resolve_seed(
            cli_value="AUTO",
            env_key="RANDOM_SEED",
            experiment_name="test_exp"
        )

        assert result == "AUTO"

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

        assert result1 == result2 == result3 == "AUTO"

    def test_different_experiment_names_return_same_auto(self) -> None:
        """Test that different experiment names all return 'AUTO' (resolution happens at RUN level)."""
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

        # Both should return "AUTO" string (resolution happens at RUN level)
        assert result1 == "AUTO"
        assert result2 == "AUTO"


class TestLoadEnv:
    """Test cases for the load_env method.

    NOTE: load_env() now only creates a cached snapshot of os.environ.
    The .env file is loaded once at application startup by bcllm.py.
    """

    def test_load_env_creates_snapshot_of_os_environ(self) -> None:
        """Test that load_env creates a snapshot of current os.environ."""
        import os
        resolver = ConfigResolver()

        result = resolver.load_env()

        # Should return a copy of os.environ, not empty dict
        assert result == dict(os.environ)
        assert resolver.env_dict == dict(os.environ)
        # Verify it's a copy, not the same object
        assert resolver.env_dict is not os.environ

    def test_load_env_populates_env_dict(self) -> None:
        """Test that load_env populates env_dict from .env file."""
        resolver = ConfigResolver()

        result = resolver.load_env()

        assert isinstance(result, dict)
        assert isinstance(resolver.env_dict, dict)


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


class TestResolveSeedForRun:
    """Test cases for resolve_seed_for_run method (AUTO resolution at RUN level)."""

    def test_auto_generates_deterministic_seed_from_run_id(self) -> None:
        """Test that AUTO generates deterministic seed from run_id + experiment_id."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result1 = resolver.resolve_seed_for_run(
            cli_value="AUTO",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_abc123",
            experiment_id="exp_xyz789"
        )

        result2 = resolver.resolve_seed_for_run(
            cli_value="AUTO",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_abc123",
            experiment_id="exp_xyz789"
        )

        assert isinstance(result1, int)
        assert result1 > 0
        assert result1 == result2

    def test_different_runs_produce_different_seeds(self) -> None:
        """Test that different run IDs produce different seeds."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result1 = resolver.resolve_seed_for_run(
            cli_value="AUTO",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_xyz789"
        )

        result2 = resolver.resolve_seed_for_run(
            cli_value="AUTO",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_002",
            experiment_id="exp_xyz789"
        )

        assert result1 != result2

    def test_different_experiments_produce_different_seeds(self) -> None:
        """Test that different experiment IDs produce different seeds."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result1 = resolver.resolve_seed_for_run(
            cli_value="AUTO",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_abc123",
            experiment_id="exp_001"
        )

        result2 = resolver.resolve_seed_for_run(
            cli_value="AUTO",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_abc123",
            experiment_id="exp_002"
        )

        assert result1 != result2

    def test_integer_cli_value_returns_integer(self) -> None:
        """Test that integer CLI value is returned as-is."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_seed_for_run(
            cli_value="42",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result == 42

    def test_cli_auto_overrides_env_integer(self) -> None:
        """Test that CLI AUTO generates seed even when .env has integer."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RUN_RESPONSES_SEED": "123"}

        result = resolver.resolve_seed_for_run(
            cli_value="AUTO",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert isinstance(result, int)
        assert result != 123

    def test_env_auto_generates_seed(self) -> None:
        """Test that AUTO from .env generates deterministic seed."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RUN_RESPONSES_SEED": "AUTO"}

        result = resolver.resolve_seed_for_run(
            cli_value=None,
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert isinstance(result, int)
        assert result > 0

    def test_none_returns_none(self) -> None:
        """Test that None CLI and missing .env returns None."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_seed_for_run(
            cli_value=None,
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result is None

    def test_auto_case_insensitive_for_run(self) -> None:
        """Test that AUTO is case-insensitive for run-level resolution."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result1 = resolver.resolve_seed_for_run(
            cli_value="AUTO",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_001"
        )

        result2 = resolver.resolve_seed_for_run(
            cli_value="auto",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_001"
        )

        result3 = resolver.resolve_seed_for_run(
            cli_value="Auto",
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result1 == result2 == result3


class TestBuildExperimentConfigDict:
    """Test cases for build_experiment_config_dict method."""

    def test_returns_dict_with_14_keys(self) -> None:
        """Test that experiment config has 14 expected keys.

        NOTE: QUESTIONS_STATUS_ADD and QUESTIONS_STATUS_EXCLUDE are NOT persisted
        (used for filtering at creation time only). MODELS_DEFAULT_FOR_EXPERIMENTS
        was removed from the system.
        """
        resolver = ConfigResolver()
        resolver.env_dict = {
            "QUESTIONS_DATASET_PATH": "/path/to/questions",
            "QUESTIONS_STATUS_ADD": "active",
            "QUESTIONS_STATUS_EXCLUDE": "draft",
            "BASE_URL": "https://api.example.com",
            "MODEL_MAX_TOKENS_REASONING": "1000",
            "MODEL_MAX_TOKENS_TOTAL": "4096",
            "MODEL_REASONING_EFFORT": "high",
            "MODEL_REPEAT_PENALTY": "1.1",
            "MODEL_TEMPERATURE": "0.7",
            "MODEL_TOP_K": "50",
            "MODEL_TOP_P": "0.9",
            "MODEL_VISION": "true",
            "STRUCTURED_OUTPUTS": "false",
            "RUN_RESPONSES_SEED": "42",
            "SYSTEM_PROMPT": "Test system prompt",
            "USER_PROMPT": "Test user prompt",
        }

        class MockArgs:
            seed = None
            system_prompt = None
            user_prompt = None
            url = None
            reasoning_tokens = None
            max_reasoning = None
            max_tokens = None
            reasoning = None
            repeat_penalty = None
            temperature = None
            top_k = None
            top_p = None
            vision = None
            structured = None
            experiment_name = "test_exp"

        result = resolver.build_experiment_config_dict(MockArgs())

        expected_keys = {
            "QUESTIONS_DATASET_PATH",
            "BASE_URL",
            "MODEL_MAX_TOKENS_REASONING",
            "MODEL_MAX_TOKENS_TOTAL",
            "MODEL_REASONING_EFFORT",
            "MODEL_REPEAT_PENALTY",
            "MODEL_TEMPERATURE",
            "MODEL_TOP_K",
            "MODEL_TOP_P",
            "MODEL_VISION",
            "STRUCTURED_OUTPUTS",
            "RUN_RESPONSES_SEED",
            "SYSTEM_PROMPT",
            "USER_PROMPT",
        }

        assert set(result.keys()) == expected_keys
        assert len(result) == 14  # 14 keys total

    def test_does_not_include_system_keys(self) -> None:
        """Test that SYSTEM keys are NOT included in experiment config."""
        resolver = ConfigResolver()
        resolver.env_dict = {
            "DATABASE_PATH": "./data/bcllm.db",
            "EXECUTION_MODE": "prod",
            "LOG_FILE_PATH": "./logs/app.log",
            "LOG_LEVEL": "INFO",
            "OPENROUTER_DEBUG_ENABLED": "true",
        }

        class MockArgs:
            seed = None
            experiment_name = "test_exp"

        result = resolver.build_experiment_config_dict(MockArgs())

        forbidden_keys = {
            "DATABASE_PATH",
            "EXECUTION_MODE",
            "LOG_FILE_PATH",
            "LOG_LEVEL",
            "OPENROUTER_DEBUG_ENABLED",
        }

        assert not (forbidden_keys & set(result.keys()))

    def test_contract_keys_are_upper_case(self) -> None:
        """Test that all contract keys use UPPER_CASE naming."""
        resolver = ConfigResolver()
        resolver.env_dict = {
            "QUESTIONS_DATASET_PATH": "/path",
            "BASE_URL": "https://api.example.com",
            "MODEL_TEMPERATURE": "0.7",
            "RUN_RESPONSES_SEED": "42",
            "SYSTEM_PROMPT": "test",
            "USER_PROMPT": "test",
        }

        class MockArgs:
            seed = None
            experiment_name = "test_exp"

        result = resolver.build_experiment_config_dict(MockArgs())

        # All keys should be UPPER_CASE
        for key in result.keys():
            assert key == key.upper() or key in ("SYSTEM_PROMPT", "USER_PROMPT", "BASE_URL")

    def test_empty_string_env_values_resolved_as_none(self) -> None:
        """Test that empty string values in .env are treated as None.

        This ensures that fields like MODEL_REASONING_EFFORT= in .env
        produce null in config_json, not empty strings.
        """
        resolver = ConfigResolver()
        resolver.env_dict = {
            "QUESTIONS_DATASET_PATH": "/path/to/questions",
            "MODEL_REASONING_EFFORT": "",
            "MODEL_TEMPERATURE": "",
            "MODEL_TOP_P": "",
            "MODEL_TOP_K": "",
            "MODEL_MAX_TOKENS_TOTAL": "",
            "MODEL_MAX_TOKENS_REASONING": "",
            "MODEL_REPEAT_PENALTY": "",
            "MODEL_VISION": "",
            "STRUCTURED_OUTPUTS": "",
            "BASE_URL": "",
            "RUN_RESPONSES_SEED": "",
            "SYSTEM_PROMPT": "",
            "USER_PROMPT": "",
        }

        class MockArgs:
            seed = None
            system_prompt = None
            user_prompt = None
            url = None
            reasoning_tokens = None
            max_reasoning = None
            max_tokens = None
            reasoning = None
            repeat_penalty = None
            temperature = None
            top_k = None
            top_p = None
            vision = None
            structured = None
            experiment_name = "test_exp"

        result = resolver.build_experiment_config_dict(MockArgs())

        # All empty string fields should resolve to None
        assert result["MODEL_REASONING_EFFORT"] is None
        assert result["MODEL_TEMPERATURE"] is None
        assert result["MODEL_TOP_P"] is None
        assert result["MODEL_TOP_K"] is None
        assert result["MODEL_MAX_TOKENS_TOTAL"] is None
        assert result["MODEL_MAX_TOKENS_REASONING"] is None
        assert result["MODEL_REPEAT_PENALTY"] is None
        assert result["BASE_URL"] is None
        assert result["SYSTEM_PROMPT"] is None
        assert result["USER_PROMPT"] is None


class TestBuildModelConfigDict:
    """Test cases for build_model_config_dict method."""

    def test_returns_dict_with_10_keys(self) -> None:
        """Test that model config has all 10 expected keys."""
        resolver = ConfigResolver()
        resolver.env_dict = {
            "BASE_URL": "https://api.example.com",
            "MODEL_MAX_TOKENS_REASONING": "1000",
            "MODEL_MAX_TOKENS_TOTAL": "4096",
            "MODEL_REASONING_EFFORT": "high",
            "MODEL_REPEAT_PENALTY": "1.1",
            "MODEL_TEMPERATURE": "0.7",
            "MODEL_TOP_K": "50",
            "MODEL_TOP_P": "0.9",
            "MODEL_VISION": "true",
            "STRUCTURED_OUTPUTS": "false",
        }

        class MockArgs:
            url = None
            reasoning_tokens = None
            max_reasoning = None
            max_tokens = None
            reasoning = None
            repeat_penalty = None
            temperature = None
            top_k = None
            top_p = None
            vision = None
            structured = None

        class MockExperiment:
            config_json = "{}"

        result = resolver.build_model_config_dict(MockArgs(), MockExperiment())

        expected_keys = {
            "BASE_URL",
            "MODEL_MAX_TOKENS_REASONING",
            "MODEL_MAX_TOKENS_TOTAL",
            "MODEL_REASONING_EFFORT",
            "MODEL_REPEAT_PENALTY",
            "MODEL_TEMPERATURE",
            "MODEL_TOP_K",
            "MODEL_TOP_P",
            "MODEL_VISION",
            "STRUCTURED_OUTPUTS",
        }

        assert set(result.keys()) == expected_keys
        assert len(result) == 10

    def test_boolean_values_case_insensitive(self) -> None:
        """Test that boolean values are case-insensitive."""
        resolver = ConfigResolver()

        # Test various case combinations
        assert resolver._parse_bool_value("true") is True
        assert resolver._parse_bool_value("True") is True
        assert resolver._parse_bool_value("TRUE") is True
        assert resolver._parse_bool_value("false") is False
        assert resolver._parse_bool_value("False") is False
        assert resolver._parse_bool_value("FALSE") is False
        # 'system-default' should be normalized to FORCE_SYSTEM_DEFAULT before reaching here
        # but legacy string 'null' is still handled for backward compatibility (deprecated)
        assert resolver._parse_bool_value("NULL") is None  # Deprecated, but handled
        assert resolver._parse_bool_value("null") is None  # Deprecated, but handled
        assert resolver._parse_bool_value(None) is None


class TestBuildRunConfigDict:
    """Test cases for build_run_config_dict method."""

    def test_returns_dict_with_3_keys(self) -> None:
        """Test that run config has all 3 expected keys."""
        resolver = ConfigResolver()
        resolver.env_dict = {
            "RUN_RESPONSES_SEED": "42",
            "SYSTEM_PROMPT": "Test system",
            "USER_PROMPT": "Test user",
        }

        class MockArgs:
            seed = None
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = "{}"

        result = resolver.build_run_config_dict(MockArgs(), MockExperiment())

        expected_keys = {"RUN_RESPONSES_SEED", "SYSTEM_PROMPT", "USER_PROMPT"}

        assert set(result.keys()) == expected_keys
        assert len(result) == 3

    def test_auto_seed_resolved_at_run_level(self) -> None:
        """Test that AUTO seed is resolved to integer at run creation."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RUN_RESPONSES_SEED": "AUTO"}

        class MockArgs:
            seed = None
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = "{}"

        result = resolver.build_run_config_dict(MockArgs(), MockExperiment())

        # AUTO should be resolved to an integer
        assert isinstance(result["RUN_RESPONSES_SEED"], int)
        assert result["RUN_RESPONSES_SEED"] > 0

    def test_run_seed_is_per_run_unique(self) -> None:
        """Test that AUTO seed produces different values for different runs."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RUN_RESPONSES_SEED": "AUTO"}

        class MockArgs:
            seed = None
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = "{}"

        # Simulate two different runs
        result1 = resolver.resolve_seed_for_run(
            cli_value=None,
            env_key="RUN_RESPONSES_SEED",
            run_id="run_001",
            experiment_id="exp_001"
        )

        result2 = resolver.resolve_seed_for_run(
            cli_value=None,
            env_key="RUN_RESPONSES_SEED",
            run_id="run_002",
            experiment_id="exp_001"
        )

        assert result1 != result2
        assert isinstance(result1, int)
        assert isinstance(result2, int)
