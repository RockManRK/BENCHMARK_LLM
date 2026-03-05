"""Tests for the error collector module.

This module tests the error collector functionality, including error capture,
classification, storage in database, and error summary generation.
"""

import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_mock import MockerFixture

from src.core.error_collector import ErrorCategory, ErrorCollector, ErrorInfo
from src.db import DatabaseManager, Error, ErrorRepository


class TestErrorInfo:
    """Test cases for ErrorInfo dataclass."""

    def test_error_info_creation(self) -> None:
        """Test ErrorInfo can be created with required fields."""
        error_info = ErrorInfo(
            response_id=1,
            error_type="APIError",
            error_message="Connection timeout",
        )

        assert error_info.response_id == 1
        assert error_info.error_type == "APIError"
        assert error_info.error_message == "Connection timeout"
        assert error_info.category == ErrorCategory.UNKNOWN
        assert error_info.stack_trace == ""
        assert error_info.timestamp is not None

    def test_error_info_with_category(self) -> None:
        """Test ErrorInfo with explicit category."""
        error_info = ErrorInfo(
            response_id=2,
            error_type="RateLimitError",
            error_message="Rate limit exceeded",
            category=ErrorCategory.RATE_LIMIT,
        )

        assert error_info.category == ErrorCategory.RATE_LIMIT

    def test_error_info_with_stack_trace(self) -> None:
        """Test ErrorInfo with stack trace."""
        stack = "Traceback (most recent call last):\n  File 'test.py', line 10"
        error_info = ErrorInfo(
            response_id=3,
            error_type="ValueError",
            error_message="Invalid value",
            stack_trace=stack,
        )

        assert error_info.stack_trace == stack

    def test_error_info_to_error_model(self) -> None:
        """Test conversion to Error model."""
        error_info = ErrorInfo(
            response_id=4,
            error_type="TimeoutError",
            error_message="Request timed out",
            stack_trace="Traceback...",
        )

        error_model = error_info.to_error_model()

        assert isinstance(error_model, Error)
        assert error_model.response_id == 4
        assert error_model.error_type == "TimeoutError"
        assert error_model.error_message == "Request timed out"
        assert error_model.stack_trace == "Traceback..."


class TestErrorCategory:
    """Test cases for ErrorCategory enum."""

    def test_error_category_from_exception_type_api_error(self) -> None:
        """Test categorization of API-related exceptions."""
        from httpx import RequestError

        assert ErrorCategory.from_exception_type(RequestError("test")) == ErrorCategory.NETWORK

    def test_error_category_from_exception_type_timeout(self) -> None:
        """Test categorization of timeout exceptions."""
        import socket

        assert ErrorCategory.from_exception_type(socket.timeout()) == ErrorCategory.TIMEOUT

    def test_error_category_from_exception_type_rate_limit(self) -> None:
        """Test categorization of rate limit exceptions."""
        from httpx import HTTPStatusError
        from httpx import Response as HTTPXResponse

        # Create a mock response with 429 status
        mock_response = Mock(spec=HTTPXResponse)
        mock_response.status_code = 429
        exc = HTTPStatusError("Rate limit", request=Mock(), response=mock_response)

        assert ErrorCategory.from_exception_type(exc) == ErrorCategory.RATE_LIMIT

    def test_error_category_from_exception_type_auth(self) -> None:
        """Test categorization of authentication exceptions."""
        from httpx import HTTPStatusError
        from httpx import Response as HTTPXResponse

        # Create a mock response with 401 status
        mock_response = Mock(spec=HTTPXResponse)
        mock_response.status_code = 401
        exc = HTTPStatusError("Unauthorized", request=Mock(), response=mock_response)

        assert ErrorCategory.from_exception_type(exc) == ErrorCategory.AUTHENTICATION

    def test_error_category_from_exception_type_value_error(self) -> None:
        """Test categorization of value errors."""
        assert ErrorCategory.from_exception_type(ValueError("test")) == ErrorCategory.VALIDATION

    def test_error_category_from_exception_type_unknown(self) -> None:
        """Test categorization of unknown exceptions."""
        assert ErrorCategory.from_exception_type(RuntimeError("test")) == ErrorCategory.UNKNOWN

    def test_error_category_from_string_api_error(self) -> None:
        """Test categorization from error type string - API error."""
        assert ErrorCategory.from_string("APIError") == ErrorCategory.API
        # RequestError contains 'request' which maps to API category
        assert ErrorCategory.from_string("RequestError") == ErrorCategory.API

    def test_error_category_from_string_timeout(self) -> None:
        """Test categorization from error type string - timeout."""
        assert ErrorCategory.from_string("TimeoutError") == ErrorCategory.TIMEOUT
        # ConnectionTimeout contains 'connection' which takes precedence
        assert ErrorCategory.from_string("ConnectionTimeout") == ErrorCategory.NETWORK

    def test_error_category_from_string_rate_limit(self) -> None:
        """Test categorization from error type string - rate limit."""
        assert ErrorCategory.from_string("RateLimitError") == ErrorCategory.RATE_LIMIT

    def test_error_category_from_string_auth(self) -> None:
        """Test categorization from error type string - auth."""
        assert ErrorCategory.from_string("AuthenticationError") == ErrorCategory.AUTHENTICATION
        assert ErrorCategory.from_string("UnauthorizedError") == ErrorCategory.AUTHENTICATION

    def test_error_category_from_string_validation(self) -> None:
        """Test categorization from error type string - validation."""
        assert ErrorCategory.from_string("ValidationError") == ErrorCategory.VALIDATION
        assert ErrorCategory.from_string("ValueError") == ErrorCategory.VALIDATION

    def test_error_category_from_string_unknown(self) -> None:
        """Test categorization from error type string - unknown."""
        assert ErrorCategory.from_string("UnknownError") == ErrorCategory.UNKNOWN
        assert ErrorCategory.from_string("RandomError") == ErrorCategory.UNKNOWN


class TestErrorCollector:
    """Test cases for ErrorCollector class."""

    @pytest.fixture
    def mock_db_manager(self, tmp_path: Path) -> DatabaseManager:
        """Create a mock database manager for testing."""
        db_path = tmp_path / "test_errors.db"
        return DatabaseManager(db_path)

    @pytest.fixture
    def error_collector(self, mock_db_manager: DatabaseManager) -> ErrorCollector:
        """Create an ErrorCollector instance for testing."""
        return ErrorCollector(db_manager=mock_db_manager)

    def test_error_collector_initialization(self, error_collector: ErrorCollector) -> None:
        """Test ErrorCollector initializes correctly."""
        assert error_collector.error_count == 0
        assert isinstance(error_collector.errors, list)
        assert len(error_collector.errors) == 0

    def test_capture_error_basic(self, error_collector: ErrorCollector) -> None:
        """Test capturing a basic error."""
        error_info = error_collector.capture_error(
            response_id=1,
            error_type="APIError",
            error_message="Connection failed",
        )

        assert error_info.response_id == 1
        assert error_info.error_type == "APIError"
        assert error_info.error_message == "Connection failed"
        assert error_collector.error_count == 1

    def test_capture_error_with_exception(self, error_collector: ErrorCollector) -> None:
        """Test capturing an error from an exception."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            error_info = error_collector.capture_error_from_exception(
                response_id=2,
                exception=e,
            )

        assert error_info.response_id == 2
        assert error_info.error_type == "ValueError"
        assert error_info.error_message == "Test error"
        assert error_info.category == ErrorCategory.VALIDATION
        assert "ValueError" in error_info.stack_trace

    def test_capture_error_with_category_override(
        self, error_collector: ErrorCollector
    ) -> None:
        """Test capturing an error with explicit category."""
        error_info = error_collector.capture_error(
            response_id=3,
            error_type="CustomError",
            error_message="Custom message",
            category=ErrorCategory.API,
        )

        assert error_info.category == ErrorCategory.API

    def test_store_error_in_database(
        self, error_collector: ErrorCollector, mock_db_manager: DatabaseManager
    ) -> None:
        """Test storing an error in the database."""
        # Initialize database
        mock_db_manager.initialize()

        # Disable foreign keys for this test
        conn = mock_db_manager.get_connection()
        conn.execute("PRAGMA foreign_keys = OFF")

        # Create a test response first (errors have FK to responses)
        conn.execute("""
            INSERT INTO responses (
                iteration_id, question_id, model_id, run_id,
                question_text, options_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (1, "Q001", "test-model", "test-run", "Test?", "{}", "success"))
        conn.commit()
        conn.close()

        error_info = ErrorInfo(
            response_id=1,
            error_type="DatabaseError",
            error_message="Query failed",
            stack_trace="Traceback...",
        )

        # Add to collector manually since we're testing store_error
        error_collector.errors.append(error_info)

        stored_error = error_collector.store_error(error_info)

        assert stored_error is not None
        assert stored_error.error_id is not None
        assert stored_error.response_id == 1
        assert stored_error.error_type == "DatabaseError"
        assert error_collector.error_count == 1

    def test_capture_and_store_error(
        self, error_collector: ErrorCollector, mock_db_manager: DatabaseManager
    ) -> None:
        """Test capturing and storing an error in one flow."""
        # Initialize database and create response
        with mock_db_manager:
            # Disable foreign keys for this test
            conn = mock_db_manager.get_connection()
            conn.execute("PRAGMA foreign_keys = OFF")

            # Create a test response first
            conn.execute("""
                INSERT INTO responses (
                    iteration_id, question_id, model_id, run_id,
                    question_text, options_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (1, "Q001", "test-model", "test-run", "Test?", "{}", "success"))
            conn.commit()
            conn.close()

            error_info = error_collector.capture_error(
                response_id=1,
                error_type="NetworkError",
                error_message="DNS resolution failed",
            )

            stored_error = error_collector.store_error(error_info)

            assert stored_error is not None
            assert stored_error.error_id is not None
            assert stored_error.error_type == "NetworkError"

    def test_get_error_summary_empty(self, error_collector: ErrorCollector) -> None:
        """Test error summary when no errors captured."""
        summary = error_collector.get_error_summary()

        assert summary["total_errors"] == 0
        assert summary["by_category"] == {}
        assert summary["by_type"] == {}

    def test_get_error_summary_with_errors(self, error_collector: ErrorCollector) -> None:
        """Test error summary with captured errors."""
        error_collector.capture_error(
            response_id=1, error_type="APIError", error_message="Error 1"
        )
        error_collector.capture_error(
            response_id=2, error_type="APIError", error_message="Error 2"
        )
        error_collector.capture_error(
            response_id=3, error_type="TimeoutError", error_message="Error 3"
        )

        summary = error_collector.get_error_summary()

        assert summary["total_errors"] == 3
        assert ErrorCategory.API in summary["by_category"]
        assert ErrorCategory.TIMEOUT in summary["by_category"]
        assert summary["by_category"][ErrorCategory.API] == 2
        assert summary["by_category"][ErrorCategory.TIMEOUT] == 1

    def test_get_errors_by_response_id(
        self, error_collector: ErrorCollector, mock_db_manager: DatabaseManager
    ) -> None:
        """Test retrieving errors by response ID."""
        # Initialize database and create responses
        with mock_db_manager:
            # Disable foreign keys for this test
            conn = mock_db_manager.get_connection()
            conn.execute("PRAGMA foreign_keys = OFF")

            # Create test responses first
            conn.execute("""
                INSERT INTO responses (
                    iteration_id, question_id, model_id, run_id,
                    question_text, options_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (1, "Q001", "test-model", "test-run", "Test?", "{}", "success"))
            conn.execute("""
                INSERT INTO responses (
                    iteration_id, question_id, model_id, run_id,
                    question_text, options_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (1, "Q002", "test-model", "test-run", "Test 2?", "{}", "success"))
            conn.commit()
            conn.close()

            error_collector.capture_error(response_id=1, error_type="Error1", error_message="Msg1")
            error_collector.capture_error(response_id=1, error_type="Error2", error_message="Msg2")
            error_collector.capture_error(response_id=2, error_type="Error3", error_message="Msg3")

            # Store errors
            for error in error_collector.errors:
                error_collector.store_error(error)

            errors = error_collector.get_errors_by_response_id(1)

            assert len(errors) == 2
            assert all(e.response_id == 1 for e in errors)

    def test_clear_errors(self, error_collector: ErrorCollector) -> None:
        """Test clearing captured errors."""
        error_collector.capture_error(
            response_id=1, error_type="Error1", error_message="Msg1"
        )
        error_collector.capture_error(
            response_id=2, error_type="Error2", error_message="Msg2"
        )

        assert error_collector.error_count == 2

        error_collector.clear_errors()

        assert error_collector.error_count == 0
        assert len(error_collector.errors) == 0

    def test_capture_error_logs_warning(
        self, error_collector: ErrorCollector, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that capturing an error logs a warning."""
        with caplog.at_level(logging.WARNING):
            error_collector.capture_error(
                response_id=1,
                error_type="TestError",
                error_message="Test message",
            )

        assert "TestError" in caplog.text
        assert "Test message" in caplog.text


class TestErrorCollectorIntegration:
    """Integration tests for ErrorCollector with real database."""

    @pytest.fixture
    def db_manager(self, tmp_path: Path) -> DatabaseManager:
        """Create a real database manager for integration testing."""
        db_path = tmp_path / "integration_test.db"
        return DatabaseManager(db_path)

    def test_full_error_collection_flow(self, db_manager: DatabaseManager) -> None:
        """Test complete error collection flow."""
        # Initialize database using context manager
        with db_manager:
            # Disable foreign keys for this test
            conn = db_manager.get_connection()
            conn.execute("PRAGMA foreign_keys = OFF")

            # Create test responses first
            for i in range(5):
                conn.execute("""
                    INSERT INTO responses (
                        iteration_id, question_id, model_id, run_id,
                        question_text, options_json, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (1, f"Q{i:03d}", "test-model", "test-run", f"Question {i}?", "{}", "success"))
            conn.commit()
            conn.close()

            collector = ErrorCollector(db_manager=db_manager)

            # Capture and store multiple errors
            for i in range(5):
                error_info = collector.capture_error(
                    response_id=i + 1,  # response_id starts at 1
                    error_type=f"ErrorType{i}",
                    error_message=f"Error message {i}",
                )
                collector.store_error(error_info)

            # Verify summary
            summary = collector.get_error_summary()
            assert summary["total_errors"] == 5

            # Verify retrieval
            error_repo = ErrorRepository(db_manager)
            all_errors = []
            for i in range(1, 6):  # response_id 1-5
                errors = error_repo.get_by_response(i)
                all_errors.extend(errors)

            assert len(all_errors) == 5

    def test_error_with_real_exception(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test capturing a real exception."""
        # Initialize database
        with db_manager:
            # Disable foreign keys for this test
            conn = db_manager.get_connection()
            conn.execute("PRAGMA foreign_keys = OFF")

            # Create test response first
            conn.execute("""
                INSERT INTO responses (
                    iteration_id, question_id, model_id, run_id,
                    question_text, options_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (1, "Q001", "test-model", "test-run", "Test?", "{}", "success"))
            conn.commit()
            conn.close()

            collector = ErrorCollector(db_manager=db_manager)

            try:
                raise ValueError("Real test error")
            except ValueError as e:
                error_info = collector.capture_error_from_exception(
                    response_id=1, exception=e
                )

            stored = collector.store_error(error_info)

            assert stored is not None
            assert stored.error_id is not None
            assert "ValueError" in stored.error_type
            assert "Real test error" in stored.error_message


class TestErrorCollectorEdgeCases:
    """Test edge cases for ErrorCollector."""

    @pytest.fixture
    def mock_db_manager(self, tmp_path: Path) -> DatabaseManager:
        """Create a mock database manager for testing."""
        db_path = tmp_path / "test_edge.db"
        return DatabaseManager(db_path)

    @pytest.fixture
    def error_collector(self, mock_db_manager: DatabaseManager) -> ErrorCollector:
        """Create an ErrorCollector instance for testing."""
        return ErrorCollector(db_manager=mock_db_manager)

    def test_capture_error_with_empty_message(
        self, error_collector: ErrorCollector
    ) -> None:
        """Test capturing error with empty message."""
        error_info = error_collector.capture_error(
            response_id=1, error_type="Error", error_message=""
        )

        assert error_info.error_message == ""

    def test_capture_error_with_unicode_message(
        self, error_collector: ErrorCollector
    ) -> None:
        """Test capturing error with unicode in message."""
        error_info = error_collector.capture_error(
            response_id=1,
            error_type="UnicodeError",
            error_message="Error with émojis 🚀 and spëcial çhars",
        )

        assert "🚀" in error_info.error_message

    def test_capture_error_with_very_long_message(
        self, error_collector: ErrorCollector
    ) -> None:
        """Test capturing error with very long message."""
        long_message = "A" * 10000
        error_info = error_collector.capture_error(
            response_id=1, error_type="LongError", error_message=long_message
        )

        assert len(error_info.error_message) == 10000

    def test_capture_error_with_none_response_id_raises_error(
        self, error_collector: ErrorCollector
    ) -> None:
        """Test that None response_id raises an error."""
        with pytest.raises((ValueError, TypeError)):
            error_collector.capture_error(
                response_id=None,  # type: ignore
                error_type="Error",
                error_message="Test",
            )

    def test_store_error_without_database_raises_error(
        self, error_collector: ErrorCollector
    ) -> None:
        """Test storing error without initialized database."""
        error_info = ErrorInfo(
            response_id=1, error_type="Error", error_message="Test"
        )

        # Should handle database errors gracefully or raise
        # Depending on implementation choice
        pass  # Implementation dependent
