"""Unit tests for ConfigResolver.

Tests cover:
- resolve_prompt() with CLI, .env, and default values
- resolve_randomization_seed() with CLI, .env, AUTO, and None values
  (Randomization Seed only — controls AnswerRandomizer; unrelated to
  Model Seed, the seed sent to the API for inference, not yet
  implemented — see docs/status/seed-vocabulary-separation-investigation.md)
- resolve_randomization_seed_for_run() — the canonical Run-creation-time
  resolver (AUTO resolution, Experiment -> Run inheritance)
- Model Seed (MODEL_SEED) resolution at Experiment and model_variant level
  (Checkpoint B — see docs/status/model-seed-checkpoint-b-design.md)
- load_env() behavior
- resolve_config_dict() integration
"""

import json
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


class TestResolveRandomizationSeed:
    """Test cases for the resolve_randomization_seed method (EXPERIMENT
    level - does NOT resolve AUTO). Renamed 2026-08-20 from
    TestResolveSeed/resolve_seed (seed vocabulary separation checkpoint)."""

    def test_integer_value_returns_integer(self) -> None:
        """Test that integer seed value is returned."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_randomization_seed(
            cli_value="42",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result == 42

    def test_auto_from_cli_returns_auto_string(self) -> None:
        """Test that AUTO from CLI returns 'AUTO' string (NOT resolved at experiment level)."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_randomization_seed(
            cli_value="AUTO",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result == "AUTO"

    def test_auto_from_env_returns_auto_string(self) -> None:
        """Test that AUTO from .env returns 'AUTO' string (NOT resolved at experiment level)."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOMIZATION_SEED": "AUTO"}

        result = resolver.resolve_randomization_seed(
            cli_value=None,
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result == "AUTO"

    def test_cli_auto_takes_priority_over_env_integer(self) -> None:
        """Test that CLI AUTO takes priority over .env integer."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOMIZATION_SEED": "42"}

        result = resolver.resolve_randomization_seed(
            cli_value="AUTO",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result == "AUTO"

    def test_cli_integer_takes_priority_over_env_auto(self) -> None:
        """Test that CLI integer takes priority over .env AUTO."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOMIZATION_SEED": "AUTO"}

        result = resolver.resolve_randomization_seed(
            cli_value="42",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result == 42

    def test_none_returns_none(self) -> None:
        """Test that None CLI and missing .env returns None."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_randomization_seed(
            cli_value=None,
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result is None

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_randomization_seed(
            cli_value="",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result is None

    def test_whitespace_only_returns_none(self) -> None:
        """Test that whitespace-only string returns None."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver.resolve_randomization_seed(
            cli_value="   ",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result is None

    def test_auto_case_insensitive(self) -> None:
        """Test that AUTO is case-insensitive."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result1 = resolver.resolve_randomization_seed(
            cli_value="AUTO",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        result2 = resolver.resolve_randomization_seed(
            cli_value="auto",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        result3 = resolver.resolve_randomization_seed(
            cli_value="Auto",
            env_key="RANDOMIZATION_SEED",
            experiment_name="test_exp"
        )

        assert result1 == result2 == result3 == "AUTO"

    def test_different_experiment_names_return_same_auto(self) -> None:
        """Test that different experiment names all return 'AUTO' (resolution happens at RUN level)."""
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result1 = resolver.resolve_randomization_seed(
            cli_value="AUTO",
            env_key="RANDOMIZATION_SEED",
            experiment_name="exp1"
        )

        result2 = resolver.resolve_randomization_seed(
            cli_value="AUTO",
            env_key="RANDOMIZATION_SEED",
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


class TestResolveRandomizationSeedForRun:
    """Test cases for resolve_randomization_seed_for_run — the canonical
    Run-creation-time resolver (AUTO resolution happens here, and only
    here). Renamed and re-scoped 2026-08-20 from resolve_seed_for_run,
    which took an env_key/consulted .env — wrong for run-level
    resolution, which only ever inherits from the Experiment's own
    already-resolved seed, never .env directly. The new signature takes
    `experiment_seed` (the experiment's resolved value) instead of an
    env_key."""

    def test_auto_generates_deterministic_seed_from_run_id(self) -> None:
        """Test that AUTO generates deterministic seed from run_id + experiment_id."""
        resolver = ConfigResolver()

        result1 = resolver.resolve_randomization_seed_for_run(
            cli_value="AUTO",
            experiment_seed=None,
            run_id="run_abc123",
            experiment_id="exp_xyz789"
        )

        result2 = resolver.resolve_randomization_seed_for_run(
            cli_value="AUTO",
            experiment_seed=None,
            run_id="run_abc123",
            experiment_id="exp_xyz789"
        )

        assert isinstance(result1, int)
        assert result1 > 0
        assert result1 == result2

    def test_different_runs_produce_different_seeds(self) -> None:
        """Test that different run IDs produce different seeds."""
        resolver = ConfigResolver()

        result1 = resolver.resolve_randomization_seed_for_run(
            cli_value="AUTO",
            experiment_seed=None,
            run_id="run_001",
            experiment_id="exp_xyz789"
        )

        result2 = resolver.resolve_randomization_seed_for_run(
            cli_value="AUTO",
            experiment_seed=None,
            run_id="run_002",
            experiment_id="exp_xyz789"
        )

        assert result1 != result2

    def test_different_experiments_produce_different_seeds(self) -> None:
        """Test that different experiment IDs produce different seeds."""
        resolver = ConfigResolver()

        result1 = resolver.resolve_randomization_seed_for_run(
            cli_value="AUTO",
            experiment_seed=None,
            run_id="run_abc123",
            experiment_id="exp_001"
        )

        result2 = resolver.resolve_randomization_seed_for_run(
            cli_value="AUTO",
            experiment_seed=None,
            run_id="run_abc123",
            experiment_id="exp_002"
        )

        assert result1 != result2

    def test_integer_cli_value_returns_integer(self) -> None:
        """Test that integer CLI value is returned as-is."""
        resolver = ConfigResolver()

        result = resolver.resolve_randomization_seed_for_run(
            cli_value="42",
            experiment_seed=None,
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result == 42

    def test_zero_cli_value_is_valid_and_preserved(self) -> None:
        """Seed 0 must not be treated as falsy/unset."""
        resolver = ConfigResolver()

        result = resolver.resolve_randomization_seed_for_run(
            cli_value="0",
            experiment_seed=123,
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result == 0

    def test_cli_auto_overrides_experiment_integer(self) -> None:
        """Test that CLI AUTO generates seed even when the experiment has an integer."""
        resolver = ConfigResolver()

        result = resolver.resolve_randomization_seed_for_run(
            cli_value="AUTO",
            experiment_seed=123,
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert isinstance(result, int)
        assert result != 123

    def test_inherited_auto_from_experiment_generates_seed(self) -> None:
        """Test that AUTO inherited from the experiment generates a deterministic seed."""
        resolver = ConfigResolver()

        result = resolver.resolve_randomization_seed_for_run(
            cli_value=None,
            experiment_seed="AUTO",
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert isinstance(result, int)
        assert result > 0

    def test_none_cli_and_none_experiment_returns_none(self) -> None:
        """Test that omitted CLI value and nothing configured on the experiment returns None."""
        resolver = ConfigResolver()

        result = resolver.resolve_randomization_seed_for_run(
            cli_value=None,
            experiment_seed=None,
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result is None

    def test_inherited_none_from_experiment_resolves_to_none_not_auto_generated(self) -> None:
        """Regression: inheriting an explicit None from the experiment must
        resolve to None — it must NEVER silently invent a random seed.
        This is the exact case the pre-fix inline logic in
        build_run_config_dict got wrong (`if exp_seed is None: <generate
        a seed anyway>`), which only ever looked correct before because
        None was always substituted with the "OFF" string sentinel
        before reaching this point — a sentinel that no longer exists."""
        resolver = ConfigResolver()

        result = resolver.resolve_randomization_seed_for_run(
            cli_value=None,
            experiment_seed=None,
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result is None

    def test_system_default_breaks_inheritance_even_with_experiment_seed(self) -> None:
        """system-default (FORCE_SYSTEM_DEFAULT) must resolve to None
        regardless of what the experiment has configured."""
        from src.core.special_config_values import FORCE_SYSTEM_DEFAULT

        resolver = ConfigResolver()

        result = resolver.resolve_randomization_seed_for_run(
            cli_value=FORCE_SYSTEM_DEFAULT,
            experiment_seed=42,
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result is None

    def test_invalid_cli_value_raises_value_error(self) -> None:
        """An unparseable --randomization-seed must be a usage error, never silently None."""
        resolver = ConfigResolver()

        with pytest.raises(ValueError):
            resolver.resolve_randomization_seed_for_run(
                cli_value="not-a-number",
                experiment_seed=None,
                run_id="run_001",
                experiment_id="exp_001"
            )

    def test_invalid_inherited_experiment_value_raises_value_error(self) -> None:
        """An invalid inherited experiment value must also be a usage
        error, never silently coerced to None — pre-production, no
        legacy data means every reachable experiment_seed is already
        clean, but this guards against a bug producing garbage."""
        resolver = ConfigResolver()

        with pytest.raises(ValueError):
            resolver.resolve_randomization_seed_for_run(
                cli_value=None,
                experiment_seed="not-a-number",
                run_id="run_001",
                experiment_id="exp_001"
            )

    def test_auto_case_insensitive_for_run(self) -> None:
        """Test that AUTO is case-insensitive for run-level resolution."""
        resolver = ConfigResolver()

        result1 = resolver.resolve_randomization_seed_for_run(
            cli_value="AUTO",
            experiment_seed=None,
            run_id="run_001",
            experiment_id="exp_001"
        )

        result2 = resolver.resolve_randomization_seed_for_run(
            cli_value="auto",
            experiment_seed=None,
            run_id="run_001",
            experiment_id="exp_001"
        )

        result3 = resolver.resolve_randomization_seed_for_run(
            cli_value="Auto",
            experiment_seed=None,
            run_id="run_001",
            experiment_id="exp_001"
        )

        assert result1 == result2 == result3


class TestBuildExperimentConfigDict:
    """Test cases for build_experiment_config_dict method."""

    def test_returns_dict_with_17_keys(self) -> None:
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
            "RANDOMIZATION_SEED": "42",
            "SYSTEM_PROMPT": "Test system prompt",
            "USER_PROMPT": "Test user prompt",
        }

        class MockArgs:
            randomization_seed = None
            system_prompt = None
            user_prompt = None
            url = None
            reasoning_tokens = None
            max_reasoning = None
            max_tokens = None
            reasoning = None
            repeat_penalty = None
            model_seed = None
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
            "MODEL_SEED",
            "MODEL_TEMPERATURE",
            "MODEL_TOP_K",
            "MODEL_TOP_P",
            "MODEL_VISION",
            "STRUCTURED_OUTPUTS",
            "RANDOMIZATION_SEED",
            "SYSTEM_PROMPT",
            "USER_PROMPT",
            "PROVIDER_LOCK",
            "PROVIDER_SELECTION_STRATEGY",
        }

        assert set(result.keys()) == expected_keys
        assert len(result) == 17  # 17 keys total (added MODEL_SEED, Checkpoint B)

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
            randomization_seed = None
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
            "RANDOMIZATION_SEED": "42",
            "SYSTEM_PROMPT": "test",
            "USER_PROMPT": "test",
        }

        class MockArgs:
            randomization_seed = None
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
            "RANDOMIZATION_SEED": "",
            "SYSTEM_PROMPT": "",
            "USER_PROMPT": "",
        }

        class MockArgs:
            randomization_seed = None
            system_prompt = None
            user_prompt = None
            url = None
            reasoning_tokens = None
            max_reasoning = None
            max_tokens = None
            reasoning = None
            repeat_penalty = None
            model_seed = None
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

    def test_returns_dict_with_12_keys(self) -> None:
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
            "MODEL_SEED",
            "MODEL_TEMPERATURE",
            "MODEL_TOP_K",
            "MODEL_TOP_P",
            "MODEL_VISION",
            "STRUCTURED_OUTPUTS",
            "PROVIDER",
        }

        assert set(result.keys()) == expected_keys
        assert len(result) == 12  # 12 keys total (added MODEL_SEED, Checkpoint B)

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


class TestModelSeedResolution:
    """Model Seed (MODEL_SEED) resolution — Checkpoint B. Structurally a
    plain model parameter (mirrors PROVIDER/MODEL_REPEAT_PENALTY): no
    .env fallback at variant-creation time, no AUTO state anywhere, total
    separation from RANDOMIZATION_SEED. See
    docs/status/model-seed-checkpoint-b-design.md."""

    def test_experiment_level_cli_wins_over_env(self) -> None:
        resolver = ConfigResolver()
        resolver.env_dict = {"MODEL_SEED": "99"}

        class MockArgs:
            model_seed = "42"

        result = resolver._resolve_with_force_system_default(
            MockArgs.model_seed, "MODEL_SEED", resolver._parse_int_env
        )
        assert result == "42"

    def test_experiment_level_falls_back_to_env_when_cli_absent(self) -> None:
        resolver = ConfigResolver()
        resolver.env_dict = {"MODEL_SEED": "99"}

        result = resolver._resolve_with_force_system_default(
            None, "MODEL_SEED", resolver._parse_int_env
        )
        assert result == 99

    def test_experiment_level_system_default_ignores_env(self) -> None:
        from src.core.special_config_values import FORCE_SYSTEM_DEFAULT

        resolver = ConfigResolver()
        resolver.env_dict = {"MODEL_SEED": "99"}

        result = resolver._resolve_with_force_system_default(
            FORCE_SYSTEM_DEFAULT, "MODEL_SEED", resolver._parse_int_env
        )
        assert result is None

    def test_experiment_level_nothing_configured_resolves_none(self) -> None:
        resolver = ConfigResolver()
        resolver.env_dict = {}

        result = resolver._resolve_with_force_system_default(
            None, "MODEL_SEED", resolver._parse_int_env
        )
        assert result is None

    def test_variant_level_cli_wins_over_experiment(self) -> None:
        resolver = ConfigResolver()

        class MockArgs:
            model_seed = 42

        exp_config = {"MODEL_SEED": 99}
        result = resolver._resolve_cli_or_experiment(
            MockArgs.model_seed, exp_config, "MODEL_SEED", int
        )
        assert result == 42

    def test_variant_level_inherits_from_experiment_when_cli_absent(self) -> None:
        resolver = ConfigResolver()
        exp_config = {"MODEL_SEED": 99}

        result = resolver._resolve_cli_or_experiment(
            None, exp_config, "MODEL_SEED", int
        )
        assert result == 99

    def test_variant_level_system_default_breaks_inheritance_even_with_experiment_value(self) -> None:
        """Direct analogue of Checkpoint A's
        test_system_default_breaks_inheritance_even_with_experiment_seed —
        system-default must resolve to None even when the experiment has a
        real MODEL_SEED configured."""
        from src.core.special_config_values import FORCE_SYSTEM_DEFAULT

        resolver = ConfigResolver()
        exp_config = {"MODEL_SEED": 99}

        result = resolver._resolve_cli_or_experiment(
            FORCE_SYSTEM_DEFAULT, exp_config, "MODEL_SEED", int
        )
        assert result is None

    def test_variant_level_never_consults_env(self) -> None:
        """Variant-level MODEL_SEED resolution must never fall back to
        .env — only CLI and the experiment's own frozen config."""
        resolver = ConfigResolver()
        resolver.env_dict = {"MODEL_SEED": "99"}  # must be ignored entirely
        exp_config = {}  # experiment has nothing configured either

        result = resolver._resolve_cli_or_experiment(
            None, exp_config, "MODEL_SEED", int
        )
        assert result is None

    def test_zero_preserved_at_experiment_level(self) -> None:
        resolver = ConfigResolver()
        resolver.env_dict = {}

        class MockArgs:
            model_seed = "0"

        result = resolver._resolve_with_force_system_default(
            MockArgs.model_seed, "MODEL_SEED", resolver._parse_int_env
        )
        assert result == "0"  # unparsed CLI passthrough, parsed later by build_model_config_dict's parse_int

    def test_zero_preserved_at_variant_level(self) -> None:
        resolver = ConfigResolver()
        exp_config = {}

        result = resolver._resolve_cli_or_experiment(0, exp_config, "MODEL_SEED", int)
        assert result == 0

    def test_build_experiment_config_dict_includes_model_seed(self) -> None:
        resolver = ConfigResolver()
        resolver.env_dict = {}

        class MockArgs:
            randomization_seed = None
            system_prompt = None
            user_prompt = None
            url = None
            reasoning_tokens = None
            max_reasoning = None
            max_tokens = None
            reasoning = None
            repeat_penalty = None
            model_seed = "42"
            temperature = None
            top_k = None
            top_p = None
            vision = None
            structured = None
            experiment_name = "test_exp"

        result = resolver.build_experiment_config_dict(MockArgs())
        assert result["MODEL_SEED"] == "42"

    def test_build_model_config_dict_includes_model_seed(self) -> None:
        resolver = ConfigResolver()

        class MockArgs:
            url = None
            reasoning_tokens = None
            max_reasoning = None
            max_tokens = None
            reasoning = None
            repeat_penalty = None
            model_seed = 42
            temperature = None
            top_k = None
            top_p = None
            vision = None
            structured = None
            provider = None

        class MockExperiment:
            config_json = "{}"

        result = resolver.build_model_config_dict(MockArgs(), MockExperiment())
        assert result["MODEL_SEED"] == 42

    def test_build_model_config_dict_model_seed_never_reads_randomization_seed(self) -> None:
        """Total separation: an experiment's RANDOMIZATION_SEED must never
        leak into a variant's MODEL_SEED, even if both happen to be set."""
        resolver = ConfigResolver()

        class MockArgs:
            url = None
            reasoning_tokens = None
            max_reasoning = None
            max_tokens = None
            reasoning = None
            repeat_penalty = None
            model_seed = None
            temperature = None
            top_k = None
            top_p = None
            vision = None
            structured = None
            provider = None

        class MockExperiment:
            config_json = json.dumps({"RANDOMIZATION_SEED": 7})

        result = resolver.build_model_config_dict(MockArgs(), MockExperiment())
        assert result["MODEL_SEED"] is None


class TestBuildRunConfigDict:
    """Test cases for build_run_config_dict method."""

    def test_returns_dict_with_3_keys(self) -> None:
        """Test that run config has all 3 expected keys."""
        resolver = ConfigResolver()
        resolver.env_dict = {
            "RANDOMIZATION_SEED": "42",
            "SYSTEM_PROMPT": "Test system",
            "USER_PROMPT": "Test user",
        }

        class MockArgs:
            randomization_seed = None
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = "{}"

        result = resolver.build_run_config_dict(MockArgs(), MockExperiment())

        expected_keys = {"RANDOMIZATION_SEED", "SYSTEM_PROMPT", "USER_PROMPT"}

        assert set(result.keys()) == expected_keys
        assert len(result) == 3

    def test_nothing_configured_anywhere_resolves_to_none_never_auto_generated(self) -> None:
        """Regression: build_run_config_dict never consults .env (by
        design — 'Resolution order: CLI > experiment > NULL (NO .env
        consultation)', unchanged) — and, since the 2026-08-20 seed
        vocabulary separation checkpoint, an experiment with NOTHING
        configured for RANDOMIZATION_SEED (empty config_json) must
        resolve a new run's seed to None, not silently auto-generate a
        random one. This used to pass for the wrong reason: the old
        inline logic treated "no key in experiment config" the same as
        "AUTO", auto-generating a seed regardless of .env — exactly the
        bug docs/status/known-issues.md's Planner entry and this
        checkpoint's canonical resolve_randomization_seed_for_run fixed."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOMIZATION_SEED": "AUTO"}  # must be ignored — no .env consultation

        class MockArgs:
            randomization_seed = None
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = "{}"

        result = resolver.build_run_config_dict(MockArgs(), MockExperiment())

        # Nothing configured anywhere -> None, never an invented seed.
        assert result["RANDOMIZATION_SEED"] is None

    def test_run_seed_is_per_run_unique(self) -> None:
        """Test that AUTO seed produces different values for different runs."""
        resolver = ConfigResolver()
        resolver.env_dict = {"RANDOMIZATION_SEED": "AUTO"}

        class MockArgs:
            randomization_seed = None
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = "{}"

        # Simulate two different runs, both inheriting AUTO from the experiment
        result1 = resolver.resolve_randomization_seed_for_run(
            cli_value=None,
            experiment_seed="AUTO",
            run_id="run_001",
            experiment_id="exp_001"
        )

        result2 = resolver.resolve_randomization_seed_for_run(
            cli_value=None,
            experiment_seed="AUTO",
            run_id="run_002",
            experiment_id="exp_001"
        )

        assert result1 != result2
        assert isinstance(result1, int)
        assert isinstance(result2, int)

    def test_two_runs_cli_auto_get_different_seeds(self) -> None:
        """Regression: CLI --seed AUTO must produce unique seeds per run."""
        resolver = ConfigResolver()

        class MockArgs:
            randomization_seed = "AUTO"
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = '{"RANDOMIZATION_SEED": null}'

        seed1 = resolver.build_run_config_dict(MockArgs(), MockExperiment(), run_id="run_001")["RANDOMIZATION_SEED"]
        seed2 = resolver.build_run_config_dict(MockArgs(), MockExperiment(), run_id="run_002")["RANDOMIZATION_SEED"]

        assert seed1 != seed2, f"Both runs got same seed: {seed1}"
        assert isinstance(seed1, int)
        assert isinstance(seed2, int)

    def test_two_runs_inherit_auto_get_different_seeds(self) -> None:
        """Regression: Inheriting AUTO from experiment must produce unique seeds per run."""
        resolver = ConfigResolver()

        class MockArgs:
            randomization_seed = None
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = '{"RANDOMIZATION_SEED": "AUTO"}'

        seed1 = resolver.build_run_config_dict(MockArgs(), MockExperiment(), run_id="run_001")["RANDOMIZATION_SEED"]
        seed2 = resolver.build_run_config_dict(MockArgs(), MockExperiment(), run_id="run_002")["RANDOMIZATION_SEED"]

        assert seed1 != seed2, f"Both runs got same seed: {seed1}"

    def test_seed_is_deterministic_for_same_run_id(self) -> None:
        """Reproducibility: same run_id + experiment_id must always produce same seed."""
        resolver = ConfigResolver()

        class MockArgs:
            randomization_seed = "AUTO"
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = '{}'

        seed1 = resolver.build_run_config_dict(MockArgs(), MockExperiment(), run_id="run_001")["RANDOMIZATION_SEED"]
        seed2 = resolver.build_run_config_dict(MockArgs(), MockExperiment(), run_id="run_001")["RANDOMIZATION_SEED"]

        assert seed1 == seed2, f"Same run_id produced different seeds: {seed1} vs {seed2}"

    def test_fixed_numeric_experiment_seed_propagates(self) -> None:
        """Numeric experiment seed should propagate to runs directly."""
        resolver = ConfigResolver()

        class MockArgs:
            randomization_seed = None
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = '{"RANDOMIZATION_SEED": 42}'

        config = resolver.build_run_config_dict(MockArgs(), MockExperiment(), run_id="run_001")

        assert config["RANDOMIZATION_SEED"] == 42

    def test_cli_seed_overrides_experiment_auto(self) -> None:
        """Explicit CLI seed should override experiment AUTO configuration."""
        resolver = ConfigResolver()

        class MockArgs:
            randomization_seed = 999
            system_prompt = None
            user_prompt = None

        class MockExperiment:
            experiment_id = "exp_001"
            config_json = '{"RANDOMIZATION_SEED": "AUTO"}'

        config = resolver.build_run_config_dict(MockArgs(), MockExperiment(), run_id="run_001")

        assert config["RANDOMIZATION_SEED"] == 999
