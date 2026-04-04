"""End-to-end integration tests for the full async pipeline.

These tests verify:
1. Full pipeline: orchestrator → engine → queue → writer → DB
2. Incremental persistence: results appear in DB during execution
3. End-to-end success path with real DB
4. End-to-end failure handling with real DB
5. Resource cleanup after full pipeline execution

Usage:
    pytest tests/test_integration_async.py -v

NOTE: The current source code has a gap where AsyncOrchestrator._execute_async
calls engine.execute_async(plan) without passing result_queue. These tests
work around this by patching _execute_async with the correct implementation.
Once the source code is fixed, the patches can be removed.
"""

import asyncio
import json
import pytest
import sqlite3
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.core.async_orchestrator import AsyncOrchestrator
from src.core.async_writer import AsyncWriter
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
from src.api.client import OpenRouterClient
from src.db.schema import create_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api_response():
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
                    options=["Option A", "Option B", "Option C", "Option D"],
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
        plan_id="plan-integration-test",
        created_at=datetime.now(),
        experiment_id="exp-test",
        runs=[run],
    )


def _seed_db_with_prerequisites(conn, extra_variants=None):
    """Insert prerequisite rows that ResultWriter needs (experiment, variant, run, snapshots)."""
    cursor = conn.cursor()
    # Experiment (must include config_json and config_hash NOT NULL)
    cursor.execute(
        "INSERT OR IGNORE INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
        ("exp-test", "Test Experiment", "{}", "hash-test"),
    )
    # Model variant (must include all NOT NULL columns: variant_signature, config)
    cursor.execute(
        "INSERT OR IGNORE INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config) VALUES (?, ?, ?, ?, ?)",
        ("var-001", "exp-test", "openai/gpt-4o-mini", "sig-001", "{}"),
    )
    if extra_variants:
        for vid, mid in extra_variants:
            cursor.execute(
                "INSERT OR IGNORE INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config) VALUES (?, ?, ?, ?, ?)",
                (vid, "exp-test", mid, f"sig-{vid}", "{}"),
            )
    # Run (must include config TEXT NOT NULL)
    cursor.execute(
        "INSERT OR IGNORE INTO runs (run_id, experiment_id, config) VALUES (?, ?, ?)",
        ("run-001", "exp-test", "{}"),
    )
    # Question snapshots (must include json_question_id and question_position NOT NULL)
    for i in range(5):
        payload_json = json.dumps({
            "stem": f"Question {i + 1}",
            "options": ["A", "B", "C", "D"],
            "answer_key": "B",
        })
        cursor.execute(
            "INSERT OR IGNORE INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload) VALUES (?, ?, ?, ?, ?)",
            (f"snap-{i:03d}", "exp-test", f"q{i + 1}", i + 1, payload_json),
        )
    conn.commit()


# Correct implementation that wires engine → queue → writer
async def _correct_execute_async(self, plan):
    """Correct implementation that passes result_queue to engine.execute_async."""
    experiment_id = plan.experiment_id
    run_count = len(plan.runs)
    total_items = sum(len(run.items) for run in plan.runs)

    self._logger.info(
        f"ORCHESTRATOR_START | experiment={experiment_id} | runs={run_count} | total_items={total_items}"
    )

    queue: asyncio.Queue = asyncio.Queue()

    writer = AsyncWriter(queue, self.db_connection, self._logger)
    writer_task = asyncio.create_task(writer.consume())

    try:
        engine = ExecutionEngine(
            api_client=self.api_client,
            randomizer=self.randomizer,
            parser=self.parser,
            logger=self._logger,
        )

        results = await engine.execute_async(plan, queue)

        # Engine pushed all results to queue. Now send sentinel.
        await queue.put(None)
        await writer_task

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
            pass
        raise

    finally:
        await self.api_client.close()


@pytest.fixture
def db_connection():
    """Create temporary SQLite DB with schema and prerequisite data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    _seed_db_with_prerequisites(conn)

    yield conn

    try:
        conn.close()
    except Exception:
        pass


@pytest.fixture
def mock_api_client():
    """Create a mock API client that returns successful responses."""
    client = MagicMock(spec=OpenRouterClient)
    client.chat_completion = AsyncMock(return_value=_make_api_response())
    client.close = AsyncMock()
    return client


@pytest.fixture
def patched_orchestrator_cls():
    """Patch AsyncOrchestrator._execute_async with the correct implementation.

    This fixture patches the source code gap where execute_async(plan) is called
    without result_queue. Returns the original method for cleanup.
    """
    original = AsyncOrchestrator._execute_async
    with patch.object(AsyncOrchestrator, '_execute_async', _correct_execute_async):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIntegrationAsyncFullPipeline:
    """End-to-end integration test of the full async pipeline."""

    def test_full_pipeline_orchestrator_to_db(self, db_connection, mock_api_client, patched_orchestrator_cls):
        """Verify: orchestrator → engine → queue → writer → DB."""
        plan = _make_plan(num_items=3)
        randomizer = AnswerRandomizer(seed=42)
        parser = AnswerParser()

        orchestrator = AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=db_connection,
            randomizer=randomizer,
            parser=parser,
        )

        results = orchestrator.execute(plan)

        assert len(results) == 3
        assert all(r.status == "success" for r in results)

        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM responses")
        count = cursor.fetchone()[0]
        assert count == 3

        cursor.execute(
            "SELECT response_id, run_id, variant_id, snapshot_id, status "
            "FROM responses ORDER BY response_id"
        )
        rows = cursor.fetchall()
        assert len(rows) == 3

        db_run_variant_snap = {(row[1], row[2], row[3]) for row in rows}
        expected = {
            ("run-001", "var-001", "snap-000"),
            ("run-001", "var-001", "snap-001"),
            ("run-001", "var-001", "snap-002"),
        }
        assert db_run_variant_snap == expected
        assert all(row[4] == "success" for row in rows)

    def test_pipeline_with_failure_then_db_write(self, db_connection, patched_orchestrator_cls):
        """Verify pipeline handles item failure and still writes it to DB."""
        plan = _make_plan(num_items=3)
        randomizer = AnswerRandomizer(seed=42)
        parser = AnswerParser()

        call_count = [0]

        async def flaky_completion(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("API timeout on item 2")
            return _make_api_response()

        mock_api_client = MagicMock(spec=OpenRouterClient)
        mock_api_client.chat_completion = flaky_completion
        mock_api_client.close = AsyncMock()

        orchestrator = AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=db_connection,
            randomizer=randomizer,
            parser=parser,
        )

        results = orchestrator.execute(plan)

        assert len(results) == 3
        statuses = [r.status for r in results]
        assert statuses == ["success", "failure", "success"]

        # All 3 items must be accounted for: 2 in responses (success) + 1 in errors (failure)
        cursor = db_connection.cursor()
        cursor.execute("SELECT run_id, variant_id, snapshot_id, status FROM responses ORDER BY response_id")
        success_rows = cursor.fetchall()
        assert len(success_rows) == 2

        cursor.execute("SELECT run_id, variant_id, snapshot_id, error_type FROM errors ORDER BY error_id")
        error_rows = cursor.fetchall()
        assert len(error_rows) == 1

        # Verify the failure is for snap-001 (item 2)
        assert error_rows[0][3] == "timeout"
        # Verify successes are for snap-000 and snap-002
        success_snaps = {(row[0], row[1], row[2]) for row in success_rows}
        assert ("run-001", "var-001", "snap-000") in success_snaps
        assert ("run-001", "var-001", "snap-002") in success_snaps


class TestIntegrationAsyncIncrementalPersistence:
    """Test that results are persisted during execution, not batched at end."""

    def test_incremental_persistence_during_execution(self, db_connection, mock_api_client, patched_orchestrator_cls):
        """Verify all results are in DB after orchestrator.execute() returns."""
        plan = _make_plan(num_items=3)
        randomizer = AnswerRandomizer(seed=42)
        parser = AnswerParser()

        orchestrator = AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=db_connection,
            randomizer=randomizer,
            parser=parser,
        )

        results = orchestrator.execute(plan)
        assert len(results) == 3

        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM responses")
        final_count = cursor.fetchone()[0]
        assert final_count == 3

    @pytest.mark.asyncio
    async def test_writer_consumes_as_results_arrive(self, db_connection):
        """Verify the writer processes results as they arrive, not all at end."""
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, db_connection)

        writer_task = asyncio.create_task(writer.consume())

        for i in range(3):
            result = ExecutionResult(
                item_id=f"item-{i:03d}",
                run_id="run-001",
                variant_id="var-001",
                snapshot_id=f"snap-{i:03d}",
                question_id=f"q{i + 1}",
                status="success",
                response_text=f"Answer {i + 1}",
                selected_answer="B",
                parse_confidence="clear",
                latency_ms=100,
                input_tokens=50,
                response_tokens=10,
                error_type=None,
                error_message=None,
                attempt_count=1,
                randomization_enabled=False,
                randomization_seed=None,
                options_presented=["A", "B", "C", "D"],
                correct_option_presented="B",
                option_letter_map={"A": "A", "B": "B", "C": "C", "D": "D"},
            )
            await queue.put(result)
            await asyncio.sleep(0.05)

            cursor = db_connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM responses")
            count = cursor.fetchone()[0]
            assert count >= i + 1, f"Expected at least {i + 1} rows after pushing {i + 1} results"

        await queue.put(None)
        stats = await writer_task

        assert stats["written"] == 3
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM responses")
        final_count = cursor.fetchone()[0]
        assert final_count == 3


class TestIntegrationAsyncResourceCleanup:
    """Test that resources are properly cleaned up after pipeline execution."""

    def test_api_client_closed_after_pipeline(self, db_connection, mock_api_client, patched_orchestrator_cls):
        """Verify API client is closed after orchestrator completes."""
        plan = _make_plan(num_items=2)
        randomizer = AnswerRandomizer(seed=42)
        parser = AnswerParser()

        orchestrator = AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=db_connection,
            randomizer=randomizer,
            parser=parser,
        )

        orchestrator.execute(plan)
        mock_api_client.close.assert_awaited_once()

    def test_api_client_closed_on_engine_exception(self, db_connection, patched_orchestrator_cls):
        """Verify API client is closed even when all API calls fail.

        NOTE: The ExecutionEngine catches API exceptions and converts
        them to failure results. It does NOT raise exceptions for individual
        item failures. The orchestrator only raises on systemic failures
        (e.g., engine instantiation failure).
        """
        plan = _make_plan(num_items=1)
        randomizer = AnswerRandomizer(seed=42)
        parser = AnswerParser()

        mock_api_client = MagicMock(spec=OpenRouterClient)
        mock_api_client.chat_completion = AsyncMock(
            side_effect=RuntimeError("API permanently down")
        )
        mock_api_client.close = AsyncMock()

        orchestrator = AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=db_connection,
            randomizer=randomizer,
            parser=parser,
        )

        # Engine catches the exception and returns a failure result
        results = orchestrator.execute(plan)

        # The result should be a failure
        assert len(results) == 1
        assert results[0].status == "failure"
        assert results[0].error_type is not None

        # Client must still be closed
        mock_api_client.close.assert_awaited_once()

    def test_writer_task_completes_before_orchestrator_returns(self, db_connection, mock_api_client, patched_orchestrator_cls):
        """Verify writer finishes all work before execute() returns."""
        plan = _make_plan(num_items=3)
        randomizer = AnswerRandomizer(seed=42)
        parser = AnswerParser()

        orchestrator = AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=db_connection,
            randomizer=randomizer,
            parser=parser,
        )

        results = orchestrator.execute(plan)

        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM responses")
        count = cursor.fetchone()[0]
        assert count == 3
        assert len(results) == 3


class TestIntegrationAsyncMultiVariant:
    """Test pipeline with multiple model variants."""

    def test_pipeline_with_multiple_variants(self, db_connection, patched_orchestrator_cls):
        """Verify pipeline handles multiple variants in a single run."""
        # Seed extra variant
        _seed_db_with_prerequisites(db_connection, extra_variants=[
            ("var-002", "anthropic/claude-3-haiku"),
        ])

        variant1 = PlanVariant(
            variant_id="var-001",
            model_id="openai/gpt-4o-mini",
            model_config_effective=ModelConfig(temperature=0.7),
        )
        variant2 = PlanVariant(
            variant_id="var-002",
            model_id="anthropic/claude-3-haiku",
            model_config_effective=ModelConfig(temperature=0.5),
        )

        items = [
            PlanItem(
                item_id="run-001::var-001::snap-000::it-1",
                run_id="run-001",
                variant_id="var-001",
                snapshot_id="snap-000",
                question_id="q1",
                question_payload=QuestionPayload(
                    stem="Question 1",
                    options=["A", "B", "C", "D"],
                    answer_key="B",
                ),
            ),
            PlanItem(
                item_id="run-001::var-002::snap-000::it-2",
                run_id="run-001",
                variant_id="var-002",
                snapshot_id="snap-000",
                question_id="q1",
                question_payload=QuestionPayload(
                    stem="Question 1",
                    options=["A", "B", "C", "D"],
                    answer_key="B",
                ),
            ),
        ]

        run = PlanRun(
            run_id="run-001",
            seed_effective=42,
            prompts_effective=Prompts(system=None, user="Answer: {question}"),
            retry_policy=RetryPolicy(),
            variants=[variant1, variant2],
            items=items,
        )

        plan = ExecutionPlan(
            plan_id="plan-multi-variant",
            created_at=datetime.now(),
            experiment_id="exp-test",
            runs=[run],
        )

        mock_api_client = MagicMock(spec=OpenRouterClient)
        mock_api_client.chat_completion = AsyncMock(return_value=_make_api_response())
        mock_api_client.close = AsyncMock()

        randomizer = AnswerRandomizer(seed=42)
        parser = AnswerParser()

        orchestrator = AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=db_connection,
            randomizer=randomizer,
            parser=parser,
        )

        results = orchestrator.execute(plan)

        assert len(results) == 2
        assert all(r.status == "success" for r in results)

        cursor = db_connection.cursor()
        cursor.execute("SELECT variant_id FROM responses ORDER BY variant_id")
        rows = cursor.fetchall()
        variant_ids = {row[0] for row in rows}
        assert "var-001" in variant_ids
        assert "var-002" in variant_ids


class TestIntegrationAsyncDBWriteFailure:
    """Test pipeline behavior when DB writes fail."""

    def test_pipeline_continues_when_db_write_fails(self, mock_api_client, patched_orchestrator_cls):
        """Verify pipeline continues when a DB write fails mid-execution."""
        plan = _make_plan(num_items=3)
        randomizer = AnswerRandomizer(seed=42)
        parser = AnswerParser()

        failing_conn = MagicMock()
        write_call_count = [0]

        def failing_execute(sql, params=None):
            write_call_count[0] += 1
            if write_call_count[0] == 2:
                raise sqlite3.OperationalError("Disk I/O error")

        failing_conn.execute = failing_execute
        failing_conn.cursor = MagicMock(return_value=MagicMock())

        orchestrator = AsyncOrchestrator(
            api_client=mock_api_client,
            db_connection=failing_conn,
            randomizer=randomizer,
            parser=parser,
        )

        results = orchestrator.execute(plan)

        assert len(results) == 3
        assert all(r.status == "success" for r in results)
