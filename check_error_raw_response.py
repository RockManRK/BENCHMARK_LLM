"""Script to verify raw_response_json is empty for error responses.

This script checks if responses with status='error' have raw_response_json
populated or if they are missing this data.
"""

import sqlite3
from pathlib import Path

# Database path
db_path = Path("./data/benchmark.db")

if not db_path.exists():
    print(f"❌ Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Query to get error responses with their raw_response_json
cursor.execute("""
    SELECT 
        response_id,
        question_id,
        model_id,
        status,
        error_details,
        raw_response_json,
        CASE 
            WHEN raw_response_json IS NULL THEN 'NULL'
            WHEN raw_response_json = '' THEN 'EMPTY'
            WHEN length(raw_response_json) = 0 THEN 'EMPTY_STRING'
            ELSE 'HAS_DATA'
        END as raw_response_status
    FROM responses
    WHERE status = 'error'
    ORDER BY response_id DESC
    LIMIT 20
""")

error_responses = cursor.fetchall()

print("=" * 80)
print("ERROR RESPONSES - raw_response_json VERIFICATION")
print("=" * 80)
print(f"\nTotal error responses found: {len(error_responses)}\n")

if len(error_responses) == 0:
    print("No error responses found in database.")
else:
    # Count by raw_response_status
    status_counts = {}
    for row in error_responses:
        status = row["raw_response_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    print("raw_response_json status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  - {status}: {count}")

    print("\n" + "-" * 80)
    print("DETAILED ERROR RESPONSES:")
    print("-" * 80)

    for row in error_responses:
        print(f"\nResponse ID: {row['response_id']}")
        print(f"  Question ID: {row['question_id']}")
        print(f"  Model: {row['model_id']}")
        print(f"  Status: {row['status']}")
        print(f"  raw_response_json status: {row['raw_response_status']}")
        
        if row["error_details"]:
            import json
            try:
                error_details = json.loads(row["error_details"])
                print(f"  Error Type: {error_details.get('error_type', 'N/A')}")
                print(f"  HTTP Status: {error_details.get('http_status', 'N/A')}")
                print(f"  Message: {error_details.get('message', 'N/A')[:100]}")
                
                # Check if raw_body was truncated
                raw_body = error_details.get('raw_body', {})
                if isinstance(raw_body, dict) and raw_body.get('truncated'):
                    print(f"  ⚠️  raw_body was TRUNCATED in error_details")
                    print(f"      Note says: {raw_body.get('note', 'N/A')}")
            except (json.JSONDecodeError, TypeError) as e:
                print(f"  Error parsing error_details: {e}")
                print(f"  Raw error_details: {row['error_details'][:200]}")
        
        if row["raw_response_json"]:
            print(f"  raw_response_json length: {len(row['raw_response_json'])}")
            try:
                raw_data = json.loads(row["raw_response_json"])
                print(f"  raw_response_json preview: {str(raw_data)[:200]}")
            except:
                print(f"  raw_response_json (raw): {row['raw_response_json'][:200]}")
        else:
            print(f"  ❌ raw_response_json is EMPTY/NULL")

print("\n" + "=" * 80)
print("ANALYSIS:")
print("=" * 80)

# Check if there's a pattern
null_count = status_counts.get('NULL', 0) + status_counts.get('EMPTY', 0) + status_counts.get('EMPTY_STRING', 0)
has_data_count = status_counts.get('HAS_DATA', 0)

if null_count > 0 and has_data_count == 0:
    print("\n⚠️  ISSUE CONFIRMED: All error responses have EMPTY raw_response_json")
    print("\nThis suggests that when errors occur, the code is NOT saving the raw API")
    print("response to the raw_response_json column.")
    print("\nROOT CAUSE:")
    print("  The _store_error() method in question_executor.py creates a Response")
    print("  object WITHOUT the raw_response_json field when handling errors.")
    print("\n  The error response body IS available in _handle_http_error() via")
    print("  error.response.json(), but it's only stored in error_details (truncated),")
    print("  NOT in raw_response_json.")
elif has_data_count > 0:
    print(f"\n✅ raw_response_json is populated in {has_data_count} error responses")
    print("   The system appears to be working correctly.")
else:
    print("\n⚠️  No error responses found to analyze.")

conn.close()
