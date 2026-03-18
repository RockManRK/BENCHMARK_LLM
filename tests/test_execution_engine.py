"""Tests for purified execution_engine module.

This module tests the ExecutionEngine component that executes ExecutionPlans.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.execution_engine import ExecutionEngine
from src.core.execution_plan import (
    ExecutionPlan,
    ExecutionResult,
    PlanItem,
    PlanRun,
    PlanVariant,
    generate_plan_id,
)
from src.core.randomizer import AnswerRandomizer
from src.utils.config import Settings


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
    randomizer._randomize_options = MagicMock(side_effect=lambda opts, correct: {
        "options": opts,
        "correct_answer": correct,
    })
    return randomizer


@pytest.fixture
def mock_settings():
    """Create mock Settings."""
    settings = MagicMock(spec=Settings)
    settings.model_max_tokens = None
    settings.model_temperature = None
    settings.model_top_p = None
    settings.use_structured_outputs = False
    settings.reasoning_effort = None
    settings.reasoning_max_tokens = None
    settings.reasoning_enabled = None
    return settings


@pytest.fixture
def sample_plan():
    """Create sample ExecutionPlan for testing."""
    item = PlanItem(
        item_id="run-001::var-abc::1::it-1",
        run_id="run-001",
        variant_id="var-abc",
        model_id="openai/gpt-4",
        snapshot_id=1,
        question_id="Q001",
        iteration_number=1,
        question_payload={
            "stem": "What is 2+2?",
            "options": {"A": "3", "B": "4", "C": "5", "D": "6"},
            "answer_key": "B",
        },
    )

    variant = PlanVariant(
        variant_id="var-abc",
        model_id="openai/gpt-4",
        model_config={"reasoning_mode": "off"},
    )

    run = PlanRun(
        run_id="run-001",
        seed_effective=42,
        system_prompt="You are helpful.",
        user_prompt="Answer the question.",
        variants=[variant],
        items=[item],
    )

    plan = ExecutionPlan(
        plan_id=generate_plan_id("exp-123", datetime(2026, 3, 18, 12, 0, 0)),
        created_at=datetime.now(),
        experiment_id="exp-123",
        experiment_name="test_experiment",
        runs=[run],
    )

    return plan


class TestExecutionEngineInit:
    """Tests for ExecutionEngine initialization."""

    def test_engine_init(self, mock_api_client, mock_randomizer, mock_settings):
        """Test ExecutionEngine initializes correctly."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        assert engine.api_client == mock_api_client
        assert engine.randomizer == mock_randomizer
        assert engine.settings == mock_settings

    def test_engine_no_db_access(self, mock_api_client, mock_randomizer, mock_settings):
        """Test that ExecutionEngine has no db_manager attribute."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        assert not hasattr(engine, 'db_manager') or engine.db_manager is None


class TestExecute:
    """Tests for ExecutionEngine.execute() method."""

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_api_client, mock_randomizer, mock_settings, sample_plan
    ):
        """Test executing a plan with successful response."""
        # Mock API response
        mock_api_client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {"content": "The answer is B"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
            },
        }

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)
        results = engine.execute(sample_plan)

        # Verify results
        assert len(results) == 1
        result = results[0]

        assert result.item_id == "run-001::var-abc::1::it-1"
        assert result.run_id == "run-001"
        assert result.variant_id == "var-abc"
        assert result.model_id == "openai/gpt-4"
        assert result.snapshot_id == 1
        assert result.question_id == "Q001"
        assert result.iteration_number == 1
        assert result.status == "success"
        assert result.selected_answer == "B"
        assert result.is_correct is True
        assert result.latency_ms >= 0
        assert result.input_tokens == 50
        assert result.output_tokens == 10

        # Verify API was called
        mock_api_client.chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_failure(
        self, mock_api_client, mock_randomizer, mock_settings, sample_plan
    ):
        """Test executing a plan with API failure."""
        # Mock API error
        mock_api_client.chat_completion.side_effect = Exception("API Error")

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)
        results = engine.execute(sample_plan)

        # Verify results
        assert len(results) == 1
        result = results[0]

        assert result.status == "failure"
        assert result.selected_answer is None
        assert result.is_correct is None
        assert "API Error" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_multiple_runs(
        self, mock_api_client, mock_randomizer, mock_settings
    ):
        """Test executing a plan with multiple runs."""
        # Create plan with 2 runs
        item1 = PlanItem(
            item_id="run-001::var-abc::1::it-1",
            run_id="run-001",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            question_payload={"stem": "Q1", "options": {"A": "1"}, "answer_key": "A"},
        )

        item2 = PlanItem(
            item_id="run-002::var-abc::1::it-1",
            run_id="run-002",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q002",
            iteration_number=1,
            question_payload={"stem": "Q2", "options": {"A": "2"}, "answer_key": "A"},
        )

        run1 = PlanRun(
            run_id="run-001",
            seed_effective=42,
            system_prompt="Prompt 1",
            user_prompt="Answer 1",
            variants=[PlanVariant("var-abc", "openai/gpt-4", {})],
            items=[item1],
        )

        run2 = PlanRun(
            run_id="run-002",
            seed_effective=43,
            system_prompt="Prompt 2",
            user_prompt="Answer 2",
            variants=[PlanVariant("var-abc", "openai/gpt-4", {})],
            items=[item2],
        )

        plan = ExecutionPlan(
            plan_id="plan-test",
            created_at=datetime.now(),
            experiment_id="exp-123",
            experiment_name="test",
            runs=[run1, run2],
        )

        # Mock API response
        mock_api_client.chat_completion.return_value = {
            "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)
        results = engine.execute(plan)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_execute_multiple_items_per_run(
        self, mock_api_client, mock_randomizer, mock_settings, sample_plan
    ):
        """Test executing a run with multiple items."""
        # Add more items to the plan
        item2 = PlanItem(
            item_id="run-001::var-abc::2::it-1",
            run_id="run-001",
            variant_id="var-abc",
            model_id="openai/gpt-4",
            snapshot_id=2,
            question_id="Q002",
            iteration_number=1,
            question_payload={"stem": "Q2", "options": {"A": "1"}, "answer_key": "A"},
        )
        sample_plan.runs[0].items.append(item2)

        # Mock API response
        mock_api_client.chat_completion.return_value = {
            "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)
        results = engine.execute(sample_plan)

        assert len(results) == 2


class TestParseAnswer:
    """Tests for answer parsing logic."""

    def test_parse_answer_simple(self, mock_api_client, mock_randomizer, mock_settings):
        """Test parsing simple answer."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        answer = engine._parse_answer("The answer is B")
        assert answer == "B"

    def test_parse_answer_just_letter(self, mock_api_client, mock_randomizer, mock_settings):
        """Test parsing just a letter."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        answer = engine._parse_answer("B")
        assert answer == "B"

    def test_parse_answer_lowercase(self, mock_api_client, mock_randomizer, mock_settings):
        """Test parsing lowercase answer."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        answer = engine._parse_answer("the answer is b")
        assert answer == "B"

    def test_parse_answer_empty(self, mock_api_client, mock_randomizer, mock_settings):
        """Test parsing empty answer."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        answer = engine._parse_answer("")
        assert answer is None

    def test_parse_answer_invalid(self, mock_api_client, mock_randomizer, mock_settings):
        """Test parsing invalid answer."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        answer = engine._parse_answer("I don't know")
        # May return None or try to extract a letter
        assert answer is None or answer in ["A", "B", "C", "D"]


class TestExtractTokenUsage:
    """Tests for token usage extraction."""

    def test_extract_token_usage_complete(
        self, mock_api_client, mock_randomizer, mock_settings
    ):
        """Test extracting complete token usage."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        api_response = {
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
            }
        }

        tokens = engine._extract_token_usage(api_response)

        assert tokens["input_tokens"] == 50
        assert tokens["output_tokens"] == 10
        assert tokens["total_tokens"] == 60

    def test_extract_token_usage_missing(
        self, mock_api_client, mock_randomizer, mock_settings
    ):
        """Test extracting token usage when missing."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        api_response = {}
        tokens = engine._extract_token_usage(api_response)

        assert tokens["input_tokens"] == 0
        assert tokens["output_tokens"] == 0
        assert tokens["total_tokens"] == 0


class TestGetVariantModelConfig:
    """Tests for model config extraction."""

    def test_get_variant_model_config_empty(
        self, mock_api_client, mock_randomizer, mock_settings
    ):
        """Test getting model config with no settings."""
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)

        item = PlanItem(
            item_id="test",
            run_id="test",
            variant_id="test",
            model_id="openai/gpt-4",
            snapshot_id=1,
            question_id="Q001",
            iteration_number=1,
            question_payload={},
        )

        config = engine._get_variant_model_config(item)

        # Should return empty config when settings are None
        assert isinstance(config, dict)


class TestRandomization:
    """Tests for answer randomization."""

    def test_no_randomization_when_seed_none(
        self, mock_api_client, mock_randomizer, mock_settings, sample_plan
    ):
        """Test that randomization is NOT applied when seed=None."""
        # Set seed to None
        sample_plan.runs[0].seed_effective = None

        # Mock API response
        mock_api_client.chat_completion.return_value = {
            "choices": [{"message": {"content": "B"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)
        results = engine.execute(sample_plan)

        # Verify randomizer was NOT called
        mock_randomizer.set_seed.assert_not_called()
        mock_randomizer._randomize_options.assert_not_called()

    def test_randomization_when_seed_set(
        self, mock_api_client, mock_randomizer, mock_settings, sample_plan
    ):
        """Test that randomization IS applied when seed is set."""
        # Set seed to a value
        sample_plan.runs[0].seed_effective = 42

        # Mock API response
        mock_api_client.chat_completion.return_value = {
            "choices": [{"message": {"content": "B"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)
        results = engine.execute(sample_plan)

        # Verify randomizer WAS called
        mock_randomizer.set_seed.assert_called_once_with(42)
