"""Configuration resolver for benchmark_llm project.

This module provides centralized configuration resolution with explicit
priority ordering: CLI > .env > system defaults > NULL.

All configuration values flow through this resolver to ensure:
- No hardcoded defaults in execution code
- Explicit configuration freeze at experiment creation
- Auditable configuration resolution
- Null-by-default for prompts (no fallback strings)
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
    ) -> int | None:
        """Resolve seed value.

        Resolution order:
        1. CLI value (if provided and not "AUTO")
        2. .env value (if key exists and not "AUTO")
        3. "AUTO" from CLI or .env: generate deterministic seed from experiment_name
        4. None (no randomization)

        Args:
            cli_value: Value from CLI --seed flag (already parsed), or None.
            env_key: Key to look up in .env (e.g., "RANDOM_SEED").
            experiment_name: Experiment name for AUTO generation.

        Returns:
            Integer seed, or None for no randomization.
            If cli_value or env value is "AUTO", generates deterministic seed from experiment_name.
            Empty strings are treated as "not provided".

        Example:
            >>> resolver = ConfigResolver()
            >>> resolver.load_env()
            >>> # Integer value: returns integer
            >>> resolver.resolve_seed("42", "RANDOM_SEED", "exp1")
            42
            >>> # AUTO: generates deterministic seed from experiment name
            >>> resolver.resolve_seed("AUTO", "RANDOM_SEED", "exp1")
            <hash-based integer>
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
                return self._generate_seed_from_name(experiment_name)
            if isinstance(parsed, int):
                return parsed

        env_value = self.env_dict.get(env_key)
        if env_value is not None:
            parsed = parse_seed_value(env_value)
            if parsed == "AUTO":
                return self._generate_seed_from_name(experiment_name)
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

    def resolve_config_dict(
        self,
        cli_args,
        env_dict: dict | None = None
    ) -> dict:
        """Build complete configuration dictionary.

        Resolves all configuration values using the priority chain:
        CLI > .env > system defaults > NULL

        Only includes keys with non-None values in the returned dict.

        Args:
            cli_args: Parsed CLI arguments (argparse.Namespace).
            env_dict: Loaded .env dictionary. If None, uses self.env_dict.

        Returns:
            Dictionary with all resolved configuration values:
            - seed: int | None (only included if provided)
            - retry_policy: str | None (only included if provided)
            - system_prompt: str | None (only included if provided)
            - user_prompt: str | None (only included if provided)

        Example:
            >>> resolver = ConfigResolver()
            >>> resolver.load_env()
            >>> args = argparse.Namespace(
            ...     seed="42",
            ...     system_prompt="Custom system",
            ...     user_prompt="Custom user",
            ...     retry_policy="exponential"
            ... )
            >>> config = resolver.resolve_config_dict(args)
            >>> print(config["seed"])
            42
        """
        if env_dict is not None:
            self.env_dict = env_dict

        experiment_name = getattr(cli_args, 'create_experiment', None) or \
                          getattr(cli_args, 'experiment_name', 'default')

        resolved_seed = self.resolve_seed(
            cli_value=getattr(cli_args, 'seed', None),
            env_key="RANDOM_SEED",
            experiment_name=experiment_name
        )

        resolved_system_prompt = self.resolve_prompt(
            cli_value=getattr(cli_args, 'system_prompt', None),
            env_key="SYSTEM_PROMPT_TEMPLATE",
            default=None
        )

        resolved_user_prompt = self.resolve_prompt(
            cli_value=getattr(cli_args, 'user_prompt', None),
            env_key="USER_PROMPT_TEMPLATE",
            default=None
        )

        resolved_retry_policy = self.resolve_prompt(
            cli_value=getattr(cli_args, 'retry_policy', None),
            env_key="RETRY_POLICY",
            default=None
        )

        result: dict = {}

        if resolved_seed is not None:
            result["seed"] = resolved_seed

        if resolved_retry_policy is not None:
            result["retry_policy"] = resolved_retry_policy

        if resolved_system_prompt is not None:
            result["system_prompt"] = resolved_system_prompt

        if resolved_user_prompt is not None:
            result["user_prompt"] = resolved_user_prompt

        return result
