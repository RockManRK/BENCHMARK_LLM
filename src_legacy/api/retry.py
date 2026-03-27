"""Retry logic module for OpenRouter API client.

This module provides retry functionality with exponential backoff
for handling transient failures, rate limiting, and timeouts.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Coroutine, ParamSpec, TypeVar

import httpx

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, message: str, last_exception: Exception | None = None) -> None:
        """Initialize RetryError.

        Args:
            message: Error message describing the failure.
            last_exception: The last exception that was raised, if any.
        """
        super().__init__(message)
        self.last_exception = last_exception


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for exponential backoff.
        max_delay: Maximum delay in seconds between retries.
        exponential_base: Base for exponential backoff calculation.
        retryable_status_codes: HTTP status codes that should trigger retries.

    Example:
        >>> config = RetryConfig(
        ...     max_retries=5,
        ...     base_delay=1.0,
        ...     max_delay=60.0,
        ... )
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_status_codes: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])


class RetryHandler:
    """Handler for retry logic with exponential backoff.

    This class provides functionality to execute async functions with
    automatic retry on transient failures.

    Attributes:
        config: RetryConfig instance controlling retry behavior.

    Example:
        >>> config = RetryConfig(max_retries=3)
        >>> handler = RetryHandler(config)
        >>> result = await handler.execute(my_async_function)
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        """Initialize the RetryHandler.

        Args:
            config: Optional RetryConfig. Uses defaults if not provided.

        Example:
            >>> handler = RetryHandler()
            >>> handler = RetryConfig(max_retries=5)
            >>> handler = RetryHandler(config)
        """
        self.config = config or RetryConfig()

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt.

        Uses exponential backoff with jitter-free calculation.

        Args:
            attempt: The current attempt number (0-indexed).

        Returns:
            Delay in seconds before the next retry attempt.

        Example:
            >>> handler = RetryHandler()
            >>> handler._calculate_delay(0)
            1.0
            >>> handler._calculate_delay(1)
            2.0
            >>> handler._calculate_delay(2)
            4.0
        """
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        return min(delay, self.config.max_delay)

    def _is_retryable_exception(self, exc: Exception) -> bool:
        """Determine if an exception should trigger a retry.

        Args:
            exc: The exception to evaluate.

        Returns:
            True if the exception should trigger a retry, False otherwise.

        Example:
            >>> handler = RetryHandler()
            >>> exc = httpx.TimeoutException("Timeout")
            >>> handler._is_retryable_exception(exc)
            True
        """
        if isinstance(exc, httpx.TimeoutException):
            return True
        
        if isinstance(exc, httpx.ConnectError):
            return True
        
        if isinstance(exc, httpx.NetworkError):
            return True
        
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in self.config.retryable_status_codes
        
        return False

    async def execute(
        self,
        func: Callable[P, Coroutine[Any, Any, T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Execute an async function with retry logic.

        Attempts to execute the function, retrying on transient failures
        with exponential backoff.

        Args:
            func: The async function to execute.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            The result of the function execution.

        Raises:
            RetryError: If all retry attempts are exhausted.
            Exception: If a non-retryable exception is raised.

        Example:
            >>> handler = RetryHandler()
            >>> result = await handler.execute(my_async_func, arg1, arg2)
        """
        last_exception: Exception | None = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"Operation succeeded after {attempt} retry attempt(s)")
                
                return result

            except Exception as exc:
                last_exception = exc
                
                if not self._is_retryable_exception(exc):
                    logger.warning(f"Non-retryable error: {exc}")
                    raise
                
                if attempt >= self.config.max_retries:
                    logger.error(f"Max retries ({self.config.max_retries}) exceeded")
                    raise RetryError(
                        f"Max retries exceeded after {self.config.max_retries} attempts",
                        last_exception=exc
                    ) from exc
                
                delay = self._calculate_delay(attempt)
                logger.info(
                    f"Retry attempt {attempt + 1}/{self.config.max_retries} "
                    f"after {delay:.2f}s delay due to: {exc}"
                )
                
                await asyncio.sleep(delay)
        
        # This should never be reached, but included for type safety
        raise RetryError(
            "Unexpected retry loop completion",
            last_exception=last_exception
        )

    def retry(
        self,
        func: Callable[P, Coroutine[Any, Any, T]],
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        """Decorator for adding retry logic to async functions.

        Args:
            func: The async function to decorate.

        Returns:
            The decorated function with retry logic.

        Example:
            >>> handler = RetryHandler()
            >>> @handler.retry
            ... async def my_func():
            ...     return "result"
        """
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await self.execute(func, *args, **kwargs)
        
        return wrapper
