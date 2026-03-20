"""Test suite for TO-BE database schema.

Tests verify:
- All 6 tables are created
- Correct columns exist on each table
- UNIQUE constraints are present
- CHECK constraints are present
- Indexes are created
"""

import sqlite3
import pytest

from src_v2.db.schema import create_schema, get_schema_sql


@pytest.fixture
def in_memory_conn():
    """Create in-memory database for schema tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    yield conn
    conn.close()


class TestSchemaCreation:
    """Tests for schema creation."""

    @pytest.mark.domain_rule("TO-BE schema must create exactly 6 tables")
    def test_schema_creates_all_tables(self, in_memory_conn):
        """Verify all 6 TO-BE tables exist."""
        cursor = in_memory_conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            "errors",
            "experiments",
            "model_variants",
            "question_snapshots",
            "responses",
            "runs",
        ]

        assert tables == expected_tables, (
            f"Expected tables {expected_tables}, got {tables}"
        )

    @pytest.mark.domain_rule("experiments table must have all TO-BE columns")
    def test_experiments_table_has_correct_columns(self, in_memory_conn):
        """Verify experiments table has all required columns."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA table_info(experiments)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "experiment_id": "TEXT",
            "name": "TEXT",
            "description": "TEXT",
            "config_json": "TEXT",
            "config_hash": "TEXT",
            "system_prompt": "TEXT",
            "user_prompt": "TEXT",
            "created_at": "TIMESTAMP",
            "is_active": "BOOLEAN",
        }

        for col, col_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"
            assert columns[col].upper() == col_type.upper(), (
                f"Column {col} has type {columns[col]}, expected {col_type}"
            )

    @pytest.mark.domain_rule("model_variants must have experiment_id FK")
    def test_model_variants_table_has_correct_columns(self, in_memory_conn):
        """Verify model_variants table has all required columns."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA table_info(model_variants)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "variant_id": "TEXT",
            "experiment_id": "TEXT",
            "model_id": "TEXT",
            "variant_signature": "TEXT",
            "reasoning_mode": "TEXT",
            "reasoning_effort": "TEXT",
            "max_output_tokens": "INTEGER",
            "vision_enabled": "BOOLEAN",
            "structured_output": "BOOLEAN",
            "web_access_enabled": "BOOLEAN",
            "created_at": "TIMESTAMP",
            "is_active": "BOOLEAN",
        }

        for col, col_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"

    @pytest.mark.domain_rule("question_snapshots must have experiment_id FK")
    def test_question_snapshots_table_has_correct_columns(self, in_memory_conn):
        """Verify question_snapshots table has all required columns."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA table_info(question_snapshots)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "snapshot_id": "TEXT",
            "experiment_id": "TEXT",
            "question_id": "TEXT",
            "question_payload": "TEXT",
            "created_at": "TIMESTAMP",
            "is_active": "BOOLEAN",
        }

        for col, col_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"

    @pytest.mark.domain_rule("runs table must have status CHECK constraint")
    def test_runs_table_has_correct_columns(self, in_memory_conn):
        """Verify runs table has all required columns."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA table_info(runs)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "run_id": "TEXT",
            "experiment_id": "TEXT",
            "seed": "INTEGER",
            "status": "TEXT",
            "started_at": "TIMESTAMP",
            "finished_at": "TIMESTAMP",
            "created_at": "TIMESTAMP",
        }

        for col, col_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"

    @pytest.mark.domain_rule("responses table must have review fields")
    def test_responses_table_has_correct_columns(self, in_memory_conn):
        """Verify responses table has all required columns including review fields."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA table_info(responses)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "response_id": "TEXT",
            "run_id": "TEXT",
            "variant_id": "TEXT",
            "snapshot_id": "TEXT",
            "model_id": "TEXT",
            "question_id": "TEXT",
            "response_text": "TEXT",
            "selected_answer": "TEXT",
            "is_correct": "BOOLEAN",
            "parse_confidence": "TEXT",
            "needs_review": "BOOLEAN",
            "manual_answer": "TEXT",
            "latency_ms": "INTEGER",
            "input_tokens": "INTEGER",
            "output_tokens": "INTEGER",
            "created_at": "TIMESTAMP",
        }

        for col, col_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"

    @pytest.mark.domain_rule("errors table must have error classification fields")
    def test_errors_table_has_correct_columns(self, in_memory_conn):
        """Verify errors table has all required columns."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA table_info(errors)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "error_id": "TEXT",
            "run_id": "TEXT",
            "variant_id": "TEXT",
            "snapshot_id": "TEXT",
            "error_type": "TEXT",
            "error_message": "TEXT",
            "attempt_count": "INTEGER",
            "stack_trace": "TEXT",
            "created_at": "TIMESTAMP",
        }

        for col, col_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"


class TestConstraints:
    """Tests for database constraints."""

    @pytest.mark.domain_rule("responses must have UNIQUE constraint on (run_id, variant_id, snapshot_id)")
    def test_responses_has_unique_constraint(self, in_memory_conn):
        """Verify responses table has UNIQUE constraint."""
        cursor = in_memory_conn.cursor()

        # Insert first response
        cursor.execute("""
            INSERT INTO experiments (experiment_id, name, config_json, config_hash, system_prompt, user_prompt)
            VALUES ('exp1', 'test', '{}', 'hash1', 'system', 'user')
        """)
        cursor.execute("""
            INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature)
            VALUES ('var1', 'exp1', 'openai/gpt-4', 'gpt4-v1')
        """)
        cursor.execute("""
            INSERT INTO question_snapshots (snapshot_id, experiment_id, question_id, question_payload)
            VALUES ('snap1', 'exp1', 'q1', '{}')
        """)
        cursor.execute("""
            INSERT INTO runs (run_id, experiment_id, status)
            VALUES ('run1', 'exp1', 'pending')
        """)
        cursor.execute("""
            INSERT INTO responses (response_id, run_id, variant_id, snapshot_id, model_id, question_id)
            VALUES ('resp1', 'run1', 'var1', 'snap1', 'openai/gpt-4', 'q1')
        """)
        in_memory_conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO responses (response_id, run_id, variant_id, snapshot_id, model_id, question_id)
                VALUES ('resp2', 'run1', 'var1', 'snap1', 'openai/gpt-4', 'q1')
            """)

    @pytest.mark.domain_rule("runs.status must have CHECK constraint")
    def test_runs_has_check_constraint(self, in_memory_conn):
        """Verify runs table has CHECK constraint on status."""
        cursor = in_memory_conn.cursor()

        cursor.execute("""
            INSERT INTO experiments (experiment_id, name, config_json, config_hash, system_prompt, user_prompt)
            VALUES ('exp1', 'test', '{}', 'hash1', 'system', 'user')
        """)
        in_memory_conn.commit()

        # Try to insert invalid status
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO runs (run_id, experiment_id, status)
                VALUES ('run1', 'exp1', 'invalid_status')
            """)

        # Valid statuses should work
        valid_statuses = ['pending', 'running', 'completed', 'failed', 'partial_failed']
        for i, status in enumerate(valid_statuses):
            cursor.execute(f"""
                INSERT INTO runs (run_id, experiment_id, status)
                VALUES ('run_{status}', 'exp1', '{status}')
            """)
        in_memory_conn.commit()

    @pytest.mark.domain_rule("experiments.name must be UNIQUE")
    def test_experiments_name_is_unique(self, in_memory_conn):
        """Verify experiments.name has UNIQUE constraint."""
        cursor = in_memory_conn.cursor()

        cursor.execute("""
            INSERT INTO experiments (experiment_id, name, config_json, config_hash, system_prompt, user_prompt)
            VALUES ('exp1', 'test_exp', '{}', 'hash1', 'system', 'user')
        """)
        in_memory_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO experiments (experiment_id, name, config_json, config_hash, system_prompt, user_prompt)
                VALUES ('exp2', 'test_exp', '{}', 'hash2', 'system', 'user')
            """)

    @pytest.mark.domain_rule("model_variants must have UNIQUE(experiment_id, variant_signature)")
    def test_model_variants_has_unique_constraint(self, in_memory_conn):
        """Verify model_variants has UNIQUE constraint on (experiment_id, variant_signature)."""
        cursor = in_memory_conn.cursor()

        cursor.execute("""
            INSERT INTO experiments (experiment_id, name, config_json, config_hash, system_prompt, user_prompt)
            VALUES ('exp1', 'test', '{}', 'hash1', 'system', 'user')
        """)
        cursor.execute("""
            INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature)
            VALUES ('var1', 'exp1', 'openai/gpt-4', 'gpt4-v1')
        """)
        in_memory_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature)
                VALUES ('var2', 'exp1', 'anthropic/claude', 'gpt4-v1')
            """)

    @pytest.mark.domain_rule("question_snapshots must have UNIQUE(experiment_id, question_id)")
    def test_question_snapshots_has_unique_constraint(self, in_memory_conn):
        """Verify question_snapshots has UNIQUE constraint on (experiment_id, question_id)."""
        cursor = in_memory_conn.cursor()

        cursor.execute("""
            INSERT INTO experiments (experiment_id, name, config_json, config_hash, system_prompt, user_prompt)
            VALUES ('exp1', 'test', '{}', 'hash1', 'system', 'user')
        """)
        cursor.execute("""
            INSERT INTO question_snapshots (snapshot_id, experiment_id, question_id, question_payload)
            VALUES ('snap1', 'exp1', 'q1', '{}')
        """)
        in_memory_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO question_snapshots (snapshot_id, experiment_id, question_id, question_payload)
                VALUES ('snap2', 'exp1', 'q1', '{"different": "payload"}')
            """)


class TestIndexes:
    """Tests for database indexes."""

    @pytest.mark.domain_rule("Schema must create all specified indexes")
    def test_schema_creates_all_indexes(self, in_memory_conn):
        """Verify all required indexes exist."""
        cursor = in_memory_conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            "idx_experiments_active",
            "idx_variants_by_experiment",
            "idx_snapshots_by_experiment",
            "idx_runs_by_experiment",
            "idx_runs_pending",
            "idx_responses_needs_review",
            "idx_responses_by_run",
            "idx_errors_by_run",
        ]

        for idx in expected_indexes:
            assert idx in indexes, f"Missing index: {idx}"

    @pytest.mark.domain_rule("idx_experiments_active must be partial index on is_active=TRUE")
    def test_partial_index_on_experiments(self, in_memory_conn):
        """Verify partial index on experiments.is_active."""
        cursor = in_memory_conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='idx_experiments_active'")
        row = cursor.fetchone()
        assert row is not None
        sql = row[0]
        assert "WHERE is_active = TRUE" in sql or "WHERE is_active=1" in sql.lower()

    @pytest.mark.domain_rule("idx_runs_pending must be partial index on status='pending'")
    def test_partial_index_on_runs(self, in_memory_conn):
        """Verify partial index on runs.status."""
        cursor = in_memory_conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='idx_runs_pending'")
        row = cursor.fetchone()
        assert row is not None
        sql = row[0]
        assert "WHERE status = 'pending'" in sql or "WHERE status='pending'" in sql


class TestForeignKeys:
    """Tests for foreign key relationships."""

    @pytest.mark.domain_rule("model_variants.experiment_id must reference experiments")
    def test_model_variants_fk_experiment(self, in_memory_conn):
        """Verify model_variants references valid experiment."""
        cursor = in_memory_conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Try to insert variant with non-existent experiment
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature)
                VALUES ('var1', 'nonexistent', 'openai/gpt-4', 'gpt4-v1')
            """)

    @pytest.mark.domain_rule("question_snapshots.experiment_id must reference experiments")
    def test_question_snapshots_fk_experiment(self, in_memory_conn):
        """Verify question_snapshots references valid experiment."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO question_snapshots (snapshot_id, experiment_id, question_id, question_payload)
                VALUES ('snap1', 'nonexistent', 'q1', '{}')
            """)

    @pytest.mark.domain_rule("runs.experiment_id must reference experiments")
    def test_runs_fk_experiment(self, in_memory_conn):
        """Verify runs references valid experiment."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO runs (run_id, experiment_id, status)
                VALUES ('run1', 'nonexistent', 'pending')
            """)

    @pytest.mark.domain_rule("responses must reference valid run, variant, snapshot")
    def test_responses_fk_references(self, in_memory_conn):
        """Verify responses references valid entities."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")

        # Insert valid experiment first
        cursor.execute("""
            INSERT INTO experiments (experiment_id, name, config_json, config_hash, system_prompt, user_prompt)
            VALUES ('exp1', 'test', '{}', 'hash1', 'system', 'user')
        """)
        in_memory_conn.commit()

        # Try to insert response with non-existent run
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO responses (response_id, run_id, variant_id, snapshot_id, model_id, question_id)
                VALUES ('resp1', 'nonexistent', 'var1', 'snap1', 'openai/gpt-4', 'q1')
            """)

    @pytest.mark.domain_rule("errors must reference valid run, variant, snapshot")
    def test_errors_fk_references(self, in_memory_conn):
        """Verify errors references valid entities."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO errors (error_id, run_id, variant_id, snapshot_id, error_type, error_message)
                VALUES ('err1', 'nonexistent', 'var1', 'snap1', 'api_error', 'test error')
            """)
