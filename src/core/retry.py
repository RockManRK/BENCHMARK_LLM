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
    >>> from src.core.retry import RetryHandler
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
from logging import Logger
from typing import Any, Awaitable, Callable, Optional, TypeVar

from src.core.execution_plan import RetryPolicy
from src.api.errors import APIError
from src.utils.logging_config import get_logger
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event
import logging


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

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        logger: Optional[Logger] = None,
        operation_id: str | None = None,
    ) -> None:
        """Initialize retry handler.

        Args:
            policy: Retry policy configuration. Uses default if None.
            logger: Optional logger instance. If not provided, uses get_logger('api.retry').
            operation_id: Correlation ID for the CLI invocation this
                handler's retries belong to (logging only).
        """
        self.policy = policy if policy is not None else RetryPolicy()
        self._logger = logger or get_logger('api.retry')
        self._operation_id = operation_id

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
        context: str = "",
        **kwargs: Any,
    ) -> T:
        """Execute function with retry policy.

        Args:
            func: Async function to execute
            *args: Positional arguments to pass to func
            context: Optional context string for logging (e.g., "item=run-001::var-abc::snap-xyz::it-1")
            **kwargs: Keyword arguments to pass to func

        Returns:
            Function result

        Raises:
            Last exception if all attempts fail, with _retry_attempts attribute set
            Exception immediately if error is not retryable

        Example:
            >>> async def fetch_data():
            ...     response = await client.get(url)
            ...     return response.json()
            >>>
            >>> result = await handler.execute_with_retry(fetch_data, context="item=001")
            >>> # Or with args/kwargs:
            >>> result = await handler.execute_with_retry(api_func, arg1, arg2, key=value)
        """
        # Extract operation name for logging
        operation_name = getattr(func, '__name__', 'unknown')
        max_attempts = self.policy.max_attempts

        # Build log context
        log_context = f"operation={operation_name}"
        if context:
            log_context = f"{log_context} | {context}"

        emit_event(
            self._logger, Event.RETRY_START, operation_id=self._operation_id,
            context=log_context, max_attempts=max_attempts,
        )

        last_exception: Exception | None = None
        attempt = 0

        for attempt in range(1, max_attempts + 1):
            try:
                result = await func(*args, **kwargs)

                # Log success after retry (if attempt > 1)
                if attempt > 1:
                    emit_event(
                        self._logger, Event.RETRY_SUCCESS, operation_id=self._operation_id,
                        context=log_context, attempts=attempt,
                    )

                return result

            except APIError as e:
                last_exception = e
                error_message = str(e)

                # Check if retryable
                if not self.is_retryable(e):
                    emit_event(
                        self._logger, Event.RETRY_NON_RETRYABLE, level=logging.WARNING,
                        operation_id=self._operation_id, context=log_context,
                        attempt=attempt, error_type=e.error_type,
                    )
                    raise

                # Check if more attempts available
                if attempt >= max_attempts:
                    break

                # Wait before retry
                delay = self.calculate_delay(attempt)

                emit_event(
                    self._logger, Event.RETRY_ATTEMPT, level=logging.WARNING,
                    operation_id=self._operation_id, context=log_context,
                    attempt=attempt, max_attempts=max_attempts,
                    delay_ms=round(delay * 1000), error=error_message,
                )

                await asyncio.sleep(delay)

            except Exception as e:
                # Non-APIError exceptions - use whitelist to determine retryability
                # Only explicitly transient errors are retried; all others fail fast
                last_exception = e
                error_message = str(e)
                error_type = type(e).__name__

                # Whitelist of explicitly retryable exception types
                # These represent known transient failures that are safe to retry
                RETRYABLE_EXCEPTIONS = (
                    ConnectionError,      # Network connectivity issues
                    TimeoutError,         # Request timeouts
                    OSError,              # Low-level network/OS errors
                )

                # Fail fast for programming errors and unknown exceptions
                if not isinstance(e, RETRYABLE_EXCEPTIONS):
                    emit_event(
                        self._logger, Event.RETRY_NON_RETRYABLE, level=logging.ERROR,
                        operation_id=self._operation_id, context=log_context,
                        attempt=attempt, error_type=error_type, error=error_message,
                    )
                    raise  # Programming error or unknown exception - fail immediately

                # Check if more attempts available for whitelisted exceptions
                if attempt >= max_attempts:
                    break

                # Wait before retry (use default delay for transient errors)
                delay = self.calculate_delay(attempt)

                emit_event(
                    self._logger, Event.RETRY_ATTEMPT, level=logging.WARNING,
                    operation_id=self._operation_id, context=log_context,
                    attempt=attempt, max_attempts=max_attempts,
                    delay_ms=round(delay * 1000), error=error_message,
                )

                await asyncio.sleep(delay)

        # All attempts exhausted
        if last_exception is not None:
            error_message = str(last_exception)
            emit_event(
                self._logger, Event.RETRY_EXHAUSTED, level=logging.ERROR,
                operation_id=self._operation_id, context=log_context,
                attempts=attempt, last_error=error_message,
            )
            # Attach attempt count to exception for ExecutionResult
            setattr(last_exception, '_retry_attempts', attempt)
            raise last_exception

        # Should not reach here, but satisfy type checker
        raise RuntimeError("Retry loop completed without result or exception")
