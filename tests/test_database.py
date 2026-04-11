"""Tests for the database module.

This module tests the database schema, models, and repository layer
for the benchmark_llm project.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import pytest

from src.db.models import Response, Run
from src.db.repository import (
    ModelRepository,
    ResponseRepository,
    RunRepository,
)
from src.db.schema import DatabaseManager, get_schema_sql


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path for testing."""
    return tmp_path / "test_benchmark.db"


@pytest.fixture
def db_manager(temp_db_path: Path) -> Generator[DatabaseManager, None, None]:
    """Create a DatabaseManager instance with a temporary database."""
    manager = DatabaseManager(temp_db_path)
    manager.initialize()
    yield manager
    manager.close()


@pytest.fixture
def db_connection(db_manager: DatabaseManager) -> Generator[sqlite3.Connection, None, None]:
    """Create a database connection for testing."""
    conn = db_manager.get_connection()
    yield conn
    conn.close()


class TestDatabaseSchema:
    """Test cases for database schema and initialization."""

    def test_get_schema_sql_returns_valid_sql(self) -> None:
        """Test that get_schema_sql returns valid CREATE TABLE statements."""
        schema = get_schema_sql()
        assert isinstance(schema, str)
        assert len(schema) > 0
        assert "CREATE TABLE" in schema
        assert "runs" in schema
        assert "models" in schema
        assert "responses" in schema
        assert "errors" in schema
        assert "operational_logs" in schema

    def test_database_initialization_creates_tables(self, db_connection: sqlite3.Connection) -> None:
        """Test that database initialization creates all required tables."""
        cursor = db_connection.cursor()

        # Get all table names
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "runs",
            "models",
            "responses",
            "errors",
            "operational_logs",
        }

        assert expected_tables.issubset(tables)

    def test_runs_table_schema(self, db_connection: sqlite3.Connection) -> None:
        """Test that runs table has correct schema."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(runs)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert "run_id" in columns
        assert "created_at" in columns
        assert "config" in columns
        assert "status" in columns

    def test_models_table_schema(self, db_connection: sqlite3.Connection) -> None:
        """Test that models table has correct schema."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(models)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert "model_id" in columns
        assert "model_name" in columns
        assert "provider" in columns

    def test_responses_table_schema(self, db_connection: sqlite3.Connection) -> None:
        """Test that responses table has correct schema."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(responses)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        # Identification
        assert "response_id" in columns
        assert "run_id" in columns
        assert "snapshot_id" in columns
        assert "question_id" in columns
        assert "model_id" in columns
        assert "iteration" in columns

        # Response data
        assert "selected_answer" in columns
        assert "response_text" in columns
        assert "is_correct" in columns
        assert "status" in columns

        # Termination
        assert "finish_reason" in columns
        assert "error_details" in columns

        # Performance
        assert "latency_ms" in columns

        # Tokens
        assert "input_tokens" in columns
        assert "response_tokens" in columns
        assert "total_tokens" in columns
        assert "reasoning_tokens" in columns
        assert "effective_tokens" in columns

        # Cost
        assert "cost" in columns

        # Audit
        assert "raw_response_json" in columns
        assert "timestamp" in columns

        # Manual review
        assert "parse_confidence" in columns
        assert "review_status" in columns
        assert "reviewed_at" in columns
        assert "manual_answer" in columns

    def test_errors_table_schema(self, db_connection: sqlite3.Connection) -> None:
        """Test that errors table has correct schema."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(errors)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert "error_id" in columns
        assert "response_id" in columns
        assert "error_type" in columns
        assert "error_message" in columns
        assert "stack_trace" in columns
        assert "timestamp" in columns

    def test_operational_logs_table_schema(self, db_connection: sqlite3.Connection) -> None:
        """Test that operational_logs table has correct schema."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(operational_logs)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert "log_id" in columns
        assert "run_id" in columns
        assert "level" in columns
        assert "message" in columns
        assert "timestamp" in columns

    def test_database_manager_connection(self, temp_db_path: Path) -> None:
        """Test that DatabaseManager can create connections."""
        manager = DatabaseManager(temp_db_path)
        conn = manager.get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        conn.close()
        manager.close()

    def test_database_manager_close(self, temp_db_path: Path) -> None:
        """Test that DatabaseManager can be closed."""
        manager = DatabaseManager(temp_db_path)
        manager.initialize()
        manager.close()
        # Should not raise an error


class TestModels:
    """Test cases for data models."""

    def test_run_dataclass_creation(self) -> None:
        """Test creating a Run dataclass instance."""
        run = Run(
            run_id="test-run-001",
            created_at=datetime.now(),
            config='{"models": ["gpt-4"], "iterations": 3}',
            status="pending",
        )
        assert run.run_id == "test-run-001"
        assert run.status == "pending"

    def test_run_dataclass_defaults(self) -> None:
        """Test Run dataclass default values."""
        run = Run(run_id="test-run-002")
        assert run.status == "pending"
        assert run.config == "{}"

    def test_response_dataclass_creation(self) -> None:
        """Test creating a Response dataclass instance."""
        response = Response(
            run_id="test-run-001",
            snapshot_id=1,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
            selected_answer="A",
            correct_answer="A",
            is_correct=True,
            response_text="The capital of France is Paris.",
            input_tokens=50,
            response_tokens=20,
            latency_ms=1500,
            status="success",
        )
        assert response.question_id == "Q001"
        assert response.selected_answer == "A"
        assert response.is_correct is True

    def test_response_dataclass_defaults(self) -> None:
        """Test Response dataclass default values."""
        response = Response(
            run_id="test-run-001",
            snapshot_id=1,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
        )
        assert response.status == "pending"
        assert response.is_correct is None
        assert response.parse_confidence == "unknown"

    def test_response_dataclass_defaults(self) -> None:
        """Test Response dataclass default values."""
        response = Response(
            run_id="test-run-001",
            snapshot_id=1,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
        )
        assert response.status == "pending"
        assert response.is_correct is None
        assert response.parse_confidence == "unknown"


class TestRunRepository:
    """Test cases for RunRepository CRUD operations."""

    def test_create_run(self, db_manager: DatabaseManager) -> None:
        """Test creating a new run."""
        repo = RunRepository(db_manager)
        run = Run(
            run_id="test-run-001",
            created_at=datetime.now(),
            config='{"models": ["gpt-4"]}',
            status="pending",
        )
        
        created = repo.create(run)
        
        assert created.run_id == "test-run-001"
        assert created.status == "pending"

    def test_get_run_by_id(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a run by ID."""
        repo = RunRepository(db_manager)
        run = Run(
            run_id="test-run-002",
            created_at=datetime.now(),
            config='{}',
            status="pending",
        )
        repo.create(run)
        
        retrieved = repo.get_by_id("test-run-002")
        
        assert retrieved is not None
        assert retrieved.run_id == "test-run-002"
        assert retrieved.status == "pending"

    def test_get_run_by_id_not_found(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a non-existent run."""
        repo = RunRepository(db_manager)
        retrieved = repo.get_by_id("non-existent-run")
        assert retrieved is None

    def test_get_all_runs(self, db_manager: DatabaseManager) -> None:
        """Test retrieving all runs."""
        repo = RunRepository(db_manager)
        run1 = Run(run_id="run-1", created_at=datetime.now())
        run2 = Run(run_id="run-2", created_at=datetime.now())
        run3 = Run(run_id="run-3", created_at=datetime.now())
        
        repo.create(run1)
        repo.create(run2)
        repo.create(run3)
        
        runs = repo.get_all()
        
        assert len(runs) == 3
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"run-1", "run-2", "run-3"}

    def test_update_run(self, db_manager: DatabaseManager) -> None:
        """Test updating a run."""
        repo = RunRepository(db_manager)
        run = Run(run_id="test-run-003", created_at=datetime.now(), status="pending")
        repo.create(run)
        
        run.status = "completed"
        updated = repo.update(run)
        
        assert updated is not None
        assert updated.status == "completed"
        
        retrieved = repo.get_by_id("test-run-003")
        assert retrieved is not None
        assert retrieved.status == "completed"

    def test_update_nonexistent_run(self, db_manager: DatabaseManager) -> None:
        """Test updating a non-existent run."""
        repo = RunRepository(db_manager)
        run = Run(run_id="non-existent", created_at=datetime.now(), status="completed")
        updated = repo.update(run)
        assert updated is None

    def test_delete_run(self, db_manager: DatabaseManager) -> None:
        """Test deleting a run."""
        repo = RunRepository(db_manager)
        run = Run(run_id="test-run-004", created_at=datetime.now())
        repo.create(run)
        
        deleted = repo.delete("test-run-004")
        assert deleted is True
        
        retrieved = repo.get_by_id("test-run-004")
        assert retrieved is None

    def test_delete_nonexistent_run(self, db_manager: DatabaseManager) -> None:
        """Test deleting a non-existent run."""
        repo = RunRepository(db_manager)
        deleted = repo.delete("non-existent")
        assert deleted is False


class TestModelRepository:
    """Test cases for ModelRepository CRUD operations."""

    def test_create_model(self, db_manager: DatabaseManager) -> None:
        """Test creating a new model."""
        repo = ModelRepository(db_manager)
        created = repo.create("gpt-4", "GPT-4", "OpenAI")
        
        assert created.model_id == "gpt-4"
        assert created.model_name == "GPT-4"
        assert created.provider == "OpenAI"

    def test_create_model_duplicate(self, db_manager: DatabaseManager) -> None:
        """Test creating a duplicate model."""
        repo = ModelRepository(db_manager)
        repo.create("gpt-4", "GPT-4", "OpenAI")
        
        with pytest.raises(sqlite3.IntegrityError):
            repo.create("gpt-4", "GPT-4", "OpenAI")

    def test_get_model_by_id(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a model by ID."""
        repo = ModelRepository(db_manager)
        repo.create("gpt-4", "GPT-4", "OpenAI")
        
        model = repo.get_by_id("gpt-4")
        
        assert model is not None
        assert model.model_name == "GPT-4"

    def test_get_model_by_id_not_found(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a non-existent model."""
        repo = ModelRepository(db_manager)
        model = repo.get_by_id("non-existent")
        assert model is None

    def test_get_all_models(self, db_manager: DatabaseManager) -> None:
        """Test retrieving all models."""
        repo = ModelRepository(db_manager)
        repo.create("gpt-4", "GPT-4", "OpenAI")
        repo.create("claude-3", "Claude 3", "Anthropic")
        repo.create("gemini-pro", "Gemini Pro", "Google")
        
        models = repo.get_all()
        
        assert len(models) == 3
        model_ids = {m.model_id for m in models}
        assert model_ids == {"gpt-4", "claude-3", "gemini-pro"}

    def test_update_model(self, db_manager: DatabaseManager) -> None:
        """Test updating a model."""
        repo = ModelRepository(db_manager)
        repo.create("gpt-4", "GPT-4", "OpenAI")
        
        updated = repo.update("gpt-4", "GPT-4 Turbo", "OpenAI")
        
        assert updated is not None
        assert updated.model_name == "GPT-4 Turbo"
        
        model = repo.get_by_id("gpt-4")
        assert model is not None
        assert model.model_name == "GPT-4 Turbo"

    def test_update_nonexistent_model(self, db_manager: DatabaseManager) -> None:
        """Test updating a non-existent model."""
        repo = ModelRepository(db_manager)
        updated = repo.update("non-existent", "Name", "Provider")
        assert updated is None

    def test_delete_model(self, db_manager: DatabaseManager) -> None:
        """Test deleting a model."""
        repo = ModelRepository(db_manager)
        repo.create("gpt-4", "GPT-4", "OpenAI")
        
        deleted = repo.delete("gpt-4")
        assert deleted is True
        
        model = repo.get_by_id("gpt-4")
        assert model is None

    def test_delete_nonexistent_model(self, db_manager: DatabaseManager) -> None:
        """Test deleting a non-existent model."""
        repo = ModelRepository(db_manager)
        deleted = repo.delete("non-existent")
        assert deleted is False


class TestResponseRepository:
    """Test cases for ResponseRepository CRUD operations."""

    def _setup_response_test_data(self, db_manager: DatabaseManager) -> tuple[RunRepository, ModelRepository, ResponseRepository]:
        """Set up required parent records for response tests."""
        run_repo = RunRepository(db_manager)
        model_repo = ModelRepository(db_manager)
        response_repo = ResponseRepository(db_manager)

        # Create run
        run = Run(run_id="test-run-001", created_at=datetime.now())
        run_repo.create(run)

        # Create model
        model_repo.create("gpt-4", "GPT-4", "OpenAI")

        return run_repo, model_repo, response_repo

    def test_create_response(self, db_manager: DatabaseManager) -> None:
        """Test creating a new response."""
        _, _, repo = self._setup_response_test_data(db_manager)
        response = Response(
            run_id="test-run-001",
            snapshot_id=None,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
            selected_answer="A",
            correct_answer="A",
            is_correct=True,
            response_text="Test response",
            input_tokens=10,
            response_tokens=5,
            latency_ms=100,
            status="success",
        )

        created = repo.create(response)

        assert created.response_id is not None
        assert created.question_id == "Q001"
        assert created.selected_answer == "A"

    def test_get_response_by_id(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a response by ID."""
        _, _, repo = self._setup_response_test_data(db_manager)
        response = Response(
            run_id="test-run-001",
            snapshot_id=None,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
        )
        created = repo.create(response)

        retrieved = repo.get_by_id(created.response_id)

        assert retrieved is not None
        assert retrieved.response_id == created.response_id

    def test_get_response_by_id_not_found(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a non-existent response."""
        repo = ResponseRepository(db_manager)
        retrieved = repo.get_by_id(99999)
        assert retrieved is None

    def test_get_responses_by_run(self, db_manager: DatabaseManager) -> None:
        """Test retrieving responses by run ID."""
        _, _, repo = self._setup_response_test_data(db_manager)

        response1 = Response(
            run_id="test-run-001",
            snapshot_id=None,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
        )
        response2 = Response(
            run_id="test-run-001",
            snapshot_id=None,
            question_id="Q002",
            model_id="gpt-4",
            iteration=1,
        )
        response3 = Response(
            run_id="test-run-001",
            snapshot_id=None,
            question_id="Q001",
            model_id="gpt-4",
            iteration=2,
        )

        repo.create(response1)
        repo.create(response2)
        repo.create(response3)

        responses = repo.get_by_run("test-run-001")

        assert len(responses) == 3

    def test_get_responses_by_run(self, db_manager: DatabaseManager) -> None:
        """Test retrieving responses by run ID."""
        run_repo = RunRepository(db_manager)
        model_repo = ModelRepository(db_manager)
        repo = ResponseRepository(db_manager)

        # Create run-1
        run1 = Run(run_id="run-1", created_at=datetime.now())
        run_repo.create(run1)
        model_repo.create("gpt-4", "GPT-4", "OpenAI")

        # Create run-2
        run2 = Run(run_id="run-2", created_at=datetime.now())
        run_repo.create(run2)

        response1 = Response(
            run_id="run-1",
            snapshot_id=None,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
        )
        response2 = Response(
            run_id="run-2",
            snapshot_id=None,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
        )

        repo.create(response1)
        repo.create(response2)

        responses = repo.get_by_run("run-1")

        assert len(responses) == 1
        assert responses[0].run_id == "run-1"

    def test_update_response(self, db_manager: DatabaseManager) -> None:
        """Test updating a response."""
        _, _, repo = self._setup_response_test_data(db_manager)
        response = Response(
            run_id="test-run-001",
            snapshot_id=None,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
            status="pending",
        )
        created = repo.create(response)

        created.status = "success"
        created.selected_answer = "A"
        updated = repo.update(created)

        assert updated is not None
        assert updated.status == "success"
        assert updated.selected_answer == "A"

    def test_update_nonexistent_response(self, db_manager: DatabaseManager) -> None:
        """Test updating a non-existent response."""
        repo = ResponseRepository(db_manager)
        response = Response(
            run_id="test-run-001",
            snapshot_id=None,
            question_id="Q001",
            model_id="gpt-4",
            iteration=1,
        )
        response.response_id = 99999
        updated = repo.update(response)
        assert updated is None

    def test_delete_response(self, db_manager: DatabaseManager) -> None:
        """Test deleting a response."""
        _, _, _, repo = self._setup_response_test_data(db_manager)
        response = Response(
            iteration_id=1,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test",
            options_json="{}",
        )
        created = repo.create(response)
        
        deleted = repo.delete(created.response_id)
        assert deleted is True
        
        retrieved = repo.get_by_id(created.response_id)
        assert retrieved is None

    def test_delete_nonexistent_response(self, db_manager: DatabaseManager) -> None:
        """Test deleting a non-existent response."""
        repo = ResponseRepository(db_manager)
        deleted = repo.delete(99999)
        assert deleted is False


class TestTransactionHandling:
    """Test cases for transaction handling."""

    def test_transaction_commit(self, temp_db_path: Path) -> None:
        """Test that transactions are properly committed."""
        manager = DatabaseManager(temp_db_path)
        manager.initialize()
        
        conn = manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO runs (run_id, created_at, config, status) VALUES (?, ?, ?, ?)",
                ("tx-test-001", datetime.now().isoformat(), "{}", "pending"),
            )
            conn.commit()
        finally:
            conn.close()
        
        # Verify data persists after commit
        conn2 = manager.get_connection()
        try:
            cursor = conn2.cursor()
            cursor.execute("SELECT run_id FROM runs WHERE run_id = ?", ("tx-test-001",))
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "tx-test-001"
        finally:
            conn2.close()
        
        manager.close()

    def test_transaction_rollback(self, temp_db_path: Path) -> None:
        """Test that transactions can be rolled back."""
        manager = DatabaseManager(temp_db_path)
        manager.initialize()
        
        conn = manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO runs (run_id, created_at, config, status) VALUES (?, ?, ?, ?)",
                ("tx-rollback-001", datetime.now().isoformat(), "{}", "pending"),
            )
            conn.rollback()
        finally:
            conn.close()
        
        # Verify data was rolled back
        conn2 = manager.get_connection()
        try:
            cursor = conn2.cursor()
            cursor.execute("SELECT run_id FROM runs WHERE run_id = ?", ("tx-rollback-001",))
            result = cursor.fetchone()
            assert result is None
        finally:
            conn2.close()
        
        manager.close()

    def test_repository_operations_use_transactions(self, db_manager: DatabaseManager) -> None:
        """Test that repository operations properly use transactions."""
        run_repo = RunRepository(db_manager)
        
        # Create a run
        run = Run(run_id="tx-repo-test", created_at=datetime.now())
        run_repo.create(run)
        
        # Verify it was committed
        retrieved = run_repo.get_by_id("tx-repo-test")
        assert retrieved is not None
        assert retrieved.run_id == "tx-repo-test"
