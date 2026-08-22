"""Unit tests for ExecutionEngine vision gating logic.

Tests cover:
- Vision enabled + question has image -> multimodal message
- Vision disabled + question has image -> text-only message + warning logged
- No image -> text-only message
- Vision enabled + image missing -> FileNotFoundError (item failure)
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

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
from src.core.execution_engine import ExecutionEngine, ExecutionResult
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser, ParsedAnswer
from src.core.retry import RetryHandler


@dataclass
class MockCompletionResponse:
    """Mock CompletionResponse for testing."""
    content: str
    model_id: str
    input_tokens: int
    response_tokens: int
    latency_ms: int


class MockOpenRouterClient:
    """Mock OpenRouterClient for testing."""

    def __init__(self) -> None:
        self._call_args_list = []
        self._chat_completion_return_value = MockCompletionResponse(
            content="The answer is (B).",
            model_id="openai/gpt-4",
            input_tokens=50,
            response_tokens=10,
            latency_ms=500,
        )
        self._chat_completion_side_effect = None

    async def chat_completion(
        self,
        payload: dict,
        base_url: str | None = None,
        operation_id: str | None = None,
    ) -> MockCompletionResponse:
        """Mock chat completion that records calls.

        `payload` is the single canonical request dict built by
        `build_chat_completion_payload` — 'model_id'/'messages' keys are
        derived from it here for backward-compatible assertions below
        (see docs/status/model-seed-checkpoint-b-design.md, Part 1: the
        client no longer receives scalar kwargs, only the payload).
        Fixed 2026-08-21 (test-debt reconciliation, group 1): this mock
        still declared the pre-refactor model_id/messages/**kwargs
        signature, so every real call (payload=..., base_url=...,
        operation_id=...) raised TypeError — see
        tests/unit/core/test_execution_engine.py's MockOpenRouterClient
        for the already-fixed sibling this mirrors.
        """
        self._call_args_list.append({
            'model_id': payload.get('model'),
            'messages': payload.get('messages'),
            'payload': payload,
            'kwargs': payload,
            'base_url': base_url,
        })

        if self._chat_completion_side_effect is not None:
            if isinstance(self._chat_completion_side_effect, Exception):
                raise self._chat_completion_side_effect
            elif callable(self._chat_completion_side_effect):
                return self._chat_completion_side_effect()

        return self._chat_completion_return_value

    def reset(self) -> None:
        """Reset recorded calls."""
        self._call_args_list = []


def _make_mock_answer_parser(answer: str = "B", confidence: str = "clear") -> AnswerParser:
    """Create a mock AnswerParser."""
    parser = MagicMock(spec=AnswerParser)
    parser.parse.return_value = ParsedAnswer(
        answer=answer,
        confidence=confidence,
    )
    return parser


def _make_mock_randomizer() -> AnswerRandomizer:
    """Create a mock AnswerRandomizer."""
    randomizer = MagicMock(spec=AnswerRandomizer)
    randomizer.randomize_options.side_effect = lambda opts, seed: {"options": opts}
    return randomizer


def _make_minimal_plan_run(
    seed: int | None = None,
    system_prompt: str | None = None,
    user_prompt: str = "Answer the question.",
    retry_policy: RetryPolicy | None = None,
) -> PlanRun:
    """Create a minimal PlanRun for testing."""
    return PlanRun(
        run_id="test-run",
        randomization_seed_effective=seed,
        prompts_effective=Prompts(system=system_prompt, user=user_prompt),
        retry_policy=retry_policy or RetryPolicy(max_attempts=1),
        variants=[],
        items=[],
    )


def _make_plan_item(
    question_payload: QuestionPayload,
    run_id: str = "test-run",
    variant_id: str = "test-variant",
) -> PlanItem:
    """Create a PlanItem with given question payload."""
    return PlanItem(
        item_id=f"{run_id}::{variant_id}::snap-001::it-1",
        run_id=run_id,
        variant_id=variant_id,
        snapshot_id="snap-001",
        question_id="q-test",
        question_payload=question_payload,
    )


class TestBuildUserMessageForItem:
    """Tests for _build_user_message_for_item vision gating logic."""

    @pytest.fixture
    def engine(self) -> ExecutionEngine:
        """Create a test ExecutionEngine with mock dependencies."""
        api_client = MockOpenRouterClient()
        randomizer = _make_mock_randomizer()
        parser = _make_mock_answer_parser()
        return ExecutionEngine(api_client, randomizer, parser)

    @pytest.fixture
    def tmp_image_file(self, tmp_path: Path) -> Path:
        """Create a temporary PNG image file for testing."""
        png_header = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0x0F, 0x00, 0x00,
            0x01, 0x01, 0x01, 0x00, 0x18, 0xDD, 0x8D, 0xB4,
            0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
            0xAE, 0x42, 0x60, 0x82,
        ])
        image_file = tmp_path / "test_image.png"
        image_file.write_bytes(png_header)
        return image_file

    def test_vision_enabled_question_has_image_builds_multimodal(
        self, engine: ExecutionEngine, tmp_image_file: Path
    ):
        """Vision enabled + question has image -> multimodal message."""
        question_payload = QuestionPayload(
            stem="What is in this X-ray?",
            options=["Pneumonia", "Fracture", "Normal", "Tumor"],
            answer_key="A",
            has_image=True,
            image_path=str(tmp_image_file),
        )
        item = _make_plan_item(question_payload)
        model_config = ModelConfig(enable_vision=True)

        result = engine._build_user_message_for_item(
            item=item,
            options=question_payload.options,
            user_prompt_template="Answer the question.",
            model_config=model_config,
        )

        assert result is not None
        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "image_url"

    def test_vision_disabled_question_has_image_builds_text_only_with_warning(
        self, engine: ExecutionEngine, tmp_image_file: Path, caplog: pytest.LogCaptureFixture
    ):
        """Vision disabled + question has image -> text-only message + warning logged."""
        question_payload = QuestionPayload(
            stem="What is in this X-ray?",
            options=["Pneumonia", "Fracture", "Normal", "Tumor"],
            answer_key="A",
            has_image=True,
            image_path=str(tmp_image_file),
        )
        item = _make_plan_item(question_payload)
        model_config = ModelConfig(enable_vision=False)

        result = engine._build_user_message_for_item(
            item=item,
            options=question_payload.options,
            user_prompt_template="Answer the question.",
            model_config=model_config,
        )

        # Should be text-only (dict with 'content' as string, not list)
        assert result is not None
        assert result["role"] == "user"
        assert isinstance(result["content"], str)
        assert "X-ray" in result["content"]

        # Warning should have been logged
        assert any("VISION_DISABLED" in record.message for record in caplog.records)

    def test_no_image_builds_text_only(self, engine: ExecutionEngine):
        """No image -> text-only message regardless of vision flag."""
        question_payload = QuestionPayload(
            stem="What is 2+2?",
            options=["3", "4", "5", "6"],
            answer_key="B",
            has_image=False,
            image_path=None,
        )
        item = _make_plan_item(question_payload)

        # Test with vision enabled (should still be text-only since no image)
        model_config_vision_on = ModelConfig(enable_vision=True)
        result = engine._build_user_message_for_item(
            item=item,
            options=question_payload.options,
            user_prompt_template="Answer the question.",
            model_config=model_config_vision_on,
        )

        assert result is not None
        assert isinstance(result["content"], str)

        # Test with vision disabled (should also be text-only)
        model_config_vision_off = ModelConfig(enable_vision=False)
        result = engine._build_user_message_for_item(
            item=item,
            options=question_payload.options,
            user_prompt_template="Answer the question.",
            model_config=model_config_vision_off,
        )

        assert result is not None
        assert isinstance(result["content"], str)

    def test_vision_enabled_image_missing_raises_file_not_found(self, engine: ExecutionEngine):
        """Vision enabled + image missing -> FileNotFoundError."""
        question_payload = QuestionPayload(
            stem="What is in this X-ray?",
            options=["Pneumonia", "Fracture", "Normal", "Tumor"],
            answer_key="A",
            has_image=True,
            image_path="data/assets/nonexistent_image.png",
        )
        item = _make_plan_item(question_payload)
        model_config = ModelConfig(enable_vision=True)

        with pytest.raises(FileNotFoundError, match="Image file not found"):
            engine._build_user_message_for_item(
                item=item,
                options=question_payload.options,
                user_prompt_template="Answer the question.",
                model_config=model_config,
            )


class TestExecuteItemAsyncVisionGating:
    """Integration-level tests for vision gating in _execute_item_async."""

    @pytest.fixture
    def api_client(self) -> MockOpenRouterClient:
        return MockOpenRouterClient()

    @pytest.fixture
    def engine(self, api_client: MockOpenRouterClient) -> ExecutionEngine:
        randomizer = _make_mock_randomizer()
        parser = _make_mock_answer_parser()
        return ExecutionEngine(api_client, randomizer, parser)

    @pytest.fixture
    def tmp_image_file(self, tmp_path: Path) -> Path:
        png_header = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0x0F, 0x00, 0x00,
            0x01, 0x01, 0x01, 0x00, 0x18, 0xDD, 0x8D, 0xB4,
            0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
            0xAE, 0x42, 0x60, 0x82,
        ])
        image_file = tmp_path / "test_image.png"
        image_file.write_bytes(png_header)
        return image_file

    @pytest.mark.asyncio
    async def test_vision_enabled_sends_multimodal_message(
        self, engine: ExecutionEngine, api_client: MockOpenRouterClient, tmp_image_file: Path
    ):
        """When vision is enabled and question has image, API receives multimodal message."""
        question_payload = QuestionPayload(
            stem="What is in this X-ray?",
            options=["Pneumonia", "Fracture", "Normal", "Tumor"],
            answer_key="A",
            has_image=True,
            image_path=str(tmp_image_file),
        )
        item = _make_plan_item(question_payload)
        variant = PlanVariant(
            variant_id="test-variant",
            model_id="openai/gpt-4-vision",
            model_config_effective=ModelConfig(enable_vision=True),
        )
        run = _make_minimal_plan_run()
        run = PlanRun(
            run_id=run.run_id,
            randomization_seed_effective=run.randomization_seed_effective,
            prompts_effective=run.prompts_effective,
            retry_policy=run.retry_policy,
            variants=[variant],
            items=[item],
        )

        result = await engine._execute_item_async(item, run)

        assert result.status == "success"
        # Verify API received a multimodal message
        assert len(api_client._call_args_list) == 1
        messages = api_client._call_args_list[0]["messages"]
        user_message = messages[-1]  # Last message should be user message
        assert isinstance(user_message["content"], list)
        assert user_message["content"][0]["type"] == "text"
        assert user_message["content"][1]["type"] == "image_url"

    @pytest.mark.asyncio
    async def test_vision_disabled_sends_text_only_message(
        self, engine: ExecutionEngine, api_client: MockOpenRouterClient, tmp_image_file: Path
    ):
        """When vision is disabled, API receives text-only message even if question has image."""
        question_payload = QuestionPayload(
            stem="What is in this X-ray?",
            options=["Pneumonia", "Fracture", "Normal", "Tumor"],
            answer_key="A",
            has_image=True,
            image_path=str(tmp_image_file),
        )
        item = _make_plan_item(question_payload)
        variant = PlanVariant(
            variant_id="test-variant",
            model_id="openai/gpt-4",
            model_config_effective=ModelConfig(enable_vision=False),
        )
        run = _make_minimal_plan_run()
        run = PlanRun(
            run_id=run.run_id,
            randomization_seed_effective=run.randomization_seed_effective,
            prompts_effective=run.prompts_effective,
            retry_policy=run.retry_policy,
            variants=[variant],
            items=[item],
        )

        result = await engine._execute_item_async(item, run)

        assert result.status == "success"
        # Verify API received a text-only message
        assert len(api_client._call_args_list) == 1
        messages = api_client._call_args_list[0]["messages"]
        user_message = messages[-1]
        assert isinstance(user_message["content"], str)

    @pytest.mark.asyncio
    async def test_vision_enabled_image_missing_marks_failure(
        self, engine: ExecutionEngine, api_client: MockOpenRouterClient
    ):
        """When vision is enabled but image is missing, item is marked as failure."""
        question_payload = QuestionPayload(
            stem="What is in this X-ray?",
            options=["Pneumonia", "Fracture", "Normal", "Tumor"],
            answer_key="A",
            has_image=True,
            image_path="data/assets/nonexistent_image.png",
        )
        item = _make_plan_item(question_payload)
        variant = PlanVariant(
            variant_id="test-variant",
            model_id="openai/gpt-4-vision",
            model_config_effective=ModelConfig(enable_vision=True),
        )
        run = _make_minimal_plan_run()
        run = PlanRun(
            run_id=run.run_id,
            randomization_seed_effective=run.randomization_seed_effective,
            prompts_effective=run.prompts_effective,
            retry_policy=run.retry_policy,
            variants=[variant],
            items=[item],
        )

        result = await engine._execute_item_async(item, run)

        assert result.status == "failure"
        assert result.error_type is not None
        # API should NOT have been called
        assert len(api_client._call_args_list) == 0
