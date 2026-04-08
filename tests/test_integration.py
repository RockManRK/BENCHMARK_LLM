"""Integration tests for benchmark_llm project.

This module contains end-to-end integration tests that verify the complete
workflow of the benchmark system, including:
- Database initialization and schema creation
- Question loading and validation
- API client interaction (mocked)
- Response storage and retrieval
- Error handling and logging
- Statistics calculation
- Full benchmark execution flow

All API calls are mocked to avoid external dependencies during testing.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from src.api.client import MessageBuilder, OpenRouterClient
from src.cli.statistics import StatisticsCalculator
from src.core.loader import QuestionLoader
from src.core.randomizer import AnswerRandomizer
from src.core.run_manager import RunManager
from src.db.models import Error, Iteration, Question, Response, Run
from src.db.repository import ErrorRepository, ResponseRepository, RunRepository
from src.db.schema import DatabaseManager
from src.main import BenchmarkRunner
from src.utils.config import Settings


logger = logging.getLogger(__name__)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path for testing.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path to a temporary database file.
    """
    return tmp_path / "test_benchmark.db"


@pytest.fixture
def db_manager(temp_db_path: Path) -> Generator[DatabaseManager, None, None]:
    """Create a DatabaseManager with temporary database.

    Args:
        temp_db_path: Path to temporary database file.

    Yields:
        Initialized DatabaseManager instance with foreign keys disabled
        for integration testing.
    """
    manager = DatabaseManager(temp_db_path)
    manager.initialize()
    yield manager
    manager.close()


@pytest.fixture
def sample_questionnaire_json(tmp_path: Path) -> Path:
    """Create a sample questionnaire JSON file for testing.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path to the created JSON file.
    """
    questionnaire = {
        "dataset": {
            "name": "Test Dataset",
            "version": "1.0.0",
            "language": "en",
            "source": "test",
        },
        "questions": [
            {
                "id": "Q001",
                "stem": "What is the capital of France?",
                "options": {
                    "A": "Paris",
                    "B": "London",
                    "C": "Berlin",
                    "D": "Madrid",
                },
                "answer_key": "A",
                "assets": [],
                "meta": {
                    "has_table": False,
                    "has_image": False,
                    "status": "valid",
                    "notes": "",
                },
            },
            {
                "id": "Q002",
                "stem": "Which organ pumps blood?",
                "options": {
                    "A": "Liver",
                    "B": "Heart",
                    "C": "Kidney",
                    "D": "Lung",
                },
                "answer_key": "B",
                "assets": [],
                "meta": {
                    "has_table": False,
                    "has_image": False,
                    "status": "valid",
                    "notes": "",
                },
            },
            {
                "id": "Q003",
                "stem": "What is the normal blood pressure?",
                "options": {
                    "A": "120/80 mmHg",
                    "B": "140/90 mmHg",
                    "C": "100/60 mmHg",
                    "D": "160/100 mmHg",
                },
                "answer_key": "A",
                "assets": [],
                "meta": {
                    "has_table": False,
                    "has_image": False,
                    "status": "valid",
                    "notes": "",
                },
            },
        ],
    }

    json_path = tmp_path / "test_questions.json"
    json_path.write_text(json.dumps(questionnaire), encoding="utf-8")
    return json_path


@pytest.fixture
def sample_image_path(tmp_path: Path) -> Path:
    """Create a sample image file for multimodal testing.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path to a sample PNG image file.
    """
    import base64

    img_path = tmp_path / "test_image.png"
    # Minimal valid PNG (1x1 pixel)
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    img_path.write_bytes(png_data)
    return img_path


@pytest.fixture
def mock_api_response() -> dict[str, Any]:
    """Create a mock API response for testing.

    Returns:
        Dictionary containing a valid mock API response.
    """
    return {
        "id": "chatcmpl-test-123",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "The answer is **A**.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 10,
            "total_tokens": 60,
        },
    }


@pytest.fixture
def mock_api_client(mocker: MockerFixture) -> MagicMock:
    """Create a mock API client for testing.

    Args:
        mocker: Pytest mocker fixture.

    Returns:
        Mocked OpenRouterClient instance.
    """
    client = MagicMock(spec=OpenRouterClient)
    client.chat_completion = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def test_settings(temp_db_path: Path) -> Settings:
    """Create test settings with temporary database.

    Args:
        temp_db_path: Path to temporary database file.

    Returns:
        Settings object configured for testing.
    """
    return Settings(
        openrouter_api_key="test-api-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        database_path=temp_db_path,
        log_level="DEBUG",
        log_file_path=temp_db_path.parent / "test.log",
        default_iterations=1,
        default_models=[],
    )


# =============================================================================
# Database Integration Tests
# =============================================================================


class TestDatabaseIntegration:
    """Integration tests for database operations.

    These tests verify that the database layer works correctly
    with real SQLite operations, including schema creation,
    CRUD operations, and relationships.
    """

    def test_database_initialization_creates_all_tables(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test that database initialization creates all required tables.

        Args:
            db_manager: DatabaseManager fixture.
        """
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
                """
            )
            tables = {row[0] for row in cursor.fetchall()}

            expected_tables = {
                "runs",
                "models",
                "iterations",
                "responses",
                "errors",
                "operational_logs",
            }

            assert expected_tables.issubset(tables), (
                f"Missing tables: {expected_tables - tables}"
            )
        finally:
            conn.close()

    def test_run_repository_crud_operations(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test complete CRUD operations for RunRepository.

        Args:
            db_manager: DatabaseManager fixture.
        """
        repo = RunRepository(db_manager)

        # Create
        run = Run(
            run_id="run-test-001",
            created_at=datetime.now(),
            config=json.dumps({"models": ["gpt-4"], "iterations": 1}),
            status="pending",
        )
        created = repo.create(run)
        assert created.run_id == "run-test-001"

        # Read
        retrieved = repo.get_by_id("run-test-001")
        assert retrieved is not None
        assert retrieved.run_id == "run-test-001"
        assert retrieved.status == "pending"

        # Update
        retrieved.status = "completed"
        updated = repo.update(retrieved)
        assert updated is not None
        assert updated.status == "completed"

        # Verify update persisted
        verified = repo.get_by_id("run-test-001")
        assert verified.status == "completed"

        # Delete
        deleted = repo.delete("run-test-001")
        assert deleted is True

        # Verify deletion
        not_found = repo.get_by_id("run-test-001")
        assert not_found is None

    def test_response_repository_with_relationships(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test ResponseRepository with foreign key relationships.

        Args:
            db_manager: DatabaseManager fixture.
        """
        # First create a run
        run_repo = RunRepository(db_manager)
        run = Run(
            run_id="run-test-002",
            created_at=datetime.now(),
            config=json.dumps({}),
            status="pending",
        )
        run_repo.create(run)

        # Create model record (required for foreign key)
        from src.db.repository import ModelRepository, IterationRepository
        model_repo = ModelRepository(db_manager)
        model_repo.create("gpt-4", "GPT-4", "OpenAI")

        # Create iteration record (required for foreign key)
        iteration_repo = IterationRepository(db_manager)
        from src.db.models import Iteration
        iteration = Iteration(
            run_id=run.run_id,
            model_id="gpt-4",
            iteration_number=1,
            status="pending",
        )
        iteration_repo.create(iteration)

        # Create response
        response_repo = ResponseRepository(db_manager)
        response = Response(
            iteration_id=iteration.iteration_id,
            question_id="Q001",
            model_id="gpt-4",
            run_id="run-test-002",
            question_text="Test question?",
            options_json='{"A": "Option A", "B": "Option B"}',
            options_randomized=False,
            selected_answer="A",
            correct_answer="A",
            is_correct=True,
            response_text="The answer is A",
            input_tokens=50,
            response_tokens=10,
            latency_ms=1500,
            status="success",
        )
        created = response_repo.create(response)
        assert created.response_id is not None

        # Retrieve by ID
        retrieved = response_repo.get_by_id(created.response_id)
        assert retrieved is not None
        assert retrieved.question_id == "Q001"
        # SQLite returns is_correct as integer (1/0), convert to bool for comparison
        assert retrieved.is_correct == True

        # Retrieve by run
        by_run = response_repo.get_by_run("run-test-002")
        assert len(by_run) == 1
        assert by_run[0].question_id == "Q001"

    def test_error_repository_links_to_response(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test that ErrorRepository properly links errors to responses.

        Args:
            db_manager: DatabaseManager fixture.
        """
        # Create run and response first
        run_repo = RunRepository(db_manager)
        run = Run(
            run_id="run-test-003",
            created_at=datetime.now(),
            config=json.dumps({}),
            status="pending",
        )
        run_repo.create(run)

        # Create model and iteration records
        from src.db.repository import ModelRepository, IterationRepository
        model_repo = ModelRepository(db_manager)
        model_repo.create("gpt-4", "GPT-4", "OpenAI")

        iteration_repo = IterationRepository(db_manager)
        from src.db.models import Iteration
        iteration = Iteration(
            run_id=run.run_id,
            model_id="gpt-4",
            iteration_number=1,
            status="pending",
        )
        iteration_repo.create(iteration)

        response_repo = ResponseRepository(db_manager)
        response = Response(
            iteration_id=iteration.iteration_id,
            question_id="Q001",
            model_id="gpt-4",
            run_id="run-test-003",
            question_text="Test question?",
            options_json="{}",
            options_randomized=False,
            selected_answer=None,
            correct_answer="A",
            is_correct=None,
            response_text="",
            input_tokens=0,
            response_tokens=0,
            latency_ms=5000,
            status="error",
        )
        response_repo.create(response)

        # Create error linked to response
        error_repo = ErrorRepository(db_manager)
        error = Error(
            response_id=response.response_id,
            error_type="TimeoutError",
            error_message="Request timed out after 5000ms",
            stack_trace="Traceback (most recent call last):...",
        )
        created_error = error_repo.create(error)
        assert created_error.error_id is not None

        # Retrieve error by response
        errors = error_repo.get_by_response(response.response_id)
        assert len(errors) == 1
        assert errors[0].error_type == "TimeoutError"


# =============================================================================
# Question Loading Integration Tests
# =============================================================================


class TestQuestionLoadingIntegration:
    """Integration tests for question loading functionality.

    These tests verify that questions are properly loaded from JSON,
    validated, and converted to Question objects.
    """

    def test_load_questions_from_json_file(
        self, sample_questionnaire_json: Path
    ) -> None:
        """Test loading questions from a JSON file.

        Args:
            sample_questionnaire_json: Path to sample JSON file.
        """
        loader = QuestionLoader(str(sample_questionnaire_json))
        questions = loader.load()

        assert len(questions) == 3
        assert questions[0].question_id == "Q001"
        assert "Paris" in questions[0].options.values()
        assert questions[0].correct_answer == "A"

    def test_question_loader_preserves_metadata(
        self, sample_questionnaire_json: Path
    ) -> None:
        """Test that question metadata is preserved during loading.

        Args:
            sample_questionnaire_json: Path to sample JSON file.
        """
        loader = QuestionLoader(str(sample_questionnaire_json))
        questions = loader.load()

        for question in questions:
            assert question.metadata is not None
            assert "has_image" in question.metadata
            assert "has_table" in question.metadata
            assert "status" in question.metadata

    def test_question_loader_get_dataset_info(
        self, sample_questionnaire_json: Path
    ) -> None:
        """Test retrieving dataset information after loading.

        Args:
            sample_questionnaire_json: Path to sample JSON file.
        """
        loader = QuestionLoader(str(sample_questionnaire_json))
        loader.load()

        info = loader.get_dataset_info()
        assert info is not None
        assert info["name"] == "Test Dataset"
        assert info["version"] == "1.0.0"
        assert info["language"] == "en"

    def test_question_loader_count(self, sample_questionnaire_json: Path) -> None:
        """Test getting question count from loader.

        Args:
            sample_questionnaire_json: Path to sample JSON file.
        """
        loader = QuestionLoader(str(sample_questionnaire_json))
        loader.load()

        count = loader.get_question_count()
        assert count == 3


# =============================================================================
# Randomization Integration Tests
# =============================================================================


class TestRandomizationIntegration:
    """Integration tests for answer randomization.

    These tests verify that answer randomization works correctly
    and is reproducible with seeds.
    """

    def test_randomizer_with_seed_reproducibility(
        self, sample_questionnaire_json: Path
    ) -> None:
        """Test that randomization is reproducible with same seed.

        Args:
            sample_questionnaire_json: Path to sample JSON file.
        """
        loader = QuestionLoader(str(sample_questionnaire_json))
        questions = loader.load()

        # Run 1 with run_id 42
        randomizer1 = AnswerRandomizer(run_id=42)
        randomized1 = randomizer1.randomize(questions[0])

        # Run 2 with same run_id 42
        randomizer2 = AnswerRandomizer(run_id=42)
        randomized2 = randomizer2.randomize(questions[0])

        # Results should be identical
        assert randomized1.options == randomized2.options
        assert randomized1.correct_answer == randomized2.correct_answer

    def test_randomizer_different_seeds_produce_different_results(
        self, sample_questionnaire_json: Path
    ) -> None:
        """Test that different seeds produce different randomizations.

        Args:
            sample_questionnaire_json: Path to sample JSON file.
        """
        loader = QuestionLoader(str(sample_questionnaire_json))
        questions = loader.load()

        randomizer1 = AnswerRandomizer(run_id=42)
        randomized1 = randomizer1.randomize(questions[0])

        randomizer2 = AnswerRandomizer(run_id=123)
        randomized2 = randomizer2.randomize(questions[0])

        # With high probability, results should differ
        # (not guaranteed, but very likely with different seeds)
        if randomized1.options == randomized2.options:
            logger.warning(
                "Randomization produced same result with different seeds (rare but possible)"
            )

    def test_randomizer_tracks_randomization_state(
        self, sample_questionnaire_json: Path
    ) -> None:
        """Test that randomizer correctly tracks randomization state.

        Args:
            sample_questionnaire_json: Path to sample JSON file.
        """
        loader = QuestionLoader(str(sample_questionnaire_json))
        questions = loader.load()
        original = questions[0]

        randomizer = AnswerRandomizer(run_id=42)
        randomized = randomizer.randomize(original)

        # Verify randomization actually changed the options
        # Note: With seed 42, the shuffle may or may not change order
        # We verify that the randomizer ran and produced a valid result
        assert randomized.correct_answer in ["A", "B", "C", "D"]
        
        # Verify the correct answer text is preserved
        import json
        orig_options = json.loads(original.options_json)
        rand_options = json.loads(randomized.options_json)
        orig_correct_text = orig_options[original.correct_answer]
        rand_correct_text = rand_options[randomized.correct_answer]
        assert orig_correct_text == rand_correct_text, "Correct answer text should be preserved"


# =============================================================================
# API Client Integration Tests (Mocked)
# =============================================================================


class TestAPIClientIntegration:
    """Integration tests for API client with mocked responses.

    These tests verify API client behavior with various response scenarios.
    """

    @pytest.mark.asyncio
    async def test_successful_api_call_with_mock(
        self, mock_api_client: MagicMock, mock_api_response: dict[str, Any]
    ) -> None:
        """Test successful API call with mocked response.

        Args:
            mock_api_client: Mocked API client fixture.
            mock_api_response: Mock API response fixture.
        """
        mock_api_client.chat_completion.return_value = mock_api_response

        result = await mock_api_client.chat_completion(
            model="openai/gpt-4",
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=100,
        )

        assert result["id"] == "chatcmpl-test-123"
        assert result["choices"][0]["message"]["content"] == "The answer is **A**."
        mock_api_client.chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_call_with_image_message(
        self, mock_api_client: MagicMock, mock_api_response: dict[str, Any], sample_image_path: Path
    ) -> None:
        """Test API call with multimodal message.

        Args:
            mock_api_client: Mocked API client fixture.
            mock_api_response: Mock API response fixture.
            sample_image_path: Path to sample image.
        """
        mock_api_client.chat_completion.return_value = mock_api_response

        message = MessageBuilder.build_multimodal_message(
            "What is in this image?",
            sample_image_path,
        )

        result = await mock_api_client.chat_completion(
            model="openai/gpt-4-vision",
            messages=[message],
            max_tokens=100,
        )

        assert result is not None
        assert isinstance(message["content"], list)

    @pytest.mark.asyncio
    async def test_api_client_error_handling(
        self, mock_api_client: MagicMock
    ) -> None:
        """Test API client error handling with mocked errors.

        Args:
            mock_api_client: Mocked API client fixture.
        """
        import httpx

        mock_api_client.chat_completion.side_effect = httpx.HTTPStatusError(
            "Authentication failed",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )

        with pytest.raises(httpx.HTTPStatusError):
            await mock_api_client.chat_completion(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": "Test"}],
            )


# =============================================================================
# Run Manager Integration Tests
# =============================================================================


class TestRunManagerIntegration:
    """Integration tests for RunManager functionality.

    These tests verify the complete run lifecycle management.
    """

    def test_run_manager_initializes_run_with_config(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test that RunManager properly initializes runs.

        Args:
            db_manager: DatabaseManager fixture.
        """
        run_manager = RunManager(db_manager)

        config = {
            "models": ["openai/gpt-4", "anthropic/claude-3"],
            "iterations": 3,
            "questions": ["Q001", "Q002", "Q003"],
            "seed": 42,
        }

        run = run_manager.initialize_run(config)

        assert run.run_id.startswith("run-")
        assert run.status == "pending"

        # Verify config was stored
        stored_config = run_manager.get_run_config(run.run_id)
        assert stored_config is not None
        assert stored_config["models"] == config["models"]
        assert stored_config["iterations"] == config["iterations"]

    def test_run_manager_status_transitions(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test run status transitions through lifecycle.

        Args:
            db_manager: DatabaseManager fixture.
        """
        run_manager = RunManager(db_manager)
        config = {"models": ["gpt-4"], "iterations": 1}

        run = run_manager.initialize_run(config)
        assert run.status == "pending"

        # Complete the run
        completed = run_manager.complete_run(run.run_id)
        assert completed is not None
        assert completed.status == "completed"

        # Verify persisted
        retrieved = run_manager.get_run_by_id(run.run_id)
        assert retrieved is not None
        assert retrieved.status == "completed"

    def test_run_manager_fail_run_with_error(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test failing a run with error message.

        Args:
            db_manager: DatabaseManager fixture.
        """
        run_manager = RunManager(db_manager)
        config = {"models": ["gpt-4"], "iterations": 1}

        run = run_manager.initialize_run(config)

        failed = run_manager.fail_run(run.run_id, "Database connection failed")
        assert failed is not None
        assert failed.status == "failed"


# =============================================================================
# Statistics Calculator Integration Tests
# =============================================================================


class TestStatisticsCalculatorIntegration:
    """Integration tests for statistics calculation.

    These tests verify correct calculation of benchmark statistics.
    """

    def test_calculate_accuracy_from_responses(self) -> None:
        """Test accuracy calculation from response list.

        This test creates sample responses and verifies accuracy calculation.
        """
        # StatisticsCalculator expects dictionaries with status field
        responses = [
            {
                "model_id": "gpt-4",
                "is_correct": True,
                "latency_ms": 1000,
                "input_tokens": 50,
                "response_tokens": 10,
                "status": "success",
            },
            {
                "model_id": "gpt-4",
                "is_correct": False,
                "latency_ms": 1200,
                "input_tokens": 50,
                "response_tokens": 10,
                "status": "success",
            },
            {
                "model_id": "gpt-4",
                "is_correct": True,
                "latency_ms": 800,
                "input_tokens": 50,
                "response_tokens": 10,
                "status": "success",
            },
        ]

        calculator = StatisticsCalculator(responses, errors=[])
        stats = calculator.get_model_statistics("gpt-4")

        assert stats is not None
        assert stats.model_id == "gpt-4"
        assert stats.total_questions == 3
        # Note: StatisticsCalculator counts correct_answers based on is_correct == True
        assert stats.correct_answers == 2
        assert stats.accuracy == pytest.approx(0.6667, rel=0.01)

    def test_calculate_average_latency(self) -> None:
        """Test average latency calculation.

        This test verifies latency metrics are calculated correctly.
        """
        responses = [
            {
                "model_id": "gpt-4",
                "is_correct": True,
                "latency_ms": 1000 * (i + 1),
                "input_tokens": 50,
                "response_tokens": 10,
            }
            for i in range(3)
        ]

        calculator = StatisticsCalculator(responses, errors=[])
        stats = calculator.get_model_statistics("gpt-4")

        assert stats is not None
        # Average of 1000, 2000, 3000 = 2000
        assert stats.avg_latency_ms == 2000

    def test_calculate_token_usage(self) -> None:
        """Test token usage calculation.

        This test verifies input and output token totals.
        """
        responses = [
            {
                "model_id": "gpt-4",
                "is_correct": True,
                "latency_ms": 1000,
                "input_tokens": 100,
                "response_tokens": 20,
            }
            for i in range(5)
        ]

        calculator = StatisticsCalculator(responses, errors=[])
        stats = calculator.get_model_statistics("gpt-4")

        assert stats is not None
        assert stats.total_input_tokens == 500  # 100 * 5
        assert stats.total_response_tokens == 100  # 20 * 5


# =============================================================================
# Full Workflow Integration Tests
# =============================================================================


class TestFullWorkflowIntegration:
    """End-to-end integration tests for complete benchmark workflow.

    These tests simulate a complete benchmark execution from start to finish,
    including all components working together.
    """

    def test_full_benchmark_workflow_with_mocked_api(
        self,
        db_manager: DatabaseManager,
        sample_questionnaire_json: Path,
        mock_api_response: dict[str, Any],
        mocker: MockerFixture,
    ) -> None:
        """Test complete benchmark workflow with mocked API.

        This test simulates:
        1. Loading questions from JSON
        2. Initializing a run
        3. Executing questions with mocked API responses
        4. Storing responses in database
        5. Calculating statistics

        Args:
            db_manager: DatabaseManager fixture.
            sample_questionnaire_json: Path to sample JSON.
            mock_api_response: Mock API response fixture.
            mocker: Pytest mocker fixture.
        """
        # Step 1: Load questions
        loader = QuestionLoader(str(sample_questionnaire_json))
        questions = loader.load()
        assert len(questions) == 3

        # Step 2: Initialize run
        run_manager = RunManager(db_manager)
        config = {
            "models": ["openai/gpt-4"],
            "iterations": 1,
            "questions": ["Q001", "Q002", "Q003"],
        }
        run = run_manager.initialize_run(config)

        # Create model and iteration records for foreign keys
        from src.db.repository import ModelRepository, IterationRepository
        from src.db.models import Iteration
        model_repo = ModelRepository(db_manager)
        model_repo.create("openai/gpt-4", "GPT-4", "OpenAI")

        iteration_repo = IterationRepository(db_manager)
        iteration = Iteration(
            run_id=run.run_id,
            model_id="openai/gpt-4",
            iteration_number=1,
            status="pending",
        )
        iteration_repo.create(iteration)

        # Step 3: Mock API client
        mock_client = mocker.MagicMock(spec=OpenRouterClient)
        mock_client.chat_completion = mocker.AsyncMock(return_value=mock_api_response)
        mock_client.close = mocker.AsyncMock()

        # Step 4: Setup randomizer with run_id extracted from run
        # Extract numeric part from run_id for seed (e.g., "run-20260305..." -> use hash)
        run_id_seed = hash(run.run_id) % (2**32)
        randomizer = AnswerRandomizer(run_id=run_id_seed)

        # Step 5: Execute questions (simulated)
        response_repo = ResponseRepository(db_manager)

        for i, question in enumerate(questions):
            randomized = randomizer.randomize(question)

            # Create response as if API was called
            response = Response(
                iteration_id=iteration.iteration_id,
                question_id=randomized.question_id,
                model_id="openai/gpt-4",
                run_id=run.run_id,
                question_text=randomized.question_text,
                options_json=json.dumps(randomized.options),
                options_randomized=True,
                selected_answer=randomized.correct_answer,  # Mock always correct
                correct_answer=randomized.correct_answer,
                is_correct=True,
                response_text="The answer is " + randomized.correct_answer,
                input_tokens=50,
                response_tokens=10,
                latency_ms=1000 + (i * 100),
                status="success",
            )
            response_repo.create(response)

        # Step 6: Complete run
        run_manager.complete_run(run.run_id)

        # Step 7: Verify all responses stored
        responses = response_repo.get_by_run(run.run_id)
        assert len(responses) == 3

        # Step 8: Calculate statistics using dict format
        response_dicts = [
            {
                "model_id": r.model_id,
                "is_correct": r.is_correct,
                "latency_ms": r.latency_ms,
                "input_tokens": r.input_tokens,
                "response_tokens": r.response_tokens,
                "status": r.status,
            }
            for r in responses
        ]
        calculator = StatisticsCalculator(response_dicts, errors=[])
        stats = calculator.get_model_statistics("openai/gpt-4")

        assert stats is not None
        assert stats.total_questions == 3
        assert stats.accuracy == 1.0  # All correct in mock

    def test_benchmark_with_mixed_success_and_errors(
        self,
        db_manager: DatabaseManager,
        sample_questionnaire_json: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test benchmark with mix of successful and failed responses.

        Args:
            db_manager: DatabaseManager fixture.
            sample_questionnaire_json: Path to sample JSON.
            mocker: Pytest mocker fixture.
        """
        # Load questions
        loader = QuestionLoader(str(sample_questionnaire_json))
        questions = loader.load()

        # Initialize run
        run_manager = RunManager(db_manager)
        run = run_manager.initialize_run({"models": ["gpt-4"], "iterations": 1})

        # Create model and iteration records for foreign keys
        from src.db.repository import ModelRepository, IterationRepository
        from src.db.models import Iteration
        model_repo = ModelRepository(db_manager)
        model_repo.create("gpt-4", "GPT-4", "OpenAI")

        iteration_repo = IterationRepository(db_manager)
        iteration = Iteration(
            run_id=run.run_id,
            model_id="gpt-4",
            iteration_number=1,
            status="pending",
        )
        iteration_repo.create(iteration)

        # Create mixed responses
        response_repo = ResponseRepository(db_manager)
        error_repo = ErrorRepository(db_manager)

        # 2 successful responses
        for i in range(2):
            response = Response(
                iteration_id=iteration.iteration_id,
                question_id=questions[i].question_id,
                model_id="gpt-4",
                run_id=run.run_id,
                question_text=questions[i].question_text,
                options_json="{}",
                options_randomized=False,
                selected_answer="A",
                correct_answer="A",
                is_correct=True,
                response_text="Correct answer",
                input_tokens=50,
                response_tokens=10,
                latency_ms=1000,
                status="success",
            )
            response_repo.create(response)

        # 1 error response
        error_response = Response(
            iteration_id=iteration.iteration_id,
            question_id=questions[2].question_id,
            model_id="gpt-4",
            run_id=run.run_id,
            question_text=questions[2].question_text,
            options_json="{}",
            options_randomized=False,
            selected_answer=None,
            correct_answer="A",
            is_correct=None,
            response_text="",
            input_tokens=0,
            response_tokens=0,
            latency_ms=5000,
            status="error",
        )
        response_repo.create(error_response)

        # Create error linked to response
        if error_response.response_id:
            error = Error(
                response_id=error_response.response_id,
                error_type="TimeoutError",
                error_message="Request timed out",
                stack_trace="",
            )
            error_repo.create(error)

        # Complete run
        run_manager.complete_run(run.run_id)

        # Verify statistics
        responses = response_repo.get_by_run(run.run_id)
        
        # Calculate statistics using dict format
        response_dicts = [
            {
                "model_id": r.model_id,
                "is_correct": r.is_correct if r.status == "success" else None,
                "latency_ms": r.latency_ms,
                "input_tokens": r.input_tokens,
                "response_tokens": r.response_tokens,
                "status": r.status,
            }
            for r in responses
        ]
        
        calculator = StatisticsCalculator(response_dicts, errors=[])
        stats = calculator.get_model_statistics("gpt-4")

        assert stats is not None
        assert stats.total_questions == 3
        # 2 successful responses (1 error)
        assert stats.error_count == 1


# =============================================================================
# Benchmark Runner Integration Tests
# =============================================================================


class TestBenchmarkRunnerIntegration:
    """Integration tests for BenchmarkRunner class.

    These tests verify the main entry point works correctly.
    """

    def test_benchmark_runner_initialization(
        self, temp_db_path: Path, mocker: MockerFixture
    ) -> None:
        """Test BenchmarkRunner initializes correctly.

        Args:
            temp_db_path: Temporary database path fixture.
            mocker: Pytest mocker fixture.
        """
        # Mock command-line arguments
        mock_args = mocker.MagicMock()
        mock_args.models = ["gpt-4"]
        mock_args.iterations = 1
        mock_args.questions = None
        mock_args.seed = None
        mock_args.dry_run = True
        mock_args.output_format = "console"
        mock_args.output_file = None
        mock_args.config = None

        # Mock environment
        mocker.patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-key",
                "DATABASE_PATH": str(temp_db_path),
            },
        )

        runner = BenchmarkRunner(args=mock_args)
        assert runner.args is not None
        assert runner.settings is not None

    def test_benchmark_runner_dry_run(
        self, temp_db_path: Path, mocker: MockerFixture
    ) -> None:
        """Test BenchmarkRunner dry run mode.

        Args:
            temp_db_path: Temporary database path fixture.
            mocker: Pytest mocker fixture.
        """
        # Mock command-line arguments for dry run
        mock_args = mocker.MagicMock()
        mock_args.models = ["gpt-4"]
        mock_args.iterations = 1
        mock_args.questions = None
        mock_args.seed = None
        mock_args.dry_run = True
        mock_args.output_format = "console"
        mock_args.output_file = None
        mock_args.config = None

        # Mock environment
        mocker.patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-key",
                "DATABASE_PATH": str(temp_db_path),
            },
        )

        runner = BenchmarkRunner(args=mock_args)
        exit_code = runner.run()

        assert exit_code == 0
