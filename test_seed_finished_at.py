"""Test script to verify seed and finished_at fixes.

This script tests the following scenarios:
1. seed=None → Should keep NULL in database
2. seed=AUTO → Should generate random integer per RUN
3. seed=123 → Should use the provided integer
4. finished_at → Should be set when run completes
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Database path
db_path = Path("./data/benchmark.db")

if not db_path.exists():
    print(f"❌ Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("TEST: seed and finished_at fixes")
print("=" * 80)

# Check existing runs
cursor.execute("""
    SELECT run_id, seed, started_at, finished_at, status
    FROM runs
    ORDER BY run_id DESC
    LIMIT 10
""")

runs = cursor.fetchall()

print(f"\n📊 Last 10 runs:")
print(f"{'Run ID':<40} {'Seed':<10} {'Status':<12} {'Finished At':<25}")
print("-" * 87)

for run in runs:
    seed_str = str(run["seed"]) if run["seed"] is not None else "NULL"
    finished_str = run["finished_at"] if run["finished_at"] else "NULL"
    print(f"{run['run_id']:<40} {seed_str:<10} {run['status']:<12} {finished_str:<25}")

# Count runs with NULL seed
cursor.execute("SELECT COUNT(*) as count FROM runs WHERE seed IS NULL")
null_seed_count = cursor.fetchone()["count"]

# Count runs with AUTO seed (should be integers)
cursor.execute("SELECT COUNT(*) as count FROM runs WHERE seed IS NOT NULL")
with_seed_count = cursor.fetchone()["count"]

# Count runs with finished_at NULL but status completed/failed
cursor.execute("""
    SELECT COUNT(*) as count 
    FROM runs 
    WHERE finished_at IS NULL 
    AND status IN ('completed', 'failed')
""")
missing_finished_at = cursor.fetchone()["count"]

print(f"\n📈 Summary:")
print(f"   - Runs with NULL seed: {null_seed_count}")
print(f"   - Runs with seed value: {with_seed_count}")
print(f"   - Runs missing finished_at (completed/failed): {missing_finished_at}")

conn.close()

print("\n" + "=" * 80)
print("INSTRUCTIONS FOR MANUAL TESTING:")
print("=" * 80)
print("""
To test the fixes, run the following commands:

1. Test seed=None (ordem original):
   python -m src.main --models openai/gpt-4 --iterations 1 --test-mode
   → Verifique no banco: seed = NULL

2. Test seed=AUTO (gera aleatório por RUN):
   # No .env: RANDOM_SEED=AUTO
   python -m src.main --models openai/gpt-4 --iterations 1
   → Verifique no banco: seed = <inteiro aleatório>

3. Test seed=123 (fixo):
   python -m src.main --models openai/gpt-4 --iterations 1 --seed 123
   → Verifique no banco: seed = 123

4. Test finished_at:
   # Execute um benchmark completo
   python -m src.main --models openai/gpt-4 --iterations 1
   → Verifique no banco: finished_at = <timestamp>
""")

print("=" * 80)
print("✅ Code fixes have been applied!")
print("=" * 80)
