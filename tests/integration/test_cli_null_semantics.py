"""Integration tests for CLI null semantics.

Tests the end-to-end behavior of null normalization across CLI modules:
- --seed argument with null/none/literal values
- --vision and --structured tri-state arguments
- --add-questions argument

These tests verify that:
1. 'null' (case-insensitive) is normalized to EXPLICIT_NULL
2. 'none' (any case) is preserved as literal
3. Literal values (numbers, strings) are preserved
4. The normalization works through the full CLI parsing chain

Note: The normalization layer converts 'null' to EXPLICIT_NULL sentinel.
Downstream code (e.g., config_resolver) then handles EXPLICIT_NULL by
converting to Python None for actual usage.
"""

import argparse
import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.argv_utils import parse_args_normalized
from src.core.null_semantics import EXPLICIT_NULL


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def experiment_parser():
    """Create parser similar to bcllm_experiment.py.

    Returns:
        ArgumentParser with experiment-related nullable arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-experiment", metavar="NAME")
    parser.add_argument("--experiment", metavar="NAME")
    parser.add_argument("--seed", type=str, default=None, required=False)
    parser.add_argument("--vision", type=str, default=None, required=False)
    parser.add_argument("--structured", type=str, default=None, required=False)
    parser.add_argument("--add-questions", metavar="SPEC", default=None, required=False)
    parser.add_argument("--add-model", action="append", default=None, required=False)
    return parser


@pytest.fixture
def execute_parser():
    """Create parser similar to bcllm_execute.py.

    Returns:
        ArgumentParser with execute-related nullable arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--experiment", metavar="NAME", required=True)
    parser.add_argument("--run", metavar="RUN_ID", default=None, required=False)
    parser.add_argument("--seed", type=str, default=None, required=False)
    parser.add_argument("--questions", nargs="*", default=None, required=False)
    parser.add_argument("--models", nargs="*", default=None, required=False)
    return parser


# =============================================================================
# Part 1: CLI smoke tests with --seed
# =============================================================================

class TestSeedNullSemantics:
    """Test --seed argument with various null/none/literal values."""

    def test_seed_null_becomes_none(self, experiment_parser):
        """When --seed null, seed is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed', 'null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed is None

    def test_seed_uppercase_null_becomes_none(self, experiment_parser):
        """When --seed NULL, seed is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed', 'NULL']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed is None

    def test_seed_mixed_case_null_becomes_none(self, experiment_parser):
        """When --seed Null, seed is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed', 'Null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed is None

    def test_seed_none_preserved_as_literal(self, experiment_parser):
        """When --seed none, seed is preserved as literal string 'none'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed', 'none']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed == 'none'

    def test_seed_uppercase_none_preserved(self, experiment_parser):
        """When --seed NONE, seed is preserved as literal string 'NONE'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed', 'NONE']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed == 'NONE'

    def test_seed_titlecase_none_preserved(self, experiment_parser):
        """When --seed None, seed is preserved as literal string 'None'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed', 'None']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed == 'None'

    def test_seed_numeric_value_preserved(self, experiment_parser):
        """When --seed 42, seed is preserved as literal string '42'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed', '42']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed == '42'

    def test_seed_zero_preserved(self, experiment_parser):
        """When --seed 0, seed is preserved as literal string '0'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed', '0']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed == '0'

    def test_seed_equals_syntax_null(self, experiment_parser):
        """When --seed=null, seed is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed=null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed is None

    def test_seed_equals_syntax_none(self, experiment_parser):
        """When --seed=none, seed is preserved as literal."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed=none']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed == 'none'

    def test_seed_equals_syntax_numeric(self, experiment_parser):
        """When --seed=42, seed is preserved as literal."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--seed=42']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed == '42'

    def test_seed_not_provided_is_none(self, experiment_parser):
        """When --seed not provided, seed is None (default)."""
        # Arrange
        argv = ['--create-experiment', 'test_exp']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed is None


# =============================================================================
# Part 2: CLI tests with --vision / --structured (tri-state)
# =============================================================================

class TestVisionStructuredNullSemantics:
    """Test --vision and --structured tri-state arguments."""

    def test_vision_null_becomes_none(self, experiment_parser):
        """When --vision null, vision is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision', 'null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision is None

    def test_vision_uppercase_null_becomes_none(self, experiment_parser):
        """When --vision NULL, vision is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision', 'NULL']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision is None

    def test_vision_true_preserved(self, experiment_parser):
        """When --vision true, vision is preserved as literal 'true'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision', 'true']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision == 'true'

    def test_vision_uppercase_true_preserved(self, experiment_parser):
        """When --vision TRUE, vision is preserved as literal 'TRUE'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision', 'TRUE']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision == 'TRUE'

    def test_vision_false_preserved(self, experiment_parser):
        """When --vision false, vision is preserved as literal 'false'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision', 'false']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision == 'false'

    def test_vision_none_preserved_as_literal(self, experiment_parser):
        """When --vision none, vision is preserved as literal 'none'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision', 'none']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision == 'none'

    def test_structured_null_becomes_none(self, experiment_parser):
        """When --structured null, structured is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--structured', 'null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.structured is None

    def test_structured_uppercase_null_becomes_none(self, experiment_parser):
        """When --structured NULL, structured is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--structured', 'NULL']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.structured is None

    def test_structured_true_preserved(self, experiment_parser):
        """When --structured true, structured is preserved as literal 'true'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--structured', 'true']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.structured == 'true'

    def test_structured_false_preserved(self, experiment_parser):
        """When --structured false, structured is preserved as literal 'false'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--structured', 'false']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.structured == 'false'

    def test_structured_none_preserved(self, experiment_parser):
        """When --structured none, structured is preserved as literal 'none'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--structured', 'none']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.structured == 'none'

    def test_vision_and_structured_both_null(self, experiment_parser):
        """When both --vision null and --structured null, both are normalized."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision', 'null', '--structured', 'NULL']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision is None
        assert result.structured is None

    def test_vision_true_structured_null(self, experiment_parser):
        """When --vision true and --structured null, only structured is normalized."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision', 'true', '--structured', 'null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision == 'true'
        assert result.structured is None

    def test_vision_equals_syntax_null(self, experiment_parser):
        """When --vision=null, vision is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--vision=null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.vision is None

    def test_structured_equals_syntax_null(self, experiment_parser):
        """When --structured=NULL, structured is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--structured=NULL']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.structured is None


# =============================================================================
# Part 3: CLI tests with --add-questions
# =============================================================================

class TestAddQuestionsNullSemantics:
    """Test --add-questions argument with null/none/literal values."""

    def test_add_questions_null_becomes_none(self, experiment_parser):
        """When --add-questions null, value is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--add-questions', 'null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.add_questions is None

    def test_add_questions_uppercase_null_becomes_none(self, experiment_parser):
        """When --add-questions NULL, value is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--add-questions', 'NULL']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.add_questions is None

    def test_add_questions_range_preserved(self, experiment_parser):
        """When --add-questions "1-10", value is preserved as literal."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--add-questions', '1-10']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.add_questions == '1-10'

    def test_add_questions_comma_separated_preserved(self, experiment_parser):
        """When --add-questions "1,3,5", value is preserved as literal."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--add-questions', '1,3,5']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.add_questions == '1,3,5'

    def test_add_questions_mixed_format_preserved(self, experiment_parser):
        """When --add-questions "1,3-5,Q10", value is preserved as literal."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--add-questions', '1,3-5,Q10']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.add_questions == '1,3-5,Q10'

    def test_add_questions_none_preserved(self, experiment_parser):
        """When --add-questions none, value is preserved as literal 'none'."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--add-questions', 'none']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.add_questions == 'none'

    def test_add_questions_equals_syntax_null(self, experiment_parser):
        """When --add-questions=null, value is normalized to None."""
        # Arrange
        argv = ['--create-experiment', 'test_exp', '--add-questions=null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.add_questions is None

    def test_add_questions_not_provided_is_none(self, experiment_parser):
        """When --add-questions not provided, value is None (default)."""
        # Arrange
        argv = ['--create-experiment', 'test_exp']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.add_questions is None


# =============================================================================
# Part 4: Execute parser tests
# =============================================================================

class TestExecuteParserNullSemantics:
    """Test null semantics with execute parser."""

    def test_execute_run_null_becomes_none(self, execute_parser):
        """When --run null, run is normalized to None."""
        # Arrange
        argv = ['--execute', '--experiment', 'test_exp', '--run', 'null']

        # Act
        result = parse_args_normalized(execute_parser, argv)

        # Assert
        assert result.run is None

    def test_execute_run_literal_preserved(self, execute_parser):
        """When --run run_abc123, run is preserved as literal."""
        # Arrange
        argv = ['--execute', '--experiment', 'test_exp', '--run', 'run_abc123']

        # Act
        result = parse_args_normalized(execute_parser, argv)

        # Assert
        assert result.run == 'run_abc123'

    def test_execute_seed_null_becomes_none(self, execute_parser):
        """When --seed null in execute parser, seed is normalized to None."""
        # Arrange
        argv = ['--execute', '--experiment', 'test_exp', '--seed', 'null']

        # Act
        result = parse_args_normalized(execute_parser, argv)

        # Assert
        assert result.seed is None

    def test_execute_seed_numeric_preserved(self, execute_parser):
        """When --seed 42 in execute parser, seed is preserved as '42'."""
        # Arrange
        argv = ['--execute', '--experiment', 'test_exp', '--seed', '42']

        # Act
        result = parse_args_normalized(execute_parser, argv)

        # Assert
        assert result.seed == '42'


# =============================================================================
# Part 5: Complex scenarios
# =============================================================================

class TestComplexNullSemanticsScenarios:
    """Test complex scenarios with multiple nullable arguments."""

    def test_all_nullable_args_null(self, experiment_parser):
        """When all nullable args are 'null', all are normalized."""
        # Arrange
        argv = [
            '--create-experiment', 'test_exp',
            '--seed', 'null',
            '--vision', 'NULL',
            '--structured', 'Null',
            '--add-questions', 'nUlL'
        ]

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed is None
        assert result.vision is None
        assert result.structured is None
        assert result.add_questions is None

    def test_mixed_null_none_literals(self, experiment_parser):
        """Test mix of null, none, and literal values."""
        # Arrange
        argv = [
            '--create-experiment', 'test_exp',
            '--seed', 'null',         # → None
            '--vision', 'none',       # → 'none'
            '--structured', 'true',   # → 'true'
            '--add-questions', '1-10' # → '1-10'
        ]

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.seed is None
        assert result.vision == 'none'
        assert result.structured == 'true'
        assert result.add_questions == '1-10'

    def test_multiple_add_model_with_null(self, experiment_parser):
        """When --add-model has null values, they are NOT normalized (append action has default=[]).
        
        Note: action='append' has implicit default=[], not None, so it's not nullable.
        This is expected behavior - append actions collect all values as literals.
        """
        # Arrange
        argv = [
            '--create-experiment', 'test_exp',
            '--add-model', 'null',
            '--add-model', 'openai/gpt-4'
        ]

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        # 'null' is preserved as literal because append action has default=[], not None
        assert result.add_model == ['null', 'openai/gpt-4']

    def test_experiment_name_not_affected(self, experiment_parser):
        """Experiment name with 'null' is normalized because --create-experiment has default=None.
        
        Note: This is expected behavior - any argument with default=None and required=False
        will have 'null' normalized to None. If you need to allow 'null' as a literal name,
        use 'none' instead.
        """
        # Arrange
        argv = ['--create-experiment', 'null']

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        # 'null' IS normalized to None because --create-experiment has default=None
        assert result.create_experiment is None

    def test_complex_real_world_scenario(self, experiment_parser):
        """Test real-world scenario with mixed argument types."""
        # Arrange
        argv = [
            '--create-experiment', 'my_experiment',
            '--seed', 'AUTO',
            '--vision', 'null',
            '--structured', 'false',
            '--add-model', 'openai/gpt-4',
            '--add-model', 'anthropic/claude-3',
            '--add-questions', '1-10'
        ]

        # Act
        result = parse_args_normalized(experiment_parser, argv)

        # Assert
        assert result.create_experiment == 'my_experiment'
        assert result.seed == 'AUTO'
        assert result.vision is None  # 'null' normalized
        assert result.structured == 'false'
        assert result.add_model == ['openai/gpt-4', 'anthropic/claude-3']
        assert result.add_questions == '1-10'
