"""Integration tests for execution pipeline contract invariants.

Validates system contract invariants:
- I3 — Strong Idempotency / Cost Protection: Re-execution MUST skip items
       with persisted responses. No API calls for completed items.
- I4 — Run Consolidation from DB Only: runs.duration derived from DB, not
       in-memory.
- I5 — Single Owner: Only RunFinalizer updates runs.* (status/duration).

All tests use in-memory SQLite with mocked API client.
"""

import json
import uuid
import pytest
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.db.repository import (
    ExperimentRepository,
    VariantRepository,
    SnapshotRepository,
    RunRepository,
    ResponseRepository,
)
from src.db.models import Experiment, ModelVariant, QuestionSnapshot, Run
from src.api.client import CompletionResponse
from src.core.planner import Planner
from src.core.execution_engine import ExecutionEngine
from src.core.result_writer import ResultWriter
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser
from src.core.run_finalizer import RunFinalizer
from src.core.async_orchestrator import AsyncOrchestrator


# =============================================================================
# Test Helpers
# =============================================================================

def _setup_minimal_experiment(conn, name="test-exp", num_questions=3):
    """Create experiment + 1 variant + N snapshots + 1 run.

    Returns dict with all IDs for downstream use.
    """
    exp_id = f"exp_{uuid.uuid4().hex[:8]}"
    experiment = Experiment(
        experiment_id=exp_id,
        name=name,
        description="Test experiment",
        config_json='{"SYSTEM_PROMPT": "You are helpful.", "USER_PROMPT": "Answer: {question}"}',
        config_hash="abc123",
    )
    ExperimentRepository(conn).save(experiment)

    variant_id = f"var_{uuid.uuid4().hex[:8]}"
    variant = ModelVariant(
        variant_id=variant_id,
        experiment_id=exp_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
        config='{}',
    )
    VariantRepository(conn).save(variant)

    snapshot_ids = []
    for i in range(1, num_questions + 1):
        snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
        payload = {
            "stem": f"Question {i} stem",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer_key": "B",
        }
        snapshot = QuestionSnapshot(
            snapshot_id=snapshot_id,
            experiment_id=exp_id,
            json_question_id=f"Q{i:02d}",
            question_position=i,
            question_payload=json.dumps(payload),
        )
        SnapshotRepository(conn).save(snapshot)
        snapshot_ids.append(snapshot_id)

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    run = Run(
        run_id=run_id,
        experiment_id=exp_id,
        status="pending",
        duration=0,
    )
    RunRepository(conn).save(run, config={"RANDOMIZATION_SEED": 42})

    return {
        "experiment_id": exp_id,
        "experiment_name": name,
        "variant_id": variant_id,
        "snapshot_ids": snapshot_ids,
        "run_id": run_id,
    }


def _execute_plan(conn, plan, mock_api_client):
    """Execute a plan via ExecutionEngine + ResultWriter synchronously."""
    import asyncio

    async def _run():
        queue = asyncio.Queue()
        engine = ExecutionEngine(
            api_client=mock_api_client,
            randomizer=AnswerRandomizer(seed=42),
            parser=AnswerParser(),
        )
        writer = ResultWriter(conn)

        # Execute all items
        results = await engine.execute_async(plan, queue)

        # Write all results
        for result in results:
            writer.write_result(result)

        return results

    return asyncio.run(_run())


def _make_mock_api_client(content="The answer is (B).", latency_ms=500):
    """Create a mock API client returning a deterministic response."""
    from src.api.client import OpenRouterClient
    client = MagicMock(spec=OpenRouterClient)
    client.chat_completion = AsyncMock(
        return_value=CompletionResponse(
            content=content,
            model_id="openai/gpt-4",
            input_tokens=50,
            response_tokens=10,
            latency_ms=latency_ms,
            raw_response={"content": content, "model": "openai/gpt-4"},
        )
    )
    client.close = AsyncMock()
    return client


def _count_api_calls(mock_client):
    """Count how many times chat_completion was called."""
    return mock_client.chat_completion.call_count


def _get_run_row(conn, run_id):
    """Get run row from DB."""
    cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    return cursor.fetchone()


def _count_responses(conn, run_id):
    """Count responses with raw_response IS NOT NULL for a run."""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM responses WHERE run_id = ? AND raw_response IS NOT NULL",
        (run_id,),
    )
    return cursor.fetchone()[0]


def _sum_latency_ms(conn, run_id):
    """Sum latency_ms from responses for a run."""
    cursor = conn.execute(
        "SELECT COALESCE(SUM(latency_ms), 0) FROM responses WHERE run_id = ? AND raw_response IS NOT NULL",
        (run_id,),
    )
    return cursor.fetchone()[0]


# =============================================================================
# I3 — Strong Idempotency / Cost Protection
# =============================================================================

@pytest.mark.integration
class TestIdempotencyContract:
    """Tests for I3: Re-execution MUST skip items with persisted responses."""

    def test_reexecution_skips_completed_items(self, in_memory_db):
        """
        Verify: Re-executing the same run makes ZERO new API calls.

        Steps:
        1. Create experiment, run, variant, snapshots
        2. Execute the run (first time — all items execute)
        3. Count API calls from first execution
        4. Re-execute the SAME run via a new plan
        5. Assert: API call count did NOT increase
        6. Assert: runs.duration unchanged
        7. Assert: runs.status unchanged
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=3)
        run_id = ctx["run_id"]

        mock_client = _make_mock_api_client()

        # First execution
        planner = Planner(in_memory_db)
        plan1 = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])
        results1 = _execute_plan(in_memory_db, plan1, mock_client)

        # Verify first execution produced results
        assert len(results1) == 3
        api_calls_after_first = _count_api_calls(mock_client)
        assert api_calls_after_first == 3

        # Finalize the run (simulating what AsyncOrchestrator does)
        finalizer = RunFinalizer(in_memory_db)
        finalizer.finalize_run(run_id)

        # Capture run state after first execution
        run_row_after_first = _get_run_row(in_memory_db, run_id)
        duration_after_first = run_row_after_first["duration"]
        status_after_first = run_row_after_first["status"]

        # Re-execute: build a new plan for the same run
        planner2 = Planner(in_memory_db)
        plan2 = planner2.build_plan(ctx["experiment_name"], run_ids=[run_id])

        # The plan should have 0 items since all are already executed
        plan2_items_count = sum(len(pr.items) for pr in plan2.runs)
        assert plan2_items_count == 0, (
            f"Expected 0 items in re-execution plan (all should be skipped), "
            f"got {plan2_items_count}"
        )

        # Execute the re-plan (should be a no-op)
        results2 = _execute_plan(in_memory_db, plan2, mock_client)

        # Verify: No new API calls were made
        api_calls_after_second = _count_api_calls(mock_client)
        assert api_calls_after_second == api_calls_after_first, (
            f"Expected {api_calls_after_first} API calls after re-execution, "
            f"got {api_calls_after_second} — idempotency violated"
        )

        # Verify: runs.duration unchanged
        run_row_after_second = _get_run_row(in_memory_db, run_id)
        assert run_row_after_second["duration"] == duration_after_first, (
            f"Duration changed after re-execution: "
            f"{duration_after_first} -> {run_row_after_second['duration']}"
        )

        # Verify: runs.status unchanged
        assert run_row_after_second["status"] == status_after_first, (
            f"Status changed after re-execution: "
            f"{status_after_first} -> {run_row_after_second['status']}"
        )

        # Verify: Response count unchanged
        resp_count = _count_responses(in_memory_db, run_id)
        assert resp_count == 3, f"Expected 3 responses, got {resp_count}"

    def test_partial_reexecution_only_executes_missing(self, in_memory_db):
        """
        Verify: When some items already have responses, only missing items execute.

        Steps:
        1. Create experiment, run, variant, 3 snapshots
        2. Manually insert responses for 2 items (simulating partial execution)
        3. Execute the run
        4. Assert: API client called ONLY for the 1 missing item
        5. Assert: runs.duration includes ALL items (old + new)
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=3)
        run_id = ctx["run_id"]
        variant_id = ctx["variant_id"]
        snapshot_ids = ctx["snapshot_ids"]

        # Manually insert responses for first 2 snapshots
        resp_repo = ResponseRepository(in_memory_db)
        from src.db.models import Response
        for i in range(2):
            response = Response(
                response_id=f"resp_manual_{i}",
                run_id=run_id,
                variant_id=variant_id,
                snapshot_id=snapshot_ids[i],
                model_id="openai/gpt-4",
                question_id=f"Q{i+1:02d}",
                status="success",
                response_text="The answer is (B).",
                selected_answer="B",
                parse_confidence="clear",
                raw_response='{"content": "The answer is (B)."}',
                latency_ms=300 + i * 100,  # 300ms, 400ms
                input_tokens=50,
                response_tokens=10,
            )
            resp_repo.save(response)

        # Verify: 2 responses exist
        assert _count_responses(in_memory_db, run_id) == 2

        # Now execute the run — should only execute the 3rd item
        mock_client = _make_mock_api_client(latency_ms=200)
        planner = Planner(in_memory_db)
        plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])

        # Verify plan only has 1 item (the missing one)
        plan_items = sum(len(pr.items) for pr in plan.runs)
        assert plan_items == 1, f"Expected 1 item in plan, got {plan_items}"

        results = _execute_plan(in_memory_db, plan, mock_client)

        # Verify: API called exactly once (for the missing item)
        assert _count_api_calls(mock_client) == 1

        # Verify: Total responses = 3 (2 manual + 1 executed)
        assert _count_responses(in_memory_db, run_id) == 3

        # Finalize and verify duration includes ALL items
        finalizer = RunFinalizer(in_memory_db)
        finalizer.finalize_run(run_id)

        run_row = _get_run_row(in_memory_db, run_id)
        # Expected: 300 + 400 + 200 = 900ms
        expected_duration = 300 + 400 + 200
        assert run_row["duration"] == expected_duration, (
            f"Expected duration {expected_duration}ms (all items), "
            f"got {run_row['duration']}ms"
        )


# =============================================================================
# I4 — Run Consolidation from DB Only
# =============================================================================

@pytest.mark.integration
class TestRunConsolidationContract:
    """Tests for I4: runs.duration derived from DB, not in-memory."""

    def test_duration_derived_from_db_not_memory(self, in_memory_db):
        """
        Verify: runs.duration matches SUM(latency_ms) from DB responses.

        Steps:
        1. Create experiment, run, variant, 3 snapshots
        2. Execute the run with known latency values
        3. Finalize the run
        4. Query DB for SUM(latency_ms)
        5. Assert: runs.duration == SUM(latency_ms) from DB
        6. Assert: no other code path updates runs.duration
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=3)
        run_id = ctx["run_id"]

        # Use a mock client with known latency_ms per call
        call_counter = [0]
        latencies = [100, 200, 300]  # Known latencies

        from src.api.client import OpenRouterClient
        mock_client = MagicMock(spec=OpenRouterClient)

        def side_effect(*args, **kwargs):
            latency = latencies[call_counter[0]]
            call_counter[0] += 1
            return CompletionResponse(
                content="The answer is (B).",
                model_id="openai/gpt-4",
                input_tokens=50,
                response_tokens=10,
                latency_ms=latency,
                raw_response={"content": "The answer is (B).", "model": "openai/gpt-4"},
            )

        mock_client.chat_completion = AsyncMock(side_effect=side_effect)

        # Execute
        planner = Planner(in_memory_db)
        plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])
        results = _execute_plan(in_memory_db, plan, mock_client)
        assert len(results) == 3

        # Finalize
        finalizer = RunFinalizer(in_memory_db)
        finalizer.finalize_run(run_id)

        # Get duration from DB
        run_row = _get_run_row(in_memory_db, run_id)
        db_duration = run_row["duration"]

        # Get SUM(latency_ms) from DB directly
        db_sum_latency = _sum_latency_ms(in_memory_db, run_id)

        # Verify: runs.duration == SUM(latency_ms)
        assert db_duration == db_sum_latency, (
            f"runs.duration ({db_duration}) != SUM(latency_ms) ({db_sum_latency}) "
            f"— duration not derived from DB"
        )

        # Expected: 100 + 200 + 300 = 600
        expected = sum(latencies)
        assert db_duration == expected, (
            f"Expected duration {expected}ms, got {db_duration}ms"
        )

    def test_duration_includes_only_successful_responses(self, in_memory_db):
        """
        Verify: Duration calculation only includes responses with raw_response.

        Error-only records (no raw_response) should NOT contribute to duration.
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=2)
        run_id = ctx["run_id"]
        variant_id = ctx["variant_id"]
        snapshot_ids = ctx["snapshot_ids"]

        # Insert one successful response
        resp_repo = ResponseRepository(in_memory_db)
        from src.db.models import Response
        success_response = Response(
            response_id="resp_success",
            run_id=run_id,
            variant_id=variant_id,
            snapshot_id=snapshot_ids[0],
            model_id="openai/gpt-4",
            question_id="Q01",
            status="success",
            response_text="The answer is (B).",
            selected_answer="B",
            parse_confidence="clear",
            raw_response='{"content": "The answer is (B)."}',
            latency_ms=500,
            input_tokens=50,
            response_tokens=10,
        )
        resp_repo.save(success_response)

        # Insert one error-only record (no raw_response)
        error_response = Response(
            response_id="resp_error",
            run_id=run_id,
            variant_id=variant_id,
            snapshot_id=snapshot_ids[1],
            model_id="openai/gpt-4",
            question_id="Q02",
            status="failure",
            response_text=None,
            selected_answer=None,
            parse_confidence=None,
            raw_response=None,  # No raw response
            latency_ms=999,  # This should NOT be counted
            input_tokens=0,
            response_tokens=0,
        )
        resp_repo.save(error_response)

        # Also insert into errors table via ResultWriter
        from src.core.result_writer import ResultWriter
        from src.core.execution_engine import ExecutionResult

        error_result = ExecutionResult(
            item_id="item-fail",
            run_id=run_id,
            variant_id=variant_id,
            snapshot_id=snapshot_ids[1],
            question_id="Q02",
            status="failure",
            error_type="api_error",
            error_message="API timeout",
            attempt_count=3,
            response_text=None,
            selected_answer=None,
            parse_confidence=None,
            latency_ms=None,
            input_tokens=None,
            response_tokens=None,
            reasoning_tokens=None,
            raw_response=None,
            started_at=datetime.now(),
            finished_at=datetime.now(),
        )
        ResultWriter(in_memory_db).write_result(error_result)

        # Finalize
        finalizer = RunFinalizer(in_memory_db)
        finalizer.finalize_run(run_id)

        run_row = _get_run_row(in_memory_db, run_id)

        # Duration should only include the successful response (500ms)
        assert run_row["duration"] == 500, (
            f"Expected duration 500ms (successful only), got {run_row['duration']}ms"
        )


# =============================================================================
# I5 — Single Owner
# =============================================================================

@pytest.mark.integration
class TestSingleOwnerContract:
    """Tests for I5: Only RunFinalizer updates runs.status and runs.duration."""

    def test_run_finalizer_is_single_owner(self, in_memory_db):
        """
        Verify: After execution, runs.status/duration were set by RunFinalizer.

        Steps:
        1. Create experiment, run, variant, snapshots
        2. Execute the run
        3. Verify run is still 'pending' before finalization
        4. Finalize via RunFinalizer
        5. Verify runs.status and runs.duration were updated
        6. Verify AsyncOrchestrator does NOT contain UPDATE runs SQL
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=2)
        run_id = ctx["run_id"]

        mock_client = _make_mock_api_client()

        # Execute
        planner = Planner(in_memory_db)
        plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])
        results = _execute_plan(in_memory_db, plan, mock_client)
        assert len(results) == 2

        # Before finalization, run should still be 'pending'
        run_row_before = _get_run_row(in_memory_db, run_id)
        assert run_row_before["status"] == "pending", (
            f"Run status should be 'pending' before finalization, "
            f"got '{run_row_before['status']}'"
        )

        # Finalize
        finalizer = RunFinalizer(in_memory_db)
        result = finalizer.finalize_run(run_id)

        # Verify finalizer returned correct status
        assert result["status"] == "completed"
        assert result["duration_ms"] > 0
        assert result["response_count"] == 2

        # Verify DB was updated
        run_row_after = _get_run_row(in_memory_db, run_id)
        assert run_row_after["status"] == "completed"
        assert run_row_after["duration"] > 0

    def test_async_orchestrator_has_no_update_runs_sql(self):
        """
        Verify: AsyncOrchestrator source does NOT contain UPDATE runs SQL.

        This is a static analysis check ensuring AsyncOrchestrator never
        directly updates runs.* — only RunFinalizer should.
        """
        import inspect
        from src.core.async_orchestrator import AsyncOrchestrator

        # Get the source code of AsyncOrchestrator
        source = inspect.getsource(AsyncOrchestrator)

        # Verify AsyncOrchestrator does NOT contain UPDATE runs SQL
        assert "UPDATE runs" not in source, (
            "AsyncOrchestrator contains 'UPDATE runs' SQL — "
            "this violates I5 (Single Owner). Only RunFinalizer may update runs.*"
        )

        # Verify AsyncOrchestrator DOES call RunFinalizer
        assert "RunFinalizer" in source, (
            "AsyncOrchestrator does not reference RunFinalizer — "
            "run finalization would be skipped"
        )

    def test_no_other_component_updates_runs(self, in_memory_db):
        """
        Verify: After execution WITHOUT finalization, runs.status/duration
        remain unchanged. Only explicit RunFinalizer call updates them.
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=2)
        run_id = ctx["run_id"]

        mock_client = _make_mock_api_client()

        # Execute via engine + writer (NOT via orchestrator which calls finalizer)
        planner = Planner(in_memory_db)
        plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])
        results = _execute_plan(in_memory_db, plan, mock_client)
        assert len(results) == 2

        # Verify: Without calling RunFinalizer, runs.status is still 'pending'
        # and duration is still 0
        run_row = _get_run_row(in_memory_db, run_id)
        assert run_row["status"] == "pending", (
            f"Run status should remain 'pending' without finalization, "
            f"got '{run_row['status']}'"
        )
        assert run_row["duration"] == 0, (
            f"Run duration should remain 0 without finalization, "
            f"got {run_row['duration']}"
        )

        # Now finalize and verify update
        finalizer = RunFinalizer(in_memory_db)
        finalizer.finalize_run(run_id)

        run_row_after = _get_run_row(in_memory_db, run_id)
        assert run_row_after["status"] == "completed"
        assert run_row_after["duration"] > 0
