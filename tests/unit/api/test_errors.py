"""Tests for API error classification module.

This module tests the error hierarchy and classification logic.
All errors are explicit - no fallback behavior, no heuristics.

Domain Rules:
- HTTP 429 → RateLimitError
- HTTP 5xx → ServerError
- HTTP 401 → AuthenticationError
- HTTP 4xx (non-auth) → ClientError
- Timeout → TimeoutError
- Network failures → NetworkError
"""

import pytest
from src.api.errors import (
    APIError,
    AuthenticationError,
    RateLimitError,
    ServerError,
    ClientError,
    TimeoutError,
    NetworkError,
    ErrorClassifier,
)


class TestAPIErrorBase:
    """Test cases for base APIError class."""

    @pytest.mark.domain_rule
    def test_api_error_initialization(self):
        """Base APIError initializes with message, error_type, and raw_error."""
        error = APIError(
            message="Test error",
            error_type="test_error",
            raw_error={"code": "TEST"},
        )

        assert error.message == "Test error"
        assert error.error_type == "test_error"
        assert error.raw_error == {"code": "TEST"}

    @pytest.mark.domain_rule
    def test_api_error_raw_error_optional(self):
        """APIError can be created without raw_error."""
        error = APIError(
            message="Simple error",
            error_type="simple",
        )

        assert error.message == "Simple error"
        assert error.error_type == "simple"
        assert error.raw_error is None


class TestErrorClassifierHTTP:
    """Test cases for HTTP error classification."""

    @pytest.mark.domain_rule
    def test_error_classifier_429(self):
        """HTTP 429 → RateLimitError."""
        error = ErrorClassifier.classify_http(429, "Rate limit exceeded")

        assert isinstance(error, RateLimitError)
        assert error.error_type == "http_429"
        assert "429" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_500(self):
        """HTTP 500 → ServerError."""
        error = ErrorClassifier.classify_http(500, "Internal Server Error")

        assert isinstance(error, ServerError)
        assert error.error_type == "http_5xx"
        assert "500" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_502(self):
        """HTTP 502 → ServerError."""
        error = ErrorClassifier.classify_http(502, "Bad Gateway")

        assert isinstance(error, ServerError)
        assert error.error_type == "http_5xx"
        assert "502" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_503(self):
        """HTTP 503 → ServerError."""
        error = ErrorClassifier.classify_http(503, "Service Unavailable")

        assert isinstance(error, ServerError)
        assert error.error_type == "http_5xx"
        assert "503" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_504(self):
        """HTTP 504 → ServerError."""
        error = ErrorClassifier.classify_http(504, "Gateway TIMEOUT")

        assert isinstance(error, ServerError)
        assert error.error_type == "http_5xx"
        assert "504" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_401(self):
        """HTTP 401 → AuthenticationError."""
        error = ErrorClassifier.classify_http(401, "Unauthorized")

        assert isinstance(error, AuthenticationError)
        assert error.error_type == "authentication"
        assert "401" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_403(self):
        """HTTP 403 → AuthenticationError (authorization)."""
        error = ErrorClassifier.classify_http(403, "Forbidden")

        assert isinstance(error, AuthenticationError)
        assert error.error_type == "authentication"
        assert "403" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_404(self):
        """HTTP 404 → ClientError."""
        error = ErrorClassifier.classify_http(404, "Not Found")

        assert isinstance(error, ClientError)
        assert error.error_type == "http_4xx"
        assert "404" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_400(self):
        """HTTP 400 → ClientError."""
        error = ErrorClassifier.classify_http(400, "Bad Request")

        assert isinstance(error, ClientError)
        assert error.error_type == "http_4xx"
        assert "400" in error.message

    @pytest.mark.domain_rule
    def test_error_classifier_422(self):
        """HTTP 422 → ClientError."""
        error = ErrorClassifier.classify_http(422, "Unprocessable Entity")

        assert isinstance(error, ClientError)
        assert error.error_type == "http_4xx"
        assert "422" in error.message


class TestErrorClassifierSpecial:
    """Test cases for special error classification."""

    @pytest.mark.domain_rule
    def test_error_classifier_timeout(self):
        """Timeout → TimeoutError."""
        error = ErrorClassifier.classify_timeout()

        assert isinstance(error, TimeoutError)
        assert error.error_type == "timeout"

    @pytest.mark.domain_rule
    def test_error_classifier_network_error(self):
        """Network failure → NetworkError."""
        error = ErrorClassifier.classify_network("Connection refused")

        assert isinstance(error, NetworkError)
        assert error.error_type == "network_error"
        assert "Connection refused" in error.message


class TestErrorSubclasses:
    """Test cases for specific error subclasses."""

    @pytest.mark.domain_rule
    def test_authentication_error(self):
        """AuthenticationError has correct error_type."""
        error = AuthenticationError("Invalid API key")

        assert error.error_type == "authentication"
        assert "Invalid API key" in error.message

    @pytest.mark.domain_rule
    def test_rate_limit_error(self):
        """RateLimitError has correct error_type."""
        error = RateLimitError("Rate limit exceeded")

        assert error.error_type == "http_429"
        assert "Rate limit exceeded" in error.message

    @pytest.mark.domain_rule
    def test_server_error(self):
        """ServerError has correct error_type."""
        error = ServerError("Internal server error")

        assert error.error_type == "http_5xx"
        assert "Internal server error" in error.message

    @pytest.mark.domain_rule
    def test_client_error(self):
        """ClientError has correct error_type."""
        error = ClientError("Bad request")

        assert error.error_type == "http_4xx"
        assert "Bad request" in error.message

    @pytest.mark.domain_rule
    def test_timeout_error(self):
        """TimeoutError has correct error_type."""
        error = TimeoutError("Request timed out")

        assert error.error_type == "timeout"
        assert "Request timed out" in error.message

    @pytest.mark.domain_rule
    def test_network_error(self):
        """NetworkError has correct error_type."""
        error = NetworkError("Connection refused")

        assert error.error_type == "network_error"
        assert "Connection refused" in error.message
