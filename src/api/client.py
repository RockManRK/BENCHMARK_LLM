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
    >>> from src.api.client import OpenRouterClient
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

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import Logger
from typing import Any, Optional

import httpx

from src.api.errors import (
    APIError,
    AuthenticationError,
    ClientError,
    NetworkError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ErrorClassifier,
)
from src.utils.logging_config import get_logger


@dataclass
class CompletionResponse:
    """Raw API response (provider-agnostic).

    This dataclass contains the parsed response from any completion
    provider. It is standardized across providers for consistent handling.

    Attributes:
        content: The generated text content
        model_id: Model identifier that generated the response
        input_tokens: Number of input tokens used
        response_tokens: Number of output tokens generated
        latency_ms: API call latency in milliseconds
        raw_response: Optional provider-specific raw response data (dict for non-streaming, list for streaming)

    Example:
        >>> response = CompletionResponse(
        ...     content="Answer is (B).",
        ...     model_id="openai/gpt-4",
        ...     input_tokens=50,
        ...     response_tokens=10,
        ...     latency_ms=500,
        ... )
    """

    content: str
    model_id: str
    input_tokens: int
    response_tokens: int
    latency_ms: int
    raw_response: list[dict] | dict | None = None


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
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResponse:
        """Perform chat completion API call.

        Args:
            model_id: Model identifier (provider-specific)
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            max_tokens: Maximum output tokens
            stop: Stop sequences
            response_format: Response format configuration for structured outputs

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
        logger: Optional[Logger] = None,
        debug_enabled: bool = False,
    ) -> None:
        """Initialize OpenRouter client.

        Args:
            api_key: API key for authentication
            base_url: Base URL for API endpoints
            timeout: Request timeout in seconds
            logger: Optional logger instance. If not provided, uses get_logger('api.client').
            debug_enabled: Enable debug payload in API requests (default: False)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._logger = logger or get_logger('api.client')
        self._client = httpx.AsyncClient(timeout=timeout)
        self._debug_enabled = debug_enabled

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
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResponse:
        """Perform OpenRouter chat completion.

        Args:
            model_id: Model identifier (e.g., "openai/gpt-4")
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            max_tokens: Maximum output tokens
            stop: Stop sequences
            response_format: Response format configuration for structured outputs.
                            Example: {"type": "json_object"}

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

        # Calculate prompt length for logging
        prompt_length = sum(len(msg.get("content", "")) for msg in messages)

        # Log API request
        self._logger.info(
            f"API_REQUEST | endpoint=/v1 | model={model_id} | prompt_length={prompt_length}"
        )

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

            # Add response format for structured outputs
            if response_format is not None:
                payload["response_format"] = response_format

            # Enable streaming mode
            payload["stream"] = True

            # Add debug payload if enabled (per OpenRouter docs)
            if self._debug_enabled:
                payload["debug"] = {"echo_upstream_body": True}
                self._logger.info(f"DEBUG_ENABLED | adding debug payload to request for model={model_id}")
            else:
                self._logger.debug(f"DEBUG_DISABLED | debug not enabled for model={model_id}")

            # Make the request
            # Note: base_url may or may not include /v1 suffix, so ensure correct path
            base = self.base_url.rstrip('/')
            endpoint = 'v1/chat/completions' if not base.endswith('/v1') else 'chat/completions'
            response = await self._client.post(
                url=f"{base}/{endpoint}",
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

            # Parse SSE stream
            response.raise_for_status()
            chunks: list[dict] = []
            
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                
                data = line[6:]  # Remove "data: " prefix
                if data == "[DONE]":
                    break
                
                try:
                    chunk = json.loads(data)
                    chunks.append(chunk)
                except json.JSONDecodeError as e:
                    self._logger.warning(f"Failed to parse SSE chunk: {e}")
                    continue

            # Aggregate content from all chunks (streaming deltas)
            aggregated_content: str = ""
            for chunk in chunks:
                if chunk.get("choices") and len(chunk["choices"]) > 0:
                    # OpenRouter streaming uses delta, not message
                    choice = chunk["choices"][0]
                    delta = choice.get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        aggregated_content += content

            # Extract other fields from final chunk
            final_chunk = chunks[-1] if chunks else {}
            usage = final_chunk.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            # Extract finish_reason from final chunk
            finish_reason = None
            if final_chunk.get("choices") and len(final_chunk["choices"]) > 0:
                finish_reason = final_chunk["choices"][0].get("finish_reason")

            # Calculate total tokens
            total_tokens = input_tokens + output_tokens

            # Log API response
            self._logger.info(
                f"API_RESPONSE | model={model_id} | latency={latency_ms}ms | tokens={total_tokens} | finish_reason={finish_reason}"
            )

            # raw_response contains ALL chunks (including debug)
            raw_response = chunks

            return CompletionResponse(
                content=aggregated_content,
                model_id=model_id,
                input_tokens=input_tokens,
                response_tokens=output_tokens,
                latency_ms=latency_ms,
                raw_response=raw_response,
            )

        except httpx.TimeoutException as e:
            error_type = "timeout"
            error_message = str(e)
            self._logger.error(
                f"API_ERROR | model={model_id} | error_type={error_type} | error={error_message}"
            )
            raise ErrorClassifier.classify_timeout(str(e))
        except httpx.ConnectError as e:
            error_type = "network_error"
            error_message = str(e)
            self._logger.error(
                f"API_ERROR | model={model_id} | error_type={error_type} | error={error_message}"
            )
            raise ErrorClassifier.classify_network(str(e))
        except httpx.RequestError as e:
            error_type = "network_error"
            error_message = str(e)
            self._logger.error(
                f"API_ERROR | model={model_id} | error_type={error_type} | error={error_message}"
            )
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

        # Classify error type based on status code
        status_code = response.status_code
        if status_code in (401, 403):
            error_type = "authentication_error"
        elif status_code == 429:
            error_type = "rate_limit"
        elif status_code >= 500:
            error_type = "server_error"
        else:
            error_type = "client_error"

        # Log HTTP error
        self._logger.error(
            f"API_ERROR | status={status_code} | error_type={error_type} | error={error_message}"
        )

        # Classify and raise appropriate error
        error = ErrorClassifier.classify_http(status_code, error_message)
        raise error
