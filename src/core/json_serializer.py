import json
from typing import Any


def serialize_json(data: Any, pretty: bool = False) -> str | None:
    """Serialize data to JSON string.

    Args:
        data: Data to serialize (dict, list, str, or None)
        pretty: If True, format with indent=2 for readability.
                If False, compact format with no whitespace.

    Returns:
        JSON string or None if input is None.
        If input is already a string, returns it as-is.
    """
    if data is None:
        return None

    # If already a string, assume it's already serialized JSON
    if isinstance(data, str):
        return data

    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)

    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
