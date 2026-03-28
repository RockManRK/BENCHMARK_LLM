"""Unit tests for mode resolver.

Tests the deterministic CLI mode resolution system.

The mode resolver's responsibility is to:
1. Inspect raw sys.argv (not parsed argparse namespace)
2. Apply explicit priority rules to determine MODE
3. Return a Mode enum value

Mode Resolution Rules (in priority order):
1. If --execute is present → Mode.EXECUTE
2. Else if --create-experiment is present → Mode.CREATE
3. Else if --experiment is present → Mode.MODIFY
4. Else → Mode.INVALID

Important constraints:
- --questions and --add-questions must NOT influence mode resolution
- Mode must be determined before interpreting any semantic arguments
- The resolver operates on raw argv strings, not parsed objects
"""

import pytest
from src.core.mode_resolver import resolve_mode
from src.core.mode import Mode


class TestModeResolverValidModes:
    """Test valid mode detection for each recognized flag."""

    def test_execute_flag_returns_execute_mode(self):
        """When --execute is present, resolver returns Mode.EXECUTE."""
        # Arrange
        argv = ["bcllm", "--execute"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_create_experiment_flag_returns_create_mode(self):
        """When --create-experiment is present (without --execute), resolver returns Mode.CREATE."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_create_experiment_with_value_returns_create_mode(self):
        """When --create-experiment has a value, resolver still returns Mode.CREATE."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "experiment_name"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_experiment_flag_returns_modify_mode(self):
        """When --experiment is present (without higher priority flags), resolver returns Mode.MODIFY."""
        # Arrange
        argv = ["bcllm", "--experiment", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY

    def test_experiment_with_value_returns_modify_mode(self):
        """When --experiment has a value, resolver still returns Mode.MODIFY."""
        # Arrange
        argv = ["bcllm", "--experiment", "existing_experiment"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY


class TestModeResolverPriority:
    """Test priority ordering when multiple mode flags are present."""

    def test_execute_over_create(self):
        """When both --execute and --create-experiment are present, EXECUTE wins (highest priority)."""
        # Arrange
        argv = ["bcllm", "--execute", "--create-experiment", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_execute_over_modify(self):
        """When both --execute and --experiment are present, EXECUTE wins (highest priority)."""
        # Arrange
        argv = ["bcllm", "--experiment", "my_exp", "--execute"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_create_over_modify(self):
        """When both --create-experiment and --experiment are present, CREATE wins (second priority)."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "my_exp", "--experiment", "other_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_execute_create_modify_all_present(self):
        """When all three mode flags are present, EXECUTE wins (highest priority)."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "new", "--experiment", "existing", "--execute"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_priority_order_execute_first(self):
        """When --execute appears first, it wins regardless of position of other flags."""
        # Arrange
        argv = ["bcllm", "--execute", "--experiment", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_priority_order_execute_last(self):
        """When --execute appears last, it wins regardless of position of other flags."""
        # Arrange
        argv = ["bcllm", "--experiment", "my_exp", "--create-experiment", "new", "--execute"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_priority_order_execute_middle(self):
        """When --execute appears in the middle, it wins regardless of position of other flags."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "new", "--execute", "--experiment", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_create_over_modify_create_first(self):
        """When --create-experiment appears before --experiment, CREATE wins."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "new", "--experiment", "existing"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_create_over_modify_create_last(self):
        """When --create-experiment appears after --experiment, CREATE still wins."""
        # Arrange
        argv = ["bcllm", "--experiment", "existing", "--create-experiment", "new"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE


class TestModeResolverInvalid:
    """Test invalid or missing mode scenarios."""

    def test_empty_argv_returns_invalid(self):
        """When argv contains only the script name, resolver returns Mode.INVALID."""
        # Arrange
        argv = ["bcllm"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_only_help_flag_returns_invalid(self):
        """When only --help is present (no mode flags), resolver returns Mode.INVALID."""
        # Arrange
        argv = ["bcllm", "--help"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_only_list_experiments_returns_invalid(self):
        """When only --list-experiments is present (no mode flags), resolver returns Mode.INVALID."""
        # Arrange
        argv = ["bcllm", "--list-experiments"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_only_version_flag_returns_invalid(self):
        """When only --version is present (no mode flags), resolver returns Mode.INVALID."""
        # Arrange
        argv = ["bcllm", "--version"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_unknown_flags_only_returns_invalid(self):
        """When only unknown flags are present (no mode flags), resolver returns Mode.INVALID."""
        # Arrange
        argv = ["bcllm", "--unknown-flag", "--another-unknown"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_empty_list_returns_invalid(self):
        """When argv is completely empty, resolver returns Mode.INVALID."""
        # Arrange
        argv = []

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID


class TestModeResolverNonModeFlags:
    """Test that non-mode flags don't affect mode resolution."""

    def test_experiment_with_add_model_returns_modify(self):
        """When --experiment is present with --add-model, resolver returns Mode.MODIFY."""
        # Arrange
        argv = ["bcllm", "--experiment", "my_exp", "--add-model", "google/gemini"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY

    def test_experiment_with_add_questions_returns_modify(self):
        """When --experiment is present with --add-questions, resolver returns Mode.MODIFY.
        
        This validates that --add-questions does NOT influence mode resolution.
        """
        # Arrange
        argv = ["bcllm", "--experiment", "my_exp", "--add-questions", "1-10"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY

    def test_execute_with_questions_returns_execute(self):
        """When --execute is present with --questions, resolver returns Mode.EXECUTE.
        
        This validates that --questions does NOT influence mode resolution.
        """
        # Arrange
        argv = ["bcllm", "--execute", "--questions", "Q001"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_create_experiment_with_multiple_non_mode_flags(self):
        """When --create-experiment is present with multiple non-mode flags, resolver returns Mode.CREATE."""
        # Arrange
        argv = [
            "bcllm",
            "--create-experiment", "new_exp",
            "--add-model", "openai/gpt-4",
            "--add-questions", "q1,q2,q3",
            "--verbose"
        ]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_experiment_with_list_questions_returns_modify(self):
        """When --experiment is present with --list-questions, resolver returns Mode.MODIFY."""
        # Arrange
        argv = ["bcllm", "--experiment", "my_exp", "--list-questions"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY

    def test_experiment_with_remove_model_returns_modify(self):
        """When --experiment is present with --remove-model, resolver returns Mode.MODIFY."""
        # Arrange
        argv = ["bcllm", "--experiment", "my_exp", "--remove-model", "openai/gpt-4"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY

    def test_execute_with_multiple_non_mode_flags(self):
        """When --execute is present with multiple non-mode flags, resolver returns Mode.EXECUTE."""
        # Arrange
        argv = [
            "bcllm",
            "--execute",
            "--experiment", "my_exp",  # This should not override --execute
            "--verbose",
            "--debug"
        ]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE


class TestModeResolverEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_experiment_as_value_for_other_flag(self):
        """When --experiment appears as a value for another flag, it should still be detected.
        
        Example: --add-model foo --experiment bar
        The resolver should detect --experiment and return Mode.MODIFY.
        """
        # Arrange
        argv = ["bcllm", "--add-model", "foo", "--experiment", "bar"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY

    def test_create_experiment_as_value_for_other_flag(self):
        """When --create-experiment appears as a value for another flag, it should still be detected."""
        # Arrange
        argv = ["bcllm", "--verbose", "--create-experiment", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_case_sensitivity_execute_uppercase(self):
        """When --EXECUTE (uppercase) is present, it should NOT match (case sensitive)."""
        # Arrange
        argv = ["bcllm", "--EXECUTE"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_case_sensitivity_create_uppercase(self):
        """When --CREATE-EXPERIMENT (uppercase) is present, it should NOT match (case sensitive)."""
        # Arrange
        argv = ["bcllm", "--CREATE-EXPERIMENT", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_case_sensitivity_mixed_case(self):
        """When --Execute (mixed case) is present, it should NOT match (case sensitive)."""
        # Arrange
        argv = ["bcllm", "--Execute"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_case_sensitivity_experiment_uppercase(self):
        """When --EXPERIMENT (uppercase) is present, it should NOT match (case sensitive)."""
        # Arrange
        argv = ["bcllm", "--EXPERIMENT", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_partial_flag_match_execute(self):
        """When --execute-now (partial match) is present, it should NOT match exact flag name."""
        # Arrange
        argv = ["bcllm", "--execute-now"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_partial_flag_match_create(self):
        """When --create-experiment-now (partial match) is present, it should NOT match exact flag name."""
        # Arrange
        argv = ["bcllm", "--create-experiment-now", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_partial_flag_match_experiment(self):
        """When --experiment-name (partial match) is present, it should NOT match exact flag name."""
        # Arrange
        argv = ["bcllm", "--experiment-name", "my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_flag_with_equals_sign(self):
        """When flag uses equals sign (--execute=true), it should still be detected."""
        # Arrange
        argv = ["bcllm", "--execute=true"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_flag_with_equals_sign_create(self):
        """When --create-experiment uses equals sign, it should still be detected."""
        # Arrange
        argv = ["bcllm", "--create-experiment=my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_flag_with_equals_sign_experiment(self):
        """When --experiment uses equals sign, it should still be detected."""
        # Arrange
        argv = ["bcllm", "--experiment=my_exp"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY

    def test_multiple_same_mode_flags(self):
        """When the same mode flag appears multiple times, resolver returns the correct mode."""
        # Arrange
        argv = ["bcllm", "--execute", "--execute"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_hyphen_variations(self):
        """When flag uses single hyphen (-execute), it should NOT match (requires double hyphen)."""
        # Arrange
        argv = ["bcllm", "-execute"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.INVALID

    def test_whitespace_in_argv(self):
        """When argv contains whitespace elements, resolver handles them correctly."""
        # Arrange
        argv = ["bcllm", "  ", "--execute", "  "]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE

    def test_unicode_in_flag_value(self):
        """When flag value contains unicode, resolver still detects the mode flag."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "实验名称"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_special_characters_in_flag_value(self):
        """When flag value contains special characters, resolver still detects the mode flag."""
        # Arrange
        argv = ["bcllm", "--experiment", "exp-with_special.chars"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.MODIFY

    def test_very_long_argv(self):
        """When argv contains many flags, resolver correctly identifies the mode."""
        # Arrange
        argv = [
            "bcllm",
            "--verbose", "--debug", "--color", "always",
            "--timeout", "300",
            "--create-experiment", "very_long_experiment_name",
            "--add-model", "openai/gpt-4",
            "--add-model", "anthropic/claude-3",
            "--add-questions", "q1,q2,q3,q4,q5",
            "--output-format", "json"
        ]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.CREATE

    def test_null_byte_in_argv(self):
        """When argv contains null bytes, resolver handles them gracefully."""
        # Arrange
        argv = ["bcllm\x00", "--execute"]

        # Act
        result = resolve_mode(argv)

        # Assert
        assert result == Mode.EXECUTE
