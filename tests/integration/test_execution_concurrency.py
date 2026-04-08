"""Integration tests for execution pipeline concurrency invariants.

Validates system contract invariant:
- I1 — Single Pipeline with Configurable Concurrency:
  - concurrency=1 behaves sequential
  - concurrency>1 works correctly
  - Idempotency is preserved at all concurrency levels

All tests use in-memory SQLite with mocked API client.
"""

import asyncio
import json
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call

import pytest

# Add src to path for imports
import sys
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
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser
from src.core.run_finalizer import RunFinalizer
from src.core.async_orchestrator import AsyncOrchestrator


# =============================================================================
# Test Helpers
# =============================================================================

def _setup_minimal_experiment(conn, name="test-exp", num_questions=4):
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
    RunRepository(conn).save(run, config={"RUN_RESPONSES_SEED": 42})

    return {
        "experiment_id": exp_id,
        "experiment_name": name,
        "variant_id": variant_id,
        "snapshot_ids": snapshot_ids,
        "run_id": run_id,
    }


def _make_mock_api_client_with_tracking(latency_ms=100):
    """Create a mock API client that tracks call order and timing."""
    from src.api.client import OpenRouterClient

    call_log = []  # List of (timestamp, call_index) tuples

    async def tracked_completion(*args, **kwargs):
        call_index = len(call_log)
        timestamp = time.monotonic()
        call_log.append({"timestamp": timestamp, "index": call_index, "args": args, "kwargs": kwargs})
        # Simulate some async work
        await asyncio.sleep(latency_ms / 1000.0)
        return CompletionResponse(
            content="The answer is (B).",
            model_id="openai/gpt-4",
            input_tokens=50,
            response_tokens=10,
            latency_ms=latency_ms,
            raw_response={"content": "The answer is (B).", "model": "openai/gpt-4"},
        )

    client = MagicMock(spec=OpenRouterClient)
    client.chat_completion = AsyncMock(side_effect=tracked_completion)
    client.close = AsyncMock()
    client._call_log = call_log  # Expose for inspection
    return client


def _count_responses(conn, run_id):
    """Count responses with raw_response IS NOT NULL for a run."""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM responses WHERE run_id = ? AND raw_response IS NOT NULL",
        (run_id,),
    )
    return cursor.fetchone()[0]


def _get_run_row(conn, run_id):
    """Get run row from DB."""
    cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    return cursor.fetchone()


def _execute_via_orchestrator(conn, plan, mock_client, max_concurrency=1):
    """Execute a plan via AsyncOrchestrator."""
    orchestrator = AsyncOrchestrator(
        api_client=mock_client,
        db_connection=conn,
        randomizer=AnswerRandomizer(seed=42),
        parser=AnswerParser(),
        max_concurrency=max_concurrency,
    )
    results = orchestrator.execute(plan)

    # Finalize each run
    for run in plan.runs:
        finalizer = RunFinalizer(conn)
        finalizer.finalize_run(run.run_id)

    return results


# =============================================================================
# I1 — Single Pipeline with Configurable Concurrency
# =============================================================================

@pytest.mark.integration
class TestConcurrencyContract:
    """Tests for I1: Pipeline with configurable concurrency."""

    def test_concurrency_1_sequential(self, in_memory_db):
        """
        Verify: With concurrency=1, all items complete sequentially.

        Steps:
        1. Create experiment with 4 questions
        2. Execute with concurrency=1
        3. Verify all items completed
        4. Verify call timestamps show sequential ordering (no overlap)
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=4)
        run_id = ctx["run_id"]

        mock_client = _make_mock_api_client_with_tracking(latency_ms=50)

        planner = Planner(in_memory_db)
        plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])

        results = _execute_via_orchestrator(
            in_memory_db, plan, mock_client, max_concurrency=1
        )

        # Verify all items completed
        assert len(results) == 4
        assert all(r.status == "success" for r in results)

        # Verify all responses persisted
        assert _count_responses(in_memory_db, run_id) == 4

        # Verify run finalized correctly
        run_row = _get_run_row(in_memory_db, run_id)
        assert run_row["status"] == "completed"
        assert run_row["duration"] > 0

        # Verify sequential ordering: each call starts after the previous one
        call_log = mock_client._call_log
        assert len(call_log) == 4
        for i in range(1, len(call_log)):
            assert call_log[i]["timestamp"] >= call_log[i - 1]["timestamp"], (
                f"Call {i} started before call {i-1} completed — "
                f"sequential execution violated"
            )

    def test_concurrency_4_parallel(self, in_memory_db):
        """
        Verify: With concurrency=4, all items complete correctly.

        Steps:
        1. Create experiment with 4 questions
        2. Execute with concurrency=4
        3. Verify all items completed
        4. Verify all responses persisted, no duplicates
        5. Verify run finalized correctly
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=4)
        run_id = ctx["run_id"]

        mock_client = _make_mock_api_client_with_tracking(latency_ms=50)

        planner = Planner(in_memory_db)
        plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])

        results = _execute_via_orchestrator(
            in_memory_db, plan, mock_client, max_concurrency=4
        )

        # Verify all items completed
        assert len(results) == 4
        assert all(r.status == "success" for r in results)

        # Verify all responses persisted
        assert _count_responses(in_memory_db, run_id) == 4

        # Verify no duplicate rows (UNIQUE constraint on run_id, variant_id, snapshot_id)
        cursor = in_memory_db.execute(
            """
            SELECT run_id, variant_id, snapshot_id, COUNT(*) as cnt
            FROM responses
            WHERE run_id = ? AND raw_response IS NOT NULL
            GROUP BY run_id, variant_id, snapshot_id
            HAVING cnt > 1
            """,
            (run_id,),
        )
        duplicates = cursor.fetchall()
        assert len(duplicates) == 0, f"Found duplicate responses: {duplicates}"

        # Verify run finalized correctly
        run_row = _get_run_row(in_memory_db, run_id)
        assert run_row["status"] == "completed"
        assert run_row["duration"] > 0

    def test_concurrency_4_reexecution_skip(self, in_memory_db):
        """
        Verify: Re-execution with concurrency=4 skips completed items.

        Steps:
        1. Create experiment with 4 questions
        2. Execute with concurrency=4
        3. Re-execute same run with concurrency=4
        4. Assert: no new API calls
        5. Assert: duration unchanged
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=4)
        run_id = ctx["run_id"]

        mock_client = _make_mock_api_client_with_tracking(latency_ms=50)

        # First execution
        planner = Planner(in_memory_db)
        plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])

        results = _execute_via_orchestrator(
            in_memory_db, plan, mock_client, max_concurrency=4
        )
        assert len(results) == 4

        api_calls_first = mock_client.chat_completion.call_count
        assert api_calls_first == 4

        run_row_after_first = _get_run_row(in_memory_db, run_id)
        duration_after_first = run_row_after_first["duration"]

        # Re-execute: new plan should have 0 items
        planner2 = Planner(in_memory_db)
        plan2 = planner2.build_plan(ctx["experiment_name"], run_ids=[run_id])
        plan2_items = sum(len(pr.items) for pr in plan2.runs)
        assert plan2_items == 0, (
            f"Expected 0 items in re-execution plan, got {plan2_items}"
        )

        # Execute re-plan (should be no-op)
        results2 = _execute_via_orchestrator(
            in_memory_db, plan2, mock_client, max_concurrency=4
        )
        assert len(results2) == 0

        # Verify: No new API calls
        api_calls_second = mock_client.chat_completion.call_count
        assert api_calls_second == api_calls_first, (
            f"Expected {api_calls_first} API calls after re-execution, "
            f"got {api_calls_second}"
        )

        # Verify: Duration unchanged
        run_row_after_second = _get_run_row(in_memory_db, run_id)
        assert run_row_after_second["duration"] == duration_after_first, (
            f"Duration changed: {duration_after_first} -> "
            f"{run_row_after_second['duration']}"
        )

    def test_concurrency_preserves_idempotency(self, in_memory_db):
        """
        Verify: Multiple re-executions with concurrency=4 never increase response count.

        Steps:
        1. Create experiment with 4 questions
        2. Execute with concurrency=4
        3. Re-execute 3 more times
        4. Assert: response count never increases beyond 4
        5. Assert: no duplicate rows
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=4)
        run_id = ctx["run_id"]

        for execution_round in range(4):
            mock_client = _make_mock_api_client_with_tracking(latency_ms=50)

            planner = Planner(in_memory_db)
            plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])

            plan_items = sum(len(pr.items) for pr in plan.runs)

            results = _execute_via_orchestrator(
                in_memory_db, plan, mock_client, max_concurrency=4
            )

            # After first execution: 4 items executed
            # After subsequent: 0 items (all skipped)
            if execution_round == 0:
                assert len(results) == 4
                assert mock_client.chat_completion.call_count == 4
            else:
                assert len(results) == 0
                assert mock_client.chat_completion.call_count == 0

            # Verify response count never exceeds 4
            resp_count = _count_responses(in_memory_db, run_id)
            assert resp_count == 4, (
                f"Round {execution_round}: Expected 4 responses, got {resp_count}"
            )

            # Verify no duplicates
            cursor = in_memory_db.execute(
                """
                SELECT run_id, variant_id, snapshot_id, COUNT(*) as cnt
                FROM responses
                WHERE run_id = ? AND raw_response IS NOT NULL
                GROUP BY run_id, variant_id, snapshot_id
                HAVING cnt > 1
                """,
                (run_id,),
            )
            duplicates = cursor.fetchall()
            assert len(duplicates) == 0, (
                f"Round {execution_round}: Found duplicate responses: {duplicates}"
            )

        # Final verification after all rounds
        run_row = _get_run_row(in_memory_db, run_id)
        assert run_row["status"] == "completed"


@pytest.mark.integration
class TestConcurrencyCorrectness:
    """Additional correctness tests for concurrency behavior."""

    def test_concurrency_2_correctness(self, in_memory_db):
        """
        Verify: concurrency=2 produces correct results.

        Tests a middle-ground concurrency level.
        """
        ctx = _setup_minimal_experiment(in_memory_db, num_questions=4)
        run_id = ctx["run_id"]

        mock_client = _make_mock_api_client_with_tracking(latency_ms=50)

        planner = Planner(in_memory_db)
        plan = planner.build_plan(ctx["experiment_name"], run_ids=[run_id])

        results = _execute_via_orchestrator(
            in_memory_db, plan, mock_client, max_concurrency=2
        )

        assert len(results) == 4
        assert all(r.status == "success" for r in results)
        assert _count_responses(in_memory_db, run_id) == 4

        run_row = _get_run_row(in_memory_db, run_id)
        assert run_row["status"] == "completed"

    def test_concurrency_with_multiple_variants(self, in_memory_db):
        """
        Verify: Concurrency works with multiple model variants.

        Steps:
        1. Create experiment with 2 variants and 2 questions
        2. Execute with concurrency=2
        3. Verify: 4 responses total (2 variants × 2 questions)
        4. Verify: Each variant has correct responses
        """
        exp_id = f"exp_{uuid.uuid4().hex[:8]}"
        experiment = Experiment(
            experiment_id=exp_id,
            name="multi-variant-exp",
            description="Test",
            config_json='{"SYSTEM_PROMPT": "Help.", "USER_PROMPT": "Answer: {question}"}',
            config_hash="abc",
        )
        ExperimentRepository(in_memory_db).save(experiment)

        # Add 2 variants
        variant_ids = []
        for model_id in ["openai/gpt-4", "anthropic/claude-3"]:
            variant_id = f"var_{uuid.uuid4().hex[:8]}"
            variant = ModelVariant(
                variant_id=variant_id,
                experiment_id=exp_id,
                model_id=model_id,
                variant_signature=model_id.replace("/", "_"),
                config='{}',
            )
            VariantRepository(in_memory_db).save(variant)
            variant_ids.append(variant_id)

        # Add 2 snapshots
        snapshot_ids = []
        for i in range(1, 3):
            snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
            payload = {
                "stem": f"Question {i}",
                "options": ["A", "B", "C", "D"],
                "answer_key": "B",
            }
            snapshot = QuestionSnapshot(
                snapshot_id=snapshot_id,
                experiment_id=exp_id,
                json_question_id=f"Q{i:02d}",
                question_position=i,
                question_payload=json.dumps(payload),
            )
            SnapshotRepository(in_memory_db).save(snapshot)
            snapshot_ids.append(snapshot_id)

        # Create run
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        run = Run(
            run_id=run_id,
            experiment_id=exp_id,
            status="pending",
            duration=0,
        )
        RunRepository(in_memory_db).save(run, config={"RUN_RESPONSES_SEED": 42})

        # Execute
        mock_client = _make_mock_api_client_with_tracking(latency_ms=50)
        planner = Planner(in_memory_db)
        plan = planner.build_plan("multi-variant-exp", run_ids=[run_id])

        # Plan should have 4 items (2 variants × 2 questions)
        plan_items = sum(len(pr.items) for pr in plan.runs)
        assert plan_items == 4

        results = _execute_via_orchestrator(
            in_memory_db, plan, mock_client, max_concurrency=2
        )

        assert len(results) == 4
        assert all(r.status == "success" for r in results)

        # Count responses
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM responses WHERE run_id = ? AND raw_response IS NOT NULL",
            (run_id,),
        )
        assert cursor.fetchone()[0] == 4

        # Verify both variants have responses
        for vid in variant_ids:
            cursor = in_memory_db.execute(
                "SELECT COUNT(*) FROM responses WHERE run_id = ? AND variant_id = ? AND raw_response IS NOT NULL",
                (run_id, vid),
            )
            count = cursor.fetchone()[0]
            assert count == 2, f"Variant {vid} should have 2 responses, got {count}"
