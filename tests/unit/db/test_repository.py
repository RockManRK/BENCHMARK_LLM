"""Tests for TO-BE repository layer.

Verifies:
- CRUD operations for all 6 repositories
- Foreign key enforcement
- Soft delete behavior
- Query filtering (active_only, by_experiment, etc.)
"""

import json
import sqlite3

import pytest

from src.db.models import (
    Experiment,
    ModelVariant,
    QuestionSnapshot,
    Run,
    Response,
)
from src.db.repository import (
    ExperimentRepository,
    VariantRepository,
    SnapshotRepository,
    RunRepository,
    ResponseRepository,
)


@pytest.fixture
def db_conn():
    """Create in-memory database connection."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


@pytest.fixture
def repos(db_conn):
    """Create all repositories with initialized schema."""
    from src.db.schema import create_schema
    create_schema(db_conn)

    return {
        "experiment": ExperimentRepository(db_conn),
        "variant": VariantRepository(db_conn),
        "snapshot": SnapshotRepository(db_conn),
        "run": RunRepository(db_conn),
        "response": ResponseRepository(db_conn),
    }


class TestExperimentRepository:
    """Tests for ExperimentRepository CRUD operations."""

    @pytest.mark.domain_rule("Experiments are root entities (no FK dependencies)")
    def test_repository_crud_experiment(self, repos):
        """Verify basic CRUD for experiments."""
        repo = repos["experiment"]

        # CREATE
        experiment = Experiment(
            experiment_id="exp_001",
            name="test_exp",
            description="Test experiment",
            config_json="{}",
            config_hash="abc123",
            system_prompt="system",
            user_prompt="user",
        )
        repo.save(experiment)

        # READ by ID
        retrieved = repo.get_by_id("exp_001")
        assert retrieved is not None
        assert retrieved.name == "test_exp"

        # READ by name
        by_name = repo.get_by_name("test_exp")
        assert by_name is not None
        assert by_name.experiment_id == "exp_001"

        # UPDATE
        experiment.description = "Updated description"
        repo.save(experiment)
        updated = repo.get_by_id("exp_001")
        assert updated.description == "Updated description"

        # SOFT DELETE
        repo.deactivate("exp_001")
        deactivated = repo.get_by_id("exp_001")
        assert deactivated.is_active is False

    @pytest.mark.domain_rule("Experiments must support soft delete")
    def test_repository_soft_delete_experiment(self, repos):
        """Verify soft delete sets is_active = FALSE."""
        repo = repos["experiment"]

        # Create two experiments
        exp1 = Experiment(
            experiment_id="exp_inactive",
            name="inactive_exp",
            config_json="{}",
            config_hash="h1",
            system_prompt="s",
            user_prompt="u",
        )
        exp2 = Experiment(
            experiment_id="exp_active",
            name="active_exp",
            config_json="{}",
            config_hash="h2",
            system_prompt="s",
            user_prompt="u",
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
        config = json.dumps({
            "reasoning_effort": "low",
            "vision": True,
            "structured_output": True,
        })
        variant = ModelVariant(
            variant_id="var_001",
            experiment_id="exp_var_test",
            model_id="openai/gpt-4",
            variant_signature="gpt4-default",
            config=config,
        )
        var_repo.save(variant)

        # READ
        retrieved = var_repo.get_by_id("var_001")
        assert retrieved is not None
        assert retrieved.model_id == "openai/gpt-4"
        assert retrieved.experiment_id == "exp_var_test"
        assert retrieved.config == config

        # LIST by experiment
        variants = var_repo.list_by_experiment("exp_var_test")
        assert len(variants) == 1
        assert variants[0].variant_id == "var_001"

        # UPDATE
        updated_config = json.dumps({"reasoning_effort": "high", "vision": False})
        variant.config = updated_config
        var_repo.save(variant)
        updated = var_repo.get_by_id("var_001")
        assert updated.config == updated_config

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
            config="{}",
        )
        var2 = ModelVariant(
            variant_id="var_exp2",
            experiment_id="exp2",
            model_id="anthropic/claude",
            variant_signature="claude",
            config="{}",
        )
        var_repo.save(var1)
        var_repo.save(var2)

        # List should be filtered by experiment
        variants1 = var_repo.list_by_experiment("exp1")
        assert len(variants1) == 1
        assert variants1[0].variant_id == "var_exp1"

        variants2 = var_repo.list_by_experiment("exp2")
        assert len(variants2) == 1
        assert variants2[0].variant_id == "var_exp2"


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
        payload = json.dumps({
            "stem": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "answer_key": "B",
        })
        snapshot = QuestionSnapshot(
            snapshot_id="snap_001",
            experiment_id="exp_snap_test",
            question_id="q_math_001",
            question_payload=payload,
        )
        snap_repo.save(snapshot)

        # READ by ID
        retrieved = snap_repo.get_by_id("snap_001")
        assert retrieved is not None
        assert retrieved.question_id == "q_math_001"
        assert retrieved.experiment_id == "exp_snap_test"

        # READ by experiment and question
        by_eq = snap_repo.get_by_experiment_and_question("exp_snap_test", "q_math_001")
        assert by_eq is not None
        assert by_eq.snapshot_id == "snap_001"

        # LIST by experiment
        snapshots = snap_repo.list_by_experiment("exp_snap_test")
        assert len(snapshots) == 1

        # SOFT DELETE
        snap_repo.deactivate("snap_001")
        assert snap_repo.get_by_id("snap_001").is_active is False


class TestRunRepository:
    """Tests for RunRepository CRUD operations."""

    @pytest.mark.domain_rule("Runs must belong to experiments (FK)")
    def test_repository_crud_run(self, repos):
        """Verify CRUD for runs with experiment FK."""
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

        # STATUS TRANSITION: pending -> completed
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
        for i, status in enumerate(["pending", "completed", "failed"]):
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

    @pytest.mark.domain_rule("Responses must calculate review_status on save")
    def test_repository_response_review_status(self, repos):
        """Verify review_status is calculated correctly on save."""
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
            config="{}",
        )
        var_repo.save(variant)

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
            status="pending",
        )
        run_repo.save(run)

        # CREATE response with clear answer (should be 'auto')
        response = Response(
            response_id="resp_clear",
            run_id="run_resp",
            variant_id="var_resp",
            snapshot_id="snap_resp",
            model_id="openai/gpt-4",
            question_id="q_resp",
            selected_answer="A",
            parse_confidence="clear",
        )
        resp_repo.save(response)

        # Check the persisted value
        persisted = resp_repo.get_by_id("resp_clear")
        assert persisted.review_status == 'auto'

        # CREATE response with ambiguous confidence (needs review)
        response_ambig = Response(
            response_id="resp_ambig",
            run_id="run_resp",
            variant_id="var_resp",
            snapshot_id="snap_resp",
            model_id="openai/gpt-4",
            question_id="q_resp",
            selected_answer="B",
            parse_confidence="ambiguous",
        )
        resp_repo.save(response_ambig)

        # Check the persisted value
        persisted_ambig = resp_repo.get_by_id("resp_ambig")
        assert persisted_ambig.review_status == 'needs_review'

    @pytest.mark.domain_rule("Responses must support listing by review_status")
    def test_response_list_needs_review(self, repos):
        """Verify listing responses that need review."""
        # Setup (same as previous test)
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

        # Create TWO variants to allow unique (run_id, variant_id, snapshot_id) combinations
        variant1 = ModelVariant(
            variant_id="var_review_1",
            experiment_id="exp_review",
            model_id="openai/gpt-4",
            variant_signature="gpt4-v1",
            config="{}",
        )
        variant2 = ModelVariant(
            variant_id="var_review_2",
            experiment_id="exp_review",
            model_id="anthropic/claude",
            variant_signature="claude-v1",
            config="{}",
        )
        var_repo.save(variant1)
        var_repo.save(variant2)

        # Create TWO snapshots
        payload1 = {"stem": "Q1?", "options": ["A", "B"], "answer_key": "A"}
        payload2 = {"stem": "Q2?", "options": ["A", "B"], "answer_key": "B"}
        snapshot1 = QuestionSnapshot(
            snapshot_id="snap_review_1",
            experiment_id="exp_review",
            question_id="q_review_1",
            question_payload=json.dumps(payload1),
        )
        snapshot2 = QuestionSnapshot(
            snapshot_id="snap_review_2",
            experiment_id="exp_review",
            question_id="q_review_2",
            question_payload=json.dumps(payload2),
        )
        snap_repo.save(snapshot1)
        snap_repo.save(snapshot2)

        run = Run(
            run_id="run_review",
            experiment_id="exp_review",
            status="pending",
        )
        run_repo.save(run)

        # Create responses with different needs_review states
        # Each must have unique (run_id, variant_id, snapshot_id) combination
        test_cases = [
            # (response_id, variant_id, snapshot_id, selected_answer, parse_confidence, expected_needs_review)
            ("resp_review_1", "var_review_1", "snap_review_1", "A", "clear", False),
            ("resp_review_2", "var_review_1", "snap_review_2", "B", "ambiguous", True),
            ("resp_review_3", "var_review_2", "snap_review_1", None, "unknown", True),
        ]

        for resp_id, var_id, snap_id, answer, confidence, _ in test_cases:
            resp = Response(
                response_id=resp_id,
                run_id="run_review",
                variant_id=var_id,
                snapshot_id=snap_id,
                model_id="openai/gpt-4",
                question_id="q_review_1",
                selected_answer=answer,
                parse_confidence=confidence,
            )
            resp_repo.save(resp)

        # List needs review should return 2 (resp_review_2 and resp_review_3)
        needs_review = resp_repo.list_needs_review()
        assert len(needs_review) == 2
        
        # Verify the correct ones are flagged
        needs_review_ids = {r.response_id for r in needs_review}
        assert needs_review_ids == {"resp_review_2", "resp_review_3"}


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
            config="{}",
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
        )

        with pytest.raises(sqlite3.IntegrityError):
            run_repo.save(run)


class TestCreatedAtNotNull:
    """Tests for created_at NOT NULL constraint."""

    @pytest.mark.domain_rule("created_at must be populated by DB DEFAULT")
    def test_experiment_created_at_populated(self, repos):
        """Verify experiment.created_at is populated by DB (not NULL)."""
        repo = repos["experiment"]

        experiment = Experiment(
            experiment_id="exp_created_at",
            name="created_at_test",
            config_json="{}",
            config_hash="hash123",
        )
        repo.save(experiment)

        retrieved = repo.get_by_id("exp_created_at")
        assert retrieved is not None
        assert retrieved.created_at is not None
        assert isinstance(retrieved.created_at, str)

    @pytest.mark.domain_rule("created_at must be populated by DB DEFAULT")
    def test_variant_created_at_populated(self, repos):
        """Verify variant.created_at is populated by DB (not NULL)."""
        exp_repo = repos["experiment"]
        var_repo = repos["variant"]

        # Create experiment first
        experiment = Experiment(
            experiment_id="exp_var_created_at",
            name="var_created_at_test",
            config_json="{}",
            config_hash="hash123",
        )
        exp_repo.save(experiment)

        variant = ModelVariant(
            variant_id="var_created_at",
            experiment_id="exp_var_created_at",
            model_id="openai/gpt-4",
            variant_signature="gpt4-test",
            config="{}",
        )
        var_repo.save(variant)

        retrieved = var_repo.get_by_id("var_created_at")
        assert retrieved is not None
        assert retrieved.created_at is not None

    @pytest.mark.domain_rule("created_at must be populated by DB DEFAULT")
    def test_snapshot_created_at_populated(self, repos):
        """Verify snapshot.created_at is populated by DB (not NULL)."""
        exp_repo = repos["experiment"]
        snap_repo = repos["snapshot"]

        experiment = Experiment(
            experiment_id="exp_snap_created_at",
            name="snap_created_at_test",
            config_json="{}",
            config_hash="hash123",
        )
        exp_repo.save(experiment)

        snapshot = QuestionSnapshot(
            snapshot_id="snap_created_at",
            experiment_id="exp_snap_created_at",
            json_question_id="q_test",
            question_position=1,
            question_payload="{}",
        )
        snap_repo.save(snapshot)

        retrieved = snap_repo.get_by_id("snap_created_at")
        assert retrieved is not None
        assert retrieved.created_at is not None

    @pytest.mark.domain_rule("created_at must be populated by DB DEFAULT")
    def test_run_created_at_populated(self, repos):
        """Verify run.created_at is populated by DB (not NULL)."""
        exp_repo = repos["experiment"]
        run_repo = repos["run"]

        experiment = Experiment(
            experiment_id="exp_run_created_at",
            name="run_created_at_test",
            config_json="{}",
            config_hash="hash123",
        )
        exp_repo.save(experiment)

        run = Run(
            run_id="run_created_at",
            experiment_id="exp_run_created_at",
            config={"seed": 42},
            status="pending",
        )
        run_repo.save(run)

        retrieved = run_repo.get_by_id("run_created_at")
        assert retrieved is not None
        assert retrieved.created_at is not None


class TestConfigJsonPersistence:
    """Tests for configuration JSON persistence."""

    @pytest.mark.domain_rule("experiment config_json must persist all 18 keys")
    def test_experiment_config_json_persists_all_keys(self, repos):
        """Verify experiment config_json persists all 18 expected keys."""
        repo = repos["experiment"]

        import json
        config = {
            "QUESTIONS_DATASET_PATH": "/path/to/questions",
            "BASE_URL": "https://api.example.com",
            "MODEL_MAX_TOKENS_REASONING": 1000,
            "MODEL_MAX_TOKENS_TOTAL": 4096,
            "MODEL_REASONING_EFFORT": "high",
            "MODEL_REPEAT_PENALTY": 1.1,
            "MODEL_TEMPERATURE": 0.7,
            "MODEL_TOP_K": 50,
            "MODEL_TOP_P": 0.9,
            "MODEL_VISION": True,
            "STRUCTURED_OUTPUTS": False,
            "RUN_RESPONSES_SEED": 42,
            "SYSTEM_PROMPT": "Test system prompt",
            "USER_PROMPT": "Test user prompt",
        }

        experiment = Experiment(
            experiment_id="exp_config_test",
            name="config_test_exp",
            config_json=json.dumps(config),
            config_hash="hash123",
        )
        repo.save(experiment)

        retrieved = repo.get_by_id("exp_config_test")
        assert retrieved is not None

        retrieved_config = json.loads(retrieved.config_json)
        assert len(retrieved_config) == 17  # 17 keys

        # Verify all keys preserved
        for key, expected_value in config.items():
            assert key in retrieved_config
            assert retrieved_config[key] == expected_value

    @pytest.mark.domain_rule("model variant config must persist all 10 keys")
    def test_variant_config_persists_all_10_keys(self, repos):
        """Verify model variant config persists all 10 expected keys."""
        exp_repo = repos["experiment"]
        var_repo = repos["variant"]

        import json
        config = {
            "BASE_URL": "https://api.example.com",
            "MODEL_MAX_TOKENS_REASONING": 1000,
            "MODEL_MAX_TOKENS_TOTAL": 4096,
            "MODEL_REASONING_EFFORT": "high",
            "MODEL_REPEAT_PENALTY": 1.1,
            "MODEL_TEMPERATURE": 0.7,
            "MODEL_TOP_K": 50,
            "MODEL_TOP_P": 0.9,
            "MODEL_VISION": True,
            "STRUCTURED_OUTPUTS": False,
        }

        experiment = Experiment(
            experiment_id="exp_var_config",
            name="var_config_test",
            config_json="{}",
            config_hash="hash123",
        )
        exp_repo.save(experiment)

        variant = ModelVariant(
            variant_id="var_config_test",
            experiment_id="exp_var_config",
            model_id="openai/gpt-4",
            variant_signature="gpt4-config-test",
            config=json.dumps(config),
        )
        var_repo.save(variant)

        retrieved = var_repo.get_by_id("var_config_test")
        assert retrieved is not None

        retrieved_config = json.loads(retrieved.config)
        assert len(retrieved_config) == 10

        for key, expected_value in config.items():
            assert key in retrieved_config
            assert retrieved_config[key] == expected_value

    @pytest.mark.domain_rule("run config must persist seed and prompts")
    def test_run_config_persists_seed_and_prompts(self, repos):
        """Verify run config persists seed and prompts."""
        exp_repo = repos["experiment"]
        run_repo = repos["run"]

        import json
        config = {
            "seed": 42,
            "system_prompt": "Test system",
            "user_prompt": "Test user",
        }

        experiment = Experiment(
            experiment_id="exp_run_config",
            name="run_config_test",
            config_json="{}",
            config_hash="hash123",
        )
        exp_repo.save(experiment)

        run = Run(
            run_id="run_config_test",
            experiment_id="exp_run_config",
            config=json.dumps(config),
            status="pending",
        )
        run_repo.save(run)

        retrieved = run_repo.get_by_id("run_config_test")
        assert retrieved is not None

        retrieved_config = json.loads(retrieved.config)
        assert retrieved_config["seed"] == 42
        assert retrieved_config["system_prompt"] == "Test system"
        assert retrieved_config["user_prompt"] == "Test user"

    @pytest.mark.domain_rule("config JSON must handle null values correctly")
    def test_config_handles_null_values(self, repos):
        """Verify config JSON handles null values correctly."""
        repo = repos["experiment"]

        import json
        config = {
            "QUESTIONS_DATASET_PATH": None,
            "BASE_URL": None,
            "MODEL_TEMPERATURE": None,
            "RUN_RESPONSES_SEED": "OFF",
            "SYSTEM_PROMPT": None,
            "USER_PROMPT": None,
        }

        experiment = Experiment(
            experiment_id="exp_null_config",
            name="null_config_test",
            config_json=json.dumps(config),
            config_hash="hash123",
        )
        repo.save(experiment)

        retrieved = repo.get_by_id("exp_null_config")
        assert retrieved is not None

        retrieved_config = json.loads(retrieved.config_json)
        assert retrieved_config["QUESTIONS_DATASET_PATH"] is None
        assert retrieved_config["BASE_URL"] is None
        assert retrieved_config["MODEL_TEMPERATURE"] is None
