"""Verification script to check logging, streaming, and raw_response_json."""

import json
import sqlite3
from pathlib import Path

def verify_database():
    """Verify database has raw_response_json column and data."""
    db_path = Path("data/benchmark.db")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        print("   Run a benchmark test first to create the database.")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if raw_response_json column exists
    cursor.execute("PRAGMA table_info(responses)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "raw_response_json" not in columns:
        print("❌ raw_response_json column not found in responses table")
        print("   Run: sqlite3 data/benchmark.db < add_raw_response_column.sql")
        conn.close()
        return False
    
    print("✅ raw_response_json column exists in responses table")
    
    # Check if there are any responses
    cursor.execute("SELECT COUNT(*) FROM responses")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("⚠️  No responses in database yet")
        print("   Run a benchmark test to create responses")
        conn.close()
        return False
    
    print(f"✅ Found {count} response(s) in database")
    
    # Check raw_response_json data
    cursor.execute("""
        SELECT response_id, question_id, response_text, raw_response_json 
        FROM responses 
        ORDER BY response_id DESC 
        LIMIT 5
    """)
    
    responses = cursor.fetchall()
    
    print("\n=== Recent Responses ===")
    for row in responses:
        response_id, question_id, response_text, raw_json = row
        
        # Check response_text length
        text_len = len(response_text) if response_text else 0
        
        # Check raw_response_json
        if raw_json:
            try:
                raw_data = json.loads(raw_json)
                choices = raw_data.get("choices", [])
                has_choices = len(choices) > 0
                stream_status = raw_data.get("stream", "not specified")
            except json.JSONDecodeError:
                has_choices = False
                stream_status = "invalid JSON"
        else:
            has_choices = False
            stream_status = "NULL"
        
        print(f"\nResponse {response_id} (Question {question_id}):")
        print(f"  - response_text length: {text_len} chars")
        print(f"  - raw_response_json: {'✅' if raw_json else '❌'}")
        print(f"  - Has choices in raw: {'✅' if has_choices else '❌'}")
        print(f"  - Stream field: {stream_status}")
        
        if raw_json and has_choices:
            # Show first choice content
            try:
                raw_data = json.loads(raw_json)
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    reasoning = message.get("reasoning_content", "")
                    print(f"  - Content preview: {content[:100]}...")
                    if reasoning:
                        print(f"  - Reasoning preview: {reasoning[:100]}...")
            except:
                pass
    
    conn.close()
    return True


def verify_log_file():
    """Verify log file is being written."""
    log_path = Path("logs/benchmark.log")
    
    if not log_path.exists():
        print(f"❌ Log file not found at {log_path}")
        return False
    
    # Check file size
    file_size = log_path.stat().st_size
    
    if file_size == 0:
        print(f"❌ Log file is empty at {log_path}")
        return False
    
    print(f"✅ Log file exists: {log_path} ({file_size:,} bytes)")
    
    # Check last modified time
    import datetime
    mtime = log_path.stat().st_mtime
    mtime_dt = datetime.datetime.fromtimestamp(mtime)
    now = datetime.datetime.now()
    age = now - mtime_dt
    
    print(f"   Last modified: {mtime_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Age: {age.seconds // 60} minutes ago")
    
    if age.seconds > 300:  # 5 minutes
        print(f"⚠️  Log file is {age.seconds // 60} minutes old")
        print("   Consider running a fresh test")
    
    # Show last 10 lines
    print("\n=== Last 10 Log Lines ===")
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[-10:]:
            print(line.strip())
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Benchmark LLM - Verification Script")
    print("=" * 60)
    print()
    
    print("Checking database...")
    print("-" * 60)
    db_ok = verify_database()
    print()
    
    print("Checking log file...")
    print("-" * 60)
    log_ok = verify_log_file()
    print()
    
    print("=" * 60)
    if db_ok and log_ok:
        print("✅ All checks passed!")
    else:
        print("⚠️  Some checks failed. See messages above.")
    print("=" * 60)
