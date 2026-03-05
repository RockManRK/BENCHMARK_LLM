"""Database module for SQLite persistence.

This module provides the complete database layer for the benchmark_llm project,
including schema management, data models, and repository classes for CRUD operations.

Example:
    >>> from src.db import DatabaseManager, RunRepository, Run
    >>> from pathlib import Path
    >>>
    >>> with DatabaseManager(Path("./data/benchmark.db")) as db_manager:
    ...     run_repo = RunRepository(db_manager)
    ...     run = Run(run_id="run-001")
    ...     run_repo.create(run)
"""

from src.db.models import Error, Iteration, Model, OperationalLog, Question, Response, Run
from src.db.repository import (
    ErrorRepository,
    IterationRepository,
    ModelRepository,
    ResponseRepository,
    RunRepository,
)
from src.db.schema import DatabaseManager, get_schema_sql

__all__ = [
    # Schema
    "DatabaseManager",
    "get_schema_sql",
    # Models
    "Run",
    "Model",
    "Question",
    "Response",
    "Error",
    "Iteration",
    "OperationalLog",
    # Repositories
    "RunRepository",
    "ModelRepository",
    "ResponseRepository",
    "ErrorRepository",
    "IterationRepository",
]
