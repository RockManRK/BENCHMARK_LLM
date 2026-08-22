"""Integration tests for vision execution.

Tests cover end-to-end vision execution scenarios:
- Execute question with image + vision enabled -> API receives multimodal message
- Execute question with image + vision disabled -> API receives text-only message
- Execute question without image -> API receives text-only message
- Verify API receives correct multimodal message format
"""

import base64
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
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
    """Mock OpenRouterClient that records all API calls for inspection."""

    def __init__(self) -> None:
        self._call_args_list: list[dict] = []
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
        """Mock chat completion that records all call arguments.

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


def _make_mock_answer_parser() -> AnswerParser:
    """Create a mock AnswerParser."""
    parser = MagicMock(spec=AnswerParser)
    parser.parse.return_value = ParsedAnswer(
        answer="B",
        confidence="clear",
    )
    return parser


def _make_mock_randomizer() -> AnswerRandomizer:
    """Create a mock AnswerRandomizer."""
    randomizer = MagicMock(spec=AnswerRandomizer)
    randomizer.randomize_options.side_effect = lambda opts, seed: {"options": opts}
    return randomizer


class TestVisionExecutionIntegration:
    """Integration tests for vision execution flow."""

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
        """Create a temporary PNG image file."""
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
    async def test_execute_question_with_image_vision_enabled(
        self, engine: ExecutionEngine, api_client: MockOpenRouterClient, tmp_image_file: Path
    ):
        """Executing a question with image + vision enabled sends multimodal message to API."""
        question_payload = QuestionPayload(
            stem="What is in this X-ray?",
            options=["Pneumonia", "Fracture", "Normal", "Tumor"],
            answer_key="A",
            has_image=True,
            image_path=str(tmp_image_file),
        )
        item = PlanItem(
            item_id="run-001::var-001::snap-001::it-1",
            run_id="run-001",
            variant_id="var-001",
            snapshot_id="snap-001",
            question_id="q005",
            question_payload=question_payload,
        )
        variant = PlanVariant(
            variant_id="var-001",
            model_id="openai/gpt-4-vision",
            model_config_effective=ModelConfig(enable_vision=True),
        )
        run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=None,
            prompts_effective=Prompts(system=None, user="Answer the question."),
            retry_policy=RetryPolicy(max_attempts=1),
            variants=[variant],
            items=[item],
        )

        result = await engine._execute_item_async(item, run)

        assert result.status == "success"
        assert len(api_client._call_args_list) == 1

        # Verify API received a multimodal message
        messages = api_client._call_args_list[0]["messages"]
        user_message = messages[-1]
        assert isinstance(user_message["content"], list)
        assert len(user_message["content"]) == 2
        assert user_message["content"][0]["type"] == "text"
        assert user_message["content"][1]["type"] == "image_url"
        assert user_message["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_execute_question_with_image_vision_disabled(
        self, engine: ExecutionEngine, api_client: MockOpenRouterClient, tmp_image_file: Path
    ):
        """Executing a question with image + vision disabled sends text-only message to API."""
        question_payload = QuestionPayload(
            stem="What is in this X-ray?",
            options=["Pneumonia", "Fracture", "Normal", "Tumor"],
            answer_key="A",
            has_image=True,
            image_path=str(tmp_image_file),
        )
        item = PlanItem(
            item_id="run-001::var-001::snap-001::it-1",
            run_id="run-001",
            variant_id="var-001",
            snapshot_id="snap-001",
            question_id="q005",
            question_payload=question_payload,
        )
        variant = PlanVariant(
            variant_id="var-001",
            model_id="openai/gpt-4",
            model_config_effective=ModelConfig(enable_vision=False),
        )
        run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=None,
            prompts_effective=Prompts(system=None, user="Answer the question."),
            retry_policy=RetryPolicy(max_attempts=1),
            variants=[variant],
            items=[item],
        )

        result = await engine._execute_item_async(item, run)

        assert result.status == "success"
        assert len(api_client._call_args_list) == 1

        # Verify API received a text-only message
        messages = api_client._call_args_list[0]["messages"]
        user_message = messages[-1]
        assert isinstance(user_message["content"], str)
        assert "X-ray" in user_message["content"]

    @pytest.mark.asyncio
    async def test_execute_question_without_image(
        self, engine: ExecutionEngine, api_client: MockOpenRouterClient
    ):
        """Executing a question without image sends text-only message regardless of vision flag."""
        question_payload = QuestionPayload(
            stem="What is 2+2?",
            options=["3", "4", "5", "6"],
            answer_key="B",
            has_image=False,
            image_path=None,
        )
        item = PlanItem(
            item_id="run-001::var-001::snap-001::it-1",
            run_id="run-001",
            variant_id="var-001",
            snapshot_id="snap-001",
            question_id="q001",
            question_payload=question_payload,
        )
        # Even with vision enabled, no image means text-only
        variant = PlanVariant(
            variant_id="var-001",
            model_id="openai/gpt-4-vision",
            model_config_effective=ModelConfig(enable_vision=True),
        )
        run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=None,
            prompts_effective=Prompts(system=None, user="Answer the question."),
            retry_policy=RetryPolicy(max_attempts=1),
            variants=[variant],
            items=[item],
        )

        result = await engine._execute_item_async(item, run)

        assert result.status == "success"
        assert len(api_client._call_args_list) == 1

        # Verify API received a text-only message
        messages = api_client._call_args_list[0]["messages"]
        user_message = messages[-1]
        assert isinstance(user_message["content"], str)
        assert "2+2" in user_message["content"]

    @pytest.mark.asyncio
    async def test_api_receives_multimodal_message_correct_format(
        self, engine: ExecutionEngine, api_client: MockOpenRouterClient, tmp_image_file: Path
    ):
        """Verify API receives multimodal message in the exact OpenRouter format."""
        question_payload = QuestionPayload(
            stem="Describe the findings in this image.",
            options=["Normal", "Abnormal", "Unclear", "None of the above"],
            answer_key="B",
            has_image=True,
            image_path=str(tmp_image_file),
        )
        item = PlanItem(
            item_id="run-001::var-001::snap-001::it-1",
            run_id="run-001",
            variant_id="var-001",
            snapshot_id="snap-001",
            question_id="q005",
            question_payload=question_payload,
        )
        variant = PlanVariant(
            variant_id="var-001",
            model_id="google/gemini-pro-vision",
            model_config_effective=ModelConfig(enable_vision=True),
        )
        run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=None,
            prompts_effective=Prompts(system="You are a medical assistant.", user="Answer carefully."),
            retry_policy=RetryPolicy(max_attempts=1),
            variants=[variant],
            items=[item],
        )

        result = await engine._execute_item_async(item, run)

        assert result.status == "success"
        assert len(api_client._call_args_list) == 1

        call_data = api_client._call_args_list[0]

        # Verify model_id is correct
        assert call_data["model_id"] == "google/gemini-pro-vision"

        # Verify messages structure
        messages = call_data["messages"]

        # System prompt should be first (if present)
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a medical assistant."

        # User message should be multimodal
        user_message = messages[1]
        assert user_message["role"] == "user"

        # Content must be a list with text first, then image
        content = user_message["content"]
        assert isinstance(content, list)
        assert len(content) == 2

        # Text FIRST (per OpenRouter recommendation)
        assert content[0]["type"] == "text"
        assert "Describe the findings" in content[0]["text"]
        assert "Normal" in content[0]["text"]  # Options should be in the text

        # Image second
        assert content[1]["type"] == "image_url"
        image_url = content[1]["image_url"]["url"]
        assert image_url.startswith("data:image/png;base64,")

        # Verify the base64 encoding is correct
        encoded_data = image_url.split(",", 1)[1]
        decoded = base64.b64decode(encoded_data)
        assert decoded == tmp_image_file.read_bytes()
