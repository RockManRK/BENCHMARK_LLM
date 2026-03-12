"""Unit tests for seed and finished_at fixes."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.core.run_manager import RunManager
from src.utils.config import Settings, ExecutionMode


class TestDetermineSeed:
    """Test the _determine_seed method."""

    @pytest.fixture
    def run_manager(self):
        """Create a RunManager instance for testing."""
        mock_db = MagicMock()
        settings = Settings(execution_mode=ExecutionMode.TEST)
        return RunManager(mock_db, settings)

    def test_seed_none_returns_none(self, run_manager):
        """Test that seed=None returns None."""
        config = {"seed": None}
        result = run_manager._determine_seed(config)
        assert result is None

    def test_seed_empty_string_returns_none(self, run_manager):
        """Test that seed="" returns None."""
        config = {"seed": ""}
        result = run_manager._determine_seed(config)
        assert result is None

    def test_seed_auto_generates_random(self, run_manager):
        """Test that seed="AUTO" generates a random integer."""
        config = {"seed": "AUTO"}
        result = run_manager._determine_seed(config)
        
        # Should return an integer
        assert isinstance(result, int)
        # Should be in valid range (0 to 2^31 - 1)
        assert 0 <= result < 2**31
        
        # Two calls should generate different seeds (most of the time)
        result2 = run_manager._determine_seed(config)
        # Note: There's a tiny chance they could be the same, but very unlikely
        # We're mainly testing that it generates valid integers

    def test_seed_int_uses_provided_value(self, run_manager):
        """Test that seed=123 uses the provided value."""
        config = {"seed": 123}
        result = run_manager._determine_seed(config)
        assert result == 123

    def test_seed_string_int_converts(self, run_manager):
        """Test that seed="456" converts to integer."""
        config = {"seed": "456"}
        result = run_manager._determine_seed(config)
        assert result == 456

    def test_seed_invalid_string_returns_none(self, run_manager):
        """Test that invalid seed strings return None."""
        config = {"seed": "invalid"}
        result = run_manager._determine_seed(config)
        assert result is None


class TestUpdateRunStatusFinishedAt:
    """Test that update_run_status sets finished_at correctly."""

    @pytest.fixture
    def run_manager(self):
        """Create a RunManager instance for testing."""
        mock_db = MagicMock()
        settings = Settings(execution_mode=ExecutionMode.TEST)
        manager = RunManager(mock_db, settings)
        
        # Mock repositories
        manager._run_repository = MagicMock()
        return manager

    def test_completed_status_sets_finished_at(self, run_manager):
        """Test that status='completed' sets finished_at."""
        # Create a mock run
        mock_run = MagicMock()
        mock_run.run_id = "run-test-1"
        mock_run.status = "running"
        mock_run.finished_at = None
        
        run_manager._run_repository.get_by_id.return_value = mock_run
        
        # Update status to completed
        result = run_manager.update_run_status("run-test-1", "completed")
        
        # Verify finished_at was set
        assert mock_run.finished_at is not None
        assert isinstance(mock_run.finished_at, datetime)
        # Verify update was called
        run_manager._run_repository.update.assert_called_once()

    def test_failed_status_sets_finished_at(self, run_manager):
        """Test that status='failed' sets finished_at."""
        mock_run = MagicMock()
        mock_run.run_id = "run-test-2"
        mock_run.status = "running"
        mock_run.finished_at = None
        
        run_manager._run_repository.get_by_id.return_value = mock_run
        
        result = run_manager.update_run_status("run-test-2", "failed")
        
        assert mock_run.finished_at is not None
        assert isinstance(mock_run.finished_at, datetime)

    def test_running_status_does_not_set_finished_at(self, run_manager):
        """Test that status='running' does NOT set finished_at."""
        mock_run = MagicMock()
        mock_run.run_id = "run-test-3"
        mock_run.status = "pending"
        mock_run.finished_at = None
        
        run_manager._run_repository.get_by_id.return_value = mock_run
        
        result = run_manager.update_run_status("run-test-3", "running")
        
        # finished_at should still be None
        assert mock_run.finished_at is None

    def test_finished_at_not_overwritten_if_already_set(self, run_manager):
        """Test that existing finished_at is not overwritten."""
        existing_time = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_run = MagicMock()
        mock_run.run_id = "run-test-4"
        mock_run.status = "running"
        mock_run.finished_at = existing_time
        
        run_manager._run_repository.get_by_id.return_value = mock_run
        
        result = run_manager.update_run_status("run-test-4", "completed")
        
        # Should keep the original finished_at
        assert mock_run.finished_at == existing_time


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
