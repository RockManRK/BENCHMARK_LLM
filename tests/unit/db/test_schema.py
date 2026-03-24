"""Tests for TO-BE database schema creation.

Verifies:
- All 6 tables are created with correct columns
- Foreign key constraints are properly defined
- UNIQUE and CHECK constraints exist
- Partial indexes are created for common query patterns
"""

import sqlite3

import pytest

from src_v2.db.schema import get_schema_sql, create_schema


@pytest.fixture
def in_memory_conn():
    """Create in-memory database with TO-BE schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    yield conn
    conn.close()


class TestSchemaCreation:
    """Verify schema creation creates all tables and columns."""

    @pytest.mark.domain_rule("all 6 TO-BE tables must exist")
    def test_schema_creates_all_tables(self, in_memory_conn):
        """Verify all TO-BE tables are created."""
        cursor = in_memory_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "experiments",
            "model_variants",
            "question_snapshots",
            "runs",
            "responses",
            "errors",
        }

        assert tables == expected_tables, f"Missing tables: {expected_tables - tables}"

    @pytest.mark.domain_rule("experiments table must have config_hash")
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
            assert (
                columns[col] == col_type
            ), f"Column {col} has type {columns[col]}, expected {col_type}"

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
            "config": "TEXT",
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
            "is_active": "BOOLEAN",
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
            "model_id": "TEXT",
            "question_id": "TEXT",
            "error_type": "TEXT",
            "error_message": "TEXT",
            "attempt_count": "INTEGER",
            "stack_trace": "TEXT",
            "created_at": "TIMESTAMP",
        }

        for col, col_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"


class TestConstraints:
    """Verify constraints are properly created."""

    @pytest.mark.domain_rule("responses must have unique constraint")
    def test_responses_has_unique_constraint(self, in_memory_conn):
        """Verify responses table has UNIQUE constraint on (run_id, variant_id, snapshot_id)."""
        cursor = in_memory_conn.cursor()

        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='responses'"
        )
        sql = cursor.fetchone()[0]

        assert "UNIQUE(run_id, variant_id, snapshot_id)" in sql

    @pytest.mark.domain_rule("runs must have status CHECK constraint")
    def test_runs_has_check_constraint(self, in_memory_conn):
        """Verify runs table has CHECK constraint on status."""
        cursor = in_memory_conn.cursor()

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='runs'")
        sql = cursor.fetchone()[0]

        assert "CHECK(status IN (" in sql
        assert "'pending'" in sql
        assert "'running'" in sql
        assert "'completed'" in sql
        assert "'failed'" in sql
        assert "'partial_failed'" in sql

    @pytest.mark.domain_rule("experiments.name must be unique")
    def test_experiments_name_is_unique(self, in_memory_conn):
        """Verify experiments.name has UNIQUE constraint."""
        cursor = in_memory_conn.cursor()

        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='experiments'"
        )
        sql = cursor.fetchone()[0]

        assert "name              TEXT UNIQUE NOT NULL" in sql

    @pytest.mark.domain_rule("model_variants must have unique constraint")
    def test_model_variants_has_unique_constraint(self, in_memory_conn):
        """Verify model_variants has UNIQUE constraint on (experiment_id, variant_signature)."""
        cursor = in_memory_conn.cursor()

        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='model_variants'"
        )
        sql = cursor.fetchone()[0]

        assert "UNIQUE(experiment_id, variant_signature)" in sql

    @pytest.mark.domain_rule("question_snapshots must have unique constraint")
    def test_question_snapshots_has_unique_constraint(self, in_memory_conn):
        """Verify question_snapshots has UNIQUE constraint on (experiment_id, question_id)."""
        cursor = in_memory_conn.cursor()

        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='question_snapshots'"
        )
        sql = cursor.fetchone()[0]

        assert "UNIQUE(experiment_id, question_id)" in sql


class TestIndexes:
    """Verify indexes are properly created."""

    @pytest.mark.domain_rule("all required indexes must exist")
    def test_schema_creates_all_indexes(self, in_memory_conn):
        """Verify all expected indexes are created."""
        cursor = in_memory_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        expected_indexes = {
            "idx_experiments_active",
            "idx_variants_by_experiment",
            "idx_snapshots_by_experiment",
            "idx_runs_by_experiment",
            "idx_runs_pending",
            "idx_runs_active",
            "idx_responses_needs_review",
            "idx_responses_by_run",
            "idx_errors_by_run",
        }

        assert (
            indexes == expected_indexes
        ), f"Missing indexes: {expected_indexes - indexes}"

    @pytest.mark.domain_rule("partial index for active experiments")
    def test_partial_index_on_experiments(self, in_memory_conn):
        """Verify partial index on experiments(is_active) WHERE is_active = TRUE."""
        cursor = in_memory_conn.cursor()
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_experiments_active'"
        )
        sql = cursor.fetchone()[0]

        assert "WHERE is_active = TRUE" in sql

    @pytest.mark.domain_rule("partial index for pending runs")
    def test_partial_index_on_runs(self, in_memory_conn):
        """Verify partial index on runs(status) WHERE status = 'pending'."""
        cursor = in_memory_conn.cursor()
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_runs_pending'"
        )
        sql = cursor.fetchone()[0]

        assert "WHERE status = 'pending'" in sql


class TestForeignKeys:
    """Verify foreign key constraints are properly defined."""

    @pytest.mark.domain_rule("model_variants must reference experiments")
    def test_model_variants_fk_experiment(self, in_memory_conn):
        """Verify model_variants.experiment_id references experiments."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(model_variants)")
        fks = cursor.fetchall()

        assert len(fks) == 1
        assert fks[0][2] == "experiments"
        assert fks[0][3] == "experiment_id"

    @pytest.mark.domain_rule("question_snapshots must reference experiments")
    def test_question_snapshots_fk_experiment(self, in_memory_conn):
        """Verify question_snapshots.experiment_id references experiments."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(question_snapshots)")
        fks = cursor.fetchall()

        assert len(fks) == 1
        assert fks[0][2] == "experiments"
        assert fks[0][3] == "experiment_id"

    @pytest.mark.domain_rule("runs must reference experiments")
    def test_runs_fk_experiment(self, in_memory_conn):
        """Verify runs.experiment_id references experiments."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(runs)")
        fks = cursor.fetchall()

        assert len(fks) == 1
        assert fks[0][2] == "experiments"
        assert fks[0][3] == "experiment_id"

    @pytest.mark.domain_rule("responses must reference runs, model_variants, question_snapshots")
    def test_responses_fk_references(self, in_memory_conn):
        """Verify responses table has all required foreign keys."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(responses)")
        fks = cursor.fetchall()

        referenced_tables = {fk[2] for fk in fks}
        assert referenced_tables == {"runs", "model_variants", "question_snapshots"}

    @pytest.mark.domain_rule("errors must reference runs, model_variants, question_snapshots")
    def test_errors_fk_references(self, in_memory_conn):
        """Verify errors table has all required foreign keys."""
        cursor = in_memory_conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(errors)")
        fks = cursor.fetchall()

        referenced_tables = {fk[2] for fk in fks}
        assert referenced_tables == {"runs", "model_variants", "question_snapshots"}
