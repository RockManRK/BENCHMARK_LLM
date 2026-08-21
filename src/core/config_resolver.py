"""Configuration resolver for benchmark_llm project.

This module provides centralized configuration resolution with explicit
priority ordering: CLI > .env > system defaults > system-default.

All configuration values flow through this resolver to ensure:
- No hardcoded defaults in execution code
- Explicit configuration freeze at experiment creation
- Auditable configuration resolution
- Null-by-default for prompts (no fallback strings)

CRITICAL: Randomization Seed AUTO resolution happens at RUN_CREATION only, never at experiment level.
CRITICAL: FORCE_SYSTEM_DEFAULT means "explicitly use system default" - no fallback to .env.

ARCHITECTURAL NOTE:
- The .env file is loaded ONCE at application startup by bcllm.py (entry point)
- This module does NOT load .env - it only reads from os.environ
- All modules must assume os.environ is already populated
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

import os

from .special_config_values import FORCE_SYSTEM_DEFAULT
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event
from src.utils.logging_config import get_logger


def parse_randomization_seed_strict(value: str | int | None) -> int | str | None:
    """Parse a --randomization-seed / RANDOMIZATION_SEED value strictly —
    the single shared implementation for both experiment-level
    (`resolve_randomization_seed`) and run-level
    (`resolve_randomization_seed_for_run`) resolution.

    Renamed 2026-08-20 (seed vocabulary separation checkpoint) from
    `parse_seed_value_strict` — this parses ONLY the Randomization Seed
    (the AnswerRandomizer's seed, controls presented option order). It
    is not used for, and must never be reused by, Model Seed (the
    seed sent to the API for inference) — Model Seed has no AUTO concept
    and uses `parse_int_or_system_default` instead, the same generic
    parser every other model-level integer flag uses.

    `value` is usually a string (from argparse or the experiment's own
    frozen config), but an already-resolved `int` is accepted and passed
    through unchanged too — some callers (e.g. programmatic/test
    callers, not the real CLI) build the config dict with an already-int
    seed rather than a CLI string.

    Returns:
        - `None` if `value` is `None` or empty/whitespace-only (means
          "not specified" — callers decide what that implies).
        - `"AUTO"` if `value` is `'AUTO'` (case-insensitive). `AUTO` is
          only ever valid at the Experiment level — callers resolving a
          Run's seed must reject it if it somehow reaches them already
          resolved as a Run value (it must never be persisted on a Run).
        - `int` if `value` parses as an integer, or is already one (`0`
          and negative values are valid).

    Raises:
        ValueError: for any other, non-empty, unparseable text (or a
            value that's neither `str` nor `int`) — including the
            retired textual sentinels `"OFF"`/`"NULL"`/`"NONE"` (never
            valid input; a real seed is representable only as `None`,
            an integer, or, at the Experiment level only, `"AUTO"`).
            Callers MUST surface this as a usage error, never swallow it
            back into `None`.
    """
    if value is None:
        return None

    if isinstance(value, int):
        return value

    if not isinstance(value, str):
        raise ValueError(
            f"Invalid randomization seed value: {value!r}. Expected an integer, 'AUTO', 'system-default', or empty."
        )

    if not value.strip():
        return None

    stripped = value.strip()

    if stripped.upper() == "AUTO":
        return "AUTO"

    try:
        return int(stripped)
    except ValueError:
        raise ValueError(
            f"Invalid randomization seed value: {value!r}. Expected an integer, 'AUTO', 'system-default', or empty."
        )


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
        >>> seed = resolver.resolve_randomization_seed(cli_value=None, env_key="RANDOMIZATION_SEED", experiment_name="exp1")
        >>> prompt = resolver.resolve_prompt(cli_value="Custom prompt", env_key="SYSTEM_PROMPT", default=None)
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize the configuration resolver.

        The env_dict starts empty and must be populated via load_env().

        Args:
            logger: Optional logger instance. If not provided, uses
                get_logger('core.config_resolver'). Used only for
                DETAILED-tier observability events (CONFIG_RESOLVED,
                INHERITANCE_DECISION) — see
                docs/status/checkpoint-c-logging-observability-design.md.
        """
        self.env_dict: dict[str, str] = {}
        self._logger = logger or get_logger('core.config_resolver')

    def _emit_system_default_applied(self, cli_args, *, scope: str, fields: dict[str, str]) -> None:
        """Emit SYSTEM_DEFAULT_APPLIED (DETAILED-tier) listing which
        config keys had `system-default` on the CLI for this
        creation action — `fields` maps config key -> cli_args attribute
        name. Never raises; a missing attribute is simply not flagged.
        """
        applied = [
            config_key
            for config_key, attr_name in fields.items()
            if getattr(cli_args, attr_name, None) is FORCE_SYSTEM_DEFAULT
        ]
        if applied:
            emit_event(
                self._logger, Event.SYSTEM_DEFAULT_APPLIED, level=logging.DEBUG,
                scope=scope, fields=applied,
            )

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
            >>> print(env_values.get("RANDOMIZATION_SEED"))
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

    def resolve_randomization_seed(
        self,
        cli_value: str | None,
        env_key: str,
        experiment_name: str
    ) -> int | str | None:
        """Resolve Randomization Seed for experiment level (does NOT
        resolve AUTO). Renamed 2026-08-20 from `resolve_seed`.

        Resolution order:
        1. CLI value (if provided and not "AUTO")
        2. .env value (if key exists and not "AUTO")
        3. "AUTO" from CLI or .env: return "AUTO" string (NOT resolved)
        4. None (no randomization)

        CRITICAL: This method does NOT resolve AUTO to a number.
        AUTO resolution happens only in resolve_randomization_seed_for_run(),
        once, at Run creation.
        CRITICAL: FORCE_SYSTEM_DEFAULT means "explicitly null" - no fallback.

        Args:
            cli_value: Value from CLI --randomization-seed flag (already
                parsed), or None.
            env_key: Key to look up in .env — "RANDOMIZATION_SEED" in
                production; kept as a parameter for testability.
            experiment_name: Experiment name (unused by this method
                directly; kept for call-site symmetry with the run-level
                resolver, which needs run_id/experiment_id for AUTO
                generation — experiment-level resolution never generates
                a number, so it needs no id of its own).

        Returns:
            Integer seed, "AUTO" string, or None for no randomization.
            If cli_value or env value is "AUTO", returns "AUTO" (not resolved).

        Example:
            >>> resolver = ConfigResolver()
            >>> resolver.load_env()
            >>> # Integer value: returns integer
            >>> resolver.resolve_randomization_seed("42", "RANDOMIZATION_SEED", "exp1")
            42
            >>> # AUTO: returns "AUTO" string (NOT resolved)
            >>> resolver.resolve_randomization_seed("AUTO", "RANDOMIZATION_SEED", "exp1")
            'AUTO'
            >>> # None: returns None
            >>> resolver.resolve_randomization_seed(None, "RANDOMIZATION_SEED", "exp1")
            None
            >>> # FORCE_SYSTEM_DEFAULT: no fallback to .env
            >>> resolver.resolve_randomization_seed(FORCE_SYSTEM_DEFAULT, "RANDOMIZATION_SEED", "exp1")
            None
        """
        # Check CLI value first
        if cli_value is not None and cli_value is not FORCE_SYSTEM_DEFAULT:
            parsed = parse_randomization_seed_strict(cli_value)
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
            parsed = parse_randomization_seed_strict(env_value)
            if parsed == "AUTO":
                return "AUTO"
            if isinstance(parsed, int):
                return parsed

        return None

    def resolve_randomization_seed_for_run(
        self,
        cli_value: str | int | None,
        experiment_seed: str | int | None,
        run_id: str,
        experiment_id: str,
    ) -> int | None:
        """The single canonical resolution for a Run's RANDOMIZATION_SEED
        — the only place AUTO is ever resolved to a number, and the only
        method `build_run_config_dict` delegates to for this (no more
        inline duplicate logic there).

        Renamed and re-scoped 2026-08-20 from `resolve_seed_for_run`,
        which took an `env_key`/consulted `self.env_dict` — WRONG for
        run-level resolution, which must NEVER consult `.env` (only CLI
        and the frozen experiment config; see
        `docs/contracts/configuration-hierarchy.md`'s "Run configuration
        is frozen at creation" and "no .env consultation after
        experiment creation"). That mismatch is exactly why this method
        had zero production callers before this rename —
        `build_run_config_dict` needed inheritance from the *experiment*,
        not `.env`, so it grew its own separate, inline copy instead of
        ever calling this one. This version takes the experiment's
        already-resolved seed value directly, not an env_key.

        Resolution order:
        1. `cli_value` provided (not None, not FORCE_SYSTEM_DEFAULT):
           parse strictly; "AUTO" resolves to a fresh deterministic
           integer; otherwise use the integer (including 0) as-is.
        2. `cli_value` is FORCE_SYSTEM_DEFAULT (system-default): break
           inheritance entirely, resolve to None — regardless of what
           the experiment has configured.
        3. `cli_value` is None (flag omitted): inherit `experiment_seed`.
           - `experiment_seed` is None (or missing): resolve to None —
             inheriting "nothing configured" must never invent a seed.
           - `experiment_seed` is "AUTO": resolve to a fresh
             deterministic integer (the ONLY place AUTO ever becomes a
             number — it can never reach a persisted Run as the string
             "AUTO").
           - `experiment_seed` is an int (or int-parseable string): use
             it as-is.
        4. Any unparseable text, in `cli_value` or in `experiment_seed`,
           raises ValueError — a usage error the caller must surface,
           never silently coerced to None.

        Args:
            cli_value: Value from CLI --randomization-seed flag (already
                parsed by argparse to str, int, FORCE_SYSTEM_DEFAULT, or
                None), or None if the flag was omitted.
            experiment_seed: The experiment's own resolved
                RANDOMIZATION_SEED value (int, "AUTO", or None) — read
                directly from the experiment's frozen config_json by the
                caller; this method never reads `.env` or the DB itself.
            run_id: Run ID for AUTO generation.
            experiment_id: Experiment ID for AUTO generation.

        Returns:
            int | None — never "AUTO", never any other string.

        Example:
            >>> resolver = ConfigResolver()
            >>> # AUTO inherited from experiment: generates deterministic seed
            >>> resolver.resolve_randomization_seed_for_run(None, "AUTO", "run_abc123", "exp_xyz789")
            <hash-based integer>
            >>> # system-default breaks inheritance even if experiment has a seed
            >>> resolver.resolve_randomization_seed_for_run(FORCE_SYSTEM_DEFAULT, 42, "run_abc123", "exp_xyz789")

            >>> # nothing configured anywhere: None, not an invented seed
            >>> resolver.resolve_randomization_seed_for_run(None, None, "run_abc123", "exp_xyz789")

        """
        if cli_value is FORCE_SYSTEM_DEFAULT:
            return None

        if cli_value is not None:
            parsed = parse_randomization_seed_strict(cli_value)
            if parsed == "AUTO":
                resolved = self._generate_randomization_seed_from_run(run_id, experiment_id)
                emit_event(
                    self._logger, Event.INHERITANCE_DECISION, level=logging.DEBUG,
                    run_id=run_id, experiment_id=experiment_id, key="RANDOMIZATION_SEED",
                    source="cli_auto", resolved_value=resolved,
                )
                return resolved
            return parsed  # int, including 0

        # cli_value omitted -> inherit from the experiment
        if experiment_seed is None:
            return None

        parsed = parse_randomization_seed_strict(experiment_seed)
        if parsed == "AUTO":
            resolved = self._generate_randomization_seed_from_run(run_id, experiment_id)
            emit_event(
                self._logger, Event.INHERITANCE_DECISION, level=logging.DEBUG,
                run_id=run_id, experiment_id=experiment_id, key="RANDOMIZATION_SEED",
                source="experiment_auto", resolved_value=resolved,
            )
            return resolved
        return parsed  # int, including 0

    def _generate_randomization_seed_from_run(self, run_id: str, experiment_id: str) -> int:
        """Generate deterministic Randomization Seed from run and
        experiment IDs. Renamed 2026-08-20 from `_generate_seed_from_run`.

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

    def resolve_provider_lock(
        self,
        cli_value: str | None,
        env_key: str = "AUTO_PROVIDER_LOCK",
        default: bool = False
    ) -> bool | None | type[FORCE_SYSTEM_DEFAULT]:
        """Resolve provider lock setting.

        Resolution order:
        1. CLI value (if provided and not FORCE_SYSTEM_DEFAULT)
        2. .env value (AUTO_PROVIDER_LOCK)
        3. Default (false)

        CRITICAL: FORCE_SYSTEM_DEFAULT means "explicitly false" - no fallback to .env.

        Args:
            cli_value: CLI value (may be FORCE_SYSTEM_DEFAULT for 'system-default' input).
            env_key: Environment variable key for .env lookup.
            default: Default value if not specified anywhere.

        Returns:
            True if lock enabled, False if disabled, FORCE_SYSTEM_DEFAULT for explicit system-default.
        """
        # CLI was FORCE_SYSTEM_DEFAULT → return FORCE_SYSTEM_DEFAULT (no fallback)
        if cli_value is FORCE_SYSTEM_DEFAULT:
            return FORCE_SYSTEM_DEFAULT

        # CLI provided (not None, not FORCE_SYSTEM_DEFAULT)
        if cli_value is not None:
            parsed = self._parse_bool_value(cli_value)
            if parsed is not None:
                return parsed
            # If parsing failed, fall through to .env

        # CLI was None (not specified) → check .env
        env_value = self.env_dict.get(env_key)
        if env_value is not None:
            parsed = self._parse_bool_value(env_value)
            if parsed is not None:
                return parsed

        return default

    def resolve_provider_selection_strategy(
        self,
        env_key: str = "PROVIDER_SELECTION_STRATEGY",
        default: str = "first"
    ) -> str:
        """Resolve provider selection strategy.

        Resolution order:
        1. .env value (PROVIDER_SELECTION_STRATEGY)
        2. Default ("first")

        Valid strategies: "first", "cheapest", "fastest", "lowest-latency"

        Args:
            env_key: Environment variable key for .env lookup.
            default: Default strategy name if not specified.

        Returns:
            Strategy name: "first", "cheapest", "fastest", or "lowest-latency".
        """
        env_value = self.env_dict.get(env_key)
        if env_value and env_value.strip():
            return env_value.strip().lower()
        return default

    def _resolve_reasoning_pair(
        self,
        cli_effort,
        cli_tokens,
        resolved_effort,
        resolved_tokens,
    ) -> tuple:
        """Apply reasoning mode-suppression on top of each field's own,
        already-independently-resolved value (system-default/.env/
        experiment-inheritance — computed by the caller via
        `_resolve_with_force_system_default`/`_resolve_cli_or_experiment`,
        unchanged).

        OpenRouter's `reasoning` object accepts only ONE of `effort`/
        `max_tokens` — see docs/Manuais_Diversos/openrouterdocs/reasoning_tokens.md
        ("One of the following (not both)"). A same-layer conflict (both
        concretely set on the SAME --create-experiment/--add-model
        command) is rejected as a usage error (exit 2) before this is ever
        called — see src/cli/commands/{model,experiment}.py's command
        bodies. This method handles the remaining case: a concrete value
        for one field at THIS layer combined with an inherited value for
        the OTHER field from a parent layer.

        Mode-suppression rule (user decision, 2026-08-21):
        - A concrete effort value (including 'none') is a complete mode
          selection — it suppresses ANY inherited/resolved budget
          (max_tokens), even one that would otherwise be validly
          inherited.
        - A concrete (positive — enforced at CLI parse time, never 0 or
          negative by the time this runs) tokens value is equally a
          complete mode selection — it suppresses ANY inherited/resolved
          effort.
        - `system-default` on either field is NOT a mode selection — it
          only clears THAT field at this layer; it does not suppress the
          sibling field's own, independent resolution. (Already true of
          `resolved_effort`/`resolved_tokens` as passed in — this method
          only adds the concrete-value suppression on top.)
        - Absent (not passed at all) on either field means "no opinion at
          this layer" for THAT field alone — it does not trigger
          suppression of the sibling.

        Args:
            cli_effort: The raw CLI value for --reasoning (None,
                FORCE_SYSTEM_DEFAULT, or a concrete string) — used only to
                classify "is this field concretely set at this layer",
                never re-resolved here.
            cli_tokens: The raw CLI value for --reasoning-tokens, same
                shape.
            resolved_effort: MODEL_REASONING_EFFORT already resolved by
                the caller (system-default/.env/experiment fallback
                already applied).
            resolved_tokens: MODEL_MAX_TOKENS_REASONING already resolved
                the same way.

        Returns:
            (effort, tokens) — never both non-None.
        """
        effort_is_concrete = cli_effort is not None and cli_effort is not FORCE_SYSTEM_DEFAULT
        tokens_is_concrete = cli_tokens is not None and cli_tokens is not FORCE_SYSTEM_DEFAULT

        if effort_is_concrete:
            return resolved_effort, None
        if tokens_is_concrete:
            return None, resolved_tokens
        return resolved_effort, resolved_tokens

    def build_experiment_config_dict(self, cli_args) -> dict:
        """Build complete configuration dictionary for experiment creation.

        Includes ALL experiment-scoped keys.
        SYSTEM keys are resolved at runtime and NOT stored in experiment config.

        Resolution strategy:
        - EXPERIMENT keys (1): Resolved from .env at experiment creation
        - MODEL keys (11): Resolved from CLI/.env as defaults for model variants
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
            Dictionary with 16 configuration keys (3 EXPERIMENT + 10 MODEL + 3 RUN).
        """
        resolved_randomization_seed = self.resolve_randomization_seed(
            cli_value=getattr(cli_args, 'randomization_seed', None),
            env_key="RANDOMIZATION_SEED",
            experiment_name=getattr(cli_args, 'create_experiment', 'default')
        )

        # Resolve PROVIDER_LOCK from CLI > .env > default
        resolved_provider_lock = self.resolve_provider_lock(
            cli_value=getattr(cli_args, 'provider_lock', None),
            env_key="AUTO_PROVIDER_LOCK",
            default=False
        )

        # Resolve PROVIDER_SELECTION_STRATEGY from .env > default
        resolved_strategy = self.resolve_provider_selection_strategy(
            env_key="PROVIDER_SELECTION_STRATEGY",
            default="first"
        )

        # Reasoning effort/tokens are resolved together, not independently
        # — see _resolve_reasoning_pair's docstring for the mode-
        # suppression rule (a concrete value for one field suppresses the
        # OTHER field's inheritance; system-default only clears its own
        # field). --max-reasoning removed 2026-08-21: it was a true,
        # undocumented synonym of --reasoning-tokens (identical help text,
        # fed the exact same MODEL_MAX_TOKENS_REASONING key via a
        # since-removed `or` fallback that also silently discarded a
        # legitimate `0`/system-default value — see known-issues.md).
        _resolved_reasoning_effort = self._resolve_with_force_system_default(
            getattr(cli_args, 'reasoning', None),
            "MODEL_REASONING_EFFORT"
        )
        _resolved_reasoning_tokens = self._resolve_with_force_system_default(
            getattr(cli_args, 'reasoning_tokens', None),
            "MODEL_MAX_TOKENS_REASONING",
            self._parse_int_env
        )
        _resolved_reasoning_effort, _resolved_reasoning_tokens = self._resolve_reasoning_pair(
            getattr(cli_args, 'reasoning', None),
            getattr(cli_args, 'reasoning_tokens', None),
            _resolved_reasoning_effort,
            _resolved_reasoning_tokens,
        )
        # _resolve_reasoning_pair only suppresses the sibling field when
        # THIS layer's CLI value is itself concrete — it has no opinion
        # when neither --reasoning nor --reasoning-tokens was passed at
        # all, since then both fields independently fall through to their
        # own fallback. At experiment-creation time that fallback is
        # .env, and .env can genuinely have BOTH MODEL_REASONING_EFFORT
        # and MODEL_MAX_TOKENS_REASONING set (nothing enforces exclusivity
        # in a plain .env file) — the CLI's own same-layer conflict check
        # (src/cli/commands/experiment.py) never sees this, since it only
        # inspects the raw CLI values, not .env. Caught here instead,
        # once, at the one point where .env is actually consulted (model-
        # level --add-model never reads .env — see build_model_config_dict
        # — so a NEW experiment created via this path can never hand a
        # model_variant two live reasoning keys at once; only a
        # pre-fix/historical experiment could, and that residual case is
        # deliberately left to the existing defense-in-depth: the payload
        # builder's priority fallback plus Event.REASONING_CONFLICT — see
        # docs/status/known-issues.md, 2026-08-21, Essence Guardian
        # finding).
        if _resolved_reasoning_effort is not None and _resolved_reasoning_tokens is not None:
            raise ValueError(
                "Both MODEL_REASONING_EFFORT and MODEL_MAX_TOKENS_REASONING are "
                "set in .env (or one via .env, one via CLI) — OpenRouter's "
                "reasoning object accepts only one of effort/max_tokens. Pass "
                "--reasoning or --reasoning-tokens explicitly (with the other "
                "as system-default) to resolve which one applies, or clear one "
                "of MODEL_REASONING_EFFORT/MODEL_MAX_TOKENS_REASONING in .env."
            )

        resolved = {
            # EXPERIMENT keys (3) - Resolved from .env at experiment creation
            "QUESTIONS_DATASET_PATH": self.env_dict.get("QUESTIONS_DATASET_PATH"),
            "PROVIDER_LOCK": resolved_provider_lock if resolved_provider_lock is not FORCE_SYSTEM_DEFAULT else None,
            "PROVIDER_SELECTION_STRATEGY": resolved_strategy,

            # MODEL keys (11) - Resolved from CLI/.env as defaults for model variants
            "BASE_URL": self._resolve_with_force_system_default(
                getattr(cli_args, 'url', None),
                "BASE_URL"
            ),
            "MODEL_MAX_TOKENS_REASONING": _resolved_reasoning_tokens,
            "MODEL_MAX_TOKENS_TOTAL": self._resolve_with_force_system_default(
                getattr(cli_args, 'max_tokens', None),
                "MODEL_MAX_TOKENS_TOTAL",
                self._parse_int_env
            ),
            "MODEL_REASONING_EFFORT": _resolved_reasoning_effort,
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
            # Model Seed — sent as the API request's "seed" field. Belongs
            # to Experiment and model_variant, never to Run. No AUTO
            # semantics (unlike RANDOMIZATION_SEED below). Never affects
            # AnswerRandomizer. See
            # docs/status/model-seed-checkpoint-b-design.md.
            "MODEL_SEED": self._resolve_with_force_system_default(
                getattr(cli_args, 'model_seed', None),
                "MODEL_SEED",
                self._parse_int_env
            ),

            # RUN keys (3) - Resolved from CLI/.env as defaults for runs
            # Real None (JSON null) means "no randomization" — no textual
            # sentinel. "AUTO" (the string) is the only special value
            # ever stored here; resolved to a concrete int only once, at
            # Run creation (resolve_randomization_seed_for_run).
            "RANDOMIZATION_SEED": resolved_randomization_seed,
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

        emit_event(
            self._logger, Event.CONFIG_RESOLVED, level=logging.DEBUG,
            scope="experiment", experiment_name=getattr(cli_args, 'create_experiment', None),
            resolved=resolved,
        )
        self._emit_system_default_applied(cli_args, scope="experiment", fields={
            "BASE_URL": "url",
            "MODEL_MAX_TOKENS_REASONING": "reasoning_tokens",
            "MODEL_MAX_TOKENS_TOTAL": "max_tokens",
            "MODEL_REASONING_EFFORT": "reasoning",
            "MODEL_REPEAT_PENALTY": "repeat_penalty",
            "MODEL_SEED": "model_seed",
            "MODEL_TEMPERATURE": "temperature",
            "MODEL_TOP_K": "top_k",
            "MODEL_TOP_P": "top_p",
        })

        return resolved

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

    def build_run_config_dict(self, cli_args, experiment, run_id: str = "") -> dict:
        """Build complete configuration dictionary for run creation.

        Includes ALL run-level keys from contract, even if null.
        Randomization Seed AUTO is resolved here (at RUN_CREATION) — see
        resolve_randomization_seed_for_run, the single canonical
        implementation this delegates to (no inline duplicate logic here
        anymore, as of the 2026-08-20 seed vocabulary separation
        checkpoint).
        Resolution order: CLI > experiment > NULL (NO .env consultation)

        Args:
            cli_args: Parsed CLI arguments (argparse.Namespace).
            experiment: Experiment entity with config_json.
            run_id: Run identifier for AUTO seed generation.

        Returns:
            Dictionary with ALL run-level configuration keys:
            - RANDOMIZATION_SEED: int | None (AUTO resolved here)
            - SYSTEM_PROMPT: str | None
            - USER_PROMPT: str | None
        """
        import json

        exp_config = json.loads(experiment.config_json) if experiment.config_json else {}

        resolved_randomization_seed = self.resolve_randomization_seed_for_run(
            cli_value=getattr(cli_args, 'randomization_seed', None),
            experiment_seed=exp_config.get("RANDOMIZATION_SEED"),
            run_id=run_id,
            experiment_id=experiment.experiment_id,
        )

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

        resolved = {
            "RANDOMIZATION_SEED": resolved_randomization_seed,
            "SYSTEM_PROMPT": resolved_system_prompt,
            "USER_PROMPT": resolved_user_prompt,
        }

        emit_event(
            self._logger, Event.CONFIG_RESOLVED, level=logging.DEBUG,
            scope="run", run_id=run_id, experiment_id=getattr(experiment, 'experiment_id', None),
            resolved=resolved,
        )
        self._emit_system_default_applied(cli_args, scope="run", fields={
            "RANDOMIZATION_SEED": "randomization_seed",
            "SYSTEM_PROMPT": "system_prompt",
            "USER_PROMPT": "user_prompt",
        })

        return resolved

    def build_model_config_dict(self, cli_args, experiment) -> dict:
        """Build complete configuration dictionary for model variant creation.

        Includes ALL 12 model-level keys from contract, even if null.
        Resolution order: CLI > experiment > NULL (NO .env consultation)

        Args:
            cli_args: Parsed CLI arguments (argparse.Namespace).
            experiment: Experiment entity (for potential inheritance).

        Returns:
            Dictionary with ALL 12 model-level configuration keys:
            - BASE_URL: str | None
            - MODEL_MAX_TOKENS_REASONING: int | None
            - MODEL_MAX_TOKENS_TOTAL: int | None
            - MODEL_REASONING_EFFORT: str | None
            - MODEL_REPEAT_PENALTY: float | None
            - MODEL_SEED: int | None (sent as the API request's "seed"
              field; distinct from RANDOMIZATION_SEED, which never appears
              here — see docs/status/model-seed-checkpoint-b-design.md)
            - MODEL_TEMPERATURE: float | None
            - MODEL_TOP_K: int | None
            - MODEL_TOP_P: float | None
            - MODEL_VISION: bool | None
            - STRUCTURED_OUTPUTS: bool | None
            - PROVIDER: str | None
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

        # Reasoning effort/tokens resolved together — see
        # _resolve_reasoning_pair's docstring (mode-suppression rule).
        # --max-reasoning removed 2026-08-21 (true synonym of
        # --reasoning-tokens, see known-issues.md).
        _resolved_reasoning_effort = self._resolve_cli_or_experiment(
            getattr(cli_args, 'reasoning', None),
            exp_config,
            "MODEL_REASONING_EFFORT"
        )
        _resolved_reasoning_tokens = self._resolve_cli_or_experiment(
            getattr(cli_args, 'reasoning_tokens', None),
            exp_config,
            "MODEL_MAX_TOKENS_REASONING",
            parse_int
        )
        _resolved_reasoning_effort, _resolved_reasoning_tokens = self._resolve_reasoning_pair(
            getattr(cli_args, 'reasoning', None),
            getattr(cli_args, 'reasoning_tokens', None),
            _resolved_reasoning_effort,
            _resolved_reasoning_tokens,
        )

        resolved = {
            "BASE_URL": self._resolve_cli_or_experiment(
                getattr(cli_args, 'url', None),
                exp_config,
                "BASE_URL"
            ),
            "MODEL_MAX_TOKENS_REASONING": _resolved_reasoning_tokens,
            "MODEL_MAX_TOKENS_TOTAL": self._resolve_cli_or_experiment(
                getattr(cli_args, 'max_tokens', None),
                exp_config,
                "MODEL_MAX_TOKENS_TOTAL",
                parse_int
            ),
            "MODEL_REASONING_EFFORT": _resolved_reasoning_effort,
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
            "PROVIDER": self._resolve_cli_or_experiment(
                getattr(cli_args, 'provider', None),
                exp_config,
                "PROVIDER"
            ),
            "MODEL_SEED": self._resolve_cli_or_experiment(
                getattr(cli_args, 'model_seed', None),
                exp_config,
                "MODEL_SEED",
                parse_int
            ),
        }

        emit_event(
            self._logger, Event.CONFIG_RESOLVED, level=logging.DEBUG,
            scope="model_variant", experiment_id=getattr(experiment, 'experiment_id', None),
            resolved=resolved,
        )
        self._emit_system_default_applied(cli_args, scope="model_variant", fields={
            "BASE_URL": "url",
            "MODEL_MAX_TOKENS_REASONING": "reasoning_tokens",
            "MODEL_MAX_TOKENS_TOTAL": "max_tokens",
            "MODEL_REASONING_EFFORT": "reasoning",
            "MODEL_REPEAT_PENALTY": "repeat_penalty",
            "MODEL_SEED": "model_seed",
            "MODEL_TEMPERATURE": "temperature",
            "MODEL_TOP_K": "top_k",
            "MODEL_TOP_P": "top_p",
            "MODEL_VISION": "vision",
            "STRUCTURED_OUTPUTS": "structured",
            "PROVIDER": "provider",
        })

        return resolved

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
        if isinstance(value, bool):
            # A real Python bool reaches here when this parser is applied
            # to an experiment's ALREADY-resolved MODEL_VISION/
            # STRUCTURED_OUTPUTS value during model-variant inheritance
            # (_resolve_cli_or_experiment calls this same parser on
            # exp_config.get(exp_key), which is a real bool after the
            # config_json round-trip through JSON, not a CLI string).
            # Previously fell through to `return None` below, silently
            # discarding the inherited True/False on every --add-model
            # that didn't repeat --vision/--structured explicitly — see
            # docs/status/known-issues.md, 2026-08-21.
            return value
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
