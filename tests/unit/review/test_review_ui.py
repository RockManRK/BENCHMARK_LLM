#!/usr/bin/env python3
"""Unit tests for ReviewUI module.

Tests cover:
- ReviewItem and ReviewStatistics dataclasses
- ReviewUI initialization
- Classification logic

Usage:
    pytest tests/unit/review/test_review_ui.py -v
"""

import json
import sqlite3

import pytest

from src_v2.db.models import Response
from src_v2.db.schema import create_schema
from src_v2.review.review_ui import ReviewItem, ReviewStatistics, ReviewUI


@pytest.fixture
def test_conn():
    """Create in-memory test database connection."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def review_ui(test_conn):
    """Create ReviewUI instance with test connection."""
    return ReviewUI(test_conn)


class TestReviewItem:
    """Tests for ReviewItem dataclass."""

    def test_create_review_item(self):
        """Test creating a ReviewItem with all required fields."""
        response = Response(
            response_id="resp_001",
            run_id="run_001",
            variant_id="var_001",
            snapshot_id="snap_001",
            model_id="openai/gpt-4",
            question_id="Q001",
            response_text="The answer is C",
            selected_answer="C",
            is_correct=True,
            parse_confidence="clear",
            needs_review=False,
        )

        item = ReviewItem(
            response=response,
            question_stem="What is the capital of France?",
            question_options={"A": "London", "B": "Paris", "C": "Berlin", "D": "Madrid"},
            correct_answer="B",
        )

        assert item.response.response_id == "resp_001"
        assert item.question_stem == "What is the capital of France?"
        assert len(item.question_options) == 4
        assert item.correct_answer == "B"


class TestReviewStatistics:
    """Tests for ReviewStatistics dataclass."""

    def test_create_empty_statistics(self):
        """Test creating empty ReviewStatistics."""
        stats = ReviewStatistics()

        assert stats.total_pending == 0
        assert stats.total_processed == 0
        assert stats.by_classification == {}
        assert stats.by_question == {}
        assert stats.by_model == {}

    def test_statistics_with_classification(self):
        """Test ReviewStatistics with classification counts."""
        stats = ReviewStatistics(
            total_pending=10,
            total_processed=5,
            by_classification={"A": 3, "B": 2},
            by_question={"Q001": 5, "Q002": 5},
            by_model={"gpt-4": 10},
        )

        assert stats.total_pending == 10
        assert stats.total_processed == 5
        assert stats.by_classification["A"] == 3
        assert stats.by_classification["B"] == 2


class TestReviewUI:
    """Tests for ReviewUI class."""

    def test_init(self, review_ui):
        """Test ReviewUI initialization."""
        assert review_ui._pending_items == []
        assert review_ui._current_index == 0
        assert review_ui._statistics.total_pending == 0
        assert review_ui._history == []

    def test_get_pending_by_experiment_empty(self, review_ui, test_conn):
        """Test getting pending items when none exist."""
        cursor = test_conn.cursor()
        cursor.execute("""
            INSERT INTO experiments (experiment_id, name, config_json, config_hash, system_prompt, user_prompt)
            VALUES ('exp_001', 'test_exp', '{}', 'hash123', 'system', 'user')
        """)
        test_conn.commit()

        items = review_ui.get_pending_by_experiment("exp_001")
        assert items == []

    def test_classification_labels_complete(self, review_ui):
        """Test that all classification labels are defined."""
        expected_classifications = {"A", "B", "C", "D", "N", "E"}
        actual_classifications = set(review_ui.CLASSIFICATION_LABELS.keys())

        assert expected_classifications == actual_classifications

        assert review_ui.CLASSIFICATION_LABELS["A"] == "Correct"
        assert review_ui.CLASSIFICATION_LABELS["B"] == "Partial"
        assert review_ui.CLASSIFICATION_LABELS["C"] == "Wrong"
        assert review_ui.CLASSIFICATION_LABELS["D"] == "Empty"
        assert review_ui.CLASSIFICATION_LABELS["N"] == "None"
        assert review_ui.CLASSIFICATION_LABELS["E"] == "Error"

    def test_save_classification_skip_noop(self, review_ui):
        """Test that skip classification doesn't modify response."""
        response = Response(
            response_id="resp_001",
            run_id="run_001",
            variant_id="var_001",
            snapshot_id="snap_001",
            model_id="openai/gpt-4",
            question_id="Q001",
            needs_review=True,
        )

        item = ReviewItem(
            response=response,
            question_stem="Test question",
            question_options={"A": "Option A"},
            correct_answer="A",
        )

        review_ui._save_classification(item, "S")

        assert item.response.manual_answer is None
        assert item.response.needs_review is True
        assert item.response.selected_answer is None

    def test_save_classification_correct_logic(self, review_ui):
        """Test correct classification logic."""
        response = Response(
            response_id="resp_001",
            run_id="run_001",
            variant_id="var_001",
            snapshot_id="snap_001",
            model_id="openai/gpt-4",
            question_id="Q001",
            response_text="The answer is B",
        )

        item = ReviewItem(
            response=response,
            question_stem="What is the capital of France?",
            question_options={"A": "London", "B": "Paris", "C": "Berlin", "D": "Madrid"},
            correct_answer="B",
        )

        review_ui._save_classification(item, "B")

        assert item.response.manual_answer == "B"
        assert item.response.needs_review is False
        assert item.response.selected_answer == "B"
        assert item.response.is_correct is True

    def test_save_classification_wrong_logic(self, review_ui):
        """Test wrong classification logic."""
        response = Response(
            response_id="resp_001",
            run_id="run_001",
            variant_id="var_001",
            snapshot_id="snap_001",
            model_id="openai/gpt-4",
            question_id="Q001",
        )

        item = ReviewItem(
            response=response,
            question_stem="What is the capital of France?",
            question_options={"A": "London", "B": "Paris", "C": "Berlin", "D": "Madrid"},
            correct_answer="B",
        )

        review_ui._save_classification(item, "C")

        assert item.response.manual_answer == "C"
        assert item.response.needs_review is False
        assert item.response.selected_answer == "C"
        assert item.response.is_correct is False

    def test_save_classification_none_logic(self, review_ui):
        """Test 'N' (none) classification logic."""
        response = Response(
            response_id="resp_001",
            run_id="run_001",
            variant_id="var_001",
            snapshot_id="snap_001",
            model_id="openai/gpt-4",
            question_id="Q001",
        )

        item = ReviewItem(
            response=response,
            question_stem="Test question",
            question_options={"A": "Option A"},
            correct_answer="A",
        )

        review_ui._save_classification(item, "N")

        assert item.response.manual_answer is None
        assert item.response.needs_review is False
        assert item.response.selected_answer is None
        assert item.response.is_correct is False

    def test_save_classification_error_logic(self, review_ui):
        """Test 'E' (error) classification logic."""
        response = Response(
            response_id="resp_001",
            run_id="run_001",
            variant_id="var_001",
            snapshot_id="snap_001",
            model_id="openai/gpt-4",
            question_id="Q001",
        )

        item = ReviewItem(
            response=response,
            question_stem="Test question",
            question_options={"A": "Option A"},
            correct_answer="A",
        )

        review_ui._save_classification(item, "E")

        assert item.response.manual_answer is None
        assert item.response.needs_review is False
        assert item.response.selected_answer is None
        assert item.response.is_correct is False
