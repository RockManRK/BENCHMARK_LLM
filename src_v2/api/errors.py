"""API error hierarchy and classification module.

This module defines the error types for the API layer. All errors
are explicit - no fallback behavior, no heuristics.

Error Types:
- APIError: Base error for all API-related failures
- AuthenticationError: Authentication/authorization failures (401, 403)
- RateLimitError: Rate limit exceeded (429)
- ServerError: Server errors (5xx)
- ClientError: Client errors (4xx, non-auth)
- TimeoutError: Request timeouts
- NetworkError: Network connectivity failures

The ErrorClassifier provides static methods to classify HTTP errors
into domain-specific error types.
"""

from __future__ import annotations


class APIError(Exception):
    """Base API error.

    All API-related errors inherit from this base class.
    Each error has a type for programmatic handling.

    Attributes:
        message: Human-readable error message
        error_type: Machine-readable error type identifier
        raw_error: Optional raw error data from provider

    Example:
        >>> error = APIError("Request failed", "http_5xx")
        >>> raise error
    """

    def __init__(
        self,
        message: str,
        error_type: str,
        raw_error: dict | None = None,
    ) -> None:
        """Initialize API error.

        Args:
            message: Human-readable error message
            error_type: Machine-readable error type identifier
            raw_error: Optional raw error data from provider
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.raw_error = raw_error


class AuthenticationError(APIError):
    """Authentication/authorization failure.

    Raised when API authentication fails (HTTP 401) or
    when authorization is denied (HTTP 403).

    Example:
        >>> raise AuthenticationError("Invalid API key")
    """

    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        """Initialize authentication error.

        Args:
            message: Human-readable error message
            raw_error: Optional raw error data from provider
        """
        super().__init__(message, error_type="authentication", raw_error=raw_error)


class RateLimitError(APIError):
    """Rate limit exceeded.

    Raised when the API rate limit is exceeded (HTTP 429).
    This error is typically retryable with backoff.

    Example:
        >>> raise RateLimitError("Rate limit exceeded")
    """

    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        """Initialize rate limit error.

        Args:
            message: Human-readable error message
            raw_error: Optional raw error data from provider
        """
        super().__init__(message, error_type="http_429", raw_error=raw_error)


class ServerError(APIError):
    """Server error.

    Raised when the server returns an error (HTTP 5xx).
    These errors are typically retryable.

    Example:
        >>> raise ServerError("Internal server error")
    """

    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        """Initialize server error.

        Args:
            message: Human-readable error message
            raw_error: Optional raw error data from provider
        """
        super().__init__(message, error_type="http_5xx", raw_error=raw_error)


class ClientError(APIError):
    """Client error.

    Raised when the client sends an invalid request (HTTP 4xx, non-auth).
    These errors are typically NOT retryable.

    Example:
        >>> raise ClientError("Bad request")
    """

    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        """Initialize client error.

        Args:
            message: Human-readable error message
            raw_error: Optional raw error data from provider
        """
        super().__init__(message, error_type="http_4xx", raw_error=raw_error)


class TimeoutError(APIError):  # type: ignore
    """Request timeout.

    Raised when a request times out. This error is retryable.

    Note:
        This class shadows the built-in TimeoutError but is distinct.
        It inherits from APIError for consistent error handling.

    Example:
        >>> raise TimeoutError("Request timed out")
    """

    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        """Initialize timeout error.

        Args:
            message: Human-readable error message
            raw_error: Optional raw error data from provider
        """
        super().__init__(message, error_type="timeout", raw_error=raw_error)


class NetworkError(APIError):
    """Network connectivity error.

    Raised when network connectivity fails. This error is retryable.

    Example:
        >>> raise NetworkError("Connection refused")
    """

    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        """Initialize network error.

        Args:
            message: Human-readable error message
            raw_error: Optional raw error data from provider
        """
        super().__init__(message, error_type="network_error", raw_error=raw_error)


class ErrorClassifier:
    """Classifies HTTP errors into domain error types.

    This class provides static methods to classify errors based on
    HTTP status codes and error conditions. The classifier is
    deterministic - no heuristics, no inference.

    Example:
        >>> error = ErrorClassifier.classify_http(429, "Rate limit")
        >>> isinstance(error, RateLimitError)
        True
    """

    @staticmethod
    def classify_http(status_code: int, response_text: str) -> APIError:
        """Classify HTTP error by status code.

        Args:
            status_code: HTTP status code
            response_text: Response body text

        Returns:
            Specific APIError subclass

        Classification Rules:
            - 429 → RateLimitError
            - 5xx → ServerError
            - 401, 403 → AuthenticationError
            - 4xx (other) → ClientError
        """
        message = f"HTTP {status_code}: {response_text}"

        if status_code == 429:
            return RateLimitError(message)

        if 500 <= status_code < 600:
            return ServerError(message)

        if status_code in (401, 403):
            return AuthenticationError(message)

        if 400 <= status_code < 500:
            return ClientError(message)

        # Fallback for unexpected status codes
        return APIError(message, error_type=f"http_{status_code}")

    @staticmethod
    def classify_timeout(message: str = "Request timed out") -> TimeoutError:
        """Classify timeout error.

        Args:
            message: Error message

        Returns:
            TimeoutError instance
        """
        return TimeoutError(message)

    @staticmethod
    def classify_network(message: str = "Network error") -> NetworkError:
        """Classify network error.

        Args:
            message: Error message

        Returns:
            NetworkError instance
        """
        return NetworkError(message)
