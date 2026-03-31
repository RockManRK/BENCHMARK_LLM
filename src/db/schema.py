"""TO-BE database schema creation.

This module creates the complete TO-BE schema with:
- 6 tables: experiments, model_variants, question_snapshots, runs, responses, errors
- Foreign key relationships
- UNIQUE and CHECK constraints
- Indexes for common query patterns
- NO soft delete (is_active removed from all tables)

Schema is created programmatically (no migration scripts).
"""

import sqlite3


def get_schema_sql() -> str:
    """Return complete TO-BE schema SQL.

    Returns:
        SQL script to create all tables, constraints, and indexes.
    """
    return """
    -- Enable foreign keys
    PRAGMA foreign_keys = ON;

    -- ============================================================================
    -- experiments table
    -- ============================================================================
    CREATE TABLE IF NOT EXISTS experiments (
        experiment_id     TEXT PRIMARY KEY,
        name              TEXT UNIQUE NOT NULL,
        description       TEXT,
        config_json       TEXT NOT NULL,
        config_hash       TEXT NOT NULL,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- ============================================================================
    -- model_variants table (with experiment_id FK)
    -- ============================================================================
    CREATE TABLE IF NOT EXISTS model_variants (
        variant_id        TEXT PRIMARY KEY,
        experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
        model_id          TEXT NOT NULL,
        variant_signature TEXT NOT NULL,
        config            TEXT NOT NULL,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(experiment_id, variant_signature)
    );

    -- Index for variants by experiment
    CREATE INDEX IF NOT EXISTS idx_variants_by_experiment ON model_variants(experiment_id);

    -- ============================================================================
    -- question_snapshots table (with experiment_id FK)
    -- ============================================================================
    CREATE TABLE IF NOT EXISTS question_snapshots (
        snapshot_id       TEXT PRIMARY KEY,
        experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
        json_question_id  TEXT NOT NULL,
        question_position INTEGER NOT NULL,
        question_payload  TEXT NOT NULL,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(experiment_id, question_position)
    );

    -- Index for snapshots by experiment
    CREATE INDEX IF NOT EXISTS idx_snapshots_by_experiment ON question_snapshots(experiment_id);

    -- ============================================================================
    -- runs table
    -- ============================================================================
    CREATE TABLE IF NOT EXISTS runs (
        run_id            TEXT PRIMARY KEY,
        experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
        config            TEXT NOT NULL,
        status            TEXT NOT NULL DEFAULT 'pending',
        duration          INTEGER DEFAULT 0,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK(status IN ('pending', 'running', 'completed', 'failed', 'partial_failed'))
    );

    -- Index for listing runs by experiment
    CREATE INDEX IF NOT EXISTS idx_runs_by_experiment ON runs(experiment_id);

    -- Partial index for pending runs (common query for execution)
    CREATE INDEX IF NOT EXISTS idx_runs_pending ON runs(status) WHERE status = 'pending';

    -- ============================================================================
    -- responses table
    -- ============================================================================
    CREATE TABLE IF NOT EXISTS responses (
        response_id       TEXT PRIMARY KEY,
        run_id            TEXT NOT NULL REFERENCES runs(run_id),
        variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
        snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
        model_id          TEXT NOT NULL,
        question_id       TEXT NOT NULL,
        status            TEXT,
        finish_reason     TEXT,
        error_details     TEXT,
        response_text     TEXT,
        selected_answer   TEXT,
        is_correct        BOOLEAN,
        parse_confidence  TEXT DEFAULT 'unknown',
        review_status     TEXT,
        needs_review      BOOLEAN DEFAULT FALSE,
        manual_answer     TEXT,
        raw_response      TEXT,
        cost              REAL,
        input_tokens      INTEGER,
        response_tokens   INTEGER,
        reasoning_tokens  INTEGER,
        effective_tokens  INTEGER,
        latency_ms        INTEGER,
        started_at        TIMESTAMP,
        finished_at       TIMESTAMP,
        UNIQUE(run_id, variant_id, snapshot_id)
    );

    -- Index for listing responses by run
    CREATE INDEX IF NOT EXISTS idx_responses_by_run ON responses(run_id);

    -- Partial index for responses needing review
    CREATE INDEX IF NOT EXISTS idx_responses_needs_review ON responses(review_status) WHERE review_status = 'needs_review';

    -- ============================================================================
    -- errors table
    -- ============================================================================
    CREATE TABLE IF NOT EXISTS errors (
        error_id          TEXT PRIMARY KEY,
        run_id            TEXT NOT NULL REFERENCES runs(run_id),
        variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
        snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
        question_id       TEXT NOT NULL,
        error_type        TEXT NOT NULL,
        error_message     TEXT NOT NULL,
        attempt_count     INTEGER NOT NULL DEFAULT 1,
        stack_trace       TEXT,
        occurred_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Index for listing errors by run
    CREATE INDEX IF NOT EXISTS idx_errors_by_run ON errors(run_id);
    """


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all TO-BE tables with constraints and indexes.

    Args:
        conn: SQLite database connection.

    Note:
        This is a greenfield schema creation - no migrations.
        Commits changes to the database.
    """
    conn.executescript(get_schema_sql())
    conn.commit()


def drop_all_tables(conn: sqlite3.Connection) -> None:
    """Drop all TO-BE tables (for testing).

    Args:
        conn: SQLite database connection.

    Warning:
        This is for testing only. Deletes all data.
    """
    conn.executescript("""
        DROP TABLE IF EXISTS errors;
        DROP TABLE IF EXISTS responses;
        DROP TABLE IF EXISTS runs;
        DROP TABLE IF EXISTS question_snapshots;
        DROP TABLE IF EXISTS model_variants;
        DROP TABLE IF EXISTS experiments;
    """)
    conn.commit()
