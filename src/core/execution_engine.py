"""Execution engine for benchmark_llm.

This module provides a unified, context-agnostic execution engine for running
benchmarks. It is responsible ONLY for execution, not for persistence or
context management.

Design Principles:
    - ExecutionEngine does NOT know about run_id, experiment_id, or database
    - ExecutionEngine does NOT persist results
    - ExecutionEngine ONLY executes and returns raw results
    - Persistence is the responsibility of the caller (BenchmarkRunner/RunManager)

Example:
    >>> engine = ExecutionEngine(api_client, randomizer, settings)
    >>> results = engine.execute(model_variants, questions, iterations)
    >>> # Caller is responsible for persisting results
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.core.iteration_executor import IterationExecutor
from src.core.randomizer import AnswerRandomizer
from src.db.models import ModelVariant, Question

logger = logging.getLogger(__name__)


@dataclass
class QuestionWithContext:
    """Question with optional context (snapshot_id).
    
    This wrapper separates execution (Question) from context (snapshot_id).
    
    - In direct flow (--models): snapshot_id = None (no persistence)
    - In hierarchical flow (--experiment --run): snapshot_id = from database
    
    Attributes:
        question: The question to execute.
        snapshot_id: Optional snapshot ID for persistence. None = execution-only mode.
    
    Example:
        >>> # Direct flow (no persistence)
        >>> q = QuestionWithContext(question=question, snapshot_id=None)
        
        >>> # Hierarchical flow (with persistence)
        >>> q = QuestionWithContext(question=question, snapshot_id=123)
    """
    question: Question
    snapshot_id: Optional[int] = None


@dataclass
class ExecutionResult:
    """Pure execution result (no context IDs).
    
    This dataclass contains only execution data, without any reference to
    run_id, experiment_id, or other context. Persistence is the caller's
    responsibility.
    
    Attributes:
        model_id: Base model identifier (e.g., "openai/gpt-4").
        variant_id: Model variant identifier (includes configuration).
        iteration: Iteration number (1-based).
        total_questions: Total number of questions in this iteration.
        completed: Number of successfully completed questions.
        errors: Number of errors encountered.
        duration_ms: Total iteration duration in milliseconds.
        responses: List of raw response data (to be persisted by caller).
    """
    model_id: str
    variant_id: str
    iteration: int
    total_questions: int
    completed: int = 0
    errors: int = 0
    duration_ms: float = 0.0
    responses: list[dict[str, Any]] = field(default_factory=list)


class ExecutionEngine:
    """Unified execution engine for benchmarks.
    
    This engine is completely agnostic of execution context. It does NOT know
    about:
    - run_id
    - experiment_id
    - CLI arguments
    - Database
    
    It ONLY executes benchmarks for given model variants and questions,
    returning raw results. Persistence is the caller's responsibility.
    
    Attributes:
        api_client: OpenRouter API client for model inference.
        randomizer: Answer randomizer for shuffling options.
        settings: Application settings.
    
    Example:
        >>> engine = ExecutionEngine(api_client, randomizer, settings)
        >>> results = engine.execute(variants, questions, iterations=3)
        >>> # Results are pure data - caller persists them
    """
    
    def __init__(
        self,
        api_client: Any,  # OpenRouterClient
        randomizer: AnswerRandomizer,
        settings: Any,  # Settings
        db_manager: Optional[Any] = None,  # Optional DatabaseManager for persistence
    ) -> None:
        """Initialize the execution engine.

        Args:
            api_client: OpenRouter API client for model inference.
            randomizer: Answer randomizer for shuffling options.
            settings: Application settings.
            db_manager: Optional DatabaseManager for persistence.
                       If None, execution-only mode (no persistence).
        """
        self.api_client = api_client
        self.randomizer = randomizer
        self.settings = settings
        self.db_manager = db_manager

        logger.debug("ExecutionEngine initialized")
    
    def execute(
        self,
        model_variants: list[ModelVariant],
        questions: list[QuestionWithContext],
        iterations: int,
        run_id: str = "",  # Optional run_id for persistence
        experiment_id: str = "",  # Optional experiment_id for persistence
    ) -> list[ExecutionResult]:
        """Execute benchmark for given models and questions.

        This method orchestrates the complete execution:
        1. For each model variant
        2. For each iteration
        3. Execute all questions
        4. Collect and return results

        Note: This method does NOT persist results. The caller is responsible
        for persisting results to the database.

        Args:
            model_variants: List of model variants to benchmark.
            questions: List of questions with optional context (snapshot_id).
                      snapshot_id=None means execution-only mode (no persistence).
            iterations: Number of iterations per model variant.
            run_id: Optional run_id for persistence. Empty = execution-only mode.
            experiment_id: Optional experiment_id for persistence. Empty = execution-only mode.
        
        Returns:
            List of ExecutionResult objects (pure data, no persistence).
        
        Example:
            >>> results = engine.execute(variants, questions, iterations=3)
            >>> for result in results:
            ...     print(f"{result.model_id}: {result.completed}/{result.total_questions}")
        """
        all_results = []

        logger.info(f"Starting execution: {len(model_variants)} model(s), "
                   f"{len(questions)} question(s), {iterations} iteration(s)")

        for variant in model_variants:
            logger.info(f"Executing model variant: {variant.variant_id}")

            for iteration_num in range(1, iterations + 1):
                logger.debug(f"  Iteration {iteration_num}/{iterations}")

                result = self._execute_single_iteration(
                    variant=variant,
                    questions=questions,
                    iteration_num=iteration_num,
                    run_id=run_id,
                    experiment_id=experiment_id,
                )

                all_results.append(result)

                logger.debug(f"    Completed: {result.completed}/{result.total_questions}, "
                           f"Errors: {result.errors}, Duration: {result.duration_ms:.0f}ms")

        logger.info(f"Execution completed: {len(all_results)} iteration(s)")
        return all_results
    
    def _execute_single_iteration(
        self,
        variant: ModelVariant,
        questions: list[QuestionWithContext],
        iteration_num: int,
        run_id: str = "",
        experiment_id: str = "",
    ) -> ExecutionResult:
        """Execute a single iteration for a model variant.

        Args:
            variant: Model variant to execute.
            questions: List of questions with optional context (snapshot_id).
            iteration_num: Iteration number (1-based).

        Returns:
            ExecutionResult for this iteration.
        """
        start_time = time.time()

        # Extract plain questions from wrappers for IterationExecutor
        plain_questions = [q.question for q in questions]

        # Create iteration executor for this variant
        # Pass snapshot_ids via model_kwargs for QuestionExecutor to use
        snapshot_ids = {q.question.question_id: q.snapshot_id for q in questions if q.snapshot_id}
        
        executor = IterationExecutor(
            db_manager=self.db_manager,  # Pass db_manager for persistence
            api_client=self.api_client,
            randomizer=self.randomizer,
            run_id=run_id,  # Pass real run_id for persistence
            model_id=variant.model_id,
            iteration_number=iteration_num,
            experiment_id=experiment_id,  # Pass real experiment_id for persistence
            model_kwargs={**self._extract_model_kwargs(), "_snapshot_ids": snapshot_ids},
            use_structured_outputs=self.settings.use_structured_outputs if self.settings else False,
            reasoning_config=self._build_reasoning_config(),
            settings=self.settings,
            system_prompt_template=self.settings.system_prompt if self.settings else None,
            user_prompt_template=self.settings.user_prompt_template if self.settings else None,
        )

        # Execute iteration (returns dict with results)
        iteration_result = executor.execute_iteration(plain_questions)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Build execution result (pure data, no context)
        result = ExecutionResult(
            model_id=variant.model_id,
            variant_id=variant.variant_id,
            iteration=iteration_num,
            total_questions=iteration_result.get("total_questions", len(questions)),
            completed=iteration_result.get("completed_questions", 0),
            errors=iteration_result.get("errors", 0),
            duration_ms=duration_ms,
            responses=iteration_result.get("responses", []),
        )
        
        return result
    
    def _extract_model_kwargs(self) -> dict[str, Any]:
        """Extract model generation parameters from settings.
        
        Returns:
            Dictionary of model kwargs (only non-None values).
        """
        if not self.settings:
            return {}
        
        kwargs = {}
        
        if hasattr(self.settings, 'model_max_tokens') and self.settings.model_max_tokens is not None:
            kwargs["max_tokens"] = self.settings.model_max_tokens
        
        if hasattr(self.settings, 'model_temperature') and self.settings.model_temperature is not None:
            kwargs["temperature"] = self.settings.model_temperature
        
        if hasattr(self.settings, 'model_top_p') and self.settings.model_top_p is not None:
            kwargs["top_p"] = self.settings.model_top_p
        
        if hasattr(self.settings, 'model_top_k') and self.settings.model_top_k is not None:
            kwargs["top_k"] = self.settings.model_top_k
        
        if hasattr(self.settings, 'model_repeat_penalty') and self.settings.model_repeat_penalty is not None:
            kwargs["repeat_penalty"] = self.settings.model_repeat_penalty
        
        return kwargs
    
    def _build_reasoning_config(self) -> dict[str, Any] | None:
        """Build reasoning configuration from settings.
        
        Returns:
            Reasoning config dict or None if not configured.
        """
        if not self.settings:
            return None
        
        reasoning_config = {}
        
        if hasattr(self.settings, 'reasoning_effort') and self.settings.reasoning_effort is not None:
            if self.settings.reasoning_effort == 'none':
                reasoning_config["enabled"] = False
            else:
                reasoning_config["effort"] = self.settings.reasoning_effort
        
        if hasattr(self.settings, 'reasoning_max_tokens') and self.settings.reasoning_max_tokens is not None:
            reasoning_config["max_tokens"] = self.settings.reasoning_max_tokens
        
        if hasattr(self.settings, 'reasoning_exclude') and self.settings.reasoning_exclude is not None:
            reasoning_config["exclude"] = self.settings.reasoning_exclude
        
        if hasattr(self.settings, 'reasoning_enabled') and self.settings.reasoning_enabled is not None:
            reasoning_config["enabled"] = self.settings.reasoning_enabled
        
        return reasoning_config if reasoning_config else None
