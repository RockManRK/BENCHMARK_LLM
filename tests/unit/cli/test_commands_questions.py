"""Tests for src/cli/commands/questions.py — the Typer replacement for
bcllm_questions.py's former argparse create_parser(), marco 4A
(2026-08-20). Verifies parse_questions_argv() behaves identically to the
old create_parser() + parse_args_normalized() for every flag/special
value/error case, before bcllm_questions.py is wired to use it.
"""

from __future__ import annotations

import pytest

from src.cli.commands.questions import parse_questions_argv, QuestionsParsedArgs
from src.core.argv_utils import ParserExit
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT


class TestValidInvocations:
    def test_add_questions_minimal(self):
        result = parse_questions_argv(["--experiment", "exp1", "--add-questions", "1-5"])
        assert isinstance(result, QuestionsParsedArgs)
        assert result.experiment == "exp1"
        assert result.add_questions == "1-5"
        assert result.list_questions is False
        assert result.remove_question is None

    def test_questions_alias(self):
        result = parse_questions_argv(["--experiment", "exp1", "--questions", "1-5"])
        assert result.add_questions == "1-5"

    def test_list_questions(self):
        result = parse_questions_argv(["--experiment", "exp1", "--list-questions"])
        assert result.list_questions is True
        assert result.add_questions is None
        assert result.remove_question is None

    def test_remove_question(self):
        result = parse_questions_argv(["--experiment", "exp1", "--remove-question", "snap_abc"])
        assert result.remove_question == "snap_abc"

    def test_where_exclude_concrete_filters(self):
        result = parse_questions_argv([
            "--experiment", "exp1", "--add-questions", "1-5",
            "--where", "status=valid", "--exclude", "status=annulled",
        ])
        assert result.where == ["status=valid"]
        assert result.exclude == ["status=annulled"]

    def test_where_repeated(self):
        result = parse_questions_argv([
            "--experiment", "exp1", "--add-questions", "1-5",
            "--where", "a=1", "--where", "b=2",
        ])
        assert result.where == ["a=1", "b=2"]

    def test_where_absent_defaults_to_empty_list(self):
        result = parse_questions_argv(["--experiment", "exp1", "--add-questions", "1-5"])
        assert result.where == []
        assert result.exclude == []

    def test_add_questions_system_default(self):
        result = parse_questions_argv(["--experiment", "exp1", "--add-questions", "system-default"])
        assert result.add_questions is FORCE_SYSTEM_DEFAULT

    def test_where_system_default(self):
        result = parse_questions_argv([
            "--experiment", "exp1", "--add-questions", "1-5", "--where", "system-default",
        ])
        assert result.where is FORCE_SYSTEM_DEFAULT

    def test_source_file(self):
        result = parse_questions_argv([
            "--experiment", "exp1", "--add-questions", "1-5", "--source-file", "/tmp/x.json",
        ])
        assert result.source_file == "/tmp/x.json"

    def test_source_file_absent_is_none(self):
        result = parse_questions_argv(["--experiment", "exp1", "--add-questions", "1-5"])
        assert result.source_file is None

    def test_output_default_console(self):
        result = parse_questions_argv(["--experiment", "exp1", "--add-questions", "1-5"])
        assert result.output == "console"

    def test_output_explicit_json(self):
        result = parse_questions_argv([
            "--experiment", "exp1", "--add-questions", "1-5", "--output", "json",
        ])
        assert result.output == "json"


class TestMutexGroup:
    def test_none_given_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "exp1"])
        assert exc_info.value.status == 2

    def test_two_given_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "exp1", "--add-questions", "1-5", "--list-questions"])
        assert exc_info.value.status == 2

    def test_alias_spelling_counts_as_the_same_action_not_a_different_one(self):
        """--questions is an alias of --add-questions, not a distinct
        group member — using the alias spelling with --list-questions
        must still be detected as two group members given (mutex
        violation), exactly as if --add-questions had been spelled out."""
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "exp1", "--questions", "1-5", "--list-questions"])
        assert exc_info.value.status == 2

    def test_alias_spelling_alone_satisfies_the_required_group_normally(self):
        """Non-regression: the alias by itself is a perfectly valid,
        single group member — must NOT be mistaken for "zero given"."""
        result = parse_questions_argv(["--experiment", "exp1", "--questions", "1-5"])
        assert result.add_questions == "1-5"

    def test_add_questions_and_remove_question_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv([
                "--experiment", "exp1", "--add-questions", "1-5", "--remove-question", "snap_x",
            ])
        assert exc_info.value.status == 2


class TestForbiddenExperimentAndOthers:
    def test_experiment_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "system-default", "--list-questions"])
        assert exc_info.value.status == 2

    def test_experiment_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "null", "--list-questions"])
        assert exc_info.value.status == 2

    def test_remove_question_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "exp1", "--remove-question", "system-default"])
        assert exc_info.value.status == 2

    def test_source_file_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv([
                "--experiment", "exp1", "--add-questions", "1-5", "--source-file", "system-default",
            ])
        assert exc_info.value.status == 2


class TestFilterContradiction:
    def test_system_default_combined_with_concrete_filter(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv([
                "--experiment", "exp1", "--add-questions", "1-5",
                "--where", "system-default", "--where", "status=valid",
            ])
        assert exc_info.value.status == 2


class TestDeprecatedNull:
    def test_add_questions_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "exp1", "--add-questions", "null"])
        assert exc_info.value.status == 2

    def test_where_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv([
                "--experiment", "exp1", "--add-questions", "1-5", "--where", "null",
            ])
        assert exc_info.value.status == 2


class TestInvalidOutputChoice:
    def test_invalid_output_value_exits_2(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "exp1", "--list-questions", "--output", "bogus"])
        assert exc_info.value.status == 2


class TestUnrecognizedOption:
    def test_unrecognized_flag_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "exp1", "--add-questions", "1-5", "--bogus", "x"])
        assert exc_info.value.status == 2


class TestMissingRequiredExperiment:
    def test_missing_experiment_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--add-questions", "1-5"])
        assert exc_info.value.status == 2


class TestHelp:
    def test_help_raises_parser_exit_status_zero(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--help"])
        assert exc_info.value.status == 0


class TestStderrMessageAlreadyPrinted:
    def test_forbidden_message_written_to_stderr(self, capsys):
        with pytest.raises(ParserExit):
            parse_questions_argv(["--experiment", "system-default", "--list-questions"])
        captured = capsys.readouterr()
        assert "system-default" in captured.err
