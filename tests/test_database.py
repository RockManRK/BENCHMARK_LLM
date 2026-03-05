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

from src.db.models import Error, Iteration, Response, Run
from src.db.repository import (
    ErrorRepository,
    IterationRepository,
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
        assert "iterations" in schema
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
            "iterations",
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

    def test_iterations_table_schema(self, db_connection: sqlite3.Connection) -> None:
        """Test that iterations table has correct schema."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(iterations)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert "iteration_id" in columns
        assert "run_id" in columns
        assert "model_id" in columns
        assert "iteration_number" in columns
        assert "started_at" in columns
        assert "completed_at" in columns
        assert "status" in columns

    def test_responses_table_schema(self, db_connection: sqlite3.Connection) -> None:
        """Test that responses table has correct schema."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(responses)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert "response_id" in columns
        assert "iteration_id" in columns
        assert "question_id" in columns
        assert "model_id" in columns
        assert "run_id" in columns
        assert "question_text" in columns
        assert "options_json" in columns
        assert "options_randomized" in columns
        assert "selected_answer" in columns
        assert "correct_answer" in columns
        assert "is_correct" in columns
        assert "response_text" in columns
        assert "input_tokens" in columns
        assert "output_tokens" in columns
        assert "latency_ms" in columns
        assert "timestamp" in columns
        assert "status" in columns

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
            status="running",
        )
        assert run.run_id == "test-run-001"
        assert run.status == "running"

    def test_run_dataclass_defaults(self) -> None:
        """Test Run dataclass default values."""
        run = Run(run_id="test-run-002")
        assert run.status == "pending"
        assert run.config == "{}"

    def test_response_dataclass_creation(self) -> None:
        """Test creating a Response dataclass instance."""
        response = Response(
            response_id=1,
            iteration_id=1,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="What is the capital of France?",
            options_json='{"A": "Paris", "B": "London", "C": "Berlin", "D": "Madrid"}',
            options_randomized=False,
            selected_answer="A",
            correct_answer="A",
            is_correct=True,
            response_text="The capital of France is Paris.",
            input_tokens=50,
            output_tokens=20,
            latency_ms=1500,
            timestamp=datetime.now(),
            status="success",
        )
        assert response.question_id == "Q001"
        assert response.selected_answer == "A"
        assert response.is_correct is True

    def test_response_dataclass_defaults(self) -> None:
        """Test Response dataclass default values."""
        response = Response(
            iteration_id=1,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test question",
            options_json="{}",
        )
        assert response.options_randomized is False
        assert response.status == "pending"

    def test_error_dataclass_creation(self) -> None:
        """Test creating an Error dataclass instance."""
        error = Error(
            error_id=1,
            response_id=1,
            error_type="APIError",
            error_message="Rate limit exceeded",
            stack_trace="Traceback...",
            timestamp=datetime.now(),
        )
        assert error.error_type == "APIError"
        assert error.error_message == "Rate limit exceeded"

    def test_error_dataclass_defaults(self) -> None:
        """Test Error dataclass default values."""
        error = Error(response_id=1, error_type="Unknown", error_message="An error occurred")
        assert error.stack_trace == ""

    def test_iteration_dataclass_creation(self) -> None:
        """Test creating an Iteration dataclass instance."""
        iteration = Iteration(
            iteration_id=1,
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            status="completed",
        )
        assert iteration.iteration_number == 1
        assert iteration.status == "completed"

    def test_iteration_dataclass_defaults(self) -> None:
        """Test Iteration dataclass default values."""
        iteration = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
        )
        assert iteration.status == "running"


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
            status="running",
        )
        repo.create(run)
        
        retrieved = repo.get_by_id("test-run-002")
        
        assert retrieved is not None
        assert retrieved.run_id == "test-run-002"
        assert retrieved.status == "running"

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

    def _setup_response_test_data(self, db_manager: DatabaseManager) -> tuple[RunRepository, ModelRepository, IterationRepository, ResponseRepository]:
        """Set up required parent records for response tests."""
        run_repo = RunRepository(db_manager)
        model_repo = ModelRepository(db_manager)
        iteration_repo = IterationRepository(db_manager)
        response_repo = ResponseRepository(db_manager)
        
        # Create run
        run = Run(run_id="test-run-001", created_at=datetime.now())
        run_repo.create(run)
        
        # Create model
        model_repo.create("gpt-4", "GPT-4", "OpenAI")
        
        # Create iteration
        iteration = Iteration(run_id="test-run-001", model_id="gpt-4", iteration_number=1, started_at=datetime.now())
        iteration_repo.create(iteration)
        
        return run_repo, model_repo, iteration_repo, response_repo

    def test_create_response(self, db_manager: DatabaseManager) -> None:
        """Test creating a new response."""
        _, _, _, repo = self._setup_response_test_data(db_manager)
        response = Response(
            iteration_id=1,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test question",
            options_json="{}",
            selected_answer="A",
            correct_answer="A",
            is_correct=True,
            response_text="Test response",
            input_tokens=10,
            output_tokens=5,
            latency_ms=100,
            status="success",
        )
        
        created = repo.create(response)
        
        assert created.response_id is not None
        assert created.question_id == "Q001"
        assert created.selected_answer == "A"

    def test_get_response_by_id(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a response by ID."""
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
        
        retrieved = repo.get_by_id(created.response_id)
        
        assert retrieved is not None
        assert retrieved.response_id == created.response_id

    def test_get_response_by_id_not_found(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a non-existent response."""
        repo = ResponseRepository(db_manager)
        retrieved = repo.get_by_id(99999)
        assert retrieved is None

    def test_get_responses_by_iteration(self, db_manager: DatabaseManager) -> None:
        """Test retrieving responses by iteration ID."""
        _, _, _, repo = self._setup_response_test_data(db_manager)
        
        response1 = Response(
            iteration_id=1,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test 1",
            options_json="{}",
        )
        response2 = Response(
            iteration_id=1,
            question_id="Q002",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test 2",
            options_json="{}",
        )
        response3 = Response(
            iteration_id=2,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test 1",
            options_json="{}",
        )
        
        repo.create(response1)
        repo.create(response2)
        
        # Create second iteration for response3
        iteration_repo = IterationRepository(db_manager)
        iteration2 = Iteration(run_id="test-run-001", model_id="gpt-4", iteration_number=2, started_at=datetime.now())
        iteration_repo.create(iteration2)
        response3.iteration_id = iteration2.iteration_id
        repo.create(response3)
        
        responses = repo.get_by_iteration(1)
        
        assert len(responses) == 2
        question_ids = {r.question_id for r in responses}
        assert question_ids == {"Q001", "Q002"}

    def test_get_responses_by_run(self, db_manager: DatabaseManager) -> None:
        """Test retrieving responses by run ID."""
        run_repo = RunRepository(db_manager)
        model_repo = ModelRepository(db_manager)
        iteration_repo = IterationRepository(db_manager)
        repo = ResponseRepository(db_manager)
        
        # Create run-1
        run1 = Run(run_id="run-1", created_at=datetime.now())
        run_repo.create(run1)
        model_repo.create("gpt-4", "GPT-4", "OpenAI")
        iter1 = Iteration(run_id="run-1", model_id="gpt-4", iteration_number=1, started_at=datetime.now())
        iteration_repo.create(iter1)
        
        # Create run-2
        run2 = Run(run_id="run-2", created_at=datetime.now())
        run_repo.create(run2)
        iter2 = Iteration(run_id="run-2", model_id="gpt-4", iteration_number=1, started_at=datetime.now())
        iteration_repo.create(iter2)
        
        response1 = Response(
            iteration_id=iter1.iteration_id,
            question_id="Q001",
            model_id="gpt-4",
            run_id="run-1",
            question_text="Test",
            options_json="{}",
        )
        response2 = Response(
            iteration_id=iter2.iteration_id,
            question_id="Q001",
            model_id="gpt-4",
            run_id="run-2",
            question_text="Test",
            options_json="{}",
        )
        
        repo.create(response1)
        repo.create(response2)
        
        responses = repo.get_by_run("run-1")
        
        assert len(responses) == 1
        assert responses[0].run_id == "run-1"

    def test_update_response(self, db_manager: DatabaseManager) -> None:
        """Test updating a response."""
        _, _, _, repo = self._setup_response_test_data(db_manager)
        response = Response(
            iteration_id=1,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test",
            options_json="{}",
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
            iteration_id=1,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test",
            options_json="{}",
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


class TestErrorRepository:
    """Test cases for ErrorRepository CRUD operations."""

    def _setup_error_test_data(self, db_manager: DatabaseManager) -> tuple[RunRepository, ModelRepository, IterationRepository, ResponseRepository, ErrorRepository]:
        """Set up required parent records for error tests."""
        run_repo = RunRepository(db_manager)
        model_repo = ModelRepository(db_manager)
        iteration_repo = IterationRepository(db_manager)
        response_repo = ResponseRepository(db_manager)
        error_repo = ErrorRepository(db_manager)
        
        # Create run
        run = Run(run_id="test-run-001", created_at=datetime.now())
        run_repo.create(run)
        
        # Create model
        model_repo.create("gpt-4", "GPT-4", "OpenAI")
        
        # Create iteration
        iteration = Iteration(run_id="test-run-001", model_id="gpt-4", iteration_number=1, started_at=datetime.now())
        iteration_repo.create(iteration)
        
        # Create response
        response = Response(
            iteration_id=iteration.iteration_id,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test",
            options_json="{}",
        )
        created_response = response_repo.create(response)
        
        return run_repo, model_repo, iteration_repo, response_repo, error_repo, created_response.response_id

    def test_create_error(self, db_manager: DatabaseManager) -> None:
        """Test creating a new error."""
        *_, error_repo, response_id = self._setup_error_test_data(db_manager)
        error = Error(
            response_id=response_id,
            error_type="APIError",
            error_message="Rate limit exceeded",
            stack_trace="Traceback...",
        )
        
        created = error_repo.create(error)
        
        assert created.error_id is not None
        assert created.error_type == "APIError"

    def test_get_error_by_id(self, db_manager: DatabaseManager) -> None:
        """Test retrieving an error by ID."""
        *_, error_repo, response_id = self._setup_error_test_data(db_manager)
        error = Error(
            response_id=response_id,
            error_type="APIError",
            error_message="Test error",
        )
        created = error_repo.create(error)
        
        retrieved = error_repo.get_by_id(created.error_id)
        
        assert retrieved is not None
        assert retrieved.error_id == created.error_id

    def test_get_error_by_id_not_found(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a non-existent error."""
        repo = ErrorRepository(db_manager)
        retrieved = repo.get_by_id(99999)
        assert retrieved is None

    def test_get_errors_by_response(self, db_manager: DatabaseManager) -> None:
        """Test retrieving errors by response ID."""
        *_, error_repo, response_id = self._setup_error_test_data(db_manager)
        
        # Create additional responses for testing
        response_repo = ResponseRepository(db_manager)
        iteration_repo = IterationRepository(db_manager)
        
        # Create second iteration and response
        iteration2 = Iteration(run_id="test-run-001", model_id="gpt-4", iteration_number=2, started_at=datetime.now())
        iteration_repo.create(iteration2)
        response2 = Response(
            iteration_id=iteration2.iteration_id,
            question_id="Q001",
            model_id="gpt-4",
            run_id="test-run-001",
            question_text="Test",
            options_json="{}",
        )
        created_response2 = response_repo.create(response2)
        
        error1 = Error(response_id=response_id, error_type="APIError", error_message="Error 1")
        error2 = Error(response_id=response_id, error_type="TimeoutError", error_message="Error 2")
        error3 = Error(response_id=created_response2.response_id, error_type="APIError", error_message="Error 3")
        
        error_repo.create(error1)
        error_repo.create(error2)
        error_repo.create(error3)
        
        errors = error_repo.get_by_response(response_id)
        
        assert len(errors) == 2
        error_types = {e.error_type for e in errors}
        assert error_types == {"APIError", "TimeoutError"}

    def test_delete_error(self, db_manager: DatabaseManager) -> None:
        """Test deleting an error."""
        *_, error_repo, response_id = self._setup_error_test_data(db_manager)
        error = Error(response_id=response_id, error_type="APIError", error_message="Test")
        created = error_repo.create(error)
        
        deleted = error_repo.delete(created.error_id)
        assert deleted is True
        
        retrieved = error_repo.get_by_id(created.error_id)
        assert retrieved is None

    def test_delete_nonexistent_error(self, db_manager: DatabaseManager) -> None:
        """Test deleting a non-existent error."""
        repo = ErrorRepository(db_manager)
        deleted = repo.delete(99999)
        assert deleted is False


class TestIterationRepository:
    """Test cases for IterationRepository CRUD operations."""

    def _setup_iteration_test_data(self, db_manager: DatabaseManager) -> tuple[RunRepository, ModelRepository, IterationRepository]:
        """Set up required parent records for iteration tests."""
        run_repo = RunRepository(db_manager)
        model_repo = ModelRepository(db_manager)
        iteration_repo = IterationRepository(db_manager)
        
        # Create run
        run = Run(run_id="test-run-001", created_at=datetime.now())
        run_repo.create(run)
        
        # Create model
        model_repo.create("gpt-4", "GPT-4", "OpenAI")
        
        return run_repo, model_repo, iteration_repo

    def test_create_iteration(self, db_manager: DatabaseManager) -> None:
        """Test creating a new iteration."""
        _, _, repo = self._setup_iteration_test_data(db_manager)
        iteration = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
        )
        
        created = repo.create(iteration)
        
        assert created.iteration_id is not None
        assert created.iteration_number == 1
        assert created.status == "running"

    def test_get_iteration_by_id(self, db_manager: DatabaseManager) -> None:
        """Test retrieving an iteration by ID."""
        _, _, repo = self._setup_iteration_test_data(db_manager)
        iteration = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
        )
        created = repo.create(iteration)
        
        retrieved = repo.get_by_id(created.iteration_id)
        
        assert retrieved is not None
        assert retrieved.iteration_id == created.iteration_id

    def test_get_iteration_by_id_not_found(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a non-existent iteration."""
        repo = IterationRepository(db_manager)
        retrieved = repo.get_by_id(99999)
        assert retrieved is None

    def test_get_iterations_by_run(self, db_manager: DatabaseManager) -> None:
        """Test retrieving iterations by run ID."""
        _, _, repo = self._setup_iteration_test_data(db_manager)
        
        iter1 = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
        )
        iter2 = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=2,
            started_at=datetime.now(),
        )
        
        # Create second run for iter3
        run_repo = RunRepository(db_manager)
        run2 = Run(run_id="test-run-002", created_at=datetime.now())
        run_repo.create(run2)
        
        iter3 = Iteration(
            run_id="test-run-002",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
        )
        
        created1 = repo.create(iter1)
        created2 = repo.create(iter2)
        repo.create(iter3)
        
        iterations = repo.get_by_run("test-run-001")
        
        assert len(iterations) == 2
        iteration_ids = {i.iteration_id for i in iterations}
        assert iteration_ids == {created1.iteration_id, created2.iteration_id}

    def test_get_iterations_by_model(self, db_manager: DatabaseManager) -> None:
        """Test retrieving iterations by model ID."""
        run_repo, model_repo, repo = self._setup_iteration_test_data(db_manager)
        
        # Create second model
        model_repo.create("claude-3", "Claude 3", "Anthropic")
        
        iter1 = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
        )
        iter2 = Iteration(
            run_id="test-run-001",
            model_id="claude-3",
            iteration_number=1,
            started_at=datetime.now(),
        )
        
        repo.create(iter1)
        repo.create(iter2)
        
        iterations = repo.get_by_model("gpt-4")
        
        assert len(iterations) == 1
        assert iterations[0].model_id == "gpt-4"

    def test_update_iteration(self, db_manager: DatabaseManager) -> None:
        """Test updating an iteration."""
        _, _, repo = self._setup_iteration_test_data(db_manager)
        iteration = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
            status="running",
        )
        created = repo.create(iteration)
        
        created.status = "completed"
        created.completed_at = datetime.now()
        updated = repo.update(created)
        
        assert updated is not None
        assert updated.status == "completed"
        assert updated.completed_at is not None

    def test_update_nonexistent_iteration(self, db_manager: DatabaseManager) -> None:
        """Test updating a non-existent iteration."""
        repo = IterationRepository(db_manager)
        iteration = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
        )
        iteration.iteration_id = 99999
        updated = repo.update(iteration)
        assert updated is None

    def test_delete_iteration(self, db_manager: DatabaseManager) -> None:
        """Test deleting an iteration."""
        _, _, repo = self._setup_iteration_test_data(db_manager)
        iteration = Iteration(
            run_id="test-run-001",
            model_id="gpt-4",
            iteration_number=1,
            started_at=datetime.now(),
        )
        created = repo.create(iteration)
        
        deleted = repo.delete(created.iteration_id)
        assert deleted is True
        
        retrieved = repo.get_by_id(created.iteration_id)
        assert retrieved is None

    def test_delete_nonexistent_iteration(self, db_manager: DatabaseManager) -> None:
        """Test deleting a non-existent iteration."""
        repo = IterationRepository(db_manager)
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
