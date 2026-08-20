"""Test debug wrapper compatibility for response parsing."""

import pytest
from src.api.error_handler import extract_error_from_raw


class TestDebugWrapperCompatibility:
    """Test that code works with and without _debug wrapper."""

    def test_extract_error_without_debug_wrapper(self):
        """Test error extraction from response without debug wrapper."""
        raw_response = {
            "error": {
                "message": "Invalid model",
                "type": "invalid_request_error"
            }
        }
        
        error = extract_error_from_raw(raw_response)
        
        assert error is not None
        assert error["error_type"] == "provider_error"
        assert error["message"] == "Invalid model"

    def test_extract_error_with_debug_wrapper(self):
        """Test error extraction from response with debug wrapper."""
        raw_response = {
            "_debug": {
                "request_payload": {"model": "test"},
                "upstream_body": None
            },
            "response": {
                "error": {
                    "message": "Invalid model",
                    "type": "invalid_request_error"
                }
            }
        }
        
        error = extract_error_from_raw(raw_response)
        
        assert error is not None
        assert error["error_type"] == "provider_error"
        assert error["message"] == "Invalid model"
        # raw_body should contain the full wrapper for debugging
        assert "_debug" in error["raw_body"]

    def test_extract_error_no_error_without_wrapper(self):
        """Test that None is returned when no error in unwrapped response."""
        raw_response = {
            "choices": [{"message": {"content": "Hello"}}],
            "usage": {"total_tokens": 10}
        }
        
        error = extract_error_from_raw(raw_response)
        
        assert error is None

    def test_extract_error_no_error_with_wrapper(self):
        """Test that None is returned when no error in wrapped response."""
        raw_response = {
            "_debug": {
                "request_payload": {"model": "test"},
                "upstream_body": None
            },
            "response": {
                "choices": [{"message": {"content": "Hello"}}],
                "usage": {"total_tokens": 10}
            }
        }
        
        error = extract_error_from_raw(raw_response)
        
        assert error is None

    def test_extract_error_from_choices_in_wrapper(self):
        """Test error detection from choices content in wrapped response."""
        raw_response = {
            "_debug": {
                "request_payload": {"model": "test"},
                "upstream_body": None
            },
            "response": {
                "choices": [{
                    "message": {
                        "content": "Error: Failed to process request"
                    }
                }]
            }
        }
        
        error = extract_error_from_raw(raw_response)
        
        assert error is not None
        assert error["error_type"] == "content_error"
        assert "Error: Failed to process request" in error["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
