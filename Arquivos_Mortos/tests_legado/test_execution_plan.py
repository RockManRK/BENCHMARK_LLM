"""Tests for execution_plan module.

This module tests the ExecutionPlan data structures and utility functions.
"""

import pytest
from datetime import datetime

from src.core.execution_plan import (
    PlanItem,
    PlanVariant,
    PlanRun,
    ExecutionPlan,
    ExecutionResult,
    generate_plan_id,
    generate_item_id,
)


class TestPlanItem:
    """Tests for PlanItem dataclass."""

    def test_create_plan_item(self):
        """Test creating a PlanItem with all required fields."""
        item = PlanItem(
            item_id="run-001::var-abc::123::it-1",
            run_id="run-001",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id=123,
            question_id="Q001",
            iteration_number=1,
            question_payload={"stem": "What is 2+2?", "options": {"A": "4", "B": "5"}},
        )

        assert item.item_id == "run-001::var-abc::123::it-1"
        assert item.run_id == "run-001"
        assert item.variant_id == "var-abc"
        assert item.model_id == "openai/gpt-4"
        assert item.snapshot_id == 123
        assert item.question_id == "Q001"
        assert item.iteration_number == 1
        assert item.question_payload["stem"] == "What is 2+2?"

    def test_plan_item_default_values(self):
        """Test that PlanItem has no default values (all required)."""
        # All fields are required, so this should work without defaults
        item = PlanItem(
            item_id="test",
            run_id="test",
            variant_id="test",
            model_id="test",
            snapshot_id=1,
            question_id="test",
            iteration_number=1,
            question_payload={},
        )
        assert item is not None


class TestPlanVariant:
    """Tests for PlanVariant dataclass."""

    def test_create_plan_variant(self):
        """Test creating a PlanVariant with model config."""
        variant = PlanVariant(
            variant_id="var-abc123",
            model_id="openai/gpt-4",
            model_config={
                "reasoning_mode": "off",
                "vision_enabled": False,
                "structured_enabled": False,
            },
        )

        assert variant.variant_id == "var-abc123"
        assert variant.model_id == "openai/gpt-4"
        assert variant.model_config["reasoning_mode"] == "off"

    def test_plan_variant_empty_config(self):
        """Test PlanVariant with empty config (uses default_factory)."""
        variant = PlanVariant(
            variant_id="var-abc",
            model_id="openai/gpt-4",
        )

        assert variant.model_config == {}


class TestPlanRun:
    """Tests for PlanRun dataclass."""

    def test_create_plan_run(self):
        """Test creating a PlanRun with variants and items."""
        variant = PlanVariant(
            variant_id="var-abc",
            model_id="openai/gpt-4",
            model_config={},
        )

        item = PlanItem(
            item_id="run-001::var-abc::123::it-1",
            run_id="run-001",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id=123,
            question_id="Q001",
            iteration_number=1,
            question_payload={},
        )

        run = PlanRun(
            run_id="run-001",
            seed_effective=42,
            system_prompt="You are helpful.",
            user_prompt="Answer the question.",
            variants=[variant],
            items=[item],
        )

        assert run.run_id == "run-001"
        assert run.seed_effective == 42
        assert len(run.variants) == 1
        assert len(run.items) == 1

    def test_plan_run_seed_none(self):
        """Test that PlanRun accepts seed=None (no randomization)."""
        run = PlanRun(
            run_id="run-001",
            seed_effective=None,
            system_prompt="You are helpful.",
            user_prompt="Answer the question.",
            variants=[],
            items=[],
        )

        assert run.seed_effective is None


class TestExecutionPlan:
    """Tests for ExecutionPlan dataclass."""

    def test_create_execution_plan(self):
        """Test creating an ExecutionPlan."""
        run = PlanRun(
            run_id="run-001",
            seed_effective=42,
            system_prompt="You are helpful.",
            user_prompt="Answer the question.",
            variants=[],
            items=[],
        )

        plan = ExecutionPlan(
            plan_id="plan-20260318-001-abc123",
            created_at=datetime.now(),
            experiment_id="exp-abc123",
            experiment_name="test_experiment",
            runs=[run],
        )

        assert plan.plan_id == "plan-20260318-001-abc123"
        assert plan.experiment_id == "exp-abc123"
        assert plan.experiment_name == "test_experiment"
        assert len(plan.runs) == 1


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful ExecutionResult."""
        result = ExecutionResult(
            item_id="run-001::var-abc::123::it-1",
            run_id="run-001",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id=123,
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

        assert result.status == "success"
        assert result.selected_answer == "B"
        assert result.is_correct is True
        assert result.latency_ms == 1200

    def test_create_failure_result(self):
        """Test creating a failed ExecutionResult."""
        result = ExecutionResult(
            item_id="run-001::var-abc::123::it-1",
            run_id="run-001",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id=123,
            question_id="Q001",
            iteration_number=1,
            status="failure",
            response_text="",
            selected_answer=None,
            is_correct=None,
            latency_ms=100,
            input_tokens=0,
            output_tokens=0,
        )

        assert result.status == "failure"
        assert result.selected_answer is None
        assert result.is_correct is None


class TestGeneratePlanId:
    """Tests for generate_plan_id function."""

    def test_generate_plan_id_format(self):
        """Test that plan ID has correct format."""
        plan_id = generate_plan_id("exp-abc123")

        # Should be: plan-YYYYMMDDHHMMSS-8charhash
        assert plan_id.startswith("plan-")
        parts = plan_id.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 14  # timestamp
        assert len(parts[2]) == 8  # hash

    def test_generate_plan_id_deterministic(self):
        """Test that plan ID is deterministic for same input."""
        timestamp = datetime(2026, 3, 18, 12, 0, 0)
        plan_id1 = generate_plan_id("exp-abc123", timestamp)
        plan_id2 = generate_plan_id("exp-abc123", timestamp)

        assert plan_id1 == plan_id2

    def test_generate_plan_id_unique(self):
        """Test that different experiments produce different IDs."""
        timestamp = datetime(2026, 3, 18, 12, 0, 0)
        plan_id1 = generate_plan_id("exp-abc123", timestamp)
        plan_id2 = generate_plan_id("exp-xyz789", timestamp)

        # Hashes should be different
        assert plan_id1 != plan_id2


class TestGenerateItemId:
    """Tests for generate_item_id function."""

    def test_generate_item_id_format(self):
        """Test that item ID has correct format."""
        item_id = generate_item_id("run-001", "var-abc", 123, 1)

        assert item_id == "run-001::var-abc::123::it-1"

    def test_generate_item_id_unique(self):
        """Test that different combinations produce different IDs."""
        id1 = generate_item_id("run-001", "var-abc", 123, 1)
        id2 = generate_item_id("run-001", "var-abc", 124, 1)
        id3 = generate_item_id("run-001", "var-xyz", 123, 1)
        id4 = generate_item_id("run-002", "var-abc", 123, 1)

        assert id1 != id2
        assert id1 != id3
        assert id1 != id4

    def test_generate_item_id_deterministic(self):
        """Test that same inputs produce same ID."""
        id1 = generate_item_id("run-001", "var-abc", 123, 1)
        id2 = generate_item_id("run-001", "var-abc", 123, 1)

        assert id1 == id2
