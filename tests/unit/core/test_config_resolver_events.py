"""Tests for the new DETAILED-tier observability events added to
ConfigResolver in Checkpoint C: CONFIG_RESOLVED, INHERITANCE_DECISION,
SYSTEM_DEFAULT_APPLIED. These close the "config_resolver.py has zero
logging" gap identified in the Checkpoint C investigation.
"""
import json
from unittest.mock import patch

from src.core.config_resolver import ConfigResolver
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT
from src.utils.log_events import Event


class _Args:
    pass


class _Experiment:
    experiment_id = "exp_test123"
    config_json = "{}"


class TestConfigResolvedEvent:
    def test_experiment_creation_emits_config_resolved(self):
        resolver = ConfigResolver()
        resolver.env_dict = {}
        args = _Args()
        args.create_experiment = "my_exp"

        with patch("src.core.config_resolver.emit_event") as spy:
            resolver.build_experiment_config_dict(args)

        event_names = [call.args[1] for call in spy.call_args_list]
        assert Event.CONFIG_RESOLVED in event_names
        resolved_call = next(c for c in spy.call_args_list if c.args[1] == Event.CONFIG_RESOLVED)
        assert resolved_call.kwargs["scope"] == "experiment"
        assert "resolved" in resolved_call.kwargs

    def test_run_creation_emits_config_resolved(self):
        resolver = ConfigResolver()
        args = _Args()
        args.randomization_seed = None
        args.system_prompt = None
        args.user_prompt = None

        with patch("src.core.config_resolver.emit_event") as spy:
            resolver.build_run_config_dict(args, _Experiment(), run_id="run_1")

        resolved_call = next(c for c in spy.call_args_list if c.args[1] == Event.CONFIG_RESOLVED)
        assert resolved_call.kwargs["scope"] == "run"
        assert resolved_call.kwargs["run_id"] == "run_1"

    def test_model_variant_creation_emits_config_resolved(self):
        resolver = ConfigResolver()
        args = _Args()
        for attr in ("url", "reasoning_tokens", "max_reasoning", "max_tokens", "reasoning",
                     "repeat_penalty", "temperature", "top_k", "top_p", "vision",
                     "structured", "provider", "model_seed"):
            setattr(args, attr, None)

        with patch("src.core.config_resolver.emit_event") as spy:
            resolver.build_model_config_dict(args, _Experiment())

        resolved_call = next(c for c in spy.call_args_list if c.args[1] == Event.CONFIG_RESOLVED)
        assert resolved_call.kwargs["scope"] == "model_variant"


class TestSystemDefaultAppliedEvent:
    def test_emitted_when_a_field_uses_system_default(self):
        resolver = ConfigResolver()
        args = _Args()
        for attr in ("url", "reasoning_tokens", "max_reasoning", "max_tokens", "reasoning",
                     "repeat_penalty", "temperature", "top_k", "top_p", "vision",
                     "structured", "provider", "model_seed"):
            setattr(args, attr, None)
        args.temperature = FORCE_SYSTEM_DEFAULT

        with patch("src.core.config_resolver.emit_event") as spy:
            resolver.build_model_config_dict(args, _Experiment())

        applied_calls = [c for c in spy.call_args_list if c.args[1] == Event.SYSTEM_DEFAULT_APPLIED]
        assert len(applied_calls) == 1
        assert "MODEL_TEMPERATURE" in applied_calls[0].kwargs["fields"]

    def test_not_emitted_when_no_field_uses_system_default(self):
        resolver = ConfigResolver()
        args = _Args()
        for attr in ("url", "reasoning_tokens", "max_reasoning", "max_tokens", "reasoning",
                     "repeat_penalty", "temperature", "top_k", "top_p", "vision",
                     "structured", "provider", "model_seed"):
            setattr(args, attr, None)

        with patch("src.core.config_resolver.emit_event") as spy:
            resolver.build_model_config_dict(args, _Experiment())

        applied_calls = [c for c in spy.call_args_list if c.args[1] == Event.SYSTEM_DEFAULT_APPLIED]
        assert len(applied_calls) == 0


class TestInheritanceDecisionEvent:
    def test_emitted_when_auto_resolved_from_cli(self):
        resolver = ConfigResolver()

        with patch("src.core.config_resolver.emit_event") as spy:
            result = resolver.resolve_randomization_seed_for_run(
                cli_value="AUTO", experiment_seed=None, run_id="run_1", experiment_id="exp_1",
            )

        assert isinstance(result, int)
        decision_calls = [c for c in spy.call_args_list if c.args[1] == Event.INHERITANCE_DECISION]
        assert len(decision_calls) == 1
        assert decision_calls[0].kwargs["source"] == "cli_auto"
        assert decision_calls[0].kwargs["resolved_value"] == result

    def test_emitted_when_auto_resolved_from_experiment(self):
        resolver = ConfigResolver()

        with patch("src.core.config_resolver.emit_event") as spy:
            result = resolver.resolve_randomization_seed_for_run(
                cli_value=None, experiment_seed="AUTO", run_id="run_1", experiment_id="exp_1",
            )

        assert isinstance(result, int)
        decision_calls = [c for c in spy.call_args_list if c.args[1] == Event.INHERITANCE_DECISION]
        assert len(decision_calls) == 1
        assert decision_calls[0].kwargs["source"] == "experiment_auto"

    def test_not_emitted_when_no_auto_involved(self):
        resolver = ConfigResolver()

        with patch("src.core.config_resolver.emit_event") as spy:
            resolver.resolve_randomization_seed_for_run(
                cli_value=42, experiment_seed=None, run_id="run_1", experiment_id="exp_1",
            )

        decision_calls = [c for c in spy.call_args_list if c.args[1] == Event.INHERITANCE_DECISION]
        assert len(decision_calls) == 0
