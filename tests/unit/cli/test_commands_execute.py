"""Tests for src/cli/commands/execute.py — the Typer replacement for
bcllm_execute.py's former argparse create_parser(), marco 4C second
slice (2026-08-21).

--questions/--models syntax changed from argparse's nargs="+" (no Click
equivalent — confirmed directly, Click's list[str] options only support
the repeated-flag style) to a single comma-separated value, presented to
the user as a real design fork before implementing — see
src/cli/commands/execute.py's module docstring and
docs/status/known-issues.md for the full decision record.

--questions selects by 1-based POSITION in the dataset now, not the
source dataset's own question ID (the old "Q001" format is REMOVED
entirely — confirmed via direct investigation that it was previously
accepted as an unvalidated literal passthrough, and no active normative
contract required preserving it).
"""

from __future__ import annotations

import pytest

from src.cli.commands.execute import (
    parse_execute_argv, ExecuteParsedArgs,
    parse_question_position_spec, parse_model_id_list,
)
from src.core.argv_utils import ParserExit


BASE = ["--experiment", "exp1", "--execute"]


class TestValidInvocations:
    def test_execute_minimal(self):
        result = parse_execute_argv(BASE)
        assert isinstance(result, ExecuteParsedArgs)
        assert result.experiment == "exp1"
        assert result.execute is True
        assert result.run is None
        assert result.questions is None
        assert result.models is None
        assert result.retry_policy is None

    def test_run_filter(self):
        result = parse_execute_argv(BASE + ["--run", "run_abc"])
        assert result.run == "run_abc"

    def test_retry_policy_passthrough_unvalidated(self):
        """--retry-policy is deliberately NOT format-validated at parse
        time — passed through as a plain string exactly as before (its
        own doc-drift question is separately tracked, out of scope)."""
        result = parse_execute_argv(BASE + ["--retry-policy", "max_attempts=5,backoff=linear"])
        assert result.retry_policy == "max_attempts=5,backoff=linear"

    def test_retry_policy_even_garbage_passes_parse_layer(self):
        """Confirms --retry-policy really is unvalidated here — garbage
        values are rejected later, in handle_execute, not at parse time."""
        result = parse_execute_argv(BASE + ["--retry-policy", "not=a=valid=policy"])
        assert result.retry_policy == "not=a=valid=policy"


class TestQuestionsPositionGrammar:
    """parse_question_position_spec's grammar directly — every case the
    user's decision explicitly enumerated."""

    def test_single_position(self):
        assert parse_question_position_spec("1") == [1]

    def test_comma_list(self):
        assert parse_question_position_spec("1,3,5") == [1, 3, 5]

    def test_inclusive_range(self):
        assert parse_question_position_spec("1-10") == list(range(1, 11))

    def test_combination(self):
        assert parse_question_position_spec("1,3,10-20") == [1, 3] + list(range(10, 21))

    def test_spaces_around_commas_and_hyphens_tolerated(self):
        assert parse_question_position_spec("1, 3, 10-20") == [1, 3] + list(range(10, 21))
        assert parse_question_position_spec("10 - 20") == list(range(10, 21))

    def test_duplicates_normalized(self):
        assert parse_question_position_spec("1,1,3,1-3") == [1, 3, 2]

    def test_range_inclusive_boundaries(self):
        result = parse_question_position_spec("5-5")
        assert result == [5]

    def test_zero_rejected(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("0")

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("-5")

    def test_inverted_range_rejected(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("10-5")

    def test_empty_item_rejected_middle_comma(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("1,,3")

    def test_empty_item_rejected_trailing_comma(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("1,3,")

    def test_empty_item_rejected_leading_comma(self):
        with pytest.raises(ValueError):
            parse_question_position_spec(",1,3")

    def test_invalid_text_rejected(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("abc")

    def test_q001_format_no_longer_accepted(self):
        """The old source-dataset-ID format is removed entirely — no
        alias, no compatibility shim (user decision, 2026-08-21)."""
        with pytest.raises(ValueError):
            parse_question_position_spec("Q001")

    def test_zero_width_range_span_rejected_before_expansion(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("1-999999999")

    def test_malformed_range_multiple_hyphens_rejected(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("1-3-5")

    def test_trailing_hyphen_rejected(self):
        with pytest.raises(ValueError):
            parse_question_position_spec("5-")


class TestModelsCommaGrammar:
    def test_single_model(self):
        assert parse_model_id_list("model-a") == ["model-a"]

    def test_multiple_models(self):
        assert parse_model_id_list("model-a,model-b") == ["model-a", "model-b"]

    def test_spaces_around_commas_tolerated(self):
        assert parse_model_id_list("model-a, model-b") == ["model-a", "model-b"]

    def test_literal_no_numeric_grammar_applied(self):
        """Model IDs are literal identifiers — a hyphen in a model name
        (e.g. a real OpenRouter slug) must NOT be treated as a range."""
        assert parse_model_id_list("var_abc-123,var_xyz-456") == ["var_abc-123", "var_xyz-456"]

    def test_empty_item_rejected(self):
        with pytest.raises(ValueError):
            parse_model_id_list("model-a,,model-b")


class TestQuestionsThroughFullParser:
    """The same grammar, exercised through parse_execute_argv end-to-end
    — confirms format errors surface as ParserExit(status=2), not a
    Python exception escaping to the caller."""

    def test_valid_spec_resolves_to_int_list(self):
        result = parse_execute_argv(BASE + ["--questions", "1,3,10-20"])
        assert result.questions == [1, 3] + list(range(10, 21))

    @pytest.mark.parametrize("spec", ["0", "-5", "10-5", "1,,3", "abc", "Q001"])
    def test_invalid_specs_are_usage_errors(self, spec):
        with pytest.raises(ParserExit) as exc_info:
            parse_execute_argv(BASE + ["--questions", spec])
        assert exc_info.value.status == 2

    def test_models_valid_spec_resolves_to_str_list(self):
        result = parse_execute_argv(BASE + ["--models", "var-a,var-b"])
        assert result.models == ["var-a", "var-b"]

    def test_models_invalid_spec_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_execute_argv(BASE + ["--models", "var-a,,var-b"])
        assert exc_info.value.status == 2

    def test_no_accidental_capture_of_following_option(self):
        """A single comma-separated value means the option parser never
        needs to guess where the value ends — --run right after
        --questions must be read as a SEPARATE option, not swallowed."""
        result = parse_execute_argv(BASE + ["--questions", "1,3", "--run", "run_x"])
        assert result.questions == [1, 3]
        assert result.run == "run_x"

    def test_coexists_with_run_and_models(self):
        result = parse_execute_argv(
            BASE + ["--questions", "1,3", "--models", "var-a", "--run", "run_x"]
        )
        assert result.questions == [1, 3]
        assert result.models == ["var-a"]
        assert result.run == "run_x"


class TestForbiddenFlags:
    def test_experiment_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_execute_argv(["--experiment", "system-default", "--execute"])
        assert exc_info.value.status == 2

    def test_experiment_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_execute_argv(["--experiment", "null", "--execute"])
        assert exc_info.value.status == 2

    def test_run_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_execute_argv(BASE + ["--run", "system-default"])
        assert exc_info.value.status == 2


class TestUnrecognizedOption:
    def test_unrecognized_flag_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_execute_argv(BASE + ["--bogus", "x"])
        assert exc_info.value.status == 2


class TestMissingRequiredExperiment:
    def test_missing_experiment_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_execute_argv(["--execute"])
        assert exc_info.value.status == 2


class TestHelp:
    def test_help_raises_parser_exit_status_zero(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_execute_argv(["--help"])
        assert exc_info.value.status == 0


class TestStderrMessageAlreadyPrinted:
    def test_forbidden_message_written_to_stderr(self, capsys):
        with pytest.raises(ParserExit):
            parse_execute_argv(["--experiment", "system-default", "--execute"])
        captured = capsys.readouterr()
        assert "system-default" in captured.err
