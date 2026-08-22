"""Tests for AsyncOrchestrator lifecycle management.

These tests verify:
1. Single event loop creation via asyncio.run()
2. httpx client created and closed exactly once
3. Sentinel shutdown order (engine → sentinel → writer)
4. Exception propagation through orchestrator
5. Resource cleanup on failure paths

Usage:
    pytest tests/test_async_orchestrator.py -v
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from datetime import datetime

from src.core.async_orchestrator import AsyncOrchestrator
from src.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    ModelConfig,
    Prompts,
    RetryPolicy,
    QuestionPayload,
)
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser
from src.core.execution_engine import ExecutionResult
from src.api.client import OpenRouterClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(num_items: int = 2) -> ExecutionPlan:
    """Build a minimal ExecutionPlan with the given number of items."""
    variant = PlanVariant(
        variant_id="var-001",
        model_id="openai/gpt-4o-mini",
        model_config_effective=ModelConfig(temperature=0.7),
    )

    items = []
    for i in range(num_items):
        items.append(
            PlanItem(
                item_id=f"run-001::var-001::snap-{i:03d}::it-{i + 1}",
                run_id="run-001",
                variant_id="var-001",
                snapshot_id=f"snap-{i:03d}",
                question_id=f"q{i + 1}",
                question_payload=QuestionPayload(
                    stem=f"What is {i + 1}+1?",
                    options=["1", "2", "3", "4"],
                    answer_key="B",
                ),
            )
        )

    run = PlanRun(
        run_id="run-001",
        randomization_seed_effective=42,
        prompts_effective=Prompts(
            system=None,
            user="Answer: {question}",
        ),
        retry_policy=RetryPolicy(max_attempts=1),
        variants=[variant],
        items=items,
    )

    return ExecutionPlan(
        plan_id="plan-test",
        created_at=datetime.now(),
        experiment_id="exp-test",
        runs=[run],
    )


def _make_item_async_side_effect(
    canned_results: list[ExecutionResult] | None = None,
    results_by_item_id: dict[str, ExecutionResult] | None = None,
    raises: Exception | None = None,
):
    """Build an async side_effect for engine._execute_item_async matching
    its real contract (src/core/execution_engine.py) — puts the result on
    result_queue (if given) and returns it. Exactly one of
    canned_results/results_by_item_id/raises should be provided.

    Added 2026-08-22 (test-debt reconciliation, group B): the real
    scheduler (AsyncOrchestrator._execute_plan_with_semaphore ->
    _execute_run_with_semaphore -> _execute_item_with_semaphore) calls
    engine._execute_item_async per item, never engine.execute_async(plan)
    — these tests previously mocked the wrong method entirely (a stale
    fixture predating the semaphore-based scheduler), so the mocked
    return value was never consumed, and the real code crashed instead
    on `engine.randomizer` (not exposed by autospec, which only reflects
    class-level members, never instance attributes set in __init__).
    """
    call_index = {"i": 0}

    async def _side_effect(item, run, retry_handler, result_queue, item_index, run_option_map, operation_id=None):
        if raises is not None:
            raise raises
        if results_by_item_id is not None:
            result = results_by_item_id[item.item_id]
        else:
            result = canned_results[call_index["i"]]
            call_index["i"] += 1
        if result_queue is not None:
            await result_queue.put(result)
        return result

    return _side_effect


def _make_success_result(item_id: str) -> ExecutionResult:
    """Build a successful ExecutionResult."""
    return ExecutionResult(
        item_id=item_id,
        run_id="run-001",
        variant_id="var-001",
        snapshot_id="snap-000",
        question_id="q1",
        status="success",
        response_text="The answer is (B).",
        selected_answer="B",
        parse_confidence="clear",
        latency_ms=100,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
        reasoning_tokens=None,
        cost=0.0001,
        effective_tokens=60,
        raw_response=None,
        started_at=datetime.now(),
        finished_at=datetime.now(),
        finish_reason="stop",
        randomization_enabled=True,
        randomization_seed=42,
        options_presented=["1", "2", "3", "4"],
        correct_option_presented="B",
        option_letter_map={"A": "A", "B": "B", "C": "C", "D": "D"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAsyncOrchestratorLifecycle:
    """Test that orchestrator manages resources correctly."""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client with close method."""
        client = MagicMock(spec=OpenRouterClient)
        client.chat_completion = AsyncMock(return_value=MagicMock(
            content="The answer is (B).",
            model_id="openai/gpt-4o-mini",
            input_tokens=50,
            response_tokens=10,
            latency_ms=100,
        ))
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_db(self):
        """Create a mock database connection."""
        return MagicMock()

    @pytest.fixture
    def randomizer(self):
        """Create a seeded randomizer."""
        return AnswerRandomizer(seed=42)

    @pytest.fixture
    def parser(self):
        """Create an answer parser."""
        return AnswerParser()

    def test_execute_creates_single_event_loop(self, orchestrator):
        """Verify asyncio.run() is called exactly once.

        The orchestrator.execute() method is the ONLY entry point and
        uses asyncio.run() internally. We verify this by checking that
        execute() returns results without raising, meaning one event
        loop was created and completed.

        NOTE: This test is NOT async because orchestrator.execute() is
        synchronous and calls asyncio.run() internally. Running it inside
        a pytest.mark.asyncio test would raise:
        "asyncio.run() cannot be called from a running event loop"
        """
        plan = _make_plan(num_items=1)
        mock_results = [_make_success_result("run-001::var-001::snap-000::it-1")]

        with patch(
            'src.core.async_orchestrator.ExecutionEngine',
            autospec=True,
        ) as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.randomizer = orchestrator.randomizer
            mock_engine._execute_item_async = AsyncMock(
                side_effect=_make_item_async_side_effect(canned_results=mock_results)
            )

            results = orchestrator.execute(plan)

            assert len(results) == 1
            assert results[0].status == "success"
            # The real per-item method was called once inside the event loop
            mock_engine._execute_item_async.assert_awaited_once()

    def test_httpx_client_closed_once(self, orchestrator, mock_api_client):
        """Verify httpx client is closed after all items complete.

        The orchestrator must call api_client.close() exactly once
        in the finally block, regardless of success or failure.
        """
        plan = _make_plan(num_items=2)
        mock_results = [
            _make_success_result("run-001::var-001::snap-000::it-1"),
            _make_success_result("run-001::var-001::snap-001::it-2"),
        ]

        with patch(
            'src.core.async_orchestrator.ExecutionEngine',
            autospec=True,
        ) as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.randomizer = orchestrator.randomizer
            mock_engine._execute_item_async = AsyncMock(
                side_effect=_make_item_async_side_effect(
                    results_by_item_id={r.item_id: r for r in mock_results}
                )
            )

            results = orchestrator.execute(plan)

            # Verify close was called exactly once
            mock_api_client.close.assert_awaited_once()
            assert len(results) == 2

    def test_sentinel_shutdown_order(self, mock_api_client, mock_db, randomizer, parser):
        """Verify sentinel is put on queue after every item result, before
        writer shutdown.

        The lifecycle order is:
        1. Engine executes all items, each pushed onto the queue as it completes
        2. Sentinel (None) is put on queue after all items are scheduled
        3. Writer task is awaited (drains all items + sentinel)
        4. API client is closed

        Fixed 2026-08-22 (test-debt reconciliation, group B): now drives
        the real per-item path (engine._execute_item_async, which puts
        its own result on result_queue — see
        src/core/execution_engine.py) instead of a no-longer-called
        engine.execute_async(plan), so the sentinel-after-items ordering
        is proven against the real queue-population mechanism, not
        merely asserted about a queue nothing real ever populated.
        """
        plan = _make_plan(num_items=2)
        queue_items_captured = []

        mock_results = [
            _make_success_result("run-001::var-001::snap-000::it-1"),
            _make_success_result("run-001::var-001::snap-001::it-2"),
        ]

        # Patch queue.put to capture the sentinel order
        original_queue_class = asyncio.Queue

        class TrackedQueue(original_queue_class):
            async def put(self, item):
                queue_items_captured.append(item)
                return await super().put(item)

        with patch(
            'src.core.async_orchestrator.ExecutionEngine',
            autospec=True,
        ) as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.randomizer = randomizer
            mock_engine._execute_item_async = AsyncMock(
                side_effect=_make_item_async_side_effect(
                    results_by_item_id={r.item_id: r for r in mock_results}
                )
            )

            with patch('asyncio.Queue', TrackedQueue):
                orchestrator = AsyncOrchestrator(
                    api_client=mock_api_client,
                    db_connection=mock_db,
                    randomizer=randomizer,
                    parser=parser,
                )

                results = orchestrator.execute(plan)

        # Verify sentinel (None) appears after both item results
        sentinel_indices = [
            i for i, item in enumerate(queue_items_captured) if item is None
        ]
        item_indices = [
            i for i, item in enumerate(queue_items_captured) if item is not None
        ]
        assert len(sentinel_indices) >= 1, "Sentinel (None) was not put on queue"
        assert len(item_indices) == 2, "Both item results should have been queued"
        assert max(item_indices) < min(sentinel_indices), (
            "Sentinel must be queued after every item result"
        )

        # Verify API client was closed
        mock_api_client.close.assert_awaited_once()
        assert len(results) == 2

    def test_exception_propagates_through_orchestrator(
        self, orchestrator, mock_api_client
    ):
        """Verify engine exceptions propagate through orchestrator correctly.

        When the engine raises an exception, the orchestrator must:
        1. Still send the sentinel to the queue
        2. Still await the writer task
        3. Still close the API client
        4. Re-raise the original exception
        """
        plan = _make_plan(num_items=1)

        with patch(
            'src.core.async_orchestrator.ExecutionEngine',
            autospec=True,
        ) as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.randomizer = orchestrator.randomizer
            mock_engine._execute_item_async = AsyncMock(
                side_effect=_make_item_async_side_effect(
                    raises=RuntimeError("Simulated engine failure")
                )
            )

            with pytest.raises(RuntimeError, match="Simulated engine failure"):
                orchestrator.execute(plan)

            # API client must still be closed despite exception
            mock_api_client.close.assert_awaited_once()

    def test_exception_propagates_with_writer_task_failure(
        self, orchestrator, mock_api_client
    ):
        """Verify orchestrator handles writer task failure during exception path.

        If the writer task also raises during the exception cleanup path,
        the orchestrator must not let the writer exception mask the original
        engine exception.
        """
        plan = _make_plan(num_items=1)

        # Create an AsyncWriter stand-in that fails on consume.
        # Fixed 2026-08-22 (test-debt reconciliation, group C): this
        # stand-in no longer represented the minimal real AsyncWriter
        # interface the orchestrator actually depends on —
        # AsyncOrchestrator._execute_async reads writer.abort_event
        # unconditionally (as an argument to
        # _execute_plan_with_semaphore, well before any exception path)
        # and, since ADR-004/ASY-01, also calls writer.drain_abandoned()
        # in its except-Exception cleanup branch when the writer aborted.
        # A fake lacking abort_event crashed with AttributeError instead
        # of letting the intended ValueError propagate. Not a production
        # bug — production always constructs a real AsyncWriter, which
        # always has both.
        class FailingWriter:
            def __init__(self):
                self.abort_event = asyncio.Event()
                self.abort_info = None

            async def consume(self):
                raise RuntimeError("Writer failure during cleanup")

            def drain_abandoned(self):
                return 0

        with patch(
            'src.core.async_orchestrator.ExecutionEngine',
            autospec=True,
        ) as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.randomizer = orchestrator.randomizer
            mock_engine._execute_item_async = AsyncMock(
                side_effect=_make_item_async_side_effect(
                    raises=ValueError("Original engine error")
                )
            )

            # Patch AsyncWriter import inside _execute_async
            with patch(
                'src.core.async_writer.AsyncWriter',
                return_value=FailingWriter(),
            ):
                # The original engine error should propagate
                with pytest.raises(ValueError, match="Original engine error"):
                    orchestrator.execute(plan)

            mock_api_client.close.assert_awaited_once()

    def test_writer_task_awaited_after_engine_completes(
        self, mock_api_client, mock_db, randomizer, parser
    ):
        """Verify the writer task is awaited after engine finishes.

        The orchestrator must not return until the writer has drained
        all queued items. We verify this by tracking consume() completion.
        """
        plan = _make_plan(num_items=2)
        writer_consumed = asyncio.Event()

        mock_results = [
            _make_success_result("run-001::var-001::snap-000::it-1"),
            _make_success_result("run-001::var-001::snap-001::it-2"),
        ]

        async def slow_consume(self):
            # Original consume logic but signal when done
            while True:
                result = await self._queue.get()
                if result is None:
                    self._queue.task_done()
                    break
            writer_consumed.set()
            return {"written": 2, "skipped": 0, "errors": 0}

        with patch(
            'src.core.async_orchestrator.ExecutionEngine',
            autospec=True,
        ) as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.randomizer = randomizer
            mock_engine._execute_item_async = AsyncMock(
                side_effect=_make_item_async_side_effect(
                    results_by_item_id={r.item_id: r for r in mock_results}
                )
            )

            with patch(
                'src.core.async_writer.AsyncWriter.consume',
                slow_consume,
            ):
                orchestrator = AsyncOrchestrator(
                    api_client=mock_api_client,
                    db_connection=mock_db,
                    randomizer=randomizer,
                    parser=parser,
                )

                results = orchestrator.execute(plan)

                # Writer must have consumed before execute() returned
                assert writer_consumed.is_set()
                assert len(results) == 2

    def test_execute_with_empty_plan(self, orchestrator):
        """Verify orchestrator handles plan with zero items."""
        plan = ExecutionPlan(
            plan_id="plan-empty",
            created_at=datetime.now(),
            experiment_id="exp-test",
            runs=[],
        )

        with patch(
            'src.core.async_orchestrator.ExecutionEngine',
            autospec=True,
        ) as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.execute_async = AsyncMock(return_value=[])

            results = orchestrator.execute(plan)

            assert results == []
            # Close still called even with no items
            orchestrator.api_client.close.assert_awaited_once()

    def test_execute_with_multiple_runs(self, mock_api_client, mock_db, randomizer, parser):
        """Verify orchestrator handles plans with multiple runs."""
        variant = PlanVariant(
            variant_id="var-001",
            model_id="openai/gpt-4o-mini",
            model_config_effective=ModelConfig(temperature=0.7),
        )

        items_run1 = [
            PlanItem(
                item_id="run-001::var-001::snap-000::it-1",
                run_id="run-001",
                variant_id="var-001",
                snapshot_id="snap-000",
                question_id="q1",
                question_payload=QuestionPayload(
                    stem="Question 1",
                    options=["A", "B", "C", "D"],
                    answer_key="A",
                ),
            )
        ]

        items_run2 = [
            PlanItem(
                item_id="run-002::var-001::snap-001::it-1",
                run_id="run-002",
                variant_id="var-001",
                snapshot_id="snap-001",
                question_id="q2",
                question_payload=QuestionPayload(
                    stem="Question 2",
                    options=["A", "B", "C", "D"],
                    answer_key="B",
                ),
            )
        ]

        plan = ExecutionPlan(
            plan_id="plan-multi-run",
            created_at=datetime.now(),
            experiment_id="exp-test",
            runs=[
                PlanRun(
                    run_id="run-001",
                    randomization_seed_effective=42,
                    prompts_effective=Prompts(system=None, user="Answer: {question}"),
                    retry_policy=RetryPolicy(),
                    variants=[variant],
                    items=items_run1,
                ),
                PlanRun(
                    run_id="run-002",
                    randomization_seed_effective=99,
                    prompts_effective=Prompts(system=None, user="Answer: {question}"),
                    retry_policy=RetryPolicy(),
                    variants=[variant],
                    items=items_run2,
                ),
            ],
        )

        mock_results = [
            _make_success_result("run-001::var-001::snap-000::it-1"),
            _make_success_result("run-002::var-001::snap-001::it-1"),
        ]

        with patch(
            'src.core.async_orchestrator.ExecutionEngine',
            autospec=True,
        ) as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.randomizer = randomizer
            mock_engine._execute_item_async = AsyncMock(
                side_effect=_make_item_async_side_effect(
                    results_by_item_id={r.item_id: r for r in mock_results}
                )
            )

            orchestrator = AsyncOrchestrator(
                api_client=mock_api_client,
                db_connection=mock_db,
                randomizer=randomizer,
                parser=parser,
            )

            results = orchestrator.execute(plan)

            assert len(results) == 2
            mock_api_client.close.assert_awaited_once()

    @pytest.fixture
    def orchestrator(self, mock_api_client, mock_db, randomizer, parser):
        """Create an orchestrator with mocked dependencies."""
        return AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=mock_db,
            randomizer=randomizer,
            parser=parser,
        )
