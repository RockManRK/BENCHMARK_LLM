"""Unit tests for QuestionLoader module.

This module contains comprehensive tests for:
- Dataset loading (valid, invalid, missing files)
- Payload validation (required fields, placeholder detection)
- ID extraction and mapping
- Question specification parsing (single, range, comma-separated, mixed)
- Internal ID assignment

Tests follow the project's testing conventions and target >80% coverage.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src_v2.core.question_loader import QuestionLoader


class TestLoadDataset:
    """Test cases for load_dataset method."""

    @pytest.fixture
    def valid_json_file(self, tmp_path: Path) -> Path:
        """Create a temporary valid JSON file for testing."""
        data = {
            "dataset": {
                "name": "Test Dataset",
                "version": "1.0",
            },
            "questions": [
                {
                    "id": "Q001",
                    "stem": "Test question 1",
                    "options": ["A", "B", "C", "D"],
                    "answer_key": "A",
                },
                {
                    "id": "Q002",
                    "stem": "Test question 2",
                    "options": ["A", "B", "C", "D"],
                    "answer_key": "B",
                },
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
            "dataset": {"name": "Empty", "version": "1.0"},
            "questions": []
        }
        json_file = tmp_path / "empty.json"
        json_file.write_text(json.dumps(data))
        return json_file

    @pytest.fixture
    def flat_list_file(self, tmp_path: Path) -> Path:
        """Create a JSON file with flat list format."""
        data = [
            {"id": "Q001", "stem": "Q1", "options": ["A", "B"], "answer_key": "A"},
            {"id": "Q002", "stem": "Q2", "options": ["A", "B"], "answer_key": "B"},
        ]
        json_file = tmp_path / "flat_list.json"
        json_file.write_text(json.dumps(data))
        return json_file

    def test_load_valid_json_file(self, valid_json_file: Path) -> None:
        """Test loading a valid JSON dataset file."""
        loader = QuestionLoader()
        questions = loader.load_dataset(str(valid_json_file))
        
        assert len(questions) == 2
        assert questions[0]["id"] == "Q001"
        assert questions[1]["id"] == "Q002"

    def test_load_flat_list_format(self, flat_list_file: Path) -> None:
        """Test loading flat list format dataset."""
        loader = QuestionLoader()
        questions = loader.load_dataset(str(flat_list_file))
        
        assert len(questions) == 2
        assert questions[0]["stem"] == "Q1"

    def test_load_file_not_found_raises_error(self) -> None:
        """Test that loading nonexistent file raises FileNotFoundError."""
        loader = QuestionLoader()
        
        with pytest.raises(FileNotFoundError, match="Question dataset not found"):
            loader.load_dataset("/nonexistent/path/file.json")

    def test_load_invalid_json_raises_error(self, invalid_json_file: Path) -> None:
        """Test that loading invalid JSON raises JSONDecodeError."""
        loader = QuestionLoader()
        
        with pytest.raises(json.JSONDecodeError):
            loader.load_dataset(str(invalid_json_file))

    def test_load_empty_questions_raises_error(self, empty_questions_file: Path) -> None:
        """Test that loading empty questions list raises ValueError."""
        loader = QuestionLoader()
        
        with pytest.raises(ValueError, match="Question dataset is empty"):
            loader.load_dataset(str(empty_questions_file))

    def test_load_from_env_var(self, valid_json_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading dataset path from environment variable."""
        monkeypatch.setenv("QUESTIONS_DATASET_PATH", str(valid_json_file))
        
        loader = QuestionLoader()
        questions = loader.load_dataset(None)
        
        assert len(questions) == 2

    def test_load_default_path_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default path is used when env var is not set."""
        monkeypatch.delenv("QUESTIONS_DATASET_PATH", raising=False)
        
        loader = QuestionLoader()
        
        with pytest.raises(FileNotFoundError):
            loader.load_dataset(None)

    def test_load_dataset_returns_list(self, valid_json_file: Path) -> None:
        """Test that load_dataset returns a list."""
        loader = QuestionLoader()
        questions = loader.load_dataset(str(valid_json_file))
        
        assert isinstance(questions, list)


class TestValidatePayload:
    """Test cases for validate_payload method."""

    @pytest.fixture
    def loader(self) -> QuestionLoader:
        """Create QuestionLoader instance."""
        return QuestionLoader()

    def test_valid_question_returns_true(self, loader: QuestionLoader) -> None:
        """Test that valid question returns True."""
        question = {
            "stem": "What is the capital of France?",
            "options": ["Paris", "London", "Berlin", "Madrid"],
            "answer_key": "A",
        }
        
        assert loader.validate_payload(question) is True

    def test_missing_stem_returns_false(self, loader: QuestionLoader) -> None:
        """Test that missing stem returns False."""
        question = {
            "options": ["Paris", "London", "Berlin", "Madrid"],
            "answer_key": "A",
        }
        
        assert loader.validate_payload(question) is False

    def test_missing_options_returns_false(self, loader: QuestionLoader) -> None:
        """Test that missing options returns False."""
        question = {
            "stem": "What is the capital of France?",
            "answer_key": "A",
        }
        
        assert loader.validate_payload(question) is False

    def test_missing_answer_key_returns_false(self, loader: QuestionLoader) -> None:
        """Test that missing answer_key returns False."""
        question = {
            "stem": "What is the capital of France?",
            "options": ["Paris", "London", "Berlin", "Madrid"],
        }
        
        assert loader.validate_payload(question) is False

    def test_empty_stem_returns_false(self, loader: QuestionLoader) -> None:
        """Test that empty stem returns False."""
        question = {
            "stem": "",
            "options": ["Paris", "London", "Berlin", "Madrid"],
            "answer_key": "A",
        }
        
        assert loader.validate_payload(question) is False

    def test_whitespace_only_stem_returns_false(self, loader: QuestionLoader) -> None:
        """Test that whitespace-only stem returns False."""
        question = {
            "stem": "   ",
            "options": ["Paris", "London", "Berlin", "Madrid"],
            "answer_key": "A",
        }
        
        assert loader.validate_payload(question) is False

    def test_empty_options_list_returns_false(self, loader: QuestionLoader) -> None:
        """Test that empty options list returns False."""
        question = {
            "stem": "What is the capital of France?",
            "options": [],
            "answer_key": "A",
        }
        
        assert loader.validate_payload(question) is False

    def test_empty_answer_key_returns_false(self, loader: QuestionLoader) -> None:
        """Test that empty answer_key returns False."""
        question = {
            "stem": "What is the capital of France?",
            "options": ["Paris", "London", "Berlin", "Madrid"],
            "answer_key": "",
        }
        
        assert loader.validate_payload(question) is False

    def test_whitespace_only_answer_key_returns_false(self, loader: QuestionLoader) -> None:
        """Test that whitespace-only answer_key returns False."""
        question = {
            "stem": "What is the capital of France?",
            "options": ["Paris", "London", "Berlin", "Madrid"],
            "answer_key": "  ",
        }
        
        assert loader.validate_payload(question) is False

    def test_extra_fields_ignored(self, loader: QuestionLoader) -> None:
        """Test that extra fields don't affect validation."""
        question = {
            "stem": "What is the capital of France?",
            "options": ["Paris", "London", "Berlin", "Madrid"],
            "answer_key": "A",
            "extra_field": "ignored",
            "meta": {"status": "valid"},
        }
        
        assert loader.validate_payload(question) is True


class TestValidateAnswerKeyUniqueness:
    """Test cases for validate_answer_key_uniqueness method."""

    @pytest.fixture
    def loader(self) -> QuestionLoader:
        """Create QuestionLoader instance."""
        return QuestionLoader()

    def test_varied_answer_keys_returns_true(self, loader: QuestionLoader) -> None:
        """Test that varied answer keys return True."""
        questions = [
            {"stem": "Q1", "options": ["A", "B"], "answer_key": "A"},
            {"stem": "Q2", "options": ["A", "B"], "answer_key": "B"},
            {"stem": "Q3", "options": ["A", "B"], "answer_key": "A"},
        ]
        
        assert loader.validate_answer_key_uniqueness(questions) is True

    def test_constant_answer_key_returns_false(self, loader: QuestionLoader) -> None:
        """Test that constant answer key (placeholder data) returns False."""
        questions = [
            {"stem": "Q1", "options": ["A", "B"], "answer_key": "B"},
            {"stem": "Q2", "options": ["A", "B"], "answer_key": "B"},
            {"stem": "Q3", "options": ["A", "B"], "answer_key": "B"},
        ]
        
        assert loader.validate_answer_key_uniqueness(questions) is False

    def test_empty_list_returns_true(self, loader: QuestionLoader) -> None:
        """Test that empty list returns True."""
        questions = []
        
        assert loader.validate_answer_key_uniqueness(questions) is True

    def test_single_question_returns_true(self, loader: QuestionLoader) -> None:
        """Test that single question returns True."""
        questions = [
            {"stem": "Q1", "options": ["A", "B"], "answer_key": "A"},
        ]
        
        assert loader.validate_answer_key_uniqueness(questions) is True

    def test_case_insensitive_comparison(self, loader: QuestionLoader) -> None:
        """Test that answer key comparison is case-insensitive."""
        questions = [
            {"stem": "Q1", "options": ["A", "B"], "answer_key": "a"},
            {"stem": "Q2", "options": ["A", "B"], "answer_key": "A"},
            {"stem": "Q3", "options": ["A", "B"], "answer_key": "a"},
        ]
        
        assert loader.validate_answer_key_uniqueness(questions) is False


class TestGetAllQuestionIds:
    """Test cases for get_all_question_ids method."""

    @pytest.fixture
    def loader(self) -> QuestionLoader:
        """Create QuestionLoader instance."""
        return QuestionLoader()

    def test_extract_id_field(self, loader: QuestionLoader) -> None:
        """Test extracting 'id' field."""
        questions = [
            {"id": "Q001", "stem": "Q1"},
            {"id": "Q002", "stem": "Q2"},
            {"id": "Q003", "stem": "Q3"},
        ]
        
        ids = loader.get_all_question_ids(questions)
        
        assert ids == ["Q001", "Q002", "Q003"]

    def test_extract_question_id_field(self, loader: QuestionLoader) -> None:
        """Test extracting 'question_id' field."""
        questions = [
            {"question_id": "Q001", "stem": "Q1"},
            {"question_id": "Q002", "stem": "Q2"},
        ]
        
        ids = loader.get_all_question_ids(questions)
        
        assert ids == ["Q001", "Q002"]

    def test_generate_numeric_ids_when_missing(self, loader: QuestionLoader) -> None:
        """Test generating numeric IDs when questions don't have IDs."""
        questions = [
            {"stem": "Q1"},
            {"stem": "Q2"},
            {"stem": "Q3"},
        ]
        
        ids = loader.get_all_question_ids(questions)
        
        assert ids == ["1", "2", "3"]

    def test_mixed_id_and_question_id(self, loader: QuestionLoader) -> None:
        """Test handling mixed 'id' and 'question_id' fields."""
        questions = [
            {"id": "Q001", "stem": "Q1"},
            {"question_id": "Q002", "stem": "Q2"},
        ]
        
        ids = loader.get_all_question_ids(questions)
        
        assert ids == ["Q001", "Q002"]

    def test_empty_list_returns_empty(self, loader: QuestionLoader) -> None:
        """Test that empty list returns empty list."""
        ids = loader.get_all_question_ids([])
        
        assert ids == []


class TestParseQuestionSpec:
    """Test cases for parse_question_spec method."""

    @pytest.fixture
    def loader(self) -> QuestionLoader:
        """Create QuestionLoader instance."""
        return QuestionLoader()

    @pytest.fixture
    def sample_questions(self) -> list[dict]:
        """Create sample questions for testing."""
        return [
            {"internal_id": 1, "source_id": "Q001", "stem": "Question 1"},
            {"internal_id": 2, "source_id": "Q002", "stem": "Question 2"},
            {"internal_id": 3, "source_id": "Q003", "stem": "Question 3"},
            {"internal_id": 4, "source_id": "Q004", "stem": "Question 4"},
            {"internal_id": 5, "source_id": "Q005", "stem": "Question 5"},
            {"internal_id": 10, "source_id": "Q010", "stem": "Question 10"},
            {"internal_id": 15, "source_id": "Q015", "stem": "Question 15"},
        ]

    def test_single_source_id(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test parsing single source ID (Q001)."""
        result = loader.parse_question_spec("Q001", sample_questions)
        
        assert len(result) == 1
        assert result[0]["source_id"] == "Q001"
        assert result[0]["internal_id"] == 1

    def test_single_internal_id(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test parsing single internal ID (1)."""
        result = loader.parse_question_spec("1", sample_questions)
        
        assert len(result) == 1
        assert result[0]["internal_id"] == 1
        assert result[0]["source_id"] == "Q001"

    def test_comma_separated_source_ids(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test parsing comma-separated source IDs."""
        result = loader.parse_question_spec("Q001,Q003,Q005", sample_questions)
        
        assert len(result) == 3
        ids = [q["source_id"] for q in result]
        assert "Q001" in ids
        assert "Q003" in ids
        assert "Q005" in ids

    def test_comma_separated_internal_ids(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test parsing comma-separated internal IDs."""
        result = loader.parse_question_spec("1,3,5", sample_questions)
        
        assert len(result) == 3
        ids = [q["internal_id"] for q in result]
        assert 1 in ids
        assert 3 in ids
        assert 5 in ids

    def test_range_source_ids(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test parsing range of source IDs (Q001-Q005)."""
        result = loader.parse_question_spec("Q001-Q005", sample_questions)
        
        assert len(result) == 5
        ids = [q["source_id"] for q in result]
        assert "Q001" in ids
        assert "Q005" in ids

    def test_range_internal_ids(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test parsing range of internal IDs (1-5)."""
        result = loader.parse_question_spec("1-5", sample_questions)
        
        assert len(result) == 5
        ids = [q["internal_id"] for q in result]
        assert 1 in ids
        assert 5 in ids

    def test_mixed_spec(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test parsing mixed specification."""
        result = loader.parse_question_spec("Q001,Q003-Q005,10", sample_questions)
        
        assert len(result) == 5
        ids = [q["source_id"] for q in result]
        assert "Q001" in ids
        assert "Q003" in ids
        assert "Q004" in ids
        assert "Q005" in ids
        assert "Q010" in ids

    def test_invalid_spec_format_raises_error(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test that invalid spec format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid question spec format"):
            loader.parse_question_spec("invalid", sample_questions)

    def test_invalid_range_start_greater_than_end(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test that invalid range (start > end) raises ValueError."""
        with pytest.raises(ValueError, match="start > end"):
            loader.parse_question_spec("Q005-Q001", sample_questions)

    def test_id_not_found_raises_error(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test that nonexistent ID raises ValueError."""
        with pytest.raises(ValueError, match="Question IDs not found"):
            loader.parse_question_spec("Q999", sample_questions)

    def test_empty_spec_raises_error(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test that empty spec raises ValueError."""
        with pytest.raises(ValueError, match="No valid question IDs found"):
            loader.parse_question_spec("", sample_questions)

    def test_case_insensitive_source_ids(self, loader: QuestionLoader, sample_questions: list[dict]) -> None:
        """Test that source IDs are case-insensitive."""
        result1 = loader.parse_question_spec("q001", sample_questions)
        result2 = loader.parse_question_spec("Q001", sample_questions)
        
        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0]["source_id"] == result2[0]["source_id"]


class TestAssignInternalIds:
    """Test cases for assign_internal_ids method."""

    @pytest.fixture
    def loader(self) -> QuestionLoader:
        """Create QuestionLoader instance."""
        return QuestionLoader()

    def test_assigns_sequential_ids(self, loader: QuestionLoader) -> None:
        """Test that internal IDs are assigned sequentially (1..N)."""
        questions = [
            {"id": "Q001", "stem": "Q1"},
            {"id": "Q002", "stem": "Q2"},
            {"id": "Q003", "stem": "Q3"},
        ]
        
        result = loader.assign_internal_ids(questions)
        
        assert result[0]["internal_id"] == 1
        assert result[1]["internal_id"] == 2
        assert result[2]["internal_id"] == 3

    def test_preserves_source_id_from_id_field(self, loader: QuestionLoader) -> None:
        """Test that source_id is preserved from 'id' field."""
        questions = [
            {"id": "Q001", "stem": "Q1"},
            {"id": "Q002", "stem": "Q2"},
        ]
        
        result = loader.assign_internal_ids(questions)
        
        assert result[0]["source_id"] == "Q001"
        assert result[1]["source_id"] == "Q002"

    def test_preserves_source_id_from_question_id_field(self, loader: QuestionLoader) -> None:
        """Test that source_id is preserved from 'question_id' field."""
        questions = [
            {"question_id": "Q001", "stem": "Q1"},
            {"question_id": "Q002", "stem": "Q2"},
        ]
        
        result = loader.assign_internal_ids(questions)
        
        assert result[0]["source_id"] == "Q001"
        assert result[1]["source_id"] == "Q002"

    def test_no_source_id_when_missing(self, loader: QuestionLoader) -> None:
        """Test that source_id is not added when original has no ID."""
        questions = [
            {"stem": "Q1"},
            {"stem": "Q2"},
        ]
        
        result = loader.assign_internal_ids(questions)
        
        assert "source_id" not in result[0]
        assert "source_id" not in result[1]
        assert result[0]["internal_id"] == 1
        assert result[1]["internal_id"] == 2

    def test_returns_new_list(self, loader: QuestionLoader) -> None:
        """Test that method returns a new list (doesn't modify original)."""
        questions = [
            {"id": "Q001", "stem": "Q1"},
        ]
        
        result = loader.assign_internal_ids(questions)
        
        assert result is not questions
        assert "internal_id" not in questions[0]
        assert "internal_id" in result[0]

    def test_empty_list_returns_empty(self, loader: QuestionLoader) -> None:
        """Test that empty list returns empty list."""
        result = loader.assign_internal_ids([])
        
        assert result == []

    def test_internal_ids_are_one_based(self, loader: QuestionLoader) -> None:
        """Test that internal IDs start from 1 (not 0)."""
        questions = [
            {"id": "Q001", "stem": "Q1"},
        ]
        
        result = loader.assign_internal_ids(questions)
        
        assert result[0]["internal_id"] == 1


class TestIntegration:
    """Integration tests for QuestionLoader workflow."""

    def test_complete_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow: load -> assign IDs -> parse spec."""
        data = {
            "questions": [
                {"id": "Q001", "stem": "Question 1", "options": ["A", "B"], "answer_key": "A"},
                {"id": "Q002", "stem": "Question 2", "options": ["A", "B"], "answer_key": "B"},
                {"id": "Q003", "stem": "Question 3", "options": ["A", "B"], "answer_key": "A"},
                {"id": "Q004", "stem": "Question 4", "options": ["A", "B"], "answer_key": "B"},
                {"id": "Q005", "stem": "Question 5", "options": ["A", "B"], "answer_key": "A"},
            ]
        }
        
        json_file = tmp_path / "test_questions.json"
        json_file.write_text(json.dumps(data))
        
        loader = QuestionLoader()
        
        questions = loader.load_dataset(str(json_file))
        assert len(questions) == 5
        
        for q in questions:
            assert loader.validate_payload(q) is True
        
        assert loader.validate_answer_key_uniqueness(questions) is True
        
        questions_with_ids = loader.assign_internal_ids(questions)
        assert questions_with_ids[0]["internal_id"] == 1
        assert questions_with_ids[0]["source_id"] == "Q001"
        
        selected = loader.parse_question_spec("Q001,Q003-Q005", questions_with_ids)
        assert len(selected) == 4
        
        selected_ids = [q["source_id"] for q in selected]
        assert "Q001" in selected_ids
        assert "Q003" in selected_ids
        assert "Q004" in selected_ids
        assert "Q005" in selected_ids

    def test_load_validate_select_by_internal_id(self, tmp_path: Path) -> None:
        """Test loading, validating, and selecting by internal ID."""
        data = {
            "questions": [
                {"id": "Q001", "stem": "Question 1", "options": ["A", "B"], "answer_key": "A"},
                {"id": "Q002", "stem": "Question 2", "options": ["A", "B"], "answer_key": "B"},
                {"id": "Q003", "stem": "Question 3", "options": ["A", "B"], "answer_key": "A"},
            ]
        }
        
        json_file = tmp_path / "test_questions.json"
        json_file.write_text(json.dumps(data))
        
        loader = QuestionLoader()
        questions = loader.load_dataset(str(json_file))
        questions_with_ids = loader.assign_internal_ids(questions)
        
        selected = loader.parse_question_spec("1,3", questions_with_ids)
        
        assert len(selected) == 2
        assert selected[0]["internal_id"] == 1
        assert selected[1]["internal_id"] == 3
