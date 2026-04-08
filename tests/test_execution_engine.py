"""Tests for purified execution_engine module.

This module tests the ExecutionEngine component that executes ExecutionPlans.
Updated to use execute_async() (async) — the sync execute() wrapper has been removed.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.core.execution_engine import ExecutionEngine
from src.core.execution_plan import (
    ExecutionPlan,
    PlanItem,
    PlanRun,
    PlanVariant,
    generate_plan_id,
)
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser


@pytest.fixture
def mock_api_client():
    """Create mock OpenRouterClient."""
    client = MagicMock()
    client.chat_completion = AsyncMock()
    return client


@pytest.fixture
def mock_randomizer():
    """Create mock AnswerRandomizer."""
    randomizer = MagicMock(spec=AnswerRandomizer)
    randomizer.set_seed = MagicMock()
    return randomizer


@pytest.fixture
def parser():
    """Create AnswerParser instance."""
    return AnswerParser()


@pytest.fixture
def sample_plan():
    """Create sample ExecutionPlan for testing."""
    item = PlanItem(
        item_id="run-001::var-abc::snap-1::it-1",
        run_id="run-001",
        variant_id="var-abc",
        model_id="openai/gpt-4",
        snapshot_id="snap-1",
        question_id="Q001",
        question_payload={
            "stem": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "answer_key": "B",
            "has_image": False,
            "image_path": None,
        },
    )

    from src.core.execution_plan import ModelConfig
    variant = PlanVariant(
        variant_id="var-abc",
        model_id="openai/gpt-4",
        model_config_effective=ModelConfig(),
    )

    run = PlanRun(
        run_id="run-001",
        seed_effective=42,
        prompts_effective=type('Prompts', (), {'system': 'You are helpful.', 'user': 'Answer the question.'})(),
        variants=[variant],
        items=[item],
        retry_policy=type('RetryPolicy', (), {
            'max_attempts': 1, 'initial_delay_ms': 1000, 'max_delay_ms': 10000, 'backoff_multiplier': 2.0
        })(),
    )

    plan = ExecutionPlan(
        plan_id=generate_plan_id("exp-123", datetime(2026, 3, 18, 12, 0, 0)),
        created_at=datetime.now(),
        experiment_id="exp-123",
        experiment_name="test_experiment",
        runs=[run],
    )

    return plan


def _make_completion_response(content="The answer is B", finish_reason="stop",
                               prompt_tokens=50, completion_tokens=10, total_tokens=60):
    """Create a mock CompletionResponse-like object."""
    resp = MagicMock()
    resp.content = content
    resp.finish_reason = finish_reason
    resp.input_tokens = prompt_tokens
    resp.response_tokens = completion_tokens
    resp.reasoning_tokens = None
    resp.cost = 0.0001
    resp.raw_response = [{"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]}]
    return resp


class TestExecutionEngineInit:
    """Tests for ExecutionEngine initialization."""

    def test_engine_init(self, mock_api_client, mock_randomizer, parser):
        """Test ExecutionEngine initializes correctly."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, parser)

        assert engine.api_client == mock_api_client
        assert engine.randomizer == mock_randomizer
        assert engine.parser == parser

    def test_engine_no_db_access(self, mock_api_client, mock_randomizer, parser):
        """Test that ExecutionEngine has no db_manager attribute."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, parser)

        assert not hasattr(engine, 'db_manager')


class TestExecuteAsync:
    """Tests for ExecutionEngine.execute_async() method."""

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_api_client, mock_randomizer, parser, sample_plan
    ):
        """Test executing a plan with successful response."""
        mock_api_client.chat_completion.return_value = _make_completion_response()

        engine = ExecutionEngine(mock_api_client, mock_randomizer, parser)
        queue = asyncio.Queue()
        results = await engine.execute_async(sample_plan, queue)

        assert len(results) == 1
        result = results[0]

        assert result.item_id == "run-001::var-abc::snap-1::it-1"
        assert result.run_id == "run-001"
        assert result.variant_id == "var-abc"
        assert result.snapshot_id == "snap-1"
        assert result.question_id == "Q001"
        assert result.status == "success"
        assert result.input_tokens == 50
        assert result.response_tokens == 10

        mock_api_client.chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_failure(
        self, mock_api_client, mock_randomizer, parser, sample_plan
    ):
        """Test executing a plan with API failure."""
        mock_api_client.chat_completion.side_effect = Exception("API Error")

        engine = ExecutionEngine(mock_api_client, mock_randomizer, parser)
        queue = asyncio.Queue()
        results = await engine.execute_async(sample_plan, queue)

        assert len(results) == 1
        result = results[0]

        assert result.status == "failure"
        assert result.selected_answer is None
        assert "API Error" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_multiple_items(
        self, mock_api_client, mock_randomizer, parser
    ):
        """Test executing a run with multiple items."""
        from src.core.execution_plan import ModelConfig

        item1 = PlanItem(
            item_id="run-001::var-abc::snap-1::it-1",
            run_id="run-001",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id="snap-1",
            question_id="Q001",
            question_payload={"stem": "Q1", "options": ["1"], "answer_key": "A", "has_image": False, "image_path": None},
        )

        item2 = PlanItem(
            item_id="run-001::var-abc::snap-2::it-1",
            run_id="run-001",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id="snap-2",
            question_id="Q002",
            question_payload={"stem": "Q2", "options": ["2"], "answer_key": "A", "has_image": False, "image_path": None},
        )

        variant = PlanVariant(
            variant_id="var-abc",
            model_id="openai/gpt-4",
            model_config_effective=ModelConfig(),
        )

        run = PlanRun(
            run_id="run-001",
            seed_effective=42,
            prompts_effective=type('Prompts', (), {'system': None, 'user': 'Answer.'})(),
            variants=[variant],
            items=[item1, item2],
            retry_policy=type('RetryPolicy', (), {
                'max_attempts': 1, 'initial_delay_ms': 1000, 'max_delay_ms': 10000, 'backoff_multiplier': 2.0
            })(),
        )

        plan = ExecutionPlan(
            plan_id="plan-test",
            created_at=datetime.now(),
            experiment_id="exp-123",
            experiment_name="test",
            runs=[run],
        )

        mock_api_client.chat_completion.return_value = _make_completion_response(content="A")

        engine = ExecutionEngine(mock_api_client, mock_randomizer, parser)
        queue = asyncio.Queue()
        results = await engine.execute_async(plan, queue)

        assert len(results) == 2


class TestRandomization:
    """Tests for answer randomization."""

    @pytest.mark.asyncio
    async def test_no_randomization_when_seed_none(
        self, mock_api_client, mock_randomizer, parser, sample_plan
    ):
        """Test that randomization is NOT applied when seed=None."""
        sample_plan.runs[0].seed_effective = None
        mock_api_client.chat_completion.return_value = _make_completion_response()

        engine = ExecutionEngine(mock_api_client, mock_randomizer, parser)
        queue = asyncio.Queue()
        await engine.execute_async(sample_plan, queue)

        mock_randomizer.set_seed.assert_not_called()

    @pytest.mark.asyncio
    async def test_randomization_when_seed_set(
        self, mock_api_client, mock_randomizer, parser, sample_plan
    ):
        """Test that randomization IS applied when seed is set."""
        sample_plan.runs[0].seed_effective = 42
        mock_api_client.chat_completion.return_value = _make_completion_response()

        engine = ExecutionEngine(mock_api_client, mock_randomizer, parser)
        queue = asyncio.Queue()
        await engine.execute_async(sample_plan, queue)

        mock_randomizer.set_seed.assert_called_once_with(42)
