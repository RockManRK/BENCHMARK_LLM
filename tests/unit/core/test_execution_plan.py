"""Tests for ExecutionPlan data structures.

This module tests the immutable dataclasses that form the core
of the TO-BE execution system. All dataclasses use frozen=True
to prevent modification after creation.

Tests are organized by domain rules:
- Immutability guarantees (frozen dataclasses)
- Default value correctness
- Structure validation
- Factory integration
"""

import pytest
from datetime import datetime
from dataclasses import FrozenInstanceError

from src.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    Prompts,
    RetryPolicy,
    ModelConfig,
    QuestionPayload,
)


# =============================================================================
# IMMUTABILITY TESTS (Domain Rules)
# =============================================================================


@pytest.mark.domain_rule
def test_plan_is_immutable():
    """ExecutionPlan uses frozen=True to prevent modification."""
    # Arrange
    plan = ExecutionPlan(
        plan_id="plan-123",
        created_at=datetime.now(),
        experiment_id="exp-abc",
        runs=[],
    )

    # Act & Assert
    with pytest.raises(FrozenInstanceError):
        plan.plan_id = "plan-456"  # Should fail


@pytest.mark.domain_rule
def test_plan_run_is_immutable():
    """PlanRun uses frozen=True to prevent modification."""
    # Arrange
    run = PlanRun(
        run_id="run-123",
        randomization_seed_effective=42,
        prompts_effective=Prompts(system="System", user="User"),
        retry_policy=RetryPolicy(),
        variants=[],
        items=[],
    )

    # Act & Assert
    with pytest.raises(FrozenInstanceError):
        run.run_id = "run-456"  # Should fail


@pytest.mark.domain_rule
def test_plan_item_is_immutable():
    """PlanItem uses frozen=True to prevent modification."""
    # Arrange
    item = PlanItem(
        item_id="item-123",
        run_id="run-123",
        variant_id="var-abc",
        snapshot_id="snap-xyz",
        question_id="q1",
        question_payload=QuestionPayload(
            stem="What is 2+2?",
            options=["3", "4", "5", "6"],
            answer_key="4",
        ),
    )

    # Act & Assert
    with pytest.raises(FrozenInstanceError):
        item.item_id = "item-456"  # Should fail


@pytest.mark.domain_rule
def test_plan_variant_is_immutable():
    """PlanVariant uses frozen=True to prevent modification."""
    # Arrange
    variant = PlanVariant(
        variant_id="var-abc",
        model_id="openai/gpt-4",
        model_config_effective=ModelConfig(),
    )

    # Act & Assert
    with pytest.raises(FrozenInstanceError):
        variant.variant_id = "var-xyz"  # Should fail


# =============================================================================
# DEFAULT VALUE TESTS
# =============================================================================


def test_retry_policy_defaults():
    """RetryPolicy provides correct default values."""
    # Arrange & Act
    policy = RetryPolicy()

    # Assert
    assert policy.max_attempts == 3
    assert policy.backoff == "exponential"
    assert policy.retry_on == ("timeout", "http_429", "http_5xx", "network_error")


def test_model_config_defaults():
    """ModelConfig provides correct default values."""
    # Arrange & Act
    config = ModelConfig()

    # Assert
    assert config.temperature is None
    assert config.top_p is None
    assert config.max_output_tokens is None
    assert config.enable_vision is False
    assert config.structured_output is False
    assert config.reasoning_mode == "off"
    assert config.reasoning_effort is None


# =============================================================================
# STRUCTURE TESTS
# =============================================================================


def test_prompts_structure():
    """Prompts dataclass has correct structure."""
    # Arrange
    system_prompt = "You are a helpful assistant."
    user_prompt = "Answer the question: {question}"

    # Act
    prompts = Prompts(system=system_prompt, user=user_prompt)

    # Assert
    assert prompts.system == system_prompt
    assert prompts.user == user_prompt
    # Verify immutability
    with pytest.raises(FrozenInstanceError):
        prompts.system = "Changed"  # type: ignore[misc]


def test_question_payload_structure():
    """QuestionPayload dataclass has correct structure."""
    # Arrange
    stem = "What is the capital of France?"
    options = ["London", "Berlin", "Paris", "Madrid"]
    answer_key = "Paris"

    # Act
    payload = QuestionPayload(stem=stem, options=options, answer_key=answer_key)

    # Assert
    assert payload.stem == stem
    assert payload.options == options
    assert payload.answer_key == answer_key
    # Verify immutability
    with pytest.raises(FrozenInstanceError):
        payload.stem = "Changed"  # type: ignore[misc]


# =============================================================================
# INTEGRATION TESTS (with factories)
# =============================================================================


def test_plan_creation_with_factories():
    """ExecutionPlan can be created using factory pattern.

    This test demonstrates the integration between ExecutionPlan
    dataclasses and the test factories, ensuring the data structures
    work correctly with the testing infrastructure.
    """
    # Arrange - Create supporting data using factories pattern
    # (In real usage, these would come from the Planner reading the database)
    from tests.factories import ExperimentFactory, VariantFactory, SnapshotFactory, RunFactory

    # Create base entities using factories
    experiment = ExperimentFactory.create(
        name="test-execution-plan",
        system_prompt="Test system prompt",
        user_prompt="Test user prompt",
    )
    variant = VariantFactory.create(experiment_id=experiment.experiment_id)
    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="q1",
    )
    run = RunFactory.create(
        experiment_id=experiment.experiment_id,
        randomization_seed=42,
        status="pending",
    )

    # Build ExecutionPlan components
    prompts = Prompts(
        system="Test system prompt",
        user="Test user prompt",
    )

    plan_variant = PlanVariant(
        variant_id=variant.variant_id,
        model_id=variant.model_id,
        model_config_effective=ModelConfig(),
    )

    import json
    question_payload_dict = json.loads(snapshot.question_payload)
    question_payload = QuestionPayload(
        stem=question_payload_dict["stem"],
        options=question_payload_dict["options"],
        answer_key=question_payload_dict["answer_key"],
    )

    plan_item = PlanItem(
        item_id=f"{run.run_id}::{variant.variant_id}::{snapshot.snapshot_id}::it-1",
        run_id=run.run_id,
        variant_id=variant.variant_id,
        snapshot_id=snapshot.snapshot_id,
        question_id=snapshot.json_question_id,
        question_payload=question_payload,
    )

    plan_run = PlanRun(
        run_id=run.run_id,
        randomization_seed_effective=42,
        prompts_effective=prompts,
        retry_policy=RetryPolicy(),
        variants=[plan_variant],
        items=[plan_item],
    )

    # Act - Create ExecutionPlan
    plan = ExecutionPlan(
        plan_id=f"plan-{experiment.experiment_id}",
        created_at=datetime.now(),
        experiment_id=experiment.experiment_id,
        runs=[plan_run],
    )

    # Assert
    assert plan.plan_id.startswith("plan-")
    assert plan.experiment_id == experiment.experiment_id
    assert len(plan.runs) == 1
    assert len(plan.runs[0].variants) == 1
    assert len(plan.runs[0].items) == 1

    # Verify the complete structure is immutable
    with pytest.raises(FrozenInstanceError):
        plan.experiment_id = "changed"  # type: ignore[misc]
