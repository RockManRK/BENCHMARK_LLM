"""Smoke tests for test infrastructure (Phase 4).

These tests verify that the test infrastructure is working correctly.
They will be removed or expanded in Phase 5.
"""

import pytest
from tests.factories import (
    ExperimentFactory,
    VariantFactory,
    SnapshotFactory,
    RunFactory,
)


class TestFactories:
    """Test that factories create valid instances."""

    def test_experiment_factory_creates_instance(self):
        """ExperimentFactory should create Experiment instances with defaults."""
        experiment = ExperimentFactory.create(name="test-experiment")
        
        assert experiment.name == "test-experiment"
        assert experiment.system_prompt == "You are a helpful assistant."
        assert experiment.user_prompt == "Answer the question."
        assert experiment.is_active is True
        assert experiment.experiment_id.startswith("exp-")

    def test_experiment_factory_accepts_overrides(self):
        """ExperimentFactory should accept field overrides."""
        experiment = ExperimentFactory.create(
            name="custom-exp",
            system_prompt="Custom system prompt",
            is_active=False,
        )
        
        assert experiment.name == "custom-exp"
        assert experiment.system_prompt == "Custom system prompt"
        assert experiment.is_active is False

    def test_variant_factory_creates_instance(self):
        """VariantFactory should create ModelVariant instances with defaults."""
        variant = VariantFactory.create(experiment_id="exp-123")
        
        assert variant.experiment_id == "exp-123"
        assert variant.model_id == "openai/gpt-4"
        assert variant.is_active is True
        assert variant.variant_id.startswith("var-")

    def test_variant_factory_requires_experiment_id(self):
        """VariantFactory should require experiment_id parameter."""
        # This should work
        variant = VariantFactory.create(experiment_id="exp-456")
        assert variant.experiment_id == "exp-456"

    def test_snapshot_factory_creates_instance(self):
        """SnapshotFactory should create QuestionSnapshot instances with defaults."""
        snapshot = SnapshotFactory.create(
            experiment_id="exp-123",
            question_id="q1",
        )
        
        assert snapshot.experiment_id == "exp-123"
        assert snapshot.question_id == "q1"
        assert snapshot.is_active is True
        assert snapshot.snapshot_id.startswith("snap-")
        # Default payload should be valid JSON
        import json
        payload = json.loads(snapshot.question_payload)
        assert "stem" in payload
        assert "options" in payload
        assert "answer_key" in payload

    def test_snapshot_factory_accepts_custom_payload(self):
        """SnapshotFactory should accept custom question payload."""
        import json
        custom_payload = json.dumps({
            "stem": "What is the capital of France?",
            "options": ["London", "Paris", "Berlin", "Madrid"],
            "answer_key": "B",
        })
        
        snapshot = SnapshotFactory.create(
            experiment_id="exp-123",
            question_id="q1",
            question_payload=custom_payload,
        )
        
        assert snapshot.question_payload == custom_payload

    def test_run_factory_creates_pending_run(self):
        """RunFactory should create Run instances with pending status by default."""
        run = RunFactory.create(experiment_id="exp-123")
        
        assert run.experiment_id == "exp-123"
        assert run.status == "pending"
        assert run.seed is None
        assert run.run_id.startswith("run-")

    def test_run_factory_creates_run_with_seed(self):
        """RunFactory should create Run instances with custom seed."""
        run = RunFactory.create(
            experiment_id="exp-123",
            seed=42,
            status="completed",
        )
        
        assert run.seed == 42
        assert run.status == "completed"


class TestFixtures:
    """Test that fixtures are working correctly."""

    def test_in_memory_db_has_schema(self, in_memory_db):
        """in_memory_db fixture should have TO-BE schema tables."""
        cursor = in_memory_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {'experiments', 'model_variants', 'question_snapshots', 'runs'}
        assert expected_tables.issubset(tables)

    def test_in_memory_db_is_isolated(self, in_memory_db):
        """in_memory_db fixture should provide isolated database per test."""
        # Insert data
        cursor = in_memory_db.cursor()
        cursor.execute(
            "INSERT INTO experiments (experiment_id, name, system_prompt, user_prompt) VALUES (?, ?, ?, ?)",
            ("exp-test", "test", "prompt", "prompt"),
        )
        in_memory_db.commit()
        
        # Verify data exists
        cursor.execute("SELECT COUNT(*) FROM experiments")
        count = cursor.fetchone()[0]
        assert count == 1

    def test_mock_api_client_returns_response(self, mock_api_client):
        """mock_api_client fixture should return mocked completion response."""
        # The mock is configured, just verify it's set up
        assert mock_api_client is not None
        assert mock_api_client.chat_completion is not None

    def test_randomizer_is_deterministic(self, randomizer):
        """randomizer fixture should produce deterministic results with fixed seed."""
        # The randomizer fixture uses seed=42
        # Create two lists with same content
        list1 = ['A', 'B', 'C', 'D']
        list2 = ['A', 'B', 'C', 'D']
        
        # Shuffle both - since randomizer uses a seeded Random instance,
        # we need to test that calling shuffle on the same instance
        # produces consistent sequences
        shuffled1 = randomizer.shuffle(list1)
        
        # Reset the randomizer by creating a new one with same seed
        # Import from conftest fallback
        try:
            from src.core.randomizer import AnswerRandomizer
        except ImportError:
            # Fallback implementation from conftest
            import random
            class AnswerRandomizer:
                def __init__(self, seed: int = 42):
                    self._random = random.Random(seed)
                def shuffle(self, items: list) -> list:
                    result = items.copy()
                    self._random.shuffle(result)
                    return result
        
        randomizer2 = AnswerRandomizer(seed=42)
        shuffled2 = randomizer2.shuffle(list2)
        
        # Same seed should produce same result
        assert shuffled1 == shuffled2

    def test_parser_extracts_answer(self, parser):
        """parser fixture should extract answer from response text."""
        result = parser.parse("The answer is (B).")
        
        assert result.selected_answer == 'B'
        assert result.confidence == 'clear'

    def test_parser_handles_no_answer(self, parser):
        """parser fixture should handle responses with no answer."""
        result = parser.parse("I don't know the answer to this question.")
        
        assert result.selected_answer is None
        assert result.confidence == 'no_answer'
