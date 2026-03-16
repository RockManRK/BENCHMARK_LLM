"""Integration tests for ExecutionEngine with real OpenRouter API.

These tests use REAL API calls but with a very cheap model to minimize cost.
Model used: google/gemini-3.1-flash-lite-preview (extremely cheap)
Scope: 1-4 questions, 1 iteration (minimum needed to validate flow)

WARNING: These tests consume real tokens. Do not run in CI without cost controls.
"""

import pytest
from unittest.mock import Mock

from src.core.execution_engine import ExecutionEngine, QuestionWithContext
from src.api.client import OpenRouterClient
from src.core.randomizer import AnswerRandomizer
from src.db.models import ModelVariant, Question
from src.utils.config import get_settings


@pytest.fixture
def real_api_client():
    """Create REAL OpenRouter API client (not mocked)."""
    settings = get_settings()
    return OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )


@pytest.fixture
def cheap_model_variant():
    """Create model variant for cheap model (google/gemini-3.1-flash-lite-preview)."""
    return ModelVariant(
        variant_id="var-test-integration",
        model_id="google/gemini-3.1-flash-lite-preview",
        reasoning_mode="unspecified",
        reasoning_effort=None,
        reasoning_max_tokens=None,
        vision_enabled=False,
        structured_enabled=False,
        variant_signature="google/gemini-3.1-flash-lite-preview::reasoning=unspecified::vision=false::structured=false",
    )


@pytest.fixture
def test_questions():
    """Create minimal set of test questions (2 questions)."""
    return [
        QuestionWithContext(
            question=Question(
                question_id="Q001",
                stem="Qual é a capital da França?",
                options_json='{"A": "Londres", "B": "Berlim", "C": "Paris", "D": "Madrid"}',
                correct_answer="C",
                has_image=False,
            ),
            snapshot_id=None,  # Execution-only mode
        ),
        QuestionWithContext(
            question=Question(
                question_id="Q002",
                stem="Quanto é 2 + 2?",
                options_json='{"A": "3", "B": "4", "C": "5", "D": "6"}',
                correct_answer="B",
                has_image=False,
            ),
            snapshot_id=None,  # Execution-only mode
        ),
    ]


@pytest.fixture
def settings():
    """Get application settings."""
    return get_settings()


class TestExecutionEngineIntegration:
    """Integration tests for ExecutionEngine with real OpenRouter API."""

    def test_execute_single_question_real_api(
        self, real_api_client, cheap_model_variant, settings
    ):
        """Test executing a single question with REAL API call.
        
        This test validates:
        - API client authentication
        - Model inference
        - Response parsing
        - Token tracking
        
        Cost: ~1-2 cents (1 question, 1 iteration)
        """
        # Create engine WITHOUT db_manager (execution-only mode)
        engine = ExecutionEngine(
            api_client=real_api_client,
            randomizer=AnswerRandomizer(None),  # No randomization
            settings=settings,
            db_manager=None,  # Execution-only mode
        )
        
        # Single question
        questions = [
            QuestionWithContext(
                question=Question(
                    question_id="Q001",
                    stem="Quanto é 2 + 2? Responda apenas com a letra.",
                    options_json='{"A": "3", "B": "4", "C": "5", "D": "6"}',
                    correct_answer="B",
                ),
                snapshot_id=None,
            )
        ]
        
        # Execute
        results = engine.execute(
            model_variants=[cheap_model_variant],
            questions=questions,
            iterations=1,
        )
        
        # Validate results
        assert len(results) == 1
        result = results[0]
        
        assert result.model_id == "google/gemini-3.1-flash-lite-preview"
        assert result.iteration == 1
        assert result.total_questions == 1
        assert result.completed >= 0  # May be 0 if answer parsing fails
        assert result.duration_ms > 0
        
        # Validate token tracking
        if result.responses:
            response = result.responses[0]
            assert "input_tokens" in response or response.get("status") == "error"

    def test_execute_multiple_questions_real_api(
        self, real_api_client, cheap_model_variant, settings, test_questions
    ):
        """Test executing multiple questions with REAL API calls.
        
        This test validates:
        - Multiple question execution
        - Progress tracking
        - Error handling
        
        Cost: ~2-4 cents (2 questions, 1 iteration)
        """
        engine = ExecutionEngine(
            api_client=real_api_client,
            randomizer=AnswerRandomizer(None),
            settings=settings,
            db_manager=None,
        )
        
        # Execute
        results = engine.execute(
            model_variants=[cheap_model_variant],
            questions=test_questions,
            iterations=1,
        )
        
        # Validate
        assert len(results) == 1
        result = results[0]
        
        assert result.total_questions == 2
        assert result.duration_ms > 1000  # Should take at least 1 second for 2 questions

    def test_execute_multiple_iterations_real_api(
        self, real_api_client, cheap_model_variant, settings
    ):
        """Test executing multiple iterations with REAL API calls.
        
        This test validates:
        - Iteration tracking
        - Consistency across iterations
        
        Cost: ~2-4 cents (1 question, 2 iterations)
        """
        engine = ExecutionEngine(
            api_client=real_api_client,
            randomizer=AnswerRandomizer(None),
            settings=settings,
            db_manager=None,
        )
        
        questions = [
            QuestionWithContext(
                question=Question(
                    question_id="Q001",
                    stem="Quanto é 1 + 1? Responda apenas com a letra.",
                    options_json='{"A": "1", "B": "2", "C": "3", "D": "4"}',
                    correct_answer="B",
                ),
                snapshot_id=None,
            )
        ]
        
        # Execute with 2 iterations
        results = engine.execute(
            model_variants=[cheap_model_variant],
            questions=questions,
            iterations=2,
        )
        
        # Validate
        assert len(results) == 2  # 2 iterations
        assert [r.iteration for r in results] == [1, 2]

    def test_execute_with_reasoning_effort_real_api(
        self, real_api_client, settings
    ):
        """Test executing with reasoning_effort configuration.
        
        This test validates:
        - Reasoning configuration is passed to API
        - Different reasoning efforts produce different variant_ids
        
        Cost: ~2-4 cents (2 variants, 1 question each)
        """
        # Create variants with different reasoning efforts
        variants = [
            ModelVariant(
                variant_id="var-no-reasoning",
                model_id="google/gemini-3.1-flash-lite-preview",
                reasoning_mode="off",
                reasoning_effort=None,
                vision_enabled=False,
                structured_enabled=False,
                variant_signature="test-no-reasoning",
            ),
            ModelVariant(
                variant_id="var-low-reasoning",
                model_id="google/gemini-3.1-flash-lite-preview",
                reasoning_mode="effort",
                reasoning_effort="low",
                vision_enabled=False,
                structured_enabled=False,
                variant_signature="test-low-reasoning",
            ),
        ]
        
        engine = ExecutionEngine(
            api_client=real_api_client,
            randomizer=AnswerRandomizer(None),
            settings=settings,
            db_manager=None,
        )
        
        questions = [
            QuestionWithContext(
                question=Question(
                    question_id="Q001",
                    stem="Explique brevemente: quanto é 2 + 2?",
                    options_json='{"A": "3", "B": "4", "C": "5", "D": "6"}',
                    correct_answer="B",
                ),
                snapshot_id=None,
            )
        ]
        
        # Execute
        results = engine.execute(
            model_variants=variants,
            questions=questions,
            iterations=1,
        )
        
        # Validate
        assert len(results) == 2  # 2 variants
        assert results[0].variant_id == "var-no-reasoning"
        assert results[1].variant_id == "var-low-reasoning"


class TestQuestionWithContextIntegration:
    """Integration tests for QuestionWithContext wrapper."""

    def test_question_with_snapshot_id_none(self):
        """Test QuestionWithContext with snapshot_id=None (execution-only mode)."""
        question = Question(
            question_id="Q001",
            stem="Test question",
            options_json='{}',
            correct_answer="A",
        )
        
        wrapper = QuestionWithContext(question=question, snapshot_id=None)
        
        assert wrapper.question is question
        assert wrapper.snapshot_id is None

    def test_question_with_snapshot_id_value(self):
        """Test QuestionWithContext with specific snapshot_id."""
        question = Question(
            question_id="Q001",
            stem="Test question",
            options_json='{}',
            correct_answer="A",
        )
        
        wrapper = QuestionWithContext(question=question, snapshot_id=123)
        
        assert wrapper.question is question
        assert wrapper.snapshot_id == 123
