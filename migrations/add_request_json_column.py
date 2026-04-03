"""Migration script to add request_json column to responses table.

This script adds the request_json column to the responses table,
which stores the complete API request payload for audit and debugging.

Usage:
    python migrations/add_request_json_column.py
"""

import sqlite3
import sys
import os


def migrate(db_path: str = "benchmark.db") -> None:
    """Add request_json column to responses table.

    Args:
        db_path: Path to the SQLite database file.
    """
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(responses)")
    columns = [row[1] for row in cursor.fetchall()]

    if "request_json" not in columns:
        print("Adding column: request_json (TEXT)")
        cursor.execute("ALTER TABLE responses ADD COLUMN request_json TEXT")
        conn.commit()
        print("Column added successfully!")
    else:
        print("Column already exists: request_json")

    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "benchmark.db"
    migrate(db_path)
