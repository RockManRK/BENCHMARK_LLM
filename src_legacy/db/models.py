"""Data models for the benchmark_llm database layer.

This module defines dataclasses representing the entities stored in the
SQLite database, providing type-safe data structures for database operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Experiment:
    """Represents a benchmark experiment with frozen configuration.

    An experiment is a research configuration that can be reproduced
    across multiple runs. Configuration is serialized and hashed for
    auditability.

    Attributes:
        experiment_id: Unique identifier for the experiment.
        name: Human-readable experiment name (unique).
        description: Optional description of the experiment.
        config_json: JSON string containing frozen configuration.
        config_hash: SHA-256 hash of configuration for deduplication.
        system_prompt_template: System prompt template used in the experiment.
        user_prompt_template: User prompt template used in the experiment.
        created_at: Timestamp when the experiment was created.

    Example:
        >>> experiment = Experiment(
        ...     experiment_id="exp-001",
        ...     name="gpt4_vs_claude3",
        ...     config_json='{"models": ["gpt-4", "claude-3"]}',
        ...     config_hash="abc123def456"
        ... )
        >>> print(experiment.name)
        gpt4_vs_claude3
    """

    name: str
    config_json: str
    config_hash: str
    experiment_id: Optional[str] = None
    description: Optional[str] = None
    system_prompt_template: Optional[str] = None
    user_prompt_template: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Run:
    """Represents a benchmark test run.

    A run is a single execution of the benchmark. It can be associated
    with an experiment or be standalone (dev mode).

    Attributes:
        run_id: Unique identifier for the run.
        experiment_id: ID of the associated experiment (NULL for dev mode).
        seed: Random seed used for this run.
        started_at: Timestamp when the run started.
        finished_at: Timestamp when the run completed.
        status: Current status (pending, running, completed, failed).

    Example:
        >>> run = Run(
        ...     run_id="run-001",
        ...     experiment_id="exp-001",
        ...     seed=42,
        ...     status="running"
        ... )
        >>> print(run.run_id)
        run-001
    """

    run_id: str
    experiment_id: Optional[str] = None
    seed: Optional[int] = None
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    status: str = "pending"


@dataclass
class Model:
    """Represents an LLM model being benchmarked.

    Attributes:
        model_id: Unique identifier for the model.
        provider: Name of the model provider (e.g., OpenAI, Anthropic).
        model_name: Human-readable name of the model.
        created_at: Timestamp when the model was registered.

    Example:
        >>> model = Model(
        ...     model_id="gpt-4",
        ...     provider="OpenAI",
        ...     model_name="GPT-4"
        ... )
        >>> print(model.model_name)
        GPT-4
    """

    model_id: str
    provider: str
    model_name: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ModelVariant:
    """Represents a model variant with execution parameters.

    A model variant is a unique combination of:
    - Base model (model_id)
    - Reasoning configuration (mode, effort, max_tokens)
    - Vision enabled
    - Structured outputs enabled

    Identity fields (define variant_signature):
    - reasoning_mode: 'off', 'auto', 'effort', 'budget', 'unspecified'
    - reasoning_effort: 'xhigh', 'high', 'medium', 'low', 'minimal' (when mode='effort')
    - max_output_tokens: integer (when mode='budget')
    - vision_enabled: boolean
    - structured_output: boolean

    Non-identity fields (NOT part of variant_signature):
    - temperature, top_p, top_k, max_tokens, repeat_penalty
    These are execution parameters that do NOT define variant identity.

    Attributes:
        variant_id: Short stable identifier (hash-based).
        model_id: Base model identifier (FK to models).
        reasoning_mode: Reasoning mode ('off', 'auto', 'effort', 'budget', 'unspecified').
        reasoning_effort: Reasoning effort level (when mode='effort').
        max_output_tokens: Maximum output tokens (when mode='budget').
        vision_enabled: Whether vision is enabled.
        structured_output: Whether structured outputs are enabled.
        variant_signature: Human-readable signature (unique per model_id + identity).
        created_at: Timestamp when the variant was registered.

    Example:
        >>> variant = ModelVariant(
        ...     variant_id="var-abc123",
        ...     model_id="openai/gpt-4",
        ...     reasoning_mode="auto",
        ...     vision_enabled=False,
        ...     structured_enabled=False,
        ...     variant_signature="openai/gpt-4::reasoning=auto::vision=false::structured=false"
        ... )
        >>> print(variant.variant_signature)
        openai/gpt-4::reasoning=auto::vision=false::structured=false
    """

    variant_id: str
    model_id: str
    variant_signature: str
    reasoning_mode: str = "unspecified"
    reasoning_effort: Optional[str] = None
    max_output_tokens: Optional[int] = None
    vision_enabled: bool = False
    structured_output: bool = False
    web_access_enabled: bool = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RunModel:
    """Represents the association between a run and a model variant.

    This dataclass tracks which model variants are associated with a run
    and their execution status. It allows models to be added to runs
    dynamically after the run has been created.

    Attributes:
        run_id: ID of the run.
        variant_id: ID of the model variant.
        status: Execution status ('pending', 'running', 'completed', 'removed').
        added_at: Timestamp when model was added to run.
        completed_at: Timestamp when all iterations completed (if applicable).

    Example:
        >>> run_model = RunModel(
        ...     run_id="run-20260313-abc123",
        ...     variant_id="var-abc123",
        ...     status="running"
        ... )
        >>> print(run_model.status)
        running
    """

    run_id: str
    variant_id: str
    status: str = "pending"
    added_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class Question:
    """Represents a question from the benchmark questionnaire.

    Questions are loaded from external files (JSON/CSV) and persisted
    in the database for reproducibility and audit trails.

    This is the CANONICAL CATALOG - questions can be updated here without
    affecting existing experiment results. Experiments use question_snapshots
    to ensure immutability.

    Attributes:
        question_id: Unique identifier for the question.
        stem: The question text/statement.
        options_json: JSON string containing answer options.
        correct_answer: The correct answer letter/value.
        has_image: Whether the question includes an image.
        image_path: Path to the image file if has_image is True.
        status: Question status (active, archived, draft).

    Example:
        >>> question = Question(
        ...     question_id="Q001",
        ...     stem="What is the capital of France?",
        ...     options_json='{"A": "Paris", "B": "London"}',
        ...     correct_answer="A"
        ... )
        >>> print(question.stem)
        What is the capital of France?
    """

    question_id: str
    stem: str
    options_json: str
    correct_answer: Optional[str] = None
    has_image: bool = False
    image_path: Optional[str] = None
    status: str = "active"


@dataclass
class QuestionSnapshot:
    """Represents an immutable snapshot of a question used in an experiment.

    Each snapshot captures the complete question JSON at the moment it was
    first used in an experiment, ensuring reproducibility even if the
    canonical question is later modified.

    Snapshots are created only once per (experiment_id, question_id) pair.
    Subsequent executions reuse the existing snapshot.

    IMPORTANT: Every snapshot MUST be associated with a valid experiment.
    There is NO support for experiment_id = NULL.

    Attributes:
        question_id: ID of the question this snapshot is for.
        question_payload: Complete JSON representation of the question.
        experiment_id: ID of the experiment this snapshot belongs to (ALWAYS required).
        snapshot_id: Auto-incrementing unique identifier (assigned by DB).
        created_at: Timestamp when the snapshot was created.

    Example:
        >>> snapshot = QuestionSnapshot(
        ...     question_id="Q001",
        ...     question_payload='{"id": "Q001", "stem": "What is 2+2?", "options": {...}}',
        ...     experiment_id="exp-001"
        ... )
        >>> print(snapshot.question_id)
        Q001
    """

    question_id: str
    question_payload: str
    experiment_id: str
    snapshot_id: str  # TEXT PRIMARY KEY - generated explicitly by application
    created_at: Optional[datetime] = None


@dataclass
class Response:
    """Represents a model's response to a question.

    This is the core data structure for storing benchmark results,
    capturing all metrics and outcomes from a single question attempt.

    Responses reference question_snapshots for immutability, and also
    include question_id as semantic redundancy for easier querying and
    debugging. The snapshot_id is the authoritative reference.

    IMPORTANT: Responses now reference model_variants (NOT base models)
    for accurate tracking of execution parameters.

    Attributes:
        run_id: ID of the run this response belongs to.
        snapshot_id: ID of the question snapshot being answered (authoritative).
        question_id: ID of the question (semantic redundancy for convenience).
        variant_id: ID of the model variant that generated the response.
        selected_answer: The answer letter selected by the model.
        response_text: Full text response from the model.
        is_correct: Whether the selected answer is correct.
        status: Response status (pending, success, error, unsupported).
        finish_reason: Reason for response termination (e.g., "stop", "length", "eos", "error").
        error_details: Detailed error information (e.g., full error response body) for debugging.
        latency_ms: Response time in milliseconds.
        input_tokens: Number of tokens in the request.
        response_tokens: Number of tokens in the response (completion tokens).
        total_tokens: Total tokens used (input_tokens + response_tokens, excludes reasoning_tokens).
        reasoning_tokens: Number of reasoning tokens used (NOT included in total_tokens).
        effective_tokens: Total computational cost (input_tokens + response_tokens + reasoning_tokens).
        cost: Cost in credits for this response (from usage.cost).
        raw_response_json: Complete raw API response as JSON string for debugging.
        timestamp: When the response was received.
        response_id: Auto-incrementing unique identifier (assigned by DB).
        parse_confidence: Confidence level from answer parsing ("unknown", "clear", "ambiguous", "no_answer", "low_confidence").
        needs_review: Whether this response needs manual review (derived from parse_confidence).
        manual_answer: Answer letter assigned during manual review (if manually reviewed).

    Example:
        >>> response = Response(
        ...     run_id="run-001",
        ...     snapshot_id=1,
        ...     question_id="Q001",
        ...     variant_id="var-abc123",
        ...     selected_answer="B",
        ...     is_correct=True,
        ...     input_tokens=50,
        ...     response_tokens=10,
        ...     latency_ms=1200,
        ...     status="success"
        ... )
        >>> print(response.is_correct)
        True
    """

    run_id: str
    snapshot_id: int
    question_id: str
    model_id: str  # Base model ID (for backward compatibility and easier querying)
    variant_id: str
    # iteration: int = 1  # REMOVED in TO-BE - multiple runs instead of multiple iterations
    response_id: Optional[int] = None
    selected_answer: Optional[str] = None
    response_text: str = ""
    is_correct: Optional[bool] = None
    status: str = "pending"
    finish_reason: Optional[str] = None
    error_details: Optional[str] = None
    latency_ms: int = 0
    input_tokens: int = 0
    response_tokens: int = 0
    total_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    effective_tokens: Optional[int] = None
    cost: Optional[float] = None
    raw_response_json: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    # Manual review fields
    parse_confidence: str = "unknown"  # "unknown", "clear", "ambiguous", "no_answer", "low_confidence"
    needs_review: bool = False
    manual_answer: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate response data after initialization.

        Ensures snapshot_id is a non-empty string.
        """
        if not self.snapshot_id or not isinstance(self.snapshot_id, str):
            raise ValueError("snapshot_id must be a non-empty string")
        if not self.question_id or not isinstance(self.question_id, str):
            raise ValueError("question_id must be a non-empty string")


@dataclass
class Error:
    """Represents an error that occurred during test execution.

    Errors are tracked separately from responses to enable detailed
    error analysis and debugging.

    Attributes:
        error_type: Type/category of the error (e.g., APIError, TimeoutError).
        error_message: Human-readable error message.
        run_id: ID of the run this error belongs to.
        question_id: ID of the question being answered when error occurred.
        variant_id: ID of the model variant that encountered the error.
        stack_trace: Full stack trace if available.
        timestamp: When the error occurred.
        error_id: Auto-incrementing unique identifier.

    Example:
        >>> error = Error(
        ...     error_type="APIError",
        ...     error_message="Rate limit exceeded",
        ...     run_id="run-001",
        ...     stack_trace="Traceback (most recent call last):..."
        ... )
        >>> print(error.error_type)
        APIError
    """

    error_type: str
    error_message: str
    error_id: Optional[int] = None
    run_id: Optional[str] = None
    question_id: Optional[str] = None
    variant_id: Optional[str] = None
    stack_trace: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
