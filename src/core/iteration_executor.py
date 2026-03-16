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
from src.core.variant_config import VariantConfig
from src.db.models import RunModel
from src.db.repository import ModelVariantRepository, ResponseRepository, RunModelRepository
from src.db.schema import DatabaseManager
from src.utils.config import Settings
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
        db_manager: Optional[DatabaseManager],
        api_client: OpenRouterClient,
        randomizer: Optional[AnswerRandomizer],
        run_id: str,
        model_id: str,
        iteration_number: int,
        experiment_id: str,
        model_kwargs: Optional[dict[str, Any]] = None,
        use_structured_outputs: bool = False,
        reasoning_config: Optional[dict[str, Any]] = None,
        settings: Optional[Settings] = None,
        system_prompt_template: Optional[str] = None,
        user_prompt_template: Optional[str] = None,
    ) -> None:
        """Initialize the IterationExecutor.

        Args:
            db_manager: DatabaseManager instance for database connections.
                       Can be None for execution-only mode (no persistence).
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
            system_prompt_template: System prompt template from experiment (frozen).
            user_prompt_template: User prompt template from experiment (frozen).

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
        self._response_repository = ResponseRepository(db_manager) if db_manager else None
        self._model_kwargs = model_kwargs or {}
        self._use_structured_outputs = use_structured_outputs
        self._reasoning_config = reasoning_config
        self.settings = settings
        self._system_prompt_template = system_prompt_template
        self._user_prompt_template = user_prompt_template
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

        # Get variant_id for this model/configuration
        # If db_manager is None, build variant_id locally (no persistence check)
        if self.db_manager:
            variant_repository = RunModelRepository(self.db_manager)
        else:
            variant_repository = None

        # Build variant config from settings to get variant_id
        reasoning_mode = "unspecified"
        reasoning_effort = None
        reasoning_max_tokens = None

        if self.settings:
            if hasattr(self.settings, 'reasoning_mode') and self.settings.reasoning_mode:
                reasoning_mode = self.settings.reasoning_mode
                if reasoning_mode == "effort" and self.settings.reasoning_effort:
                    reasoning_effort = self.settings.reasoning_effort
                if reasoning_mode == "budget" and self.settings.reasoning_max_tokens is not None:
                    reasoning_max_tokens = self.settings.reasoning_max_tokens
            else:
                if self.settings.reasoning_enabled is False:
                    reasoning_mode = "off"
                elif self.settings.reasoning_effort:
                    reasoning_mode = "effort"
                    reasoning_effort = self.settings.reasoning_effort
                elif self.settings.reasoning_max_tokens is not None:
                    reasoning_mode = "budget"
                    reasoning_max_tokens = self.settings.reasoning_max_tokens
                elif self.settings.reasoning_enabled is True:
                    reasoning_mode = "auto"

        variant_config = VariantConfig(
            reasoning_mode=reasoning_mode,
            reasoning_effort=reasoning_effort,
            reasoning_max_tokens=reasoning_max_tokens,
            vision_enabled=self.settings.enable_vision if self.settings else False,
            structured_enabled=self.settings.enable_structured if self.settings else False,
        )
        variant_id = variant_config.build_variant_id(self.model_id)

        # Get pending questions (filter out already answered)
        # If db_manager is None, execute ALL questions (no skip)
        if self.db_manager and variant_repository:
            pending_questions = self.get_pending_questions(variant_id, questions, self.iteration_number)
        else:
            # Execution-only mode: execute all questions
            pending_questions = questions

        if not pending_questions:
            logger.info(
                f"Iteration {self.iteration_number} for model {self.model_id}: "
                f"All questions already answered, skipping execution"
            )
            return {
                "status": "completed",
                "total_questions": len(questions),
                "completed_questions": 0,
                "errors": 0,
                "duration_ms": 0,
                "iteration_number": self.iteration_number,
                "run_id": self.run_id,
                "model_id": self.model_id,
                "skipped": len(questions),
            }

        logger.info(
            f"Starting iteration {self.iteration_number} for model {self.model_id} "
            f"with {len(pending_questions)} pending questions "
            f"({len(questions) - len(pending_questions)} already answered)"
        )

        # Initialize progress tracker if not provided
        if self._progress_tracker is None:
            self._progress_tracker = ProgressTracker(
                total=len(pending_questions),
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

            for question in pending_questions:
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
            "pending_questions": len(pending_questions),
            "completed_questions": completed,
            "errors": errors,
            "duration_ms": duration_ms,
            "iteration_number": self.iteration_number,
            "run_id": self.run_id,
            "model_id": self.model_id,
            "skipped": len(questions) - len(pending_questions),
        }

        logger.info(
            f"Iteration {self.iteration_number} completed: "
            f"{completed}/{len(pending_questions)} pending questions, "
            f"{len(questions) - len(pending_questions)} skipped (already answered), "
            f"{errors} errors, {duration_ms}ms"
        )

        return results

    def get_pending_questions(self, variant_id: str, questions: list, iteration: int) -> list:
        """Get questions that this model variant hasn't answered yet in this run.

        Detection key: (question_id, iteration) - each question must be answered
        once per iteration.

        Args:
            variant_id: ID of the model variant.
            questions: List of all Question objects to potentially execute.
            iteration: Iteration number (1-based).

        Returns:
            List of Question objects that still need to be answered.
        """
        if not questions:
            return []

        # Build set of (question_id, iteration) pairs already answered
        answered_keys = self._get_answered_question_keys(variant_id, iteration)

        # Filter questions: keep only those NOT in answered_keys
        pending = [q for q in questions if (q.question_id, iteration) not in answered_keys]

        if len(pending) < len(questions):
            skipped = len(questions) - len(pending)
            logger.info(
                f"Variant {variant_id}: {skipped}/{len(questions)} questions "
                f"already answered in iteration {iteration}, executing {len(pending)} pending"
            )

        return pending

    def _get_answered_question_keys(self, variant_id: str, iteration: int) -> set:
        """Get set of (question_id, iteration) keys already answered by this variant.

        Args:
            variant_id: ID of the model variant.
            iteration: Iteration number to check.

        Returns:
            Set of (question_id, iteration) tuples already answered.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT question_id, iteration
                FROM responses
                WHERE variant_id = ? AND iteration = ?
                """,
                (variant_id, iteration),
            )
            return {(row["question_id"], row["iteration"]) for row in cursor.fetchall()}
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    async def _execute_question(self, question: Any) -> dict[str, Any]:
        """Execute a single question.

        Args:
            question: Question object to execute.

        Returns:
            Dictionary containing execution results.
        """
        # Create question executor
        from src.db.repository import QuestionSnapshotRepository

        # Generate variant_id from current configuration
        # If db_manager is None, create in-memory variant (no persistence)
        if self.db_manager:
            variant_repository = ModelVariantRepository(self.db_manager)
        else:
            variant_repository = None

        # Build variant config from settings
        reasoning_mode = "unspecified"
        reasoning_effort = None
        reasoning_max_tokens = None

        if self.settings:
            if self.settings.reasoning_enabled is False:
                reasoning_mode = "off"
            elif self.settings.reasoning_effort:
                reasoning_mode = "effort"
                reasoning_effort = self.settings.reasoning_effort
            elif self.settings.reasoning_max_tokens is not None:
                reasoning_mode = "budget"
                reasoning_max_tokens = self.settings.reasoning_max_tokens
            elif self.settings.reasoning_enabled is True:
                reasoning_mode = "auto"

        variant_config = VariantConfig(
            reasoning_mode=reasoning_mode,
            reasoning_effort=reasoning_effort,
            reasoning_max_tokens=reasoning_max_tokens,
            vision_enabled=self.settings.enable_vision if self.settings else False,
            structured_enabled=self.settings.enable_structured if self.settings else False,
        )

        variant_signature = variant_config.build_signature(self.model_id)
        variant_id = variant_config.build_variant_id(self.model_id)

        # Check if variant exists, if not create it (only if db_manager is available)
        existing_variant = None
        if variant_repository:
            existing_variant = variant_repository.get_by_id(variant_id)
            if not existing_variant:
                from src.db.models import ModelVariant
                variant = ModelVariant(
                    variant_id=variant_id,
                    model_id=self.model_id,
                    reasoning_mode=variant_config.reasoning_mode,
                    reasoning_effort=variant_config.reasoning_effort,
                    reasoning_max_tokens=variant_config.reasoning_max_tokens,
                    vision_enabled=variant_config.vision_enabled,
                    structured_enabled=variant_config.structured_enabled,
                    variant_signature=variant_signature,
                )
                try:
                    variant_repository.create(variant)
                    logger.info(
                        f"Registered model variant: {variant_id} | "
                        f"model={self.model_id} | signature={variant_signature}"
                    )
                except Exception:
                    # Variant might have been created concurrently
                    existing_variant = variant_repository.get_by_id(variant_id)

        # Create snapshot repository (only if db_manager is available)
        snapshot_repository = QuestionSnapshotRepository(self.db_manager) if self.db_manager else None
        
        question_executor = QuestionExecutor(
            db_manager=self.db_manager,
            api_client=self._api_client,
            randomizer=self._randomizer,
            run_id=self.run_id,
            variant_id=variant_id,
            model_id=self.model_id,
            iteration_number=self.iteration_number,
            experiment_id=self.experiment_id,
            model_kwargs=self._model_kwargs,
            use_structured_outputs=self._use_structured_outputs,
            reasoning_config=self._reasoning_config,
            enable_vision=self.settings.enable_vision if hasattr(self, 'settings') else False,
            settings=self.settings if hasattr(self, 'settings') else None,
            snapshot_repository=snapshot_repository,
            system_prompt_template=self._system_prompt_template,
            user_prompt_template=self._user_prompt_template,
            variant_repository=variant_repository,
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
