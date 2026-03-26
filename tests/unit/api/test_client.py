"""Tests for API client module.

This module tests the provider-agnostic API client layer.
The client is a pure adapter - no database access, no configuration resolution,
no domain decisions. It only makes API calls and returns responses.

Domain Rules:
- Provider-agnostic design (abstract base + concrete implementation)
- Error translation: HTTP errors → domain error types
- Explicit inputs, explicit outputs
- No fallback behavior - fail explicitly on errors
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from src.api.client import (
    CompletionProvider,
    OpenRouterClient,
    CompletionResponse,
)
from src.api.errors import (
    AuthenticationError,
    RateLimitError,
    ServerError,
    TimeoutError,
    NetworkError,
    ClientError,
)


class TestCompletionProviderAbstract:
    """Test cases for abstract CompletionProvider base class."""

    @pytest.mark.domain_rule
    def test_completion_provider_is_abstract(self):
        """CompletionProvider is an abstract base class."""
        from abc import ABC

        assert issubclass(CompletionProvider, ABC)

    @pytest.mark.domain_rule
    def test_completion_provider_cannot_instantiate(self):
        """Cannot instantiate CompletionProvider directly."""
        with pytest.raises(TypeError, match="abstract"):
            CompletionProvider()

    @pytest.mark.domain_rule
    def test_completion_provider_requires_chat_completion(self):
        """Concrete implementations must implement chat_completion."""
        from abc import ABC, abstractmethod

        # Verify abstractmethod is defined
        assert 'chat_completion' in CompletionProvider.__abstractmethods__


class TestCompletionResponse:
    """Test cases for CompletionResponse dataclass."""

    @pytest.mark.domain_rule
    def test_completion_response_initialization(self):
        """CompletionResponse initializes with all required fields."""
        response = CompletionResponse(
            content="Answer is (B).",
            model_id="openai/gpt-4",
            input_tokens=50,
            output_tokens=10,
            latency_ms=500,
        )

        assert response.content == "Answer is (B)."
        assert response.model_id == "openai/gpt-4"
        assert response.input_tokens == 50
        assert response.output_tokens == 10
        assert response.latency_ms == 500

    @pytest.mark.domain_rule
    def test_completion_response_raw_response_optional(self):
        """CompletionResponse.raw_response is optional."""
        response = CompletionResponse(
            content="Answer",
            model_id="test/model",
            input_tokens=10,
            output_tokens=5,
            latency_ms=100,
        )

        assert response.raw_response is None

    @pytest.mark.domain_rule
    def test_completion_response_with_raw_response(self):
        """CompletionResponse can include raw provider response."""
        raw = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Answer"}}],
        }

        response = CompletionResponse(
            content="Answer",
            model_id="test/model",
            input_tokens=10,
            output_tokens=5,
            latency_ms=100,
            raw_response=raw,
        )

        assert response.raw_response == raw


class TestOpenRouterClientInitialization:
    """Test cases for OpenRouterClient initialization."""

    @pytest.mark.domain_rule
    def test_openrouter_client_initialization(self):
        """Client initializes with api_key and base_url."""
        client = OpenRouterClient(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

        assert client.api_key == "test-key"
        assert client.base_url == "https://openrouter.ai/api/v1"

    @pytest.mark.domain_rule
    def test_openrouter_client_default_base_url(self):
        """Client uses default base_url when not provided."""
        client = OpenRouterClient(api_key="test-key")

        assert client.base_url == "https://openrouter.ai/api/v1"

    @pytest.mark.domain_rule
    def test_openrouter_client_implements_completion_provider(self):
        """OpenRouterClient implements CompletionProvider interface."""
        client = OpenRouterClient(api_key="test-key")

        assert isinstance(client, CompletionProvider)


class TestOpenRouterClientChatCompletion:
    """Test cases for OpenRouterClient chat_completion method."""

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_success(self):
        """Successful API call returns CompletionResponse."""
        client = OpenRouterClient(api_key="test-key")

        # Mock the actual HTTP call
        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Answer is (B)."}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10},
            }
            mock_post.return_value = mock_response

            response = await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
            )

            assert isinstance(response, CompletionResponse)
            assert response.content == "Answer is (B)."
            assert response.input_tokens == 50
            assert response.output_tokens == 10

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_with_options(self):
        """Temperature, top_p, max_tokens passed correctly to API."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            mock_post.return_value = mock_response

            await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
                temperature=0.7,
                top_p=0.9,
                max_tokens=100,
                stop=["\n"],
            )

            # Verify request payload
            call_args = mock_post.call_args
            request_payload = call_args.kwargs.get("json", {})

            assert request_payload["temperature"] == 0.7
            assert request_payload["top_p"] == 0.9
            assert request_payload["max_tokens"] == 100
            assert request_payload["stop"] == ["\n"]

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_includes_auth_header(self):
        """API key included in Authorization header."""
        client = OpenRouterClient(api_key="secret-key-123")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            mock_post.return_value = mock_response

            await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
            )

            # Verify headers
            call_args = mock_post.call_args
            headers = call_args.kwargs.get("headers", {})

            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer secret-key-123"

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_includes_content_type(self):
        """Content-Type header set to application/json."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            mock_post.return_value = mock_response

            await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
            )

            call_args = mock_post.call_args
            headers = call_args.kwargs.get("headers", {})

            assert headers.get("Content-Type") == "application/json"

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_extracts_latency(self):
        """Latency extracted from response timing."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            mock_post.return_value = mock_response

            response = await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
            )

            # latency_ms should be set (implementation-dependent)
            assert response.latency_ms is not None
            assert isinstance(response.latency_ms, int)
            assert response.latency_ms >= 0


class TestOpenRouterClientErrorHandling:
    """Test cases for OpenRouterClient error handling."""

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_authentication_error(self):
        """401 → AuthenticationError."""
        client = OpenRouterClient(api_key="invalid-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {
                "error": {"message": "Invalid API key"}
            }
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
            mock_post.return_value = mock_response

            with pytest.raises(AuthenticationError, match="401"):
                await client.chat_completion(
                    model_id="openai/gpt-4",
                    messages=[{"role": "user", "content": "Question?"}],
                )

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_rate_limit_error(self):
        """429 → RateLimitError."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.json.return_value = {
                "error": {"message": "Rate limit exceeded"}
            }
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Too Many Requests",
                request=MagicMock(),
                response=mock_response,
            )
            mock_post.return_value = mock_response

            with pytest.raises(RateLimitError, match="429"):
                await client.chat_completion(
                    model_id="openai/gpt-4",
                    messages=[{"role": "user", "content": "Question?"}],
                )

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_server_error(self):
        """500 → ServerError."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {
                "error": {"message": "Internal server error"}
            }
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(),
                response=mock_response,
            )
            mock_post.return_value = mock_response

            with pytest.raises(ServerError, match="500"):
                await client.chat_completion(
                    model_id="openai/gpt-4",
                    messages=[{"role": "user", "content": "Question?"}],
                )

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_timeout_error(self):
        """Timeout → TimeoutError."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_post.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(TimeoutError, match="timed out"):
                await client.chat_completion(
                    model_id="openai/gpt-4",
                    messages=[{"role": "user", "content": "Question?"}],
                )

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_network_error(self):
        """Network failure → NetworkError."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(NetworkError, match="Connection refused"):
                await client.chat_completion(
                    model_id="openai/gpt-4",
                    messages=[{"role": "user", "content": "Question?"}],
                )

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_chat_completion_client_error(self):
        """4xx (non-auth) → ClientError."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": {"message": "Bad request"}
            }
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=mock_response,
            )
            mock_post.return_value = mock_response

            with pytest.raises(ClientError, match="400"):
                await client.chat_completion(
                    model_id="openai/gpt-4",
                    messages=[{"role": "user", "content": "Question?"}],
                )
