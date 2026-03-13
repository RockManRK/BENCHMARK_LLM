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
        is_dev: True if run is in development mode.
        started_at: Timestamp when the run started.
        finished_at: Timestamp when the run completed.
        status: Current status (pending, running, completed, failed).

    Example:
        >>> run = Run(
        ...     run_id="run-001",
        ...     is_dev=True,
        ...     status="running"
        ... )
        >>> print(run.run_id)
        run-001
    """

    run_id: str
    is_dev: bool = True
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
        supports_multimodal: Whether the model supports multimodal input.
        metadata_json: JSON string with model metadata.
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
    supports_multimodal: bool = False
    metadata_json: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


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
        question_json: Complete JSON representation of the question.
        experiment_id: ID of the experiment this snapshot belongs to (ALWAYS required).
        snapshot_id: Auto-incrementing unique identifier (assigned by DB).
        created_at: Timestamp when the snapshot was created.

    Example:
        >>> snapshot = QuestionSnapshot(
        ...     question_id="Q001",
        ...     question_json='{"id": "Q001", "stem": "What is 2+2?", "options": {...}}',
        ...     experiment_id="exp-001"
        ... )
        >>> print(snapshot.question_id)
        Q001
    """

    question_id: str
    question_json: str
    experiment_id: str
    snapshot_id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class Response:
    """Represents a model's response to a question.

    This is the core data structure for storing benchmark results,
    capturing all metrics and outcomes from a single question attempt.

    Responses reference question_snapshots for immutability, and also
    include question_id as semantic redundancy for easier querying and
    debugging. The snapshot_id is the authoritative reference.

    Attributes:
        run_id: ID of the run this response belongs to.
        snapshot_id: ID of the question snapshot being answered (authoritative).
        question_id: ID of the question (semantic redundancy for convenience).
        model_id: ID of the model that generated the response.
        iteration: Iteration number (1-based) within the run.
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
        review_status: Review status ("auto" for auto-parsed, "manual" for manually reviewed, "skipped").
        reviewed_at: Timestamp of manual review (if manually reviewed).
        manual_answer: Answer letter assigned during manual review (if manually reviewed).

    Example:
        >>> response = Response(
        ...     run_id="run-001",
        ...     snapshot_id=1,
        ...     question_id="Q001",
        ...     model_id="gpt-4",
        ...     iteration=1,
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
    model_id: str
    iteration: int = 1
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
    review_status: str = "auto"  # "auto", "manual", "skipped"
    reviewed_at: Optional[datetime] = None
    manual_answer: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate response data after initialization.

        Ensures consistency between snapshot_id and question_id.
        """
        # Note: Full validation (checking snapshot JSON) requires database access
        # and should be done in the repository layer. This is a basic sanity check.
        if not self.snapshot_id or self.snapshot_id <= 0:
            raise ValueError("snapshot_id must be a positive integer")
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
        model_id: ID of the model that encountered the error.
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
    model_id: Optional[str] = None
    stack_trace: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
