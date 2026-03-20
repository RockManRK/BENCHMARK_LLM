"""Unit tests for bcllm_model.py CLI module.

Tests cover all CLI commands:
- --add-model
- --list-models
- --remove-model

Test Pattern:
- Use capsys for output capture
- Use patch for mocking database connection
- Use in_memory_db fixture for integration tests
- Mark domain rules with @pytest.mark.domain_rule
"""

import pytest
import sys
from unittest.mock import patch

from src_v2.db import create_schema
from src_v2.db.repository import ExperimentRepository, VariantRepository
from src_v2.db.models import Experiment, ModelVariant
from tests.factories import ExperimentFactory, VariantFactory


# =============================================================================
# Test: --add-model
# =============================================================================

@pytest.mark.domain_rule
def test_add_model_success(in_memory_db, capsys):
    """--add-model creates variant and prints success with variant_id."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_model.py",
        "--experiment", "test-exp",
        "--add-model", "openai/gpt-4",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "added" in captured.out.lower()
            assert "openai/gpt-4" in captured.out


@pytest.mark.domain_rule
def test_add_model_experiment_not_found(in_memory_db, capsys):
    """--add-model fails with 'experiment not found' message."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    test_args = [
        "bcllm_model.py",
        "--experiment", "non-existent-exp",
        "--add-model", "openai/gpt-4",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_add_model_invalid_model_id_format(in_memory_db, capsys):
    """--add-model fails with 'invalid model ID format' message."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Invalid format: missing provider
    test_args = [
        "bcllm_model.py",
        "--experiment", "test-exp",
        "--add-model", "gpt-4",  # Missing provider/
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "invalid" in captured.err.lower()
            assert "model id" in captured.err.lower()


@pytest.mark.domain_rule
def test_add_model_variant_signature_collision(in_memory_db, capsys):
    """--add-model fails with 'variant already exists' on signature collision."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Pre-create variant with same signature
    variant = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",  # Auto-generated signature
    )
    _insert_variant(in_memory_db, variant)

    # Try to add same model again (will generate same signature)
    test_args = [
        "bcllm_model.py",
        "--experiment", "test-exp",
        "--add-model", "openai/gpt-4",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "already exists" in captured.err.lower()


# =============================================================================
# Test: --list-models
# =============================================================================

def test_list_models_empty(in_memory_db, capsys):
    """--list-models shows 'no models' message when empty."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_model.py",
        "--experiment", "test-exp",
        "--list-models",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "no models" in captured.out.lower()


@pytest.mark.domain_rule
def test_list_models_with_data(in_memory_db, capsys):
    """--list-models lists models in table format."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Pre-create variants
    var1 = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
        reasoning_mode="off",
        vision_enabled=False,
        structured_output=False,
    )
    var2 = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="anthropic/claude-3",
        variant_signature="anthropic_claude-3",
        reasoning_mode="effort",
        vision_enabled=True,
        structured_output=True,
    )
    _insert_variant(in_memory_db, var1)
    _insert_variant(in_memory_db, var2)

    test_args = [
        "bcllm_model.py",
        "--experiment", "test-exp",
        "--list-models",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "openai/gpt-4" in captured.out
            assert "anthropic/claude-3" in captured.out
            # Check table format (header row)
            assert "ID" in captured.out
            assert "Model" in captured.out
            assert "Mode" in captured.out
            assert "Vision" in captured.out


@pytest.mark.domain_rule
def test_list_models_for_experiment(in_memory_db, capsys):
    """--list-models filters by experiment."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create two experiments
    exp1 = ExperimentFactory.create(name="experiment-one")
    exp2 = ExperimentFactory.create(name="experiment-two")
    _insert_experiment(in_memory_db, exp1)
    _insert_experiment(in_memory_db, exp2)

    # Add variant to exp1 only
    var1 = VariantFactory.create(
        experiment_id=exp1.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
    )
    _insert_variant(in_memory_db, var1)

    # List models for exp2 (should be empty)
    test_args = [
        "bcllm_model.py",
        "--experiment", "experiment-two",
        "--list-models",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "no models" in captured.out.lower()
            assert "openai/gpt-4" not in captured.out


# =============================================================================
# Test: --remove-model
# =============================================================================

@pytest.mark.domain_rule
def test_remove_model_success(in_memory_db, capsys):
    """--remove-model soft deletes variant and prints confirmation."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Pre-create variant
    variant = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
    )
    _insert_variant(in_memory_db, variant)

    test_args = [
        "bcllm_model.py",
        "--experiment", "test-exp",
        "--remove-model", variant.variant_id,
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "removed" in captured.out.lower()
            assert "openai/gpt-4" in captured.out

            # Verify soft delete
            var_repo = VariantRepository(in_memory_db)
            retrieved = var_repo.get_by_id(variant.variant_id)
            assert retrieved is not None
            assert retrieved.is_active is False


@pytest.mark.domain_rule
def test_remove_model_not_found(in_memory_db, capsys):
    """--remove-model fails with 'variant not found' message."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create experiment (but no variant)
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_model.py",
        "--experiment", "test-exp",
        "--remove-model", "var-non-existent",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_remove_model_from_wrong_experiment(in_memory_db, capsys):
    """--remove-model fails if variant is not in specified experiment."""
    # Arrange
    from src_v2.cli.bcllm_model import main as model_main

    # Pre-create two experiments
    exp1 = ExperimentFactory.create(name="experiment-one")
    exp2 = ExperimentFactory.create(name="experiment-two")
    _insert_experiment(in_memory_db, exp1)
    _insert_experiment(in_memory_db, exp2)

    # Add variant to exp1
    variant = VariantFactory.create(
        experiment_id=exp1.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
    )
    _insert_variant(in_memory_db, variant)

    # Try to remove from exp2
    test_args = [
        "bcllm_model.py",
        "--experiment", "experiment-two",
        "--remove-model", variant.variant_id,
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = model_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower() or "not in experiment" in captured.err.lower()


# =============================================================================
# Integration Tests (without mocking)
# =============================================================================

class TestAddModelIntegration:
    """Integration tests for --add-model with real DB."""

    def test_add_and_list_model(self, in_memory_db, capsys):
        """Add model and verify it appears in list."""
        from src_v2.cli.bcllm_model import main as model_main

        # Pre-create experiment
        exp = ExperimentFactory.create(name="integration-test")
        _insert_experiment(in_memory_db, exp)

        # Add model
        add_args = [
            "bcllm_model.py",
            "--experiment", "integration-test",
            "--add-model", "openai/gpt-4",
        ]
        with patch.object(sys, "argv", add_args):
            with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = model_main()
                assert result == 0

        # List models
        capsys.readouterr()  # Clear previous output
        list_args = [
            "bcllm_model.py",
            "--experiment", "integration-test",
            "--list-models",
        ]
        with patch.object(sys, "argv", list_args):
            with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = model_main()
                assert result == 0
                captured = capsys.readouterr()
                assert "openai/gpt-4" in captured.out

    def test_add_duplicate_signature_fails(self, in_memory_db, capsys):
        """Adding model with duplicate signature fails."""
        from src_v2.cli.bcllm_model import main as model_main

        # Pre-create experiment
        exp = ExperimentFactory.create(name="duplicate-test")
        _insert_experiment(in_memory_db, exp)

        # Add first model
        add_args = [
            "bcllm_model.py",
            "--experiment", "duplicate-test",
            "--add-model", "openai/gpt-4",
        ]
        with patch.object(sys, "argv", add_args):
            with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = model_main()
                assert result == 0

        # Try to add same model again
        with patch.object(sys, "argv", add_args):
            with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = model_main()
                assert result == 1
                captured = capsys.readouterr()
                assert "already exists" in captured.err.lower()


class TestRemoveModelIntegration:
    """Integration tests for --remove-model with real DB."""

    def test_remove_then_list_excludes(self, in_memory_db, capsys):
        """Removed model should not appear in list."""
        from src_v2.cli.bcllm_model import main as model_main

        # Pre-create experiment
        exp = ExperimentFactory.create(name="remove-test")
        _insert_experiment(in_memory_db, exp)

        # Add model
        add_args = [
            "bcllm_model.py",
            "--experiment", "remove-test",
            "--add-model", "openai/gpt-4",
        ]
        with patch.object(sys, "argv", add_args):
            with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                model_main()

        # Get variant ID
        var_repo = VariantRepository(in_memory_db)
        variants = var_repo.list_by_experiment(exp.experiment_id)
        variant_id = variants[0].variant_id

        # Remove model
        remove_args = [
            "bcllm_model.py",
            "--experiment", "remove-test",
            "--remove-model", variant_id,
        ]
        with patch.object(sys, "argv", remove_args):
            with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                model_main()

        # Clear captured output before list
        capsys.readouterr()

        # List - should not show removed model
        list_args = [
            "bcllm_model.py",
            "--experiment", "remove-test",
            "--list-models",
        ]
        with patch.object(sys, "argv", list_args):
            with patch("src_v2.cli.bcllm_model.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = model_main()
                assert result == 0
                captured = capsys.readouterr()
                # Should show "no models" since the only model was removed
                assert "no models" in captured.out.lower()


# =============================================================================
# Helper Functions
# =============================================================================

def _insert_experiment(conn, experiment: Experiment) -> None:
    """Insert experiment directly into database."""
    repo = ExperimentRepository(conn)
    repo.save(experiment)


def _insert_variant(conn, variant: ModelVariant) -> None:
    """Insert variant directly into database."""
    repo = VariantRepository(conn)
    repo.save(variant)
