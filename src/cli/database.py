#!/usr/bin/env python3
"""Persistent database connection utility for CLI modules.

This module provides shared database connection management for all CLI modules:
- Persistent database file in ./data/bcllm.db
- Automatic directory creation
- Idempotent schema initialization
- Proper connection lifecycle management

Usage:
    from src.cli.database import get_database_connection
    
    conn = get_database_connection()
    try:
        # use connection
    finally:
        conn.close()
"""

import os
import sqlite3
from pathlib import Path

from src.db.schema import create_schema


def get_database_path() -> Path:
    """Get or create database directory and return path to the SQLite file.

    Honors the DATABASE_PATH environment variable when set (e.g. loaded from
    .env by the CLI entry point), so the database location can be redirected
    without copying source code — used by the CLI test suite to run against
    an isolated sandbox database. Falls back to the historical default,
    ./data/bcllm.db relative to the project root, when unset.

    Returns:
        Path to the SQLite database file. Parent directory is created if
        missing.
    """
    override = os.getenv("DATABASE_PATH")
    if override:
        db_path = Path(override).expanduser()
        if not db_path.is_absolute():
            db_path = Path(__file__).parent.parent.parent / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "bcllm.db"


def get_database_connection() -> sqlite3.Connection:
    """Get connection to persistent database with schema initialized.

    Returns:
        SQLite connection to persistent database with row_factory set.

    Note:
        Schema is created idempotently - safe to call on existing database.
        Caller is responsible for closing the connection.
        Foreign keys are enabled for CASCADE delete support.
    """
    db_path = get_database_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Enable foreign keys for CASCADE delete
    conn.execute("PRAGMA foreign_keys = ON")

    create_schema(conn)

    return conn
