"""Apply schema to development database."""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/benchmark_dev.db")
SCHEMA_PATH = Path("src/db/schema.sql")

def main():
    # Ensure data directory exists
    DB_PATH.parent.mkdir(exist_ok=True)
    
    # Remove existing database if it exists
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing database: {DB_PATH}")
    
    # Read schema
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()
    
    # Create database and apply schema
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    
    # Verify tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Database created: {DB_PATH}")
    print(f"Tables created: {len(tables)}")
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"  - {table}: {len(columns)} columns ({', '.join(columns[:3])}...)")
    
    conn.close()
    print("\nSchema applied successfully!")

if __name__ == "__main__":
    main()
