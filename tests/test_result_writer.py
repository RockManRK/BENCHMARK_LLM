"""Tests for result_writer module.

This module tests the ResultWriter component that persists ExecutionResults.
"""

import pytest
import json
from datetime import datetime
from pathlib import Path

from src.core.result_writer import ResultWriter, WriteResult
from src.core.execution_plan import (
    ExecutionPlan,
    ExecutionResult,
    PlanItem,
    PlanRun,
    PlanVariant,
    generate_plan_id,
)
from src.db.schema import DatabaseManager
from src.db.models import Experiment, Run, Model, ModelVariant, Question, QuestionSnapshot
from src.db.repository import (
    ExperimentRepository,
    RunRepository,
    ModelRepository,
    ModelVariantRepository,
    QuestionRepository,
    QuestionSnapshotRepository,
    RunModelRepository,
    ResponseRepository,
    ErrorRepository,
)


@pytest.fixture
def db_manager():
    """Create in-memory database for testing."""
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    yield db_manager
    db_manager.close()


@pytest.fixture
def writer(db_manager):
    """Create ResultWriter instance."""
    return ResultWriter(db_manager)


@pytest.fixture
def setup_test_plan(db_manager):
    """Set up test plan and database state."""
    # Create experiment
    experiment = Experiment(
        experiment_id="exp-test123",
        name="test_experiment",
        description="Test experiment",
        config_json=json.dumps({}),
        config_hash="testhash",
        system_prompt_template="You are helpful.",
        user_prompt_template="Answer the question.",
    )
    ExperimentRepository(db_manager).create(experiment)

    # Create run
    run = Run(
        run_id="run-test001",
        experiment_id="exp-test123",
        seed=42,
        started_at=datetime.now(),
        status="running",
    )
    RunRepository(db_manager).create(run)

    # Create model
    model = Model(
        model_id="openai/gpt-4",
        provider="OpenAI",
        model_name="GPT-4",
    )
    ModelRepository(db_manager).create(model)

    # Create variant
    variant = ModelVariant(
        variant_id="var-abc123",
        model_id="openai/gpt-4",
        reasoning_mode="off",
        reasoning_effort=None,
        reasoning_max_tokens=None,
        vision_enabled=False,
        structured_enabled=False,
        variant_signature="openai/gpt-4::reasoning=off::vision=false::structured=false",
    )
    ModelVariantRepository(db_manager).create(variant)

    # Associate variant with run
    RunModelRepository(db_manager).add("run-test001", "var-abc123", status="running")

    # Create question
    question = Question(
        question_id="Q001",
        stem="What is 2+2?",
        options_json=json.dumps({"A": "3", "B": "4", "C": "5", "D": "6"}),
        correct_answer="B",
        has_image=False,
        image_path=None,
        status="active",
    )
    QuestionRepository(db_manager).create(question)

    # Create snapshot
    question_json = json.dumps({
        "id": "Q001",
        "stem": "What is 2+2?",
        "options": {"A": "3", "B": "4", "C": "5", "D": "6"},
        "answer_key": "B",
    })
    snapshot_id = QuestionSnapshotRepository(db_manager).create_if_not_exists(
        experiment_id="exp-test123",
        question_id="Q001",
        question_json=question_json,
    )

    # Create execution plan
    plan_item = PlanItem(
        item_id="run-test001::var-abc123::1::it-1",
        run_id="run-test001",
        variant_id="var-abc123",
        model_id="openai/gpt-4",
        snapshot_id=snapshot_id,
        question_id="Q001",
        iteration_number=1,
        question_payload=json.loads(question_json),
    )

    plan_variant = PlanVariant(
        variant_id="var-abc123",
        model_id="openai/gpt-4",
        model_config={"reasoning_mode": "off"},
    )

    plan_run = PlanRun(
        run_id="run-test001",
        seed_effective=42,
        system_prompt="You are helpful.",
        user_prompt="Answer the question.",
        variants=[plan_variant],
        items=[plan_item],
    )

    plan = ExecutionPlan(
        plan_id=generate_plan_id("exp-test123", datetime(2026, 3, 18, 12, 0, 0)),
        created_at=datetime.now(),
        experiment_id="exp-test123",
        experiment_name="test_experiment",
        runs=[plan_run],
    )

    return {
        "plan": plan,
        "experiment": experiment,
        "run": run,
        "variant": variant,
        "question": question,
        "snapshot_id": snapshot_id,
    }


class TestWriteResult:
    """Tests for WriteResult dataclass."""

    def test_write_result_defaults(self):
        """Test WriteResult default values."""
        result = WriteResult()

        assert result.responses_written == 0
        assert result.errors_written == 0
        assert result.responses_skipped == 0
        assert result.errors_skipped == 0
        assert result.runs_updated == []


class TestResultWriterInit:
    """Tests for ResultWriter initialization."""

    def test_writer_init(self, db_manager):
        """Test ResultWriter initializes with repositories."""
        writer = ResultWriter(db_manager)

        assert writer.db_manager == db_manager
        assert writer._response_repo is not None
        assert writer._error_repo is not None
        assert writer._run_repo is not None
        assert writer._run_model_repo is not None


class TestWriteResults:
    """Tests for ResultWriter.write_results() method."""

    def test_write_success_results(self, writer, setup_test_plan):
        """Test writing successful execution results."""
        plan = setup_test_plan["plan"]

        # Create success result
        result = ExecutionResult(
            item_id="run-test001::var-abc123::1::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            status="success",
            response_text="The answer is B",
            selected_answer="B",
            is_correct=True,
            latency_ms=1200,
            input_tokens=50,
            output_tokens=10,
        )

        write_result = writer.write_results(plan, [result])

        assert write_result.responses_written == 1
        assert write_result.errors_written == 0
        assert write_result.responses_skipped == 0
        assert len(write_result.runs_updated) == 1

        # Verify response was persisted
        responses = ResponseRepository(writer.db_manager).get_by_run("run-test001")
        assert len(responses) == 1
        assert responses[0].question_id == "Q001"
        assert responses[0].selected_answer == "B"
        assert responses[0].is_correct is True

    def test_write_failure_results(self, writer, setup_test_plan):
        """Test writing failed execution results."""
        plan = setup_test_plan["plan"]

        # Create failure result
        result = ExecutionResult(
            item_id="run-test001::var-abc123::1::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            status="failure",
            response_text="",
            selected_answer=None,
            is_correct=None,
            latency_ms=100,
            input_tokens=0,
            output_tokens=0,
            error_type="TimeoutError",
            error_message="Request timed out",
        )

        write_result = writer.write_results(plan, [result])

        assert write_result.responses_written == 0
        assert write_result.errors_written == 1

        # Verify error was persisted
        errors = ErrorRepository(writer.db_manager).get_all()
        assert len(errors) == 1
        assert errors[0].question_id == "Q001"
        assert errors[0].error_type == "TimeoutError"

    def test_write_results_idempotency(self, writer, setup_test_plan):
        """Test that write_results is idempotent (same result twice)."""
        plan = setup_test_plan["plan"]

        # Create success result
        result = ExecutionResult(
            item_id="run-test001::var-abc123::1::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            status="success",
            response_text="The answer is B",
            selected_answer="B",
            is_correct=True,
            latency_ms=1200,
            input_tokens=50,
            output_tokens=10,
        )

        # Write first time
        write_result1 = writer.write_results(plan, [result])
        assert write_result1.responses_written == 1
        assert write_result1.responses_skipped == 0

        # Write second time (should skip)
        write_result2 = writer.write_results(plan, [result])
        assert write_result2.responses_written == 0
        assert write_result2.responses_skipped == 1

        # Verify only one response exists
        responses = ResponseRepository(writer.db_manager).get_by_run("run-test001")
        assert len(responses) == 1

    def test_update_run_status_completed(self, writer, setup_test_plan):
        """Test that run status is updated to completed when all succeed."""
        plan = setup_test_plan["plan"]

        result = ExecutionResult(
            item_id="run-test001::var-abc123::1::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            status="success",
            response_text="The answer is B",
            selected_answer="B",
            is_correct=True,
            latency_ms=1200,
            input_tokens=50,
            output_tokens=10,
        )

        writer.write_results(plan, [result])

        # Verify run status
        run = RunRepository(writer.db_manager).get_by_id("run-test001")
        assert run.status == "completed"

    def test_update_run_status_partial_failed(self, writer, setup_test_plan):
        """Test that run status is updated to partial_failed when some fail."""
        plan = setup_test_plan["plan"]

        # Add another item to the plan
        from src.core.execution_plan import PlanItem

        item2 = PlanItem(
            item_id="run-test001::var-abc123::2::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=2,
            question_id="Q002",
            iteration_number=1,
            question_payload={},
        )
        plan.runs[0].items.append(item2)

        # One success, one failure
        result1 = ExecutionResult(
            item_id="run-test001::var-abc123::1::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            status="success",
            response_text="B",
            selected_answer="B",
            is_correct=True,
            latency_ms=1200,
            input_tokens=50,
            output_tokens=10,
        )

        result2 = ExecutionResult(
            item_id="run-test001::var-abc123::2::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=2,
            question_id="Q002",
            iteration_number=1,
            status="failure",
            response_text="",
            selected_answer=None,
            is_correct=None,
            latency_ms=100,
            input_tokens=0,
            output_tokens=0,
            error_type="TimeoutError",
            error_message="Timeout",
        )

        writer.write_results(plan, [result1, result2])

        # Verify run status
        run = RunRepository(writer.db_manager).get_by_id("run-test001")
        assert run.status == "partial_failed"

    def test_update_run_model_status(self, writer, setup_test_plan):
        """Test that run_model status is updated."""
        plan = setup_test_plan["plan"]

        result = ExecutionResult(
            item_id="run-test001::var-abc123::1::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            status="success",
            response_text="B",
            selected_answer="B",
            is_correct=True,
            latency_ms=1200,
            input_tokens=50,
            output_tokens=10,
        )

        writer.write_results(plan, [result])

        # Verify run_model status
        run_model = RunModelRepository(writer.db_manager).get_by_run_and_variant(
            "run-test001", "var-abc123"
        )
        assert run_model.status == "completed"


class TestResponseExists:
    """Tests for idempotency check methods."""

    def test_response_exists_true(self, writer, setup_test_plan, db_manager):
        """Test _response_exists returns True for existing response."""
        # Create a response
        from src.db.models import Response
        response = Response(
            run_id="run-test001",
            snapshot_id=1,
            question_id="Q001",
            model_id="openai/gpt-4",
            variant_id="var-abc123",
            iteration=1,
            selected_answer="B",
            response_text="Test",
            is_correct=True,
        )
        ResponseRepository(db_manager).create(response)

        # Create result with same key
        result = ExecutionResult(
            item_id="run-test001::var-abc123::1::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            status="success",
            response_text="B",
            selected_answer="B",
            is_correct=True,
            latency_ms=1200,
            input_tokens=50,
            output_tokens=10,
        )

        assert writer._response_exists(result) is True

    def test_response_exists_false(self, writer, setup_test_plan):
        """Test _response_exists returns False for non-existing response."""
        result = ExecutionResult(
            item_id="run-test001::var-abc123::1::it-1",
            run_id="run-test001",
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            status="success",
            response_text="B",
            selected_answer="B",
            is_correct=True,
            latency_ms=1200,
            input_tokens=50,
            output_tokens=10,
        )

        assert writer._response_exists(result) is False
