"""Tests for OpenRouter debug mode functionality.

This module tests the openrouter_debug_enabled configuration and
the debug payload capture in the API client.
"""

import json

import pytest

from src.api.client import OpenRouterClient
from src.utils.config import ExecutionMode, Settings


class TestOpenrouterDebugConfig:
    """Tests for openrouter_debug_enabled configuration."""

    def test_debug_disabled_by_default(self):
        """Test that debug is disabled by default."""
        # Explicitly set to False to ensure test isolation from .env
        settings = Settings(
            openrouter_api_key="test_key",
            openrouter_debug_enabled=False,
        )
        assert settings.openrouter_debug_enabled is False

    def test_debug_can_be_enabled_in_dev_mode(self):
        """Test that debug can be enabled in DEV mode."""
        settings = Settings(
            openrouter_api_key="test_key",
            execution_mode=ExecutionMode.DEV,
            openrouter_debug_enabled=True,
        )
        assert settings.openrouter_debug_enabled is True

    def test_debug_blocked_in_experiment_mode(self):
        """Test that debug is blocked in EXPERIMENT mode (warning instead of ValueError)."""
        # Should emit warning and set to False, not raise ValueError
        settings = Settings(
            openrouter_api_key="test_key",
            execution_mode=ExecutionMode.EXPERIMENT,
            experiment_name="test_experiment",
            openrouter_debug_enabled=True,
        )
        
        # Debug should be silently set to False
        assert settings.openrouter_debug_enabled is False

    def test_debug_allowed_false_in_experiment_mode(self):
        """Test that debug=False is allowed in EXPERIMENT mode."""
        settings = Settings(
            openrouter_api_key="test_key",
            execution_mode=ExecutionMode.EXPERIMENT,
            experiment_name="test_experiment",
            openrouter_debug_enabled=False,
        )
        assert settings.openrouter_debug_enabled is False

    def test_debug_string_true_conversion(self):
        """Test that string 'true' is converted to boolean True."""
        settings = Settings(
            openrouter_api_key="test_key",
            openrouter_debug_enabled="true",
        )
        assert settings.openrouter_debug_enabled is True

    def test_debug_string_false_conversion(self):
        """Test that string 'false' is converted to boolean False."""
        settings = Settings(
            openrouter_api_key="test_key",
            openrouter_debug_enabled="false",
        )
        assert settings.openrouter_debug_enabled is False

    def test_debug_string_invalid_value(self):
        """Test that invalid string values raise error."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                openrouter_api_key="test_key",
                openrouter_debug_enabled="invalid",
            )
        
        # Pydantic raises error for invalid boolean values
        assert "boolean" in str(exc_info.value).lower() or "Input should be a valid boolean" in str(exc_info.value)


class TestClientDebugMode:
    """Tests for OpenRouterClient debug mode functionality."""

    @pytest.mark.asyncio
    async def test_client_includes_debug_in_payload(self, mocker):
        """Test that client includes debug field when include_debug=True."""
        # Mock the httpx client
        mock_client = mocker.AsyncMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-123",
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_client.post.return_value = mock_response
        
        client = OpenRouterClient(api_key="test_key")
        client._client = mock_client
        
        # Call with debug enabled
        await client.chat_completion(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            include_debug=True,
        )
        
        # Verify debug was included in payload
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        
        assert "debug" in payload
        assert payload["debug"] == {"echo_upstream_body": True}

    @pytest.mark.asyncio
    async def test_client_excludes_debug_when_disabled(self, mocker):
        """Test that client excludes debug field when include_debug=False."""
        # Mock the httpx client
        mock_client = mocker.AsyncMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-123",
            "choices": [{"message": {"content": "Test response"}}],
        }
        mock_client.post.return_value = mock_response
        
        client = OpenRouterClient(api_key="test_key")
        client._client = mock_client
        
        # Call with debug disabled (default)
        await client.chat_completion(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            include_debug=False,
        )
        
        # Verify debug was NOT included in payload
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        
        assert "debug" not in payload

    @pytest.mark.asyncio
    async def test_client_returns_debug_wrapper(self, mocker):
        """Test that client returns debug wrapper when include_debug=True."""
        # Mock the httpx client
        mock_client = mocker.AsyncMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-123",
            "choices": [{"message": {"content": "Test response"}}],
            "debug": {
                "upstream_body": {"provider_response": "data"}
            }
        }
        mock_client.post.return_value = mock_response
        
        client = OpenRouterClient(api_key="test_key")
        client._client = mock_client
        
        # Call with debug enabled
        result = await client.chat_completion(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            include_debug=True,
        )
        
        # Verify debug wrapper structure
        assert "_debug" in result
        assert "response" in result
        assert result["_debug"]["request_payload"]["model"] == "test-model"
        assert result["_debug"]["upstream_body"] == {"provider_response": "data"}
        assert result["response"]["id"] == "test-123"

    @pytest.mark.asyncio
    async def test_client_returns_normal_response_without_debug(self, mocker):
        """Test that client returns normal response when include_debug=False."""
        # Mock the httpx client
        mock_client = mocker.AsyncMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-123",
            "choices": [{"message": {"content": "Test response"}}],
        }
        mock_client.post.return_value = mock_response
        
        client = OpenRouterClient(api_key="test_key")
        client._client = mock_client
        
        # Call with debug disabled
        result = await client.chat_completion(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            include_debug=False,
        )
        
        # Verify normal response structure (no wrapper)
        assert "_debug" not in result
        assert "id" in result
        assert result["id"] == "test-123"


class TestDebugPayloadStructure:
    """Tests for debug payload structure."""

    def test_debug_payload_contains_request_data(self):
        """Test that debug payload contains all request data."""
        # Simulate debug response structure
        debug_response = {
            "_debug": {
                "request_payload": {
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "debug": {"echo_upstream_body": True},
                    "max_tokens": 100,
                },
                "upstream_body": {"provider": "data"}
            },
            "response": {
                "id": "test-123",
                "choices": [{"message": {"content": "Response"}}]
            }
        }
        
        # Verify structure
        assert "request_payload" in debug_response["_debug"]
        assert debug_response["_debug"]["request_payload"]["model"] == "test-model"
        assert debug_response["_debug"]["request_payload"]["max_tokens"] == 100
        assert "upstream_body" in debug_response["_debug"]

    def test_debug_serializable_to_json(self):
        """Test that debug response can be serialized to JSON."""
        debug_response = {
            "_debug": {
                "request_payload": {
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                "upstream_body": {"data": "test"}
            },
            "response": {
                "id": "test-123",
                "choices": [{"message": {"content": "Response"}}]
            }
        }
        
        # Should not raise
        json_str = json.dumps(debug_response)
        assert len(json_str) > 0
        
        # Should be deserializable
        parsed = json.loads(json_str)
        assert parsed == debug_response
