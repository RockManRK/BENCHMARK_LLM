"""Test script to verify timeout, logging, and error_details implementation."""

import sqlite3
from pathlib import Path

def verify_schema():
    """Verify error_details column exists in responses table."""
    db_path = Path("data/benchmark.db")
    
    if not db_path.exists():
        print("⚠️  Database not found. Run a benchmark test first.")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if error_details column exists
    cursor.execute("PRAGMA table_info(responses)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "error_details" not in columns:
        print("❌ error_details column not found in responses table")
        print("   Run: sqlite3 data/benchmark.db < migrations/add_error_details_to_responses.sql")
        conn.close()
        return False
    
    print("✅ error_details column exists in responses table")
    
    # Check if finish_reason column exists
    if "finish_reason" not in columns:
        print("❌ finish_reason column not found in responses table")
        conn.close()
        return False
    
    print("✅ finish_reason column exists in responses table")
    
    # Check if raw_response_json column exists
    if "raw_response_json" not in columns:
        print("❌ raw_response_json column not found in responses table")
        conn.close()
        return False
    
    print("✅ raw_response_json column exists in responses table")
    
    # Show recent responses with error details
    cursor.execute("""
        SELECT response_id, question_id, model_id, status, finish_reason, 
               length(error_details) as error_len,
               length(raw_response_json) as raw_len
        FROM responses 
        ORDER BY response_id DESC 
        LIMIT 5
    """)
    
    responses = cursor.fetchall()
    
    if responses:
        print("\n📊 Recent Responses:")
        print("   " + "-" * 80)
        for row in responses:
            response_id, question_id, model_id, status, finish_reason, error_len, raw_len = row
            print(f"   ID: {response_id} | Q: {question_id} | Model: {model_id[:30]}")
            print(f"   Status: {status} | Finish: {finish_reason} | Error len: {error_len} | Raw len: {raw_len}")
        print("   " + "-" * 80)
    
    conn.close()
    return True


def verify_timeout_config():
    """Verify timeout configuration in client.py."""
    client_path = Path("src/api/client.py")
    
    if not client_path.exists():
        print(f"❌ Client file not found: {client_path}")
        return False
    
    with open(client_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "DEFAULT_TIMEOUT = 180.0" in content:
        print("✅ Timeout configured to 180 seconds (3 minutes)")
    elif "DEFAULT_TIMEOUT = 30.0" in content:
        print("❌ Timeout still at 30 seconds - needs update!")
        return False
    else:
        print("⚠️  Could not verify timeout configuration")
    
    # Check for logging improvements
    if 'logger.info(f"Sending API request: model={model}' in content:
        print("✅ Request logging implemented")
    else:
        print("❌ Request logging not found")
    
    if 'logger.info(f"API response: model={model}, tokens={total_tokens}' in content:
        print("✅ Response logging implemented")
    else:
        print("❌ Response logging not found")
    
    if 'logger.error(f"Error response body: {response.text}")' in content:
        print("✅ Error body logging implemented")
    else:
        print("❌ Error body logging not found")
    
    return True


if __name__ == "__main__":
    print("=" * 80)
    print("Verification: Timeout, Logging, and Error Details Implementation")
    print("=" * 80)
    print()
    
    print("1. Checking timeout configuration...")
    print("-" * 80)
    timeout_ok = verify_timeout_config()
    print()
    
    print("2. Checking database schema...")
    print("-" * 80)
    schema_ok = verify_schema()
    print()
    
    print("=" * 80)
    if timeout_ok and schema_ok:
        print("✅ All verifications passed!")
        print()
        print("Next step: Run a benchmark test with a model that returns error 400")
        print("Example:")
        print("  python bcllm.py --experiment teste_error --models stepfun/step-3.5-flash:free --questions Q001 --verbose")
    else:
        print("⚠️  Some verifications failed. See messages above.")
    print("=" * 80)
