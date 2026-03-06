"""Repository module for database CRUD operations.

This module provides repository classes for each entity in the database,
encapsulating all data access logic and providing a clean API for
database operations.
"""

import sqlite3
from datetime import datetime
from typing import Optional

from src.db.models import Error, Iteration, Model, Response, Run
from src.db.schema import DatabaseManager


class RunRepository:
    """Repository for Run entity CRUD operations.

    This class provides methods to create, read, update, and delete
    benchmark run records in the database.

    Attributes:
        db_manager: DatabaseManager instance for database connections.

    Example:
        >>> repo = RunRepository(db_manager)
        >>> run = Run(run_id="run-001", created_at=datetime.now())
        >>> created = repo.create(run)
        >>> retrieved = repo.get_by_id("run-001")
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the RunRepository.

        Args:
            db_manager: DatabaseManager instance for database connections.
        """
        self.db_manager = db_manager

    def create(self, run: Run) -> Run:
        """Create a new run record.

        Args:
            run: Run object to create.

        Returns:
            The created Run object with any database-generated values.

        Raises:
            sqlite3.Error: If there's an error inserting the record.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO runs (run_id, created_at, config, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.created_at.isoformat(),
                    run.config,
                    run.status,
                ),
            )
            conn.commit()
            return run
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, run_id: str) -> Optional[Run]:
        """Retrieve a run by its ID.

        Args:
            run_id: The unique identifier of the run.

        Returns:
            Run object if found, None otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT run_id, created_at, config, status FROM runs WHERE run_id = ?",
                (run_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Run(
                run_id=row["run_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                config=row["config"],
                status=row["status"],
            )
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_all(self) -> list[Run]:
        """Retrieve all runs.

        Returns:
            List of all Run objects in the database.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT run_id, created_at, config, status FROM runs ORDER BY created_at DESC")
            runs = []
            for row in cursor.fetchall():
                runs.append(
                    Run(
                        run_id=row["run_id"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        config=row["config"],
                        status=row["status"],
                    )
                )
            return runs
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def update(self, run: Run) -> Optional[Run]:
        """Update an existing run record.

        Args:
            run: Run object with updated values.

        Returns:
            The updated Run object if successful, None if run not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE runs
                SET created_at = ?, config = ?, status = ?
                WHERE run_id = ?
                """,
                (
                    run.created_at.isoformat(),
                    run.config,
                    run.status,
                    run.run_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return run
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, run_id: str) -> bool:
        """Delete a run record.

        Args:
            run_id: The unique identifier of the run to delete.

        Returns:
            True if deleted successfully, False if run not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()


class ModelRepository:
    """Repository for Model entity CRUD operations.

    This class provides methods to create, read, update, and delete
    model records in the database.

    Example:
        >>> repo = ModelRepository(db_manager)
        >>> model = repo.create("gpt-4", "GPT-4", "OpenAI")
        >>> retrieved = repo.get_by_id("gpt-4")
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ModelRepository.

        Args:
            db_manager: DatabaseManager instance for database connections.
        """
        self.db_manager = db_manager

    def create(
        self,
        model_id: str,
        model_name: str,
        provider: str,
        metadata: Optional[dict] = None,
        context_length: Optional[int] = None,
        max_completion_tokens: Optional[int] = None,
    ) -> Model:
        """Create a new model record.

        Args:
            model_id: Unique identifier for the model.
            model_name: Human-readable name of the model.
            provider: Name of the model provider.
            metadata: Optional dict with model metadata (n_params, size, etc.).
            context_length: Optional context window size in tokens.
            max_completion_tokens: Optional max completion tokens.

        Returns:
            The created Model object.

        Raises:
            sqlite3.IntegrityError: If a model with the same ID already exists.
        """
        import json

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO models (model_id, model_name, provider, metadata, context_length, max_completion_tokens)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    model_id,
                    model_name,
                    provider,
                    json.dumps(metadata or {}),
                    context_length,
                    max_completion_tokens,
                ),
            )
            conn.commit()
            return Model(
                model_id=model_id,
                model_name=model_name,
                provider=provider,
                metadata=json.dumps(metadata or {}),
                context_length=context_length,
                max_completion_tokens=max_completion_tokens,
            )
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, model_id: str) -> Optional[Model]:
        """Retrieve a model by its ID.

        Args:
            model_id: The unique identifier of the model.

        Returns:
            Model object if found, None otherwise.
        """
        import json

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT model_id, model_name, provider, metadata, context_length, max_completion_tokens
                FROM models WHERE model_id = ?
                """,
                (model_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Model(
                model_id=row["model_id"],
                model_name=row["model_name"],
                provider=row["provider"],
                metadata=row["metadata"] or "{}",
                context_length=row["context_length"],
                max_completion_tokens=row["max_completion_tokens"],
            )
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_all(self) -> list[Model]:
        """Retrieve all models.

        Returns:
            List of all Model objects in the database.
        """
        import json

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT model_id, model_name, provider, metadata, context_length, max_completion_tokens
                FROM models ORDER BY model_name
                """
            )
            models = []
            for row in cursor.fetchall():
                models.append(
                    Model(
                        model_id=row["model_id"],
                        model_name=row["model_name"],
                        provider=row["provider"],
                        metadata=row["metadata"] or "{}",
                        context_length=row["context_length"],
                        max_completion_tokens=row["max_completion_tokens"],
                    )
                )
            return models
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def update(
        self,
        model_id: str,
        model_name: str,
        provider: str,
        metadata: Optional[dict] = None,
        context_length: Optional[int] = None,
        max_completion_tokens: Optional[int] = None,
    ) -> Optional[Model]:
        """Update an existing model record.

        Args:
            model_id: The unique identifier of the model.
            model_name: Updated human-readable name.
            provider: Updated provider name.
            metadata: Updated metadata dict.
            context_length: Updated context window size.
            max_completion_tokens: Updated max completion tokens.

        Returns:
            The updated Model object if successful, None if model not found.
        """
        import json

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE models
                SET model_name = ?, provider = ?, metadata = ?, context_length = ?, max_completion_tokens = ?
                WHERE model_id = ?
                """,
                (
                    model_name,
                    provider,
                    json.dumps(metadata or {}),
                    context_length,
                    max_completion_tokens,
                    model_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return Model(
                model_id=model_id,
                model_name=model_name,
                provider=provider,
                metadata=json.dumps(metadata or {}),
                context_length=context_length,
                max_completion_tokens=max_completion_tokens,
            )
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, model_id: str) -> bool:
        """Delete a model record.

        Args:
            model_id: The unique identifier of the model to delete.

        Returns:
            True if deleted successfully, False if model not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM models WHERE model_id = ?", (model_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()


class ResponseRepository:
    """Repository for Response entity CRUD operations.

    This class provides methods to create, read, update, and delete
    response records in the database.

    Example:
        >>> repo = ResponseRepository(db_manager)
        >>> response = Response(iteration_id=1, question_id="Q001", ...)
        >>> created = repo.create(response)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ResponseRepository.

        Args:
            db_manager: DatabaseManager instance for database connections.
        """
        self.db_manager = db_manager

    def create(self, response: Response) -> Response:
        """Create a new response record.

        Args:
            response: Response object to create.

        Returns:
            The created Response object with database-generated response_id.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO responses (
                    iteration_id, question_id, model_id, run_id,
                    question_text, options_json, options_randomized,
                    selected_answer, correct_answer, is_correct,
                    response_text, input_tokens, output_tokens,
                    latency_ms, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.iteration_id,
                    response.question_id,
                    response.model_id,
                    response.run_id,
                    response.question_text,
                    response.options_json,
                    response.options_randomized,
                    response.selected_answer,
                    response.correct_answer,
                    response.is_correct,
                    response.response_text,
                    response.input_tokens,
                    response.output_tokens,
                    response.latency_ms,
                    response.status,
                ),
            )
            conn.commit()
            response.response_id = cursor.lastrowid
            return response
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, response_id: int) -> Optional[Response]:
        """Retrieve a response by its ID.

        Args:
            response_id: The unique identifier of the response.

        Returns:
            Response object if found, None otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, iteration_id, question_id, model_id, run_id,
                       question_text, options_json, options_randomized,
                       selected_answer, correct_answer, is_correct,
                       response_text, input_tokens, output_tokens,
                       latency_ms, timestamp, status
                FROM responses WHERE response_id = ?
                """,
                (response_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Response(
                response_id=row["response_id"],
                iteration_id=row["iteration_id"],
                question_id=row["question_id"],
                model_id=row["model_id"],
                run_id=row["run_id"],
                question_text=row["question_text"],
                options_json=row["options_json"],
                options_randomized=bool(row["options_randomized"]),
                selected_answer=row["selected_answer"],
                correct_answer=row["correct_answer"],
                is_correct=row["is_correct"],
                response_text=row["response_text"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                latency_ms=row["latency_ms"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                status=row["status"],
            )
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_iteration(self, iteration_id: int) -> list[Response]:
        """Retrieve all responses for an iteration.

        Args:
            iteration_id: The iteration ID to filter by.

        Returns:
            List of Response objects for the specified iteration.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, iteration_id, question_id, model_id, run_id,
                       question_text, options_json, options_randomized,
                       selected_answer, correct_answer, is_correct,
                       response_text, input_tokens, output_tokens,
                       latency_ms, timestamp, status
                FROM responses WHERE iteration_id = ? ORDER BY question_id
                """,
                (iteration_id,),
            )
            responses = []
            for row in cursor.fetchall():
                responses.append(
                    Response(
                        response_id=row["response_id"],
                        iteration_id=row["iteration_id"],
                        question_id=row["question_id"],
                        model_id=row["model_id"],
                        run_id=row["run_id"],
                        question_text=row["question_text"],
                        options_json=row["options_json"],
                        options_randomized=bool(row["options_randomized"]),
                        selected_answer=row["selected_answer"],
                        correct_answer=row["correct_answer"],
                        is_correct=row["is_correct"],
                        response_text=row["response_text"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        latency_ms=row["latency_ms"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        status=row["status"],
                    )
                )
            return responses
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_run(self, run_id: str) -> list[Response]:
        """Retrieve all responses for a run.

        Args:
            run_id: The run ID to filter by.

        Returns:
            List of Response objects for the specified run.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, iteration_id, question_id, model_id, run_id,
                       question_text, options_json, options_randomized,
                       selected_answer, correct_answer, is_correct,
                       response_text, input_tokens, output_tokens,
                       latency_ms, timestamp, status
                FROM responses WHERE run_id = ? ORDER BY iteration_id, question_id
                """,
                (run_id,),
            )
            responses = []
            for row in cursor.fetchall():
                responses.append(
                    Response(
                        response_id=row["response_id"],
                        iteration_id=row["iteration_id"],
                        question_id=row["question_id"],
                        model_id=row["model_id"],
                        run_id=row["run_id"],
                        question_text=row["question_text"],
                        options_json=row["options_json"],
                        options_randomized=bool(row["options_randomized"]),
                        selected_answer=row["selected_answer"],
                        correct_answer=row["correct_answer"],
                        is_correct=row["is_correct"],
                        response_text=row["response_text"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        latency_ms=row["latency_ms"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        status=row["status"],
                    )
                )
            return responses
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def update(self, response: Response) -> Optional[Response]:
        """Update an existing response record.

        Args:
            response: Response object with updated values.

        Returns:
            The updated Response object if successful, None if not found.
        """
        if response.response_id is None:
            return None

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE responses SET
                    iteration_id = ?, question_id = ?, model_id = ?, run_id = ?,
                    question_text = ?, options_json = ?, options_randomized = ?,
                    selected_answer = ?, correct_answer = ?, is_correct = ?,
                    response_text = ?, input_tokens = ?, output_tokens = ?,
                    latency_ms = ?, status = ?
                WHERE response_id = ?
                """,
                (
                    response.iteration_id,
                    response.question_id,
                    response.model_id,
                    response.run_id,
                    response.question_text,
                    response.options_json,
                    response.options_randomized,
                    response.selected_answer,
                    response.correct_answer,
                    response.is_correct,
                    response.response_text,
                    response.input_tokens,
                    response.output_tokens,
                    response.latency_ms,
                    response.status,
                    response.response_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return response
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, response_id: int) -> bool:
        """Delete a response record.

        Args:
            response_id: The unique identifier of the response to delete.

        Returns:
            True if deleted successfully, False if not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM responses WHERE response_id = ?", (response_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()


class ErrorRepository:
    """Repository for Error entity CRUD operations.

    This class provides methods to create, read, update, and delete
    error records in the database.

    Example:
        >>> repo = ErrorRepository(db_manager)
        >>> error = Error(response_id=1, error_type="APIError", error_message="...")
        >>> created = repo.create(error)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ErrorRepository.

        Args:
            db_manager: DatabaseManager instance for database connections.
        """
        self.db_manager = db_manager

    def create(self, error: Error) -> Error:
        """Create a new error record.

        Args:
            error: Error object to create.

        Returns:
            The created Error object with database-generated error_id.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO errors (response_id, error_type, error_message, stack_trace)
                VALUES (?, ?, ?, ?)
                """,
                (error.response_id, error.error_type, error.error_message, error.stack_trace),
            )
            conn.commit()
            error.error_id = cursor.lastrowid
            return error
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, error_id: int) -> Optional[Error]:
        """Retrieve an error by its ID.

        Args:
            error_id: The unique identifier of the error.

        Returns:
            Error object if found, None otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT error_id, response_id, error_type, error_message, stack_trace, timestamp
                FROM errors WHERE error_id = ?
                """,
                (error_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Error(
                error_id=row["error_id"],
                response_id=row["response_id"],
                error_type=row["error_type"],
                error_message=row["error_message"],
                stack_trace=row["stack_trace"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_response(self, response_id: int) -> list[Error]:
        """Retrieve all errors for a response.

        Args:
            response_id: The response ID to filter by.

        Returns:
            List of Error objects for the specified response.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT error_id, response_id, error_type, error_message, stack_trace, timestamp
                FROM errors WHERE response_id = ? ORDER BY timestamp
                """,
                (response_id,),
            )
            errors = []
            for row in cursor.fetchall():
                errors.append(
                    Error(
                        error_id=row["error_id"],
                        response_id=row["response_id"],
                        error_type=row["error_type"],
                        error_message=row["error_message"],
                        stack_trace=row["stack_trace"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            return errors
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, error_id: int) -> bool:
        """Delete an error record.

        Args:
            error_id: The unique identifier of the error to delete.

        Returns:
            True if deleted successfully, False if not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM errors WHERE error_id = ?", (error_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()


class IterationRepository:
    """Repository for Iteration entity CRUD operations.

    This class provides methods to create, read, update, and delete
    iteration records in the database.

    Example:
        >>> repo = IterationRepository(db_manager)
        >>> iteration = Iteration(run_id="run-001", model_id="gpt-4", iteration_number=1)
        >>> created = repo.create(iteration)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the IterationRepository.

        Args:
            db_manager: DatabaseManager instance for database connections.
        """
        self.db_manager = db_manager

    def create(self, iteration: Iteration) -> Iteration:
        """Create a new iteration record.

        Args:
            iteration: Iteration object to create.

        Returns:
            The created Iteration object with database-generated iteration_id.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO iterations (run_id, model_id, iteration_number, started_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    iteration.run_id,
                    iteration.model_id,
                    iteration.iteration_number,
                    iteration.started_at.isoformat(),
                    iteration.status,
                ),
            )
            conn.commit()
            iteration.iteration_id = cursor.lastrowid
            return iteration
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close connection for in-memory databases
            if str(self.db_manager.database_path) != ":memory:":
                conn.close()

    def get_by_id(self, iteration_id: int) -> Optional[Iteration]:
        """Retrieve an iteration by its ID.

        Args:
            iteration_id: The unique identifier of the iteration.

        Returns:
            Iteration object if found, None otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT iteration_id, run_id, model_id, iteration_number,
                       started_at, completed_at, status
                FROM iterations WHERE iteration_id = ?
                """,
                (iteration_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Iteration(
                iteration_id=row["iteration_id"],
                run_id=row["run_id"],
                model_id=row["model_id"],
                iteration_number=row["iteration_number"],
                started_at=datetime.fromisoformat(row["started_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                status=row["status"],
            )
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_run(self, run_id: str) -> list[Iteration]:
        """Retrieve all iterations for a run.

        Args:
            run_id: The run ID to filter by.

        Returns:
            List of Iteration objects for the specified run.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT iteration_id, run_id, model_id, iteration_number,
                       started_at, completed_at, status
                FROM iterations WHERE run_id = ? ORDER BY iteration_number
                """,
                (run_id,),
            )
            iterations = []
            for row in cursor.fetchall():
                iterations.append(
                    Iteration(
                        iteration_id=row["iteration_id"],
                        run_id=row["run_id"],
                        model_id=row["model_id"],
                        iteration_number=row["iteration_number"],
                        started_at=datetime.fromisoformat(row["started_at"]),
                        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                        status=row["status"],
                    )
                )
            return iterations
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_model(self, model_id: str) -> list[Iteration]:
        """Retrieve all iterations for a model.

        Args:
            model_id: The model ID to filter by.

        Returns:
            List of Iteration objects for the specified model.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT iteration_id, run_id, model_id, iteration_number,
                       started_at, completed_at, status
                FROM iterations WHERE model_id = ? ORDER BY run_id, iteration_number
                """,
                (model_id,),
            )
            iterations = []
            for row in cursor.fetchall():
                iterations.append(
                    Iteration(
                        iteration_id=row["iteration_id"],
                        run_id=row["run_id"],
                        model_id=row["model_id"],
                        iteration_number=row["iteration_number"],
                        started_at=datetime.fromisoformat(row["started_at"]),
                        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                        status=row["status"],
                    )
                )
            return iterations
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def update(self, iteration: Iteration) -> Optional[Iteration]:
        """Update an existing iteration record.

        Args:
            iteration: Iteration object with updated values.

        Returns:
            The updated Iteration object if successful, None if not found.
        """
        if iteration.iteration_id is None:
            return None

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE iterations SET
                    run_id = ?, model_id = ?, iteration_number = ?,
                    started_at = ?, completed_at = ?, status = ?
                WHERE iteration_id = ?
                """,
                (
                    iteration.run_id,
                    iteration.model_id,
                    iteration.iteration_number,
                    iteration.started_at.isoformat(),
                    iteration.completed_at.isoformat() if iteration.completed_at else None,
                    iteration.status,
                    iteration.iteration_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return iteration
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, iteration_id: int) -> bool:
        """Delete an iteration record.

        Args:
            iteration_id: The unique identifier of the iteration to delete.

        Returns:
            True if deleted successfully, False if not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM iterations WHERE iteration_id = ?", (iteration_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            # Don't close for in-memory databases
            if self.db_manager.should_close_connection():
                conn.close()
