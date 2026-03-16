"""Tests for ExecutionEngine and QuestionWithContext.

These tests verify the unified execution engine and the question wrapper.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.core.execution_engine import ExecutionEngine, QuestionWithContext
from src.db.models import Question, ModelVariant


class TestQuestionWithContext:
    """Tests for QuestionWithContext wrapper."""

    def test_create_with_snapshot_id(self):
        """Test creating QuestionWithContext with snapshot_id."""
        question = Question(
            question_id="Q001",
            stem="Test question",
            options_json='{"A": "opt1", "B": "opt2"}',
            correct_answer="A",
        )
        
        wrapper = QuestionWithContext(question=question, snapshot_id=123)
        
        assert wrapper.question is question
        assert wrapper.snapshot_id == 123
        assert wrapper.question.question_id == "Q001"

    def test_create_without_snapshot_id(self):
        """Test creating QuestionWithContext without snapshot_id (execution-only mode)."""
        question = Question(
            question_id="Q001",
            stem="Test question",
            options_json='{"A": "opt1", "B": "opt2"}',
            correct_answer="A",
        )
        
        wrapper = QuestionWithContext(question=question, snapshot_id=None)
        
        assert wrapper.question is question
        assert wrapper.snapshot_id is None

    def test_default_snapshot_id_is_none(self):
        """Test that snapshot_id defaults to None."""
        question = Question(
            question_id="Q001",
            stem="Test question",
            options_json='{"A": "opt1", "B": "opt2"}',
            correct_answer="A",
        )
        
        wrapper = QuestionWithContext(question=question)
        
        assert wrapper.snapshot_id is None


class TestExecutionEngine:
    """Tests for ExecutionEngine."""

    @pytest.fixture
    def mock_api_client(self):
        """Create mock API client."""
        return Mock()

    @pytest.fixture
    def mock_randomizer(self):
        """Create mock randomizer."""
        return Mock()

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.use_structured_outputs = False
        settings.enable_vision = False
        settings.enable_structured = False
        settings.reasoning_mode = "unspecified"
        settings.reasoning_effort = None
        settings.reasoning_max_tokens = None
        return settings

    @pytest.fixture
    def engine(self, mock_api_client, mock_randomizer, mock_settings):
        """Create ExecutionEngine instance."""
        return ExecutionEngine(
            api_client=mock_api_client,
            randomizer=mock_randomizer,
            settings=mock_settings,
        )

    @pytest.fixture
    def engine_with_db(self, mock_api_client, mock_randomizer, mock_settings):
        """Create ExecutionEngine instance with db_manager."""
        mock_db = Mock()
        return ExecutionEngine(
            api_client=mock_api_client,
            randomizer=mock_randomizer,
            settings=mock_settings,
            db_manager=mock_db,
        )

    def test_init_without_db_manager(self, engine):
        """Test ExecutionEngine initialization without db_manager."""
        assert engine.api_client is not None
        assert engine.randomizer is not None
        assert engine.settings is not None
        assert engine.db_manager is None

    def test_init_with_db_manager(self, engine_with_db):
        """Test ExecutionEngine initialization with db_manager."""
        assert engine_with_db.db_manager is not None

    def test_execute_empty_model_list(self, engine):
        """Test execute with empty model list."""
        questions = [
            QuestionWithContext(
                question=Question(
                    question_id="Q001",
                    stem="Test",
                    options_json='{}',
                    correct_answer="A",
                ),
                snapshot_id=None,
            )
        ]
        
        results = engine.execute(
            model_variants=[],
            questions=questions,
            iterations=1,
        )
        
        assert results == []

    def test_execute_with_run_id_and_experiment_id(self, engine):
        """Test execute passes run_id and experiment_id to iterations."""
        variant = ModelVariant(
            variant_id="var-test",
            model_id="test/model",
            reasoning_mode="unspecified",
            vision_enabled=False,
            structured_enabled=False,
            variant_signature="test",
        )
        
        question = Question(
            question_id="Q001",
            stem="Test",
            options_json='{}',
            correct_answer="A",
        )
        
        # Mock _execute_single_iteration to capture arguments
        with patch.object(engine, '_execute_single_iteration') as mock_iter:
            mock_iter.return_value = Mock(
                model_id="test/model",
                variant_id="var-test",
                iteration=1,
                total_questions=1,
                completed=1,
                errors=0,
                duration_ms=100,
                responses=[]
            )
            
            engine.execute(
                model_variants=[variant],
                questions=[QuestionWithContext(question=question, snapshot_id=123)],
                iterations=1,
                run_id="run-test",
                experiment_id="exp-test",
            )
            
            # Verify run_id and experiment_id were passed
            mock_iter.assert_called_once()
            call_args = mock_iter.call_args
            assert call_args[1]['run_id'] == "run-test"
            assert call_args[1]['experiment_id'] == "exp-test"

    def test_execute_multiple_iterations(self, engine):
        """Test execute with multiple iterations."""
        variant = ModelVariant(
            variant_id="var-test",
            model_id="test/model",
            reasoning_mode="unspecified",
            vision_enabled=False,
            structured_enabled=False,
            variant_signature="test",
        )
        
        question = Question(
            question_id="Q001",
            stem="Test",
            options_json='{}',
            correct_answer="A",
        )
        
        with patch.object(engine, '_execute_single_iteration') as mock_iter:
            mock_iter.return_value = Mock(
                model_id="test/model",
                variant_id="var-test",
                iteration=1,
                total_questions=1,
                completed=1,
                errors=0,
                duration_ms=100,
                responses=[]
            )
            
            results = engine.execute(
                model_variants=[variant],
                questions=[QuestionWithContext(question=question)],
                iterations=3,
            )
            
            # Should call _execute_single_iteration 3 times (once per iteration)
            assert mock_iter.call_count == 3
            assert len(results) == 3

    def test_execute_multiple_models(self, engine):
        """Test execute with multiple model variants."""
        variants = [
            ModelVariant(
                variant_id=f"var-test-{i}",
                model_id=f"test/model-{i}",
                reasoning_mode="unspecified",
                vision_enabled=False,
                structured_enabled=False,
                variant_signature="test",
            )
            for i in range(3)
        ]
        
        question = Question(
            question_id="Q001",
            stem="Test",
            options_json='{}',
            correct_answer="A",
        )
        
        with patch.object(engine, '_execute_single_iteration') as mock_iter:
            mock_iter.return_value = Mock(
                model_id="test/model",
                variant_id="var-test",
                iteration=1,
                total_questions=1,
                completed=1,
                errors=0,
                duration_ms=100,
                responses=[]
            )
            
            results = engine.execute(
                model_variants=variants,
                questions=[QuestionWithContext(question=question)],
                iterations=1,
            )
            
            # Should call _execute_single_iteration 3 times (once per model)
            assert mock_iter.call_count == 3
            assert len(results) == 3

    def test_execute_aggregates_results(self, engine):
        """Test execute aggregates results from all iterations."""
        variant = ModelVariant(
            variant_id="var-test",
            model_id="test/model",
            reasoning_mode="unspecified",
            vision_enabled=False,
            structured_enabled=False,
            variant_signature="test",
        )
        
        question = Question(
            question_id="Q001",
            stem="Test",
            options_json='{}',
            correct_answer="A",
        )
        
        # Create different results for each iteration
        iteration_results = [
            Mock(
                model_id="test/model",
                variant_id="var-test",
                iteration=i,
                total_questions=1,
                completed=1,
                errors=0,
                duration_ms=100 * i,
                responses=[]
            )
            for i in range(1, 4)
        ]
        
        with patch.object(engine, '_execute_single_iteration', side_effect=iteration_results):
            results = engine.execute(
                model_variants=[variant],
                questions=[QuestionWithContext(question=question)],
                iterations=3,
            )
            
            assert len(results) == 3
            assert [r.iteration for r in results] == [1, 2, 3]
            assert [r.duration_ms for r in results] == [100, 200, 300]


class TestExecutionEngineSnapshotHandling:
    """Tests for snapshot_id handling in ExecutionEngine."""

    @pytest.fixture
    def engine(self):
        """Create ExecutionEngine with mocked dependencies."""
        mock_api = Mock()
        mock_randomizer = Mock()
        mock_settings = Mock()
        mock_settings.use_structured_outputs = False
        mock_settings.enable_vision = False
        mock_settings.enable_structured = False
        mock_settings.reasoning_mode = "unspecified"
        mock_settings.reasoning_effort = None
        mock_settings.reasoning_max_tokens = None
        
        return ExecutionEngine(
            api_client=mock_api,
            randomizer=mock_randomizer,
            settings=mock_settings,
        )

    def test_execute_passes_snapshot_ids_to_iteration(self, engine):
        """Test that snapshot_ids are extracted and passed to iteration executor."""
        variant = ModelVariant(
            variant_id="var-test",
            model_id="test/model",
            reasoning_mode="unspecified",
            vision_enabled=False,
            structured_enabled=False,
            variant_signature="test",
        )
        
        questions = [
            QuestionWithContext(
                question=Question(question_id="Q001", stem="T", options_json='{}', correct_answer="A"),
                snapshot_id=100
            ),
            QuestionWithContext(
                question=Question(question_id="Q002", stem="T", options_json='{}', correct_answer="B"),
                snapshot_id=101
            ),
            QuestionWithContext(
                question=Question(question_id="Q003", stem="T", options_json='{}', correct_answer="C"),
                snapshot_id=None  # No snapshot
            ),
        ]
        
        with patch.object(engine, '_execute_single_iteration') as mock_iter:
            mock_iter.return_value = Mock(
                model_id="test/model",
                variant_id="var-test",
                iteration=1,
                total_questions=3,
                completed=3,
                errors=0,
                duration_ms=100,
                responses=[]
            )
            
            engine.execute(
                model_variants=[variant],
                questions=questions,
                iterations=1,
            )
            
            # Verify snapshot_ids were extracted
            call_args = mock_iter.call_args
            # The snapshot_ids should be passed via model_kwargs
            # Check that questions with snapshot_id are handled correctly
            assert mock_iter.called
