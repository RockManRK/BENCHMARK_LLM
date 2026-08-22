"""TO-BE database entity models.

Dataclasses matching the TO-BE schema exactly.
Each dataclass corresponds to one database table.

Usage:
    from src.db.models import Experiment, ModelVariant, QuestionSnapshot

    experiment = Experiment(
        experiment_id="exp_001",
        name="my_experiment",
        config_json="{}",
        config_hash="abc123",
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
        created_at: Creation timestamp (auto-set by DB)
    """
    experiment_id: str
    name: str
    description: str | None = None
    config_json: str = "{}"
    config_hash: str = ""
    created_at: str | None = None


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
    """
    variant_id: str
    experiment_id: str
    model_id: str
    variant_signature: str
    config: str = "{}"
    created_at: str | None = None


@dataclass
class QuestionSnapshot:
    """Question snapshot entity matching TO-BE schema.

    Questions are snapshotted into experiments for reproducibility.
    Snapshots are immutable after creation.

    Attributes:
        snapshot_id: Primary key (UUID format recommended)
        experiment_id: Foreign key to experiments
        json_question_id: Original dataset ID (e.g., "Q001")
        question_position: 1-based position in file (user-facing)
        question_payload: Complete question JSON (stem, options, answer_key)
        created_at: Creation timestamp (auto-set by DB)
    """
    snapshot_id: str
    experiment_id: str
    json_question_id: str
    question_position: int
    question_payload: str
    created_at: str | None = None


@dataclass
class Run:
    """Run entity matching TO-BE schema.

    A Run is a concrete execution instance of an experiment.

    Attributes:
        run_id: Primary key (UUID format recommended)
        experiment_id: Foreign key to experiments
        config: All run configurations (seed, prompts, etc.) as JSON string
        status: 'pending', 'completed', 'failed', 'partial_failed'
        duration: Accumulated execution time in milliseconds (for partial runs)
        created_at: Creation timestamp (auto-set by DB)
    """
    run_id: str
    experiment_id: str
    config: str = "{}"
    status: str = "pending"
    duration: int = 0
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
        status: Response processing status
        finish_reason: finish_reason value from API response
        error_details: Any errors returned in the API response
        response_text: Full model response text
        selected_answer: Parsed answer (A/B/C/D)
        is_correct: Whether answer matches answer_key (derived)
        parse_confidence: 'unknown', 'clear', 'ambiguous', 'no_answer', 'low_confidence'
        review_status: Manual review status ('needs_review', 'reviewed', etc.)
        manual_answer: Human override (optional)
        raw_response: Complete JSON response from API
        raw_response_consolidated: Consolidated/deduplicated raw response
            JSON (see src/core/result_writer.py's serialization) — distinct
            from raw_response, which is the response as originally
            received.
        request_json: The exact request payload sent to the API (audit
            fidelity — see docs/contracts/idempotency.md's Implementation
            Pattern and docs/status/model-seed-checkpoint-b-design.md).
        cost: Cost value from API response
        input_tokens: Number of input tokens used
        response_tokens: Number of response tokens (completion_tokens)
        reasoning_tokens: Number of reasoning tokens
        effective_tokens: Sum of input + response + reasoning tokens
        latency_ms: API call latency in milliseconds
        started_at: Local timestamp when request was sent
        finished_at: Local timestamp when response was fully received

        # Experimental context (randomization tracking — see
        # src/core/execution_engine.py::ExecutionResult's own docstring
        # for the full randomization contract these fields preserve)
        randomization_enabled: Whether answer options were randomized for
            this response.
        randomization_seed: Seed used for randomization (None if disabled).
        options_presented: Options exactly as presented to the LLM (JSON
            list, in presented order — never "de-randomized").
        correct_option_presented: Correct answer letter in the presented
            option space (not necessarily the original answer_key letter).
        option_letter_map: JSON mapping from presented letter to original
            letter.
    """
    response_id: str
    run_id: str
    variant_id: str
    snapshot_id: str
    model_id: str
    question_id: str
    status: str | None = None
    finish_reason: str | None = None
    error_details: str | None = None
    response_text: str | None = None
    selected_answer: str | None = None
    is_correct: bool | None = None
    parse_confidence: str = "unknown"
    review_status: str | None = None
    manual_answer: str | None = None
    raw_response: str | None = None
    raw_response_consolidated: str | None = None
    request_json: str | None = None
    cost: float | None = None
    input_tokens: int | None = None
    response_tokens: int | None = None
    reasoning_tokens: int | None = None
    effective_tokens: int | None = None
    latency_ms: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    randomization_enabled: bool = False
    randomization_seed: int | None = None
    options_presented: str | None = None
    correct_option_presented: str | None = None
    option_letter_map: str | None = None


