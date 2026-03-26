"""Model ID validator.

This module provides validation for model IDs in the format:
    <provider>/<model_id>

Validation rules:
- Must contain exactly one '/' character
- Provider part (before '/') must be non-empty
- Model ID part (after '/') must be non-empty
- No character restrictions - allows dots, colons, hyphens, underscores, etc.

Examples of valid model IDs:
- openai/gpt-4
- google/gemini-3.1-flash-lite-preview
- stepfun/step-3.5-flash:free
- nvidia/nemotron-3-super-120b-a12b:free

Examples of invalid model IDs:
- "" (empty string)
- "gpt-4" (missing provider)
- "openai/gpt-4/extra" (multiple slashes)
- "/gpt-4" (empty provider)
- "openai/" (empty model ID)
"""


def validate_model_id(model_id: str) -> bool:
    """Validate model ID format.

    Args:
        model_id: Model identifier to validate. Expected format: provider/model-name.
                  Allows any characters except multiple slashes or empty parts.

    Returns:
        True if format is valid, False otherwise.

    Examples:
        >>> validate_model_id("openai/gpt-4")
        True
        >>> validate_model_id("google/gemini-3.1-flash-lite-preview")
        True
        >>> validate_model_id("stepfun/step-3.5-flash:free")
        True
        >>> validate_model_id("")
        False
        >>> validate_model_id("gpt-4")
        False
        >>> validate_model_id("openai/gpt-4/extra")
        False
    """
    if not model_id:
        return False

    # Check for exactly one slash
    parts = model_id.split('/')
    if len(parts) != 2:
        return False

    provider, model_name = parts

    # Both parts must be non-empty
    if not provider or not model_name:
        return False

    return True
