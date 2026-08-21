"""Tests for src/cli/commands/provider.py — the Typer replacement for
bcllm_provider.py's former argparse create_parser(), marco 4C first slice
(2026-08-21). Verifies parse_provider_argv() behaves identically to the
old create_parser() + parse_args_normalized() for every flag/special
value/error case, before bcllm_provider.py is wired to use it.

Smallest module converted so far (2 flags, no numeric/list-typed
options, no mutex group — --resolve-providers is a plain optional
boolean, not part of a required-one-of set).
"""

from __future__ import annotations

import pytest

from src.cli.commands.provider import parse_provider_argv, ProviderParsedArgs
from src.core.argv_utils import ParserExit


class TestValidInvocations:
    def test_resolve_providers_minimal(self):
        result = parse_provider_argv(["--experiment", "exp1", "--resolve-providers"])
        assert isinstance(result, ProviderParsedArgs)
        assert result.experiment == "exp1"
        assert result.resolve_providers is True

    def test_resolve_providers_absent_defaults_false(self):
        result = parse_provider_argv(["--experiment", "exp1"])
        assert result.resolve_providers is False


class TestForbiddenFlags:
    def test_experiment_system_default_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_provider_argv(["--experiment", "system-default", "--resolve-providers"])
        assert exc_info.value.status == 2

    def test_experiment_null_rejected(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_provider_argv(["--experiment", "null", "--resolve-providers"])
        assert exc_info.value.status == 2


class TestUnrecognizedOption:
    def test_unrecognized_flag_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_provider_argv(["--experiment", "exp1", "--bogus", "x"])
        assert exc_info.value.status == 2


class TestMissingRequiredExperiment:
    def test_missing_experiment_is_usage_error(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_provider_argv(["--resolve-providers"])
        assert exc_info.value.status == 2


class TestHelp:
    def test_help_raises_parser_exit_status_zero(self):
        with pytest.raises(ParserExit) as exc_info:
            parse_provider_argv(["--help"])
        assert exc_info.value.status == 0


class TestStderrMessageAlreadyPrinted:
    def test_forbidden_message_written_to_stderr(self, capsys):
        with pytest.raises(ParserExit):
            parse_provider_argv(["--experiment", "system-default", "--resolve-providers"])
        captured = capsys.readouterr()
        assert "system-default" in captured.err
