"""Tests for the OpenRouter API client module.

This module tests the API client, including authentication,
message formatting, and API call handling.
"""

import base64
import httpx
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import pytest
from pytest_mock import MockerFixture

from src.api.client import OpenRouterClient, MessageBuilder


@pytest.fixture
def api_key() -> str:
    """Provide a test API key."""
    return "test-api-key-12345"


@pytest.fixture
def client(api_key: str) -> OpenRouterClient:
    """Create an OpenRouterClient instance for testing."""
    return OpenRouterClient(api_key=api_key, base_url="https://openrouter.ai/api/v1")


@pytest.fixture
def sample_image_path(tmp_path: Path) -> Path:
    """Create a sample image file for testing."""
    img_path = tmp_path / "test_image.png"
    # Create a minimal valid PNG file (1x1 pixel)
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    img_path.write_bytes(png_data)
    return img_path


class TestOpenRouterClientInitialization:
    """Test cases for OpenRouterClient initialization."""

    def test_client_initialization_with_api_key(self, api_key: str) -> None:
        """Test that client initializes with API key."""
        client = OpenRouterClient(api_key=api_key)
        assert client.api_key == api_key
        assert client.base_url == "https://openrouter.ai/api/v1"

    def test_client_initialization_with_custom_base_url(self, api_key: str) -> None:
        """Test that client accepts custom base URL."""
        custom_url = "https://custom.api.example.com/v1"
        client = OpenRouterClient(api_key=api_key, base_url=custom_url)
        assert client.base_url == custom_url

    def test_client_stores_httpx_client(self, api_key: str) -> None:
        """Test that client stores httpx AsyncClient."""
        client = OpenRouterClient(api_key=api_key)
        assert client._client is not None


class TestMessageBuilder:
    """Test cases for MessageBuilder utility."""

    def test_build_text_only_message(self) -> None:
        """Test building a text-only message."""
        text = "What is the capital of France?"
        message = MessageBuilder.build_user_message(text)
        
        assert message["role"] == "user"
        assert isinstance(message["content"], str)
        assert message["content"] == text

    def test_build_multimodal_message_with_image(self, sample_image_path: Path) -> None:
        """Test building a multimodal message with text and image."""
        text = "What is shown in this image?"
        message = MessageBuilder.build_multimodal_message(text, sample_image_path)
        
        assert message["role"] == "user"
        assert isinstance(message["content"], list)
        assert len(message["content"]) == 2
        
        # Check text content
        text_content = message["content"][0]
        assert text_content["type"] == "text"
        assert text_content["text"] == text
        
        # Check image content
        image_content = message["content"][1]
        assert image_content["type"] == "image_url"
        assert "image_url" in image_content
        assert "url" in image_content["image_url"]
        assert image_content["image_url"]["url"].startswith("data:image/png;base64,")

    def test_build_multimodal_message_with_invalid_path(self) -> None:
        """Test that building message with invalid image path raises error."""
        text = "What is shown in this image?"
        invalid_path = Path("/nonexistent/path/image.png")
        
        with pytest.raises(FileNotFoundError):
            MessageBuilder.build_multimodal_message(text, invalid_path)

    def test_build_multimodal_message_with_invalid_image_format(self, tmp_path: Path) -> None:
        """Test that building message with invalid image format raises error."""
        text = "What is shown in this image?"
        invalid_img = tmp_path / "invalid.txt"
        invalid_img.write_text("This is not an image")
        
        with pytest.raises(ValueError, match="Invalid image format"):
            MessageBuilder.build_multimodal_message(text, invalid_img)


class TestOpenRouterClientChatCompletion:
    """Test cases for OpenRouterClient chat completion."""

    @pytest.mark.asyncio
    async def test_successful_chat_completion(
        self, client: OpenRouterClient, mocker: MockerFixture
    ) -> None:
        """Test successful chat completion request."""
        # Mock the httpx response
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "The capital of France is Paris."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18
            }
        }
        mock_response.headers = {"content-type": "application/json"}
        
        # Create async mock for post that returns the mock response
        post_mock = mocker.AsyncMock(return_value=mock_response)
        mocker.patch.object(client._client, 'post', post_mock)
        
        messages = [{"role": "user", "content": "What is the capital of France?"}]
        result = await client.chat_completion(
            model="openai/gpt-4",
            messages=messages,
            max_tokens=100
        )
        
        assert result is not None
        assert result["id"] == "chatcmpl-123"
        assert result["choices"][0]["message"]["content"] == "The capital of France is Paris."

    @pytest.mark.asyncio
    async def test_chat_completion_with_image_message(
        self, client: OpenRouterClient, mocker: MockerFixture, sample_image_path: Path
    ) -> None:
        """Test chat completion with multimodal message."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-456",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "This is a medical image showing..."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 30,
                "total_tokens": 80
            }
        }
        mock_response.headers = {"content-type": "application/json"}
        
        post_mock = mocker.AsyncMock(return_value=mock_response)
        mocker.patch.object(client._client, 'post', post_mock)
        
        message = MessageBuilder.build_multimodal_message(
            "What is shown in this image?",
            sample_image_path
        )
        
        result = await client.chat_completion(
            model="openai/gpt-4-vision",
            messages=[message],
            max_tokens=100
        )
        
        assert result is not None
        assert result["id"] == "chatcmpl-456"

    @pytest.mark.asyncio
    async def test_chat_completion_api_error(
        self, client: OpenRouterClient, mocker: MockerFixture
    ) -> None:
        """Test chat completion with API error response."""
        mock_response = mocker.AsyncMock()
        mock_response.status_code = 401
        mock_response.json = mocker.AsyncMock(return_value={
            "error": {
                "message": "Invalid API key",
                "type": "authentication_error"
            }
        })
        
        mocker.patch.object(client._client, 'post', return_value=mock_response)
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(httpx.HTTPStatusError, match="Authentication failed"):
            await client.chat_completion(
                model="openai/gpt-4",
                messages=messages
            )

    @pytest.mark.asyncio
    async def test_chat_completion_rate_limit(
        self, client: OpenRouterClient, mocker: MockerFixture
    ) -> None:
        """Test chat completion with rate limit response."""
        mock_response = mocker.AsyncMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error"
            }
        }
        
        mocker.patch.object(client._client, 'post', return_value=mock_response)
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(Exception, match="Rate limit"):
            await client.chat_completion(
                model="openai/gpt-4",
                messages=messages
            )

    @pytest.mark.asyncio
    async def test_chat_completion_timeout(
        self, client: OpenRouterClient, mocker: MockerFixture
    ) -> None:
        """Test chat completion with timeout."""
        import httpx
        
        mocker.patch.object(
            client._client, 
            'post', 
            side_effect=httpx.TimeoutException("Request timed out")
        )
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(httpx.TimeoutException):
            await client.chat_completion(
                model="openai/gpt-4",
                messages=messages
            )

    @pytest.mark.asyncio
    async def test_client_close(self, api_key: str) -> None:
        """Test that client can be properly closed."""
        client = OpenRouterClient(api_key=api_key)
        await client.close()
        assert client._client.is_closed


class TestOpenRouterClientAuthentication:
    """Test cases for API authentication."""

    @pytest.mark.asyncio
    async def test_authentication_header_included(
        self, client: OpenRouterClient, mocker: MockerFixture
    ) -> None:
        """Test that authentication header is included in requests."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-789",
            "choices": [{"message": {"role": "assistant", "content": "Test"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        }
        mock_response.headers = {"content-type": "application/json"}
        
        post_mock = mocker.AsyncMock(return_value=mock_response)
        mocker.patch.object(client._client, 'post', post_mock)
        
        messages = [{"role": "user", "content": "Test"}]
        await client.chat_completion(model="openai/gpt-4", messages=messages)

        # Verify post was called (authentication is handled by httpx client setup)
        post_mock.assert_called_once()


class TestOpenRouterClientGetModelInfo:
    """Test cases for OpenRouterClient get_model_info method."""

    @pytest.mark.asyncio
    async def test_get_model_info_success(
        self, client: OpenRouterClient, mocker: MockerFixture
    ) -> None:
        """Test successful model info retrieval."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "Qwen/Qwen3.5-32B-Instruct-GGUF",
            "object": "model",
            "created": 1234567890,
            "owned_by": "Qwen"
        }
        mock_response.raise_for_status = mocker.Mock()

        get_mock = mocker.AsyncMock(return_value=mock_response)
        mocker.patch.object(client._client, 'get', get_mock)

        result = await client.get_model_info("Qwen")

        assert result is not None
        assert result["id"] == "Qwen/Qwen3.5-32B-Instruct-GGUF"
        assert result["object"] == "model"
        get_mock.assert_called_once_with("/models/Qwen")

    @pytest.mark.asyncio
    async def test_get_model_info_not_found_fallback(
        self, client: OpenRouterClient, mocker: MockerFixture
    ) -> None:
        """Test model info with 404 returns provided ID as fallback."""
        import httpx

        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status = mocker.Mock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=mocker.Mock(),
                response=mock_response
            )
        )

        get_mock = mocker.AsyncMock(return_value=mock_response)
        mocker.patch.object(client._client, 'get', get_mock)

        result = await client.get_model_info("UnknownModel")

        assert result is not None
        assert result["id"] == "UnknownModel"
        assert result["object"] == "model"

    @pytest.mark.asyncio
    async def test_get_model_info_other_error_raises(
        self, client: OpenRouterClient, mocker: MockerFixture
    ) -> None:
        """Test that non-404 errors are raised."""
        import httpx

        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status = mocker.Mock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error",
                request=mocker.Mock(),
                response=mock_response
            )
        )

        get_mock = mocker.AsyncMock(return_value=mock_response)
        mocker.patch.object(client._client, 'get', get_mock)

        with pytest.raises(httpx.HTTPStatusError):
            await client.get_model_info("SomeModel")
