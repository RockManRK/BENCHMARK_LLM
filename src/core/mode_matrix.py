"""MODE × MODULE matrix validation.

This module validates MODE × MODULE combinations AFTER resolution.
It does NOT orchestrate flow - it only validates if the resolved combination is allowed.

Composite Flow Support:
- (CREATE, bcllm_model) is valid when --create-experiment + --add-model are present
- (CREATE, bcllm_questions) is valid when --create-experiment + --add-questions are present
- (CREATE, bcllm_run) is valid when --create-experiment + --add-run are present

The orchestration layer (bcllm.py) ensures the experiment is created BEFORE
the action module executes.
"""
from src.core.mode import Mode


_VALID_COMBINATIONS = {
    (Mode.CREATE, "bcllm_experiment"): True,
    # NEW: Composite flows (CREATE + ADD_*)
    # The orchestration layer (bcllm.py) creates the experiment first,
    # then dispatches to the action module.
    (Mode.CREATE, "bcllm_model"): True,
    (Mode.CREATE, "bcllm_questions"): True,
    (Mode.CREATE, "bcllm_run"): True,
    
    (Mode.MODIFY, "bcllm_experiment"): True,
    (Mode.MODIFY, "bcllm_model"): True,
    (Mode.MODIFY, "bcllm_questions"): True,
    (Mode.MODIFY, "bcllm_run"): True,
    (Mode.EXECUTE, "bcllm_run"): True,
    (Mode.EXECUTE, "bcllm_execute"): True,
    (Mode.EXPORT, "bcllm_export"): True,
    (Mode.EXPORT, "bcllm_main"): True,
}

_ERROR_MESSAGES = {
    Mode.CREATE: {
        # Note: bcllm_model, bcllm_questions, bcllm_run are NOW ALLOWED in CREATE mode
        # when part of a composite flow (--create-experiment + --add-*).
        # The orchestration layer creates the experiment before dispatching.
        "bcllm_execute": (
            "Error: Invalid MODE × MODULE combination (CREATE, bcllm_execute).\n"
            "Cannot execute in CREATE mode. Execute requires --execute flag."
        ),
        "bcllm_review": (
            "Error: Invalid MODE × MODULE combination (CREATE, bcllm_review).\n"
            "Cannot review in CREATE mode. Review is a read-only operation."
        ),
        "bcllm_main": (
            "Error: Invalid MODE × MODULE combination (CREATE, bcllm_main).\n"
            "Cannot show help in CREATE mode. Use without flags to display help."
        ),
    },
    Mode.MODIFY: {
        "bcllm_execute": (
            "Error: Invalid MODE × MODULE combination (MODIFY, bcllm_execute).\n"
            "Cannot execute in MODIFY mode. Use --execute flag to run benchmarks."
        ),
        "bcllm_review": (
            "Error: Invalid MODE × MODULE combination (MODIFY, bcllm_review).\n"
            "Cannot review in MODIFY mode. Review is a read-only operation."
        ),
    },
    Mode.EXECUTE: {
        "bcllm_experiment": (
            "Error: Invalid MODE × MODULE combination (EXECUTE, bcllm_experiment).\n"
            "Cannot modify experiment in EXECUTE mode. EXECUTE is for running benchmarks only."
        ),
        "bcllm_model": (
            "Error: Invalid MODE × MODULE combination (EXECUTE, bcllm_model).\n"
            "Cannot modify models in EXECUTE mode. EXECUTE is for running benchmarks only."
        ),
        "bcllm_questions": (
            "Error: Invalid MODE × MODULE combination (EXECUTE, bcllm_questions).\n"
            "Cannot modify questions in EXECUTE mode. EXECUTE is for running benchmarks only."
        ),
    },
    Mode.EXPORT: {
        "bcllm_experiment": (
            "Error: Invalid MODE × MODULE combination (EXPORT, bcllm_experiment).\n"
            "Cannot modify experiment in EXPORT mode. EXPORT is for exporting results only."
        ),
        "bcllm_model": (
            "Error: Invalid MODE × MODULE combination (EXPORT, bcllm_model).\n"
            "Cannot modify models in EXPORT mode. EXPORT is for exporting results only."
        ),
        "bcllm_questions": (
            "Error: Invalid MODE × MODULE combination (EXPORT, bcllm_questions).\n"
            "Cannot modify questions in EXPORT mode. EXPORT is for exporting results only."
        ),
        "bcllm_run": (
            "Error: Invalid MODE × MODULE combination (EXPORT, bcllm_run).\n"
            "Cannot modify runs in EXPORT mode. EXPORT is for exporting results only."
        ),
        "bcllm_execute": (
            "Error: Invalid MODE × MODULE combination (EXPORT, bcllm_execute).\n"
            "Cannot execute in EXPORT mode. EXPORT is for exporting results only."
        ),
        "bcllm_review": (
            "Error: Invalid MODE × MODULE combination (EXPORT, bcllm_review).\n"
            "Cannot review in EXPORT mode. EXPORT is for exporting results only."
        ),
    },
}


class ModeMatrixError(Exception):
    """Raised when MODE × MODULE combination is invalid."""
    pass


def validate_mode_matrix(mode: Mode, module: str) -> bool:
    """Validate MODE × MODULE combination.

    Args:
        mode: The CLI mode (CREATE, MODIFY, EXECUTE, NONE)
        module: The module name (e.g., "bcllm_experiment")

    Returns:
        True if combination is valid

    Raises:
        ModeMatrixError: If combination is invalid. Error message includes:
            - What mode and module are invalid
            - Correct usage or guidance
            - No intent inference or auto-correction
    """
    if _VALID_COMBINATIONS.get((mode, module), False):
        return True

    error_msg = _get_error_message(mode, module)
    raise ModeMatrixError(error_msg)


def _get_error_message(mode: Mode, module: str) -> str:
    """Get error message for invalid MODE × MODULE combination.

    Args:
        mode: The CLI mode
        module: The module name

    Returns:
        Educational error message explaining what's wrong and correct usage
    """
    if mode in _ERROR_MESSAGES and module in _ERROR_MESSAGES[mode]:
        return _ERROR_MESSAGES[mode][module]

    mode_name = mode.value.upper()
    return (
        f"Error: Invalid MODE × MODULE combination ({mode_name}, {module}).\n"
        f"Hint: Check that the mode and module are compatible.\n"
        f"Usage: bcllm --<mode-flag> --<module-flag> ..."
    )
