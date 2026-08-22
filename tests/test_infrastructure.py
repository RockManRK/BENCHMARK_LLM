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
        import json
        experiment = ExperimentFactory.create(name="test-experiment")
        config = json.loads(experiment.config_json)

        assert experiment.name == "test-experiment"
        assert config["SYSTEM_PROMPT"] == "You are a helpful assistant."
        assert config["USER_PROMPT"] == "Answer the following question."
        assert experiment.experiment_id.startswith("exp-")

    def test_experiment_factory_accepts_overrides(self):
        """ExperimentFactory should accept field overrides."""
        import json
        experiment = ExperimentFactory.create(
            name="custom-exp",
            system_prompt="Custom system prompt",
        )
        config = json.loads(experiment.config_json)

        assert experiment.name == "custom-exp"
        assert config["SYSTEM_PROMPT"] == "Custom system prompt"

    def test_variant_factory_creates_instance(self):
        """VariantFactory should create ModelVariant instances with defaults."""
        variant = VariantFactory.create(experiment_id="exp-123")

        assert variant.experiment_id == "exp-123"
        assert variant.model_id == "openai/gpt-4"
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
        assert snapshot.json_question_id == "q1"
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
        import json
        run = RunFactory.create(experiment_id="exp-123")
        config = json.loads(run.config)

        assert run.experiment_id == "exp-123"
        assert run.status == "pending"
        assert config["RANDOMIZATION_SEED"] is None
        assert run.run_id.startswith("run-")

    def test_run_factory_creates_run_with_seed(self):
        """RunFactory should create Run instances with custom seed."""
        import json
        run = RunFactory.create(
            experiment_id="exp-123",
            randomization_seed=42,
            status="completed",
        )
        config = json.loads(run.config)

        assert config["RANDOMIZATION_SEED"] == 42
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
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-test", "test", "{}", ""),
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

    # Removed 2026-08-22 (test-debt reconciliation, group D):
    # test_randomizer_is_deterministic tested AnswerRandomizer.shuffle(),
    # an API that never shipped in production — this file's own module
    # docstring ("Smoke tests for test infrastructure (Phase 4)... will
    # be removed or expanded in Phase 5") and the randomizer fixture's
    # docstring in tests/conftest.py ("Fallback for Phase 4 when src
    # doesn't exist yet") confirm .shuffle() was aspirational scaffolding
    # written before AnswerRandomizer was actually implemented — the real
    # class only ever had randomize_options(options, seed=...), a pure
    # per-call function, never a stateful instance method. Not a rename
    # to chase. Equivalent, real coverage of the underlying guarantee
    # (same seed -> same shuffle) already exists end-to-end via
    # tests/integration/test_seed_independence.py::
    # test_randomization_shuffle_identical_regardless_of_model_seed and
    # tests/unit/core/test_execution_engine.py::
    # TestExecutionEngineRandomization.
    #
    # test_parser_extracts_answer / test_parser_handles_no_answer tested
    # ParsedAnswer.selected_answer, renamed to .answer (confirmed real
    # rename, not fictional). Removed rather than updated because
    # tests/test_answer_parser.py already covers both exact scenarios
    # more thoroughly against the real API: test_paren_letter
    # (parenthesized-letter extraction, confidence='clear' — the same
    # pattern "The answer is (B)." exercises) and test_no_letters /
    # test_text_without_letters / test_empty_string / test_whitespace_only
    # (answer is None, confidence='no_answer').
