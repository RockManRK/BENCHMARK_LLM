"""Data models for the benchmark_llm database layer.

This module defines dataclasses representing the entities stored in the
SQLite database, providing type-safe data structures for database operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Run:
    """Represents a benchmark test run.

    A run is a complete execution of the benchmark with specific configuration,
    potentially containing multiple iterations for different models.

    Attributes:
        run_id: Unique identifier for the run.
        created_at: Timestamp when the run was created.
        config: JSON string containing run configuration.
        status: Current status of the run (pending, running, completed, failed).

    Example:
        >>> run = Run(
        ...     run_id="run-001",
        ...     created_at=datetime.now(),
        ...     config='{"models": ["gpt-4"], "iterations": 3}',
        ...     status="running"
        ... )
        >>> print(run.run_id)
        run-001
    """

    run_id: str
    created_at: datetime = field(default_factory=datetime.now)
    config: str = "{}"
    status: str = "pending"


@dataclass
class Model:
    """Represents an LLM model being benchmarked.

    Attributes:
        model_id: Unique identifier for the model.
        model_name: Human-readable name of the model.
        provider: Name of the model provider (e.g., OpenAI, Anthropic).
        metadata: JSON string with model metadata (n_params, size, etc.).
        context_length: Context window size in tokens.
        max_completion_tokens: Maximum completion tokens.

    Example:
        >>> model = Model(
        ...     model_id="gpt-4",
        ...     model_name="GPT-4",
        ...     provider="OpenAI"
        ... )
        >>> print(model.model_name)
        GPT-4
    """

    model_id: str
    model_name: str
    provider: str
    metadata: str = "{}"
    context_length: Optional[int] = None
    max_completion_tokens: Optional[int] = None


@dataclass
class Question:
    """Represents a question from the benchmark questionnaire.

    This is a transient data class used during test execution.
    Questions are not stored directly in the database but are
    embedded in Response records.

    Attributes:
        question_id: Unique identifier for the question.
        question_text: The text content of the question.
        options: Dictionary of answer options (letter -> text).
        correct_answer: The correct answer letter.
        has_image: Whether the question includes an image.
        image_path: Path to the image file if has_image is True.
        has_table: Whether the question includes a table.
        metadata: Additional metadata about the question.

    Example:
        >>> question = Question(
        ...     question_id="Q001",
        ...     question_text="What is the capital of France?",
        ...     options={"A": "Paris", "B": "London"},
        ...     correct_answer="A"
        ... )
        >>> print(question.question_text)
        What is the capital of France?
    """

    question_id: str
    question_text: str
    options: dict[str, str] = field(default_factory=dict)
    correct_answer: str = ""
    has_image: bool = False
    image_path: Optional[str] = None
    has_table: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class Response:
    """Represents a model's response to a question.

    This is the core data structure for storing benchmark results,
    capturing all metrics and outcomes from a single question attempt.

    Attributes:
        response_id: Auto-incrementing unique identifier.
        iteration_id: ID of the iteration this response belongs to.
        question_id: ID of the question being answered.
        model_id: ID of the model that generated the response.
        run_id: ID of the run this response belongs to.
        question_text: The text of the question (denormalized for analysis).
        options_json: JSON string of answer options.
        options_randomized: Whether options were randomized.
        selected_answer: The answer letter selected by the model.
        correct_answer: The correct answer letter.
        is_correct: Whether the selected answer is correct.
        response_text: Full text response from the model.
        input_tokens: Number of tokens in the request.
        output_tokens: Number of tokens in the response.
        latency_ms: Response time in milliseconds.
        timestamp: When the response was received.
        status: Response status (pending, success, error, unsupported).

    Example:
        >>> response = Response(
        ...     iteration_id=1,
        ...     question_id="Q001",
        ...     model_id="gpt-4",
        ...     run_id="run-001",
        ...     question_text="What is 2+2?",
        ...     options_json='{"A": "3", "B": "4"}',
        ...     selected_answer="B",
        ...     correct_answer="B",
        ...     is_correct=True,
        ...     response_text="The answer is 4",
        ...     input_tokens=50,
        ...     output_tokens=10,
        ...     latency_ms=1200,
        ...     status="success"
        ... )
        >>> print(response.is_correct)
        True
    """

    iteration_id: int
    question_id: str
    model_id: str
    run_id: str
    question_text: str
    options_json: str
    response_id: Optional[int] = None
    options_randomized: bool = False
    selected_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    response_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "pending"


@dataclass
class Error:
    """Represents an error that occurred during test execution.

    Errors are tracked separately from responses to enable detailed
    error analysis and debugging.

    Attributes:
        error_id: Auto-incrementing unique identifier.
        response_id: ID of the response this error is associated with.
        error_type: Type/category of the error (e.g., APIError, TimeoutError).
        error_message: Human-readable error message.
        stack_trace: Full stack trace if available.
        timestamp: When the error occurred.

    Example:
        >>> error = Error(
        ...     response_id=1,
        ...     error_type="APIError",
        ...     error_message="Rate limit exceeded",
        ...     stack_trace="Traceback (most recent call last):..."
        ... )
        >>> print(error.error_type)
        APIError
    """

    response_id: int
    error_type: str
    error_message: str
    error_id: Optional[int] = None
    stack_trace: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Iteration:
    """Represents a single iteration of testing for a model within a run.

    Iterations enable statistical analysis by allowing multiple runs
    of the same test configuration.

    Attributes:
        iteration_id: Auto-incrementing unique identifier.
        run_id: ID of the run this iteration belongs to.
        model_id: ID of the model being tested.
        iteration_number: Sequential number of this iteration within the run.
        started_at: When the iteration started.
        completed_at: When the iteration completed (None if still running).
        status: Current status (running, completed, failed).

    Example:
        >>> iteration = Iteration(
        ...     run_id="run-001",
        ...     model_id="gpt-4",
        ...     iteration_number=1,
        ...     started_at=datetime.now(),
        ...     status="running"
        ... )
        >>> print(iteration.iteration_number)
        1
    """

    run_id: str
    model_id: str
    iteration_number: int
    started_at: datetime = field(default_factory=datetime.now)
    iteration_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    status: str = "running"


@dataclass
class OperationalLog:
    """Represents an operational log entry.

    Note: Operational logs are primarily written to .log files.
    This dataclass is provided for potential future database logging.

    Attributes:
        log_id: Auto-incrementing unique identifier.
        run_id: ID of the run this log belongs to.
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        message: Log message content.
        timestamp: When the log entry was created.
    """

    run_id: str
    level: str
    message: str
    log_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
