"""Unit tests for module resolver.

Tests the CLI module resolution system that maps raw sys.argv to module names.

Module Resolution Rules:
- Flags are mapped to specific modules (experiment, model, questions, run, execute, review, main)
- --help / -h takes highest priority → bcllm_main
- First matching flag wins for same-priority flags (left-to-right scanning)
- Case-sensitive matching (--EXECUTE does NOT match --execute)
- Supports both space-separated (--experiment my_exp) and equals-separated (--experiment=my_exp)

Test Coverage:
- Valid module detection for each module type
- Priority ordering (help > everything else)
- First-match-wins behavior
- Invalid/missing module handling
- Edge cases (equals syntax, case sensitivity, values)
"""

import pytest
from src.core.module_resolver import resolve_module


class TestModuleResolverExperiment:
    """Test experiment module detection.
    
    Validates that all experiment-related flags correctly resolve to 'bcllm_experiment'.
    """
    
    def test_create_experiment_flag(self):
        """--create-experiment resolves to bcllm_experiment."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "my_exp"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
    
    def test_experiment_flag_with_value(self):
        """--experiment with value resolves to bcllm_experiment."""
        # Arrange
        argv = ["bcllm", "--experiment", "my_exp"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
    
    def test_experiment_flag_with_equals(self):
        """--experiment=value resolves to bcllm_experiment."""
        # Arrange
        argv = ["bcllm", "--experiment=my_exp"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
    
    def test_list_experiments_flag(self):
        """--list-experiments resolves to bcllm_experiment."""
        # Arrange
        argv = ["bcllm", "--list-experiments"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
    
    def test_remove_experiment_flag(self):
        """--remove-experiment resolves to bcllm_experiment."""
        # Arrange
        argv = ["bcllm", "--remove-experiment", "my_exp"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"


class TestModuleResolverModel:
    """Test model module detection.
    
    Validates that all model-related flags correctly resolve to 'bcllm_model'.
    """
    
    def test_add_model_flag(self):
        """--add-model resolves to bcllm_model."""
        # Arrange
        argv = ["bcllm", "--add-model", "openai/gpt-4"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_model"
    
    def test_list_models_flag(self):
        """--list-models resolves to bcllm_model."""
        # Arrange
        argv = ["bcllm", "--list-models"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_model"
    
    def test_remove_model_flag(self):
        """--remove-model resolves to bcllm_model."""
        # Arrange
        argv = ["bcllm", "--remove-model", "openai/gpt-4"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_model"


class TestModuleResolverQuestions:
    """Test questions module detection.
    
    Validates that all questions-related flags correctly resolve to 'bcllm_questions'.
    """
    
    def test_add_questions_flag(self):
        """--add-questions resolves to bcllm_questions."""
        # Arrange
        argv = ["bcllm", "--add-questions"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_questions"
    
    def test_questions_flag(self):
        """--questions resolves to bcllm_questions."""
        # Arrange
        argv = ["bcllm", "--questions"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_questions"
    
    def test_list_questions_flag(self):
        """--list-questions resolves to bcllm_questions."""
        # Arrange
        argv = ["bcllm", "--list-questions"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_questions"
    
    def test_remove_question_flag(self):
        """--remove-question resolves to bcllm_questions."""
        # Arrange
        argv = ["bcllm", "--remove-question", "q1"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_questions"


class TestModuleResolverRun:
    """Test run module detection.
    
    Validates that all run-related flags correctly resolve to 'bcllm_run'.
    """
    
    def test_add_run_flag(self):
        """--add-run resolves to bcllm_run."""
        # Arrange
        argv = ["bcllm", "--add-run", "run-001"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_run"
    
    def test_create_run_flag(self):
        """--create-run resolves to bcllm_run."""
        # Arrange
        argv = ["bcllm", "--create-run", "run-001"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_run"
    
    def test_list_runs_flag(self):
        """--list-runs resolves to bcllm_run."""
        # Arrange
        argv = ["bcllm", "--list-runs"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_run"
    
    def test_run_flag_with_value(self):
        """--run with value resolves to bcllm_run."""
        # Arrange
        argv = ["bcllm", "--run", "run-001"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_run"
    
    def test_run_flag_with_equals(self):
        """--run=value resolves to bcllm_run."""
        # Arrange
        argv = ["bcllm", "--run=run-001"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_run"
    
    def test_remove_run_flag(self):
        """--remove-run resolves to bcllm_run."""
        # Arrange
        argv = ["bcllm", "--remove-run", "run-001"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_run"


class TestModuleResolverExecute:
    """Test execute module detection.
    
    Validates that --execute correctly resolves to 'bcllm_execute'.
    """
    
    def test_execute_flag(self):
        """--execute resolves to bcllm_execute."""
        # Arrange
        argv = ["bcllm", "--execute"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_execute"


class TestModuleResolverReview:
    """Test review module detection.
    
    Validates that all review-related flags correctly resolve to 'bcllm_review'.
    """
    
    def test_review_experiment_flag(self):
        """--review-experiment resolves to bcllm_review."""
        # Arrange
        argv = ["bcllm", "--review-experiment"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_review"
    
    def test_review_all_flag(self):
        """--review-all resolves to bcllm_review."""
        # Arrange
        argv = ["bcllm", "--review-all"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_review"


class TestModuleResolverMain:
    """Test main module detection (help).
    
    Validates that help flags correctly resolve to 'bcllm_main'.
    """
    
    def test_help_long_flag(self):
        """--help resolves to bcllm_main."""
        # Arrange
        argv = ["bcllm", "--help"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_main"
    
    def test_help_short_flag(self):
        """-h resolves to bcllm_main."""
        # Arrange
        argv = ["bcllm", "-h"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_main"


class TestModuleResolverPriority:
    """Test priority ordering.
    
    Validates that:
    - Help flags take highest priority regardless of position
    - First-match-wins applies for same-priority flags
    """
    
    def test_help_takes_priority_over_execute(self):
        """--help --execute resolves to bcllm_main (help wins)."""
        # Arrange
        argv = ["bcllm", "--help", "--execute"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_main"
    
    def test_help_short_takes_priority_over_create_experiment(self):
        """-h --create-experiment resolves to bcllm_main (help wins)."""
        # Arrange
        argv = ["bcllm", "-h", "--create-experiment", "my_exp"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_main"
    
    def test_help_in_middle_takes_priority(self):
        """--create-experiment --help --execute resolves to bcllm_main."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "my_exp", "--help", "--execute"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_main"
    
    def test_first_match_wins_experiment_flags(self):
        """--create-experiment --list-experiments resolves to bcllm_experiment (first match)."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "my_exp", "--list-experiments"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
    
    def test_first_match_wins_model_flags(self):
        """--add-model --list-models resolves to bcllm_model (first match)."""
        # Arrange
        argv = ["bcllm", "--add-model", "openai/gpt-4", "--list-models"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_model"
    
    def test_first_match_wins_run_flags(self):
        """--create-run --list-runs resolves to bcllm_run (first match)."""
        # Arrange
        argv = ["bcllm", "--create-run", "run-001", "--list-runs"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_run"
    
    def test_first_match_wins_cross_module(self):
        """--add-model --list-experiments resolves to bcllm_model (first module flag)."""
        # Arrange
        argv = ["bcllm", "--add-model", "openai/gpt-4", "--list-experiments"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_model"
    
    def test_first_match_wins_cross_module_reverse(self):
        """--list-experiments --add-model resolves to bcllm_experiment (first module flag)."""
        # Arrange
        argv = ["bcllm", "--list-experiments", "--add-model", "openai/gpt-4"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"


class TestModuleResolverInvalid:
    """Test invalid/missing module handling.
    
    Validates behavior when no valid module flag is present.
    """
    
    def test_empty_argv_returns_none(self):
        """Empty argv (only script name) returns None."""
        # Arrange
        argv = ["bcllm"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result is None
    
    def test_unknown_flags_only_returns_none(self):
        """Unknown flags only returns None."""
        # Arrange
        argv = ["bcllm", "--unknown-flag", "--another-unknown"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result is None
    
    def test_only_values_returns_none(self):
        """Only values (no flags) returns None."""
        # Arrange
        argv = ["bcllm", "my_exp", "run-001"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result is None
    
    def test_partial_flag_without_value_returns_none(self):
        """Partial flag match (e.g., --exper) returns None."""
        # Arrange
        argv = ["bcllm", "--exper", "my_exp"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result is None


class TestModuleResolverEdgeCases:
    """Test edge cases.
    
    Validates behavior for boundary conditions and special cases.
    """
    
    def test_case_sensitivity_execute_uppercase(self):
        """--EXECUTE does NOT match --execute (case sensitive)."""
        # Arrange
        argv = ["bcllm", "--EXECUTE"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result is None
    
    def test_case_sensitivity_help_uppercase(self):
        """--HELP does NOT match --help (case sensitive)."""
        # Arrange
        argv = ["bcllm", "--HELP"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result is None
    
    def test_case_sensitivity_mixed_case(self):
        """--Execute does NOT match --execute (case sensitive)."""
        # Arrange
        argv = ["bcllm", "--Execute"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result is None
    
    def test_flag_with_empty_value(self):
        """--experiment with empty value still resolves to bcllm_experiment."""
        # Arrange
        argv = ["bcllm", "--experiment", ""]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
    
    def test_flag_with_equals_empty_value(self):
        """--experiment= (empty value) still resolves to bcllm_experiment."""
        # Arrange
        argv = ["bcllm", "--experiment="]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
    
    def test_multiple_flags_different_modules_first_wins(self):
        """Multiple module flags: first matching flag determines module."""
        # Arrange
        argv = ["bcllm", "--list-questions", "--add-model", "openai/gpt-4", "--execute"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_questions"
    
    def test_script_name_not_treated_as_flag(self):
        """Script name 'bcllm' is not treated as a flag."""
        # Arrange
        argv = ["bcllm"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result is None
    
    def test_hyphen_in_flag_name(self):
        """Flags with hyphens are matched correctly."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "my-exp-with-hyphens"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
    
    def test_short_flag_h_only(self):
        """-h alone resolves to bcllm_main."""
        # Arrange
        argv = ["bcllm", "-h"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_main"
    
    def test_long_argv_with_multiple_flags_and_values(self):
        """Complex argv with multiple flags and values: first module flag wins."""
        # Arrange
        argv = [
            "bcllm",
            "--experiment", "my_exp",
            "--model", "openai/gpt-4",
            "--run", "run-001",
            "--execute"
        ]
        
        # Act
        result = resolve_module(argv)
        
        # Assert
        assert result == "bcllm_experiment"
