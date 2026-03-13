#!/usr/bin/env python3
"""List all database tables and their columns in a human-readable format.

Usage:
    python list_tables.py [--db PATH]

Examples:
    python list_tables.py
    python list_tables.py --db ./data/benchmark.db
"""

import argparse
import sqlite3
from pathlib import Path


def list_tables_and_columns(db_path: Path) -> None:
    """List all tables and their columns from the SQLite database.

    Args:
        db_path: Path to the SQLite database file.
    """
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get all tables (excluding internal sqlite tables)
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = cursor.fetchall()

    if not tables:
        print("📭 No tables found in the database.")
        conn.close()
        return

    print(f"📊 Database: {db_path}")
    print(f"📋 Total tables: {len(tables)}\n")
    print("=" * 80)

    for (table_name,) in tables:
        # Get column info for each table
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        print(f"\n📁 TABLE: {table_name}")
        print("-" * 40)

        if columns:
            # Column format: (cid, name, type, notnull, dflt_value, pk)
            col_names = [col[1] for col in columns]
            print(f"   Columns ({len(col_names)}): {', '.join(col_names)}")

            # Show detailed info
            print("\n   Detailed schema:")
            for col in columns:
                cid, name, col_type, notnull, default_val, pk = col
                constraints = []
                if pk:
                    constraints.append("PRIMARY KEY")
                if notnull:
                    constraints.append("NOT NULL")
                if default_val:
                    constraints.append(f"DEFAULT {default_val}")

                constraint_str = f" [{', '.join(constraints)}]" if constraints else ""
                print(f"     • {name}: {col_type}{constraint_str}")
        else:
            print("   ⚠️  No columns found (empty table)")

        print()

    conn.close()
    print("=" * 80)
    print("✅ Done!")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="List all database tables and columns"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("./data/benchmark.db"),
        help="Path to SQLite database (default: ./data/benchmark.db)"
    )
    args = parser.parse_args()

    list_tables_and_columns(args.db)


if __name__ == "__main__":
    main()
