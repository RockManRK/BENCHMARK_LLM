"""Test factories for creating domain entities.

This module provides factory classes for creating test entities
with sensible defaults. Factories reduce test boilerplate and
make tests more readable.

Usage:
    experiment = ExperimentFactory.create(name="test-exp")
    variant = VariantFactory.create(experiment_id=experiment.experiment_id)
    snapshot = SnapshotFactory.create(experiment_id=experiment.experiment_id)
    run = RunFactory.create(experiment_id=experiment.experiment_id)
"""

import uuid
import json
from dataclasses import dataclass
from typing import Any

from src.db.models import (
    Experiment,
    ModelVariant,
    QuestionSnapshot,
    Run,
    Response,
    Error,
)


class ExperimentFactory:
    """Factory for creating Experiment entities."""

    @staticmethod
    def create(
        name: str | None = None,
        system_prompt: str = "You are a helpful assistant.",
        user_prompt: str = "Answer the following question.",
        experiment_id: str | None = None,
        description: str | None = None,
        config_json: str = "{}",
        config_hash: str = "",
        is_active: bool = True,
    ) -> Experiment:
        """Create an Experiment with sensible defaults.

        Args:
            name: Experiment name (auto-generated if not provided)
            system_prompt: System prompt template
            user_prompt: User prompt template
            experiment_id: Unique ID (auto-generated if not provided)
            description: Optional description
            config_json: Frozen configuration snapshot
            config_hash: SHA-256 hash of protocol config
            is_active: Whether the experiment is active

        Returns:
            Experiment instance
        """
        if name is None:
            name = f"test-experiment-{uuid.uuid4().hex[:8]}"

        if experiment_id is None:
            experiment_id = f"exp-{uuid.uuid4().hex[:8]}"

        return Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            config_json=config_json,
            config_hash=config_hash,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            is_active=is_active,
        )


class VariantFactory:
    """Factory for creating Model Variant entities."""

    @staticmethod
    def create(
        experiment_id: str,
        model_id: str = "openai/gpt-4",
        variant_id: str | None = None,
        variant_signature: str | None = None,
        reasoning_mode: str = "off",
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
        vision_enabled: bool = False,
        structured_output: bool = False,
        web_access_enabled: bool = False,
        is_active: bool = True,
    ) -> ModelVariant:
        """Create a Model Variant with sensible defaults.

        Args:
            experiment_id: Parent experiment ID
            model_id: Base model identifier (e.g., "openai/gpt-4")
            variant_id: Unique ID (auto-generated if not provided)
            variant_signature: Human-readable identity (auto-generated if not provided)
            reasoning_mode: Reasoning mode
            reasoning_effort: Reasoning effort level
            max_output_tokens: Max tokens for budget mode
            vision_enabled: Enable vision capabilities
            structured_output: Enable structured output
            web_access_enabled: Enable web access
            is_active: Whether the variant is active

        Returns:
            ModelVariant instance
        """
        if variant_id is None:
            variant_id = f"var-{uuid.uuid4().hex[:8]}"

        if variant_signature is None:
            variant_signature = f"variant-{uuid.uuid4().hex[:6]}"

        return ModelVariant(
            variant_id=variant_id,
            experiment_id=experiment_id,
            model_id=model_id,
            variant_signature=variant_signature,
            reasoning_mode=reasoning_mode,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            vision_enabled=vision_enabled,
            structured_output=structured_output,
            web_access_enabled=web_access_enabled,
            is_active=is_active,
        )


class SnapshotFactory:
    """Factory for creating Question Snapshot entities."""

    @staticmethod
    def create(
        experiment_id: str,
        question_id: str | None = None,
        question_payload: dict[str, Any] | None = None,
        snapshot_id: str | None = None,
        created_at: str | None = None,
        is_active: bool = True,
    ) -> QuestionSnapshot:
        """Create a Question Snapshot with sensible defaults.

        Args:
            experiment_id: Parent experiment ID
            question_id: Original question ID (auto-generated if not provided)
            question_payload: Question data (default: simple multiple choice)
            snapshot_id: Unique ID (auto-generated if not provided)
            created_at: Creation timestamp (auto-generated if not provided)
            is_active: Whether the snapshot is active

        Returns:
            QuestionSnapshot instance
        """
        if question_id is None:
            question_id = f"q-{uuid.uuid4().hex[:8]}"

        if question_payload is None:
            question_payload = {
                "stem": "What is the correct answer?",
                "options": ["A", "B", "C", "D"],
                "answer_key": "B",
            }

        if snapshot_id is None:
            snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"

        return QuestionSnapshot(
            snapshot_id=snapshot_id,
            experiment_id=experiment_id,
            question_id=question_id,
            question_payload=json.dumps(question_payload),
            created_at=created_at,
            is_active=is_active,
        )


class RunFactory:
    """Factory for creating Run entities."""

    @staticmethod
    def create(
        experiment_id: str,
        seed: int | None = 42,
        run_id: str | None = None,
        status: str = "pending",
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> Run:
        """Create a Run with sensible defaults.

        Args:
            experiment_id: Parent experiment ID
            seed: Random seed for reproducibility
            run_id: Unique ID (auto-generated if not provided)
            status: Run status (default: "pending")
            started_at: Execution start timestamp
            finished_at: Execution end timestamp

        Returns:
            Run instance
        """
        if run_id is None:
            run_id = f"run-{uuid.uuid4().hex[:8]}"

        return Run(
            run_id=run_id,
            experiment_id=experiment_id,
            seed=seed,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
        )


class ResponseFactory:
    """Factory for creating Response entities."""

    @staticmethod
    def create(
        run_id: str,
        variant_id: str,
        snapshot_id: str,
        model_id: str = "openai/gpt-4",
        question_id: str | None = None,
        response_id: str | None = None,
        response_text: str | None = None,
        selected_answer: str | None = None,
        is_correct: bool | None = None,
        parse_confidence: str = "unknown",
        review_status: str | None = None,
        manual_answer: str | None = None,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        response_tokens: int | None = None,
    ) -> Response:
        """Create a Response with sensible defaults.

        Args:
            run_id: Parent run ID
            variant_id: Model variant ID
            snapshot_id: Question snapshot ID
            model_id: Base model identifier
            question_id: Original question ID (derived from snapshot if not provided)
            response_id: Unique ID (auto-generated if not provided)
            response_text: Full model response
            selected_answer: Parsed answer (A/B/C/D)
            is_correct: Whether answer is correct
            parse_confidence: Confidence level
            review_status: Review status ('needs_review', 'reviewed', 'auto')
            manual_answer: Human override
            latency_ms: API call latency
            input_tokens: Input tokens used
            response_tokens: Response tokens generated

        Returns:
            Response instance
        """
        if response_id is None:
            response_id = f"resp-{uuid.uuid4().hex[:8]}"

        if question_id is None:
            question_id = f"q-{uuid.uuid4().hex[:8]}"

        return Response(
            response_id=response_id,
            run_id=run_id,
            variant_id=variant_id,
            snapshot_id=snapshot_id,
            model_id=model_id,
            question_id=question_id,
            response_text=response_text,
            selected_answer=selected_answer,
            is_correct=is_correct,
            parse_confidence=parse_confidence,
            review_status=review_status,
            manual_answer=manual_answer,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            response_tokens=response_tokens,
        )


class ErrorFactory:
    """Factory for creating Error entities."""

    @staticmethod
    def create(
        run_id: str,
        variant_id: str,
        snapshot_id: str,
        error_type: str = "api_error",
        error_message: str = "An error occurred",
        error_id: str | None = None,
        attempt_count: int = 1,
        stack_trace: str | None = None,
    ) -> Error:
        """Create an Error with sensible defaults.

        Args:
            run_id: Parent run ID
            variant_id: Model variant ID
            snapshot_id: Question snapshot ID
            error_type: Type of error
            error_message: Human-readable message
            error_id: Unique ID (auto-generated if not provided)
            attempt_count: Number of retry attempts
            stack_trace: Optional stack trace

        Returns:
            Error instance
        """
        if error_id is None:
            error_id = f"err-{uuid.uuid4().hex[:8]}"

        return Error(
            error_id=error_id,
            run_id=run_id,
            variant_id=variant_id,
            snapshot_id=snapshot_id,
            error_type=error_type,
            error_message=error_message,
            attempt_count=attempt_count,
            stack_trace=stack_trace,
        )
