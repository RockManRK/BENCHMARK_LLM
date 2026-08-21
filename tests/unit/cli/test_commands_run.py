"""Tests for src/cli/commands/run.py — the Typer replacement for
bcllm_run.py's former argparse create_parser(), marco 4B first slice
(2026-08-20). Verifies parse_run_argv() behaves identically to the old
create_parser() + parse_args_normalized() (+ the extra
parse_randomization_seed_strict FORMAT check) for every flag/special
value/error case, before bcllm_run.py is wired to use it.
"""

from __future__ import annotations

import pytest

from src.cli.commands.run import parse_run_argv, RunParsedArgs
from src.core.argv_utils import ParserExit
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT


class TestValidInvocations:
    def test_add_run_minimal(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run"])
        assert isinstance(result, RunParsedArgs)
        assert result.experiment == "exp1"
        assert result.add_run is True
        assert result.list_runs is False
        assert result.run is None
        assert result.remove_run is None

    def test_list_runs(self):
        result = parse_run_argv(["--experiment", "exp1", "--list-runs"])
        assert result.list_runs is True

    def test_show_run(self):
        result = parse_run_argv(["--experiment", "exp1", "--run", "run_abc"])
        assert result.run == "run_abc"

    def test_remove_run(self):
        result = parse_run_argv(["--experiment", "exp1", "--remove-run", "run_abc"])
        assert result.remove_run == "run_abc"

    def test_randomization_seed_integer(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--randomization-seed", "42"])
        assert result.randomization_seed == "42"

    def test_randomization_seed_zero_preserved(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--randomization-seed", "0"])
        assert result.randomization_seed == "0"

    def test_randomization_seed_auto(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--randomization-seed", "AUTO"])
        assert result.randomization_seed == "AUTO"

    def test_randomization_seed_auto_lowercase(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--randomization-seed", "auto"])
        assert result.randomization_seed == "auto"

    def test_randomization_seed_system_default(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--randomization-seed", "system-default"])
        assert result.randomization_seed is FORCE_SYSTEM_DEFAULT

    def test_randomization_seed_absent_is_none(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run"])
        assert result.randomization_seed is None

    def test_system_prompt(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--system-prompt", "custom"])
        assert result.system_prompt == "custom"

    def test_user_prompt(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--user-prompt", "custom"])
        assert result.user_prompt == "custom"

    def test_output_default_console(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run"])
        assert result.output == "console"

    def test_output_explicit_json(self):
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--output", "json"])
        assert result.output == "json"


class TestMutexGroup:
    def test_none_given_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1"])
        assert exc_info.value.status == 2

    def test_two_given_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1", "--add-run", "--list-runs"])
        assert exc_info.value.status == 2

    def test_run_and_remove_run_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1", "--run", "run_x", "--remove-run", "run_x"])
        assert exc_info.value.status == 2


class TestForbiddenFlags:
    def test_experiment_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "system-default", "--list-runs"])
        assert exc_info.value.status == 2

    def test_experiment_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "null", "--list-runs"])
        assert exc_info.value.status == 2

    def test_run_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1", "--run", "system-default"])
        assert exc_info.value.status == 2

    def test_remove_run_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1", "--remove-run", "system-default"])
        assert exc_info.value.status == 2


class TestDeprecatedNull:
    def test_randomization_seed_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1", "--add-run", "--randomization-seed", "null"])
        assert exc_info.value.status == 2


class TestRandomizationSeedFormatValidation:
    """The extra FORMAT check parse_run_argv performs beyond scalar
    system-default normalization — mirrors
    ConfigResolver.parse_randomization_seed_strict's contract exactly."""

    def test_garbage_value_rejected_exit_2(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1", "--add-run", "--randomization-seed", "not-a-number"])
        assert exc_info.value.status == 2

    def test_empty_string_is_accepted_as_none_equivalent(self):
        """parse_randomization_seed_strict treats empty/whitespace-only
        as 'not specified' — must not be rejected as garbage."""
        result = parse_run_argv(["--experiment", "exp1", "--add-run", "--randomization-seed", ""])
        assert result.randomization_seed == ""


class TestInvalidOutputChoice:
    def test_invalid_output_value_exits_2(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1", "--list-runs", "--output", "bogus"])
        assert exc_info.value.status == 2


class TestUnrecognizedOption:
    def test_unrecognized_flag_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--experiment", "exp1", "--add-run", "--bogus", "x"])
        assert exc_info.value.status == 2


class TestMissingRequiredExperiment:
    def test_missing_experiment_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--add-run"])
        assert exc_info.value.status == 2


class TestHelp:
    def test_help_raises_parser_exit_status_zero(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_run_argv(["--help"])
        assert exc_info.value.status == 0


class TestStderrMessageAlreadyPrinted:
    def test_forbidden_message_written_to_stderr(self, capsys):
        with pytest.raises(ParserExit):
            parse_run_argv(["--experiment", "system-default", "--list-runs"])
        captured = capsys.readouterr()
        assert "system-default" in captured.err
