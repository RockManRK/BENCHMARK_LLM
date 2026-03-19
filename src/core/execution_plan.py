"""Execution Plan data structures for benchmark_llm.

This module defines immutable data structures representing the work to execute.
The ExecutionPlan is the contract between Planner and ExecutionEngine.

Design Principles:
    - ExecutionPlan is immutable after creation
    - ExecutionPlan is self-contained (no external config resolution needed)
    - ExecutionPlan is serializable for audit/replay

Example:
    >>> plan = ExecutionPlan(
    ...     plan_id="plan-20260318-001",
    ...     created_at=datetime.now(),
    ...     experiment_id="exp-abc123",
    ...     experiment_name="test_exp",
    ...     runs=[...]
    ... )
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import hashlib
import json


@dataclass
class PlanItem:
    """Single executable unit: one variant + one snapshot + one iteration.

    This is the smallest unit of execution. Each PlanItem represents
    one question being answered by one model variant in one iteration.

    Attributes:
        item_id: Unique identifier for this item (format: run::variant::snapshot::iteration)
        run_id: ID of the run this item belongs to
        variant_id: ID of the model variant to execute
        model_id: Base model identifier (e.g., "openai/gpt-4")
        snapshot_id: ID of the question snapshot to execute
        question_id: Question identifier (e.g., "Q001")
        iteration_number: Iteration number (always 1 in current model)
        question_payload: Complete question JSON for execution

    Example:
        >>> item = PlanItem(
        ...     item_id="run-001::var-abc::snap-123::it-1",
        ...     run_id="run-001",
        ...     variant_id="var-abc",
        ...     model_id="openai/gpt-4",
        ...     snapshot_id=123,
        ...     question_id="Q001",
        ...     iteration_number=1,
        ...     question_payload={"stem": "...", "options": {...}}
        ... )
    """

    item_id: str
    run_id: str
    variant_id: str
    model_id: str
    snapshot_id: int
    question_id: str
    iteration_number: int
    question_payload: dict[str, Any]


@dataclass
class PlanVariant:
    """Model variant with resolved configuration.

    Contains all configuration needed to execute a model variant.
    Configuration is fully resolved (no fallback to global settings).

    Attributes:
        variant_id: Model variant identifier
        model_id: Base model identifier (e.g., "openai/gpt-4")
        model_config: Complete configuration for API calls

    Example:
        >>> variant = PlanVariant(
        ...     variant_id="var-abc123",
        ...     model_id="openai/gpt-4",
        ...     model_config={
        ...         "vision_enabled": False,
        ...         "structured_output": False,
        ...         "reasoning_mode": "off"
        ...     }
        ... )
    """

    variant_id: str
    model_id: str
    model_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanRun:
    """Run with resolved configuration.

    Contains all configuration needed to execute a run.
    All values are resolved (run overrides experiment).

    Attributes:
        run_id: Run identifier
        seed_effective: Seed value for randomization (None = no randomization)
        system_prompt: System prompt template (run overrides experiment)
        user_prompt: User prompt template (run overrides experiment)
        variants: List of model variants to execute
        items: List of executable items for this run

    Example:
        >>> run = PlanRun(
        ...     run_id="run-001",
        ...     seed_effective=42,
        ...     system_prompt="You are a helpful assistant.",
        ...     user_prompt="Answer the following question:",
        ...     variants=[...],
        ...     items=[...]
        ... )

    Note:
        seed_effective may be None, which means:
        - No randomization is applied
        - Questions are executed in natural snapshot order
        - Execution is deterministic by construction (not by RNG)
    """

    run_id: str
    seed_effective: Optional[int]
    system_prompt: str
    user_prompt: str
    variants: list[PlanVariant]
    items: list[PlanItem]


@dataclass
class ExecutionPlan:
    """Complete immutable execution plan.

    This is the contract between Planner and ExecutionEngine.
    Once created, this plan cannot be modified.

    Attributes:
        plan_id: Unique plan identifier (format: plan-{timestamp}-{hash})
        created_at: Timestamp when plan was created
        experiment_id: Experiment identifier
        experiment_name: Human-readable experiment name
        runs: List of runs to execute

    Example:
        >>> plan = ExecutionPlan(
        ...     plan_id="plan-20260318-001-abc123",
        ...     created_at=datetime.now(),
        ...     experiment_id="exp-abc123",
        ...     experiment_name="test_experiment",
        ...     runs=[...]
        ... )
    """

    plan_id: str
    created_at: datetime
    experiment_id: str
    experiment_name: str
    runs: list[PlanRun]


@dataclass
class ExecutionResult:
    """Result of executing one PlanItem.

    Minimal result structure for first implementation.
    Optional fields stubbed as None for future expansion.

    Attributes:
        item_id: ID of the executed item
        run_id: ID of the run
        variant_id: ID of the model variant
        model_id: Base model identifier
        snapshot_id: ID of the question snapshot
        question_id: Question identifier
        iteration_number: Iteration number (always 1)
        status: Execution status ("success" or "failure")
        response_text: Model's response text
        selected_answer: Answer selected by model (A, B, C, D)
        is_correct: Whether answer matches correct_answer
        latency_ms: API call latency in milliseconds
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        error_type: Type of error (for failures)
        error_message: Error message (for failures)

    Example:
        >>> result = ExecutionResult(
        ...     item_id="run-001::var-abc::snap-123::it-1",
        ...     run_id="run-001",
        ...     variant_id="var-abc",
        ...     model_id="openai/gpt-4",
        ...     snapshot_id=123,
        ...     question_id="Q001",
        ...     iteration_number=1,
        ...     status="success",
        ...     response_text="The answer is B",
        ...     selected_answer="B",
        ...     is_correct=True,
        ...     latency_ms=1200,
        ...     input_tokens=50,
        ...     output_tokens=10
        ... )
    """

    item_id: str
    run_id: str
    variant_id: str
    model_id: str
    snapshot_id: int
    question_id: str
    iteration_number: int
    status: str  # Literal["success", "failure"]
    response_text: str
    selected_answer: Optional[str]
    is_correct: Optional[bool]
    latency_ms: int
    input_tokens: int
    output_tokens: int
    error_type: Optional[str] = None
    error_message: Optional[str] = None


def generate_plan_id(experiment_id: str, timestamp: Optional[datetime] = None) -> str:
    """Generate unique plan identifier.

    Format: plan-{YYYYMMDDHHMMSS}-{8-char-hash}

    The hash includes experiment_id and timestamp for uniqueness.

    Args:
        experiment_id: Experiment identifier to include in hash
        timestamp: Optional timestamp (uses current time if None)

    Returns:
        Unique plan identifier

    Example:
        >>> generate_plan_id("exp-abc123")
        'plan-20260318120000-a1b2c3d4'
    """
    if timestamp is None:
        timestamp = datetime.now()

    timestamp_str = timestamp.strftime("%Y%m%d%H%M%S")

    # Generate hash from experiment_id and timestamp
    hash_input = f"{experiment_id}:{timestamp_str}"
    hash_hex = hashlib.sha256(hash_input.encode()).hexdigest()[:8]

    return f"plan-{timestamp_str}-{hash_hex}"


def generate_item_id(run_id: str, variant_id: str, snapshot_id: int) -> str:
    """Generate unique item identifier.

    Format: {run_id}::{variant_id}::{snapshot_id}

    Args:
        run_id: Run identifier
        variant_id: Model variant identifier
        snapshot_id: Question snapshot identifier

    Returns:
        Unique item identifier

    Example:
        >>> generate_item_id("run-001", "var-abc", 123)
        'run-001::var-abc::123'
    """
    return f"{run_id}::{variant_id}::{snapshot_id}"
