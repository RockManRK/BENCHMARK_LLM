"""Regression tests for the 8 bcllm_model.py flags that did not support
system-default correctly before 2026-08-19 — see
docs/status/known-issues.md ("bcllm_model.py's 7 numeric flags use plain
type=int/float...") and the closely-related --reasoning choices bug found
in the same investigation.

Root cause (fixed): 7 numeric flags used plain `type=int`/`type=float`
instead of `parse_int_or_system_default`/`parse_float_or_system_default`
(src/core/special_config_values.py), so 'system-default' failed at
argparse's own type-conversion step with a generic "invalid int/float
value" error — before ever reaching the FORCE_SYSTEM_DEFAULT normalization
path that the identically-named flags on bcllm_experiment.py already used
correctly. `--reasoning` had the same class of bug via `choices=[...]`
that didn't include 'system-default'.

Each of the 8 flags is tested for: an explicit valid value, 'system-default'
(-> FORCE_SYSTEM_DEFAULT), the deprecated 'null' literal (rejected), and an
invalid value (rejected) — all via the real `create_parser()` +
`parse_args_normalized()` with the module's real SYSTEM_DEFAULT_SUPPORTED/
SYSTEM_DEFAULT_FORBIDDEN classification, not a synthetic stand-in parser.
"""

from __future__ import annotations

import argparse

import pytest

from src.cli.bcllm_model import create_parser, SYSTEM_DEFAULT_SUPPORTED, SYSTEM_DEFAULT_FORBIDDEN
from src.core.argv_utils import parse_args_normalized, ParserExit
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT


def _parse(argv: list[str]) -> argparse.Namespace:
    base = ["--experiment", "x", "--add-model", "openai/gpt-4"]
    return parse_args_normalized(
        create_parser(), base + argv,
        supported=SYSTEM_DEFAULT_SUPPORTED, forbidden=SYSTEM_DEFAULT_FORBIDDEN,
    )


INT_FLAGS = ["--max-reasoning", "--max-tokens", "--top-k", "--reasoning-tokens"]
FLOAT_FLAGS = ["--repeat-penalty", "--temperature", "--top-p"]
DEST_BY_FLAG = {
    "--max-reasoning": "max_reasoning",
    "--max-tokens": "max_tokens",
    "--top-k": "top_k",
    "--reasoning-tokens": "reasoning_tokens",
    "--repeat-penalty": "repeat_penalty",
    "--temperature": "temperature",
    "--top-p": "top_p",
}


@pytest.mark.parametrize("flag", INT_FLAGS)
class TestIntFlagsSystemDefault:
    def test_explicit_valid_value(self, flag):
        args = _parse([flag, "100"])
        assert getattr(args, DEST_BY_FLAG[flag]) == 100

    def test_system_default(self, flag):
        args = _parse([flag, "system-default"])
        assert getattr(args, DEST_BY_FLAG[flag]) is FORCE_SYSTEM_DEFAULT

    def test_system_default_case_insensitive(self, flag):
        args = _parse([flag, "SYSTEM-DEFAULT"])
        assert getattr(args, DEST_BY_FLAG[flag]) is FORCE_SYSTEM_DEFAULT

    def test_legacy_null_rejected(self, flag):
        with pytest.raises(ParserExit):
            _parse([flag, "null"])

    def test_invalid_value_rejected(self, flag):
        with pytest.raises(ParserExit):
            _parse([flag, "not-a-number"])


@pytest.mark.parametrize("flag", FLOAT_FLAGS)
class TestFloatFlagsSystemDefault:
    def test_explicit_valid_value(self, flag):
        args = _parse([flag, "0.7"])
        assert getattr(args, DEST_BY_FLAG[flag]) == 0.7

    def test_system_default(self, flag):
        args = _parse([flag, "system-default"])
        assert getattr(args, DEST_BY_FLAG[flag]) is FORCE_SYSTEM_DEFAULT

    def test_legacy_null_rejected(self, flag):
        with pytest.raises(ParserExit):
            _parse([flag, "null"])

    def test_invalid_value_rejected(self, flag):
        with pytest.raises(ParserExit):
            _parse([flag, "not-a-float"])


class TestReasoningFlagSystemDefault:
    """--reasoning uses choices=[...], not a type= parser — same bug class,
    different mechanism (argparse's own choices validation happening
    before FORCE_SYSTEM_DEFAULT normalization could ever apply)."""

    def test_explicit_valid_value(self):
        args = _parse(["--reasoning", "high"])
        assert args.reasoning == "high"

    def test_system_default(self):
        args = _parse(["--reasoning", "system-default"])
        assert args.reasoning is FORCE_SYSTEM_DEFAULT

    def test_legacy_null_rejected(self):
        """'null' was never a valid choice for --reasoning (unlike flags
        using parse_str_or_system_default) — argparse's own choices
        validation rejects it directly. Confirmed as acceptable: this
        flag never accepted 'null' as anything but garbage, so there is
        no regression versus a friendlier deprecation message that never
        existed for it."""
        with pytest.raises(ParserExit):
            _parse(["--reasoning", "null"])

    def test_invalid_value_rejected(self):
        with pytest.raises(ParserExit):
            _parse(["--reasoning", "ultra-high"])

    def test_none_literal_still_a_valid_domain_choice(self):
        """'none' is a genuine reasoning_effort value (MODEL_REASONING_EFFORT),
        unrelated to system-default/null — must keep working."""
        args = _parse(["--reasoning", "none"])
        assert args.reasoning == "none"


class TestReasoningInheritsFromExperiment:
    """'Valor herdado' — when --reasoning is not passed at --add-model time,
    ConfigResolver.build_model_config_dict inherits MODEL_REASONING_EFFORT
    from the experiment's config (set at --create-experiment time), via
    _resolve_cli_or_experiment. This is a distinct layer from CLI parsing —
    see src/core/config_resolver.py."""

    def test_reasoning_inherits_from_experiment_config_when_not_passed(self):
        from src.core.config_resolver import ConfigResolver
        from src.db.models import Experiment
        import json

        resolver = ConfigResolver()
        experiment = Experiment(
            experiment_id="exp_test",
            name="test-exp",
            description=None,
            config_json=json.dumps({"MODEL_REASONING_EFFORT": "high"}),
            config_hash="deadbeef",
        )
        args = argparse.Namespace(reasoning=None)

        config = resolver.build_model_config_dict(args, experiment)

        assert config["MODEL_REASONING_EFFORT"] == "high"

    def test_reasoning_cli_value_overrides_experiment_inheritance(self):
        from src.core.config_resolver import ConfigResolver
        from src.db.models import Experiment
        import json

        resolver = ConfigResolver()
        experiment = Experiment(
            experiment_id="exp_test",
            name="test-exp",
            description=None,
            config_json=json.dumps({"MODEL_REASONING_EFFORT": "high"}),
            config_hash="deadbeef",
        )
        args = argparse.Namespace(reasoning="low")

        config = resolver.build_model_config_dict(args, experiment)

        assert config["MODEL_REASONING_EFFORT"] == "low"

    def test_reasoning_system_default_breaks_inheritance(self):
        from src.core.config_resolver import ConfigResolver
        from src.db.models import Experiment
        import json

        resolver = ConfigResolver()
        experiment = Experiment(
            experiment_id="exp_test",
            name="test-exp",
            description=None,
            config_json=json.dumps({"MODEL_REASONING_EFFORT": "high"}),
            config_hash="deadbeef",
        )
        args = argparse.Namespace(reasoning=FORCE_SYSTEM_DEFAULT)

        config = resolver.build_model_config_dict(args, experiment)

        assert config["MODEL_REASONING_EFFORT"] is None


class TestUrlForbiddenExitCode2:
    """--url moved from a SUPPORTED-but-manually-rejected flag (exit 1) to
    FORBIDDEN (exit 2) — see docs/status/known-issues.md and the approved
    3-category classification. This is an intentional behavior change.

    `parse_args_normalized` itself raises `argparse.ArgumentError` (not
    SystemExit — that conversion happens at each module's `main()` via
    `except argparse.ArgumentError as e: parser.error(str(e))`, which is
    what actually produces exit code 2). See
    tests/cli_suite/cases/model.yaml for the real-process, real-exit-code
    proof through the full `python bcllm.py` entry point."""

    def test_url_system_default_rejected_at_parse_time(self):
        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            _parse(["--url", "system-default"])

    def test_url_ordinary_value_untouched(self):
        args = _parse(["--url", "http://localhost:8080/v1"])
        assert args.url == "http://localhost:8080/v1"


class TestProviderSystemDefaultRegression:
    """--provider was already correctly handled by ConfigResolver
    (_resolve_cli_or_experiment recognizes FORCE_SYSTEM_DEFAULT) before
    this fix — confirm it still works now that eligibility is explicit
    opt-in instead of the old default=None heuristic."""

    def test_provider_system_default_parses_to_sentinel(self):
        args = _parse(["--provider", "system-default"])
        assert args.provider is FORCE_SYSTEM_DEFAULT

    def test_provider_system_default_breaks_inheritance_at_resolver(self):
        from src.core.config_resolver import ConfigResolver
        from src.db.models import Experiment
        import json

        resolver = ConfigResolver()
        experiment = Experiment(
            experiment_id="exp_test",
            name="test-exp",
            description=None,
            config_json=json.dumps({"PROVIDER": "deepinfra/turbo"}),
            config_hash="deadbeef",
        )
        args = argparse.Namespace(provider=FORCE_SYSTEM_DEFAULT)

        config = resolver.build_model_config_dict(args, experiment)

        assert config["PROVIDER"] is None

    def test_provider_explicit_value_pins_regardless_of_experiment(self):
        from src.core.config_resolver import ConfigResolver
        from src.db.models import Experiment
        import json

        resolver = ConfigResolver()
        experiment = Experiment(
            experiment_id="exp_test",
            name="test-exp",
            description=None,
            config_json=json.dumps({}),
            config_hash="deadbeef",
        )
        args = argparse.Namespace(provider="deepinfra/turbo")

        config = resolver.build_model_config_dict(args, experiment)

        assert config["PROVIDER"] == "deepinfra/turbo"
