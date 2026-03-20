"""Test suite for TO-BE repository layer.

Tests verify:
- CRUD operations for all 6 entities
- Soft delete behavior (is_active flag)
- Active-only filtering
- Foreign key relationships
- needs_review calculation for responses
"""

import sqlite3
import pytest
from datetime import datetime

from src_v2.db.schema import create_schema
from src_v2.db.models import (
    Experiment,
    ModelVariant,
    QuestionSnapshot,
    Run,
    Response,
    Error,
)
from src_v2.db.repository import (
    ExperimentRepository,
    VariantRepository,
    SnapshotRepository,
    RunRepository,
    ResponseRepository,
    ErrorRepository,
)


@pytest.fixture
def db_conn():
    """Create in-memory database with schema for repository tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def repos(db_conn):
    """Create all repository instances."""
    return {
        "experiment": ExperimentRepository(db_conn),
        "variant": VariantRepository(db_conn),
        "snapshot": SnapshotRepository(db_conn),
        "run": RunRepository(db_conn),
        "response": ResponseRepository(db_conn),
        "error": ErrorRepository(db_conn),
    }


class TestExperimentRepository:
    """Tests for ExperimentRepository CRUD operations."""

    @pytest.mark.domain_rule("Experiments must support full CRUD cycle")
    def test_repository_crud_experiment(self, repos):
        """Verify full CRUD cycle for experiments."""
        repo = repos["experiment"]

        # CREATE
        experiment = Experiment(
            experiment_id="exp_001",
            name="test_experiment",
            description="Test experiment for CRUD",
            config_json='{"temperature": 0.7}',
            config_hash="abc123",
            system_prompt="You are a helpful assistant.",
            user_prompt="Answer the following question.",
        )
        repo.save(experiment)

        # READ by ID
        retrieved = repo.get_by_id("exp_001")
        assert retrieved is not None
        assert retrieved.name == "test_experiment"
        assert retrieved.description == "Test experiment for CRUD"

        # READ by name
        by_name = repo.get_by_name("test_experiment")
        assert by_name is not None
        assert by_name.experiment_id == "exp_001"

        # UPDATE
        experiment.description = "Updated description"
        repo.save(experiment)
        updated = repo.get_by_id("exp_001")
        assert updated.description == "Updated description"

        # LIST
        all_exps = repo.list_all(active_only=False)
        assert len(all_exps) == 1
        assert all_exps[0].experiment_id == "exp_001"

    @pytest.mark.domain_rule("Experiments must support soft delete via is_active flag")
    def test_repository_soft_delete_experiment(self, repos):
        """Verify soft delete sets is_active = FALSE."""
        repo = repos["experiment"]

        experiment = Experiment(
            experiment_id="exp_002",
            name="to_delete",
            config_json="{}",
            config_hash="hash",
            system_prompt="system",
            user_prompt="user",
        )
        repo.save(experiment)

        # Verify active
        assert repo.get_by_id("exp_002").is_active is True

        # Soft delete
        repo.deactivate("exp_002")

        # Verify inactive
        deactivated = repo.get_by_id("exp_002")
        assert deactivated.is_active is False

        # Verify not in active list
        active_exps = repo.list_all(active_only=True)
        assert len(active_exps) == 0

        # But still in full list
        all_exps = repo.list_all(active_only=False)
        assert len(all_exps) == 1

    @pytest.mark.domain_rule("Repository list must support active_only filtering")
    def test_repository_list_active_only(self, repos):
        """Verify list_all filters by is_active."""
        repo = repos["experiment"]

        # Create two experiments
        exp1 = Experiment(
            experiment_id="exp_active",
            name="active_exp",
            config_json="{}",
            config_hash="hash1",
            system_prompt="system",
            user_prompt="user",
        )
        exp2 = Experiment(
            experiment_id="exp_inactive",
            name="inactive_exp",
            config_json="{}",
            config_hash="hash2",
            system_prompt="system",
            user_prompt="user",
        )
        repo.save(exp1)
        repo.save(exp2)

        # Deactivate one
        repo.deactivate("exp_inactive")

        # Active only should return 1
        active = repo.list_all(active_only=True)
        assert len(active) == 1
        assert active[0].name == "active_exp"

        # All should return 2
        all_exps = repo.list_all(active_only=False)
        assert len(all_exps) == 2


class TestVariantRepository:
    """Tests for VariantRepository CRUD operations."""

    @pytest.mark.domain_rule("Model variants must belong to experiments (FK)")
    def test_repository_crud_variant(self, repos):
        """Verify CRUD for model variants with experiment FK."""
        exp_repo = repos["experiment"]
        var_repo = repos["variant"]

        # Create experiment first
        experiment = Experiment(
            experiment_id="exp_var_test",
            name="variant_test_exp",
            config_json="{}",
            config_hash="hash",
            system_prompt="system",
            user_prompt="user",
        )
        exp_repo.save(experiment)

        # CREATE variant
        variant = ModelVariant(
            variant_id="var_001",
            experiment_id="exp_var_test",
            model_id="openai/gpt-4",
            variant_signature="gpt4-default",
            reasoning_mode="off",
            vision_enabled=False,
            structured_output=True,
        )
        var_repo.save(variant)

        # READ
        retrieved = var_repo.get_by_id("var_001")
        assert retrieved is not None
        assert retrieved.model_id == "openai/gpt-4"
        assert retrieved.experiment_id == "exp_var_test"

        # LIST by experiment
        variants = var_repo.list_by_experiment("exp_var_test")
        assert len(variants) == 1
        assert variants[0].variant_id == "var_001"

        # UPDATE
        variant.reasoning_mode = "effort"
        var_repo.save(variant)
        updated = var_repo.get_by_id("var_001")
        assert updated.reasoning_mode == "effort"

        # SOFT DELETE
        var_repo.deactivate("var_001")
        assert var_repo.get_by_id("var_001").is_active is False

    @pytest.mark.domain_rule("Variants must support listing by experiment")
    def test_variant_list_by_experiment(self, repos):
        """Verify listing variants filtered by experiment."""
        exp_repo = repos["experiment"]
        var_repo = repos["variant"]

        # Create two experiments
        exp1 = Experiment(
            experiment_id="exp1",
            name="exp1",
            config_json="{}",
            config_hash="h1",
            system_prompt="s",
            user_prompt="u",
        )
        exp2 = Experiment(
            experiment_id="exp2",
            name="exp2",
            config_json="{}",
            config_hash="h2",
            system_prompt="s",
            user_prompt="u",
        )
        exp_repo.save(exp1)
        exp_repo.save(exp2)

        # Create variants for each
        var1 = ModelVariant(
            variant_id="var_exp1",
            experiment_id="exp1",
            model_id="openai/gpt-4",
            variant_signature="gpt4",
        )
        var2 = ModelVariant(
            variant_id="var_exp2",
            experiment_id="exp2",
            model_id="anthropic/claude",
            variant_signature="claude",
        )
        var_repo.save(var1)
        var_repo.save(var2)

        # List by experiment should filter correctly
        exp1_variants = var_repo.list_by_experiment("exp1")
        assert len(exp1_variants) == 1
        assert exp1_variants[0].variant_id == "var_exp1"

        exp2_variants = var_repo.list_by_experiment("exp2")
        assert len(exp2_variants) == 1
        assert exp2_variants[0].variant_id == "var_exp2"


class TestSnapshotRepository:
    """Tests for SnapshotRepository CRUD operations."""

    @pytest.mark.domain_rule("Question snapshots must belong to experiments (FK)")
    def test_repository_crud_snapshot(self, repos):
        """Verify CRUD for question snapshots with experiment FK."""
        exp_repo = repos["experiment"]
        snap_repo = repos["snapshot"]

        # Create experiment first
        experiment = Experiment(
            experiment_id="exp_snap_test",
            name="snapshot_test_exp",
            config_json="{}",
            config_hash="hash",
            system_prompt="system",
            user_prompt="user",
        )
        exp_repo.save(experiment)

        # CREATE snapshot
        import json
        payload = {"stem": "What is 2+2?", "options": ["3", "4", "5"], "answer_key": "B"}
        snapshot = QuestionSnapshot(
            snapshot_id="snap_001",
            experiment_id="exp_snap_test",
            question_id="q001",
            question_payload=json.dumps(payload),
        )
        snap_repo.save(snapshot)

        # READ
        retrieved = snap_repo.get_by_id("snap_001")
        assert retrieved is not None
        assert retrieved.question_id == "q001"
        assert json.loads(retrieved.question_payload) == payload

        # LIST by experiment
        snapshots = snap_repo.list_by_experiment("exp_snap_test")
        assert len(snapshots) == 1

        # SOFT DELETE
        snap_repo.deactivate("snap_001")
        assert snap_repo.get_by_id("snap_001").is_active is False


class TestRunRepository:
    """Tests for RunRepository CRUD operations."""

    @pytest.mark.domain_rule("Runs must support status transitions")
    def test_repository_crud_run(self, repos):
        """Verify CRUD for runs with status transitions."""
        exp_repo = repos["experiment"]
        run_repo = repos["run"]

        # Create experiment first
        experiment = Experiment(
            experiment_id="exp_run_test",
            name="run_test_exp",
            config_json="{}",
            config_hash="hash",
            system_prompt="system",
            user_prompt="user",
        )
        exp_repo.save(experiment)

        # CREATE run
        run = Run(
            run_id="run_001",
            experiment_id="exp_run_test",
            seed=42,
            status="pending",
        )
        run_repo.save(run)

        # READ
        retrieved = run_repo.get_by_id("run_001")
        assert retrieved is not None
        assert retrieved.status == "pending"
        assert retrieved.seed == 42

        # STATUS TRANSITION: pending -> running
        run_repo.update_status("run_001", "running")
        updated = run_repo.get_by_id("run_001")
        assert updated.status == "running"

        # STATUS TRANSITION: running -> completed
        run_repo.update_status("run_001", "completed")
        completed = run_repo.get_by_id("run_001")
        assert completed.status == "completed"

        # LIST by experiment
        runs = run_repo.list_by_experiment("exp_run_test")
        assert len(runs) == 1

        # LIST pending
        pending = run_repo.list_pending()
        assert len(pending) == 0  # We completed it

    @pytest.mark.domain_rule("Runs must support listing by status")
    def test_run_list_by_status(self, repos):
        """Verify listing runs filtered by status."""
        exp_repo = repos["experiment"]
        run_repo = repos["run"]

        # Create experiment
        experiment = Experiment(
            experiment_id="exp_status",
            name="status_test",
            config_json="{}",
            config_hash="h",
            system_prompt="s",
            user_prompt="u",
        )
        exp_repo.save(experiment)

        # Create runs with different statuses
        for i, status in enumerate(["pending", "running", "completed"]):
            run = Run(
                run_id=f"run_{status}",
                experiment_id="exp_status",
                seed=i,
                status=status,
            )
            run_repo.save(run)

        # List pending
        pending = run_repo.list_pending()
        assert len(pending) == 1
        assert pending[0].status == "pending"

        # List by experiment
        all_runs = run_repo.list_by_experiment("exp_status")
        assert len(all_runs) == 3


class TestResponseRepository:
    """Tests for ResponseRepository CRUD operations."""

    @pytest.mark.domain_rule("Responses must calculate needs_review on save")
    def test_repository_response_needs_review(self, repos):
        """Verify needs_review is calculated correctly on save."""
        # Setup: create experiment, variant, snapshot, run
        exp_repo = repos["experiment"]
        var_repo = repos["variant"]
        snap_repo = repos["snapshot"]
        run_repo = repos["run"]
        resp_repo = repos["response"]

        experiment = Experiment(
            experiment_id="exp_resp",
            name="response_test",
            config_json="{}",
            config_hash="h",
            system_prompt="s",
            user_prompt="u",
        )
        exp_repo.save(experiment)

        variant = ModelVariant(
            variant_id="var_resp",
            experiment_id="exp_resp",
            model_id="openai/gpt-4",
            variant_signature="gpt4",
        )
        var_repo.save(variant)

        import json
        payload = {"stem": "Q?", "options": ["A", "B"], "answer_key": "A"}
        snapshot = QuestionSnapshot(
            snapshot_id="snap_resp",
            experiment_id="exp_resp",
            question_id="q_resp",
            question_payload=json.dumps(payload),
        )
        snap_repo.save(snapshot)

        run = Run(
            run_id="run_resp",
            experiment_id="exp_resp",
            seed=42,
            status="running",
        )
        run_repo.save(run)

        # Response with clear answer, correct -> needs_review=False
        response1 = Response(
            response_id="resp_001",
            run_id="run_resp",
            variant_id="var_resp",
            snapshot_id="snap_resp",
            model_id="openai/gpt-4",
            question_id="q_resp",
            response_text="The answer is B",
            selected_answer="B",
            is_correct=False,
            parse_confidence="clear",
            latency_ms=150,
        )
        resp_repo.save(response1)
        saved1 = resp_repo.get_by_id("resp_001")
        assert saved1.needs_review is False  # Clear parse, has answer

        # Response with ambiguous parse -> needs_review=True
        response2 = Response(
            response_id="resp_002",
            run_id="run_resp",
            variant_id="var_resp",
            snapshot_id="snap_resp",
            model_id="openai/gpt-4",
            question_id="q_resp",
            response_text="I'm not sure...",
            selected_answer=None,
            is_correct=None,
            parse_confidence="ambiguous",
            latency_ms=200,
        )
        resp_repo.save(response2)
        saved2 = resp_repo.get_by_id("resp_002")
        assert saved2.needs_review is True  # Ambiguous parse

        # Response with no_answer -> needs_review=True
        response3 = Response(
            response_id="resp_003",
            run_id="run_resp",
            variant_id="var_resp",
            snapshot_id="snap_resp",
            model_id="openai/gpt-4",
            question_id="q_resp",
            response_text="I cannot answer this",
            selected_answer=None,
            is_correct=None,
            parse_confidence="no_answer",
            latency_ms=100,
        )
        resp_repo.save(response3)
        saved3 = resp_repo.get_by_id("resp_003")
        assert saved3.needs_review is True  # No answer

    @pytest.mark.domain_rule("Responses must be queryable by needs_review flag")
    def test_response_list_needs_review(self, repos):
        """Verify listing responses that need review.
        
        Note: Due to UNIQUE(run_id, variant_id, snapshot_id), we need different
        snapshots to create multiple responses in the same run.
        """
        # Setup
        exp_repo = repos["experiment"]
        var_repo = repos["variant"]
        snap_repo = repos["snapshot"]
        run_repo = repos["run"]
        resp_repo = repos["response"]

        experiment = Experiment(
            experiment_id="exp_review",
            name="review_test",
            config_json="{}",
            config_hash="h",
            system_prompt="s",
            user_prompt="u",
        )
        exp_repo.save(experiment)

        variant = ModelVariant(
            variant_id="var_review",
            experiment_id="exp_review",
            model_id="openai/gpt-4",
            variant_signature="gpt4",
        )
        var_repo.save(variant)

        # Create 3 different snapshots (questions)
        snapshots = []
        for i in range(3):
            snapshot = QuestionSnapshot(
                snapshot_id=f"snap_review_{i}",
                experiment_id="exp_review",
                question_id=f"q_review_{i}",
                question_payload="{}",
            )
            snap_repo.save(snapshot)
            snapshots.append(snapshot)

        run = Run(
            run_id="run_review",
            experiment_id="exp_review",
            status="running",
        )
        run_repo.save(run)

        # Response 0: ambiguous parse -> needs_review=True
        response0 = Response(
            response_id="resp_review_0",
            run_id="run_review",
            variant_id="var_review",
            snapshot_id="snap_review_0",
            model_id="openai/gpt-4",
            question_id="q_review_0",
            parse_confidence="ambiguous",
            selected_answer="A",
        )
        resp_repo.save(response0)

        # Response 1: no_answer -> needs_review=True
        response1 = Response(
            response_id="resp_review_1",
            run_id="run_review",
            variant_id="var_review",
            snapshot_id="snap_review_1",
            model_id="openai/gpt-4",
            question_id="q_review_1",
            parse_confidence="no_answer",
            selected_answer=None,
        )
        resp_repo.save(response1)

        # Response 2: clear parse with answer -> needs_review=False
        response2 = Response(
            response_id="resp_review_2",
            run_id="run_review",
            variant_id="var_review",
            snapshot_id="snap_review_2",
            model_id="openai/gpt-4",
            question_id="q_review_2",
            parse_confidence="clear",
            selected_answer="B",
        )
        resp_repo.save(response2)

        # List needing review - should return 2 (ambiguous and no_answer)
        needs_review = resp_repo.list_needs_review()
        assert len(needs_review) == 2

        # List by run - should return all 3
        by_run = resp_repo.list_by_run("run_review")
        assert len(by_run) == 3


class TestErrorRepository:
    """Tests for ErrorRepository CRUD operations."""

    @pytest.mark.domain_rule("Errors must track error classification")
    def test_repository_crud_error(self, repos):
        """Verify CRUD for errors with error classification."""
        # Setup
        exp_repo = repos["experiment"]
        var_repo = repos["variant"]
        snap_repo = repos["snapshot"]
        run_repo = repos["run"]
        error_repo = repos["error"]

        experiment = Experiment(
            experiment_id="exp_err",
            name="error_test",
            config_json="{}",
            config_hash="h",
            system_prompt="s",
            user_prompt="u",
        )
        exp_repo.save(experiment)

        variant = ModelVariant(
            variant_id="var_err",
            experiment_id="exp_err",
            model_id="openai/gpt-4",
            variant_signature="gpt4",
        )
        var_repo.save(variant)

        snapshot = QuestionSnapshot(
            snapshot_id="snap_err",
            experiment_id="exp_err",
            question_id="q_err",
            question_payload="{}",
        )
        snap_repo.save(snapshot)

        run = Run(
            run_id="run_err",
            experiment_id="exp_err",
            status="running",
        )
        run_repo.save(run)

        # CREATE error
        error = Error(
            error_id="err_001",
            run_id="run_err",
            variant_id="var_err",
            snapshot_id="snap_err",
            error_type="api_error",
            error_message="Rate limit exceeded",
            attempt_count=3,
            stack_trace="Traceback...",
        )
        error_repo.save(error)

        # READ
        retrieved = error_repo.get_by_id("err_001")
        assert retrieved is not None
        assert retrieved.error_type == "api_error"
        assert retrieved.attempt_count == 3

        # LIST by run
        errors = error_repo.list_by_run("run_err")
        assert len(errors) == 1
        assert errors[0].error_type == "api_error"

        # UPDATE
        error.attempt_count = 5
        error_repo.save(error)
        updated = error_repo.get_by_id("err_001")
        assert updated.attempt_count == 5


class TestForeignKeyEnforcement:
    """Tests for foreign key enforcement in repositories."""

    @pytest.mark.domain_rule("Repositories must respect FK constraints")
    def test_cannot_save_variant_without_experiment(self, db_conn, repos):
        """Verify cannot save variant with non-existent experiment."""
        var_repo = repos["variant"]

        variant = ModelVariant(
            variant_id="var_orphan",
            experiment_id="nonexistent",
            model_id="openai/gpt-4",
            variant_signature="orphan",
        )

        with pytest.raises(sqlite3.IntegrityError):
            var_repo.save(variant)

    @pytest.mark.domain_rule("Repositories must respect FK constraints")
    def test_cannot_save_snapshot_without_experiment(self, db_conn, repos):
        """Verify cannot save snapshot with non-existent experiment."""
        snap_repo = repos["snapshot"]

        snapshot = QuestionSnapshot(
            snapshot_id="snap_orphan",
            experiment_id="nonexistent",
            question_id="q_orphan",
            question_payload="{}",
        )

        with pytest.raises(sqlite3.IntegrityError):
            snap_repo.save(snapshot)

    @pytest.mark.domain_rule("Repositories must respect FK constraints")
    def test_cannot_save_run_without_experiment(self, db_conn, repos):
        """Verify cannot save run with non-existent experiment."""
        run_repo = repos["run"]

        run = Run(
            run_id="run_orphan",
            experiment_id="nonexistent",
            status="pending",
        )

        with pytest.raises(sqlite3.IntegrityError):
            run_repo.save(run)
