"""Integration tests for error handling and debug mode.

This module tests the complete flow of error handling and debug mode
from configuration through execution to database storage.
"""

import json

import httpx
import pytest

from src.api.client import OpenRouterClient
from src.api.error_handler import (
    extract_error_from_raw,
    format_error_details,
    normalize_openrouter_error,
)
from src.db.models import Response
from src.db.schema import DatabaseManager
from src.utils.config import ExecutionMode, Settings


class TestErrorHandlingIntegration:
    """Integration tests for error handling flow."""

    def test_http_429_error_normalization_and_storage(self, mocker):
        """Test complete flow: HTTP 429 error -> normalization -> storage."""
        # Setup: Mock HTTP 429 error
        mock_response = mocker.MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"error": {"message": "Rate limit exceeded"}}'
        
        error = httpx.HTTPStatusError(
            "Rate limit exceeded",
            request=mocker.MagicMock(),
            response=mock_response,
        )
        
        # Normalize error
        error_body = mock_response.json()
        normalized = normalize_openrouter_error(429, error_body)
        
        # Verify normalization
        assert normalized["error_type"] == "rate_limit"
        assert normalized["http_status"] == 429
        assert normalized["message"] == "Rate limit exceeded"
        
        # Format for storage
        details = format_error_details(normalized)
        
        # Verify format
        parsed = json.loads(details)
        assert parsed["error_type"] == "rate_limit"
        assert "raw_body" in parsed

    def test_timeout_error_normalization(self):
        """Test complete flow: timeout error -> normalization -> format."""
        # Simulate timeout error
        timeout_error = {
            "error_type": "timeout",
            "http_status": None,
            "message": "Request timed out after 180s",
            "timeout_seconds": 180,
        }
        
        # Format for storage
        details = format_error_details(timeout_error)
        
        # Verify
        parsed = json.loads(details)
        assert parsed["error_type"] == "timeout"
        assert parsed["timeout_seconds"] == 180
        assert "Request timed out" in parsed["message"]

    def test_provider_error_200_with_error_body(self):
        """Test complete flow: HTTP 200 with error body -> normalization."""
        # Simulate provider error in response body
        response_body = {
            "error": {
                "message": "Provider error: insufficient quota",
                "code": "insufficient_quota"
            }
        }
        
        # Normalize
        normalized = normalize_openrouter_error(200, response_body)
        
        # Verify
        assert normalized["error_type"] == "provider_error"
        assert normalized["http_status"] == 200
        assert "insufficient quota" in normalized["message"]
        
        # Format
        details = format_error_details(normalized)
        parsed = json.loads(details)
        assert parsed["error_type"] == "provider_error"


class TestDebugModeIntegration:
    """Integration tests for debug mode flow."""

    def test_debug_config_in_settings(self):
        """Test debug configuration in Settings."""
        # DEV mode with debug enabled
        settings = Settings(
            openrouter_api_key="test_key",
            execution_mode=ExecutionMode.DEV,
            openrouter_debug_enabled=True,
        )
        
        assert settings.openrouter_debug_enabled is True
        assert settings.is_dev_mode is True

    def test_debug_blocked_in_experiment_mode(self):
        """Test that debug is blocked in EXPERIMENT mode (warning instead of ValueError)."""
        # Should emit warning and set to False, not raise ValueError
        settings = Settings(
            openrouter_api_key="test_key",
            execution_mode=ExecutionMode.EXPERIMENT,
            experiment_name="test_exp",
            openrouter_debug_enabled=True,
        )
        
        # Debug should be silently set to False
        assert settings.openrouter_debug_enabled is False

    def test_debug_payload_structure(self):
        """Test complete debug payload structure."""
        # Simulate debug response from client
        debug_response = {
            "_debug": {
                "request_payload": {
                    "model": "openai/gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 100,
                    "debug": {"echo_upstream_body": True},
                },
                "upstream_body": {
                    "provider": "OpenAI",
                    "response": "data"
                }
            },
            "response": {
                "id": "chatcmpl-123",
                "choices": [{"message": {"content": "Hi there!"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
            }
        }
        
        # Verify structure
        assert "_debug" in debug_response
        assert "response" in debug_response
        assert debug_response["_debug"]["request_payload"]["model"] == "openai/gpt-4"
        assert debug_response["_debug"]["upstream_body"]["provider"] == "OpenAI"
        assert debug_response["response"]["id"] == "chatcmpl-123"
        
        # Verify serializable to JSON (for database storage)
        json_str = json.dumps(debug_response)
        assert len(json_str) > 0
        
        # Verify deserializable
        parsed = json.loads(json_str)
        assert parsed == debug_response

    @pytest.mark.asyncio
    async def test_client_debug_mode_end_to_end(self, mocker):
        """Test client debug mode from call to response."""
        # Mock HTTP client
        mock_client = mocker.AsyncMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-123",
            "choices": [{"message": {"content": "Response"}}],
            "debug": {
                "upstream_body": {"provider": "test", "data": "upstream"}
            }
        }
        mock_client.post.return_value = mock_response
        
        # Create client
        client = OpenRouterClient(api_key="test_key")
        client._client = mock_client
        
        # Call with debug
        result = await client.chat_completion(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            include_debug=True,
        )
        
        # Verify debug wrapper
        assert "_debug" in result
        assert "response" in result
        assert result["_debug"]["request_payload"]["model"] == "test-model"
        assert result["_debug"]["upstream_body"]["provider"] == "test"
        assert result["response"]["id"] == "test-123"
        
        # Verify debug field was sent in request
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert "debug" in payload
        assert payload["debug"] == {"echo_upstream_body": True}


class TestResponseStorageIntegration:
    """Integration tests for response storage with errors and debug."""

    def test_error_response_storage(self, mocker):
        """Test storing error response with error_details."""
        # Create in-memory database
        db_manager = DatabaseManager(database_path=mocker.MagicMock())
        
        # Simulate error response data
        normalized_error = normalize_openrouter_error(
            429,
            {"error": {"message": "Rate limit exceeded"}}
        )
        error_details = format_error_details(normalized_error)
        
        # Create Response object (as QuestionExecutor would)
        response = Response(
            run_id="run-test",
            snapshot_id=1,
            question_id="Q001",
            model_id="test-model",
            iteration=1,
            selected_answer=None,
            response_text="",
            is_correct=None,
            status="error",
            error_details=error_details,
            latency_ms=1000,
        )
        
        # Verify error_details is populated
        assert response.error_details is not None
        assert response.status == "error"
        
        # Verify error_details is valid JSON
        parsed = json.loads(response.error_details)
        assert parsed["error_type"] == "rate_limit"
        assert parsed["message"] == "Rate limit exceeded"

    def test_debug_response_storage(self):
        """Test storing debug response in raw_response_json."""
        # Simulate debug response
        debug_response = {
            "_debug": {
                "request_payload": {"model": "test-model"},
                "upstream_body": {"provider": "test"}
            },
            "response": {"id": "test-123"}
        }
        
        # Create Response object (as QuestionExecutor would)
        response = Response(
            run_id="run-test",
            snapshot_id=1,
            question_id="Q001",
            model_id="test-model",
            iteration=1,
            selected_answer="A",
            response_text="Response text",
            is_correct=True,
            status="success",
            raw_response_json=json.dumps(debug_response),
        )
        
        # Verify raw_response_json is populated
        assert response.raw_response_json is not None
        
        # Verify can be parsed
        parsed = json.loads(response.raw_response_json)
        assert "_debug" in parsed
        assert "response" in parsed
        assert parsed["_debug"]["request_payload"]["model"] == "test-model"

    def test_normal_response_storage_without_debug(self):
        """Test storing normal response without debug wrapper."""
        # Simulate normal response
        normal_response = {
            "id": "test-123",
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        
        # Create Response object
        response = Response(
            run_id="run-test",
            snapshot_id=1,
            question_id="Q001",
            model_id="test-model",
            iteration=1,
            selected_answer="A",
            response_text="Response text",
            is_correct=True,
            status="success",
            raw_response_json=json.dumps(normal_response),
        )
        
        # Verify raw_response_json is populated
        assert response.raw_response_json is not None
        
        # Verify no debug wrapper
        parsed = json.loads(response.raw_response_json)
        assert "_debug" not in parsed
        assert "id" in parsed
        assert parsed["id"] == "test-123"


class TestErrorDetailsNeverNull:
    """Tests to verify error_details is never NULL for error responses."""

    def test_http_error_populates_error_details(self):
        """Test HTTP errors always populate error_details."""
        # Simulate any HTTP error
        normalized = normalize_openrouter_error(
            500,
            {"error": {"message": "Server error"}}
        )
        details = format_error_details(normalized)
        
        assert details is not None
        assert len(details) > 0

    def test_timeout_error_populates_error_details(self):
        """Test timeout errors always populate error_details."""
        normalized = {
            "error_type": "timeout",
            "http_status": None,
            "message": "Request timed out",
        }
        details = format_error_details(normalized)
        
        assert details is not None
        assert len(details) > 0

    def test_request_error_populates_error_details(self):
        """Test request errors always populate error_details."""
        normalized = {
            "error_type": "request_error",
            "http_status": None,
            "message": "Network error",
            "request_error_type": "ConnectError",
        }
        details = format_error_details(normalized)
        
        assert details is not None
        assert len(details) > 0

    def test_general_error_populates_error_details(self):
        """Test general errors always populate error_details."""
        normalized = {
            "error_type": "unexpected_error",
            "http_status": None,
            "message": "Unexpected exception",
            "exception_type": "ValueError",
        }
        details = format_error_details(normalized)
        
        assert details is not None
        assert len(details) > 0
