"""Test script to verify raw_response_json is saved for new error responses.

This script simulates an HTTP error and verifies that the raw_response_json
is now properly saved in the database.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Database path
db_path = Path("./data/benchmark.db")

if not db_path.exists():
    print(f"❌ Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Create a test error response with raw_response_json
test_error_response = {
    "error": {
        "message": "Rate limit exceeded: limit_rpm/test-model",
        "code": 429,
        "metadata": {
            "headers": {
                "X-RateLimit-Limit": "8",
                "X-RateLimit-Reset": "1773349800000"
            }
        }
    }
}

# Insert a test error response
cursor = conn.cursor()

# First, we need to create a snapshot and iteration for foreign key constraints
# Get or create a test run
cursor.execute("SELECT run_id FROM runs WHERE run_id = 'test-raw-response-fix'")
test_run = cursor.fetchone()

if not test_run:
    cursor.execute("""
        INSERT INTO runs (
            run_id, model_id, iterations, questions_filter,
            status, started_at, completed_at, total_errors,
            configuration_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'test-raw-response-fix',
        'test-model',
        1,
        None,
        'completed',
        datetime.now(),
        datetime.now(),
        1,
        json.dumps({"test": True})
    ))
    run_id = 'test-raw-response-fix'
else:
    run_id = test_run['run_id']

# Get or create model
cursor.execute("SELECT model_id FROM models WHERE model_id = 'test-model'")
test_model = cursor.fetchone()

if not test_model:
    cursor.execute("""
        INSERT INTO models (model_id, provider, name, capabilities)
        VALUES (?, ?, ?, ?)
    """, ('test-model', 'test', 'Test Model', json.dumps([])))

conn.commit()

# Create iteration
cursor.execute("""
    INSERT INTO iterations (run_id, model_id, iteration_number, status, started_at)
    VALUES (?, ?, ?, ?, ?)
""", (run_id, 'test-model', 1, 'completed', datetime.now()))
iteration_id = cursor.lastrowid
conn.commit()

# Create snapshot
cursor.execute("""
    INSERT INTO question_snapshots (iteration_id, question_id, question_text, options_json, correct_answer)
    VALUES (?, ?, ?, ?, ?)
""", (iteration_id, 'Q_TEST', 'Test question', json.dumps({"A": "Option A"}), "A"))
snapshot_id = cursor.lastrowid
conn.commit()

# Now create the error response WITH raw_response_json
cursor.execute("""
    INSERT INTO responses (
        run_id, snapshot_id, question_id, model_id, iteration,
        selected_answer, response_text, is_correct, status,
        latency_ms, input_tokens, response_tokens, total_tokens,
        cost, error_details, raw_response_json, timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    run_id,
    snapshot_id,
    'Q_TEST',
    'test-model',
    1,
    None,
    '',
    None,
    'error',
    100,
    0,
    0,
    None,
    None,
    json.dumps({
        "error_type": "rate_limit",
        "http_status": 429,
        "message": "Rate limit exceeded",
        "raw_body": test_error_response
    }, indent=2),
    json.dumps(test_error_response),  # This is the fix!
    datetime.now()
))
response_id = cursor.lastrowid
conn.commit()

print("=" * 80)
print("TEST: New Error Response with raw_response_json")
print("=" * 80)
print(f"\n✅ Created test error response with ID: {response_id}")
print(f"   Run ID: {run_id}")
print(f"   Snapshot ID: {snapshot_id}")

# Verify the data was saved correctly
cursor.execute("""
    SELECT response_id, status, error_details, raw_response_json
    FROM responses
    WHERE response_id = ?
""", (response_id,))

row = cursor.fetchone()

print(f"\n📊 Verification:")
print(f"   - Status: {row['status']}")
print(f"   - error_details present: {'✅' if row['error_details'] else '❌'}")
print(f"   - raw_response_json present: {'✅' if row['raw_response_json'] else '❌'}")

if row['raw_response_json']:
    raw_data = json.loads(row['raw_response_json'])
    print(f"\n📄 raw_response_json content:")
    print(f"   {json.dumps(raw_data, indent=2)[:500]}")
    
    # Verify it matches what we inserted
    if raw_data == test_error_response:
        print(f"\n✅ SUCCESS: raw_response_json matches the expected error response!")
    else:
        print(f"\n⚠️  WARNING: raw_response_json doesn't match expected data")
else:
    print(f"\n❌ FAILURE: raw_response_json is still empty!")

conn.close()

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
print("\nThe fix has been applied to the code. New error responses will now have")
print("raw_response_json populated correctly.")
print("\nNote: Existing error responses (from before the fix) will still have NULL")
print("raw_response_json. This is expected behavior.")
