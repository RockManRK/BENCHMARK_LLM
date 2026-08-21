"""Tests for src/cli/commands/experiment.py — the Typer replacement for
bcllm_experiment.py's former argparse create_parser(), marco 4A
(2026-08-20). Verifies parse_experiment_argv() behaves identically to the
old create_parser() + parse_args_normalized() for every flag/special
value/error case, before bcllm_experiment.py is wired to use it.
"""

from __future__ import annotations

import pytest

from src.cli.commands.experiment import parse_experiment_argv, ExperimentParsedArgs
from src.core.argv_utils import ParserExit
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT


class TestValidInvocations:
    def test_create_experiment_minimal(self):
        result = parse_experiment_argv(["--create-experiment", "exp1"])
        assert isinstance(result, ExperimentParsedArgs)
        assert result.create_experiment == "exp1"
        assert result.experiment is None
        assert result.list_experiments is False
        assert result.remove_experiment is None

    def test_show_experiment(self):
        result = parse_experiment_argv(["--experiment", "exp1"])
        assert result.experiment == "exp1"

    def test_list_experiments(self):
        result = parse_experiment_argv(["--list-experiments"])
        assert result.list_experiments is True

    def test_remove_experiment(self):
        result = parse_experiment_argv(["--remove-experiment", "exp1"])
        assert result.remove_experiment == "exp1"

    def test_int_model_seed_including_zero(self):
        result = parse_experiment_argv(["--create-experiment", "exp1", "--model-seed", "0"])
        assert result.model_seed == 0
        assert result.model_seed is not None

    def test_float_temperature(self):
        result = parse_experiment_argv(["--create-experiment", "exp1", "--temperature", "0.7"])
        assert result.temperature == 0.7

    def test_string_reasoning(self):
        result = parse_experiment_argv(["--create-experiment", "exp1", "--reasoning", "high"])
        assert result.reasoning == "high"

    def test_system_default_scalar(self):
        result = parse_experiment_argv(["--create-experiment", "exp1", "--model-seed", "system-default"])
        assert result.model_seed is FORCE_SYSTEM_DEFAULT

    def test_add_model_repeated(self):
        result = parse_experiment_argv([
            "--create-experiment", "exp1", "--add-model", "a/b", "--add-model", "c/d",
        ])
        assert result.add_model == ["a/b", "c/d"]

    def test_add_model_absent_is_empty_list(self):
        result = parse_experiment_argv(["--create-experiment", "exp1"])
        assert result.add_model == []

    def test_add_questions_alias(self):
        result = parse_experiment_argv(["--create-experiment", "exp1", "--questions", "1-5"])
        assert result.add_questions == "1-5"

    def test_where_exclude_concrete(self):
        result = parse_experiment_argv([
            "--create-experiment", "exp1", "--where", "status=valid", "--exclude", "status=annulled",
        ])
        assert result.where == ["status=valid"]
        assert result.exclude == ["status=annulled"]

    def test_where_absent_is_empty_list(self):
        result = parse_experiment_argv(["--create-experiment", "exp1"])
        assert result.where == []
        assert result.exclude == []

    def test_where_system_default(self):
        result = parse_experiment_argv(["--create-experiment", "exp1", "--where", "system-default"])
        assert result.where is FORCE_SYSTEM_DEFAULT

    def test_vision_and_structured_plain_strings_not_bool_converted(self):
        result = parse_experiment_argv([
            "--create-experiment", "exp1", "--vision", "true", "--structured", "false",
        ])
        assert result.vision == "true"
        assert result.structured == "false"

    def test_output_default_console(self):
        result = parse_experiment_argv(["--create-experiment", "exp1"])
        assert result.output == "console"


class TestMutexGroup:
    def test_none_given_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv([])
        assert exc_info.value.status == 2

    def test_two_given_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--list-experiments"])
        assert exc_info.value.status == 2

    def test_create_and_remove_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--remove-experiment", "exp1"])
        assert exc_info.value.status == 2

    def test_same_flag_repeated_is_not_a_mutex_violation(self):
        """Essence Guardian finding (marco 4A pre-4B audit, 2026-08-20):
        repeating the SAME scalar mutex-group flag twice is not itself a
        mutex-group violation (only one group member has a value —
        create_experiment — the mutex count sees it once regardless of
        how many times it was written). Click keeps the last value.
        Verified sound by reading Click's source directly; exercised by
        a test for the first time here."""
        result = parse_experiment_argv(["--create-experiment", "exp1", "--create-experiment", "exp2"])
        assert result.create_experiment == "exp2"

    def test_help_combined_with_data_flag_still_shows_help(self):
        """--help takes priority over any other option per Click's
        eager-option handling — verified via source read, tested here."""
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--help"])
        assert exc_info.value.status == 0


class TestForbiddenFlags:
    def test_experiment_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--experiment", "system-default"])
        assert exc_info.value.status == 2

    def test_create_experiment_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "system-default"])
        assert exc_info.value.status == 2

    def test_url_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--url", "system-default"])
        assert exc_info.value.status == 2

    def test_remove_experiment_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--remove-experiment", "null"])
        assert exc_info.value.status == 2


class TestFilterContradiction:
    def test_system_default_combined_with_concrete_filter(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv([
                "--create-experiment", "exp1", "--where", "system-default", "--where", "status=valid",
            ])
        assert exc_info.value.status == 2


class TestDeprecatedNull:
    def test_scalar_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--model-seed", "null"])
        assert exc_info.value.status == 2

    def test_where_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--where", "null"])
        assert exc_info.value.status == 2


class TestInvalidOutputChoice:
    def test_invalid_output_value_exits_2(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--list-experiments", "--output", "bogus"])
        assert exc_info.value.status == 2


class TestInvalidValue:
    def test_invalid_int_exits_2(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--model-seed", "not-a-number"])
        assert exc_info.value.status == 2

    def test_invalid_float_exits_2(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--temperature", "abc"])
        assert exc_info.value.status == 2

    def test_unrecognized_flag_exits_2(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--create-experiment", "exp1", "--bogus", "x"])
        assert exc_info.value.status == 2


class TestHelp:
    def test_help_raises_parser_exit_status_zero(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_experiment_argv(["--help"])
        assert exc_info.value.status == 0


class TestStderrMessageAlreadyPrinted:
    def test_forbidden_message_written_to_stderr(self, capsys):
        with pytest.raises(ParserExit):
            parse_experiment_argv(["--experiment", "system-default"])
        captured = capsys.readouterr()
        assert "system-default" in captured.err
