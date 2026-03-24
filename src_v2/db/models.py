"""TO-BE database entity models.

Dataclasses matching the TO-BE schema exactly.
Each dataclass corresponds to one database table.

Usage:
    from src_v2.db.models import Experiment, ModelVariant, QuestionSnapshot

    experiment = Experiment(
        experiment_id="exp_001",
        name="my_experiment",
        config_json="{}",
        config_hash="abc123",
        system_prompt="...",
        user_prompt="...",
    )
"""

from dataclasses import dataclass, field


@dataclass
class Experiment:
    """Experiment entity matching TO-BE schema.

    Attributes:
        experiment_id: Primary key (UUID format recommended)
        name: Human-readable unique name
        description: Optional description
        config_json: Frozen configuration snapshot (JSON string)
        config_hash: SHA-256 hash of protocol config
        system_prompt: System prompt template (None = not provided)
        user_prompt: User prompt template (None = not provided)
        created_at: Creation timestamp (auto-set by DB)
        is_active: Soft delete flag (TRUE = active)
    """
    experiment_id: str
    name: str
    description: str | None = None
    config_json: str = "{}"
    config_hash: str = ""
    system_prompt: str | None = None
    user_prompt: str | None = None
    created_at: str | None = None
    is_active: bool = True


@dataclass
class ModelVariant:
    """Model variant entity matching TO-BE schema.

    A ModelVariant represents an intentional configuration of a base model.
    Variants belong to experiments (not global).

    Attributes:
        variant_id: Primary key (UUID format recommended)
        experiment_id: Foreign key to experiments
        model_id: Base model identifier (e.g., "openai/gpt-4")
        variant_signature: Human-readable identity within experiment
        config: Full execution configuration as JSON string
        created_at: Creation timestamp (auto-set by DB)
        is_active: Soft delete flag
    """
    variant_id: str
    experiment_id: str
    model_id: str
    variant_signature: str
    config: str = "{}"
    created_at: str | None = None
    is_active: bool = True


@dataclass
class QuestionSnapshot:
    """Question snapshot entity matching TO-BE schema.

    Questions are snapshotted into experiments for reproducibility.
    Snapshots are immutable after creation.

    Attributes:
        snapshot_id: Primary key (UUID format recommended)
        experiment_id: Foreign key to experiments
        question_id: Original question identifier
        question_payload: Complete question JSON (stem, options, answer_key)
        created_at: Creation timestamp (auto-set by DB)
        is_active: Soft delete flag
    """
    snapshot_id: str
    experiment_id: str
    question_id: str
    question_payload: str
    created_at: str | None = None
    is_active: bool = True


@dataclass
class Run:
    """Run entity matching TO-BE schema.

    A Run is a concrete execution instance of an experiment.

    Attributes:
        run_id: Primary key (UUID format recommended)
        experiment_id: Foreign key to experiments
        seed: Random seed for answer shuffling (None = no shuffling)
        status: 'pending', 'running', 'completed', 'failed', 'partial_failed'
        started_at: Execution start timestamp
        finished_at: Execution end timestamp
        created_at: Creation timestamp (auto-set by DB)
    """
    run_id: str
    experiment_id: str
    seed: int | None = None
    status: str = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None


@dataclass
class Response:
    """Response entity matching TO-BE schema.

    A Response is the result of executing one model variant against one question.

    Attributes:
        response_id: Primary key (UUID format recommended)
        run_id: Foreign key to runs
        variant_id: Foreign key to model_variants
        snapshot_id: Foreign key to question_snapshots
        model_id: Base model identifier (redundant for querying)
        question_id: Original question identifier (redundant for querying)
        response_text: Full model response text
        selected_answer: Parsed answer (A/B/C/D)
        is_correct: Whether answer matches answer_key (derived)
        parse_confidence: 'unknown', 'clear', 'ambiguous', 'no_answer', 'low_confidence'
        needs_review: Requires human review (derived from parse_confidence)
        manual_answer: Human override (optional)
        latency_ms: API call latency in milliseconds
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated
        created_at: Creation timestamp (auto-set by DB)
    """
    response_id: str
    run_id: str
    variant_id: str
    snapshot_id: str
    model_id: str
    question_id: str
    response_text: str | None = None
    selected_answer: str | None = None
    is_correct: bool | None = None
    parse_confidence: str = "unknown"
    needs_review: bool = False
    manual_answer: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: str | None = None


@dataclass
class Error:
    """Error entity matching TO-BE schema.

    An Error records a failure during execution.

    Attributes:
        error_id: Primary key (UUID format recommended)
        run_id: Foreign key to runs
        variant_id: Foreign key to model_variants
        snapshot_id: Foreign key to question_snapshots
        model_id: Base model identifier (redundant for querying)
        question_id: Original question identifier (redundant for querying)
        error_type: 'api_error', 'timeout', 'parse_error', 'config_error'
        error_message: Human-readable error message
        attempt_count: Number of retry attempts made
        stack_trace: Optional stack trace
        created_at: Creation timestamp (auto-set by DB)
    """
    error_id: str
    run_id: str
    variant_id: str
    snapshot_id: str
    model_id: str
    question_id: str
    error_type: str
    error_message: str
    attempt_count: int = 1
    stack_trace: str | None = None
    created_at: str | None = None
