"""Test the openrouter_debug_enabled warning behavior in EXPERIMENT mode."""

import logging
import pytest
from src.utils.config import Settings, ExecutionMode


class TestOpenRouterDebugEnabledWarning:
    """Test that openrouter_debug_enabled emits warning instead of ValueError in EXPERIMENT mode."""

    def test_debug_enabled_in_experiment_mode_emits_warning(self, caplog):
        """Test that enabling debug in EXPERIMENT mode emits a warning and continues."""
        with caplog.at_level(logging.WARNING):
            settings = Settings(
                openrouter_api_key="test_key",
                execution_mode=ExecutionMode.EXPERIMENT,
                experiment_name="test_experiment",
                openrouter_debug_enabled=True,
            )
            
            # Verify warning was logged
            assert "openrouter_debug_enabled is BLOCKED in EXPERIMENT mode" in caplog.text
            assert "Debug flag will be ignored" in caplog.text
            assert "Execution will continue without debug" in caplog.text
            
            # Verify debug was set to False
            assert settings.openrouter_debug_enabled is False
            
            # Verify execution mode is still EXPERIMENT
            assert settings.execution_mode == ExecutionMode.EXPERIMENT

    def test_debug_disabled_in_experiment_mode_no_warning(self, caplog):
        """Test that disabling debug in EXPERIMENT mode does not emit warning."""
        with caplog.at_level(logging.WARNING):
            settings = Settings(
                openrouter_api_key="test_key",
                execution_mode=ExecutionMode.EXPERIMENT,
                experiment_name="test_experiment",
                openrouter_debug_enabled=False,
            )
            
            # Verify no warning about debug
            assert "openrouter_debug_enabled is BLOCKED" not in caplog.text
            
            # Verify debug is False
            assert settings.openrouter_debug_enabled is False

    def test_debug_enabled_in_dev_mode_allowed(self, caplog):
        """Test that enabling debug in DEV mode is allowed (no warning)."""
        with caplog.at_level(logging.WARNING):
            settings = Settings(
                openrouter_api_key="test_key",
                execution_mode=ExecutionMode.DEV,
                openrouter_debug_enabled=True,
            )
            
            # Verify no warning about debug being blocked
            assert "openrouter_debug_enabled is BLOCKED" not in caplog.text
            
            # Verify debug is enabled
            assert settings.openrouter_debug_enabled is True

    def test_debug_enabled_in_test_mode_allowed(self, caplog):
        """Test that enabling debug in TEST mode is allowed (no warning)."""
        with caplog.at_level(logging.WARNING):
            settings = Settings(
                openrouter_api_key="test_key",
                execution_mode=ExecutionMode.TEST,
                openrouter_debug_enabled=True,
            )
            
            # Verify no warning about debug being blocked
            assert "openrouter_debug_enabled is BLOCKED" not in caplog.text
            
            # Verify debug is enabled
            assert settings.openrouter_debug_enabled is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
