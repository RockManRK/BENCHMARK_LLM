#!/usr/bin/env python3
"""Database migration: Add config column to model_variants table.

This migration:
1. Adds the `config` column to model_variants
2. Migrates existing deprecated fields into config JSON format
3. Preserves backward compatibility during transition

Migration steps:
1. Add config column (TEXT, NOT NULL, default '{}')
2. For each existing variant, build config from deprecated fields
3. Update variant_signature if needed (optional - can keep legacy signatures)

Usage:
    python scripts/migrate_model_variants_config.py
"""

import json
import sqlite3
from pathlib import Path


def get_database_path() -> Path:
    """Get path to database file."""
    project_root = Path(__file__).parent.parent
    return project_root / "data" / "bcllm.db"


def migrate_model_variants_config(conn: sqlite3.Connection) -> None:
    """Migrate model_variants table to use config column.

    Args:
        conn: SQLite database connection.
    """
    cursor = conn.cursor()

    # Check if config column already exists
    cursor.execute("PRAGMA table_info(model_variants)")
    columns = [row[1] for row in cursor.fetchall()]

    if "config" in columns:
        print("✓ config column already exists - skipping migration")
        return

    print("Starting model_variants config migration...")

    # Step 1: Add config column
    print("  1. Adding config column...")
    cursor.execute("""
        ALTER TABLE model_variants
        ADD COLUMN config TEXT NOT NULL DEFAULT '{}'
    """)
    conn.commit()
    print("     ✓ config column added")

    # Step 2: Migrate existing variants
    print("  2. Migrating existing variants...")
    cursor.execute("""
        SELECT variant_id, reasoning_mode, reasoning_effort,
               vision_enabled, structured_output, web_access_enabled,
               max_output_tokens
        FROM model_variants
        WHERE config = '{}'
    """)
    variants = cursor.fetchall()

    updated_count = 0
    for variant in variants:
        (variant_id, reasoning_mode, reasoning_effort,
         vision_enabled, structured_output, web_access_enabled,
         max_output_tokens) = variant

        # Build config from deprecated fields
        config = {}

        # Map reasoning_mode back to reasoning_effort
        if reasoning_mode == "effort" and reasoning_effort:
            config['reasoning_effort'] = reasoning_effort
        elif reasoning_mode == "off":
            config['reasoning_effort'] = None

        # Boolean fields
        if vision_enabled:
            config['vision'] = vision_enabled
        if structured_output:
            config['structured'] = structured_output
        if web_access_enabled:
            config['web_access'] = web_access_enabled

        # Numeric fields
        if max_output_tokens is not None:
            config['max_output_tokens'] = max_output_tokens

        # Remove None values
        config = {k: v for k, v in config.items() if v is not None}

        # Add label for UX if reasoning_effort is set
        if 'reasoning_effort' in config and config['reasoning_effort']:
            config['label'] = f"({config['reasoning_effort']})"

        # Update variant
        cursor.execute("""
            UPDATE model_variants
            SET config = ?
            WHERE variant_id = ?
        """, (json.dumps(config), variant_id))
        updated_count += 1

    conn.commit()
    print(f"     ✓ Migrated {updated_count} variant(s)")

    # Step 3: Drop deprecated columns (optional - keeping for now for rollback safety)
    print("  3. Keeping deprecated columns for rollback safety")
    print("     Note: SQLite doesn't support DROP COLUMN in older versions")
    print("     Deprecated columns will be ignored by new code")

    print("✓ Migration completed successfully")


def main() -> int:
    """Run migration."""
    db_path = get_database_path()

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("No migration needed - database will be created with new schema")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        migrate_model_variants_config(conn)
        return 0
    except Exception as e:
        print(f"Migration failed: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    sys.exit(main())
