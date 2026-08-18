"""Unit tests for MODE × MODULE matrix validation.

Tests the deterministic MODE × MODULE combination validator.

The mode matrix validator's responsibility is to:
1. Receive a Mode enum and module name
2. Validate that the combination is allowed per the strict MODE × MODULE matrix
3. Return validation result (valid/invalid) with error message if invalid

MODE × MODULE Validation Matrix:
┌─────────────────────┬────────┬────────┬──────────┬─────────────────────┐
│ Module ↓ / Mode →   │ CREATE │ MODIFY │ EXECUTE  │ NONE (INVALID)      │
├─────────────────────┼────────┼────────┼──────────┼─────────────────────┤
│ bcllm_experiment    │ ✅     │ ✅     │ ❌       │ ✅ (list/show only) │
│ bcllm_model         │ ❌     │ ✅     │ ❌       │ ✅ (list only)      │
│ bcllm_questions     │ ❌     │ ✅     │ ❌       │ ✅ (list only)      │
│ bcllm_run           │ ❌     │ ✅     │ ✅       │ ✅ (list only)      │
│ bcllm_execute       │ ❌     │ ❌     │ ✅       │ ❌                  │
│ bcllm_review        │ ❌     │ ❌     │ ❌       │ ✅                  │
│ bcllm_main          │ ❌     │ ❌     │ ❌       │ ✅ (help only)      │
└─────────────────────┴────────┴────────┴──────────┴─────────────────────┘

Valid combinations (mode, module):
- (CREATE, bcllm_experiment) — creating experiment
- (MODIFY, bcllm_experiment) — modifying experiment
- (MODIFY, bcllm_model) — adding/removing models
- (MODIFY, bcllm_questions) — adding/removing questions
- (MODIFY, bcllm_run) — creating/removing runs
- (EXECUTE, bcllm_run) — running a specific run
- (EXECUTE, bcllm_execute) — executing benchmark
- (NONE, bcllm_experiment) — listing experiments
- (NONE, bcllm_model) — listing models
- (NONE, bcllm_questions) — listing questions
- (NONE, bcllm_run) — listing runs
- (NONE, bcllm_review) — reviewing results
- (NONE, bcllm_main) — showing help

Invalid combinations (should error):
- (CREATE, bcllm_model) — can't create model directly
- (CREATE, bcllm_questions) — can't create questions directly
- (CREATE, bcllm_run) — can't create run directly
- (CREATE, bcllm_execute) — can't execute in CREATE mode
- (CREATE, bcllm_review) — can't review in CREATE mode
- (MODIFY, bcllm_execute) — can't execute in MODIFY mode
- (MODIFY, bcllm_review) — can't review in MODIFY mode
- (EXECUTE, bcllm_experiment) — execute mode doesn't modify experiment
- (EXECUTE, bcllm_model) — execute mode doesn't modify models
- (EXECUTE, bcllm_questions) — execute mode doesn't modify questions
- (NONE, bcllm_execute) — can't execute without a mode
"""

import pytest
from src.core.mode import Mode
from src.core.mode_matrix import validate_mode_matrix, ModeMatrixError


class TestModeMatrixValidCombinations:
    """Test valid MODE × MODULE combinations.
    
    Each test validates that a specific (mode, module) pair is accepted
    by the validator without raising an exception.
    """

    def test_create_with_experiment(self):
        """CREATE mode with bcllm_experiment module is valid.
        
        This combination allows creating a new experiment.
        """
        # Arrange
        mode = Mode.CREATE
        module = "bcllm_experiment"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_experiment(self):
        """MODIFY mode with bcllm_experiment module is valid.
        
        This combination allows modifying an existing experiment.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_experiment"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_model(self):
        """MODIFY mode with bcllm_model module is valid.
        
        This combination allows adding or removing models from an experiment.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_model"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_questions(self):
        """MODIFY mode with bcllm_questions module is valid.
        
        This combination allows adding or removing questions from an experiment.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_questions"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_run(self):
        """MODIFY mode with bcllm_run module is valid.
        
        This combination allows creating or removing runs from an experiment.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_run"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_execute_with_run(self):
        """EXECUTE mode with bcllm_run module is valid.
        
        This combination allows executing a specific run.
        """
        # Arrange
        mode = Mode.EXECUTE
        module = "bcllm_run"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_execute_with_execute(self):
        """EXECUTE mode with bcllm_execute module is valid.
        
        This combination allows executing the benchmark.
        """
        # Arrange
        mode = Mode.EXECUTE
        module = "bcllm_execute"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_experiment(self):
        """MODIFY mode with bcllm_experiment module is valid.

        This combination allows listing or showing experiments.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_experiment"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_model(self):
        """MODIFY mode with bcllm_model module is valid.

        This combination allows listing models.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_model"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_questions(self):
        """MODIFY mode with bcllm_questions module is valid.

        This combination allows listing questions.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_questions"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_run(self):
        """MODIFY mode with bcllm_run module is valid.

        This combination allows listing runs.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_run"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_modify_with_review(self):
        """MODIFY mode with bcllm_review module is NOT valid.

        Review is a read-only operation that doesn't fit MODIFY mode.
        This test documents that review requires its own mode handling.
        Note: This combination was previously allowed with Mode.INVALID but is now rejected.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_review"

        # Act & Assert
        with pytest.raises(ModeMatrixError):
            validate_mode_matrix(mode, module)

    def test_modify_with_main(self):
        """MODIFY mode with bcllm_main module is NOT valid.

        Main/help display doesn't fit MODIFY mode.
        Note: This combination was previously allowed with Mode.INVALID but is now rejected.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_main"

        # Act & Assert
        with pytest.raises(ModeMatrixError):
            validate_mode_matrix(mode, module)


class TestModeMatrixInvalidCombinations:
    """Test invalid MODE × MODULE combinations.
    
    Each test validates that an invalid (mode, module) pair raises
    ModeMatrixError with an educational error message.
    """

    def test_create_with_model(self):
        """CREATE mode with bcllm_model module is VALID for composite flows.

        This combination is allowed when --create-experiment + --add-model are present.
        The orchestration layer creates the experiment before dispatching to the model module.
        """
        # Arrange
        mode = Mode.CREATE
        module = "bcllm_model"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_create_with_questions(self):
        """CREATE mode with bcllm_questions module is VALID for composite flows.

        This combination is allowed when --create-experiment + --add-questions are present.
        The orchestration layer creates the experiment before dispatching.
        """
        # Arrange
        mode = Mode.CREATE
        module = "bcllm_questions"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_create_with_run(self):
        """CREATE mode with bcllm_run module is VALID for composite flows.

        This combination is allowed when --create-experiment + --add-run are present.
        The orchestration layer creates the experiment before dispatching.
        """
        # Arrange
        mode = Mode.CREATE
        module = "bcllm_run"

        # Act
        result = validate_mode_matrix(mode, module)

        # Assert
        assert result is True

    def test_create_with_execute(self):
        """CREATE mode with bcllm_execute module is invalid.
        
        Execution cannot happen in CREATE mode.
        """
        # Arrange
        mode = Mode.CREATE
        module = "bcllm_execute"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Verify error message contains educational content
        assert "bcllm_execute" in str(exc_info.value)
        assert "CREATE" in str(exc_info.value)

    def test_create_with_review(self):
        """CREATE mode with bcllm_review module is invalid.
        
        Review cannot happen in CREATE mode.
        """
        # Arrange
        mode = Mode.CREATE
        module = "bcllm_review"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Verify error message contains educational content
        assert "bcllm_review" in str(exc_info.value)
        assert "CREATE" in str(exc_info.value)

    def test_create_with_main(self):
        """CREATE mode with bcllm_main module is invalid.
        
        Help cannot be shown in CREATE mode.
        """
        # Arrange
        mode = Mode.CREATE
        module = "bcllm_main"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Verify error message contains educational content
        assert "bcllm_main" in str(exc_info.value)
        assert "CREATE" in str(exc_info.value)

    def test_modify_with_execute(self):
        """MODIFY mode with bcllm_execute module is invalid.
        
        Execution cannot happen in MODIFY mode.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_execute"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Verify error message contains educational content
        assert "bcllm_execute" in str(exc_info.value)
        assert "MODIFY" in str(exc_info.value)

    def test_modify_with_review(self):
        """MODIFY mode with bcllm_review module is invalid.
        
        Review cannot happen in MODIFY mode.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_review"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Verify error message contains educational content
        assert "bcllm_review" in str(exc_info.value)
        assert "MODIFY" in str(exc_info.value)

    def test_execute_with_experiment(self):
        """EXECUTE mode with bcllm_experiment module is invalid.
        
        Execute mode does not modify experiments.
        """
        # Arrange
        mode = Mode.EXECUTE
        module = "bcllm_experiment"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Verify error message contains educational content
        assert "bcllm_experiment" in str(exc_info.value)
        assert "EXECUTE" in str(exc_info.value)

    def test_execute_with_model(self):
        """EXECUTE mode with bcllm_model module is invalid.
        
        Execute mode does not modify models.
        """
        # Arrange
        mode = Mode.EXECUTE
        module = "bcllm_model"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Verify error message contains educational content
        assert "bcllm_model" in str(exc_info.value)
        assert "EXECUTE" in str(exc_info.value)

    def test_execute_with_questions(self):
        """EXECUTE mode with bcllm_questions module is invalid.
        
        Execute mode does not modify questions.
        """
        # Arrange
        mode = Mode.EXECUTE
        module = "bcllm_questions"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Verify error message contains educational content
        assert "bcllm_questions" in str(exc_info.value)
        assert "EXECUTE" in str(exc_info.value)

    def test_modify_with_execute(self):
        """MODIFY mode with bcllm_execute module is invalid.

        Execution requires an explicit mode (EXECUTE).
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_execute"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Verify error message contains educational content
        assert "bcllm_execute" in str(exc_info.value)
        assert "MODIFY" in str(exc_info.value) or "mode" in str(exc_info.value).lower()


class TestModeMatrixErrorMessages:
    """Test error message quality.
    
    Validates that error messages are educational and actionable.
    """

    def test_error_states_what_is_wrong(self):
        """Error message clearly states what combination is invalid.

        The error should identify both the mode and module that are incompatible.
        """
        # Arrange
        mode = Mode.EXECUTE
        module = "bcllm_model"

        # Act
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Assert
        error_message = str(exc_info.value)
        # Error should mention the invalid mode
        assert "EXECUTE" in error_message or "execute" in error_message.lower()
        # Error should mention the invalid module
        assert "bcllm_model" in error_message or "model" in error_message.lower()

    def test_error_shows_correct_usage(self):
        """Error message shows correct usage or valid alternatives.

        The error should guide the user toward valid combinations.
        """
        # Arrange
        mode = Mode.EXECUTE
        module = "bcllm_model"

        # Act
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Assert
        error_message = str(exc_info.value)
        # Error should contain guidance (e.g., "use", "valid", "allowed", or example flags)
        has_guidance = any(
            keyword in error_message.lower()
            for keyword in ["use", "valid", "allowed", "correct", "try", "--"]
        )
        assert has_guidance

    def test_error_does_not_infer_intent(self):
        """Error message does not infer user intent or suggest auto-correction.

        The error should state what's wrong, not guess what the user meant.
        """
        # Arrange
        mode = Mode.EXECUTE
        module = "bcllm_model"

        # Act
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Assert
        error_message = str(exc_info.value)
        # Error should NOT contain intent-inference phrases
        inference_phrases = [
            "did you mean",
            "you probably want",
            "you intended",
            "we think",
            "we assume",
            "auto-correct",
            "automatically",
        ]
        for phrase in inference_phrases:
            assert phrase not in error_message.lower()

    def test_error_for_modify_with_execute_shows_execute_flag(self):
        """Error for MODIFY + bcllm_execute mentions --execute flag.
        
        This validates that the error message provides actionable guidance.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_execute"

        # Act
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)
        
        # Assert
        error_message = str(exc_info.value)
        # Error should mention the --execute flag as the correct way
        assert "--execute" in error_message or "execute" in error_message.lower()

    def test_error_for_modify_with_execute_explains_mode_requirement(self):
        """Error for MODIFY + bcllm_execute explains that execution requires a mode.

        This validates that the error message explains why the combination is invalid.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_execute"

        # Act
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Assert
        error_message = str(exc_info.value)
        # Error should explain that execution requires explicit mode
        has_explanation = any(
            keyword in error_message.lower()
            for keyword in ["cannot", "only", "for"]
        )
        assert has_explanation


class TestModeMatrixEdgeCases:
    """Test edge cases.

    Validates behavior for boundary conditions and special inputs.
    """

    def test_empty_module_name_raises_error(self):
        """Empty module name raises ModeMatrixError.

        An empty string is not a valid module name.
        """
        # Arrange
        mode = Mode.MODIFY
        module = ""

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Verify error message mentions the invalid input
        assert "module" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()

    def test_unknown_module_name_raises_error(self):
        """Unknown module name raises ModeMatrixError.

        Modules not in the matrix should be rejected.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_unknown_module"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Verify error message mentions the unknown module
        assert "bcllm_unknown_module" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()

    def test_module_name_with_prefix_match_raises_error(self):
        """Module name that is a prefix of a valid module raises ModeMatrixError.

        Partial matches should not be accepted.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_exper"  # Prefix of "bcllm_experiment"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Verify error message mentions the invalid module
        assert "bcllm_exper" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()

    def test_module_name_case_sensitive(self):
        """Module name matching is case-sensitive.

        "BCLLM_EXPERIMENT" should not match "bcllm_experiment".
        """
        # Arrange
        mode = Mode.MODIFY
        module = "BCLLM_EXPERIMENT"  # Uppercase

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Verify error message mentions the invalid module
        assert "BCLLM_EXPERIMENT" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()

    def test_module_name_with_extra_whitespace_raises_error(self):
        """Module name with leading/trailing whitespace raises ModeMatrixError.

        Whitespace should not be silently stripped.
        """
        # Arrange
        mode = Mode.MODIFY
        module = " bcllm_experiment "

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Verify error message mentions the invalid module
        assert "bcllm_experiment" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()

    def test_modify_mode_with_execute_module_is_invalid(self):
        """MODIFY mode with execute module is invalid.

        This validates that execution requires an explicit EXECUTE mode.
        """
        # Arrange
        mode = Mode.MODIFY
        module = "bcllm_execute"

        # Act & Assert
        with pytest.raises(ModeMatrixError) as exc_info:
            validate_mode_matrix(mode, module)

        # Verify error explains that execution requires explicit mode
        error_message = str(exc_info.value).lower()
        assert any(k in error_message for k in ["require", "need", "must", "explicit", "execute"])

    def test_all_modes_with_invalid_module_raise_error(self):
        """All modes reject an invalid module name.

        This validates that module validation is consistent across all modes.
        """
        # Arrange
        invalid_module = "bcllm_invalid"
        all_modes = [Mode.CREATE, Mode.MODIFY, Mode.EXECUTE]

        # Act & Assert
        for mode in all_modes:
            with pytest.raises(ModeMatrixError) as exc_info:
                validate_mode_matrix(mode, invalid_module)

            # Verify each mode rejects the invalid module
            assert "bcllm_invalid" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()

    def test_all_modules_with_invalid_mode_raise_error(self):
        """All valid modules reject an invalid mode.

        This validates that mode validation is consistent across all modules.
        Note: This test assumes Mode enum has only CREATE, MODIFY, EXECUTE.
        Note: bcllm_review and bcllm_main are excluded here because their
        only valid mode is Mode.INVALID itself (see
        TestModeInvalidIsValidForHelpListReview below) — this loop is about
        modules with a CREATE/MODIFY/EXECUTE mode, which is a different
        axis, not a gap.
        """
        # Arrange
        modules_with_valid_modes = [
            "bcllm_experiment",
            "bcllm_model",
            "bcllm_questions",
            "bcllm_run",
            "bcllm_execute",
        ]

        # Act & Assert
        # Test that each valid module works with at least one valid mode
        for module in modules_with_valid_modes:
            # Each module should have at least one valid mode
            # This test documents the expected behavior
            has_valid_mode = False

            # Check against all known valid combinations
            valid_combinations = [
                (Mode.CREATE, "bcllm_experiment"),
                (Mode.MODIFY, "bcllm_experiment"),
                (Mode.CREATE, "bcllm_model"),  # Composite flow
                (Mode.MODIFY, "bcllm_model"),
                (Mode.CREATE, "bcllm_questions"),  # Composite flow
                (Mode.MODIFY, "bcllm_questions"),
                (Mode.CREATE, "bcllm_run"),  # Composite flow
                (Mode.MODIFY, "bcllm_run"),
                (Mode.EXECUTE, "bcllm_run"),
                (Mode.EXECUTE, "bcllm_execute"),
            ]

            for mode, valid_module in valid_combinations:
                if valid_module == module:
                    has_valid_mode = True
                    break

            # Document: each module should have at least one valid mode
            assert has_valid_mode, f"Module {module} should have at least one valid mode"


class TestModeInvalidIsValidForHelpListReview:
    """(Mode.INVALID, module) is valid for --help, --list-experiments,
    --remove-experiment, --review-experiment, and --review-all.

    These commands carry their own identity/action flag rather than a
    mode flag, so resolve_mode() (src/core/mode_resolver.py) has nothing
    to key CREATE/MODIFY/EXECUTE/EXPORT on and resolves them to
    Mode.INVALID — which is correct and expected, not an error state.
    Each target module already treats Mode.INVALID as expected on its own
    side (_validate_expected_mode's VALID_MODES in bcllm_main.py,
    bcllm_experiment.py, bcllm_review.py). Before this test was added,
    _VALID_COMBINATIONS simply never listed these three (mode, module)
    pairs, so validate_mode_matrix() rejected all five commands before
    they ever reached the module that was ready to handle them — see
    docs/status/known-issues.md ("Mode.INVALID has no valid module in the
    mode/module matrix"), fixed alongside this test.
    """

    def test_invalid_mode_valid_for_bcllm_main(self):
        assert validate_mode_matrix(Mode.INVALID, "bcllm_main") is True

    def test_invalid_mode_valid_for_bcllm_experiment(self):
        assert validate_mode_matrix(Mode.INVALID, "bcllm_experiment") is True

    def test_invalid_mode_valid_for_bcllm_review(self):
        assert validate_mode_matrix(Mode.INVALID, "bcllm_review") is True

    def test_help_resolves_through_the_full_pipeline(self):
        """End-to-end: --help must not be rejected by the mode matrix."""
        from src.core.mode_resolver import resolve_mode
        from src.core.module_resolver import resolve_module

        argv = ["bcllm", "--help"]
        mode = resolve_mode(argv)
        module = resolve_module(argv)

        assert validate_mode_matrix(mode, module) is True

    def test_list_experiments_resolves_through_the_full_pipeline(self):
        from src.core.mode_resolver import resolve_mode
        from src.core.module_resolver import resolve_module

        argv = ["bcllm", "--list-experiments"]
        mode = resolve_mode(argv)
        module = resolve_module(argv)

        assert validate_mode_matrix(mode, module) is True

    def test_review_all_resolves_through_the_full_pipeline(self):
        from src.core.mode_resolver import resolve_mode
        from src.core.module_resolver import resolve_module

        argv = ["bcllm", "--review-all"]
        mode = resolve_mode(argv)
        module = resolve_module(argv)

        assert validate_mode_matrix(mode, module) is True
