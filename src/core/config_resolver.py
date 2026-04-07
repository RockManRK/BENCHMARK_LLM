"""Configuration resolver for benchmark_llm project.

This module provides centralized configuration resolution with explicit
priority ordering: CLI > .env > system defaults > system-default.

All configuration values flow through this resolver to ensure:
- No hardcoded defaults in execution code
- Explicit configuration freeze at experiment creation
- Auditable configuration resolution
- Null-by-default for prompts (no fallback strings)

CRITICAL: Seed AUTO resolution happens at RUN_CREATION only, never at experiment level.
CRITICAL: FORCE_SYSTEM_DEFAULT means "explicitly use system default" - no fallback to .env.

ARCHITECTURAL NOTE:
- The .env file is loaded ONCE at application startup by bcllm.py (entry point)
- This module does NOT load .env - it only reads from os.environ
- All modules must assume os.environ is already populated
"""

import hashlib
from pathlib import Path
from typing import Optional

import os

from .null_semantics import FORCE_SYSTEM_DEFAULT


class ConfigResolver:
    """Centralized configuration resolver.

    Resolution order: CLI > .env > system defaults > NULL

    This resolver ensures that all configuration values follow the
    explicit priority chain, with no implicit defaults or inference.

    Attributes:
        env_dict: Cached snapshot of os.environ at time of load_env() call

    Example:
        >>> resolver = ConfigResolver()
        >>> resolver.load_env()
        >>> seed = resolver.resolve_seed(cli_value=None, env_key="RANDOM_SEED", experiment_name="exp1")
        >>> prompt = resolver.resolve_prompt(cli_value="Custom prompt", env_key="SYSTEM_PROMPT", default=None)
    """

    def __init__(self) -> None:
        """Initialize the configuration resolver.

        The env_dict starts empty and must be populated via load_env().
        """
        self.env_dict: dict[str, str] = {}

    def load_env(self) -> dict[str, str]:
        """Create a cached snapshot of current os.environ.
        
        NOTE: This does NOT load the .env file from disk.
        The .env file is loaded once at application startup by bcllm.py.
        This method only creates a cached snapshot for performance.

        Returns:
            Dictionary copy of current os.environ.

        Example:
            >>> resolver = ConfigResolver()
            >>> env_values = resolver.load_env()
            >>> print(env_values.get("RANDOM_SEED"))
        """
        # Create a cached snapshot of os.environ
        # The .env file was already loaded by bcllm.py at startup
        self.env_dict = dict(os.environ)
        return self.env_dict

    def resolve_prompt(
        self,
        cli_value: str | None,
        env_key: str,
        default: str | None = None
    ) -> str | None:
        """Resolve prompt value.

        Resolution order:
        1. CLI value (if provided and not empty)
        2. .env value (if key exists and not empty)
        3. Default (if provided)
        4. None (null-by-default)

        CRITICAL: FORCE_SYSTEM_DEFAULT means "explicitly null" - no fallback.

        Args:
            cli_value: Value from CLI flag (already parsed), or None.
            env_key: Key to look up in .env (e.g., "SYSTEM_PROMPT_TEMPLATE").
            default: Fallback default if CLI and .env both missing. Use None for null-by-default.

        Returns:
            Resolved prompt string, or None if not provided anywhere.
            Empty strings are treated as "not provided" and fall through.

        Example:
            >>> resolver = ConfigResolver()
            >>> resolver.load_env()
            >>> # CLI provided: returns CLI value
            >>> resolver.resolve_prompt("Custom prompt", "SYSTEM_PROMPT", None)
            'Custom prompt'
            >>> # CLI missing, .env has value: returns .env value
            >>> resolver.resolve_prompt(None, "SYSTEM_PROMPT", None)
            'Value from .env'
            >>> # All missing, no default: returns None
            >>> resolver.resolve_prompt(None, "NONEXISTENT_KEY", None)
            None
            >>> # CLI FORCE_SYSTEM_DEFAULT: no fallback to .env
            >>> resolver.resolve_prompt(FORCE_SYSTEM_DEFAULT, "SYSTEM_PROMPT", None)
            None
        """
        # CLI was FORCE_SYSTEM_DEFAULT → return None (no fallback)
        if cli_value is FORCE_SYSTEM_DEFAULT:
            return None
        
        # CLI provided (not None, not FORCE_SYSTEM_DEFAULT)
        if cli_value is not None and cli_value.strip():
            return cli_value.strip()

        # CLI was None (not specified) → check .env
        env_value = self.env_dict.get(env_key)
        if env_value is not None and env_value.strip():
            return env_value.strip()

        return default

    def resolve_seed(
        self,
        cli_value: str | None,
        env_key: str,
        experiment_name: str
    ) -> int | str | None:
        """Resolve seed value for experiment level (does NOT resolve AUTO).

        Resolution order:
        1. CLI value (if provided and not "AUTO")
        2. .env value (if key exists and not "AUTO")
        3. "AUTO" from CLI or .env: return "AUTO" string (NOT resolved)
        4. None (no randomization)

        CRITICAL: This method does NOT resolve AUTO to a number.
        AUTO resolution happens only in resolve_seed_for_run().
        CRITICAL: FORCE_SYSTEM_DEFAULT means "explicitly null" - no fallback.

        Args:
            cli_value: Value from CLI --seed flag (already parsed), or None.
            env_key: Key to look up in .env (e.g., "RANDOM_SEED").
            experiment_name: Experiment name for AUTO generation.

        Returns:
            Integer seed, "AUTO" string, or None for no randomization.
            If cli_value or env value is "AUTO", returns "AUTO" (not resolved).

        Example:
            >>> resolver = ConfigResolver()
            >>> resolver.load_env()
            >>> # Integer value: returns integer
            >>> resolver.resolve_seed("42", "RANDOM_SEED", "exp1")
            42
            >>> # AUTO: returns "AUTO" string (NOT resolved)
            >>> resolver.resolve_seed("AUTO", "RANDOM_SEED", "exp1")
            'AUTO'
            >>> # None: returns None
            >>> resolver.resolve_seed(None, "RANDOM_SEED", "exp1")
            None
            >>> # FORCE_SYSTEM_DEFAULT: no fallback to .env
            >>> resolver.resolve_seed(FORCE_SYSTEM_DEFAULT, "RANDOM_SEED", "exp1")
            None
        """
        def parse_seed_value(value: str) -> int | str | None:
            """Parse a seed value string.

            Returns:
                - int if value is a valid integer
                - "AUTO" if value is "AUTO" (case-insensitive)
                - None if value is empty or whitespace
            """
            if value is None or not value.strip():
                return None

            value_stripped = value.strip()

            if value_stripped.upper() == "AUTO":
                return "AUTO"

            try:
                return int(value_stripped)
            except ValueError:
                return None

        # Check CLI value first
        if cli_value is not None and cli_value is not FORCE_SYSTEM_DEFAULT:
            parsed = parse_seed_value(cli_value)
            if parsed == "AUTO":
                return "AUTO"
            if isinstance(parsed, int):
                return parsed
        
        # CLI was FORCE_SYSTEM_DEFAULT → return None (no fallback)
        if cli_value is FORCE_SYSTEM_DEFAULT:
            return None
        
        # CLI was None (not specified) → check .env
        env_value = self.env_dict.get(env_key)
        if env_value is not None:
            parsed = parse_seed_value(env_value)
            if parsed == "AUTO":
                return "AUTO"
            if isinstance(parsed, int):
                return parsed

        return None

    def resolve_seed_for_run(
        self,
        cli_value: str | None,
        env_key: str,
        run_id: str,
        experiment_id: str
    ) -> int | None:
        """Resolve seed value for RUN_CREATION (AUTO is resolved here).

        Resolution order:
        1. CLI value (if provided and not "AUTO")
        2. .env value (if key exists and not "AUTO")
        3. "AUTO" from CLI or .env: generate deterministic seed from run_id + experiment_id
        4. None (no randomization)

        CRITICAL: This is the ONLY place where AUTO is resolved to a number.

        Args:
            cli_value: Value from CLI --seed flag (already parsed), or None.
            env_key: Key to look up in .env (e.g., "RANDOM_SEED").
            run_id: Run ID for AUTO generation.
            experiment_id: Experiment ID for AUTO generation.

        Returns:
            Integer seed, or None for no randomization.
            If cli_value or env value is "AUTO", generates deterministic seed.

        Example:
            >>> resolver = ConfigResolver()
            >>> resolver.load_env()
            >>> # AUTO: generates deterministic seed from run + experiment
            >>> resolver.resolve_seed_for_run("AUTO", "RANDOM_SEED", "run_abc123", "exp_xyz789")
            <hash-based integer>
        """
        def parse_seed_value(value: str) -> int | str | None:
            """Parse a seed value string.

            Returns:
                - int if value is a valid integer
                - "AUTO" if value is "AUTO" (case-insensitive)
                - None if value is empty or whitespace
            """
            if value is None or not value.strip():
                return None

            value_stripped = value.strip()

            if value_stripped.upper() == "AUTO":
                return "AUTO"

            try:
                return int(value_stripped)
            except ValueError:
                return None

        if cli_value is not None:
            parsed = parse_seed_value(cli_value)
            if parsed == "AUTO":
                return self._generate_seed_from_run(run_id, experiment_id)
            if isinstance(parsed, int):
                return parsed

        env_value = self.env_dict.get(env_key)
        if env_value is not None:
            parsed = parse_seed_value(env_value)
            if parsed == "AUTO":
                return self._generate_seed_from_run(run_id, experiment_id)
            if isinstance(parsed, int):
                return parsed

        return None

    def _generate_seed_from_name(self, experiment_name: str) -> int:
        """Generate deterministic seed from experiment name.

        Uses SHA-256 hash of the experiment name to generate a
        deterministic, reproducible seed value.

        Args:
            experiment_name: Name of the experiment.

        Returns:
            Positive integer seed derived from hash of experiment name.
        """
        hash_bytes = hashlib.sha256(experiment_name.encode()).digest()
        seed = int.from_bytes(hash_bytes[:8], byteorder='big')
        return seed % (2**31)

    def _generate_seed_from_run(self, run_id: str, experiment_id: str) -> int:
        """Generate deterministic seed from run and experiment IDs.

        Uses SHA-256 hash of combined run_id and experiment_id to generate
        a deterministic, reproducible seed value.

        Args:
            run_id: Run identifier.
            experiment_id: Parent experiment identifier.

        Returns:
            Positive integer seed derived from hash of run_id:experiment_id.
        """
        combined = f"{experiment_id}:{run_id}"
        hash_bytes = hashlib.sha256(combined.encode()).digest()
        seed = int.from_bytes(hash_bytes[:8], byteorder='big')
        return seed % (2**31)

    def build_experiment_config_dict(self, cli_args) -> dict:
        """Build complete configuration dictionary for experiment creation.

        Includes ALL experiment-scoped keys.
        SYSTEM keys are resolved at runtime and NOT stored in experiment config.

        Resolution strategy:
        - EXPERIMENT keys (1): Resolved from .env at experiment creation
        - MODEL keys (10): Resolved from CLI/.env as defaults for model variants
        - RUN keys (3): Resolved from CLI/.env as defaults for runs

        SYSTEM keys REMOVED (resolved at system startup, not stored):
        - DATABASE_PATH
        - EXECUTION_MODE
        - LOG_FILE_PATH
        - LOG_LEVEL
        - OPENROUTER_DEBUG_ENABLED

        EXPERIMENT keys NOT stored (resolved at creation time, not persisted):
        - QUESTIONS_STATUS_ADD (used for filtering, not stored)
        - QUESTIONS_STATUS_EXCLUDE (used for filtering, not stored)

        Args:
            cli_args: Parsed CLI arguments (argparse.Namespace).

        Returns:
            Dictionary with 14 configuration keys (1 EXPERIMENT + 10 MODEL + 3 RUN).
        """
        resolved_seed = self.resolve_seed(
            cli_value=getattr(cli_args, 'seed', None),
            env_key="RUN_RESPONSES_SEED",
            experiment_name=getattr(cli_args, 'create_experiment', 'default')
        )

        return {
            # EXPERIMENT keys (1) - Resolved from .env at experiment creation
            "QUESTIONS_DATASET_PATH": self.env_dict.get("QUESTIONS_DATASET_PATH"),

            # MODEL keys (10) - Resolved from CLI/.env as defaults for model variants
            "BASE_URL": self._resolve_with_force_system_default(
                getattr(cli_args, 'url', None),
                "BASE_URL"
            ),
            "MODEL_MAX_TOKENS_REASONING": self._resolve_with_force_system_default(
                getattr(cli_args, 'reasoning_tokens', None) or getattr(cli_args, 'max_reasoning', None),
                "MODEL_MAX_TOKENS_REASONING",
                self._parse_int_env
            ),
            "MODEL_MAX_TOKENS_TOTAL": self._resolve_with_force_system_default(
                getattr(cli_args, 'max_tokens', None),
                "MODEL_MAX_TOKENS_TOTAL",
                self._parse_int_env
            ),
            "MODEL_REASONING_EFFORT": self._resolve_with_force_system_default(
                getattr(cli_args, 'reasoning', None),
                "MODEL_REASONING_EFFORT"
            ),
            "MODEL_REPEAT_PENALTY": self._resolve_with_force_system_default(
                getattr(cli_args, 'repeat_penalty', None),
                "MODEL_REPEAT_PENALTY",
                self._parse_float_env
            ),
            "MODEL_TEMPERATURE": self._resolve_with_force_system_default(
                getattr(cli_args, 'temperature', None),
                "MODEL_TEMPERATURE",
                self._parse_float_env
            ),
            "MODEL_TOP_K": self._resolve_with_force_system_default(
                getattr(cli_args, 'top_k', None),
                "MODEL_TOP_K",
                self._parse_int_env
            ),
            "MODEL_TOP_P": self._resolve_with_force_system_default(
                getattr(cli_args, 'top_p', None),
                "MODEL_TOP_P",
                self._parse_float_env
            ),
            "MODEL_VISION": self._resolve_bool_cli_or_env(getattr(cli_args, 'vision', None), "MODEL_VISION"),
            "STRUCTURED_OUTPUTS": self._resolve_bool_cli_or_env(getattr(cli_args, 'structured', None), "STRUCTURED_OUTPUTS"),

            # RUN keys (3) - Resolved from CLI/.env as defaults for runs
            "RUN_RESPONSES_SEED": resolved_seed if resolved_seed is not None else "OFF",
            "SYSTEM_PROMPT": self.resolve_prompt(
                cli_value=getattr(cli_args, 'system_prompt', None),
                env_key="SYSTEM_PROMPT",
                default=None
            ),
            "USER_PROMPT": self.resolve_prompt(
                cli_value=getattr(cli_args, 'user_prompt', None),
                env_key="USER_PROMPT",
                default=None
            ),
        }

    def _resolve_cli_or_experiment(
        self,
        cli_value: str | float | int | None,
        exp_config: dict,
        exp_key: str,
        parser=None
    ) -> str | int | float | bool | None:
        """Resolve configuration value from CLI or experiment config only.

        This method enforces the post-experiment-creation contract:
        configuration must inherit from experiment.config_json, NOT from .env.

        Resolution order:
        1. CLI value (if provided and not FORCE_SYSTEM_DEFAULT)
        2. Experiment config value (if key exists)
        3. None (system-default)

        CRITICAL: FORCE_SYSTEM_DEFAULT means "explicitly use system-default" - no fallback.

        Args:
            cli_value: Value from CLI flag, or None.
            exp_config: Experiment's config_json dictionary.
            exp_key: Key to look up in experiment config.
            parser: Optional parser function to apply to the result.

        Returns:
            Resolved configuration value, or None if not provided anywhere.
        """
        if cli_value is FORCE_SYSTEM_DEFAULT:
            return None

        if cli_value is not None:
            if parser is not None:
                return parser(cli_value)
            if isinstance(cli_value, str):
                return cli_value.strip()
            return cli_value

        exp_value = exp_config.get(exp_key)
        if exp_value is not None and parser is not None:
            return parser(exp_value)
        if exp_value is not None and isinstance(exp_value, str):
            return exp_value.strip()
        return exp_value

    def build_run_config_dict(self, cli_args, experiment) -> dict:
        """Build complete configuration dictionary for run creation.

        Includes ALL run-level keys from contract, even if null.
        Seed AUTO is resolved here (at RUN_CREATION).
        Resolution order: CLI > experiment > NULL (NO .env consultation)

        Args:
            cli_args: Parsed CLI arguments (argparse.Namespace).
            experiment: Experiment entity with config_json.

        Returns:
            Dictionary with ALL run-level configuration keys:
            - RUN_RESPONSES_SEED: int | None (AUTO resolved here)
            - SYSTEM_PROMPT: str | None
            - USER_PROMPT: str | None
        """
        import json

        exp_config = json.loads(experiment.config_json) if experiment.config_json else {}

        cli_seed = getattr(cli_args, 'seed', None)
        if cli_seed == "AUTO":
            resolved_seed = self._generate_seed_from_run("", experiment.experiment_id)
        elif cli_seed is not None and cli_seed is not FORCE_SYSTEM_DEFAULT:
            try:
                resolved_seed = int(cli_seed)
            except ValueError:
                resolved_seed = None
        elif cli_seed is FORCE_SYSTEM_DEFAULT:
            # Explicit system-default: no randomization, regardless of experiment config
            resolved_seed = None
        else:
            exp_seed = exp_config.get("RUN_RESPONSES_SEED")
            if exp_seed is None or exp_seed == "AUTO":
                resolved_seed = self._generate_seed_from_run("", experiment.experiment_id)
            elif exp_seed is not None:
                try:
                    resolved_seed = int(exp_seed)
                except ValueError:
                    resolved_seed = None
            else:
                resolved_seed = None

        resolved_system_prompt = self._resolve_cli_or_experiment(
            cli_value=getattr(cli_args, 'system_prompt', None),
            exp_config=exp_config,
            exp_key="SYSTEM_PROMPT"
        )

        resolved_user_prompt = self._resolve_cli_or_experiment(
            cli_value=getattr(cli_args, 'user_prompt', None),
            exp_config=exp_config,
            exp_key="USER_PROMPT"
        )

        return {
            "RUN_RESPONSES_SEED": resolved_seed,
            "SYSTEM_PROMPT": resolved_system_prompt,
            "USER_PROMPT": resolved_user_prompt,
        }

    def build_model_config_dict(self, cli_args, experiment) -> dict:
        """Build complete configuration dictionary for model variant creation.

        Includes ALL 10 model-level keys from contract, even if null.
        Resolution order: CLI > experiment > NULL (NO .env consultation)

        Args:
            cli_args: Parsed CLI arguments (argparse.Namespace).
            experiment: Experiment entity (for potential inheritance).

        Returns:
            Dictionary with ALL 10 model-level configuration keys:
            - BASE_URL: str | None
            - MODEL_MAX_TOKENS_REASONING: int | None
            - MODEL_MAX_TOKENS_TOTAL: int | None
            - MODEL_REASONING_EFFORT: str | None
            - MODEL_REPEAT_PENALTY: float | None
            - MODEL_TEMPERATURE: float | None
            - MODEL_TOP_K: int | None
            - MODEL_TOP_P: float | None
            - MODEL_VISION: bool | None
            - STRUCTURED_OUTPUTS: bool | None
        """
        import json

        exp_config = json.loads(experiment.config_json) if experiment.config_json else {}

        def parse_int(value: str | None) -> int | None:
            """Parse integer from string."""
            if value is None:
                return None
            try:
                return int(value)
            except ValueError:
                return None

        def parse_float(value: str | None) -> float | None:
            """Parse float from string."""
            if value is None:
                return None
            try:
                return float(value)
            except ValueError:
                return None

        return {
            "BASE_URL": self._resolve_cli_or_experiment(
                getattr(cli_args, 'url', None),
                exp_config,
                "BASE_URL"
            ),
            "MODEL_MAX_TOKENS_REASONING": self._resolve_cli_or_experiment(
                getattr(cli_args, 'reasoning_tokens', None) or getattr(cli_args, 'max_reasoning', None),
                exp_config,
                "MODEL_MAX_TOKENS_REASONING",
                parse_int
            ),
            "MODEL_MAX_TOKENS_TOTAL": self._resolve_cli_or_experiment(
                getattr(cli_args, 'max_tokens', None),
                exp_config,
                "MODEL_MAX_TOKENS_TOTAL",
                parse_int
            ),
            "MODEL_REASONING_EFFORT": self._resolve_cli_or_experiment(
                getattr(cli_args, 'reasoning', None),
                exp_config,
                "MODEL_REASONING_EFFORT"
            ),
            "MODEL_REPEAT_PENALTY": self._resolve_cli_or_experiment(
                getattr(cli_args, 'repeat_penalty', None),
                exp_config,
                "MODEL_REPEAT_PENALTY",
                parse_float
            ),
            "MODEL_TEMPERATURE": self._resolve_cli_or_experiment(
                getattr(cli_args, 'temperature', None),
                exp_config,
                "MODEL_TEMPERATURE",
                parse_float
            ),
            "MODEL_TOP_K": self._resolve_cli_or_experiment(
                getattr(cli_args, 'top_k', None),
                exp_config,
                "MODEL_TOP_K",
                parse_int
            ),
            "MODEL_TOP_P": self._resolve_cli_or_experiment(
                getattr(cli_args, 'top_p', None),
                exp_config,
                "MODEL_TOP_P",
                parse_float
            ),
            "MODEL_VISION": self._resolve_cli_or_experiment(
                getattr(cli_args, 'vision', None),
                exp_config,
                "MODEL_VISION",
                self._parse_bool_value
            ),
            "STRUCTURED_OUTPUTS": self._resolve_cli_or_experiment(
                getattr(cli_args, 'structured', None),
                exp_config,
                "STRUCTURED_OUTPUTS",
                self._parse_bool_value
            ),
        }

    def _parse_json_env(self, key: str) -> list | None:
        """Parse JSON array from environment variable.

        Args:
            key: Environment variable key.

        Returns:
            Parsed list or None if not found/invalid.
        """
        import json
        value = self.env_dict.get(key)
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    def _parse_bool_value(self, value: str | type[FORCE_SYSTEM_DEFAULT] | None) -> bool | None:
        """Parse boolean from CLI value.

        Args:
            value: String value from CLI ('true', 'false', 'system-default', or None),
                   or FORCE_SYSTEM_DEFAULT for explicit system-default from CLI.

        Returns:
            Parsed boolean or None if 'system-default' (FORCE_SYSTEM_DEFAULT) or not provided.

        Note:
            - FORCE_SYSTEM_DEFAULT represents explicit 'system-default' from CLI - returns None
            - String 'system-default' should be normalized to FORCE_SYSTEM_DEFAULT before reaching here
            - String 'none' is treated as literal string (not special)
            - Legacy string 'null' is deprecated but handled for backward compatibility
        """
        if value is FORCE_SYSTEM_DEFAULT:
            return None  # Explicit system-default from CLI
        if value is None:
            return None  # Absent flag
        if isinstance(value, str):
            if value.lower() == 'true':
                return True
            if value.lower() == 'false':
                return False
            if value.lower() == 'null':
                return None  # Legacy deprecated value, treat as system-default
        return None

    def _resolve_bool_cli_or_env(self, cli_value: str | type[FORCE_SYSTEM_DEFAULT] | None, env_key: str) -> bool | None:
        """Resolve boolean from CLI > .env.

        Args:
            cli_value: String value from CLI ('true', 'false', 'system-default', or None),
                       or FORCE_SYSTEM_DEFAULT for explicit system-default from CLI.
            env_key: Environment variable key.

        Returns:
            CLI value if provided (including False), otherwise .env value.

        Note:
            - FORCE_SYSTEM_DEFAULT means "explicitly system-default" - no fallback to .env
            - String 'system-default' should be normalized to FORCE_SYSTEM_DEFAULT before reaching here
            - Legacy string 'NULL' is deprecated but handled for backward compatibility
        """
        if cli_value is not None:
            parsed = self._parse_bool_value(cli_value)
            if parsed is not None:
                return parsed
            # If cli_value is FORCE_SYSTEM_DEFAULT, return None (no fallback)
            if cli_value is FORCE_SYSTEM_DEFAULT:
                return None
            # Handle legacy string 'NULL' (should be normalized already)
            if isinstance(cli_value, str) and cli_value.upper() == 'NULL':
                return None
        return self._parse_bool_env(env_key)

    def _parse_bool_env(self, key: str) -> bool | None:
        """Parse boolean from environment variable.

        Args:
            key: Environment variable key.

        Returns:
            Parsed boolean or None if not found/invalid.
        """
        value = self.env_dict.get(key)
        if not value:
            return None
        if value.lower() in ('true', '1', 'yes'):
            return True
        if value.lower() in ('false', '0', 'no'):
            return False
        return None

    def _parse_int_env(self, key: str) -> int | None:
        """Parse integer from environment variable.

        Args:
            key: Environment variable key.

        Returns:
            Parsed integer or None if not found/invalid.
        """
        value = self.env_dict.get(key)
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _parse_float_env(self, key: str) -> float | None:
        """Parse float from environment variable.

        Args:
            key: Environment variable key.

        Returns:
            Parsed float or None if not found/invalid.
        """
        value = self.env_dict.get(key)
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _resolve_with_force_system_default(self, cli_value, env_key, parser_func=None):
        """Resolve value with FORCE_SYSTEM_DEFAULT support.

        Resolution order:
        1. CLI value (if provided and not FORCE_SYSTEM_DEFAULT)
        2. .env value (if key exists)
        3. None (system-default)

        CRITICAL: FORCE_SYSTEM_DEFAULT means "explicitly use system-default" - no fallback to .env.

        Args:
            cli_value: Value from CLI (may be FORCE_SYSTEM_DEFAULT)
            env_key: Key to look up in .env
            parser_func: Optional parser function (e.g., _parse_int_env)

        Returns:
            CLI value if provided (and not FORCE_SYSTEM_DEFAULT), else .env value, else None

        Example:
            >>> resolver = ConfigResolver()
            >>> resolver.load_env()
            >>> # CLI provided: returns CLI value
            >>> resolver._resolve_with_force_system_default("42", "MODEL_TEMPERATURE")
            '42'
            >>> # CLI FORCE_SYSTEM_DEFAULT: no fallback to .env
            >>> resolver._resolve_with_force_system_default(FORCE_SYSTEM_DEFAULT, "MODEL_TEMPERATURE")
            None
            >>> # CLI None, .env has value: returns .env value
            >>> resolver._resolve_with_force_system_default(None, "MODEL_TEMPERATURE")
            '0.7'
        """
        # CLI was FORCE_SYSTEM_DEFAULT → return None (no fallback)
        if cli_value is FORCE_SYSTEM_DEFAULT:
            return None

        # CLI provided
        if cli_value is not None:
            return cli_value

        # CLI was None (not specified) → check .env
        env_value = self.env_dict.get(env_key)
        if env_value is not None and env_value != "":
            if parser_func:
                return parser_func(env_key)
            return env_value

        return None
