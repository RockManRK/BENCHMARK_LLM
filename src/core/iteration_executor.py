"""Iteration executor module for benchmark_llm project.

This module provides functionality to execute a single iteration
of benchmark testing for a specific model, coordinating question
execution and tracking progress.
"""

import logging
import time
from datetime import datetime
from typing import Any, Optional

from src.api.client import OpenRouterClient
from src.core.question_executor import QuestionExecutor
from src.core.randomizer import AnswerRandomizer
from src.db.models import Iteration
from src.db.repository import IterationRepository
from src.db.schema import DatabaseManager
from src.utils.progress import ProgressTracker

logger = logging.getLogger(__name__)


class IterationExecutor:
    """Executes a single iteration of benchmark testing.

    This class coordinates the execution of all questions for a single
    iteration of testing with a specific model. It manages:
    - Iteration lifecycle (start, complete, fail)
    - Question execution coordination
    - Progress tracking
    - Error handling and statistics

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        api_client: OpenRouterClient instance for API calls.
        randomizer: AnswerRandomizer instance for answer shuffling.
        run_id: ID of the current benchmark run.
        model_id: ID of the model being tested.
        iteration_number: Sequential iteration number.

    Example:
        >>> executor = IterationExecutor(
        ...     db_manager, api_client, randomizer,
        ...     run_id="run-123", model_id="gpt-4", iteration_number=1
        ... )
        >>> results = executor.execute_iteration(questions)
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        api_client: OpenRouterClient,
        randomizer: AnswerRandomizer,
        run_id: str,
        model_id: str,
        iteration_number: int,
        model_kwargs: Optional[dict[str, Any]] = None,
        use_structured_outputs: bool = False,
        reasoning_config: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize the IterationExecutor.

        Args:
            db_manager: DatabaseManager instance for database connections.
            api_client: OpenRouterClient instance for API calls.
            randomizer: AnswerRandomizer instance for answer shuffling.
            run_id: ID of the current benchmark run.
            model_id: ID of the model being tested.
            iteration_number: Sequential iteration number (1-based).
            model_kwargs: Optional dict with model generation parameters.
            use_structured_outputs: Whether to use structured outputs (JSON schema)
                for model responses. Falls back to traditional method if not supported.
            reasoning_config: Optional reasoning configuration (OpenRouter standard).

        Example:
            >>> executor = IterationExecutor(
            ...     db_manager, api_client, randomizer,
            ...     run_id="run-123", model_id="gpt-4", iteration_number=1,
            ...     model_kwargs={"max_tokens": 16384},
            ...     use_structured_outputs=True,
            ...     reasoning_config={"effort": "high"}
            ... )
        """
        self.db_manager = db_manager
        self._api_client = api_client
        self._randomizer = randomizer
        self.run_id = run_id
        self.model_id = model_id
        self.iteration_number = iteration_number
        self._iteration_repository = IterationRepository(db_manager)
        self._model_kwargs = model_kwargs or {}
        self._use_structured_outputs = use_structured_outputs
        self._reasoning_config = reasoning_config
        self._current_iteration: Optional[Iteration] = None
        self._progress_tracker: Optional[ProgressTracker] = None

        logger.info(
            f"IterationExecutor initialized for run={run_id}, "
            f"model={model_id}, iteration={iteration_number}, "
            f"reasoning_config={self._reasoning_config}"
        )

    def execute_iteration(
        self, questions: list[Any], progress_tracker: Optional[ProgressTracker] = None
    ) -> dict[str, Any]:
        """Execute a single iteration for all questions.

        This method coordinates the execution of all questions in the
        iteration, tracking progress and handling errors.

        Args:
            questions: List of Question objects to execute.
            progress_tracker: Optional ProgressTracker for progress updates.

        Returns:
            Dictionary containing iteration results:
            - status: "completed" or "failed"
            - total_questions: Total number of questions
            - completed_questions: Number successfully completed
            - errors: Number of errors encountered
            - duration_ms: Total iteration duration in milliseconds
            - iteration_id: Database ID of the iteration

        Example:
            >>> results = executor.execute_iteration(questions)
            >>> print(f"Completed {results['completed_questions']}/{results['total_questions']}")
        """
        start_time = time.time()
        self._progress_tracker = progress_tracker

        logger.info(
            f"Starting iteration {self.iteration_number} for model {self.model_id} "
            f"with {len(questions)} questions"
        )

        # Create iteration record in database
        self._current_iteration = self._create_iteration_record()
        iteration_id = self._current_iteration.iteration_id

        if iteration_id is None:
            logger.error("Failed to create iteration record")
            return {
                "status": "failed",
                "total_questions": len(questions),
                "completed_questions": 0,
                "errors": 1,
                "duration_ms": 0,
                "iteration_id": None,
                "error_message": "Failed to create iteration record",
            }

        # Initialize progress tracker if not provided
        if self._progress_tracker is None:
            self._progress_tracker = ProgressTracker(
                total=len(questions),
                run_id=self.run_id,
                model_id=self.model_id,
                iteration_number=self.iteration_number,
                description="Questions",
            )
            self._progress_tracker.start()

        # Execute questions
        completed = 0
        errors = 0

        # Create a single event loop for all questions to avoid httpx connection close issues
        import asyncio

        async def execute_all_questions():
            """Execute all questions in a single event loop."""
            nonlocal completed, errors
            
            for question in questions:
                try:
                    # Execute question in the current running loop
                    result = await self._execute_question(question, iteration_id)

                    if result.get("status") == "success":
                        completed += 1
                    else:
                        errors += 1
                        logger.warning(
                            f"Question {question.question_id} failed: "
                            f"{result.get('error_message', 'Unknown error')}"
                        )

                except Exception as e:
                    errors += 1
                    logger.exception(
                        f"Unexpected error executing question {question.question_id}: {e}"
                    )

                # Update progress
                if self._progress_tracker:
                    self._progress_tracker.update(1)

        # Run all questions in a single event loop
        asyncio.run(execute_all_questions())

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Update iteration status
        status = "completed" if errors == 0 or completed > 0 else "failed"
        self._complete_iteration(status)

        # Compile results
        results = {
            "status": status,
            "total_questions": len(questions),
            "completed_questions": completed,
            "errors": errors,
            "duration_ms": duration_ms,
            "iteration_id": iteration_id,
            "run_id": self.run_id,
            "model_id": self.model_id,
            "iteration_number": self.iteration_number,
        }

        logger.info(
            f"Iteration {self.iteration_number} completed: "
            f"{completed}/{len(questions)} questions, "
            f"{errors} errors, {duration_ms}ms"
        )

        return results

    def _create_iteration_record(self) -> Iteration:
        """Create an iteration record in the database.

        Returns:
            The created Iteration object with database-generated ID.

        Raises:
            Exception: If database operation fails.
        """
        iteration = Iteration(
            run_id=self.run_id,
            model_id=self.model_id,
            iteration_number=self.iteration_number,
            started_at=datetime.now(),
            status="running",
        )

        self._iteration_repository.create(iteration)

        logger.debug(
            f"Created iteration record: run={self.run_id}, "
            f"model={self.model_id}, iteration={self.iteration_number}"
        )

        return iteration

    async def _execute_question(
        self, question: Any, iteration_id: int
    ) -> dict[str, Any]:
        """Execute a single question.

        Args:
            question: Question object to execute.
            iteration_id: Database ID of the current iteration.

        Returns:
            Dictionary containing execution results.
        """
        # Create question executor
        question_executor = QuestionExecutor(
            db_manager=self.db_manager,
            api_client=self._api_client,
            randomizer=self._randomizer,
            run_id=self.run_id,
            model_id=self.model_id,
            iteration_id=iteration_id,
            model_kwargs=self._model_kwargs,
            use_structured_outputs=self._use_structured_outputs,
            reasoning_config=self._reasoning_config,
            enable_vision=self.settings.enable_vision if hasattr(self, 'settings') else False,
        )

        # Execute question and await result
        result = await question_executor.execute_question(question)

        return result

    def _complete_iteration(self, status: str) -> None:
        """Mark the iteration as complete.

        Args:
            status: Final status ("completed" or "failed").
        """
        if self._current_iteration is None:
            return

        self._current_iteration.status = status
        self._current_iteration.completed_at = datetime.now()

        # Update in database
        self._iteration_repository.update(self._current_iteration)

        logger.info(
            f"Iteration {self.iteration_number} marked as {status} "
            f"for model {self.model_id}"
        )

    def get_iteration_id(self) -> Optional[int]:
        """Get the current iteration ID.

        Returns:
            The iteration ID if an iteration has been created, None otherwise.

        Example:
            >>> executor.execute_iteration(questions)
            >>> iteration_id = executor.get_iteration_id()
        """
        if self._current_iteration:
            return self._current_iteration.iteration_id
        return None

    def get_progress_tracker(self) -> Optional[ProgressTracker]:
        """Get the progress tracker for this iteration.

        Returns:
            The ProgressTracker instance if one exists, None otherwise.
        """
        return self._progress_tracker
