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
        CHECK(status IN ('pending', 'completed', 'failed', 'partial_failed'))
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
        manual_answer     TEXT,
        raw_response      TEXT,
        raw_response_consolidated TEXT,
        request_json      TEXT,
        cost              REAL,
        input_tokens      INTEGER,
        response_tokens   INTEGER,
        reasoning_tokens  INTEGER,
        effective_tokens  INTEGER,
        latency_ms        INTEGER,
        started_at        TIMESTAMP,
        finished_at       TIMESTAMP,

        -- Experimental context (randomization tracking)
        -- Estas colunas congelam o contexto experimental real:
        -- randomization_enabled: se randomização foi aplicada
        -- randomization_seed: seed usada (None = desligada)
        -- options_presented: alternativas como apresentadas (JSON)
        -- correct_option_presented: gabarito no espaço apresentado
        -- option_letter_map: mapeamento de letra apresentada para original
        randomization_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        randomization_seed  INTEGER,
        options_presented   TEXT,
        correct_option_presented TEXT,
        option_letter_map   TEXT,

        UNIQUE(run_id, variant_id, snapshot_id)
    );

    -- Index for listing responses by run
    CREATE INDEX IF NOT EXISTS idx_responses_by_run ON responses(run_id);

    -- ============================================================================
    -- errors table
    -- ============================================================================
    -- Errors are keyed by (response_id, attempt_number).
    -- response_id is a logical reference (no FK constraint) because errors may
    -- be written before the response row exists (e.g., API failure on first attempt).
    CREATE TABLE IF NOT EXISTS errors (
        error_id          TEXT NOT NULL,
        response_id       TEXT NOT NULL,
        run_id            TEXT NOT NULL REFERENCES runs(run_id),
        variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
        snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
        question_id       TEXT NOT NULL,
        error_type        TEXT NOT NULL,
        error_message     TEXT NOT NULL,
        attempt_number    INTEGER NOT NULL DEFAULT 1,
        attempt_count     INTEGER NOT NULL DEFAULT 1,
        stack_trace       TEXT,
        occurred_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (response_id, attempt_number)
    );

    -- Index for listing errors by run
    CREATE INDEX IF NOT EXISTS idx_errors_by_run ON errors(run_id);

    -- Index for error history per response
    CREATE INDEX IF NOT EXISTS idx_errors_by_response ON errors(response_id);
    """


def migrate_errors_table(conn: sqlite3.Connection) -> None:
    """Migrate errors table to new schema with response_id FK and composite PK.

    Handles both fresh databases (already correct via CREATE TABLE IF NOT EXISTS)
    and existing databases with the old schema (single-column PK, no response_id).

    Steps:
    1. Check if migration is needed (old schema detected).
    2. Create new errors table with correct schema (if not already present).
    3. Copy existing data, backfilling response_id and attempt_number.
    4. Drop old table and rename new one.

    Args:
        conn: SQLite database connection.
    """
    cursor = conn.cursor()

    # Check if errors table exists
    cursor.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='errors'"
    )
    if cursor.fetchone()[0] == 0:
        return  # Table doesn't exist yet — will be created by create_schema()

    # Check if response_id column already exists
    cursor.execute("PRAGMA table_info(errors)")
    columns = {row[1] for row in cursor.fetchall()}

    if "response_id" in columns:
        return  # Already migrated

    # Old schema detected — migrate
    # Disable FK checks temporarily — old data may reference deleted records
    cursor.execute("PRAGMA foreign_keys = OFF")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors_new (
            error_id          TEXT NOT NULL,
            response_id       TEXT NOT NULL,
            run_id            TEXT NOT NULL REFERENCES runs(run_id),
            variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
            snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
            question_id       TEXT NOT NULL,
            error_type        TEXT NOT NULL,
            error_message     TEXT NOT NULL,
            attempt_number    INTEGER NOT NULL DEFAULT 1,
            attempt_count     INTEGER NOT NULL DEFAULT 1,
            stack_trace       TEXT,
            occurred_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (response_id, attempt_number)
        )
    """)

    # Copy data, generating response_id deterministically from (run_id, variant_id, snapshot_id)
    # Format: resp-{run_id}-{variant_id}-{snapshot_id}
    cursor.execute("""
        INSERT INTO errors_new (
            error_id, response_id, run_id, variant_id, snapshot_id,
            question_id, error_type, error_message, attempt_number, attempt_count,
            stack_trace, occurred_at
        )
        SELECT
            error_id,
            'resp-' || run_id || '-' || variant_id || '-' || snapshot_id,
            run_id, variant_id, snapshot_id,
            question_id, error_type, error_message,
            1, attempt_count,
            stack_trace, occurred_at
        FROM errors
    """)

    # Drop old table and rename
    cursor.execute("DROP TABLE errors")
    cursor.execute("ALTER TABLE errors_new RENAME TO errors")

    # Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_by_run ON errors(run_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_errors_by_response ON errors(response_id)"
    )

    # Re-enable FK checks
    cursor.execute("PRAGMA foreign_keys = ON")

    conn.commit()


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
