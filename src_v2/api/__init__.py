"""API layer for Benchmark LLM.

This package provides the API adapter layer - a pure, provider-agnostic
interface for LLM completions. The API layer has:

- NO database access
- NO configuration resolution
- NO domain decisions
- NO fallback behavior

All inputs are explicit, all outputs are explicit.

Key Components:
- CompletionProvider: Abstract base class for all providers
- OpenRouterClient: Concrete implementation for OpenRouter API
- CompletionResponse: Standardized response dataclass
- Error hierarchy: APIError and subclasses
- ErrorClassifier: HTTP error → domain error translation
- RetryHandler: Policy-driven retry logic

Example:
    >>> from src_v2.api import OpenRouterClient, CompletionResponse
    >>> from src_v2.api.errors import AuthenticationError
    >>> from src_v2.api.retry import RetryHandler
    >>> from src_v2.core.execution_plan import RetryPolicy
    >>>
    >>> # Create client
    >>> client = OpenRouterClient(api_key="your-api-key")
    >>>
    >>> # Create retry handler
    >>> policy = RetryPolicy(max_attempts=3)
    >>> handler = RetryHandler(policy)
    >>>
    >>> # Execute with retry
    >>> async def call_api():
    ...     return await client.chat_completion(
    ...         model_id="openai/gpt-4",
    ...         messages=[{"role": "user", "content": "Hello!"}],
    ...     )
    >>>
    >>> response = await handler.execute_with_retry(call_api)
"""

from src_v2.api.client import (
    CompletionProvider,
    OpenRouterClient,
    CompletionResponse,
)

from src_v2.api.errors import (
    APIError,
    AuthenticationError,
    RateLimitError,
    ServerError,
    ClientError,
    TimeoutError,
    NetworkError,
    ErrorClassifier,
)

from src_v2.api.retry import (
    RetryHandler,
)


__all__ = [
    # Client
    'CompletionProvider',
    'OpenRouterClient',
    'CompletionResponse',
    # Errors
    'APIError',
    'AuthenticationError',
    'RateLimitError',
    'ServerError',
    'ClientError',
    'TimeoutError',
    'NetworkError',
    'ErrorClassifier',
    # Retry
    'RetryHandler',
]
