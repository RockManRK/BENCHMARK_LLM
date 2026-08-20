"""Tests for the CLI presentation foundation (Typer migration Fase 2).

Verifies:
- Importing the new layer has zero side effects (no output, no DB
  connection, no logging reconfiguration) — see
  docs/contracts/interaction-contracts.md Section 2 and the Fase 2
  conditions in the CLI migration plan.
- The pieces that do exist (Console singletons, semantic theme, exit-code
  wrapper, Typer nullable-value callbacks) behave correctly in isolation,
  with no command wired to them yet.
"""

import importlib
import sys

import pytest


IMPORT_TARGETS = [
    "src.cli.presentation",
    "src.cli.presentation.console",
    "src.cli.presentation.theme",
    "src.cli.presentation.errors",
    "src.cli.param_types",
]


@pytest.mark.parametrize("module_name", IMPORT_TARGETS)
def test_import_produces_no_output(module_name, capsys, monkeypatch):
    """Importing any presentation-foundation module prints nothing."""
    for name in list(sys.modules):
        if name == module_name or name.startswith(module_name + "."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    importlib.import_module(module_name)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize("module_name", IMPORT_TARGETS)
def test_import_does_not_touch_database(module_name, monkeypatch):
    """Importing any presentation-foundation module never calls sqlite3.connect."""
    import sqlite3

    def _fail_connect(*args, **kwargs):
        raise AssertionError(f"sqlite3.connect() called while importing {module_name}")

    monkeypatch.setattr(sqlite3, "connect", _fail_connect)

    for name in list(sys.modules):
        if name == module_name or name.startswith(module_name + "."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", IMPORT_TARGETS)
def test_import_does_not_reconfigure_logging(module_name, monkeypatch):
    """Importing any presentation-foundation module never touches root logger handlers."""
    import logging

    root = logging.getLogger()
    handlers_before = list(root.handlers)
    level_before = root.level

    for name in list(sys.modules):
        if name == module_name or name.startswith(module_name + "."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    importlib.import_module(module_name)

    assert root.handlers == handlers_before
    assert root.level == level_before


class TestTheme:
    def test_semantic_theme_defines_the_four_basic_styles(self):
        from src.cli.presentation.theme import SEMANTIC_THEME

        for name in ("success", "warning", "error", "info"):
            assert SEMANTIC_THEME.styles.get(name) is not None, f"missing style: {name}"


class TestConsole:
    def test_console_and_error_console_are_distinct_singletons(self):
        from src.cli.presentation.console import console, error_console

        assert console is not error_console
        assert error_console.stderr is True

    def test_console_uses_the_semantic_theme(self):
        from src.cli.presentation.console import console

        assert console.get_style("success") is not None


class TestRunCommand:
    def test_normal_return_passes_through(self):
        from src.cli.presentation.errors import run_command, EXIT_SUCCESS

        assert run_command(lambda: EXIT_SUCCESS) == EXIT_SUCCESS

    def test_domain_error_return_passes_through(self):
        from src.cli.presentation.errors import run_command, EXIT_DOMAIN_ERROR

        assert run_command(lambda: EXIT_DOMAIN_ERROR) == EXIT_DOMAIN_ERROR

    def test_keyboard_interrupt_maps_to_130(self):
        from src.cli.presentation.errors import run_command, EXIT_INTERRUPTED

        def _raises():
            raise KeyboardInterrupt()

        assert run_command(_raises) == EXIT_INTERRUPTED

    def test_does_not_catch_usage_errors_or_any_other_exception(self):
        """run_command must never convert a usage error (or anything else)
        into EXIT_DOMAIN_ERROR — exit code 2 is Typer/Click's own job,
        raised during argument parsing, before this function ever runs.
        This only proves the wrapper itself has no bare `except Exception`;
        the end-to-end "a bad argument on a real command exits 2" case
        needs an actual Typer app and is deferred to Fase 4 marco 4A (see
        the docstring of run_command)."""
        import typer
        from src.cli.presentation.errors import run_command

        def _raises_bad_parameter():
            raise typer.BadParameter("bad value")

        with pytest.raises(typer.BadParameter):
            run_command(_raises_bad_parameter)

        def _raises_arbitrary():
            raise ValueError("not a usage error, not a KeyboardInterrupt")

        with pytest.raises(ValueError):
            run_command(_raises_arbitrary)


class TestTyperSystemDefaultParsers:
    def test_int_accepts_system_default(self):
        from src.cli.param_types import typer_int_or_system_default
        from src.core.special_config_values import FORCE_SYSTEM_DEFAULT

        assert typer_int_or_system_default("system-default") is FORCE_SYSTEM_DEFAULT
        assert typer_int_or_system_default("SYSTEM-DEFAULT") is FORCE_SYSTEM_DEFAULT

    def test_int_accepts_none_passthrough(self):
        from src.cli.param_types import typer_int_or_system_default

        assert typer_int_or_system_default(None) is None

    def test_int_parses_valid_integer(self):
        from src.cli.param_types import typer_int_or_system_default

        assert typer_int_or_system_default("42") == 42

    def test_int_rejects_deprecated_null(self):
        import typer
        from src.cli.param_types import typer_int_or_system_default

        with pytest.raises(typer.BadParameter):
            typer_int_or_system_default("null")

    def test_int_rejects_garbage(self):
        import typer
        from src.cli.param_types import typer_int_or_system_default

        with pytest.raises(typer.BadParameter):
            typer_int_or_system_default("not-a-number")

    def test_float_parses_valid_float(self):
        from src.cli.param_types import typer_float_or_system_default

        assert typer_float_or_system_default("0.7") == 0.7

    def test_float_accepts_system_default(self):
        from src.cli.param_types import typer_float_or_system_default
        from src.core.special_config_values import FORCE_SYSTEM_DEFAULT

        assert typer_float_or_system_default("system-default") is FORCE_SYSTEM_DEFAULT

    def test_str_preserves_none_literal(self):
        """'none' is a valid reasoning_effort value — must NOT become FORCE_SYSTEM_DEFAULT or None."""
        from src.cli.param_types import typer_str_or_system_default

        assert typer_str_or_system_default("none") == "none"

    def test_str_accepts_system_default(self):
        from src.cli.param_types import typer_str_or_system_default
        from src.core.special_config_values import FORCE_SYSTEM_DEFAULT

        assert typer_str_or_system_default("system-default") is FORCE_SYSTEM_DEFAULT

    def test_str_rejects_deprecated_null(self):
        import typer
        from src.cli.param_types import typer_str_or_system_default

        with pytest.raises(typer.BadParameter):
            typer_str_or_system_default("null")
