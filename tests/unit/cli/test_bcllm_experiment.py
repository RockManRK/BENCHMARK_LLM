"""Unit tests for bcllm_experiment.py CLI module.

Tests cover all CLI commands:
- --create-experiment
- --experiment (show details)
- --list-experiments
- --remove-experiment

Test Pattern:
- Use capsys for output capture
- Use patch for mocking database connection
- Use in_memory_db fixture for integration tests
- Mark domain rules with @pytest.mark.domain_rule
"""

import pytest
import sys
from io import StringIO
from unittest.mock import patch, MagicMock
from unittest.mock import PropertyMock

from src.core.mode import Mode
from src.db import create_schema
from src.db.repository import ExperimentRepository
from src.db.models import Experiment
from tests.factories import ExperimentFactory


# =============================================================================
# Test: --create-experiment
# =============================================================================

@pytest.mark.domain_rule
def test_create_experiment_success(in_memory_db, capsys):
    """--create-experiment creates experiment and prints success message."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    test_args = ["bcllm_experiment.py", "--create-experiment", "test-exp"]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.CREATE)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "created" in captured.out.lower()
            assert "test-exp" in captured.out


@pytest.mark.domain_rule
def test_create_experiment_name_collision(in_memory_db, capsys):
    """--create-experiment fails with 'already exists' message on collision."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    # Pre-create experiment using repository directly
    repo = ExperimentRepository(in_memory_db)
    experiment = Experiment(
        experiment_id="exp-test-collision",
        name="test-exp",
        description="",
        config_json="{}",
        config_hash="",
        system_prompt="You are a helpful assistant.",
        user_prompt="Answer the following question.",
    )
    repo.save(experiment)
    
    test_args = ["bcllm_experiment.py", "--create-experiment", "test-exp"]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.CREATE)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "already exists" in captured.err.lower()


def test_create_experiment_invalid_name(in_memory_db, capsys):
    """--create-experiment fails with validation message for invalid name."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    # Empty name should fail
    test_args = ["bcllm_experiment.py", "--create-experiment", ""]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.CREATE)

            # Assert
            # Empty name should fail argparse validation or business logic
            # Either way, it should not succeed
            assert result != 0


# =============================================================================
# Test: --experiment (show details)
# =============================================================================

@pytest.mark.domain_rule
def test_show_experiment_success(in_memory_db, capsys):
    """--experiment shows experiment details."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    # Pre-create experiment
    repo = ExperimentRepository(in_memory_db)
    experiment = Experiment(
        experiment_id="exp-test-show",
        name="test-exp",
        description="",
        config_json="{}",
        config_hash="",
        system_prompt="Test system prompt",
        user_prompt="Answer the question.",
    )
    repo.save(experiment)
    
    test_args = ["bcllm_experiment.py", "--experiment", "test-exp"]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.MODIFY)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "test-exp" in captured.out
            assert "Test system prompt" in captured.out


@pytest.mark.domain_rule
def test_show_experiment_not_found(in_memory_db, capsys):
    """--experiment fails with 'not found' message."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    test_args = ["bcllm_experiment.py", "--experiment", "non-existent-exp"]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.MODIFY)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()


# =============================================================================
# Test: --list-experiments
# =============================================================================

def test_list_experiments_empty(in_memory_db, capsys):
    """--list-experiments shows 'no experiments' message when empty."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    test_args = ["bcllm_experiment.py", "--list-experiments"]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.INVALID)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "no experiments found" in captured.out.lower()


@pytest.mark.domain_rule
def test_list_experiments_with_data(in_memory_db, capsys):
    """--list-experiments lists experiments in table format."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    # Pre-create experiments
    repo = ExperimentRepository(in_memory_db)
    exp1 = Experiment(
        experiment_id="exp-one",
        name="experiment-one",
        description="",
        config_json="{}",
        config_hash="",
        system_prompt="System prompt 1",
        user_prompt="User prompt 1",
    )
    exp2 = Experiment(
        experiment_id="exp-two",
        name="experiment-two",
        description="",
        config_json="{}",
        config_hash="",
        system_prompt="System prompt 2",
        user_prompt="User prompt 2",
    )
    repo.save(exp1)
    repo.save(exp2)
    
    test_args = ["bcllm_experiment.py", "--list-experiments"]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.INVALID)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "experiment-one" in captured.out
            assert "experiment-two" in captured.out
            # Check table format (header row)
            assert "Name" in captured.out
            assert "ID" in captured.out


# =============================================================================
# Test: --remove-experiment
# =============================================================================

@pytest.mark.domain_rule
def test_remove_experiment_success(in_memory_db, capsys):
    """--remove-experiment soft deletes and prints confirmation."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    # Pre-create experiment
    repo = ExperimentRepository(in_memory_db)
    experiment = Experiment(
        experiment_id="exp-to-remove",
        name="test-exp-to-remove",
        description="",
        config_json="{}",
        config_hash="",
        system_prompt="You are a helpful assistant.",
        user_prompt="Answer the following question.",
    )
    repo.save(experiment)
    
    test_args = ["bcllm_experiment.py", "--remove-experiment", "test-exp-to-remove"]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.CREATE)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "removed" in captured.out.lower()
            assert "test-exp-to-remove" in captured.out

            # Verify soft delete (experiment still exists but is inactive)
            retrieved = repo.get_by_name("test-exp-to-remove")
            assert retrieved is not None
            assert retrieved.is_active is False


@pytest.mark.domain_rule
def test_remove_experiment_not_found(in_memory_db, capsys):
    """--remove-experiment fails with 'not found' message."""
    # Arrange
    from src.cli.bcllm_experiment import main as experiment_main
    
    test_args = ["bcllm_experiment.py", "--remove-experiment", "non-existent-exp"]
    
    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            
            # Act
            result = experiment_main(Mode.CREATE)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()


# =============================================================================
# Integration Tests (without mocking)
# =============================================================================

class TestCreateExperimentIntegration:
    """Integration tests for --create-experiment with real DB."""
    
    def test_create_and_retrieve(self, in_memory_db, capsys):
        """Create experiment and verify it can be retrieved."""
        from src.cli.bcllm_experiment import main as experiment_main

        # Create
        create_args = ["bcllm_experiment.py", "--create-experiment", "integration-test"]
        with patch.object(sys, "argv", create_args):
            with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = experiment_main(Mode.CREATE)
                assert result == 0

        # Retrieve
        show_args = ["bcllm_experiment.py", "--experiment", "integration-test"]
        with patch.object(sys, "argv", show_args):
            with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = experiment_main(Mode.MODIFY)
                assert result == 0
                captured = capsys.readouterr()
                assert "integration-test" in captured.out

    def test_create_duplicate_fails(self, in_memory_db, capsys):
        """Creating duplicate experiment fails."""
        from src.cli.bcllm_experiment import main as experiment_main

        # Create first
        create_args = ["bcllm_experiment.py", "--create-experiment", "duplicate-test"]
        with patch.object(sys, "argv", create_args):
            with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = experiment_main(Mode.CREATE)
                assert result == 0

        # Try to create duplicate
        with patch.object(sys, "argv", create_args):
            with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = experiment_main(Mode.CREATE)
                assert result == 1
                captured = capsys.readouterr()
                assert "already exists" in captured.err.lower()


class TestRemoveExperimentIntegration:
    """Integration tests for --remove-experiment with real DB."""
    
    def test_remove_then_list_excludes(self, in_memory_db, capsys):
        """Removed experiment should not appear in list."""
        from src.cli.bcllm_experiment import main as experiment_main

        # Create
        create_args = ["bcllm_experiment.py", "--create-experiment", "to-be-removed"]
        with patch.object(sys, "argv", create_args):
            with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                experiment_main(Mode.CREATE)

        # Remove
        remove_args = ["bcllm_experiment.py", "--remove-experiment", "to-be-removed"]
        with patch.object(sys, "argv", remove_args):
            with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                experiment_main(Mode.CREATE)

        # Clear captured output before list
        capsys.readouterr()

        # List - should not show removed experiment
        list_args = ["bcllm_experiment.py", "--list-experiments"]
        with patch.object(sys, "argv", list_args):
            with patch("src.cli.bcllm_experiment.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = experiment_main(Mode.INVALID)
                assert result == 0
                captured = capsys.readouterr()
                assert "to-be-removed" not in captured.out
