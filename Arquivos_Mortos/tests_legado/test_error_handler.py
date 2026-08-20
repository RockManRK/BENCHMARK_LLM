"""Tests for the error_handler module.

This module tests the error normalization and formatting functions
for OpenRouter API errors.
"""

import json

import pytest

from src.api.error_handler import (
    extract_error_from_raw,
    format_error_details,
    normalize_openrouter_error,
)


class TestNormalizeOpenrouterError:
    """Tests for normalize_openrouter_error function."""

    def test_normalize_rate_limit_429(self):
        """Test normalization of HTTP 429 rate limit error."""
        response_body = {"error": {"message": "Rate limit exceeded"}}
        
        result = normalize_openrouter_error(429, response_body)
        
        assert result["error_type"] == "rate_limit"
        assert result["http_status"] == 429
        assert result["message"] == "Rate limit exceeded"
        assert result["raw_body"] == response_body

    def test_normalize_authentication_401(self):
        """Test normalization of HTTP 401 authentication error."""
        response_body = {"error": {"message": "Invalid API key"}}
        
        result = normalize_openrouter_error(401, response_body)
        
        assert result["error_type"] == "authentication"
        assert result["http_status"] == 401
        assert result["message"] == "Invalid API key"

    def test_normalize_provider_error_200_with_error_body(self):
        """Test normalization of HTTP 200 with error in response body."""
        response_body = {"error": {"message": "Provider error: model unavailable"}}
        
        result = normalize_openrouter_error(200, response_body)
        
        assert result["error_type"] == "provider_error"
        assert result["http_status"] == 200
        assert result["message"] == "Provider error: model unavailable"

    def test_normalize_server_error_500(self):
        """Test normalization of HTTP 500 server error."""
        response_body = {"error": {"message": "Internal server error"}}
        
        result = normalize_openrouter_error(500, response_body)
        
        assert result["error_type"] == "server_error"
        assert result["http_status"] == 500

    def test_normalize_unknown_error_type(self):
        """Test normalization of unknown HTTP status codes."""
        response_body = {"error": {"message": "Unknown error"}}
        
        result = normalize_openrouter_error(418, response_body)  # 418 = I'm a teapot
        
        assert result["error_type"] == "api_error"  # Default for unknown
        assert result["http_status"] == 418

    def test_normalize_error_without_error_key(self):
        """Test normalization when response has message at top level."""
        response_body = {"message": "Direct error message"}
        
        result = normalize_openrouter_error(400, response_body)
        
        assert result["error_type"] == "bad_request"
        assert result["message"] == "Direct error message"

    def test_normalize_error_with_non_dict_error(self):
        """Test normalization when error is not a dict."""
        response_body = {"error": "Simple error string"}
        
        result = normalize_openrouter_error(400, response_body)
        
        assert result["error_type"] == "bad_request"
        assert result["message"] == "Simple error string"


class TestExtractErrorFromRaw:
    """Tests for extract_error_from_raw function."""

    def test_extract_error_present(self):
        """Test extraction when error is present in response."""
        raw_response = {"error": {"message": "Model not found"}}
        
        result = extract_error_from_raw(raw_response)
        
        assert result is not None
        assert result["error_type"] == "provider_error"
        assert result["message"] == "Model not found"

    def test_extract_no_error(self):
        """Test extraction when no error is present."""
        raw_response = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Hello!"}}],
        }
        
        result = extract_error_from_raw(raw_response)
        
        assert result is None

    def test_extract_error_from_choices_content(self):
        """Test extraction when error is in message content."""
        raw_response = {
            "choices": [
                {
                    "message": {
                        "content": "Error: Failed to process request"
                    }
                }
            ]
        }
        
        result = extract_error_from_raw(raw_response)
        
        assert result is not None
        assert result["error_type"] == "content_error"
        assert "Error: Failed to process request" in result["message"]

    def test_extract_no_error_in_content(self):
        """Test extraction when content doesn't contain error indicators."""
        raw_response = {
            "choices": [
                {
                    "message": {
                        "content": "The answer is B"
                    }
                }
            ]
        }
        
        result = extract_error_from_raw(raw_response)
        
        assert result is None


class TestFormatErrorDetails:
    """Tests for format_error_details function."""

    def test_format_small_error_dict(self):
        """Test formatting of small error dictionary."""
        error_dict = {
            "error_type": "rate_limit",
            "message": "Rate limit exceeded",
            "http_status": 429,
        }
        
        result = format_error_details(error_dict)
        
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["error_type"] == "rate_limit"
        assert parsed["message"] == "Rate limit exceeded"

    def test_format_large_raw_body_truncation(self):
        """Test that large raw_body is truncated."""
        large_body = {"data": "x" * 2000}  # Large body
        error_dict = {
            "error_type": "server_error",
            "message": "Server error",
            "raw_body": large_body,
        }
        
        result = format_error_details(error_dict)
        
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed.get("raw_body_truncated") is True
        assert parsed["raw_body"]["truncated"] is True

    def test_format_with_raw_body(self):
        """Test formatting with normal-sized raw_body."""
        error_dict = {
            "error_type": "authentication",
            "message": "Invalid key",
            "raw_body": {"error": {"code": "invalid_api_key"}},
        }
        
        result = format_error_details(error_dict)
        
        parsed = json.loads(result)
        assert parsed["raw_body"] == {"error": {"code": "invalid_api_key"}}


class TestErrorHandlingIntegration:
    """Integration tests for error handling scenarios."""

    def test_scenario_rate_limit(self):
        """Test complete scenario: HTTP 429 rate limit."""
        # Simulate API response
        response_body = {"error": {"message": "Rate limit exceeded"}}
        
        # Normalize
        normalized = normalize_openrouter_error(429, response_body)
        
        # Format
        details = format_error_details(normalized)
        
        # Verify
        parsed = json.loads(details)
        assert parsed["error_type"] == "rate_limit"
        assert parsed["http_status"] == 429
        assert "raw_body" in parsed

    def test_scenario_provider_error(self):
        """Test complete scenario: HTTP 200 with provider error."""
        # Simulate API response with error in body
        response_body = {
            "error": {
                "message": "Provider error: insufficient quota",
                "code": "insufficient_quota"
            }
        }
        
        # Normalize
        normalized = normalize_openrouter_error(200, response_body)
        
        # Format
        details = format_error_details(normalized)
        
        # Verify
        parsed = json.loads(details)
        assert parsed["error_type"] == "provider_error"
        assert parsed["http_status"] == 200
        assert "insufficient quota" in parsed["message"]

    def test_scenario_timeout(self):
        """Test complete scenario: timeout error."""
        # Simulate timeout error
        timeout_error = {
            "error_type": "timeout",
            "http_status": None,
            "message": "Request timed out after 180s",
            "timeout_seconds": 180,
        }
        
        # Format
        details = format_error_details(timeout_error)
        
        # Verify
        parsed = json.loads(details)
        assert parsed["error_type"] == "timeout"
        assert parsed["timeout_seconds"] == 180
