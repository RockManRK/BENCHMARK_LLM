"""Iteration executor module for benchmark_llm project.

This module provides functionality to execute a single iteration
of benchmark testing for a specific model, coordinating question
execution and tracking progress.

Note: Iterations are no longer stored as separate entities. The iteration
number is stored directly in the responses table.
"""

import logging
import time
from datetime import datetime
from typing import Any, Optional

from src.api.client import OpenRouterClient
from src.core.question_executor import QuestionExecutor
from src.core.randomizer import AnswerRandomizer
from src.db.repository import ResponseRepository
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
        randomizer: Optional[AnswerRandomizer],
        run_id: str,
        model_id: str,
        iteration_number: int,
        experiment_id: str,
        model_kwargs: Optional[dict[str, Any]] = None,
        use_structured_outputs: bool = False,
        reasoning_config: Optional[dict[str, Any]] = None,
        settings: Optional[Any] = None,
    ) -> None:
        """Initialize the IterationExecutor.

        Args:
            db_manager: DatabaseManager instance for database connections.
            api_client: OpenRouterClient instance for API calls.
            randomizer: AnswerRandomizer instance for answer shuffling, or None to disable randomization.
            run_id: ID of the current benchmark run.
            model_id: ID of the model being tested.
            iteration_number: Sequential iteration number (1-based).
            experiment_id: ID of the experiment (ALWAYS required, never None).
            model_kwargs: Optional dict with model generation parameters.
            use_structured_outputs: Whether to use structured outputs (JSON schema)
                for model responses. Falls back to traditional method if not supported.
            reasoning_config: Optional reasoning configuration (OpenRouter standard).

        Example:
            >>> executor = IterationExecutor(
            ...     db_manager, api_client, randomizer,
            ...     run_id="run-123", model_id="gpt-4", iteration_number=1,
            ...     experiment_id="exp-001",
            ...     model_kwargs={"max_tokens": 16384},
            ...     use_structured_outputs=True,
            ...     reasoning_config={"effort": "high"}
            ... )
        """
        self.db_manager = db_manager
        self._api_client = api_client
        self._randomizer = randomizer  # Can be None (no randomization)
        self.run_id = run_id
        self.model_id = model_id
        self.iteration_number = iteration_number
        self.experiment_id = experiment_id
        self._response_repository = ResponseRepository(db_manager)
        self._model_kwargs = model_kwargs or {}
        self._use_structured_outputs = use_structured_outputs
        self._reasoning_config = reasoning_config
        self.settings = settings
        self._progress_tracker: Optional[ProgressTracker] = None

        logger.info(
            f"IterationExecutor initialized for run={run_id}, "
            f"model={model_id}, iteration={iteration_number}, "
            f"experiment_id={experiment_id}, "
            f"reasoning_config={self._reasoning_config}"
        )

    def execute_iteration(
        self, questions: list[Any], progress_tracker: Optional[ProgressTracker] = None
    ) -> dict[str, Any]:
        """Execute a single iteration for all questions.

        This method coordinates the execution of all questions in the
        iteration, tracking progress and handling errors.

        Note: Iterations are no longer stored as separate entities.
        The iteration number is stored directly in responses.

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
            - iteration_number: Iteration number (not an ID)

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
                    result = await self._execute_question(question)

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

        # Compile results
        results = {
            "status": "completed" if errors == 0 or completed > 0 else "failed",
            "total_questions": len(questions),
            "completed_questions": completed,
            "errors": errors,
            "duration_ms": duration_ms,
            "iteration_number": self.iteration_number,
            "run_id": self.run_id,
            "model_id": self.model_id,
        }

        logger.info(
            f"Iteration {self.iteration_number} completed: "
            f"{completed}/{len(questions)} questions, "
            f"{errors} errors, {duration_ms}ms"
        )

        return results

    async def _execute_question(self, question: Any) -> dict[str, Any]:
        """Execute a single question.

        Args:
            question: Question object to execute.

        Returns:
            Dictionary containing execution results.
        """
        # Create question executor
        from src.db.repository import QuestionSnapshotRepository

        snapshot_repository = QuestionSnapshotRepository(self.db_manager)
        question_executor = QuestionExecutor(
            db_manager=self.db_manager,
            api_client=self._api_client,
            randomizer=self._randomizer,
            run_id=self.run_id,
            model_id=self.model_id,
            iteration_number=self.iteration_number,
            experiment_id=self.experiment_id,
            model_kwargs=self._model_kwargs,
            use_structured_outputs=self._use_structured_outputs,
            reasoning_config=self._reasoning_config,
            enable_vision=self.settings.enable_vision if hasattr(self, 'settings') else False,
            settings=self.settings if hasattr(self, 'settings') else None,
            snapshot_repository=snapshot_repository,
        )

        # Execute question and await result
        result = await question_executor.execute_question(question)

        return result

    def get_progress_tracker(self) -> Optional[ProgressTracker]:
        """Get the progress tracker for this iteration.

        Returns:
            The ProgressTracker instance if one exists, None otherwise.
        """
        return self._progress_tracker
