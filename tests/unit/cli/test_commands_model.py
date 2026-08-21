"""Tests for src/cli/commands/model.py — the Typer replacement for
bcllm_model.py's former argparse create_parser(), marco 4B second slice
(2026-08-20). Verifies parse_model_argv() behaves identically to the old
create_parser() + parse_args_normalized() for every flag/special
value/error case, before bcllm_model.py is wired to use it.

--reasoning is exercised the most thoroughly here — it is the one flag in
this module with a real argparse choices=[...] constraint (unlike its
free-string counterpart on bcllm_experiment.py), replicated via a real
Enum (src/cli/commands/model.py::ReasoningEffort) so invalid values
(including the deprecated 'null', never a valid choice for this flag) are
rejected before FORCE_SYSTEM_DEFAULT normalization could ever apply — see
tests/unit/cli/test_bcllm_model_system_default.py (pre-Typer regression
tests) for the historical bug this replicates the fix for.
"""

from __future__ import annotations

import pytest

from src.cli.commands.model import parse_model_argv, ModelParsedArgs
from src.core.argv_utils import ParserExit
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT


BASE = ["--experiment", "exp1", "--add-model", "openai/gpt-4"]


class TestValidInvocations:
    def test_add_model_minimal(self):
        result = parse_model_argv(BASE)
        assert isinstance(result, ModelParsedArgs)
        assert result.experiment == "exp1"
        assert result.add_model == "openai/gpt-4"
        assert result.list_models is False
        assert result.remove_model is None

    def test_list_models(self):
        result = parse_model_argv(["--experiment", "exp1", "--list-models"])
        assert result.list_models is True

    def test_remove_model(self):
        result = parse_model_argv(["--experiment", "exp1", "--remove-model", "var_abc"])
        assert result.remove_model == "var_abc"

    def test_output_default_console(self):
        result = parse_model_argv(BASE)
        assert result.output == "console"

    def test_output_explicit_json(self):
        result = parse_model_argv(BASE + ["--output", "json"])
        assert result.output == "json"

    def test_url_ordinary_value(self):
        result = parse_model_argv(BASE + ["--url", "http://localhost:8080/v1"])
        assert result.url == "http://localhost:8080/v1"


class TestIntFlagsSystemDefault:
    INT_FLAGS = [
        ("--max-tokens", "max_tokens"),
        ("--top-k", "top_k"),
        ("--reasoning-tokens", "reasoning_tokens"),
        ("--model-seed", "model_seed"),
    ]

    @pytest.mark.parametrize("flag,dest", INT_FLAGS)
    def test_explicit_valid_value(self, flag, dest):
        result = parse_model_argv(BASE + [flag, "100"])
        assert getattr(result, dest) == 100

    @pytest.mark.parametrize("flag,dest", INT_FLAGS)
    def test_system_default(self, flag, dest):
        result = parse_model_argv(BASE + [flag, "system-default"])
        assert getattr(result, dest) is FORCE_SYSTEM_DEFAULT

    @pytest.mark.parametrize("flag,dest", INT_FLAGS)
    def test_system_default_case_insensitive(self, flag, dest):
        result = parse_model_argv(BASE + [flag, "SYSTEM-DEFAULT"])
        assert getattr(result, dest) is FORCE_SYSTEM_DEFAULT

    @pytest.mark.parametrize("flag,dest", INT_FLAGS)
    def test_legacy_null_rejected(self, flag, dest):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + [flag, "null"])
        assert exc_info.value.status == 2

    @pytest.mark.parametrize("flag,dest", INT_FLAGS)
    def test_invalid_value_rejected(self, flag, dest):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + [flag, "not-a-number"])
        assert exc_info.value.status == 2

    def test_model_seed_zero_preserved(self):
        """MODEL_SEED=0 is a real, distinct value from None/system-default
        — must not be collapsed or treated as falsy anywhere in parsing."""
        result = parse_model_argv(BASE + ["--model-seed", "0"])
        assert result.model_seed == 0


class TestFloatFlagsSystemDefault:
    FLOAT_FLAGS = [
        ("--repeat-penalty", "repeat_penalty"),
        ("--temperature", "temperature"),
        ("--top-p", "top_p"),
    ]

    @pytest.mark.parametrize("flag,dest", FLOAT_FLAGS)
    def test_explicit_valid_value(self, flag, dest):
        result = parse_model_argv(BASE + [flag, "0.7"])
        assert getattr(result, dest) == 0.7

    @pytest.mark.parametrize("flag,dest", FLOAT_FLAGS)
    def test_system_default(self, flag, dest):
        result = parse_model_argv(BASE + [flag, "system-default"])
        assert getattr(result, dest) is FORCE_SYSTEM_DEFAULT

    @pytest.mark.parametrize("flag,dest", FLOAT_FLAGS)
    def test_legacy_null_rejected(self, flag, dest):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + [flag, "null"])
        assert exc_info.value.status == 2

    @pytest.mark.parametrize("flag,dest", FLOAT_FLAGS)
    def test_invalid_value_rejected(self, flag, dest):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + [flag, "not-a-float"])
        assert exc_info.value.status == 2


class TestStringSupportedFlagsSystemDefault:
    STR_FLAGS = [
        ("--vision", "vision"),
        ("--structured", "structured"),
        ("--provider", "provider"),
    ]

    @pytest.mark.parametrize("flag,dest", STR_FLAGS)
    def test_explicit_value_passthrough(self, flag, dest):
        result = parse_model_argv(BASE + [flag, "true"])
        assert getattr(result, dest) == "true"

    @pytest.mark.parametrize("flag,dest", STR_FLAGS)
    def test_system_default(self, flag, dest):
        result = parse_model_argv(BASE + [flag, "system-default"])
        assert getattr(result, dest) is FORCE_SYSTEM_DEFAULT

    @pytest.mark.parametrize("flag,dest", STR_FLAGS)
    def test_legacy_null_rejected(self, flag, dest):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + [flag, "null"])
        assert exc_info.value.status == 2

    def test_provider_slug_passthrough(self):
        result = parse_model_argv(BASE + ["--provider", "deepinfra/turbo"])
        assert result.provider == "deepinfra/turbo"


class TestReasoningChoicesPlusSystemDefault:
    """--reasoning has BOTH a real choices=[...] constraint AND
    SYSTEM_DEFAULT_SUPPORTED membership — the one flag in this module
    needing the Enum-based approach instead of a plain str callback."""

    def test_explicit_valid_value(self):
        result = parse_model_argv(BASE + ["--reasoning", "high"])
        assert result.reasoning == "high"

    def test_none_literal_is_a_valid_domain_choice(self):
        """'none' is a genuine reasoning_effort value (MODEL_REASONING_EFFORT),
        unrelated to system-default/null — must keep working, and must NOT
        collapse to Python None."""
        result = parse_model_argv(BASE + ["--reasoning", "none"])
        assert result.reasoning == "none"

    def test_system_default(self):
        result = parse_model_argv(BASE + ["--reasoning", "system-default"])
        assert result.reasoning is FORCE_SYSTEM_DEFAULT

    def test_absent_is_none(self):
        result = parse_model_argv(BASE)
        assert result.reasoning is None

    def test_legacy_null_rejected(self):
        """'null' was never a valid choice for --reasoning — argparse's
        own choices validation rejected it directly, pre-Typer; the Enum
        here must reject it the same way (invalid choice, not a
        deprecated-null-specific message)."""
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--reasoning", "null"])
        assert exc_info.value.status == 2

    def test_invalid_value_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--reasoning", "ultra-high"])
        assert exc_info.value.status == 2

    @pytest.mark.parametrize("value", ["none", "minimal", "low", "medium", "high", "xhigh"])
    def test_every_real_choice_accepted(self, value):
        result = parse_model_argv(BASE + ["--reasoning", value])
        assert result.reasoning == value


class TestReasoningTokensPositiveIntOnly:
    """--max-reasoning removed 2026-08-21 (true synonym of
    --reasoning-tokens — see docs/status/known-issues.md).
    --reasoning-tokens now rejects 0/negative as a usage error: Anthropic's
    documented floor is 1024 tokens regardless of what's requested, so
    persisting a literal 0 would misrepresent what actually happens at
    execution; --reasoning none already exists to disable reasoning."""

    def test_zero_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--reasoning-tokens", "0"])
        assert exc_info.value.status == 2

    def test_negative_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--reasoning-tokens", "-5"])
        assert exc_info.value.status == 2

    def test_positive_accepted(self):
        result = parse_model_argv(BASE + ["--reasoning-tokens", "1"])
        assert result.reasoning_tokens == 1

    def test_system_default_not_affected_by_positivity_check(self):
        result = parse_model_argv(BASE + ["--reasoning-tokens", "system-default"])
        assert result.reasoning_tokens is FORCE_SYSTEM_DEFAULT

    def test_max_reasoning_flag_no_longer_exists(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--max-reasoning", "500"])
        assert exc_info.value.status == 2


class TestReasoningEffortTokensSameLayerConflict:
    """OpenRouter's reasoning object accepts only ONE of effort/max_tokens
    — a concrete value for BOTH on the same command is a usage error, not
    silently resolved by priority (docs/status/known-issues.md, 2026-08-21)."""

    def test_both_concrete_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--reasoning", "high", "--reasoning-tokens", "2000"])
        assert exc_info.value.status == 2

    def test_reasoning_none_plus_tokens_is_still_a_conflict(self):
        """'none' is a concrete effort value, not an absence — combining
        it with a concrete --reasoning-tokens is exactly the same conflict
        class as any other effort value."""
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--reasoning", "none", "--reasoning-tokens", "2000"])
        assert exc_info.value.status == 2

    def test_reasoning_concrete_plus_tokens_system_default_is_not_a_conflict(self):
        """system-default is not a mode selection — it doesn't collide
        with a concrete effort on the sibling field."""
        result = parse_model_argv(BASE + ["--reasoning", "high", "--reasoning-tokens", "system-default"])
        assert result.reasoning == "high"
        assert result.reasoning_tokens is FORCE_SYSTEM_DEFAULT

    def test_reasoning_system_default_plus_tokens_concrete_is_not_a_conflict(self):
        result = parse_model_argv(BASE + ["--reasoning", "system-default", "--reasoning-tokens", "2000"])
        assert result.reasoning is FORCE_SYSTEM_DEFAULT
        assert result.reasoning_tokens == 2000

    def test_both_system_default_is_not_a_conflict(self):
        result = parse_model_argv(BASE + ["--reasoning", "system-default", "--reasoning-tokens", "system-default"])
        assert result.reasoning is FORCE_SYSTEM_DEFAULT
        assert result.reasoning_tokens is FORCE_SYSTEM_DEFAULT

    def test_reasoning_alone_is_not_a_conflict(self):
        result = parse_model_argv(BASE + ["--reasoning", "high"])
        assert result.reasoning == "high"
        assert result.reasoning_tokens is None

    def test_tokens_alone_is_not_a_conflict(self):
        result = parse_model_argv(BASE + ["--reasoning-tokens", "2000"])
        assert result.reasoning is None
        assert result.reasoning_tokens == 2000


class TestMutexGroup:
    def test_none_given_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--experiment", "exp1"])
        assert exc_info.value.status == 2

    def test_two_given_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--experiment", "exp1", "--add-model", "openai/gpt-4", "--list-models"])
        assert exc_info.value.status == 2

    def test_add_model_and_remove_model_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv([
                "--experiment", "exp1",
                "--add-model", "openai/gpt-4", "--remove-model", "var_x",
            ])
        assert exc_info.value.status == 2


class TestForbiddenFlags:
    def test_experiment_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--experiment", "system-default", "--list-models"])
        assert exc_info.value.status == 2

    def test_experiment_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--experiment", "null", "--list-models"])
        assert exc_info.value.status == 2

    def test_add_model_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--experiment", "exp1", "--add-model", "system-default"])
        assert exc_info.value.status == 2

    def test_remove_model_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--experiment", "exp1", "--remove-model", "system-default"])
        assert exc_info.value.status == 2

    def test_url_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--url", "system-default"])
        assert exc_info.value.status == 2

    def test_url_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--url", "null"])
        assert exc_info.value.status == 2


class TestInvalidOutputChoice:
    def test_invalid_output_value_exits_2(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--experiment", "exp1", "--list-models", "--output", "bogus"])
        assert exc_info.value.status == 2


class TestUnrecognizedOption:
    def test_unrecognized_flag_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(BASE + ["--bogus", "x"])
        assert exc_info.value.status == 2


class TestMissingRequiredExperiment:
    def test_missing_experiment_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--add-model", "openai/gpt-4"])
        assert exc_info.value.status == 2


class TestHelp:
    def test_help_raises_parser_exit_status_zero(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_model_argv(["--help"])
        assert exc_info.value.status == 0


class TestStderrMessageAlreadyPrinted:
    def test_forbidden_message_written_to_stderr(self, capsys):
        with pytest.raises(ParserExit):
            parse_model_argv(["--experiment", "system-default", "--list-models"])
        captured = capsys.readouterr()
        assert "system-default" in captured.err
