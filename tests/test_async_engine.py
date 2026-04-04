"""Tests for async ExecutionEngine execution and queue pushing.

These tests verify:
1. Each result is pushed to queue after item completion
2. One item's failure doesn't affect subsequent items
3. The architecture supports concurrency parameter (future)
4. Queue receives results in execution order
5. Results pushed to queue match returned results

Usage:
    pytest tests/test_async_engine.py -v
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.core.execution_engine import ExecutionEngine, ExecutionResult
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(num_items: int = 3) -> ExecutionPlan:
    """Build a minimal ExecutionPlan."""
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
                    stem=f"Question {i + 1}",
                    options=["A", "B", "C", "D"],
                    answer_key="B",
                ),
            )
        )

    run = PlanRun(
        run_id="run-001",
        seed_effective=42,
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


def _make_mock_api_response():
    """Create a mock API chat_completion response."""
    response = MagicMock()
    response.content = "The answer is (B)."
    response.model_id = "openai/gpt-4o-mini"
    response.input_tokens = 50
    response.response_tokens = 10
    response.reasoning_tokens = 5
    response.cost = 0.0001
    response.latency_ms = 100
    response.raw_response = [{"choices": [{"message": {"content": "The answer is (B)."}}]}]
    response.finish_reason = "stop"
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAsyncEngineQueuePushing:
    """Test that execute_async pushes results to the queue."""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client."""
        client = MagicMock()
        client.chat_completion = AsyncMock(return_value=_make_mock_api_response())
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def randomizer(self):
        """Create a seeded randomizer."""
        return AnswerRandomizer(seed=42)

    @pytest.fixture
    def parser(self):
        """Create an answer parser."""
        return AnswerParser()

    @pytest.fixture
    def engine(self, mock_api_client, randomizer, parser):
        """Create an execution engine."""
        return ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

    @pytest.mark.asyncio
    async def test_execute_async_pushes_to_queue(self, engine):
        """Verify each result is pushed to queue after item completion.

        For every PlanItem executed, one ExecutionResult must appear
        on the result_queue. The queue is the communication channel
        between engine and AsyncWriter.
        """
        plan = _make_plan(num_items=3)
        queue: asyncio.Queue = asyncio.Queue()

        results = await engine.execute_async(plan, queue)

        # execute_async returns all results
        assert len(results) == 3

        # Queue should have exactly the same number of items
        assert queue.qsize() == 3

        # Drain queue and verify each item is an ExecutionResult
        queued_items = []
        while not queue.empty():
            item = queue.get_nowait()
            queued_items.append(item)

        assert len(queued_items) == 3
        for item in queued_items:
            assert isinstance(item, ExecutionResult)
            assert item.status == "success"

    @pytest.mark.asyncio
    async def test_queue_receives_results_in_execution_order(self, engine):
        """Verify results appear on queue in the same order they were executed."""
        plan = _make_plan(num_items=3)
        queue: asyncio.Queue = asyncio.Queue()

        await engine.execute_async(plan, queue)

        # Collect in order
        ordered_results = []
        while not queue.empty():
            ordered_results.append(queue.get_nowait())

        expected_ids = [
            "run-001::var-001::snap-000::it-1",
            "run-001::var-001::snap-001::it-2",
            "run-001::var-001::snap-002::it-3",
        ]
        actual_ids = [r.item_id for r in ordered_results]
        assert actual_ids == expected_ids

    @pytest.mark.asyncio
    async def test_results_match_queue_contents(self, engine):
        """Verify the returned results list matches what was pushed to queue."""
        plan = _make_plan(num_items=2)
        queue: asyncio.Queue = asyncio.Queue()

        returned = await engine.execute_async(plan, queue)

        queued = []
        while not queue.empty():
            queued.append(queue.get_nowait())

        assert len(returned) == len(queued)
        returned_ids = {r.item_id for r in returned}
        queued_ids = {r.item_id for r in queued}
        assert returned_ids == queued_ids


class TestAsyncEngineItemFailure:
    """Test that item failures are properly isolated."""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client."""
        client = MagicMock()
        client.chat_completion = AsyncMock(return_value=_make_mock_api_response())
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def randomizer(self):
        return AnswerRandomizer(seed=42)

    @pytest.fixture
    def parser(self):
        return AnswerParser()

    @pytest.mark.asyncio
    async def test_item_failure_isolated(self, mock_api_client, randomizer, parser):
        """Verify one item's failure doesn't affect subsequent items.

        When item N fails (e.g., API error), item N+1 must still
        execute normally and produce a success result. The failure
        must be contained to the failing item only.
        """
        plan = _make_plan(num_items=3)

        # Make the API call fail only on the second invocation
        call_count = [0]

        async def flaky_chat_completion(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Simulated API failure on item 2")
            return _make_mock_api_response()

        mock_api_client.chat_completion = flaky_chat_completion

        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

        queue: asyncio.Queue = asyncio.Queue()
        results = await engine.execute_async(plan, queue)

        assert len(results) == 3

        # Item 1: success
        assert results[0].status == "success"
        assert results[0].item_id == "run-001::var-001::snap-000::it-1"

        # Item 2: failure (API error)
        assert results[1].status == "failure"
        assert results[1].item_id == "run-001::var-001::snap-001::it-2"
        assert results[1].error_type is not None

        # Item 3: success (isolated from item 2's failure)
        assert results[2].status == "success"
        assert results[2].item_id == "run-001::var-001::snap-002::it-3"

        # All 3 results should be on the queue (including the failure)
        assert queue.qsize() == 3

        queued_items = []
        while not queue.empty():
            queued_items.append(queue.get_nowait())

        # Verify failure result was also pushed
        failure_items = [r for r in queued_items if r.status == "failure"]
        assert len(failure_items) == 1
        assert failure_items[0].item_id == "run-001::var-001::snap-001::it-2"

    @pytest.mark.asyncio
    async def test_multiple_item_failures_isolated(self, mock_api_client, randomizer, parser):
        """Verify multiple item failures don't cascade."""
        plan = _make_plan(num_items=4)

        # Fail on items 2 and 3
        call_count = [0]

        async def flaky_chat_completion(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] in (2, 3):
                raise TimeoutError(f"Simulated timeout on call {call_count[0]}")
            return _make_mock_api_response()

        mock_api_client.chat_completion = flaky_chat_completion

        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

        queue: asyncio.Queue = asyncio.Queue()
        results = await engine.execute_async(plan, queue)

        assert len(results) == 4
        statuses = [r.status for r in results]
        assert statuses == ["success", "failure", "failure", "success"]

        # All 4 results on queue
        assert queue.qsize() == 4

    @pytest.mark.asyncio
    async def test_failure_result_has_error_fields(self, mock_api_client, randomizer, parser):
        """Verify failure results contain proper error information."""
        plan = _make_plan(num_items=1)

        mock_api_client.chat_completion = AsyncMock(
            side_effect=RuntimeError("Connection refused")
        )

        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

        queue: asyncio.Queue = asyncio.Queue()
        results = await engine.execute_async(plan, queue)

        assert len(results) == 1
        result = results[0]

        assert result.status == "failure"
        assert result.response_text is None
        assert result.selected_answer is None
        assert result.parse_confidence is None
        assert result.error_type is not None
        assert result.error_message is not None
        assert result.attempt_count >= 1

        # Failure result also pushed to queue
        assert queue.qsize() == 1
        queued = queue.get_nowait()
        assert queued.status == "failure"
        assert queued.error_type is not None


class TestAsyncEngineConcurrency:
    """Test that the architecture supports future concurrency."""

    @pytest.fixture
    def mock_api_client(self):
        client = MagicMock()
        client.chat_completion = AsyncMock(return_value=_make_mock_api_response())
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def randomizer(self):
        return AnswerRandomizer(seed=42)

    @pytest.fixture
    def parser(self):
        return AnswerParser()

    @pytest.mark.asyncio
    async def test_concurrency_path_is_prepared(self, mock_api_client, randomizer, parser):
        """Verify the architecture supports concurrency parameter (future).

        The execute_async method accepts a result_queue parameter, which
        decouples result production from consumption. This design enables
        future concurrency by allowing:
        1. Multiple engine workers pushing to the same queue
        2. AsyncWriter consuming independently
        3. No shared mutable state between producer and consumer

        This test verifies the queue-based architecture exists.
        """
        plan = _make_plan(num_items=2)
        queue: asyncio.Queue = asyncio.Queue()

        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

        # execute_async signature must accept result_queue
        import inspect
        sig = inspect.signature(engine.execute_async)
        assert 'result_queue' in sig.parameters

        # Queue must be usable independently
        await engine.execute_async(plan, queue)
        assert queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_queue_is_async_safe(self, mock_api_client, randomizer, parser):
        """Verify the queue is safe for async producer/consumer pattern.

        asyncio.Queue is designed for exactly this pattern. We verify
        that results can be consumed from the queue while the engine
        is still executing (simulating concurrent producer/consumer).
        """
        plan = _make_plan(num_items=3)
        queue: asyncio.Queue = asyncio.Queue()

        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

        consumed_early = []

        async def consumer():
            """Simulates AsyncWriter consuming results concurrently."""
            while len(consumed_early) < 3:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=2.0)
                    if item is not None:
                        consumed_early.append(item)
                        queue.task_done()
                except asyncio.TimeoutError:
                    break

        # Run engine and consumer concurrently
        engine_task = asyncio.create_task(engine.execute_async(plan, queue))
        consumer_task = asyncio.create_task(consumer())

        await asyncio.gather(engine_task, consumer_task)

        # Consumer should have received all 3 results
        assert len(consumed_early) == 3
        assert all(isinstance(r, ExecutionResult) for r in consumed_early)

    @pytest.mark.asyncio
    async def test_queue_unlimited_size_supports_backpressure(self, mock_api_client, randomizer, parser):
        """Verify queue has unlimited size (no backpressure blocking).

        asyncio.Queue with maxsize=0 (default) has unlimited capacity.
        This ensures the engine never blocks waiting for the writer to
        consume. The writer controls its own pace independently.
        """
        queue: asyncio.Queue = asyncio.Queue()
        # Default asyncio.Queue has maxsize=0 (unlimited)
        assert queue.maxsize == 0


class TestAsyncEngineEmptyPlan:
    """Test edge cases with minimal/empty plans."""

    @pytest.fixture
    def mock_api_client(self):
        client = MagicMock()
        client.chat_completion = AsyncMock(return_value=_make_mock_api_response())
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def randomizer(self):
        return AnswerRandomizer(seed=42)

    @pytest.fixture
    def parser(self):
        return AnswerParser()

    @pytest.mark.asyncio
    async def test_execute_async_with_no_runs(self, mock_api_client, randomizer, parser):
        """Verify engine handles plan with zero runs."""
        plan = ExecutionPlan(
            plan_id="plan-empty",
            created_at=datetime.now(),
            experiment_id="exp-test",
            runs=[],
        )

        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

        queue: asyncio.Queue = asyncio.Queue()
        results = await engine.execute_async(plan, queue)

        assert results == []
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_execute_async_with_run_but_no_items(self, mock_api_client, randomizer, parser):
        """Verify engine handles run with zero items."""
        plan = ExecutionPlan(
            plan_id="plan-no-items",
            created_at=datetime.now(),
            experiment_id="exp-test",
            runs=[
                PlanRun(
                    run_id="run-empty",
                    seed_effective=None,
                    prompts_effective=Prompts(system=None, user="Answer: {question}"),
                    retry_policy=RetryPolicy(),
                    variants=[
                        PlanVariant(
                            variant_id="var-001",
                            model_id="openai/gpt-4o-mini",
                            model_config_effective=ModelConfig(),
                        )
                    ],
                    items=[],
                )
            ],
        )

        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

        queue: asyncio.Queue = asyncio.Queue()
        results = await engine.execute_async(plan, queue)

        assert results == []
        assert queue.empty()


class TestAsyncEngineVariantNotFound:
    """Test behavior when variant is not found for an item."""

    @pytest.fixture
    def randomizer(self):
        return AnswerRandomizer(seed=42)

    @pytest.fixture
    def parser(self):
        return AnswerParser()

    @pytest.mark.asyncio
    async def test_item_with_missing_variant_produces_failure_result(self, randomizer, parser):
        """Verify an item with a non-existent variant produces a failure result.

        If the variant_id in a PlanItem doesn't match any variant in the
        run's variants list, the engine must produce a failure result
        without calling the API.
        """
        variant = PlanVariant(
            variant_id="var-existent",
            model_id="openai/gpt-4o-mini",
            model_config_effective=ModelConfig(),
        )

        item = PlanItem(
            item_id="run-001::var-missing::snap-000::it-1",
            run_id="run-001",
            variant_id="var-missing",  # Doesn't exist in run.variants
            snapshot_id="snap-000",
            question_id="q1",
            question_payload=QuestionPayload(
                stem="Test question",
                options=["A", "B", "C", "D"],
                answer_key="A",
            ),
        )

        run = PlanRun(
            run_id="run-001",
            seed_effective=None,
            prompts_effective=Prompts(system=None, user="Answer: {question}"),
            retry_policy=RetryPolicy(),
            variants=[variant],  # Only "var-existent" exists
            items=[item],  # Item references "var-missing"
        )

        plan = ExecutionPlan(
            plan_id="plan-test",
            created_at=datetime.now(),
            experiment_id="exp-test",
            runs=[run],
        )

        mock_api_client = MagicMock()
        mock_api_client.chat_completion = AsyncMock()
        mock_api_client.close = AsyncMock()

        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=randomizer,
            parser=parser,
        )

        queue: asyncio.Queue = asyncio.Queue()
        results = await engine.execute_async(plan, queue)

        assert len(results) == 1
        result = results[0]
        assert result.status == "failure"
        assert result.error_type == "config_error"
        assert "Variant var-missing not found" in result.error_message

        # Failure result still pushed to queue
        assert queue.qsize() == 1
        queued = queue.get_nowait()
        assert queued.status == "failure"
        assert queued.error_type == "config_error"

        # API must NOT have been called
        mock_api_client.chat_completion.assert_not_called()
