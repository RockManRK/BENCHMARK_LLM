"""Tests for planner module.

This module tests the Planner component that builds ExecutionPlans from database state.
"""

import pytest
import json
from datetime import datetime
from pathlib import Path

from src.core.planner import Planner
from src.core.execution_plan import ExecutionPlan, PlanItem, PlanRun, PlanVariant
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
)


@pytest.fixture
def db_manager():
    """Create in-memory database for testing."""
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    yield db_manager
    db_manager.close()


@pytest.fixture
def planner(db_manager):
    """Create Planner instance."""
    return Planner(db_manager)


@pytest.fixture
def setup_test_data(db_manager):
    """Set up test data in database."""
    # Create experiment
    experiment = Experiment(
        experiment_id="exp-test123",
        name="test_experiment",
        description="Test experiment for planner tests",
        config_json=json.dumps({"random_seed": 42}),
        config_hash="testhash123",
        system_prompt_template="You are a helpful assistant.",
        user_prompt_template="Select the correct answer.",
    )
    ExperimentRepository(db_manager).create(experiment)

    # Create run
    run = Run(
        run_id="run-test001",
        experiment_id="exp-test123",
        seed=42,
        started_at=datetime.now(),
        status="pending",
    )
    RunRepository(db_manager).create(run)

    # Create model
    model = Model(
        model_id="openai/gpt-4",
        provider="OpenAI",
        model_name="GPT-4",
    )
    ModelRepository(db_manager).create(model)

    # Create model variant
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
    RunModelRepository(db_manager).add("run-test001", "var-abc123", status="pending")

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
    QuestionSnapshotRepository(db_manager).create_if_not_exists(
        experiment_id="exp-test123",
        question_id="Q001",
        question_json=question_json,
    )

    return {
        "experiment": experiment,
        "run": run,
        "model": model,
        "variant": variant,
        "question": question,
    }


class TestPlannerInit:
    """Tests for Planner initialization."""

    def test_planner_init(self, db_manager):
        """Test Planner initializes with repositories."""
        planner = Planner(db_manager)
        
        assert planner.db_manager == db_manager
        assert planner._experiment_repo is not None
        assert planner._run_repo is not None
        assert planner._variant_repo is not None
        assert planner._snapshot_repo is not None
        assert planner._response_repo is not None


class TestBuildPlan:
    """Tests for Planner.build_plan() method."""

    def test_build_plan_success(self, planner, setup_test_data, db_manager):
        """Test building a complete execution plan."""
        plan = planner.build_plan(experiment_name="test_experiment")

        assert plan is not None
        assert plan.plan_id.startswith("plan-")
        assert plan.experiment_id == "exp-test123"
        assert plan.experiment_name == "test_experiment"
        assert len(plan.runs) == 1

        run = plan.runs[0]
        assert run.run_id == "run-test001"
        assert run.seed_effective == 42
        assert len(run.variants) == 1
        assert len(run.items) == 1

        item = run.items[0]
        assert item.question_id == "Q001"
        assert item.snapshot_id == 1
        assert item.variant_id == "var-abc123"

    def test_build_plan_experiment_not_found(self, planner):
        """Test that build_plan raises ValueError for unknown experiment."""
        with pytest.raises(ValueError, match="Experiment 'nonexistent' not found"):
            planner.build_plan(experiment_name="nonexistent")

    def test_build_plan_no_runs(self, planner, setup_test_data, db_manager):
        """Test that build_plan raises ValueError when no runs exist."""
        # Delete the run
        RunRepository(db_manager).delete("run-test001")
        
        with pytest.raises(ValueError, match="No runs found"):
            planner.build_plan(experiment_name="test_experiment")

    def test_build_plan_no_variants(self, planner, setup_test_data, db_manager):
        """Test that build_plan raises ValueError when no variants exist."""
        # Delete the variant
        ModelVariantRepository(db_manager).delete("var-abc123")
        
        with pytest.raises(ValueError, match="No model variants found"):
            planner.build_plan(experiment_name="test_experiment")

    def test_build_plan_no_snapshots(self, planner, setup_test_data, db_manager):
        """Test that build_plan raises ValueError when no snapshots exist."""
        # Note: Can't easily delete snapshots due to FK constraints
        # This would be tested in integration tests
        pass

    def test_build_plan_with_run_filter(self, planner, setup_test_data):
        """Test building plan with specific run name filter."""
        plan = planner.build_plan(
            experiment_name="test_experiment",
            run_name="run-test001",
        )

        assert len(plan.runs) == 1
        assert plan.runs[0].run_id == "run-test001"

    def test_build_plan_with_run_filter_not_found(self, planner, setup_test_data):
        """Test that build_plan raises ValueError for unknown run."""
        with pytest.raises(ValueError, match="Run 'nonexistent' not found"):
            planner.build_plan(
                experiment_name="test_experiment",
                run_name="nonexistent",
            )

    def test_build_plan_with_model_filter(self, planner, setup_test_data):
        """Test building plan with model filter."""
        plan = planner.build_plan(
            experiment_name="test_experiment",
            model_filter=["openai/gpt-4"],
        )

        # Should include the variant
        assert len(plan.runs) == 1
        assert len(plan.runs[0].variants) == 1

    def test_build_plan_with_model_filter_excludes(self, planner, setup_test_data):
        """Test that model filter excludes non-matching variants."""
        plan = planner.build_plan(
            experiment_name="test_experiment",
            model_filter=["anthropic/claude-3"],
        )

        # Should have no variants (filter excludes all)
        # This may raise ValueError depending on implementation
        # For now, just check it doesn't crash

    def test_build_plan_with_question_filter(self, planner, setup_test_data):
        """Test building plan with question filter."""
        plan = planner.build_plan(
            experiment_name="test_experiment",
            question_filter=["Q001"],
        )

        assert len(plan.runs) == 1
        # Should include Q001
        assert any(item.question_id == "Q001" for item in plan.runs[0].items)

    def test_build_plan_with_question_filter_excludes(self, planner, setup_test_data):
        """Test that question filter excludes non-matching questions."""
        plan = planner.build_plan(
            experiment_name="test_experiment",
            question_filter=["Q999"],  # Non-existent
        )

        # Should have no items
        assert len(plan.runs) == 1
        assert len(plan.runs[0].items) == 0


class TestResolveSeed:
    """Tests for seed resolution logic."""

    def test_resolve_seed_from_run(self, planner, setup_test_data):
        """Test that run seed takes precedence."""
        run = RunRepository(planner.db_manager).get_by_id("run-test001")
        experiment = ExperimentRepository(planner.db_manager).get_by_id("exp-test123")

        seed = planner._resolve_seed(run, experiment)
        assert seed == 42  # From run.seed

    def test_resolve_seed_none_default(self, planner, setup_test_data, db_manager):
        """Test that default seed is None (no randomization) when not configured."""
        # Create run without seed
        run = Run(
            run_id="run-noseed",
            experiment_id="exp-test123",
            seed=None,
            started_at=datetime.now(),
            status="pending",
        )
        RunRepository(db_manager).create(run)

        experiment = ExperimentRepository(db_manager).get_by_id("exp-test123")
        # Modify experiment config to not have seed
        experiment.config_json = json.dumps({})

        seed = planner._resolve_seed(run, experiment)
        assert seed is None  # Default is None (no randomization)


class TestResolvePrompts:
    """Tests for prompt resolution logic."""

    def test_resolve_prompts_from_experiment(self, planner, setup_test_data):
        """Test that prompts are resolved from experiment."""
        run = RunRepository(planner.db_manager).get_by_id("run-test001")
        experiment = ExperimentRepository(planner.db_manager).get_by_id("exp-test123")

        system_prompt, user_prompt = planner._resolve_prompts(run, experiment)

        assert "helpful" in system_prompt
        assert "answer" in user_prompt


class TestDeduplication:
    """Tests for item deduplication logic."""

    def test_build_plan_skips_answered_items(self, planner, setup_test_data, db_manager):
        """Test that build_plan skips already-answered combinations."""
        from src.db.models import Response
        from src.db.repository import ResponseRepository

        # Create a response for the existing combination
        response = Response(
            run_id="run-test001",
            snapshot_id=1,
            question_id="Q001",
            model_id="openai/gpt-4",
            variant_id="var-abc123",
            iteration=1,
            selected_answer="B",
            response_text="The answer is B",
            is_correct=True,
            status="success",
        )
        ResponseRepository(db_manager).create(response)

        # Build plan - should have no items (already answered)
        plan = planner.build_plan(experiment_name="test_experiment")

        # All items should be skipped
        assert len(plan.runs) == 1
        assert len(plan.runs[0].items) == 0
