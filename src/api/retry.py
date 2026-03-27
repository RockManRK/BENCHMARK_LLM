"""Retry handler module for API calls.

This module provides policy-driven retry logic. The retry handler
does not decide retry behavior - it only executes the policy passed to it.

Key Components:
- RetryHandler: Executes retry logic based on RetryPolicy
- Backoff strategies: exponential, linear, constant

The retry handler is used by the ExecutionEngine to handle transient
failures during API calls.

Example:
    >>> from src.core.execution_plan import RetryPolicy
    >>> from src.api.retry import RetryHandler
    >>>
    >>> policy = RetryPolicy(max_attempts=3, backoff='exponential')
    >>> handler = RetryHandler(policy)
    >>>
    >>> async def api_call():
    ...     # Make API call
    ...     pass
    >>>
    >>> result = await handler.execute_with_retry(api_call)
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

from src.core.execution_plan import RetryPolicy
from src.api.errors import APIError


T = TypeVar('T')


class RetryHandler:
    """Handles retry logic based on RetryPolicy.

    The retry handler is policy-driven. It does not decide which
    errors are retryable or what backoff strategy to use. It only
    executes the policy passed to it.

    Attributes:
        policy: Retry policy configuration

    Example:
        >>> policy = RetryPolicy(max_attempts=3, backoff='exponential')
        >>> handler = RetryHandler(policy)
        >>> result = await handler.execute_with_retry(some_async_func)
    """

    def __init__(self, policy: RetryPolicy | None = None) -> None:
        """Initialize retry handler.

        Args:
            policy: Retry policy configuration. Uses default if None.
        """
        self.policy = policy if policy is not None else RetryPolicy()

    def is_retryable(self, error: APIError) -> bool:
        """Check if error is retryable based on policy.

        Args:
            error: API error to check

        Returns:
            True if error type is in policy.retry_on
        """
        return error.error_type in self.policy.retry_on

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay based on backoff strategy.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds

        Backoff Strategies:
            - exponential: 2^attempt seconds
            - linear: attempt seconds
            - constant: 1 second (always)
        """
        if self.policy.backoff == 'exponential':
            return 2 ** attempt

        if self.policy.backoff == 'linear':
            return float(attempt)

        # constant
        return 1.0

    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with retry policy.

        Args:
            func: Async function to execute
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func

        Returns:
            Function result

        Raises:
            Last exception if all attempts fail
            Exception immediately if error is not retryable

        Example:
            >>> async def fetch_data():
            ...     response = await client.get(url)
            ...     return response.json()
            >>>
            >>> result = await handler.execute_with_retry(fetch_data)
        """
        last_exception: Exception | None = None

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                return await func(*args, **kwargs)

            except APIError as e:
                last_exception = e

                # Check if retryable
                if not self.is_retryable(e):
                    raise

                # Check if more attempts available
                if attempt >= self.policy.max_attempts:
                    break

                # Wait before retry
                delay = self.calculate_delay(attempt)
                await asyncio.sleep(delay)

            except Exception as e:
                # Non-APIError exceptions
                last_exception = e

                # Check if more attempts available
                if attempt >= self.policy.max_attempts:
                    break

                # Wait before retry (use default delay for unknown errors)
                delay = self.calculate_delay(attempt)
                await asyncio.sleep(delay)

        # All attempts exhausted
        if last_exception is not None:
            raise last_exception

        # Should not reach here, but satisfy type checker
        raise RuntimeError("Retry loop completed without result or exception")
