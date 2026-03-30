"""MODE × MODULE matrix validation."""
from src.core.mode import Mode


_VALID_COMBINATIONS = {
    (Mode.CREATE, "bcllm_experiment"): True,
    (Mode.MODIFY, "bcllm_experiment"): True,
    (Mode.MODIFY, "bcllm_model"): True,
    (Mode.MODIFY, "bcllm_questions"): True,
    (Mode.MODIFY, "bcllm_run"): True,
    (Mode.EXECUTE, "bcllm_run"): True,
    (Mode.EXECUTE, "bcllm_execute"): True,
    (Mode.EXPORT, "bcllm_export"): True,
    (Mode.EXPORT, "bcllm_main"): True,
    (Mode.INVALID, "bcllm_experiment"): True,
    (Mode.INVALID, "bcllm_model"): True,
    (Mode.INVALID, "bcllm_questions"): True,
    (Mode.INVALID, "bcllm_run"): True,
    (Mode.INVALID, "bcllm_review"): True,
    (Mode.INVALID, "bcllm_export"): True,
    (Mode.INVALID, "bcllm_main"): True,
}

_ERROR_MESSAGES = {
    Mode.CREATE: {
        "bcllm_model": (
            "Error: Invalid MODE × MODULE combination (CREATE, bcllm_model).\n"
            "Cannot create models directly. Use --create-experiment first, then --experiment NAME --add-model."
        ),
        "bcllm_questions": (
            "Error: Invalid MODE × MODULE combination (CREATE, bcllm_questions).\n"
            "Cannot create questions directly. Use --create-experiment first, then --experiment NAME --add-questions."
        ),
        "bcllm_run": (
            "Error: Invalid MODE × MODULE combination (CREATE, bcllm_run).\n"
            "Cannot create runs directly. Use --create-experiment first, then --experiment NAME --add-run."
        ),
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
    Mode.INVALID: {
        "bcllm_execute": (
            "Error: Invalid MODE × MODULE combination (INVALID, bcllm_execute).\n"
            "Cannot execute without a valid mode. Execution requires explicit --execute flag."
        ),
        "bcllm_export": (
            "Error: Invalid MODE × MODULE combination (INVALID, bcllm_export).\n"
            "Cannot export without a valid mode. Export requires explicit --export flag."
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
