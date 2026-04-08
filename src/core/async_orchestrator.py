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
    ) -> None:
        """Initialize orchestrator with dependencies.

        Args:
            api_client: OpenRouter API client (owns httpx.AsyncClient)
            db_connection: SQLite database connection for AsyncWriter
            randomizer: Answer option randomizer (seeded)
            parser: Response parser with confidence levels
            logger: Optional logger instance. If not provided, uses
                    get_logger('core.async_orchestrator').

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
        6. Run await engine.execute_async(plan)
        7. Put sentinel (None) on queue
        8. Await writer task completion
        9. Close httpx.AsyncClient via api_client.close()
        10. Return results

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

            results = await engine.execute_async(plan, result_queue=queue)

            await queue.put(None)
            await writer_task

            # Update run statuses in DB based on execution results
            self._update_run_statuses(results)

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

    def _update_run_statuses(self, results: list[ExecutionResult]) -> None:
        """Update run statuses and accumulate duration in DB based on execution results.

        Groups results by run_id and determines terminal status:
        - all success → 'completed'
        - all failure → 'failed'
        - mixed → 'partial_failed'

        Duration is accumulated from successful responses only (latency_ms).
        """
        from collections import defaultdict

        run_results: dict[str, list[ExecutionResult]] = defaultdict(list)
        for r in results:
            run_results[r.run_id].append(r)

        cursor = self.db_connection.cursor()
        for run_id, run_items in run_results.items():
            successes = sum(1 for r in run_items if r.status == 'success')
            failures = sum(1 for r in run_items if r.status == 'failure')

            if failures == 0:
                status = 'completed'
            elif successes == 0:
                status = 'failed'
            else:
                status = 'partial_failed'

            # Calculate total latency from successful responses only
            latency_ms = sum(
                r.latency_ms for r in run_items
                if r.status == 'success' and r.latency_ms is not None
            )

            # Update status AND accumulate duration
            if latency_ms > 0:
                cursor.execute(
                    "UPDATE runs SET status = ?, duration = duration + ? WHERE run_id = ?",
                    (status, latency_ms, run_id),
                )
            else:
                cursor.execute(
                    "UPDATE runs SET status = ? WHERE run_id = ?",
                    (status, run_id),
                )

        self.db_connection.commit()

        # Log duration updates for auditability
        for run_id, run_items in run_results.items():
            run_latency = sum(
                r.latency_ms for r in run_items
                if r.status == 'success' and r.latency_ms is not None
            )
            self._logger.info(
                f"RUN_UPDATE | run={run_id} | latency_added={run_latency}ms"
            )

        self._logger.info(
            f"RUN_STATUS_UPDATED | runs={len(run_results)} | "
            f"statuses={ {rid: 'completed' if all(r.status == 'success' for r in rs) else 'failed' if all(r.status == 'failure' for r in rs) else 'partial_failed' for rid, rs in run_results.items()} }"
        )
