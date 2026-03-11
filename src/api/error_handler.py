"""Error handler module for OpenRouter API errors.

This module provides functions for normalizing and formatting errors
from the OpenRouter API, ensuring consistent error_details population
in the responses table.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def normalize_openrouter_error(http_status: int, response_body: dict[str, Any]) -> dict[str, Any]:
    """Normalize an OpenRouter API error into a standard format.

    Converts various error response formats from OpenRouter into a
    consistent dictionary structure for storage in error_details.

    Args:
        http_status: HTTP status code from the API response.
        response_body: The parsed JSON response body from the API.

    Returns:
        A dictionary containing normalized error information:
        - error_type: Category of error (e.g., "rate_limit", "authentication", "provider_error")
        - http_status: The HTTP status code
        - message: Human-readable error message
        - raw_body: The original response body for debugging

    Example:
        >>> error = normalize_openrouter_error(429, {"error": {"message": "Rate limit exceeded"}})
        >>> print(error["error_type"])
        rate_limit
        >>> print(error["message"])
        Rate limit exceeded
    """
    # Extract error message from various response formats
    error_message = "Unknown error"
    
    # Try to extract message from standard OpenRouter format
    if "error" in response_body:
        error_data = response_body["error"]
        if isinstance(error_data, dict):
            error_message = error_data.get("message", str(error_data))
        else:
            error_message = str(error_data)
    elif "message" in response_body:
        error_message = response_body["message"]
    
    # Determine error type based on HTTP status
    error_type_map = {
        400: "bad_request",
        401: "authentication",
        403: "forbidden",
        404: "not_found",
        429: "rate_limit",
        500: "server_error",
        502: "bad_gateway",
        503: "service_unavailable",
        504: "gateway_timeout",
    }
    
    error_type = error_type_map.get(http_status, "api_error")
    
    # Special handling for 200 with provider error in body
    if http_status == 200 and "error" in response_body:
        error_type = "provider_error"
        logger.warning(f"HTTP 200 with error in body: {error_message}")
    
    normalized = {
        "error_type": error_type,
        "http_status": http_status,
        "message": error_message,
        "raw_body": response_body,
    }
    
    logger.debug(f"Normalized error: type={error_type}, status={http_status}, message={error_message}")
    return normalized


def extract_error_from_raw(raw_response: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Extract error information from a raw API response.

    Checks if a raw API response contains error information and
    extracts it into a normalized format.
    
    Handles both wrapped (with _debug) and unwrapped responses:
    - If wrapped: extracts error from raw_response.get("response", raw_response)
    - If unwrapped: extracts error from raw_response directly

    Args:
        raw_response: The raw API response dictionary.
            If debug enabled: {"_debug": {...}, "response": {...}}
            Otherwise: {...} (direct API response)

    Returns:
        A normalized error dictionary if an error is found, None otherwise.
        The returned dict has the same structure as normalize_openrouter_error().

    Example:
        >>> response = {"error": {"message": "Invalid model"}}
        >>> error = extract_error_from_raw(response)
        >>> if error:
        ...     print(f"Error: {error['message']}")
    """
    # Handle debug wrapper format:
    # If debug enabled, response is in raw_response['response']; otherwise, use raw_response directly
    response_data = raw_response.get("response", raw_response)
    
    # Check for error in response
    if "error" in response_data:
        # Assume this is an error response with status 200
        # Normalize using response_data but preserve raw_response for raw_body
        normalized = normalize_openrouter_error(200, response_data)
        # Override raw_body with full raw_response to preserve debug wrapper
        normalized["raw_body"] = raw_response
        return normalized

    # Check for error in choices (some providers return errors this way)
    choices = response_data.get("choices", [])
    if choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message", {})
            if isinstance(message, dict):
                # Check for error indicators in the message
                content = message.get("content", "")
                if "error" in content.lower() or "failed" in content.lower():
                    logger.warning(f"Potential error in response content: {content[:200]}")
                    return {
                        "error_type": "content_error",
                        "http_status": 200,
                        "message": content,
                        "raw_body": raw_response,
                    }

    # No error found
    return None


def format_error_details(error_dict: dict[str, Any]) -> str:
    """Format an error dictionary as a string for storage.

    Converts a normalized error dictionary into a JSON string
    suitable for storage in the error_details column.

    Args:
        error_dict: Normalized error dictionary from normalize_openrouter_error().

    Returns:
        JSON string representation of the error dictionary.

    Example:
        >>> error = {"error_type": "rate_limit", "message": "Rate limit exceeded"}
        >>> details = format_error_details(error)
        >>> print(details)
        {"error_type": "rate_limit", "message": "Rate limit exceeded"}
    """
    import json
    
    try:
        # Remove raw_body from formatted string if it's too large
        display_dict = error_dict.copy()
        raw_body = display_dict.get("raw_body")
        
        if raw_body and len(json.dumps(raw_body)) > 1000:
            # Truncate large raw_body for readability
            display_dict["raw_body_truncated"] = True
            display_dict["raw_body"] = {"truncated": True, "note": "See raw_response_json for full details"}
        
        return json.dumps(display_dict, indent=2, default=str)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to format error details: {e}")
        return json.dumps({"error": "Failed to format error details", "original": str(error_dict)})
