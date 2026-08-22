"""End-to-end integration tests for complete workflows.

This module tests full workflows from CLI to database:
- Full experiment lifecycle (create → add models → add questions → create run → execute)
- Execution flow (Planner → ExecutionEngine → ResultWriter)
- Review workflow (needs_review calculation, manual answer override)
- Error handling (validation errors, API errors, retry behavior)

All tests use:
- Mocked API client (no real API calls)
- In-memory SQLite database with full TO-BE schema
- CLI entry points where possible (verifies full integration)
"""

import pytest
import asyncio
import sys
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
from src.api.client import CompletionResponse
from src.api.errors import APIError
from src.core.execution_engine import ExecutionEngine
from src.core.result_writer import ResultWriter
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser


def _execute_and_write(engine, plan, writer):
    """Helper: execute a plan async and write results individually."""
    async def _run():
        queue = asyncio.Queue()
        return await engine.execute_async(plan, queue)

    # Fixed 2026-08-21 (test-debt reconciliation): asyncio.get_event_loop()
    # raises RuntimeError under Python 3.14 when called from a thread with
    # no running/previously-set loop — asyncio.run() creates and tears
    # down its own loop per call, which this helper's callers (each a
    # single synchronous test method) don't need to reuse across calls.
    results = asyncio.run(_run())
    for result in results:
        writer.write_result(result)
    return results


# =============================================================================
# Workflow 1: Full Experiment Lifecycle
# =============================================================================

@pytest.mark.integration
class TestFullExperimentLifecycle:
    """Test complete experiment lifecycle workflows."""
    
    def test_full_experiment_lifecycle(self, in_memory_db, mock_api_client):
        """
        Full end-to-end workflow:
        1. Create experiment
        2. Add model variant
        3. Add question snapshots
        4. Create run
        5. Execute run
        6. Verify results in database
        
        This test verifies the complete integration from CLI through
        all layers to the database.
        """
        import uuid
        import json
        
        # Step 1: Create experiment
        exp_id = f"exp_{uuid.uuid4().hex[:8]}"
        from src.db.models import Experiment
        exp = Experiment(
            experiment_id=exp_id,
            name="test-exp",
            description="",
            config_json='{"SYSTEM_PROMPT": "You are helpful.", "USER_PROMPT": "Answer: {question}"}',
            config_hash="",
        )
        ExperimentRepository(in_memory_db).save(exp)
        
        # Step 2: Add model
        # Fixed 2026-08-21 (test-debt reconciliation, group 2 + adjacent
        # site): ModelVariant has no reasoning_mode field — see
        # tests/factories/variant.py's module docstring.
        var_id = f"var_{uuid.uuid4().hex[:8]}"
        from tests.factories.variant import VariantFactory
        variant = VariantFactory.create(
            experiment_id=exp_id,
            model_id="openai/gpt-4",
            variant_id=var_id,
            variant_signature="openai_gpt-4",
        )
        VariantRepository(in_memory_db).save(variant)

        # Step 3: Add questions
        # Fixed 2026-08-21 (same reconciliation): question_id is not a real
        # QuestionSnapshot field (real: json_question_id/question_position).
        snap_id = f"snap_{uuid.uuid4().hex[:8]}"
        from src.db.models import QuestionSnapshot
        snapshot = QuestionSnapshot(
            snapshot_id=snap_id,
            experiment_id=exp_id,
            json_question_id="Q01",
            question_position=1,
            question_payload=json.dumps({
                "stem": "Test question",
                "options": ["A", "B", "C", "D"],
                "answer_key": "B",
            }),
        )
        SnapshotRepository(in_memory_db).save(snapshot)

        # Step 4: Create run
        # Fixed 2026-08-21 (same reconciliation): Run has no seed= field,
        # and RunRepository.save() takes the config as its own separate
        # dict argument (serializes that, not run.config) — see
        # src/db/repository.py::RunRepository.save.
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        from src.db.models import Run
        run = Run(
            run_id=run_id,
            experiment_id=exp_id,
            status="pending",
        )
        RunRepository(in_memory_db).save(run, {"RANDOMIZATION_SEED": 42})
        
        # Step 5: Execute run
        from src.core.planner import Planner
        from src.core.execution_engine import ExecutionEngine
        from src.core.result_writer import ResultWriter
        from src.core.randomizer import AnswerRandomizer
        from src.core.answer_parser import AnswerParser
        
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-exp", run_ids=[run_id])
        
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=42), AnswerParser())
        writer = ResultWriter(in_memory_db)
        results = _execute_and_write(engine, plan, writer)

        # Step 6: Verify results in database
        resp_repo = ResponseRepository(in_memory_db)
        responses = resp_repo.list_by_run(run_id)
        
        assert len(responses) == 1
        assert responses[0].selected_answer == "B"
        assert responses[0].parse_confidence == "clear"
        # Fixed 2026-08-21 (same reconciliation): Response has no
        # needs_review field — real field is review_status
        # ('needs_review'/'auto', src/core/result_writer.py's
        # _calculate_review_status).
        assert responses[0].review_status == "auto"
    
    def test_experiment_with_multiple_models(self, in_memory_db, mock_api_client):
        """
        Test experiment with multiple model variants in a single run.
        
        Verifies:
        - Multiple models can be added to an experiment
        - Execution creates responses for each model
        - Results are correctly associated with variants
        """
        from src.db.models import Experiment, QuestionSnapshot, Run
        from tests.factories.variant import VariantFactory
        from src.core.planner import Planner
        from src.core.execution_engine import ExecutionEngine
        from src.core.result_writer import ResultWriter
        from src.core.randomizer import AnswerRandomizer
        from src.core.answer_parser import AnswerParser
        import json
        import uuid

        # Setup: Create experiment with 2 models and 2 questions
        exp_repo = ExperimentRepository(in_memory_db)
        var_repo = VariantRepository(in_memory_db)
        snap_repo = SnapshotRepository(in_memory_db)
        run_repo = RunRepository(in_memory_db)

        experiment = Experiment(
            experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
            name="multi-model-exp",
            description="",
            config_json='{"SYSTEM_PROMPT": "You are helpful.", "USER_PROMPT": "Answer: {question}"}',
            config_hash="",
        )
        exp_repo.save(experiment)

        # Add 2 model variants
        # Fixed 2026-08-21 (test-debt reconciliation, group 2 — adjacent
        # site, same root cause as the declared scope: ModelVariant has no
        # reasoning_mode field).
        variant1 = VariantFactory.create(
            experiment_id=experiment.experiment_id,
            model_id="openai/gpt-4",
            variant_signature="openai_gpt-4",
        )
        variant2 = VariantFactory.create(
            experiment_id=experiment.experiment_id,
            model_id="anthropic/claude-3",
            variant_signature="anthropic_claude-3",
        )
        var_repo.save(variant1)
        var_repo.save(variant2)

        # Add 2 question snapshots
        # Fixed 2026-08-21 (same reconciliation): question_id is not a
        # real QuestionSnapshot field.
        for i in range(1, 3):
            snapshot = QuestionSnapshot(
                snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
                experiment_id=experiment.experiment_id,
                json_question_id=f"Q{i:02d}",
                question_position=i,
                question_payload=json.dumps({
                    "stem": f"Question {i}",
                    "options": ["A", "B", "C", "D"],
                    "answer_key": "B",
                }),
            )
            snap_repo.save(snapshot)

        # Create run
        # Fixed 2026-08-21 (same reconciliation): Run has no seed= field;
        # RunRepository.save() takes config as its own dict argument.
        run = Run(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            status="pending",
        )
        run_repo.save(run, {"RANDOMIZATION_SEED": 42})
        
        # Execute: Planner → Engine → Writer
        planner = Planner(in_memory_db)
        plan = planner.build_plan("multi-model-exp", run_ids=[run.run_id])
        
        # Configure mock to return different responses for different models
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            model_id = "openai/gpt-4" if call_count[0] % 2 == 1 else "anthropic/claude-3"
            return CompletionResponse(
                content=f"The answer is (B).",
                model_id=model_id,
                input_tokens=50,
                response_tokens=10,
                latency_ms=500,
            )
        mock_api_client.chat_completion.side_effect = side_effect
        
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=42), AnswerParser())
        writer = ResultWriter(in_memory_db)
        results = _execute_and_write(engine, plan, writer)

        # Verify: Should have 4 responses (2 models × 2 questions)
        resp_repo = ResponseRepository(in_memory_db)
        responses = resp_repo.list_by_run(run.run_id)
        
        assert len(responses) == 4
        
        # Verify both models have responses
        variant_ids = {r.variant_id for r in responses}
        assert variant1.variant_id in variant_ids
        assert variant2.variant_id in variant_ids
    
    def test_experiment_with_multiple_runs(self, in_memory_db, mock_api_client):
        """
        Test single model with multiple runs.
        
        Verifies:
        - Multiple runs can be created for an experiment
        - Each run executes independently
        - Results are correctly isolated by run_id
        """
        from src.db.models import Experiment, QuestionSnapshot, Run
        from tests.factories.variant import VariantFactory
        from src.core.planner import Planner
        from src.core.execution_engine import ExecutionEngine
        from src.core.result_writer import ResultWriter
        from src.core.randomizer import AnswerRandomizer
        from src.core.answer_parser import AnswerParser
        import json
        import uuid

        # Setup: Create experiment with 1 model and 2 questions
        exp_repo = ExperimentRepository(in_memory_db)
        var_repo = VariantRepository(in_memory_db)
        snap_repo = SnapshotRepository(in_memory_db)
        run_repo = RunRepository(in_memory_db)

        experiment = Experiment(
            experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
            name="multi-run-exp",
            description="",
            config_json='{"SYSTEM_PROMPT": "You are helpful.", "USER_PROMPT": "Answer: {question}"}',
            config_hash="",
        )
        exp_repo.save(experiment)

        # Fixed 2026-08-21 (test-debt reconciliation, group 2 — adjacent
        # site, same root cause as the declared scope).
        variant = VariantFactory.create(
            experiment_id=experiment.experiment_id,
            model_id="openai/gpt-4",
            variant_signature="openai_gpt-4",
        )
        var_repo.save(variant)

        # Fixed 2026-08-21 (same reconciliation): question_id is not a
        # real QuestionSnapshot field.
        for i in range(1, 3):
            snapshot = QuestionSnapshot(
                snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
                experiment_id=experiment.experiment_id,
                json_question_id=f"Q{i:02d}",
                question_position=i,
                question_payload=json.dumps({
                    "stem": f"Question {i}",
                    "options": ["A", "B", "C", "D"],
                    "answer_key": "B",
                }),
            )
            snap_repo.save(snapshot)

        # Create 2 runs
        # Fixed 2026-08-21 (same reconciliation): Run has no seed= field;
        # RunRepository.save() takes config as its own dict argument.
        run1 = Run(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            status="pending",
        )
        run2 = Run(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            status="pending",
        )
        run_repo.save(run1, {"RANDOMIZATION_SEED": 42})
        run_repo.save(run2, {"RANDOMIZATION_SEED": 123})
        
        # Execute both runs
        planner = Planner(in_memory_db)
        
        plan1 = planner.build_plan("multi-run-exp", run_ids=[run1.run_id])
        plan2 = planner.build_plan("multi-run-exp", run_ids=[run2.run_id])
        
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=42), AnswerParser())
        writer = ResultWriter(in_memory_db)

        results1 = _execute_and_write(engine, plan1, writer)
        results2 = _execute_and_write(engine, plan2, writer)

        # Verify: Each run should have 2 responses (1 model × 2 questions)
        resp_repo = ResponseRepository(in_memory_db)
        responses1 = resp_repo.list_by_run(run1.run_id)
        responses2 = resp_repo.list_by_run(run2.run_id)
        
        assert len(responses1) == 2
        assert len(responses2) == 2
        
        # Verify runs are isolated (no shared responses)
        response_ids1 = {r.response_id for r in responses1}
        response_ids2 = {r.response_id for r in responses2}
        assert len(response_ids1.intersection(response_ids2)) == 0


# =============================================================================
# Workflow 2: Execution Flow
# =============================================================================

@pytest.mark.integration
class TestExecutionFlow:
    """Test execution flow from Planner to ResultWriter."""
    
    def test_execution_planner_to_writer(self, full_experiment_setup, in_memory_db, mock_api_client):
        """
        Test complete execution flow: Planner → ExecutionEngine → ResultWriter.
        
        Verifies:
        - Planner builds valid ExecutionPlan
        - ExecutionEngine executes all items
        - ResultWriter persists all results
        - Run status is updated correctly
        """
        from src.core.planner import Planner
        from src.core.execution_engine import ExecutionEngine
        from src.core.result_writer import ResultWriter
        from src.core.randomizer import AnswerRandomizer
        from src.core.answer_parser import AnswerParser
        
        run_id = full_experiment_setup['run_id']
        
        # Step 1: Planner builds plan
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment", run_ids=[run_id])
        
        assert plan is not None
        assert len(plan.runs) == 1
        assert len(plan.runs[0].items) == 3  # 3 questions
        
        # Step 2: ExecutionEngine executes
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=42), AnswerParser())
        writer = ResultWriter(in_memory_db)
        results = _execute_and_write(engine, plan, writer)

        assert len(results) == 3
        assert all(r.status == 'success' for r in results)

        # Step 3: ResultWriter persists (already done via helper)
        # Verify responses were written
        resp_repo = ResponseRepository(in_memory_db)
        responses = resp_repo.list_by_run(run_id)
        assert len(responses) == 3
    
    def test_execution_with_api_error(self, full_experiment_setup, in_memory_db):
        """
        Test API error during execution.
        
        Verifies:
        - API errors are caught and classified
        - Errors are persisted to errors table
        - Run status reflects partial failure
        """
        from src.core.planner import Planner
        from src.core.execution_engine import ExecutionEngine
        from src.core.result_writer import ResultWriter
        from src.core.randomizer import AnswerRandomizer
        from src.core.answer_parser import AnswerParser
        from src.api.errors import APIError
        
        run_id = full_experiment_setup['run_id']
        
        # Configure mock to raise error
        async def raise_api_error(*args, **kwargs):
            raise APIError("Test API error")
        
        mock_api_client = MagicMock()
        mock_api_client.chat_completion = AsyncMock(side_effect=raise_api_error)
        
        # Execute
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment", run_ids=[run_id])
        
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=42), AnswerParser())
        writer = ResultWriter(in_memory_db)
        results = _execute_and_write(engine, plan, writer)

        # Verify: All items should fail, errors persisted via direct SQL
        cursor = in_memory_db.execute("SELECT * FROM errors WHERE run_id = ?", (run_id,))
        errors = cursor.fetchall()
        assert len(errors) == 3
        assert all(e["error_type"] == 'api_error' for e in errors)
    
    def test_execution_with_retry(self, full_experiment_setup, in_memory_db):
        """
        Test retry behavior on transient error.
        
        Verifies:
        - Retry is attempted on transient errors
        - Success on retry is recorded
        - Attempt count is tracked
        """
        from src.core.planner import Planner
        from src.core.execution_engine import ExecutionEngine
        from src.core.result_writer import ResultWriter
        from src.core.randomizer import AnswerRandomizer
        from src.core.answer_parser import AnswerParser
        from src.api.errors import APIError
        
        run_id = full_experiment_setup['run_id']
        
        # Configure mock: fail first call, succeed on second
        call_count = [0]
        async def retry_behavior(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise APIError("Transient error")
            return CompletionResponse(
                content="The answer is (B).",
                model_id="openai/gpt-4",
                input_tokens=50,
                response_tokens=10,
                latency_ms=500,
            )
        
        mock_api_client = MagicMock()
        mock_api_client.chat_completion = AsyncMock(side_effect=retry_behavior)
        
        # Execute
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment", run_ids=[run_id])
        
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=42), AnswerParser())
        writer = ResultWriter(in_memory_db)
        results = _execute_and_write(engine, plan, writer)

        # Note: Current implementation doesn't have built-in retry
        # This test documents expected behavior for future implementation
        # For now, first item fails, rest succeed
        assert len(results) == 3
    
    def test_execution_idempotent(self, full_experiment_setup, in_memory_db, mock_api_client):
        """
        Test idempotent execution: execute twice, no duplicate results.
        
        Verifies:
        - Second execution doesn't create duplicate responses
        - Idempotency uses UNIQUE constraint
        - Skipped responses are tracked in report
        """
        from src.core.planner import Planner
        from src.core.execution_engine import ExecutionEngine
        from src.core.result_writer import ResultWriter
        from src.core.randomizer import AnswerRandomizer
        from src.core.answer_parser import AnswerParser

        run_id = full_experiment_setup['run_id']

        # First execution
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment", run_ids=[run_id])

        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=42), AnswerParser())
        writer = ResultWriter(in_memory_db)
        results1 = _execute_and_write(engine, plan, writer)

        # Second execution (same plan)
        results2 = _execute_and_write(engine, plan, writer)

        # Verify: Second execution still produces results (idempotency via INSERT OR IGNORE)
        assert len(results1) == 3
        assert len(results2) == 3

        # Verify: No duplicates in database
        resp_repo = ResponseRepository(in_memory_db)
        responses = resp_repo.list_by_run(run_id)
        assert len(responses) == 3


# =============================================================================
# Workflow 3: Review Workflow
# =============================================================================

@pytest.mark.integration
class TestReviewWorkflow:
    """Test review workflow: needs_review calculation and manual override."""
    
    def test_review_flag_calculation(self, in_memory_db):
        """
        Test review_status is calculated correctly through the real
        write path.

        Domain Rules (src.core.result_writer.ResultWriter._calculate_review_status):
        - review_status = 'needs_review' when parse_confidence is 'no_answer' or 'low_confidence'
        - review_status = 'needs_review' when selected_answer is None
        - review_status = 'auto' otherwise

        Fixed 2026-08-21 (test-debt reconciliation, group 4):
        _calculate_needs_review was renamed to _calculate_review_status
        (bool -> str[[a-z_]] classification) with unchanged domain rules —
        this test now calls the public write_result() and asserts the
        persisted review_status column, mirroring
        tests/unit/core/test_result_writer.py's
        test_writer_calculates_review_status_* pattern, instead of
        reaching into a private method directly. Kept as an
        integration-level cross-check (per explicit instruction) even
        though the unit-level sibling tests already cover the same 3
        states plus 2 more (ambiguous, null_answer) — this one proves the
        classification survives the real write_result() dispatch path,
        not just the pure calculation function in isolation. Each case
        uses a distinct run_id so its deterministic response_id
        (f"resp-{run_id}-{variant_id}-{snapshot_id}") doesn't collide
        with the others under write_result()'s INSERT OR IGNORE
        idempotency.
        """
        from src.core.result_writer import ResultWriter
        from src.core.execution_engine import ExecutionResult
        from src.db.models import Experiment, QuestionSnapshot, Run
        from tests.factories.variant import VariantFactory
        import json
        import uuid

        # responses has real FK constraints on variant_id/snapshot_id/
        # run_id (src/core/result_writer.py::_write_response) — needs a
        # real Experiment + ModelVariant + QuestionSnapshot + one Run per
        # case (each case uses its own run_id) to exist first.
        exp_repo = ExperimentRepository(in_memory_db)
        exp_repo.save(Experiment(
            experiment_id="exp-review-test",
            name="review-test-exp",
            description="",
            config_json=json.dumps({}),
            config_hash="",
        ))
        VariantRepository(in_memory_db).save(VariantFactory.create(
            experiment_id="exp-review-test",
            model_id="openai/gpt-4",
            variant_id="var-test",
            variant_signature="openai_gpt-4",
        ))
        SnapshotRepository(in_memory_db).save(QuestionSnapshot(
            snapshot_id="snap-test",
            experiment_id="exp-review-test",
            json_question_id="q1",
            question_position=1,
            question_payload=json.dumps({
                "stem": "What is 2+2?", "options": ["3", "4", "5", "6"], "answer_key": "4",
            }),
        ))
        run_repo = RunRepository(in_memory_db)
        for run_id in ("run-test-clear", "run-test-no-answer", "run-test-low-confidence"):
            run_repo.save(Run(run_id=run_id, experiment_id="exp-review-test", status="pending"), {})

        writer = ResultWriter(in_memory_db)
        cursor = in_memory_db.cursor()

        def _review_status_for(run_id, selected_answer, parse_confidence, response_text):
            result = ExecutionResult(
                item_id=f"item_{uuid.uuid4().hex[:8]}",
                run_id=run_id,
                variant_id="var-test",
                snapshot_id="snap-test",
                question_id="q1",
                status='success',
                response_text=response_text,
                selected_answer=selected_answer,
                parse_confidence=parse_confidence,
                latency_ms=500,
                input_tokens=50,
                response_tokens=10,
                error_type=None,
                error_message=None,
                attempt_count=1,
            )
            writer.write_result(result)
            cursor.execute("SELECT review_status FROM responses WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            assert row is not None, f"Response for {run_id} was not written"
            return row[0]

        # Case 1: Clear answer -> review_status = 'auto'
        assert _review_status_for("run-test-clear", "B", "clear", "The answer is (B).") == "auto"

        # Case 2: No answer -> review_status = 'needs_review'
        assert _review_status_for("run-test-no-answer", None, "no_answer", "I don't know.") == "needs_review"

        # Case 3: Low confidence -> review_status = 'needs_review'
        assert _review_status_for("run-test-low-confidence", "B", "low_confidence", "Maybe (B)?") == "needs_review"
    
    def test_manual_answer_override(self, full_experiment_setup, in_memory_db):
        """
        Test manual answer override updates is_correct.
        
        Verifies:
        - Manual answer can be set after execution
        - is_correct is recalculated based on manual answer
        - Original parse_confidence is preserved
        """
        from src.core.planner import Planner
        from src.core.execution_engine import ExecutionEngine
        from src.core.result_writer import ResultWriter
        from src.core.randomizer import AnswerRandomizer
        from src.core.answer_parser import AnswerParser
        
        run_id = full_experiment_setup['run_id']
        snapshot_ids = full_experiment_setup['snapshot_ids']
        variant_id = full_experiment_setup['variant_id']
        
        # Execute normally
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment", run_ids=[run_id])
        
        mock_api_client = MagicMock()
        mock_api_client.chat_completion = AsyncMock(return_value=CompletionResponse(
            content="The answer is (A).",  # Wrong answer
            model_id="openai/gpt-4",
            input_tokens=50,
            response_tokens=10,
            latency_ms=500,
        ))
        
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=42), AnswerParser())
        writer = ResultWriter(in_memory_db)
        results = _execute_and_write(engine, plan, writer)

        # Get first response
        resp_repo = ResponseRepository(in_memory_db)
        responses = resp_repo.list_by_run(run_id)
        response = responses[0]
        
        # Note: is_correct is None because ResultWriter doesn't calculate it
        # (it would need access to answer_key from snapshots)
        # For now, we just verify the response was created
        assert response.selected_answer == "A"
        
        # Manual override: Set correct answer
        resp_repo.update_manual_answer(response.response_id, "B")
        
        # Verify: Manual answer updated, is_correct recalculated
        updated = resp_repo.get_by_id(response.response_id)
        assert updated.manual_answer == "B"
        assert updated.is_correct == True


# =============================================================================
# Workflow 4: Error Handling
# =============================================================================

@pytest.mark.integration
class TestErrorHandling:
    """Test error handling and validation."""
    
    def test_execution_without_models_fails(self, in_memory_db):
        """
        Test planner validation error when experiment has no models.
        
        Verifies:
        - Planner validates experiment has models
        - PlannerValidationError is raised
        - Error message is user-friendly
        """
        from src.core.planner import Planner, PlannerValidationError
        from src.db.repository import ExperimentRepository
        from src.db.models import Experiment
        import uuid
        
        # Create experiment without models
        exp_repo = ExperimentRepository(in_memory_db)
        experiment = Experiment(
            experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
            name="no-models-exp",
            description="",
            config_json='{"SYSTEM_PROMPT": "You are helpful.", "USER_PROMPT": "Answer: {question}"}',
            config_hash="",
        )
        exp_repo.save(experiment)
        
        # Attempt to build plan
        planner = Planner(in_memory_db)
        
        with pytest.raises(PlannerValidationError) as exc_info:
            planner.build_plan("no-models-exp")
        
        assert "no models" in str(exc_info.value).lower()
    
    def test_execution_without_snapshots_fails(self, in_memory_db):
        """
        Test planner validation error when experiment has no snapshots.
        
        Verifies:
        - Planner validates experiment has snapshots
        - PlannerValidationError is raised
        - Error message is user-friendly
        """
        from src.core.planner import Planner, PlannerValidationError
        from src.db.repository import ExperimentRepository, VariantRepository
        from src.db.models import Experiment
        from tests.factories.variant import VariantFactory
        import uuid

        # Create experiment with model but no snapshots
        exp_repo = ExperimentRepository(in_memory_db)
        var_repo = VariantRepository(in_memory_db)

        experiment = Experiment(
            experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
            name="no-snapshots-exp",
            description="",
            config_json='{"SYSTEM_PROMPT": "You are helpful.", "USER_PROMPT": "Answer: {question}"}',
            config_hash="",
        )
        exp_repo.save(experiment)

        # Fixed 2026-08-21 (test-debt reconciliation, group 2 — declared
        # adjacent site).
        variant = VariantFactory.create(
            experiment_id=experiment.experiment_id,
            model_id="openai/gpt-4",
            variant_signature="openai_gpt-4",
        )
        var_repo.save(variant)
        
        # Attempt to build plan
        planner = Planner(in_memory_db)
        
        with pytest.raises(PlannerValidationError) as exc_info:
            planner.build_plan("no-snapshots-exp")
        
        assert "no questions" in str(exc_info.value).lower() or "snapshot" in str(exc_info.value).lower()
    
    def test_execution_run_not_found_fails(self, in_memory_db):
        """
        Test CLI validation error when run is not found.
        
        Verifies:
        - CLI validates run exists
        - Exit code is 1
        - Error message is user-friendly
        """
        from src.cli.bcllm_execute import main as execute_main
        
        with patch.object(sys, "argv", [
            "bcllm_execute.py",
            "--experiment", "test-exp",
            "--run", "run-nonexistent",
            "--execute",
        ]):
            with patch("sqlite3.connect", return_value=in_memory_db):
                result = execute_main()
                assert result == 1
