"""Database schema and connection management for benchmark_llm.

This module provides the database schema definition, initialization functions,
and connection management utilities for the SQLite database layer.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)


def get_schema_sql() -> str:
    """Return the SQL schema for creating all database tables.

    Reads the schema from the schema.sql file for maintainability.

    Returns:
        A string containing CREATE TABLE statements for all tables:
        experiments, runs, models, questions, responses, and errors.

    Example:
        >>> schema = get_schema_sql()
        >>> assert "CREATE TABLE experiments" in schema
        >>> assert "CREATE TABLE runs" in schema
    """
    # Get the directory containing this module
    schema_path = Path(__file__).parent / "schema.sql"
    
    if not schema_path.exists():
        logger.error(f"Schema file not found at {schema_path}")
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
    
    return schema_path.read_text(encoding="utf-8")


class DatabaseManager:
    """Manages SQLite database connections and initialization.

    This class provides a centralized way to manage database connections,
    handle initialization, and ensure proper cleanup.

    Attributes:
        database_path: Path to the SQLite database file.

    Example:
        >>> from pathlib import Path
        >>> manager = DatabaseManager(Path("./data/benchmark.db"))
        >>> manager.initialize()
        >>> conn = manager.get_connection()
        >>> # ... use connection ...
        >>> conn.close()
        >>> manager.close()
    """

    def __init__(self, database_path: Path) -> None:
        """Initialize the DatabaseManager.

        Args:
            database_path: Path to the SQLite database file.

        Example:
            >>> manager = DatabaseManager(Path("./data/benchmark.db"))
        """
        self.database_path = database_path
        self._connection: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Initialize the database by creating all tables.

        This method executes the schema SQL to create all required tables
        and indexes if they don't exist.

        Raises:
            sqlite3.Error: If there's an error creating the tables.

        Example:
            >>> manager = DatabaseManager(Path("./data/benchmark.db"))
            >>> manager.initialize()
        """
        # Ensure parent directory exists (skip for in-memory databases)
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            schema_sql = get_schema_sql()
            cursor.executescript(schema_sql)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            if not self.is_in_memory():
                conn.close()

        logger.debug(f"Database initialized at {self.database_path}")

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection.

        For in-memory databases, returns the same connection to ensure
        tables persist. For file databases, returns a new connection each
        time to ensure thread safety and proper isolation.

        Returns:
            A SQLite connection to the database.

        Raises:
            sqlite3.Error: If there's an error connecting to the database.

        Example:
            >>> manager = DatabaseManager(Path("./data/benchmark.db"))
            >>> conn = manager.get_connection()
            >>> cursor = conn.cursor()
            >>> cursor.execute("SELECT 1")
            >>> conn.close()
        """
        # For in-memory databases, reuse the same connection
        if str(self.database_path) == ":memory:":
            if self._connection is None:
                self._connection = sqlite3.connect(":memory:")
                self._connection.row_factory = sqlite3.Row
                self._connection.execute("PRAGMA foreign_keys = ON")
            return self._connection
        
        # For file databases, create a new connection each time
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def close(self) -> None:
        """Close any open connections and release resources.

        This method should be called when the DatabaseManager is no
        longer needed to ensure proper cleanup.

        Example:
            >>> manager = DatabaseManager(Path("./data/benchmark.db"))
            >>> manager.initialize()
            >>> # ... use manager ...
            >>> manager.close()
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def should_close_connection(self) -> bool:
        """Check if connections should be closed after operations.

        For in-memory databases, connections should NOT be closed
        after each operation to preserve data.

        Returns:
            True if connections should be closed (file databases),
            False for in-memory databases.
        """
        return str(self.database_path) != ":memory:"
    
    def is_in_memory(self) -> bool:
        """Check if the database is in-memory.

        Returns:
            True if using in-memory database, False for file databases.
        """
        return str(self.database_path) == ":memory:"

    def __enter__(self) -> "DatabaseManager":
        """Context manager entry.

        Returns:
            The DatabaseManager instance.
        """
        self.initialize()
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object | None) -> None:
        """Context manager exit.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.
        """
        self.close()
