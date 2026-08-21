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
    
    def test_remove_question_flag_does_not_resolve_to_any_module(self):
        """Normative (marco 4A, 2026-08-20): --remove-question was
        removed from the system entirely — QuestionSnapshot is immutable,
        an experiment can only grow by adding snapshots. It must not
        resolve to bcllm_questions (or any module) via a bare flag-only
        argv — see docs/status/known-issues.md."""
        argv = ["bcllm", "--remove-question", "q1"]

        result = resolve_module(argv)

        assert result is None


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
    
    def test_create_run_flag_does_not_resolve_to_any_module(self):
        """Normative (2026-08-20): --create-run was never a real flag —
        bcllm_run.py has always used --add-run. Removed as a dead/never-
        reachable duplicate entry from _MODULE_MAP/PRIORITY_FLAGS — see
        docs/status/known-issues.md."""
        argv = ["bcllm", "--create-run", "run-001"]

        result = resolve_module(argv)

        assert result is None

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
        """--run --list-runs resolves to bcllm_run (first match).
        Updated 2026-08-20: previously used the dead --create-run flag
        (never real, see docs/status/known-issues.md) — swapped for
        --run, a genuine PRIORITY_FLAGS member, preserving this test's
        original intent (multiple run-tier flags together still resolve
        deterministically to bcllm_run)."""
        # Arrange
        argv = ["bcllm", "--run", "run-001", "--list-runs"]

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
        """Specific action flags take priority over generic listing flags.
        
        Contract: When multiple module flags are present, specific action flags
        (--add-model, --add-run, etc.) take priority over generic listing flags
        (--list-experiments, --experiment, etc.), regardless of argument order.
        
        This ensures commands like '--experiment NAME --add-run' route correctly
        to the action module, not the generic module.
        """
        # Arrange
        argv = ["bcllm", "--list-experiments", "--add-model", "openai/gpt-4"]

        # Act
        result = resolve_module(argv)

        # Assert: Action flag (--add-model) takes priority over listing flag (--list-experiments)
        assert result == "bcllm_model"


class TestModuleResolverCompositeFlows:
    """Test composite flow resolution (CREATE + ADD_*).
    
    Validates that:
    - --create-experiment + --add-* resolves to the action module
    - Argument order does not affect resolution
    - All ADD_* actions are supported in composite flows
    """
    
    def test_create_experiment_with_add_model(self):
        """--create-experiment --add-model resolves to bcllm_model."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "EXP", "--add-model", "M"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert: Action flag defines module
        assert result == "bcllm_model"
    
    def test_create_experiment_with_add_questions(self):
        """--create-experiment --add-questions resolves to bcllm_questions."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "EXP", "--add-questions", "Q"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert: Action flag defines module
        assert result == "bcllm_questions"
    
    def test_create_experiment_with_add_run(self):
        """--create-experiment --add-run resolves to bcllm_run."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "EXP", "--add-run"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert: Action flag defines module
        assert result == "bcllm_run"
    
    def test_argument_order_does_not_matter_add_model(self):
        """Argument order does not affect resolution for --add-model."""
        # Arrange
        argv1 = ["bcllm", "--create-experiment", "EXP", "--add-model", "M"]
        argv2 = ["bcllm", "--add-model", "M", "--create-experiment", "EXP"]
        
        # Act
        result1 = resolve_module(argv1)
        result2 = resolve_module(argv2)
        
        # Assert: Both should resolve to bcllm_model
        assert result1 == "bcllm_model"
        assert result2 == "bcllm_model"
    
    def test_argument_order_does_not_matter_add_questions(self):
        """Argument order does not affect resolution for --add-questions."""
        # Arrange
        argv1 = ["bcllm", "--create-experiment", "EXP", "--add-questions", "Q"]
        argv2 = ["bcllm", "--add-questions", "Q", "--create-experiment", "EXP"]
        
        # Act
        result1 = resolve_module(argv1)
        result2 = resolve_module(argv2)
        
        # Assert: Both should resolve to bcllm_questions
        assert result1 == "bcllm_questions"
        assert result2 == "bcllm_questions"
    
    def test_argument_order_does_not_matter_add_run(self):
        """Argument order does not affect resolution for --add-run."""
        # Arrange
        argv1 = ["bcllm", "--create-experiment", "EXP", "--add-run"]
        argv2 = ["bcllm", "--add-run", "--create-experiment", "EXP"]
        
        # Act
        result1 = resolve_module(argv1)
        result2 = resolve_module(argv2)
        
        # Assert: Both should resolve to bcllm_run
        assert result1 == "bcllm_run"
        assert result2 == "bcllm_run"
    
    def test_create_experiment_alone_resolves_to_experiment_module(self):
        """--create-experiment without --add-* resolves to bcllm_experiment."""
        # Arrange
        argv = ["bcllm", "--create-experiment", "EXP"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert: No action flag, so context flag defines module
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
        """Multiple module flags: first matching flag determines module.
        
        Contract: When multiple flags from different modules are present,
        the first matching flag (left-to-right) determines the target module,
        except for high-priority flags (--help, --export, --execute) which
        always take precedence.
        """
        # Arrange
        argv = ["bcllm", "--list-questions", "--add-model", "openai/gpt-4", "--execute"]
        
        # Act
        result = resolve_module(argv)
        
        # Assert: --execute takes priority over other flags
        assert result == "bcllm_execute"
    
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
        """Complex argv with multiple flags and values: high-priority flags win.
        
        Contract: High-priority flags (--execute, --export, --help) always take
        precedence over module-specific flags, regardless of position.
        """
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
        
        # Assert: --execute takes priority over other module flags
        assert result == "bcllm_execute"
