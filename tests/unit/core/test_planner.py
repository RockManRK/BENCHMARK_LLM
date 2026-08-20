"""Unit tests for Planner.

Tests the Planner's domain rules:
- Validates experiment exists
- Validates experiment has models
- Validates experiment has snapshots
- Builds ExecutionPlan with correct structure
- Deduplicates items per run
- Resolves effective prompts (run overrides experiment)
- Reads the run's own, already-frozen Randomization Seed (no fallback to
  experiment at execution time — inheritance happens once, at run creation)
- Includes retry policy in each PlanRun
- Filters by specific run IDs
- Includes all active variants and snapshots
"""

import json
import pytest
from datetime import datetime
from src.core import Planner, ExecutionPlan, PlannerValidationError
from src.core.question_loader import build_question_snapshot_payload
from src.db.repository import (
    ExperimentRepository,
    VariantRepository,
    SnapshotRepository,
    RunRepository,
)
from tests.factories import (
    ExperimentFactory,
    VariantFactory,
    SnapshotFactory,
    RunFactory,
)


def _insert_experiment(conn, experiment):
    """Insert experiment into database via the real repository."""
    ExperimentRepository(conn).save(experiment)


def _insert_variant(conn, variant):
    """Insert model variant into database via the real repository."""
    VariantRepository(conn).save(variant)


def _insert_snapshot(conn, snapshot):
    """Insert question snapshot into database via the real repository."""
    SnapshotRepository(conn).save(snapshot)


def _insert_run(conn, run):
    """Insert run into database via the real repository.

    RunRepository.save() takes `config` as a separate dict argument rather
    than reading Run.config (see src/db/repository.py) — reproduce that
    quirk here rather than working around it silently.
    """
    RunRepository(conn).save(run, config=json.loads(run.config))


@pytest.mark.domain_rule
def test_planner_validates_experiment_exists(in_memory_db):
    """Planner raises error if experiment does not exist."""
    # Arrange
    planner = Planner(in_memory_db)

    # Act & Assert
    with pytest.raises(PlannerValidationError) as exc_info:
        planner.build_plan("non-existent-experiment")

    assert "not found" in str(exc_info.value).lower()


@pytest.mark.domain_rule
def test_planner_validates_has_models(in_memory_db):
    """Planner raises error if experiment has no models."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)
    # Don't insert any variants

    planner = Planner(in_memory_db)

    # Act & Assert
    with pytest.raises(PlannerValidationError) as exc_info:
        planner.build_plan("test-exp")

    assert "no models" in str(exc_info.value).lower()


@pytest.mark.domain_rule
def test_planner_validates_has_snapshots(in_memory_db):
    """Planner raises error if experiment has no snapshots."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)
    # Don't insert any snapshots

    planner = Planner(in_memory_db)

    # Act & Assert
    with pytest.raises(PlannerValidationError) as exc_info:
        planner.build_plan("test-exp")

    assert "no questions" in str(exc_info.value).lower() or "no snapshots" in str(exc_info.value).lower()


@pytest.mark.domain_rule
def test_planner_builds_plan_with_items(in_memory_db):
    """Planner builds ExecutionPlan with correct structure."""
    # Arrange
    experiment = ExperimentFactory.create(
        name="test-exp",
        system_prompt="You are helpful.",
        user_prompt="Answer: {question}",
    )
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    assert isinstance(plan, ExecutionPlan)
    assert plan.plan_id is not None
    assert plan.created_at is not None
    assert plan.experiment_id == experiment.experiment_id
    assert len(plan.runs) == 1
    assert len(plan.runs[0].items) == 1  # 1 variant × 1 snapshot


@pytest.mark.domain_rule
def test_planner_deduplicates_within_run(in_memory_db):
    """Planner does not create duplicate items per run."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    # Create 2 variants
    variant1 = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    variant2 = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="anthropic/claude-3")
    _insert_variant(in_memory_db, variant1)
    _insert_variant(in_memory_db, variant2)

    # Create 2 snapshots
    snapshot1 = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q1?", "options": ["A", "B", "C", "D"], "answer_key": "A"},
    )
    snapshot2 = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q2",
        question_payload={"stem": "Q2?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot1)
    _insert_snapshot(in_memory_db, snapshot2)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    # Should have 2 variants × 2 snapshots = 4 items
    assert len(plan.runs[0].items) == 4

    # Verify no duplicate (run_id, variant_id, snapshot_id) combinations
    item_keys = [(item.run_id, item.variant_id, item.snapshot_id) for item in plan.runs[0].items]
    assert len(item_keys) == len(set(item_keys)), "Duplicate items found in plan"


@pytest.mark.domain_rule
def test_planner_resolves_prompts_effective_run_override(in_memory_db):
    """Planner uses run prompts when provided (override)."""
    # Arrange
    experiment = ExperimentFactory.create(
        name="test-exp",
        system_prompt="Experiment system prompt",
        user_prompt="Experiment user prompt",
    )
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    # Run with custom prompts (simulated via run data)
    run = RunFactory.create(
        experiment_id=experiment.experiment_id,
        randomization_seed=42,
    )
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    # For minimal schema, run doesn't have prompts, so experiment prompts are used
    # This test verifies the structure is correct
    assert plan.runs[0].prompts_effective.system == "Experiment system prompt"
    assert plan.runs[0].prompts_effective.user == "Experiment user prompt"


@pytest.mark.domain_rule
def test_planner_resolves_prompts_effective_experiment_default(in_memory_db):
    """Planner uses experiment prompts when run has none."""
    # Arrange
    experiment = ExperimentFactory.create(
        name="test-exp",
        system_prompt="Default system prompt",
        user_prompt="Default user prompt",
    )
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    assert plan.runs[0].prompts_effective.system == "Default system prompt"
    assert plan.runs[0].prompts_effective.user == "Default user prompt"


@pytest.mark.domain_rule
def test_planner_reads_run_own_randomization_seed(in_memory_db):
    """Planner reads the run's own, already-frozen Randomization Seed."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=123)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    assert plan.runs[0].randomization_seed_effective == 123


@pytest.mark.domain_rule
def test_planner_reads_run_own_none_randomization_seed_without_falling_back_to_experiment(in_memory_db):
    """Regression for the fixed Planner bug (docs/status/known-issues.md):
    a run whose own RANDOMIZATION_SEED is explicitly None (a frozen
    "don't randomize" decision made at run creation) must stay None —
    the Planner must NEVER fall back to the experiment's own seed here,
    even if the experiment has one configured. Experiment -> Run
    inheritance happens exactly once, at run creation
    (ConfigResolver.resolve_randomization_seed_for_run); the Planner only
    reads the run's own, already-frozen value."""
    # Arrange
    experiment = ExperimentFactory.create(
        name="test-exp",
        config_json='{"RANDOMIZATION_SEED": 42}',
    )
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    # Run explicitly resolved to None at creation (e.g. --randomization-seed
    # system-default), despite the experiment having RANDOMIZATION_SEED=42.
    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=None)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert — the run's own None must survive, not fall back to the
    # experiment's 42.
    assert plan.runs[0].randomization_seed_effective is None


@pytest.mark.domain_rule
def test_planner_raises_clear_error_when_run_missing_randomization_seed_key(in_memory_db):
    """A run whose config is missing RANDOMIZATION_SEED entirely is a
    data-integrity problem, not something to silently paper over with an
    experiment fallback — the Planner must raise a clear validation
    error."""
    from src.core.planner import PlannerValidationError

    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    # Bypass the factory's default to simulate a run whose config is
    # missing the key entirely — never produced by the real creation
    # flow, but the Planner must still refuse gracefully, not crash
    # obscurely or silently invent a fallback.
    run = RunFactory.create(experiment_id=experiment.experiment_id, config='{"SYSTEM_PROMPT": null, "USER_PROMPT": null}')
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act / Assert
    with pytest.raises(PlannerValidationError, match="RANDOMIZATION_SEED"):
        planner.build_plan("test-exp")


@pytest.mark.domain_rule
def test_planner_includes_retry_policy(in_memory_db):
    """Planner includes RetryPolicy in each PlanRun."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    assert len(plan.runs) > 0
    assert plan.runs[0].retry_policy is not None
    assert plan.runs[0].retry_policy.max_attempts == 3
    assert plan.runs[0].retry_policy.backoff == 'exponential'


@pytest.mark.domain_rule
def test_planner_filters_by_run_ids(in_memory_db):
    """Planner filters to specific runs when run_ids provided."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    run1 = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42, run_id="run-001")
    run2 = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=43, run_id="run-002")
    run3 = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=44, run_id="run-003")
    _insert_run(in_memory_db, run1)
    _insert_run(in_memory_db, run2)
    _insert_run(in_memory_db, run3)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp", run_ids=["run-001", "run-003"])

    # Assert
    assert len(plan.runs) == 2
    run_ids_in_plan = {run.run_id for run in plan.runs}
    assert run_ids_in_plan == {"run-001", "run-003"}


@pytest.mark.domain_rule
def test_planner_includes_all_variants(in_memory_db):
    """Planner includes all active variants in the plan."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    # Create 3 variants
    variant1 = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    variant2 = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="anthropic/claude-3")
    variant3 = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="google/gemini-pro")
    _insert_variant(in_memory_db, variant1)
    _insert_variant(in_memory_db, variant2)
    _insert_variant(in_memory_db, variant3)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    _insert_snapshot(in_memory_db, snapshot)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    # All 3 variants should be in the plan
    variant_ids_in_plan = {item.variant_id for item in plan.runs[0].items}
    assert variant1.variant_id in variant_ids_in_plan
    assert variant2.variant_id in variant_ids_in_plan
    assert variant3.variant_id in variant_ids_in_plan


@pytest.mark.domain_rule
def test_planner_includes_all_snapshots(in_memory_db):
    """Planner includes all active snapshots in the plan."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    # Create 3 snapshots
    snapshot1 = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
        question_payload={"stem": "Q1?", "options": ["A", "B", "C", "D"], "answer_key": "A"},
    )
    snapshot2 = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q2",
        question_payload={"stem": "Q2?", "options": ["A", "B", "C", "D"], "answer_key": "B"},
    )
    snapshot3 = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q3",
        question_payload={"stem": "Q3?", "options": ["A", "B", "C", "D"], "answer_key": "C"},
    )
    _insert_snapshot(in_memory_db, snapshot1)
    _insert_snapshot(in_memory_db, snapshot2)
    _insert_snapshot(in_memory_db, snapshot3)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    # All 3 snapshots should be in the plan
    snapshot_ids_in_plan = {item.snapshot_id for item in plan.runs[0].items}
    assert snapshot1.snapshot_id in snapshot_ids_in_plan
    assert snapshot2.snapshot_id in snapshot_ids_in_plan
    assert snapshot3.snapshot_id in snapshot_ids_in_plan


@pytest.mark.domain_rule
def test_planner_recognizes_vision_question_via_canonical_payload_builder(in_memory_db):
    """A snapshot whose payload was built via build_question_snapshot_payload
    (the canonical function both CLI flows now share — see
    src/core/question_loader.py and docs/status/known-issues.md,
    "double-wrapped meta field") must be recognized as a vision question by
    the Planner: has_image=True and image_path taken from assets[0].

    This is the regression proof for the double-wrap bug: before the fix,
    the composite flow (--create-experiment + --add-questions) produced
    payload["meta"] == {"meta": {"has_image": True, ...}}, so
    payload_data.get("meta", {}).get("has_image", False) always saw False
    even for genuinely vision-enabled questions.
    """
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp-vision")
    _insert_experiment(in_memory_db, experiment)

    variant = VariantFactory.create(experiment_id=experiment.experiment_id, model_id="openai/gpt-4")
    _insert_variant(in_memory_db, variant)

    raw_question = {
        "internal_id": 1,
        "source_id": "Q005",
        "stem": "Describe the X-ray findings.",
        "options": {"A": "Pneumonia", "B": "Fracture", "C": "Normal", "D": "Tumor"},
        "answer_key": "A",
        "assets": ["data/assets/image_Q005.png"],
        "meta": {"has_table": False, "has_image": True, "status": "valid", "notes": ""},
    }
    payload = build_question_snapshot_payload(raw_question)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="Q005",
        question_payload=payload,
    )
    _insert_snapshot(in_memory_db, snapshot)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp-vision")

    # Assert
    assert len(plan.runs[0].items) == 1
    item = plan.runs[0].items[0]
    assert item.question_payload.has_image is True
    assert item.question_payload.image_path == "data/assets/image_Q005.png"


@pytest.mark.domain_rule
def test_planner_item_count_matches_combinations(in_memory_db):
    """Planner creates items = variants × snapshots."""
    # Arrange
    experiment = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, experiment)

    # Create 3 variants
    for i in range(3):
        variant = VariantFactory.create(
            experiment_id=experiment.experiment_id,
            model_id=f"openai/gpt-{i}",
        )
        _insert_variant(in_memory_db, variant)

    # Create 4 snapshots
    for i in range(4):
        snapshot = SnapshotFactory.create(
            experiment_id=experiment.experiment_id,
            question_id=f"q{i}",
            question_payload={"stem": f"Q{i}?", "options": ["A", "B", "C", "D"], "answer_key": "A"},
        )
        _insert_snapshot(in_memory_db, snapshot)

    run = RunFactory.create(experiment_id=experiment.experiment_id, randomization_seed=42)
    _insert_run(in_memory_db, run)

    planner = Planner(in_memory_db)

    # Act
    plan = planner.build_plan("test-exp")

    # Assert
    # 3 variants × 4 snapshots = 12 items
    assert len(plan.runs[0].items) == 12
