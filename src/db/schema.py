"""Database schema and connection management for benchmark_llm.

This module provides the database schema definition, initialization functions,
and connection management utilities for the SQLite database layer.
"""

import sqlite3
from pathlib import Path
from typing import Final


def get_schema_sql() -> str:
    """Return the SQL schema for creating all database tables.

    Returns:
        A string containing CREATE TABLE statements for all tables:
        runs, models, iterations, responses, errors, and operational_logs.

    Example:
        >>> schema = get_schema_sql()
        >>> assert "CREATE TABLE runs" in schema
        >>> assert "CREATE TABLE responses" in schema
    """
    return """
    -- Table: runs
    -- Stores information about benchmark test runs
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        config TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'pending'
    );

    -- Table: models
    -- Stores information about LLM models being benchmarked
    CREATE TABLE IF NOT EXISTS models (
        model_id TEXT PRIMARY KEY,
        model_name TEXT NOT NULL,
        provider TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',  -- JSON string with model details
        context_length INTEGER,
        max_completion_tokens INTEGER
    );

    -- Table: iterations
    -- Stores information about test iterations within runs
    CREATE TABLE IF NOT EXISTS iterations (
        iteration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        iteration_number INTEGER NOT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'running',
        FOREIGN KEY (run_id) REFERENCES runs(run_id),
        FOREIGN KEY (model_id) REFERENCES models(model_id)
    );

    -- Table: responses
    -- Stores model responses to questions
    CREATE TABLE IF NOT EXISTS responses (
        response_id INTEGER PRIMARY KEY AUTOINCREMENT,
        iteration_id INTEGER NOT NULL,
        question_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        question_text TEXT NOT NULL,
        options_json TEXT NOT NULL,
        options_randomized BOOLEAN NOT NULL DEFAULT 0,
        selected_answer TEXT,
        correct_answer TEXT,
        is_correct BOOLEAN,
        response_text TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        latency_ms INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'pending',
        FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
        FOREIGN KEY (model_id) REFERENCES models(model_id),
        FOREIGN KEY (run_id) REFERENCES runs(run_id)
    );

    -- Table: errors
    -- Stores error information for failed responses
    CREATE TABLE IF NOT EXISTS errors (
        error_id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL,
        error_type TEXT NOT NULL,
        error_message TEXT NOT NULL,
        stack_trace TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (response_id) REFERENCES responses(response_id)
    );

    -- Table: operational_logs
    -- Stores operational log entries (optional, primary logging is to files)
    CREATE TABLE IF NOT EXISTS operational_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        level TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (run_id) REFERENCES runs(run_id)
    );

    -- Indexes for common query patterns
    CREATE INDEX IF NOT EXISTS idx_iterations_run_id ON iterations(run_id);
    CREATE INDEX IF NOT EXISTS idx_iterations_model_id ON iterations(model_id);
    CREATE INDEX IF NOT EXISTS idx_responses_iteration_id ON responses(iteration_id);
    CREATE INDEX IF NOT EXISTS idx_responses_run_id ON responses(run_id);
    CREATE INDEX IF NOT EXISTS idx_responses_model_id ON responses(model_id);
    CREATE INDEX IF NOT EXISTS idx_errors_response_id ON errors(response_id);
    CREATE INDEX IF NOT EXISTS idx_operational_logs_run_id ON operational_logs(run_id);
    """


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
