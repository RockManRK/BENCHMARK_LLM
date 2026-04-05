"""Migration script to add raw_response_consolidated column to responses table.

This column stores a human-readable, consolidated view of the streaming response
for debugging. The original raw_response column remains unchanged (raw chunks).

Usage:
    python migrations/add_raw_response_consolidated_column.py
"""

import sqlite3
import sys
import os


def migrate(db_path: str = "benchmark.db") -> None:
    """Add raw_response_consolidated column to responses table."""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(responses)")
    columns = [row[1] for row in cursor.fetchall()]

    if "raw_response_consolidated" not in columns:
        print("Adding column: raw_response_consolidated (TEXT)")
        cursor.execute("ALTER TABLE responses ADD COLUMN raw_response_consolidated TEXT")
        conn.commit()
        print("Column added successfully!")
    else:
        print("Column already exists: raw_response_consolidated")

    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "benchmark.db"
    migrate(db_path)
