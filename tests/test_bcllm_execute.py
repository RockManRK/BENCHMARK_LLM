"""Unit tests for bcllm_execute CLI module.

Tests cover:
- Argument parsing
- Retry policy parsing
- Question ID parsing (including ranges)
- Filter validation
- No pending items detection
"""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import Mock

from src_v2.cli.bcllm_execute import (
    create_parser,
    parse_retry_policy,
    parse_question_ids,
    validate_filters,
    handle_execute,
)
from src_v2.core.execution_plan import RetryPolicy


class TestCreateParser:
    """Test argument parser creation."""

    def test_parser_creates_successfully(self):
        """Parser should be created without errors."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "bcllm_execute.py"

    def test_parser_requires_experiment(self):
        """Experiment argument should be required."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parser_accepts_experiment(self):
        """Parser should accept experiment argument."""
        parser = create_parser()
        args = parser.parse_args(["--experiment", "test_exp"])
        assert args.experiment == "test_exp"

    def test_parser_accepts_run_filter(self):
        """Parser should accept --run filter."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment", "test_exp",
            "--run", "run_abc123",
        ])
        assert args.run == "run_abc123"

    def test_parser_accepts_questions_filter(self):
        """Parser should accept --questions filter."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment", "test_exp",
            "--questions", "Q001", "Q005",
        ])
        assert args.questions == ["Q001", "Q005"]

    def test_parser_accepts_models_filter(self):
        """Parser should accept --models filter."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment", "test_exp",
            "--models", "var_xyz789",
        ])
        assert args.models == ["var_xyz789"]

    def test_parser_accepts_retry_policy(self):
        """Parser should accept --retry-policy."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment", "test_exp",
            "--retry-policy", "max_attempts=5,backoff=linear",
        ])
        assert args.retry_policy == "max_attempts=5,backoff=linear"


class TestParseRetryPolicy:
    """Test retry policy parsing."""

    def test_empty_config_returns_default(self):
        """Empty config should return default RetryPolicy."""
        policy = parse_retry_policy("")
        assert policy.max_attempts == 3
        assert policy.backoff == "exponential"

    def test_none_config_returns_default(self):
        """None config should return default RetryPolicy."""
        policy = parse_retry_policy(None)
        assert policy.max_attempts == 3
        assert policy.backoff == "exponential"

    def test_parse_max_attempts(self):
        """Should parse max_attempts correctly."""
        policy = parse_retry_policy("max_attempts=5")
        assert policy.max_attempts == 5

    def test_parse_backoff_exponential(self):
        """Should parse exponential backoff."""
        policy = parse_retry_policy("backoff=exponential")
        assert policy.backoff == "exponential"

    def test_parse_backoff_linear(self):
        """Should parse linear backoff."""
        policy = parse_retry_policy("backoff=linear")
        assert policy.backoff == "linear"

    def test_parse_backoff_constant(self):
        """Should parse constant backoff."""
        policy = parse_retry_policy("backoff=constant")
        assert policy.backoff == "constant"

    def test_parse_invalid_backoff_raises_error(self):
        """Invalid backoff should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid backoff"):
            parse_retry_policy("backoff=invalid")

    def test_parse_combined_config(self):
        """Should parse combined configuration."""
        policy = parse_retry_policy("max_attempts=5,backoff=linear")
        assert policy.max_attempts == 5
        assert policy.backoff == "linear"

    def test_parse_retry_on(self):
        """Should parse retry_on tuple (pipe-separated)."""
        policy = parse_retry_policy("retry_on=timeout|http_5xx")
        assert policy.retry_on == ("timeout", "http_5xx")


class TestParseQuestionIds:
    """Test question ID parsing with range support."""

    def test_single_question_id(self):
        """Should parse single question ID."""
        result = parse_question_ids(["Q001"])
        assert result == ["Q001"]

    def test_multiple_question_ids(self):
        """Should parse multiple question IDs."""
        result = parse_question_ids(["Q001", "Q005", "Q010"])
        assert result == ["Q001", "Q005", "Q010"]

    def test_range_expansion(self):
        """Should expand range notation."""
        result = parse_question_ids(["Q001-Q003"])
        assert result == ["Q001", "Q002", "Q003"]

    def test_range_with_padding(self):
        """Should maintain zero padding in range."""
        result = parse_question_ids(["Q001-Q005"])
        assert result == ["Q001", "Q002", "Q003", "Q004", "Q005"]

    def test_mixed_single_and_range(self):
        """Should handle mixed single IDs and ranges."""
        result = parse_question_ids(["Q001", "Q005-Q007", "Q010"])
        assert result == ["Q001", "Q005", "Q006", "Q007", "Q010"]

    def test_invalid_range_prefix_mismatch(self):
        """Should raise error for prefix mismatch in range."""
        with pytest.raises(ValueError, match="prefix mismatch"):
            parse_question_ids(["Q001-P005"])

    def test_invalid_range_format(self):
        """Should raise error for invalid range format."""
        with pytest.raises(ValueError, match="Invalid question range"):
            parse_question_ids(["Q001-"])


class TestValidateFilters:
    """Test filter validation."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary test database with full schema."""
        fd, path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        
        conn.executescript("""
            CREATE TABLE experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                config_json TEXT,
                config_hash TEXT,
                system_prompt TEXT,
                user_prompt TEXT,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
            
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                seed INTEGER,
                system_prompt TEXT,
                user_prompt TEXT,
                status TEXT,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
            
            CREATE TABLE model_variants (
                variant_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                model_id TEXT,
                variant_signature TEXT,
                reasoning_mode TEXT DEFAULT 'off',
                reasoning_effort TEXT,
                max_output_tokens INTEGER,
                vision_enabled BOOLEAN DEFAULT FALSE,
                structured_output BOOLEAN DEFAULT FALSE,
                web_access_enabled BOOLEAN DEFAULT FALSE,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
            
            CREATE TABLE question_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                question_id TEXT,
                question_payload TEXT,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
        """)
        
        conn.execute("""
            INSERT INTO experiments 
            (experiment_id, name, description, config_json, config_hash, system_prompt, user_prompt, created_at, is_active)
            VALUES ('exp-001', 'test_exp', 'Test', '{}', 'hash123', 'system', 'user', '2024-01-01', 1)
        """)
        conn.execute("INSERT INTO runs VALUES ('run-001', 'exp-001', 42, '', '', 'pending', NULL, NULL, '2024-01-01', 1)")
        conn.execute("INSERT INTO runs VALUES ('run-002', 'exp-001', 42, '', '', 'completed', NULL, NULL, '2024-01-01', 1)")
        conn.execute("INSERT INTO model_variants VALUES ('var-001', 'exp-001', 'openai/gpt-4', 'sig1', 'off', NULL, NULL, 0, 0, 0, '2024-01-01', 1)")
        conn.execute("INSERT INTO model_variants VALUES ('var-002', 'exp-001', 'anthropic/claude', 'sig2', 'off', NULL, NULL, 0, 0, 0, '2024-01-01', 1)")
        conn.execute("INSERT INTO question_snapshots VALUES ('snap-001', 'exp-001', 'Q001', '{\"stem\":\"test\",\"options\":[\"A\",\"B\"],\"answer_key\":\"A\"}', '2024-01-01', 1)")
        conn.execute("INSERT INTO question_snapshots VALUES ('snap-002', 'exp-001', 'Q005', '{\"stem\":\"test\",\"options\":[\"A\",\"B\"],\"answer_key\":\"A\"}', '2024-01-01', 1)")
        conn.commit()
        
        yield conn
        
        conn.close()
        try:
            os.unlink(path)
        except PermissionError:
            pass

    def test_valid_filters_return_empty_errors(self, temp_db):
        """Valid filters should return empty error list."""
        errors = validate_filters(temp_db, "exp-001", "run-001", ["Q001"], ["var-001"])
        assert errors == []

    def test_invalid_run_id(self, temp_db):
        """Invalid run ID should return error."""
        errors = validate_filters(temp_db, "exp-001", "run-invalid", None, None)
        assert len(errors) == 1
        assert "Run not found" in errors[0]

    def test_run_wrong_experiment(self, temp_db):
        """Run from different experiment should return error."""
        temp_db.execute("""
            INSERT INTO experiments 
            (experiment_id, name, description, config_json, config_hash, system_prompt, user_prompt, created_at, is_active)
            VALUES ('exp-002', 'other_exp', 'Test', '{}', 'hash123', 'system', 'user', '2024-01-01', 1)
        """)
        temp_db.execute("INSERT INTO runs VALUES ('run-003', 'exp-002', 42, '', '', 'pending', NULL, NULL, '2024-01-01', 1)")
        temp_db.commit()
        
        errors = validate_filters(temp_db, "exp-001", "run-003", None, None)
        assert len(errors) == 1
        assert "does not belong" in errors[0]

    def test_invalid_question_id(self, temp_db):
        """Invalid question ID should return error."""
        errors = validate_filters(temp_db, "exp-001", None, ["Q999"], None)
        assert len(errors) == 1
        assert "Question not found" in errors[0]

    def test_invalid_model_variant_id(self, temp_db):
        """Invalid model variant ID should return error."""
        errors = validate_filters(temp_db, "exp-001", None, None, ["var-999"])
        assert len(errors) == 1
        assert "Model variant not found" in errors[0]

    def test_multiple_validation_errors(self, temp_db):
        """Should collect multiple validation errors."""
        errors = validate_filters(temp_db, "exp-001", "run-invalid", ["Q999"], ["var-999"])
        assert len(errors) == 3


class TestHandleExecute:
    """Test execute command handler."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary test database with full schema."""
        fd, path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        
        conn.executescript("""
            CREATE TABLE experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                config_json TEXT,
                config_hash TEXT,
                system_prompt TEXT,
                user_prompt TEXT,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
            
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                seed INTEGER,
                system_prompt TEXT,
                user_prompt TEXT,
                status TEXT,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
            
            CREATE TABLE model_variants (
                variant_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                model_id TEXT,
                variant_signature TEXT,
                reasoning_mode TEXT DEFAULT 'off',
                reasoning_effort TEXT,
                max_output_tokens INTEGER,
                vision_enabled BOOLEAN DEFAULT FALSE,
                structured_output BOOLEAN DEFAULT FALSE,
                web_access_enabled BOOLEAN DEFAULT FALSE,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
            
            CREATE TABLE question_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                question_id TEXT,
                question_payload TEXT,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
            
            CREATE TABLE responses (
                response_id TEXT PRIMARY KEY,
                run_id TEXT,
                variant_id TEXT,
                snapshot_id TEXT,
                model_id TEXT,
                question_id TEXT,
                response_text TEXT,
                selected_answer TEXT,
                is_correct BOOLEAN,
                parse_confidence TEXT,
                needs_review BOOLEAN,
                manual_answer TEXT,
                latency_ms INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                created_at TEXT,
                UNIQUE(run_id, variant_id, snapshot_id)
            );
            
            CREATE TABLE errors (
                error_id TEXT PRIMARY KEY,
                run_id TEXT,
                variant_id TEXT,
                snapshot_id TEXT,
                model_id TEXT,
                question_id TEXT,
                error_type TEXT,
                error_message TEXT,
                attempt_count INTEGER
            );
        """)
        
        yield conn
        
        conn.close()
        try:
            os.unlink(path)
        except PermissionError:
            pass

    def test_experiment_not_found(self, temp_db):
        """Should return error when experiment not found."""
        args = Mock(
            experiment="nonexistent",
            run=None,
            questions=None,
            models=None,
            retry_policy=None,
        )
        
        result = handle_execute(args, temp_db)
        assert result == 1

    def test_no_pending_items_message(self, temp_db):
        """Should display message when no pending items."""
        temp_db.execute("""
            INSERT INTO experiments 
            (experiment_id, name, description, config_json, config_hash, system_prompt, user_prompt, created_at, is_active)
            VALUES ('exp-001', 'test_exp', 'Test', '{}', 'hash123', 'system', 'user', '2024-01-01', 1)
        """)
        temp_db.execute("INSERT INTO model_variants VALUES ('var-001', 'exp-001', 'openai/gpt-4', 'sig1', 'off', NULL, NULL, 0, 0, 0, '2024-01-01', 1)")
        temp_db.execute("INSERT INTO question_snapshots VALUES ('snap-001', 'exp-001', 'Q001', '{\"stem\":\"test\",\"options\":[\"A\",\"B\"],\"answer_key\":\"A\"}', '2024-01-01', 1)")
        temp_db.execute("INSERT INTO runs VALUES ('run-001', 'exp-001', 42, '', '', 'completed', NULL, NULL, '2024-01-01', 1)")
        temp_db.commit()

        args = Mock(
            experiment="test_exp",
            run=None,
            questions=None,
            models=None,
            retry_policy=None,
        )

        result = handle_execute(args, temp_db)
        assert result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
