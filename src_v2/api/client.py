"""API client module for LLM completions.

This module provides a provider-agnostic API client layer.
The client is a pure adapter - no database access, no configuration
resolution, no domain decisions. It only makes API calls and returns responses.

Key Components:
- CompletionProvider: Abstract base class for all providers
- OpenRouterClient: Concrete implementation for OpenRouter API
- CompletionResponse: Dataclass for API responses

The client translates HTTP errors into domain-specific error types
for consistent error handling throughout the system.

Example:
    >>> from src_v2.api.client import OpenRouterClient
    >>>
    >>> client = OpenRouterClient(api_key="your-api-key")
    >>>
    >>> response = await client.chat_completion(
    ...     model_id="openai/gpt-4",
    ...     messages=[{"role": "user", "content": "Hello!"}],
    ... )
    >>> print(response.content)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from src_v2.api.errors import (
    APIError,
    AuthenticationError,
    ClientError,
    NetworkError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ErrorClassifier,
)


@dataclass
class CompletionResponse:
    """Raw API response (provider-agnostic).

    This dataclass contains the parsed response from any completion
    provider. It is standardized across providers for consistent handling.

    Attributes:
        content: The generated text content
        model_id: Model identifier that generated the response
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated
        latency_ms: API call latency in milliseconds
        raw_response: Optional provider-specific raw response data

    Example:
        >>> response = CompletionResponse(
        ...     content="Answer is (B).",
        ...     model_id="openai/gpt-4",
        ...     input_tokens=50,
        ...     output_tokens=10,
        ...     latency_ms=500,
        ... )
    """

    content: str
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    raw_response: dict | None = None


class CompletionProvider(ABC):
    """Abstract base for all completion providers.

    This abstract base class defines the interface that all completion
    providers must implement. It ensures provider-agnostic design and
    allows easy swapping of providers.

    Example:
        >>> class CustomProvider(CompletionProvider):
        ...     async def chat_completion(self, model_id, messages, **kwargs):
        ...         # Implement provider-specific logic
        ...         return CompletionResponse(...)
    """

    @abstractmethod
    async def chat_completion(
        self,
        model_id: str,
        messages: list[dict],
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> CompletionResponse:
        """Perform chat completion API call.

        Args:
            model_id: Model identifier (provider-specific)
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            max_tokens: Maximum output tokens
            stop: Stop sequences

        Returns:
            CompletionResponse with content and metadata

        Raises:
            APIError: HTTP errors, authentication failures
            TimeoutError: Request timeouts
        """
        pass


class OpenRouterClient(CompletionProvider):
    """OpenRouter API client implementation.

    This client implements the CompletionProvider interface for the
    OpenRouter API. It handles authentication, request formatting,
    and error translation.

    Attributes:
        api_key: API key for authentication
        base_url: Base URL for API endpoints

    Example:
        >>> client = OpenRouterClient(
        ...     api_key="your-api-key",
        ...     base_url="https://openrouter.ai/api/v1",
        ... )
        >>> response = await client.chat_completion(
        ...     model_id="openai/gpt-4",
        ...     messages=[{"role": "user", "content": "Hello!"}],
        ... )
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 120,
    ) -> None:
        """Initialize OpenRouter client.

        Args:
            api_key: API key for authentication
            base_url: Base URL for API endpoints
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client.

        Should be called when the client is no longer needed to
        release resources.
        """
        await self._client.aclose()

    async def chat_completion(
        self,
        model_id: str,
        messages: list[dict],
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> CompletionResponse:
        """Perform OpenRouter chat completion.

        Args:
            model_id: Model identifier (e.g., "openai/gpt-4")
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            max_tokens: Maximum output tokens
            stop: Stop sequences

        Returns:
            CompletionResponse with content and metadata

        Raises:
            AuthenticationError: Invalid API key (401, 403)
            RateLimitError: Rate limit exceeded (429)
            ServerError: Server error (5xx)
            ClientError: Client error (4xx, non-auth)
            TimeoutError: Request timeout
            NetworkError: Network connectivity failure
        """
        start_time = time.time()

        try:
            # Build request payload
            payload: dict[str, Any] = {
                "model": model_id,
                "messages": messages,
            }

            # Add optional parameters
            if temperature is not None:
                payload["temperature"] = temperature
            if top_p is not None:
                payload["top_p"] = top_p
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if stop is not None:
                payload["stop"] = stop

            # Make the request
            response = await self._client.post(
                url=f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Handle HTTP errors
            if response.status_code >= 400:
                self._handle_http_error(response)

            # Parse successful response
            data = response.json()

            # Extract content
            content = data["choices"][0]["message"]["content"]

            # Extract token usage
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return CompletionResponse(
                content=content,
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                raw_response=data,
            )

        except httpx.TimeoutException as e:
            raise ErrorClassifier.classify_timeout(str(e))
        except httpx.ConnectError as e:
            raise ErrorClassifier.classify_network(str(e))
        except httpx.RequestError as e:
            raise NetworkError(str(e))

    def _handle_http_error(self, response: httpx.Response) -> None:
        """Handle HTTP error response.

        Args:
            response: HTTP response with error status

        Raises:
            AuthenticationError: 401, 403
            RateLimitError: 429
            ServerError: 5xx
            ClientError: 4xx (non-auth)
        """
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", str(response))
        except Exception:
            error_message = response.text or f"HTTP {response.status_code}"

        # Classify and raise appropriate error
        error = ErrorClassifier.classify_http(response.status_code, error_message)
        raise error
