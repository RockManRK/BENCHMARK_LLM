"""Tests for ExecutionEngine component.

This module tests the ExecutionEngine which executes ExecutionPlans.
The engine is pure execution with NO database access.

Key Domain Rules:
- variant_id is internal identity (tracked in results)
- model_id is external provider identifier (used for API calls only)
- No database lookups (pure execution)
- Returns ExecutionResult list (no side effects)
"""

import pytest
from datetime import datetime
from typing import Callable
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass, replace
import asyncio

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


# ============================================================================
# Mock API Client and Supporting Classes
# ============================================================================


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
    ) -> MockCompletionResponse:
        """Mock chat completion that records calls.

        `payload` is the single canonical request dict built by
        `build_chat_completion_payload` — 'model_id'/'messages'/'kwargs'
        keys are derived from it here for backward-compatible assertions
        below (see docs/status/model-seed-checkpoint-b-design.md, Part 1:
        the client no longer receives scalar kwargs, only the payload).
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

    def set_return_value(self, value: MockCompletionResponse) -> None:
        """Set the return value for chat_completion."""
        self._chat_completion_return_value = value

    def set_side_effect(self, effect: Exception | Callable) -> None:
        """Set side effect for chat_completion (exception or callable)."""
        self._chat_completion_side_effect = effect

    @property
    def call_args_list(self) -> list[dict]:
        """Get the list of call arguments."""
        return self._call_args_list


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_api_client():
    """Create mock OpenRouterClient."""
    return MockOpenRouterClient()


@pytest.fixture
def mock_randomizer():
    """Create mock AnswerRandomizer."""
    randomizer = MagicMock(spec=AnswerRandomizer)
    randomizer.set_seed = MagicMock()
    randomizer.randomize_options = MagicMock(side_effect=lambda opts, seed: {
        "options": opts,
    })
    return randomizer


@pytest.fixture
def mock_parser():
    """Create mock AnswerParser."""
    parser = MagicMock(spec=AnswerParser)
    parser.parse = MagicMock(return_value=ParsedAnswer(
        answer="B",
        confidence="clear",
    ))
    return parser


@pytest.fixture
def sample_question_payload():
    """Create sample QuestionPayload."""
    return QuestionPayload(
        stem="What is 2+2?",
        options=["3", "4", "5", "6"],
        answer_key="B",
    )


@pytest.fixture
def sample_variant():
    """Create sample PlanVariant."""
    return PlanVariant(
        variant_id="var-abc123",
        model_id="openai/gpt-4",
        model_config_effective=ModelConfig(temperature=0.7),
    )


@pytest.fixture
def sample_item(sample_variant, sample_question_payload):
    """Create sample PlanItem."""
    return PlanItem(
        item_id="run-001::var-abc123::snap-xyz::it-1",
        run_id="run-001",
        variant_id=sample_variant.variant_id,
        snapshot_id="snap-xyz",
        question_id="q1",
        question_payload=sample_question_payload,
    )


@pytest.fixture
def sample_run(sample_variant, sample_item):
    """Create sample PlanRun."""
    return PlanRun(
        run_id="run-001",
        randomization_seed_effective=42,
        prompts_effective=Prompts(
            system="You are a helpful assistant.",
            user="Answer the question: {question}",
        ),
        retry_policy=RetryPolicy(max_attempts=3),
        variants=[sample_variant],
        items=[sample_item],
    )


@pytest.fixture
def sample_plan(sample_run):
    """Create sample ExecutionPlan."""
    return ExecutionPlan(
        plan_id="plan-exp-001",
        created_at=datetime(2026, 3, 20, 12, 0, 0),
        experiment_id="exp-001",
        runs=[sample_run],
    )


# ============================================================================
# Domain Rule Tests
# ============================================================================


@pytest.mark.domain_rule
class TestExecutionEngineDomainRules:
    """Tests for ExecutionEngine domain rules."""

    def test_engine_has_no_db_access(self, mock_api_client, mock_randomizer, mock_parser):
        """ExecutionEngine has no database access - pure execution only."""
        # Arrange
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Assert: Engine has no db_connection or repository attributes
        assert not hasattr(engine, 'db_connection')
        assert not hasattr(engine, 'repository')
        assert not hasattr(engine, 'db_manager')

    @pytest.mark.asyncio
    async def test_engine_uses_variant_model_id_for_api_calls(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item, sample_run, sample_plan,
    ):
        """ExecutionEngine uses model_id from PlanVariant for API calls."""
        # Arrange
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(sample_plan)

        # Assert: API was called with model_id from variant
        assert len(mock_api_client.call_args_list) == 1
        call_args = mock_api_client.call_args_list[0]
        assert call_args['model_id'] == "openai/gpt-4"  # From PlanVariant.model_id

        # Assert: Result preserves variant_id for internal identity
        assert len(results) == 1
        assert results[0].variant_id == "var-abc123"  # Internal identity

    @pytest.mark.asyncio
    async def test_engine_preserves_variant_id_in_results(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item, sample_run, sample_plan,
    ):
        """ExecutionEngine preserves variant_id in results for identity tracking."""
        # Arrange
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(sample_plan)

        # Assert: variant_id is preserved in results
        assert len(results) == 1
        result = results[0]
        assert result.variant_id == "var-abc123"
        assert result.run_id == "run-001"
        assert result.snapshot_id == "snap-xyz"
        assert result.question_id == "q1"

    @pytest.mark.asyncio
    async def test_engine_no_config_resolution(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item, sample_run, sample_plan,
    ):
        """ExecutionEngine uses model_config_effective as-is (no defaults)."""
        # Arrange: Create variant with specific config
        variant_with_config = PlanVariant(
            variant_id="var-config",
            model_id="anthropic/claude-3",
            model_config_effective=ModelConfig(
                temperature=0.9,
                top_p=0.95,
                max_output_tokens=2000,
            ),
        )
        
        item_with_config = PlanItem(
            item_id="run-001::var-config::snap-xyz::it-1",
            run_id="run-001",
            variant_id="var-config",
            snapshot_id="snap-xyz",
            question_id="q1",
            question_payload=QuestionPayload(
                stem="What is 2+2?",
                options=["3", "4", "5", "6"],
                answer_key="B",
            ),
        )
        
        run_with_config = PlanRun(
            run_id="run-001",
            randomization_seed_effective=42,
            prompts_effective=Prompts(
                system="You are a helpful assistant.",
                user="Answer the question: {question}",
            ),
            retry_policy=RetryPolicy(max_attempts=3),
            variants=[variant_with_config],
            items=[item_with_config],
        )
        
        plan_with_config = ExecutionPlan(
            plan_id="plan-config",
            created_at=datetime(2026, 3, 20, 12, 0, 0),
            experiment_id="exp-001",
            runs=[run_with_config],
        )

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(plan_with_config)

        # Assert: Engine used the effective config (no modification)
        call_args = mock_api_client.call_args_list[0]
        kwargs = call_args['kwargs']
        # Config should be passed as-is
        assert kwargs.get('temperature') == 0.9
        assert kwargs.get('top_p') == 0.95
        assert kwargs.get('max_tokens') == 2000


# ============================================================================
# Execution Tests
# ============================================================================


@pytest.mark.domain_rule
class TestExecutionEngineExecute:
    """Tests for ExecutionEngine.execute() method."""

    @pytest.mark.asyncio
    async def test_engine_executes_all_items(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_run, sample_plan,
    ):
        """Verify each item in plan is executed."""
        # Arrange: Create plan with multiple items
        item2 = PlanItem(
            item_id="run-001::var-abc123::snap-xyz::it-2",
            run_id="run-001",
            variant_id=sample_variant.variant_id,
            snapshot_id="snap-xyz",
            question_id="q2",
            question_payload=QuestionPayload(
                stem="What is 3+3?",
                options=["5", "6", "7", "8"],
                answer_key="B",
            ),
        )
        
        run_multi = PlanRun(
            run_id="run-001",
            randomization_seed_effective=42,
            prompts_effective=Prompts(
                system="You are a helpful assistant.",
                user="Answer the question: {question}",
            ),
            retry_policy=RetryPolicy(max_attempts=3),
            variants=[sample_variant],
            items=[sample_run.items[0], item2],
        )
        
        plan_multi = ExecutionPlan(
            plan_id="plan-multi",
            created_at=datetime(2026, 3, 20, 12, 0, 0),
            experiment_id="exp-001",
            runs=[run_multi],
        )

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(plan_multi)

        # Assert: All items were executed
        assert len(results) == 2
        assert len(mock_api_client.call_args_list) == 2

    @pytest.mark.asyncio
    async def test_engine_returns_results(
        self, mock_api_client, mock_randomizer, mock_parser, sample_plan,
    ):
        """Verify ExecutionResult list returned (one per item)."""
        # Arrange
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(sample_plan)

        # Assert: Returns list of ExecutionResult
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], ExecutionResult)

    @pytest.mark.asyncio
    async def test_engine_executes_multiple_runs(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item,
    ):
        """Verify engine executes all runs in plan."""
        # Arrange: Create plan with 2 runs
        run1 = PlanRun(
            run_id="run-001",
            randomization_seed_effective=42,
            prompts_effective=Prompts(system="sys1", user="usr1"),
            retry_policy=RetryPolicy(),
            variants=[sample_variant],
            items=[sample_item],
        )

        item2 = PlanItem(
            item_id="run-002::var-abc123::snap-xyz::it-1",
            run_id="run-002",
            variant_id=sample_variant.variant_id,
            snapshot_id="snap-xyz",
            question_id="q2",
            question_payload=QuestionPayload(
                stem="Q2?",
                options=["A", "B", "C", "D"],
                answer_key="A",
            ),
        )
        
        run2 = PlanRun(
            run_id="run-002",
            randomization_seed_effective=43,
            prompts_effective=Prompts(system="sys2", user="usr2"),
            retry_policy=RetryPolicy(),
            variants=[sample_variant],
            items=[item2],
        )

        plan = ExecutionPlan(
            plan_id="plan-multi-run",
            created_at=datetime.now(),
            experiment_id="exp-001",
            runs=[run1, run2],
        )

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(plan)

        # Assert: Both runs executed
        assert len(results) == 2
        assert len(mock_api_client.call_args_list) == 2


# ============================================================================
# Randomization Tests
# ============================================================================


@pytest.mark.domain_rule
class TestExecutionEngineRandomization:
    """Tests for answer randomization."""

    @pytest.mark.asyncio
    async def test_engine_applies_randomization_with_seed(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item,
    ):
        """Verify answer options are shuffled with seed."""
        # Arrange: Create run with seed
        run_with_seed = PlanRun(
            run_id="run-001",
            randomization_seed_effective=42,
            prompts_effective=Prompts(
                system="You are a helpful assistant.",
                user="Answer the question: {question}",
            ),
            retry_policy=RetryPolicy(max_attempts=3),
            variants=[sample_variant],
            items=[sample_item],
        )
        
        plan = ExecutionPlan(
            plan_id="plan-seed",
            created_at=datetime(2026, 3, 20, 12, 0, 0),
            experiment_id="exp-001",
            runs=[run_with_seed],
        )

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(plan)

        # Assert: Randomizer was called with seed
        mock_randomizer.set_seed.assert_called_once_with(42)
        mock_randomizer.randomize_options.assert_called()

    @pytest.mark.asyncio
    async def test_engine_no_randomization_when_seed_none(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item,
    ):
        """Verify randomization is NOT applied when seed=None."""
        # Arrange: Create run with seed=None
        run_no_seed = PlanRun(
            run_id="run-001",
            randomization_seed_effective=None,
            prompts_effective=Prompts(
                system="You are a helpful assistant.",
                user="Answer the question: {question}",
            ),
            retry_policy=RetryPolicy(max_attempts=3),
            variants=[sample_variant],
            items=[sample_item],
        )
        
        plan = ExecutionPlan(
            plan_id="plan-no-seed",
            created_at=datetime(2026, 3, 20, 12, 0, 0),
            experiment_id="exp-001",
            runs=[run_no_seed],
        )

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(plan)

        # Assert: Randomizer was NOT called
        mock_randomizer.set_seed.assert_not_called()
        mock_randomizer.randomize_options.assert_not_called()


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.domain_rule
class TestExecutionEngineErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_engine_handles_api_errors(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item,
    ):
        """Verify API errors produce failure results."""
        # Arrange: Mock API error
        mock_api_client.set_side_effect(Exception("API connection error"))
        
        run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=42,
            prompts_effective=Prompts(
                system="You are a helpful assistant.",
                user="Answer the question: {question}",
            ),
            retry_policy=RetryPolicy(max_attempts=1),  # Single attempt for faster test
            variants=[sample_variant],
            items=[sample_item],
        )
        
        plan = ExecutionPlan(
            plan_id="plan-error",
            created_at=datetime(2026, 3, 20, 12, 0, 0),
            experiment_id="exp-001",
            runs=[run],
        )

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(plan)

        # Assert: Failure result returned
        assert len(results) == 1
        result = results[0]
        assert result.status == "failure"
        assert result.response_text is None
        assert result.selected_answer is None
        assert result.error_type is not None
        assert "API connection error" in result.error_message

    @pytest.mark.asyncio
    async def test_engine_records_attempt_count(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item,
    ):
        """Verify retry attempts are tracked."""
        # Arrange
        run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=42,
            prompts_effective=Prompts(
                system="You are a helpful assistant.",
                user="Answer the question: {question}",
            ),
            retry_policy=RetryPolicy(max_attempts=3),
            variants=[sample_variant],
            items=[sample_item],
        )
        
        plan = ExecutionPlan(
            plan_id="plan-attempts",
            created_at=datetime(2026, 3, 20, 12, 0, 0),
            experiment_id="exp-001",
            runs=[run],
        )

        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(plan)

        # Assert: Attempt count is tracked
        assert len(results) == 1
        result = results[0]
        assert result.attempt_count >= 1


# ============================================================================
# Result Structure Tests
# ============================================================================


class TestExecutionResultStructure:
    """Tests for ExecutionResult data structure."""

    def test_execution_result_has_all_fields(self):
        """Verify ExecutionResult has all required fields."""
        result = ExecutionResult(
            item_id="run-001::var-abc::snap-xyz::it-1",
            run_id="run-001",
            variant_id="var-abc",
            snapshot_id="snap-xyz",
            question_id="q1",
            status="success",
            response_text="The answer is (B).",
            selected_answer="B",
            parse_confidence="clear",
            latency_ms=500,
            input_tokens=50,
            response_tokens=10,
            error_type=None,
            error_message=None,
            attempt_count=1,
        )

        # Assert all fields are accessible
        assert result.item_id == "run-001::var-abc::snap-xyz::it-1"
        assert result.run_id == "run-001"
        assert result.variant_id == "var-abc"
        assert result.snapshot_id == "snap-xyz"
        assert result.question_id == "q1"
        assert result.status == "success"
        assert result.response_text == "The answer is (B)."
        assert result.selected_answer == "B"
        assert result.parse_confidence == "clear"
        assert result.latency_ms == 500
        assert result.input_tokens == 50
        assert result.response_tokens == 10
        assert result.error_type is None
        assert result.error_message is None
        assert result.attempt_count == 1

    def test_execution_result_failure(self):
        """Verify ExecutionResult for failure case."""
        result = ExecutionResult(
            item_id="run-001::var-abc::snap-xyz::it-1",
            run_id="run-001",
            variant_id="var-abc",
            snapshot_id="snap-xyz",
            question_id="q1",
            status="failure",
            response_text=None,
            selected_answer=None,
            parse_confidence=None,
            latency_ms=None,
            input_tokens=None,
            response_tokens=None,
            error_type="api_error",
            error_message="Connection timeout",
            attempt_count=3,
        )

        assert result.status == "failure"
        assert result.error_type == "api_error"
        assert result.error_message == "Connection timeout"
        assert result.attempt_count == 3


# ============================================================================
# Integration-style Tests
# ============================================================================


@pytest.mark.integration
class TestExecutionEngineIntegration:
    """Integration-style tests for ExecutionEngine."""

    @pytest.mark.asyncio
    async def test_full_execution_flow(
        self, mock_api_client, mock_randomizer, mock_parser,
        sample_variant, sample_item,
    ):
        """Test complete execution flow from plan to results."""
        # Arrange
        run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=42,
            prompts_effective=Prompts(
                system="You are a helpful assistant.",
                user="Answer the question: {question}",
            ),
            retry_policy=RetryPolicy(),
            variants=[sample_variant],
            items=[sample_item],
        )
        
        plan = ExecutionPlan(
            plan_id="plan-integration",
            created_at=datetime(2026, 3, 20, 12, 0, 0),
            experiment_id="exp-001",
            runs=[run],
        )
        
        engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_parser)

        # Act
        results = engine.execute(plan)

        # Assert: Full flow completed
        assert len(results) == 1
        result = results[0]

        # Verify result structure
        assert result.item_id == plan.runs[0].items[0].item_id
        assert result.run_id == plan.runs[0].run_id
        assert result.variant_id == plan.runs[0].variants[0].variant_id
        assert result.status == "success"
        assert result.selected_answer == "B"
        assert result.parse_confidence == "clear"

        # Verify API was called
        assert len(mock_api_client.call_args_list) == 1

        # Verify randomizer was called (seed is set)
        mock_randomizer.set_seed.assert_called_once()

        # Verify parser was called
        mock_parser.parse.assert_called_once()
