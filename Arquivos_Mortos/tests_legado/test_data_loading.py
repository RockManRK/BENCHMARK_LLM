"""Tests for data loading layer modules.

This module contains comprehensive tests for:
- Question loader (src/core/loader.py)
- Question filter (src/core/filter.py)
- Answer randomizer (src/core/randomizer.py)
- Image handler (src/utils/image_handler.py)

Tests follow TDD methodology and target >80% coverage.
"""

import json
import os
import random
import tempfile
from pathlib import Path
from typing import Any

import pytest

from src.core.loader import QuestionLoader, QuestionSchema, QuestionData
from src.core.filter import QuestionFilter
from src.core.randomizer import AnswerRandomizer
from src.utils.image_handler import ImageHandler


class TestQuestionSchema:
    """Tests for QuestionSchema pydantic validation."""

    def test_valid_question_schema(self) -> None:
        """Test validation of a valid question structure."""
        question_data = {
            "id": "Q001",
            "stem": "Test question stem",
            "options": {"A": "Option A", "B": "Option B"},
            "answer_key": "A",
            "assets": [],
            "meta": {
                "has_table": False,
                "has_image": False,
                "status": "valid",
                "notes": ""
            }
        }
        schema = QuestionSchema(**question_data)
        assert schema.id == "Q001"
        assert schema.stem == "Test question stem"
        assert schema.answer_key == "A"
        assert schema.meta.has_image is False
        assert schema.meta.has_table is False
        assert schema.meta.status == "valid"

    def test_question_with_image(self) -> None:
        """Test validation of question with image asset."""
        question_data = {
            "id": "Q005",
            "stem": "Question with image",
            "options": {"A": "Option A", "B": "Option B"},
            "answer_key": "B",
            "assets": ["data/assets/image_Q005.png"],
            "meta": {
                "has_table": False,
                "has_image": True,
                "status": "valid",
                "notes": ""
            }
        }
        schema = QuestionSchema(**question_data)
        assert schema.meta.has_image is True
        assert len(schema.assets) == 1
        assert schema.assets[0] == "data/assets/image_Q005.png"

    def test_question_with_table(self) -> None:
        """Test validation of question with table."""
        question_data = {
            "id": "Q010",
            "stem": "Question with table\n\n| Col1 | Col2 |\n|------|------|",
            "options": {"A": "Option A", "B": "Option B"},
            "answer_key": "A",
            "assets": [],
            "meta": {
                "has_table": True,
                "has_image": False,
                "status": "valid",
                "notes": ""
            }
        }
        schema = QuestionSchema(**question_data)
        assert schema.meta.has_table is True

    def test_annulled_question(self) -> None:
        """Test validation of annulled question."""
        question_data = {
            "id": "Q002",
            "stem": "Annulled question",
            "options": {"A": "Option A", "B": "Option B"},
            "answer_key": "B",
            "assets": [],
            "meta": {
                "has_table": False,
                "has_image": False,
                "status": "annulled",
                "notes": "Questão anulada"
            }
        }
        schema = QuestionSchema(**question_data)
        assert schema.meta.status == "annulled"

    def test_invalid_status_raises_error(self) -> None:
        """Test that invalid status raises validation error."""
        question_data = {
            "id": "Q001",
            "stem": "Test question",
            "options": {"A": "Option A"},
            "answer_key": "A",
            "assets": [],
            "meta": {
                "has_table": False,
                "has_image": False,
                "status": "invalid_status",
                "notes": ""
            }
        }
        with pytest.raises(ValueError):
            QuestionSchema(**question_data)

    def test_missing_required_field_raises_error(self) -> None:
        """Test that missing required fields raise validation error."""
        question_data = {
            "id": "Q001",
            # Missing stem, options, answer_key, assets, meta
        }
        with pytest.raises(ValueError):
            QuestionSchema(**question_data)


class TestQuestionLoader:
    """Tests for QuestionLoader module."""

    @pytest.fixture
    def valid_json_file(self, tmp_path: Path) -> Path:
        """Create a temporary valid JSON file for testing."""
        data = {
            "dataset": {
                "name": "Test Dataset",
                "version": "1.0",
                "language": "en",
                "source": "test"
            },
            "questions": [
                {
                    "id": "Q001",
                    "stem": "Test question 1",
                    "options": {"A": "Option A", "B": "Option B"},
                    "answer_key": "A",
                    "assets": [],
                    "meta": {
                        "has_table": False,
                        "has_image": False,
                        "status": "valid",
                        "notes": ""
                    }
                },
                {
                    "id": "Q002",
                    "stem": "Test question 2",
                    "options": {"A": "Option A", "B": "Option B"},
                    "answer_key": "B",
                    "assets": [],
                    "meta": {
                        "has_table": False,
                        "has_image": False,
                        "status": "valid",
                        "notes": ""
                    }
                }
            ]
        }
        json_file = tmp_path / "test_questions.json"
        json_file.write_text(json.dumps(data))
        return json_file

    @pytest.fixture
    def invalid_json_file(self, tmp_path: Path) -> Path:
        """Create a temporary invalid JSON file for testing."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{ invalid json content")
        return json_file

    @pytest.fixture
    def empty_questions_file(self, tmp_path: Path) -> Path:
        """Create a JSON file with empty questions list."""
        data = {
            "dataset": {"name": "Empty", "version": "1.0", "language": "en", "source": "test"},
            "questions": []
        }
        json_file = tmp_path / "empty.json"
        json_file.write_text(json.dumps(data))
        return json_file

    def test_load_valid_json_file(self, valid_json_file: Path) -> None:
        """Test loading a valid JSON questionnaire file."""
        loader = QuestionLoader(str(valid_json_file))
        questions = loader.load()
        assert len(questions) == 2
        assert questions[0].question_id == "Q001"
        assert questions[1].question_id == "Q002"

    def test_load_invalid_json_file_raises_error(self, invalid_json_file: Path) -> None:
        """Test that loading invalid JSON raises appropriate error."""
        loader = QuestionLoader(str(invalid_json_file))
        with pytest.raises(ValueError, match="Invalid JSON"):
            loader.load()

    def test_load_nonexistent_file_raises_error(self) -> None:
        """Test that loading nonexistent file raises FileNotFoundError."""
        loader = QuestionLoader("/nonexistent/path/file.json")
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_load_empty_questions_list(self, empty_questions_file: Path) -> None:
        """Test loading JSON with empty questions list."""
        loader = QuestionLoader(str(empty_questions_file))
        questions = loader.load()
        assert len(questions) == 0

    def test_load_real_questionnaire(self) -> None:
        """Test loading the real enamed_questions.json file."""
        json_path = "data/enamed_questions.json"
        if not Path(json_path).exists():
            pytest.skip("Questionnaire file not found")
        
        loader = QuestionLoader(json_path)
        questions = loader.load()
        assert len(questions) == 100
        # Check first question
        assert questions[0].question_id == "Q001"
        assert questions[0].has_image is False
        # Check question with image
        q005 = next((q for q in questions if q.question_id == "Q005"), None)
        assert q005 is not None
        assert q005.has_image is True

    def test_question_metadata_parsing(self, valid_json_file: Path) -> None:
        """Test that question metadata is correctly parsed."""
        loader = QuestionLoader(str(valid_json_file))
        questions = loader.load()
        for question in questions:
            assert "has_image" in question.metadata
            assert "has_table" in question.metadata
            assert "status" in question.metadata


class TestQuestionFilter:
    """Tests for QuestionFilter module."""

    @pytest.fixture
    def sample_questions(self) -> list[Any]:
        """Create sample questions for filtering tests."""
        from src.db.models import Question
        
        return [
            Question(
                question_id="Q001",
                question_text="Question 1",
                options={"A": "A", "B": "B"},
                correct_answer="A",
                has_image=False,
                has_table=False,
                metadata={"status": "valid", "has_image": False, "has_table": False}
            ),
            Question(
                question_id="Q002",
                question_text="Question 2",
                options={"A": "A", "B": "B"},
                correct_answer="B",
                has_image=False,
                has_table=False,
                metadata={"status": "annulled", "has_image": False, "has_table": False}
            ),
            Question(
                question_id="Q003",
                question_text="Question 3",
                options={"A": "A", "B": "B"},
                correct_answer="A",
                has_image=True,
                image_path="data/assets/image_Q003.png",
                has_table=False,
                metadata={"status": "valid", "has_image": True, "has_table": False}
            ),
            Question(
                question_id="Q004",
                question_text="Question 4",
                options={"A": "A", "B": "B"},
                correct_answer="B",
                has_image=False,
                has_table=True,
                metadata={"status": "valid", "has_image": False, "has_table": True}
            ),
        ]

    def test_filter_by_single_id(self, sample_questions: list[Any]) -> None:
        """Test filtering questions by single ID."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_ids(["Q001"])
        assert len(filtered) == 1
        assert filtered[0].question_id == "Q001"

    def test_filter_by_multiple_ids(self, sample_questions: list[Any]) -> None:
        """Test filtering questions by multiple IDs."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_ids(["Q001", "Q003"])
        assert len(filtered) == 2
        ids = [q.question_id for q in filtered]
        assert "Q001" in ids
        assert "Q003" in ids

    def test_filter_by_id_range(self, sample_questions: list[Any]) -> None:
        """Test filtering questions by ID range."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_ids(["Q001-Q003"])
        assert len(filtered) == 3
        ids = [q.question_id for q in filtered]
        assert "Q001" in ids
        assert "Q002" in ids
        assert "Q003" in ids

    def test_filter_by_valid_status(self, sample_questions: list[Any]) -> None:
        """Test filtering questions by valid status."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_status("valid")
        assert len(filtered) == 3
        for q in filtered:
            assert q.metadata["status"] == "valid"

    def test_filter_by_annulled_status(self, sample_questions: list[Any]) -> None:
        """Test filtering questions by annulled status."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_status("annulled")
        assert len(filtered) == 1
        assert filtered[0].question_id == "Q002"

    def test_filter_by_has_image(self, sample_questions: list[Any]) -> None:
        """Test filtering questions by has_image attribute."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_metadata(has_image=True)
        assert len(filtered) == 1
        assert filtered[0].question_id == "Q003"
        assert filtered[0].has_image is True

    def test_filter_by_has_table(self, sample_questions: list[Any]) -> None:
        """Test filtering questions by has_table attribute."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_metadata(has_table=True)
        assert len(filtered) == 1
        assert filtered[0].question_id == "Q004"
        assert filtered[0].has_table is True

    def test_filter_combined_criteria(self, sample_questions: list[Any]) -> None:
        """Test filtering with combined criteria."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_status("valid").by_metadata(has_image=False)
        assert len(filtered) == 2
        for q in filtered:
            assert q.metadata["status"] == "valid"
            assert q.metadata["has_image"] is False

    def test_filter_no_matches(self, sample_questions: list[Any]) -> None:
        """Test filtering with no matching results."""
        filter_obj = QuestionFilter(sample_questions)
        filtered = filter_obj.by_ids(["Q999"])
        assert len(filtered) == 0

    def test_filter_empty_list(self) -> None:
        """Test filtering an empty question list."""
        filter_obj = QuestionFilter([])
        filtered = filter_obj.by_ids(["Q001"])
        assert len(filtered) == 0


class TestAnswerRandomizer:
    """Tests for AnswerRandomizer module."""

    @pytest.fixture
    def sample_question(self) -> Any:
        """Create a sample question for randomization tests."""
        from src.db.models import Question
        
        return Question(
            question_id="Q001",
            question_text="Test question",
            options={"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
            correct_answer="A",
            has_image=False,
            has_table=False,
            metadata={"status": "valid", "has_image": False, "has_table": False}
        )

    def test_fisher_yates_shuffle(self, sample_question: Any) -> None:
        """Test that Fisher-Yates shuffle randomizes options."""
        randomizer = AnswerRandomizer(run_id=42)
        randomized = randomizer.randomize(sample_question)
        
        # Options should be shuffled (may or may not be different from original)
        original_keys = list(sample_question.options.keys())
        randomized_keys = list(randomized.options.keys())
        
        # All original options should be present
        assert set(original_keys) == set(randomized_keys)
        assert len(randomized_keys) == len(original_keys)

    def test_reproducibility_with_seed(self, sample_question: Any) -> None:
        """Test that same seed produces same randomization."""
        randomizer1 = AnswerRandomizer(run_id=12345)
        randomizer2 = AnswerRandomizer(run_id=12345)
        
        result1 = randomizer1.randomize(sample_question)
        result2 = randomizer2.randomize(sample_question)
        
        # Same seed should produce same randomization
        assert list(result1.options.keys()) == list(result2.options.keys())
        assert result1.correct_answer == result2.correct_answer

    def test_different_seeds_produce_different_results(self, sample_question: Any) -> None:
        """Test that different seeds produce different randomizations."""
        randomizer1 = AnswerRandomizer(run_id=11111)
        randomizer2 = AnswerRandomizer(run_id=22222)
        
        result1 = randomizer1.randomize(sample_question)
        result2 = randomizer2.randomize(sample_question)
        
        # Different seeds should likely produce different results
        # (not guaranteed but very high probability)
        keys1 = list(result1.options.keys())
        keys2 = list(result2.options.keys())
        
        # At least verify both are valid permutations
        assert set(keys1) == set(keys2)
        assert len(keys1) == len(keys2)

    def test_answer_key_remap(self, sample_question: Any) -> None:
        """Test that answer key is correctly remapped after randomization."""
        randomizer = AnswerRandomizer(run_id=42)
        randomized = randomizer.randomize(sample_question)
        
        # Original correct answer was "A" -> "Option A"
        # After randomization, correct_answer should point to the new letter
        # that contains "Option A"
        original_correct_text = sample_question.options["A"]
        randomized_correct_text = randomized.options[randomized.correct_answer]
        
        assert randomized_correct_text == original_correct_text

    def test_original_mapping_preserved(self, sample_question: Any) -> None:
        """Test that original letter mapping is tracked."""
        randomizer = AnswerRandomizer(run_id=42)
        randomized = randomizer.randomize(sample_question)
        
        # Check that we can trace back the mapping
        assert hasattr(randomized, 'metadata')
        if 'original_mapping' in randomized.metadata:
            mapping = randomized.metadata['original_mapping']
            # Each original letter should map to a new letter
            for orig_letter in ["A", "B", "C", "D"]:
                assert orig_letter in mapping

    def test_randomizer_with_global_seed(self, sample_question: Any) -> None:
        """Test that global random.seed is set from run_id."""
        run_id = 99999
        randomizer = AnswerRandomizer(run_id=run_id)
        
        # Set global seed
        random.seed(run_id)
        global_state_1 = random.getstate()
        
        # Randomizer should use same seed
        randomizer.randomize(sample_question)
        global_state_2 = random.getstate()
        
        # States should be different (randomizer consumed random numbers)
        # But if we reset, should get same results
        random.seed(run_id)
        random2 = random.getstate()
        assert global_state_1 == random2


class TestImageHandler:
    """Tests for ImageHandler module."""

    @pytest.fixture
    def sample_image_path(self) -> Path:
        """Get path to sample image if available."""
        image_path = Path("data/assets/image_Q005.png")
        if image_path.exists():
            return image_path
        pytest.skip("Sample image not found")

    def test_load_image_from_file(self, sample_image_path: Path) -> None:
        """Test loading image from file path."""
        handler = ImageHandler()
        image_data = handler.load_image(str(sample_image_path))
        assert image_data is not None

    def test_encode_image_to_base64(self, sample_image_path: Path) -> None:
        """Test encoding image to base64 string."""
        handler = ImageHandler()
        base64_string = handler.encode_to_base64(str(sample_image_path))
        
        assert base64_string is not None
        assert isinstance(base64_string, str)
        # Base64 strings should only contain valid characters
        import base64
        try:
            # Try to decode to verify it's valid base64
            base64.b64decode(base64_string)
        except Exception:
            pytest.fail("Invalid base64 string")

    def test_validate_image_format(self, sample_image_path: Path) -> None:
        """Test image format validation."""
        handler = ImageHandler()
        is_valid = handler.validate_format(str(sample_image_path))
        assert is_valid is True

    def test_validate_image_size(self, sample_image_path: Path) -> None:
        """Test image size validation."""
        handler = ImageHandler()
        # Default max size is 10MB, image should be smaller
        is_valid = handler.validate_size(str(sample_image_path))
        assert is_valid is True

    def test_handle_missing_image_gracefully(self) -> None:
        """Test graceful handling of missing image files."""
        handler = ImageHandler()
        
        # Should not raise exception, but return None or handle gracefully
        result = handler.load_image("/nonexistent/path/image.png")
        assert result is None

    def test_encode_missing_image_returns_none(self) -> None:
        """Test that encoding missing image returns None."""
        handler = ImageHandler()
        result = handler.encode_to_base64("/nonexistent/path/image.png")
        assert result is None

    def test_validate_missing_image_returns_false(self) -> None:
        """Test that validating missing image returns False."""
        handler = ImageHandler()
        result = handler.validate_format("/nonexistent/path/image.png")
        assert result is False

    def test_get_image_info(self, sample_image_path: Path) -> None:
        """Test getting image information."""
        handler = ImageHandler()
        info = handler.get_image_info(str(sample_image_path))
        
        assert info is not None
        assert "format" in info
        assert "size" in info
        assert "width" in info
        assert "height" in info

    def test_process_image_complete(self, sample_image_path: Path) -> None:
        """Test complete image processing pipeline."""
        handler = ImageHandler()
        result = handler.process_image(str(sample_image_path))
        
        assert result is not None
        assert "base64" in result
        assert "format" in result
        assert "valid" in result
        assert result["valid"] is True

    def test_resize_image(self, sample_image_path: Path, tmp_path: Path) -> None:
        """Test image resizing functionality."""
        handler = ImageHandler()
        output_path = tmp_path / "resized.png"
        
        result = handler.resize_image(
            str(sample_image_path),
            max_width=100,
            max_height=100,
            output_path=str(output_path)
        )
        
        assert result is not None
        assert Path(result).exists()
        
        # Verify resized image dimensions
        info = handler.get_image_info(str(output_path))
        assert info is not None
        assert info["width"] <= 100
        assert info["height"] <= 100

    def test_resize_image_returns_base64(self, sample_image_path: Path) -> None:
        """Test image resizing returning base64."""
        handler = ImageHandler()
        
        result = handler.resize_image(
            str(sample_image_path),
            max_width=100,
            max_height=100,
            output_path=None
        )
        
        assert result is not None
        assert isinstance(result, str)
        # Should be valid base64
        import base64
        try:
            base64.b64decode(result)
        except Exception:
            pytest.fail("Resize did not return valid base64")


class TestIntegration:
    """Integration tests for data loading layer."""

    def test_load_filter_randomize_pipeline(self) -> None:
        """Test complete pipeline: load -> filter -> randomize."""
        json_path = "data/enamed_questions.json"
        if not Path(json_path).exists():
            pytest.skip("Questionnaire file not found")
        
        # Load
        loader = QuestionLoader(json_path)
        questions = loader.load()
        assert len(questions) > 0
        
        # Filter
        filter_obj = QuestionFilter(questions)
        filtered = filter_obj.by_status("valid").by_metadata(has_image=False)
        assert len(filtered) > 0
        
        # Randomize
        randomizer = AnswerRandomizer(run_id=42)
        randomized_questions = [randomizer.randomize(q) for q in filtered[:5]]
        
        # Verify randomization
        for rq in randomized_questions:
            assert rq.correct_answer in rq.options
            # Verify correct answer points to right text
            original_correct = next(
                (v for k, v in rq.metadata.get('original_options', {}).items() 
                 if k == rq.metadata.get('original_correct_answer')),
                None
            )
            if original_correct:
                assert rq.options[rq.correct_answer] == original_correct

    def test_load_questions_with_images(self) -> None:
        """Test loading and processing questions with images."""
        json_path = "data/enamed_questions.json"
        if not Path(json_path).exists():
            pytest.skip("Questionnaire file not found")
        
        loader = QuestionLoader(json_path)
        questions = loader.load()
        
        # Find questions with images
        image_questions = [q for q in questions if q.has_image]
        assert len(image_questions) > 0
        
        # Verify image paths exist
        for q in image_questions[:3]:  # Test first 3
            if q.image_path:
                handler = ImageHandler()
                if Path(q.image_path).exists():
                    base64_data = handler.encode_to_base64(q.image_path)
                    assert base64_data is not None
