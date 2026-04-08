"""AsyncOrchestrator module for TO-BE architecture.

This module provides the synchronous entry point that bridges to async
internally. It owns the entire async lifecycle — one event loop, one
httpx client, one queue, one writer, one engine execution.

Key Principles:
- Single asyncio.run() call — nowhere else in the system
- httpx.AsyncClient lifecycle managed inside async context, NOT in __init__
- Writer drains all queued items before orchestration returns
- Exception-safe: client always closed, writer always shut down

Example:
    >>> from src.core.async_orchestrator import AsyncOrchestrator
    >>> from src.core.randomizer import AnswerRandomizer
    >>> from src.core.answer_parser import AnswerParser
    >>>
    >>> orchestrator = AsyncOrchestrator(
    ...     api_client=client,
    ...     db_connection=conn,
    ...     randomizer=AnswerRandomizer(),
    ...     parser=AnswerParser(),
    ... )
    >>> results = orchestrator.execute(plan)
"""

import asyncio
from logging import Logger
from typing import TYPE_CHECKING, Optional

from src.api.client import OpenRouterClient
from src.core.execution_engine import ExecutionEngine, ExecutionResult
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser
from src.core.execution_plan import ExecutionPlan
from src.core.run_finalizer import RunFinalizer
from src.utils.logging_config import get_logger

if TYPE_CHECKING:
    from src.core.async_writer import AsyncWriter


class AsyncOrchestrator:
    """Synchronous entry point that bridges to async internally.

    This class owns the complete async lifecycle:
    1. Accepts a pre-configured OpenRouterClient (with httpx.AsyncClient inside)
    2. Creates a shared asyncio.Queue for engine → writer communication
    3. Starts AsyncWriter as a background task
    4. Runs ExecutionEngine to process all items
    5. Sends sentinel to signal writer completion
    6. Awaits writer task to drain all queued items
    7. Closes the httpx client via api_client.close()
    8. Returns all ExecutionResults

    The orchestrator ensures:
    - No event loop is created per item (fixes RuntimeError: Event loop is closed)
    - httpx.AsyncClient is reused across all items
    - Writer completes before results are returned
    - Resources are cleaned up even on failure

    Attributes:
        api_client: OpenRouter API client (owns httpx.AsyncClient)
        db_connection: SQLite database connection for writer
        randomizer: Answer option randomizer
        parser: Response parser
        logger: Optional logger instance

    Example:
        >>> orchestrator = AsyncOrchestrator(client, conn, randomizer, parser)
        >>> results = orchestrator.execute(plan)
    """

    def __init__(
        self,
        api_client: OpenRouterClient,
        db_connection,
        randomizer: AnswerRandomizer,
        parser: AnswerParser,
        logger: Optional[Logger] = None,
        max_concurrency: int = 1,
    ) -> None:
        """Initialize orchestrator with dependencies.

        Args:
            api_client: OpenRouter API client (owns httpx.AsyncClient)
            db_connection: SQLite database connection for AsyncWriter
            randomizer: Answer option randomizer (seeded)
            parser: Response parser with confidence levels
            logger: Optional logger instance. If not provided, uses
                    get_logger('core.async_orchestrator').
            max_concurrency: Maximum number of concurrent item executions.
                    Controls the asyncio.Semaphore limit. Defaults to 1.

        Note:
            The api_client is created by the caller (CLI or ConfigResolver)
            and passed in. The orchestrator manages its lifecycle (close)
            inside the async context, ensuring proper cleanup.
        """
        self.api_client = api_client
        self.db_connection = db_connection
        self.randomizer = randomizer
        self.parser = parser
        self._logger = logger or get_logger('core.async_orchestrator')
        self._max_concurrency = max_concurrency

    def execute(self, plan: ExecutionPlan) -> list[ExecutionResult]:
        """Execute all items in the plan.

        This is the ONLY public method. It bridges synchronous caller
        code to asynchronous internal execution via a single asyncio.run()
        call.

        Args:
            plan: Immutable execution plan from Planner

        Returns:
            List of ExecutionResult (one per item)

        Example:
            >>> results = orchestrator.execute(plan)
            >>> for result in results:
            ...     print(f"Item {result.item_id}: {result.status}")
        """
        return asyncio.run(self._execute_async(plan))

    async def _execute_async(self, plan: ExecutionPlan) -> list[ExecutionResult]:
        """Execute all items in the plan asynchronously.

        This method follows a strict lifecycle order:
        1. Use injected OpenRouterClient (httpx.AsyncClient already initialized)
        2. Create asyncio.Queue (shared between engine and writer)
        3. Create AsyncWriter(queue, db_connection)
        4. Start writer as asyncio.create_task(writer.consume())
        5. Create ExecutionEngine(api_client, randomizer, parser)
        6. Run await engine.execute_async(plan) — items guarded by semaphore
        7. Put sentinel (None) on queue
        8. Await writer task completion (all writes flushed)
        9. Call RunFinalizer.finalize_run() for each run
        10. Close httpx.AsyncClient via api_client.close()
        11. Return results

        Args:
            plan: Immutable execution plan from Planner

        Returns:
            List of ExecutionResult (one per item)
        """
        experiment_id = plan.experiment_id
        run_count = len(plan.runs)
        total_items = sum(len(run.items) for run in plan.runs)

        self._logger.info(
            f"ORCHESTRATOR_START | experiment={experiment_id} | runs={run_count} | total_items={total_items}"
        )

        queue: asyncio.Queue = asyncio.Queue()

        from src.core.async_writer import AsyncWriter

        writer = AsyncWriter(queue, self.db_connection, self._logger)
        writer_task = asyncio.create_task(writer.consume())

        try:
            engine = ExecutionEngine(
                api_client=self.api_client,
                randomizer=self.randomizer,
                parser=self.parser,
                logger=self._logger,
            )

            # Create semaphore inside async context (correct event loop binding)
            semaphore = asyncio.Semaphore(self._max_concurrency)

            # Execute items with semaphore-based concurrency
            results = await self._execute_plan_with_semaphore(engine, plan, queue, semaphore)

            # Signal writer completion and wait for all writes to flush
            await queue.put(None)
            await writer_task

            # Finalize each run via RunFinalizer (sole owner of runs.status/duration)
            for run in plan.runs:
                finalizer = RunFinalizer(self.db_connection, self._logger)
                finalizer.finalize_run(run.run_id)

            succeeded = sum(1 for r in results if r.status == 'success')
            failed = sum(1 for r in results if r.status == 'failure')

            self._logger.info(
                f"ORCHESTRATOR_COMPLETE | experiment={experiment_id} | total={total_items} | succeeded={succeeded} | failed={failed}"
            )

            return results

        except Exception:
            await queue.put(None)

            try:
                await writer_task
            except Exception:
                # Log but don't re-raise — original exception must propagate
                self._logger.exception("Writer task failed during cleanup")

            raise

        finally:
            await self.api_client.close()

    async def _execute_plan_with_semaphore(
        self,
        engine: ExecutionEngine,
        plan: ExecutionPlan,
        queue: asyncio.Queue,
        semaphore: asyncio.Semaphore,
    ) -> list[ExecutionResult]:
        """Execute all plan items with semaphore-based concurrency control.

        Wraps each item execution with async with semaphore to
        limit concurrent API calls to max_concurrency.

        Args:
            engine: ExecutionEngine instance to use for item execution
            plan: Execution plan containing runs and items
            queue: Shared result queue for writer communication
            semaphore: Asyncio semaphore for concurrency control (created in async context)

        Returns:
            List of ExecutionResult (one per item)
        """
        all_results: list[ExecutionResult] = []

        for run in plan.runs:
            run_results = await self._execute_run_with_semaphore(engine, run, queue, semaphore)
            all_results.extend(run_results)

        return all_results

    async def _execute_run_with_semaphore(
        self,
        engine: ExecutionEngine,
        run,
        queue: asyncio.Queue,
        semaphore: asyncio.Semaphore,
    ) -> list[ExecutionResult]:
        """Execute all items in a single run with semaphore concurrency control.

        Args:
            engine: ExecutionEngine instance
            run: PlanRun to execute
            queue: Shared result queue
            semaphore: Asyncio semaphore for concurrency control

        Returns:
            List of ExecutionResult for this run
        """
        from src.core.retry import RetryHandler

        results: list[ExecutionResult] = []
        total_items = len(run.items)
        completed = 0

        run_retry_handler = RetryHandler(
            policy=run.retry_policy,
            logger=self._logger,
        )

        milestone_interval = max(1, total_items // 4)

        tasks = []
        for i, item in enumerate(run.items):
            task = asyncio.create_task(
                self._execute_item_with_semaphore(
                    engine, item, run, run_retry_handler, queue, semaphore, i
                )
            )
            tasks.append(task)

        for task in tasks:
            result = await task
            results.append(result)
            completed += 1

            if completed % milestone_interval == 0 or completed == total_items:
                percent = int((completed / total_items) * 100)
                self._logger.info(
                    f"PROGRESS_MILESTONE | run={run.run_id} | completed={completed}/{total_items} | percent={percent}%"
                )

        return results

    async def _execute_item_with_semaphore(
        self,
        engine: ExecutionEngine,
        item,
        run,
        retry_handler: RetryHandler,
        queue: asyncio.Queue,
        semaphore: asyncio.Semaphore,
        item_index: int,
    ) -> ExecutionResult:
        """Execute a single item with semaphore concurrency control.

        Args:
            engine: ExecutionEngine instance
            item: PlanItem to execute
            run: Parent PlanRun
            retry_handler: RetryHandler for this run
            queue: Shared result queue
            semaphore: Asyncio semaphore for concurrency control
            item_index: Zero-based index of item within the run (for deterministic seeding)

        Returns:
            ExecutionResult for this item
        """
        async with semaphore:
            return await engine._execute_item_async(item, run, retry_handler, queue, item_index)

