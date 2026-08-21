"""ConfigResolver.build_model_config_dict domain-level regression tests
for bcllm_model.py's --reasoning/--provider inheritance-from-experiment
behavior — a layer distinct from CLI argv parsing (these call the
resolver directly with a synthetic args object; duck-typed getattr()
access works identically whether that object is an argparse.Namespace or
src/cli/commands/model.py's ModelParsedArgs).

This file previously also covered the 8-flag system-default/'null'/
choices CLI-parsing regression suite directly against `create_parser()` +
`parse_args_normalized()` — see docs/status/known-issues.md ("bcllm_model.py's
7 numeric flags use plain type=int..." and the --reasoning choices bug
found in the same investigation) for the historical bug those tests
guarded. That coverage moved to tests/unit/cli/test_commands_model.py's
equivalent classes (TestIntFlagsSystemDefault, TestFloatFlagsSystemDefault,
TestReasoningChoicesPlusSystemDefault, TestForbiddenFlags) as part of the
Typer conversion (marco 4B second slice, 2026-08-20), which exercises the
same cases against the real parse_model_argv() — create_parser() no
longer exists on this module.
"""

from __future__ import annotations

import argparse
import json

import pytest

from src.core.special_config_values import FORCE_SYSTEM_DEFAULT


class TestReasoningInheritsFromExperiment:
    """'Valor herdado' — when --reasoning is not passed at --add-model time,
    ConfigResolver.build_model_config_dict inherits MODEL_REASONING_EFFORT
    from the experiment's config (set at --create-experiment time), via
    _resolve_cli_or_experiment. This is a distinct layer from CLI parsing —
    see src/core/config_resolver.py."""

    def test_reasoning_inherits_from_experiment_config_when_not_passed(self):
        from src.core.config_resolver import ConfigResolver
        from src.db.models import Experiment

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


class TestProviderSystemDefaultRegression:
    """--provider was already correctly handled by ConfigResolver
    (_resolve_cli_or_experiment recognizes FORCE_SYSTEM_DEFAULT) before
    the CLI-parsing fix — confirm it still works now that eligibility is
    explicit opt-in instead of the old default=None heuristic."""

    def test_provider_system_default_breaks_inheritance_at_resolver(self):
        from src.core.config_resolver import ConfigResolver
        from src.db.models import Experiment

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
