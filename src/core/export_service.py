"""Export service for benchmark results.

This module provides read-only export functionality for external analysis
and auditing. It is a validation and observability component — no execution
behavior is modified.

Usage:
    from src.core.export_service import ExportService
    
    conn = get_database_connection()
    export_service = ExportService(conn)
    result = export_service.export_run(run_id)
    json_output = result.to_json()
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import sqlite3

from src.db.repository import ResponseRepository, RunRepository, ExperimentRepository
from src.db.models import Response
from src.utils.logging_config import get_logger

_logger = get_logger('core.export_service')


@dataclass
class ExportedResponse:
    """Exported response record with computed fields.
    
    Attributes:
        response_id: Primary key from responses table
        question_id: Original question identifier
        variant_id: Model variant identifier
        model_id: Base model identifier
        snapshot_id: Question snapshot identifier
        run_id: Run identifier
        selected_answer: Parsed answer from model (A/B/C/D)
        manual_answer: Human-corrected answer (if reviewed)
        final_answer: Computed: manual_answer OR selected_answer
        answer_source: Computed: 'manual', 'automatic', or None
        is_correct: Whether final_answer matches answer_key
        parse_confidence: Parser confidence level
        latency_ms: API call latency in milliseconds
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens (mapped from response_tokens in DB)
        reasoning_tokens: Number of reasoning tokens
        effective_tokens: Computed: input + output + reasoning tokens
        status: Response processing status
        error_details: Any errors from API response
        cost: Cost value from API response
        started_at: Local timestamp when request was sent
        finished_at: Local timestamp when response was received
        request_json: Exact request payload sent to the API (audit
            fidelity — ENT-02 fix, 2026-08-21: previously silently
            omitted from every export, with no error, because it was
            missing from Response/ResponseRepository entirely).
        raw_response_consolidated: Consolidated raw response JSON.
        randomization_enabled: Whether answer options were randomized.
        randomization_seed: Seed used for randomization (None if disabled).
        options_presented: Options exactly as presented to the LLM (JSON).
        correct_option_presented: Correct answer letter in the presented
            option space.
        option_letter_map: JSON mapping from presented letter to original
            letter.
    """

    response_id: str
    question_id: str
    variant_id: str
    model_id: str
    snapshot_id: str
    run_id: str
    selected_answer: Optional[str]
    manual_answer: Optional[str]
    final_answer: Optional[str]
    answer_source: Literal['manual', 'automatic', None]
    is_correct: Optional[bool]
    parse_confidence: str
    latency_ms: Optional[int]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    reasoning_tokens: Optional[int]
    effective_tokens: Optional[int]
    status: Optional[str]
    error_details: Optional[str]
    cost: Optional[float]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    request_json: Optional[str]
    raw_response_consolidated: Optional[str]
    randomization_enabled: bool
    randomization_seed: Optional[int]
    options_presented: Optional[str]
    correct_option_presented: Optional[str]
    option_letter_map: Optional[str]


@dataclass
class ExportedError:
    """Exported error record.

    Attributes:
        error_id: Primary key from errors table
        response_id: Canonical response identifier (error versioning key)
        attempt_number: Attempt counter for this response (error versioning)
        question_id: Original question identifier
        variant_id: Model variant identifier
        snapshot_id: Question snapshot identifier
        run_id: Run identifier
        error_type: Type of error (api_error, timeout, parse_error, config_error)
        error_message: Human-readable error message
        attempt_count: Number of retry attempts made
        occurred_at: Error occurrence timestamp
    """

    error_id: str
    response_id: str
    attempt_number: int
    question_id: str
    variant_id: str
    snapshot_id: str
    run_id: str
    error_type: str
    error_message: str
    attempt_count: int
    occurred_at: Optional[datetime]


@dataclass
class ExportResult:
    """Complete export result with metadata.
    
    Attributes:
        export_version: Version of export format (for reproducibility)
        exported_at: ISO timestamp when export was generated
        experiment_name: Human-readable experiment name (for context)
        run_id: Run identifier being exported
        total_responses: Count of response records
        total_errors: Count of error records
        responses: List of exported response dictionaries
        errors: List of exported error dictionaries
    """
    
    export_version: str = "1.0"
    exported_at: Optional[str] = None
    experiment_name: Optional[str] = None
    run_id: Optional[str] = None
    total_responses: int = 0
    total_errors: int = 0
    responses: list[dict] = None
    errors: list[dict] = None
    
    def __post_init__(self):
        if self.responses is None:
            self.responses = []
        if self.errors is None:
            self.errors = []
        if self.exported_at is None:
            self.exported_at = datetime.now(timezone.utc).isoformat()
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string.
        
        Args:
            indent: JSON indentation level (default: 2)
        
        Returns:
            JSON string representation of export result.
        """
        return json.dumps(self.__dict__, indent=indent, default=str)
    
    def to_dict(self) -> dict:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation of export result.
        """
        return self.__dict__


class ExportService:
    """Service for exporting benchmark results.
    
    This service is READ-ONLY and does not modify database state.
    It provides deterministic, reproducible output for external analysis.
    
    Usage:
        conn = get_database_connection()
        export_service = ExportService(conn)
        result = export_service.export_run("run_abc123")
        print(result.to_json())
    """
    
    def __init__(self, conn: sqlite3.Connection):
        """Initialize export service with database connection.
        
        Args:
            conn: SQLite database connection.
        """
        self._conn = conn
        self._response_repo = ResponseRepository(conn)
        self._logger = get_logger('core.export_service')
    
    def export_run(self, run_id: str) -> ExportResult:
        """Export all results for a specific run.
        
        Args:
            run_id: The run ID to export.
        
        Returns:
            ExportResult with all responses and errors for the run.
        
        Logs:
            EXPORT_START: When export begins
            EXPORT_FETCHED: When responses/errors are fetched (debug)
            EXPORT_COMPLETE: When export finishes with counts
        """
        self._logger.info(f"EXPORT_START | run={run_id}")
        
        responses = self._response_repo.list_by_run(run_id)
        self._logger.debug(f"EXPORT_FETCHED | run={run_id} | responses={len(responses)}")

        # Read errors directly via SQL (no repository layer).
        # Includes response_id and attempt_number for error versioning observability.
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT error_id, response_id, attempt_number, run_id, variant_id, snapshot_id, "
            "question_id, error_type, error_message, attempt_count, occurred_at "
            "FROM errors WHERE run_id = ? ORDER BY response_id ASC, attempt_number ASC",
            (run_id,),
        )
        error_rows = cursor.fetchall()
        self._logger.debug(f"EXPORT_FETCHED | run={run_id} | errors={len(error_rows)}")

        exported_responses = [self._response_to_export(r) for r in responses]
        exported_errors = [
            ExportedError(
                error_id=row["error_id"],
                response_id=row["response_id"],
                attempt_number=row["attempt_number"],
                question_id=row["question_id"],
                variant_id=row["variant_id"],
                snapshot_id=row["snapshot_id"],
                run_id=row["run_id"],
                error_type=row["error_type"],
                error_message=row["error_message"],
                attempt_count=row["attempt_count"],
                occurred_at=row["occurred_at"],
            )
            for row in error_rows
        ]
        
        experiment_name = self._get_experiment_name_for_run(run_id)
        
        result = ExportResult(
            export_version="1.0",
            exported_at=datetime.now(timezone.utc).isoformat(),
            experiment_name=experiment_name,
            run_id=run_id,
            total_responses=len(exported_responses),
            total_errors=len(exported_errors),
            responses=[self._to_dict(r) for r in exported_responses],
            errors=[self._to_dict(e) for e in exported_errors],
        )
        
        self._logger.info(
            f"EXPORT_COMPLETE | run={run_id} | "
            f"responses={result.total_responses} | errors={result.total_errors}"
        )
        
        return result
    
    def _response_to_export(self, response: Response) -> ExportedResponse:
        """Convert Response to ExportedResponse with computed fields.
        
        Computes:
            final_answer: manual_answer OR selected_answer (null-coalescing)
            answer_source: 'manual' if manual_answer else 'automatic' if selected_answer else None
            effective_tokens: input_tokens + response_tokens + reasoning_tokens
        
        Args:
            response: Response dataclass from repository.
        
        Returns:
            ExportedResponse with all fields populated including computed fields.
        """
        final_answer = response.manual_answer or response.selected_answer
        
        if response.manual_answer:
            answer_source = 'manual'
        elif response.selected_answer:
            answer_source = 'automatic'
        else:
            answer_source = None
        
        effective_tokens = None
        if response.input_tokens is not None or response.response_tokens is not None or response.reasoning_tokens is not None:
            effective_tokens = (
                (response.input_tokens or 0) +
                (response.response_tokens or 0) +
                (response.reasoning_tokens or 0)
            )
        
        return ExportedResponse(
            response_id=response.response_id,
            question_id=response.question_id,
            variant_id=response.variant_id,
            model_id=response.model_id,
            snapshot_id=response.snapshot_id,
            run_id=response.run_id,
            selected_answer=response.selected_answer,
            manual_answer=response.manual_answer,
            final_answer=final_answer,
            answer_source=answer_source,
            is_correct=response.is_correct,
            parse_confidence=response.parse_confidence or 'unknown',
            latency_ms=response.latency_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.response_tokens,
            reasoning_tokens=response.reasoning_tokens,
            effective_tokens=effective_tokens,
            status=response.status,
            error_details=response.error_details,
            cost=response.cost,
            started_at=response.started_at,
            finished_at=response.finished_at,
            request_json=response.request_json,
            raw_response_consolidated=response.raw_response_consolidated,
            randomization_enabled=response.randomization_enabled,
            randomization_seed=response.randomization_seed,
            options_presented=response.options_presented,
            correct_option_presented=response.correct_option_presented,
            option_letter_map=response.option_letter_map,
        )

    def _get_experiment_name_for_run(self, run_id: str) -> Optional[str]:
        """Get experiment name for a run (for context in export).
        
        Args:
            run_id: Run identifier.
        
        Returns:
            Experiment name or None if run not found.
        """
        run_repo = RunRepository(self._conn)
        run = run_repo.get_by_id(run_id)
        if not run:
            return None
        
        exp_repo = ExperimentRepository(self._conn)
        experiment = exp_repo.get_by_id(run.experiment_id)
        return experiment.name if experiment else None
    
    def _to_dict(self, obj: Any) -> dict:
        """Convert dataclass to dictionary.
        
        Args:
            obj: Dataclass instance to convert.
        
        Returns:
            Dictionary with all dataclass fields.
        """
        if hasattr(obj, '__dataclass_fields__'):
            return {k: getattr(obj, k) for k in obj.__dataclass_fields__}
        return obj.__dict__
