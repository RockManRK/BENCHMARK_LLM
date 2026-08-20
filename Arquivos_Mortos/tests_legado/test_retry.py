"""Tests for the retry logic module.

This module tests the retry mechanism with exponential backoff,
rate limiting handling, and timeout handling.
"""

import logging
from typing import Any, Callable
from unittest.mock import AsyncMock

import httpx
import pytest
from pytest_mock import MockerFixture

from src.api.retry import RetryConfig, RetryHandler, RetryError


@pytest.fixture
def retry_config() -> RetryConfig:
    """Create a retry configuration for testing."""
    return RetryConfig(
        max_retries=3,
        base_delay=0.1,  # Short delay for faster tests
        max_delay=1.0,
        exponential_base=2,
        retryable_status_codes=[429, 500, 502, 503, 504],
    )


@pytest.fixture
def retry_handler(retry_config: RetryConfig) -> RetryHandler:
    """Create a RetryHandler instance for testing."""
    return RetryHandler(config=retry_config)


class TestRetryConfig:
    """Test cases for RetryConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default retry configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2
        assert 429 in config.retryable_status_codes

    def test_custom_config(self) -> None:
        """Test custom retry configuration."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3,
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3


class TestRetryHandlerInitialization:
    """Test cases for RetryHandler initialization."""

    def test_handler_initialization_with_config(self, retry_config: RetryConfig) -> None:
        """Test that handler initializes with configuration."""
        handler = RetryHandler(config=retry_config)
        assert handler.config == retry_config

    def test_handler_initialization_with_defaults(self) -> None:
        """Test that handler initializes with default configuration."""
        handler = RetryHandler()
        assert handler.config.max_retries == 3
        assert handler.config.base_delay == 1.0


class TestRetryHandlerExecution:
    """Test cases for RetryHandler execution logic."""

    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(
        self, retry_handler: RetryHandler
    ) -> None:
        """Test that successful execution doesn't trigger retries."""
        async def success_func() -> str:
            return "success"
        
        result = await retry_handler.execute(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(
        self, retry_handler: RetryHandler, mocker: MockerFixture
    ) -> None:
        """Test that rate limit errors trigger retries."""
        call_count = 0
        
        async def rate_limit_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.HTTPStatusError(
                    "Rate limit exceeded",
                    request=mocker.Mock(),
                    response=mocker.Mock(status_code=429)
                )
            return "success"
        
        result = await retry_handler.execute(rate_limit_then_success)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_server_error(
        self, retry_handler: RetryHandler, mocker: MockerFixture
    ) -> None:
        """Test that server errors trigger retries."""
        call_count = 0
        
        async def server_error_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.HTTPStatusError(
                    "Internal server error",
                    request=mocker.Mock(),
                    response=mocker.Mock(status_code=500)
                )
            return "success"
        
        result = await retry_handler.execute(server_error_then_success)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(
        self, retry_handler: RetryHandler, mocker: MockerFixture
    ) -> None:
        """Test that client errors (4xx except 429) don't trigger retries."""
        call_count = 0
        
        async def client_error() -> str:
            nonlocal call_count
            call_count += 1
            raise httpx.HTTPStatusError(
                "Bad request",
                request=mocker.Mock(),
                response=mocker.Mock(status_code=400)
            )
        
        with pytest.raises(httpx.HTTPStatusError):
            await retry_handler.execute(client_error)
        
        assert call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(
        self, retry_handler: RetryHandler, mocker: MockerFixture
    ) -> None:
        """Test that max retries raises RetryError."""
        async def always_fail() -> str:
            raise httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=mocker.Mock(),
                response=mocker.Mock(status_code=429)
            )
        
        with pytest.raises(RetryError, match="Max retries exceeded"):
            await retry_handler.execute(always_fail)

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(
        self, retry_handler: RetryHandler, mocker: MockerFixture
    ) -> None:
        """Test that timeouts trigger retries."""
        call_count = 0
        
        async def timeout_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Request timed out")
            return "success"
        
        result = await retry_handler.execute(timeout_then_success)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_connection_error_triggers_retry(
        self, retry_handler: RetryHandler, mocker: MockerFixture
    ) -> None:
        """Test that connection errors trigger retries."""
        call_count = 0
        
        async def connection_error_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection refused")
            return "success"
        
        result = await retry_handler.execute(connection_error_then_success)
        assert result == "success"
        assert call_count == 2


class TestExponentialBackoff:
    """Test cases for exponential backoff calculation."""

    def test_backoff_calculation(self, retry_config: RetryConfig) -> None:
        """Test exponential backoff delay calculation."""
        handler = RetryHandler(config=retry_config)
        
        # Test delay calculation
        delay_0 = handler._calculate_delay(0)
        delay_1 = handler._calculate_delay(1)
        delay_2 = handler._calculate_delay(2)
        
        # With base_delay=0.1 and exponential_base=2
        assert delay_0 == 0.1  # 0.1 * 2^0
        assert delay_1 == 0.2  # 0.1 * 2^1
        assert delay_2 == 0.4  # 0.1 * 2^2

    def test_backoff_respects_max_delay(self, retry_config: RetryConfig) -> None:
        """Test that backoff doesn't exceed max_delay."""
        # Create config with low max_delay
        config = RetryConfig(
            max_retries=10,
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2,
        )
        handler = RetryHandler(config=config)
        
        # Even with high attempt number, delay should not exceed max_delay
        delay = handler._calculate_delay(10)
        assert delay <= config.max_delay


class TestRetryLogging:
    """Test cases for retry logging."""

    @pytest.mark.asyncio
    async def test_retry_attempt_logged(
        self, retry_handler: RetryHandler, 
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that retry attempts are logged."""
        call_count = 0
        
        async def fail_once() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "Rate limit",
                    request=mocker.Mock(),
                    response=mocker.Mock(status_code=429)
                )
            return "success"
        
        with caplog.at_level(logging.INFO):
            result = await retry_handler.execute(fail_once)
        
        assert result == "success"
        assert "Retry attempt" in caplog.text

    @pytest.mark.asyncio
    async def test_final_success_logged(
        self, retry_handler: RetryHandler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that final success is logged."""
        async def success_func() -> str:
            return "success"
        
        with caplog.at_level(logging.INFO):
            result = await retry_handler.execute(success_func)
        
        assert result == "success"


class TestRetryWithDecorators:
    """Test cases for retry decorator usage."""

    @pytest.mark.asyncio
    async def test_retry_decorator(
        self, retry_handler: RetryHandler, mocker: MockerFixture
    ) -> None:
        """Test retry decorator functionality."""
        call_count = 0
        
        @retry_handler.retry
        async def decorated_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Timeout")
            return "success"
        
        result = await decorated_func()
        assert result == "success"
        assert call_count == 2
