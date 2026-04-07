"""Variant signature generation.

Generates deterministic, ordered variant signatures from model_id and config.

Field order (mandatory):
1. model_name
2. reasoning_effort
3. vision
4. structured
5. temperature
6. top_p
7. top_k
8. max_output_tokens
9. reasoning_tokens

Float normalization: 3 decimal places
"""

import json
from typing import Any


# Fixed field order for signature generation
# Maps contract keys to signature keys
SIGNATURE_FIELD_ORDER = [
    ('MODEL_REASONING_EFFORT', 'reasoning'),
    ('MODEL_VISION', 'vision'),
    ('STRUCTURED_OUTPUTS', 'structured'),
    ('MODEL_TEMPERATURE', 'temp'),
    ('MODEL_TOP_P', 'top_p'),
    ('MODEL_TOP_K', 'top_k'),
    ('MODEL_MAX_TOKENS_TOTAL', 'max_tokens'),
    ('MODEL_MAX_TOKENS_REASONING', 'reasoning_tokens'),
]


def normalize_float(value: float | int | str | bool) -> str:
    """Normalize numeric value to minimal canonical representation.

    Args:
        value: Float, int, string, or bool value.

    Returns:
        String representation with no trailing zeros.
        Integers are rendered without decimal point.
        Booleans are rendered as lowercase strings.
        Other types are rendered via str().

    Examples:
        0.4    -> "0.4"
        0.400  -> "0.4"
        40.0   -> "40"
        1000.0 -> "1000"
        0.95   -> "0.95"
    """
    if isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, (int, float)):
        return f"{float(value):g}"
    return str(value)


def generate_variant_signature(model_id: str, config: dict | str) -> str:
    """Generate deterministic variant signature.
    
    Args:
        model_id: Model identifier (e.g., "google/gemini-3.1-flash-lite-preview")
        config: Configuration dict or JSON string.
    
    Returns:
        Variant signature in format:
        - "gemini-3.1-flash-lite-preview" (no config)
        - "gemini-3.1-flash-lite-preview|reasoning=low" (single config)
        - "gemini-3.1-flash-lite-preview|reasoning=xhigh|temp=0.800" (multiple)
    
    Notes:
        - Field order is fixed and mandatory
        - Floats are normalized to 3 decimal places
        - Fields not in config are skipped
        - Signature is deterministic (same inputs → same output)
    """
    if isinstance(config, str):
        config = json.loads(config)
    
    model_name = model_id.split('/')[-1]
    
    config_parts = []
    for config_key, sig_key in SIGNATURE_FIELD_ORDER:
        if config_key in config:
            value = config[config_key]
            # Treat empty strings as unset (same as None)
            if value is None or value == "":
                continue
            config_parts.append(f"{sig_key}={normalize_float(value)}")
    
    if config_parts:
        return f"{model_name}|{'|'.join(config_parts)}"
    else:
        return model_name


def parse_variant_signature(signature: str) -> dict:
    """Parse variant signature into components.
    
    Args:
        signature: Variant signature string.
    
    Returns:
        Dict with model_name and config dict.
        Note: This is for debugging/inspection only.
        Do NOT use for execution - always use config column directly.
    """
    parts = signature.split('|', 1)
    model_name = parts[0]
    
    config = {}
    if len(parts) > 1:
        for item in parts[1].split('|'):
            key, value = item.split('=', 1)
            if value in ('true', 'false'):
                config[key] = value == 'true'
            else:
                try:
                    config[key] = int(value)
                except ValueError:
                    try:
                        config[key] = float(value)
                    except ValueError:
                        config[key] = value
    
    return {'model_name': model_name, 'config': config}
