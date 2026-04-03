"""Migration script to add randomization tracking columns to responses table.

This script adds the following columns to the responses table:
- randomization_enabled: Whether answer options were randomized
- randomization_seed: Seed used for randomization (None if disabled)
- options_presented: Options exactly as presented to LLM (JSON)
- correct_option_presented: Correct answer letter in presented space
- option_letter_map: Mapping from presented letter to original letter

Usage:
    python migrations/add_randomization_columns.py
"""

import sqlite3
import sys
import os


def migrate(db_path: str = "benchmark.db") -> None:
    """Add randomization tracking columns to responses table.

    Args:
        db_path: Path to the SQLite database file.
    """
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(responses)")
    columns = [row[1] for row in cursor.fetchall()]

    columns_to_add = [
        ("randomization_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("randomization_seed", "INTEGER"),
        ("options_presented", "TEXT"),
        ("correct_option_presented", "TEXT"),
        ("option_letter_map", "TEXT"),
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in columns:
            print(f"Adding column: {col_name} ({col_type})")
            cursor.execute(f"ALTER TABLE responses ADD COLUMN {col_name} {col_type}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "benchmark.db"
    migrate(db_path)
