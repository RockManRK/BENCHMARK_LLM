"""Error collector module for benchmark_llm project.

This module provides comprehensive error handling and collection functionality,
including error capture, classification, storage in database, and summary generation.

The ErrorCollector follows the error handling philosophy defined in the product
guidelines, implementing a hybrid approach with strict mode for critical paths
and graceful degradation for non-critical paths.

Example:
    >>> from src.core.error_collector import ErrorCollector, ErrorCategory
    >>> from src.db import DatabaseManager
    >>> from pathlib import Path
    >>>
    >>> db_manager = DatabaseManager(Path("./data/benchmark.db"))
    >>> collector = ErrorCollector(db_manager)
    >>>
    >>> # Capture error from exception
    >>> try:
    ...     raise ValueError("Invalid input")
    ... except ValueError as e:
    ...     error_info = collector.capture_error_from_exception(
    ...         response_id=1, exception=e
    ...     )
    ...     collector.store_error(error_info)
    >>>
    >>> # Get error summary
    >>> summary = collector.get_error_summary()
    >>> print(f"Total errors: {summary['total_errors']}")
"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from src.db import DatabaseManager, Error, ErrorRepository


class ErrorCategory(Enum):
    """Enumeration of error categories for classification.

    Categories help in analyzing error patterns and implementing
    appropriate recovery strategies.

    Attributes:
        API: API-related errors (invalid responses, parsing errors).
        NETWORK: Network connectivity issues (connection errors, DNS failures).
        TIMEOUT: Request or connection timeouts.
        RATE_LIMIT: Rate limiting errors from API providers.
        AUTHENTICATION: Authentication/authorization failures.
        VALIDATION: Data validation errors (invalid input, schema violations).
        DATABASE: Database operation failures.
        UNKNOWN: Unclassified errors that don't fit other categories.

    Example:
        >>> category = ErrorCategory.NETWORK
        >>> print(category.value)
        network
    """

    API = "api"
    NETWORK = "network"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    DATABASE = "database"
    UNKNOWN = "unknown"

    @classmethod
    def from_exception_type(cls, exception: Exception) -> "ErrorCategory":
        """Determine error category from exception type.

        Analyzes the exception type and attributes to classify
        the error into an appropriate category.

        Args:
            exception: The exception instance to classify.

        Returns:
            The most appropriate ErrorCategory for the exception.

        Example:
            >>> import httpx
            >>> try:
            ...     raise httpx.RequestError("Connection failed")
            ... except Exception as e:
            ...     category = ErrorCategory.from_exception_type(e)
            >>> print(category)
            ErrorCategory.NETWORK
        """
        exception_type = type(exception).__name__
        exception_module = type(exception).__module__

        # Import httpx for status code checking
        try:
            from httpx import HTTPStatusError

            if isinstance(exception, HTTPStatusError):
                status_code = getattr(exception.response, "status_code", 0)
                if status_code == 429:
                    return cls.RATE_LIMIT
                elif status_code in (401, 403):
                    return cls.AUTHENTICATION
                elif status_code >= 500:
                    return cls.API
                else:
                    return cls.API
        except ImportError:
            pass

        # Check for network-related exceptions
        if exception_module == "httpx" or "RequestError" in exception_type:
            return cls.NETWORK

        # Check for timeout exceptions
        if "timeout" in exception_type.lower() or exception_module == "socket":
            return cls.TIMEOUT

        # Check for authentication errors
        if "auth" in exception_type.lower() or "unauthorized" in exception_type.lower():
            return cls.AUTHENTICATION

        # Check for validation errors
        if exception_type in ("ValueError", "TypeError", "KeyError"):
            return cls.VALIDATION

        # Check for database errors
        if "sqlite" in exception_module.lower() or "database" in exception_type.lower():
            return cls.DATABASE

        return cls.UNKNOWN

    @classmethod
    def from_string(cls, error_type: str) -> "ErrorCategory":
        """Determine error category from error type string.

        Maps common error type names to their corresponding categories.

        Args:
            error_type: The error type string (e.g., "TimeoutError", "APIError").

        Returns:
            The most appropriate ErrorCategory for the error type.

        Example:
            >>> category = ErrorCategory.from_string("RateLimitError")
            >>> print(category)
            ErrorCategory.RATE_LIMIT
        """
        error_type_lower = error_type.lower()

        # API-related errors
        if any(
            keyword in error_type_lower
            for keyword in ["api", "request", "response", "http"]
        ):
            return cls.API

        # Network errors
        if any(
            keyword in error_type_lower
            for keyword in ["network", "connection", "dns", "socket"]
        ):
            return cls.NETWORK

        # Timeout errors
        if "timeout" in error_type_lower:
            return cls.TIMEOUT

        # Rate limit errors
        if "rate" in error_type_lower or "limit" in error_type_lower:
            return cls.RATE_LIMIT

        # Authentication errors
        if any(
            keyword in error_type_lower
            for keyword in ["auth", "unauthorized", "forbidden", "permission"]
        ):
            return cls.AUTHENTICATION

        # Validation errors
        if any(
            keyword in error_type_lower
            for keyword in ["validation", "value", "type", "key", "parse"]
        ):
            return cls.VALIDATION

        # Database errors
        if "database" in error_type_lower or "db" in error_type_lower:
            return cls.DATABASE

        return cls.UNKNOWN


@dataclass
class ErrorInfo:
    """Data class containing error information.

    This class encapsulates all information about a captured error,
    providing a structured format for error storage and analysis.

    Attributes:
        response_id: ID of the response this error is associated with.
        error_type: Type/class name of the error (e.g., "ValueError", "APIError").
        error_message: Human-readable error message.
        category: Error category for classification and analysis.
        stack_trace: Full stack trace if available.
        timestamp: When the error occurred.
        context: Additional context information (optional metadata).

    Example:
        >>> error_info = ErrorInfo(
        ...     response_id=1,
        ...     error_type="TimeoutError",
        ...     error_message="Request timed out after 30s",
        ...     category=ErrorCategory.TIMEOUT
        ... )
        >>> print(error_info.error_type)
        TimeoutError
    """

    response_id: int
    error_type: str
    error_message: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    stack_trace: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict[str, Any] = field(default_factory=dict)

    def to_error_model(self) -> Error:
        """Convert ErrorInfo to database Error model.

        Creates an Error dataclass instance suitable for database storage.

        Returns:
            Error model instance with data from this ErrorInfo.

        Example:
            >>> error_info = ErrorInfo(
            ...     response_id=1,
            ...     error_type="APIError",
            ...     error_message="Connection failed"
            ... )
            >>> error_model = error_info.to_error_model()
            >>> print(error_model.response_id)
            1
        """
        return Error(
            response_id=self.response_id,
            error_type=self.error_type,
            error_message=self.error_message,
            stack_trace=self.stack_trace,
            timestamp=self.timestamp,
        )


class ErrorCollector:
    """Collector for capturing, classifying, and storing errors.

    This class provides a centralized error collection mechanism,
    enabling comprehensive error tracking and analysis throughout
    the benchmark execution.

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        errors: List of captured ErrorInfo instances in memory.
        logger: Logger instance for error logging.

    Example:
        >>> from src.db import DatabaseManager
        >>> from pathlib import Path
        >>>
        >>> db_manager = DatabaseManager(Path("./data/benchmark.db"))
        >>> collector = ErrorCollector(db_manager)
        >>>
        >>> # Capture an error
        >>> error_info = collector.capture_error(
        ...     response_id=1,
        ...     error_type="APIError",
        ...     error_message="Rate limit exceeded"
        ... )
        >>>
        >>> # Store in database
        >>> collector.store_error(error_info)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ErrorCollector.

        Args:
            db_manager: DatabaseManager instance for database operations.

        Example:
            >>> db_manager = DatabaseManager(Path("./data/benchmark.db"))
            >>> collector = ErrorCollector(db_manager)
        """
        self.db_manager = db_manager
        self.errors: list[ErrorInfo] = []
        self.logger = logging.getLogger("benchmark_llm.error_collector")

    @property
    def error_count(self) -> int:
        """Get the number of captured errors.

        Returns:
            The count of errors currently captured in memory.

        Example:
            >>> collector.error_count
            5
        """
        return len(self.errors)

    def capture_error(
        self,
        response_id: int,
        error_type: str,
        error_message: str,
        category: Optional[ErrorCategory] = None,
        stack_trace: str = "",
        context: Optional[dict[str, Any]] = None,
    ) -> ErrorInfo:
        """Capture an error with detailed information.

        Creates an ErrorInfo instance and adds it to the in-memory
        collection for later storage or analysis.

        Args:
            response_id: ID of the response this error is associated with.
            error_type: Type/class name of the error.
            error_message: Human-readable error message.
            category: Optional error category. If None, will be inferred
                from error_type.
            stack_trace: Optional stack trace string.
            context: Optional additional context metadata.

        Returns:
            The created ErrorInfo instance.

        Raises:
            ValueError: If response_id is None or invalid.

        Example:
            >>> error_info = collector.capture_error(
            ...     response_id=1,
            ...     error_type="TimeoutError",
            ...     error_message="Request timed out",
            ...     category=ErrorCategory.TIMEOUT
            ... )
        """
        if response_id is None:
            raise ValueError("response_id cannot be None")

        # Determine category if not provided
        if category is None:
            category = ErrorCategory.from_string(error_type)

        error_info = ErrorInfo(
            response_id=response_id,
            error_type=error_type,
            error_message=error_message,
            category=category,
            stack_trace=stack_trace,
            context=context or {},
        )

        self.errors.append(error_info)

        # Log the error
        self.logger.warning(
            f"Error captured: {error_type} - {error_message} "
            f"(response_id={response_id}, category={category.value})"
        )

        return error_info

    def capture_error_from_exception(
        self,
        response_id: int,
        exception: Exception,
        context: Optional[dict[str, Any]] = None,
    ) -> ErrorInfo:
        """Capture an error from an exception instance.

        Extracts error information from an exception, including
        automatic category classification and stack trace capture.

        Args:
            response_id: ID of the response this error is associated with.
            exception: The exception instance to capture.
            context: Optional additional context metadata.

        Returns:
            The created ErrorInfo instance with data extracted from exception.

        Example:
            >>> try:
            ...     raise ValueError("Invalid input")
            ... except ValueError as e:
            ...     error_info = collector.capture_error_from_exception(
            ...         response_id=1, exception=e
            ...     )
        """
        error_type = type(exception).__name__
        error_message = str(exception)
        stack_trace = traceback.format_exc()
        category = ErrorCategory.from_exception_type(exception)

        return self.capture_error(
            response_id=response_id,
            error_type=error_type,
            error_message=error_message,
            category=category,
            stack_trace=stack_trace,
            context=context,
        )

    def store_error(self, error_info: ErrorInfo) -> Optional[Error]:
        """Store an error in the database.

        Persists the error information to the database using the
        ErrorRepository.

        Args:
            error_info: ErrorInfo instance to store.

        Returns:
            The stored Error model with database-generated fields,
            or None if storage failed.

        Raises:
            sqlite3.Error: If there's a database error during storage.

        Example:
            >>> error_info = ErrorInfo(
            ...     response_id=1,
            ...     error_type="APIError",
            ...     error_message="Connection failed"
            ... )
            >>> stored_error = collector.store_error(error_info)
            >>> print(stored_error.error_id)
            1
        """
        try:
            error_repo = ErrorRepository(self.db_manager)
            error_model = error_info.to_error_model()
            stored_error = error_repo.create(error_model)
            return stored_error
        except Exception as e:
            self.logger.error(f"Failed to store error in database: {e}")
            raise

    def get_error_summary(self) -> dict[str, Any]:
        """Get a summary of captured errors.

        Generates statistics about captured errors including
        total count, breakdown by category, and breakdown by type.

        Returns:
            Dictionary containing error summary statistics:
            - total_errors: Total count of captured errors
            - by_category: Dict mapping ErrorCategory to count
            - by_type: Dict mapping error_type string to count

        Example:
            >>> summary = collector.get_error_summary()
            >>> print(f"Total errors: {summary['total_errors']}")
            >>> print(f"By category: {summary['by_category']}")
        """
        by_category: dict[ErrorCategory, int] = {}
        by_type: dict[str, int] = {}

        for error in self.errors:
            # Count by category
            if error.category in by_category:
                by_category[error.category] += 1
            else:
                by_category[error.category] = 1

            # Count by type
            if error.error_type in by_type:
                by_type[error.error_type] += 1
            else:
                by_type[error.error_type] = 1

        return {
            "total_errors": len(self.errors),
            "by_category": by_category,
            "by_type": by_type,
        }

    def get_errors_by_response_id(self, response_id: int) -> list[ErrorInfo]:
        """Get all captured errors for a specific response.

        Filters the in-memory error collection by response ID.

        Args:
            response_id: The response ID to filter by.

        Returns:
            List of ErrorInfo instances for the specified response.

        Example:
            >>> errors = collector.get_errors_by_response_id(1)
            >>> for error in errors:
            ...     print(f"{error.error_type}: {error.error_message}")
        """
        return [error for error in self.errors if error.response_id == response_id]

    def clear_errors(self) -> None:
        """Clear all captured errors from memory.

        Removes all ErrorInfo instances from the in-memory collection.
        Does not affect errors already stored in the database.

        Example:
            >>> collector.clear_errors()
            >>> print(collector.error_count)
            0
        """
        self.errors.clear()
        self.logger.info("Error collector cleared")
