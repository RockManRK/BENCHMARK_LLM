"""Tests for API retry handler module.

This module tests the retry logic that is driven by RetryPolicy.
The retry handler is policy-driven - it does not decide retry behavior,
it only executes the policy passed to it.

Domain Rules:
- Retry behavior is determined by RetryPolicy
- Backoff strategies: exponential, linear, constant
- Non-retryable errors raise immediately
- Max attempts reached raises last exception
"""

import pytest
from src_v2.core.execution_plan import RetryPolicy
from src_v2.api.retry import RetryHandler
from src_v2.api.errors import (
    APIError,
    RateLimitError,
    ServerError,
    TimeoutError,
    NetworkError,
    AuthenticationError,
    ClientError,
)


class TestRetryHandlerInitialization:
    """Test cases for RetryHandler initialization."""

    @pytest.mark.domain_rule
    def test_retry_handler_initialization(self):
        """RetryHandler initializes with RetryPolicy."""
        policy = RetryPolicy(max_attempts=3, backoff='exponential')
        handler = RetryHandler(policy)

        assert handler.policy == policy

    @pytest.mark.domain_rule
    def test_retry_handler_default_policy(self):
        """RetryHandler can use default RetryPolicy."""
        handler = RetryHandler()

        assert handler.policy.max_attempts == 3
        assert handler.policy.backoff == 'exponential'


class TestRetryHandlerIsRetryable:
    """Test cases for retryable error detection."""

    @pytest.mark.domain_rule
    def test_retry_handler_is_retryable_timeout(self):
        """Timeout is retryable when in policy."""
        policy = RetryPolicy(retry_on=('timeout', 'http_5xx'))
        handler = RetryHandler(policy)
        error = TimeoutError("Request timed out")

        assert handler.is_retryable(error) is True

    @pytest.mark.domain_rule
    def test_retry_handler_is_retryable_rate_limit(self):
        """Rate limit is retryable when in policy."""
        policy = RetryPolicy(retry_on=('http_429',))
        handler = RetryHandler(policy)
        error = RateLimitError("Rate limit exceeded")

        assert handler.is_retryable(error) is True

    @pytest.mark.domain_rule
    def test_retry_handler_is_retryable_server_error(self):
        """Server error is retryable when in policy."""
        policy = RetryPolicy(retry_on=('http_5xx',))
        handler = RetryHandler(policy)
        error = ServerError("Internal server error")

        assert handler.is_retryable(error) is True

    @pytest.mark.domain_rule
    def test_retry_handler_is_retryable_network_error(self):
        """Network error is retryable when in policy."""
        policy = RetryPolicy(retry_on=('network_error',))
        handler = RetryHandler(policy)
        error = NetworkError("Connection refused")

        assert handler.is_retryable(error) is True

    @pytest.mark.domain_rule
    def test_retry_handler_not_retryable_auth_error(self):
        """Authentication error is NOT retryable by default."""
        policy = RetryPolicy(retry_on=('timeout', 'http_5xx'))
        handler = RetryHandler(policy)
        error = AuthenticationError("Invalid API key")

        assert handler.is_retryable(error) is False

    @pytest.mark.domain_rule
    def test_retry_handler_not_retryable_client_error(self):
        """Client error is NOT retryable by default."""
        policy = RetryPolicy(retry_on=('timeout', 'http_5xx'))
        handler = RetryHandler(policy)
        error = ClientError("Bad request")

        assert handler.is_retryable(error) is False

    @pytest.mark.domain_rule
    def test_retry_handler_not_retryable_when_type_not_in_policy(self):
        """Error type not in policy is NOT retryable."""
        policy = RetryPolicy(retry_on=('timeout',))
        handler = RetryHandler(policy)
        error = ServerError("Internal server error")

        assert handler.is_retryable(error) is False


class TestRetryHandlerBackoff:
    """Test cases for backoff delay calculation."""

    @pytest.mark.domain_rule
    def test_retry_handler_exponential_backoff(self):
        """Retry handler uses exponential backoff: 2, 4, 8 seconds."""
        policy = RetryPolicy(max_attempts=3, backoff='exponential')
        handler = RetryHandler(policy)

        # Exponential: 2^attempt
        assert handler.calculate_delay(1) == 2  # 2^1
        assert handler.calculate_delay(2) == 4  # 2^2
        assert handler.calculate_delay(3) == 8  # 2^3

    @pytest.mark.domain_rule
    def test_retry_handler_linear_backoff(self):
        """Retry handler uses linear backoff: 1, 2, 3 seconds."""
        policy = RetryPolicy(max_attempts=3, backoff='linear')
        handler = RetryHandler(policy)

        # Linear: attempt * 1
        assert handler.calculate_delay(1) == 1
        assert handler.calculate_delay(2) == 2
        assert handler.calculate_delay(3) == 3

    @pytest.mark.domain_rule
    def test_retry_handler_constant_backoff(self):
        """Retry handler uses constant backoff: 1, 1, 1 seconds."""
        policy = RetryPolicy(max_attempts=3, backoff='constant')
        handler = RetryHandler(policy)

        # Constant: always 1
        assert handler.calculate_delay(1) == 1
        assert handler.calculate_delay(2) == 1
        assert handler.calculate_delay(3) == 1


class TestRetryHandlerExecute:
    """Test cases for execute_with_retry logic."""

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_retry_handler_success_on_first_attempt(self):
        """Success on first attempt returns immediately."""
        handler = RetryHandler()
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await handler.execute_with_retry(success_func)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_retry_handler_success_on_second_attempt(self):
        """Returns success on retry after first failure."""
        handler = RetryHandler(RetryPolicy(max_attempts=3))
        call_count = 0

        async def fail_once_then_success():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Timeout")
            return "success"

        result = await handler.execute_with_retry(fail_once_then_success)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_retry_handler_max_attempts_reached(self):
        """Raises last exception after max attempts reached."""
        handler = RetryHandler(RetryPolicy(max_attempts=3))
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Timeout")

        with pytest.raises(TimeoutError, match="Timeout"):
            await handler.execute_with_retry(always_fail)

        assert call_count == 3  # All attempts used

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_retry_handler_non_retryable_error_raises_immediately(self):
        """Non-retryable error raises immediately without retry."""
        handler = RetryHandler(RetryPolicy(max_attempts=3))
        call_count = 0

        async def raise_auth_error():
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("Invalid API key")

        with pytest.raises(AuthenticationError, match="Invalid API key"):
            await handler.execute_with_retry(raise_auth_error)

        assert call_count == 1  # No retry

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_retry_handler_respects_retry_on_policy(self):
        """Retry handler only retries on errors in retry_on tuple."""
        # Policy only retries on timeout, NOT on http_5xx
        handler = RetryHandler(
            RetryPolicy(max_attempts=3, retry_on=('timeout',))
        )
        call_count = 0

        async def raise_server_error():
            nonlocal call_count
            call_count += 1
            raise ServerError("Internal server error")

        with pytest.raises(ServerError):
            await handler.execute_with_retry(raise_server_error)

        assert call_count == 1  # No retry because http_5xx not in policy

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_retry_handler_passes_args_and_kwargs(self):
        """Retry handler passes arguments to wrapped function."""
        handler = RetryHandler()
        received_args = []
        received_kwargs = {}

        async def capture_args(*args, **kwargs):
            nonlocal received_args, received_kwargs
            received_args = args
            received_kwargs = kwargs
            return "done"

        await handler.execute_with_retry(
            capture_args,
            "arg1",
            "arg2",
            key1="value1",
            key2="value2",
        )

        assert received_args == ("arg1", "arg2")
        assert received_kwargs == {"key1": "value1", "key2": "value2"}
