"""Configuration resolver for benchmark_llm project.

This module provides centralized configuration resolution with explicit
priority ordering: CLI > .env > system defaults > NULL.

All configuration values flow through this resolver to ensure:
- No hardcoded defaults in execution code
- Explicit configuration freeze at experiment creation
- Auditable configuration resolution
- Null-by-default for prompts (no fallback strings)

CRITICAL: Seed AUTO resolution happens at RUN_CREATION only, never at experiment level.
"""

import hashlib
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import os


class ConfigResolver:
    """Centralized configuration resolver.

    Resolution order: CLI > .env > system defaults > NULL

    This resolver ensures that all configuration values follow the
    explicit priority chain, with no implicit defaults or inference.

    Attributes:
        env_dict: Loaded .env values (cached)

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

    def load_env(self, env_path: str | None = None) -> dict[str, str]:
        """Load .env file into memory.

        Args:
            env_path: Path to .env file. If None, uses project root .env.

        Returns:
            Dictionary of key-value pairs from .env file.
            Returns empty dict if file does not exist.

        Example:
            >>> resolver = ConfigResolver()
            >>> env_values = resolver.load_env("./.env")
            >>> print(env_values.get("RANDOM_SEED"))
        """
        if env_path is None:
            env_path = ".env"

        path = Path(env_path)
        if not path.exists():
            return {}

        load_dotenv(env_path, override=True)

        self.env_dict = {
            key: value
            for key, value in os.environ.items()
        }

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
        """
        if cli_value is not None and cli_value.strip():
            return cli_value.strip()

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
                return "AUTO"
            if isinstance(parsed, int):
                return parsed

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

        Includes ONLY experiment-scoped keys (14 total).
        SYSTEM keys are resolved at runtime and NOT stored in experiment config.

        Resolution strategy:
        - EXPERIMENT keys (1): Resolved from CLI/.env at experiment creation
        - MODEL keys (10): Resolved from CLI/.env as defaults for model variants
        - RUN keys (3): Resolved from CLI/.env as defaults for runs

        SYSTEM keys REMOVED (resolved at system startup, not stored):
        - DATABASE_PATH
        - EXECUTION_MODE
        - LOG_FILE_PATH
        - LOG_LEVEL
        - OPENROUTER_DEBUG_ENABLED

        TRANSIENT keys NOT persisted (used only during CLI execution):
        - DEFAULT_QUESTIONS (transient - used for question selection)
        - QUESTIONS_STATUS_ADD (transient - used for filtering)
        - QUESTIONS_STATUS_EXCLUDE (transient - used for filtering)
        - MODELS_DEFAULT_FOR_EXPERIMENTS (transient - NOT used, models added explicitly)

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
            "BASE_URL": getattr(cli_args, 'url', None) or self.env_dict.get("BASE_URL"),
            "MODEL_MAX_TOKENS_REASONING": getattr(cli_args, 'reasoning_tokens', None) or self._parse_int_env("MODEL_MAX_TOKENS_REASONING"),
            "MODEL_MAX_TOKENS_TOTAL": getattr(cli_args, 'max_tokens', None) or self._parse_int_env("MODEL_MAX_TOKENS_TOTAL"),
            "MODEL_REASONING_EFFORT": getattr(cli_args, 'reasoning', None) or self.env_dict.get("MODEL_REASONING_EFFORT"),
            "MODEL_REPEAT_PENALTY": getattr(cli_args, 'repeat_penalty', None) or self._parse_float_env("MODEL_REPEAT_PENALTY"),
            "MODEL_TEMPERATURE": getattr(cli_args, 'temperature', None) or self._parse_float_env("MODEL_TEMPERATURE"),
            "MODEL_TOP_K": getattr(cli_args, 'top_k', None) or self._parse_int_env("MODEL_TOP_K"),
            "MODEL_TOP_P": getattr(cli_args, 'top_p', None) or self._parse_float_env("MODEL_TOP_P"),
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

    def build_run_config_dict(self, cli_args, experiment) -> dict:
        """Build complete configuration dictionary for run creation.

        Includes ALL run-level keys from contract, even if null.
        Seed AUTO is resolved here (at RUN_CREATION).

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

        resolved_seed = self.resolve_seed_for_run(
            cli_value=getattr(cli_args, 'seed', None),
            env_key="RUN_RESPONSES_SEED",
            run_id="",
            experiment_id=experiment.experiment_id
        )

        resolved_system_prompt = self.resolve_prompt(
            cli_value=getattr(cli_args, 'system_prompt', None),
            env_key="SYSTEM_PROMPT",
            default=exp_config.get("SYSTEM_PROMPT")
        )

        resolved_user_prompt = self.resolve_prompt(
            cli_value=getattr(cli_args, 'user_prompt', None),
            env_key="USER_PROMPT",
            default=exp_config.get("USER_PROMPT")
        )

        return {
            "RUN_RESPONSES_SEED": resolved_seed,
            "SYSTEM_PROMPT": resolved_system_prompt,
            "USER_PROMPT": resolved_user_prompt,
        }

    def build_model_config_dict(self, cli_args, experiment) -> dict:
        """Build complete configuration dictionary for model variant creation.

        Includes ALL 10 model-level keys from contract, even if null.
        Resolution order: CLI > .env > experiment > NULL

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

        def resolve_cli_or_env(cli_value: str | float | int | None, env_key: str, default=None):
            """Resolve value from CLI > .env > default."""
            if cli_value is not None:
                if isinstance(cli_value, (float, int)):
                    return str(cli_value)
                if cli_value.strip():
                    return cli_value.strip()
            env_value = self.env_dict.get(env_key)
            if env_value is not None and env_value.strip():
                return env_value.strip()
            return default

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
            "BASE_URL": resolve_cli_or_env(
                getattr(cli_args, 'url', None),
                "BASE_URL"
            ),
            "MODEL_MAX_TOKENS_REASONING": parse_int(resolve_cli_or_env(
                getattr(cli_args, 'reasoning_tokens', None),
                "MODEL_MAX_TOKENS_REASONING"
            )),
            "MODEL_MAX_TOKENS_TOTAL": parse_int(resolve_cli_or_env(
                getattr(cli_args, 'max_tokens', None),
                "MODEL_MAX_TOKENS_TOTAL"
            )),
            "MODEL_REASONING_EFFORT": resolve_cli_or_env(
                getattr(cli_args, 'reasoning', None),
                "MODEL_REASONING_EFFORT"
            ),
            "MODEL_REPEAT_PENALTY": parse_float(resolve_cli_or_env(
                getattr(cli_args, 'repeat_penalty', None),
                "MODEL_REPEAT_PENALTY"
            )),
            "MODEL_TEMPERATURE": parse_float(resolve_cli_or_env(
                getattr(cli_args, 'temperature', None),
                "MODEL_TEMPERATURE"
            )),
            "MODEL_TOP_K": parse_int(resolve_cli_or_env(
                getattr(cli_args, 'top_k', None),
                "MODEL_TOP_K"
            )),
            "MODEL_TOP_P": parse_float(resolve_cli_or_env(
                getattr(cli_args, 'top_p', None),
                "MODEL_TOP_P"
            )),
            "MODEL_VISION": self._resolve_bool_cli_or_env(getattr(cli_args, 'vision', None), "MODEL_VISION"),
            "STRUCTURED_OUTPUTS": self._resolve_bool_cli_or_env(getattr(cli_args, 'structured', None), "STRUCTURED_OUTPUTS"),
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

    def _parse_bool_value(self, value: str | None) -> bool | None:
        """Parse boolean from CLI value.

        Args:
            value: String value from CLI ('true', 'false', 'NULL').

        Returns:
            Parsed boolean or None if 'NULL' or not provided.
        """
        if value is None:
            return None
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        if value.upper() == 'NULL':
            return None
        return None

    def _resolve_bool_cli_or_env(self, cli_value: str | None, env_key: str) -> bool | None:
        """Resolve boolean from CLI > .env.

        Args:
            cli_value: String value from CLI ('true', 'false', 'NULL', or None).
            env_key: Environment variable key.

        Returns:
            CLI value if provided (including False), otherwise .env value.
        """
        if cli_value is not None:
            parsed = self._parse_bool_value(cli_value)
            if parsed is not None:
                return parsed
            if cli_value.upper() == 'NULL':
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
