#!/usr/bin/env python
"""Block 6e Validation Script - Real API Execution"""

import sqlite3
import json
import sys
import os

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = 'benchmark.db'

def init_schema():
    """Initialize database schema if needed."""
    from src.db.schema import create_schema
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    conn.close()
    print("Schema initialized successfully")

def check_schema():
    """Check responses table schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if responses table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='responses'")
    table = cursor.fetchone()
    
    if not table:
        print("responses table does NOT exist - initializing schema...")
        conn.close()
        init_schema()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
    
    print("\n=== Schema Compliance Check ===")
    cursor.execute('PRAGMA table_info(responses)')
    cols = cursor.fetchall()
    
    col_names = [col[1] for col in cols]
    print(f"\nColumns in responses table ({len(col_names)} total):")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")
    
    # Check contract compliance
    print("\n=== Contract Compliance ===")
    
    needs_review_present = 'needs_review' in col_names
    response_tokens_present = 'response_tokens' in col_names
    output_tokens_present = 'output_tokens' in col_names
    review_status_present = 'review_status' in col_names
    
    print(f"\n| Column | In Contract | In Code | Status |")
    print(f"|--------|-------------|---------|--------|")
    print(f"| `needs_review` | ❌ No | {'✅ Yes' if needs_review_present else '❌ No'} | {'❌ FAIL' if needs_review_present else '✅ PASS'} |")
    print(f"| `response_tokens` | ✅ Yes | {'✅ Yes' if response_tokens_present else '❌ No'} | {'✅ PASS' if response_tokens_present else '❌ FAIL'} |")
    print(f"| `output_tokens` | ❌ No | {'✅ Yes' if output_tokens_present else '❌ No'} | {'✅ PASS' if not output_tokens_present else '⚠️ PRESENT'} |")
    print(f"| `review_status` | ✅ Yes | {'✅ Yes' if review_status_present else '❌ No'} | {'✅ PASS' if review_status_present else '❌ FAIL'} |")
    
    conn.close()
    
    return {
        'needs_review': needs_review_present,
        'response_tokens': response_tokens_present,
        'output_tokens': output_tokens_present,
        'review_status': review_status_present,
        'all_columns': col_names
    }

def check_debug_capture():
    """Check if debug chunks are being captured."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n=== Debug Chunk Capture Check ===")
    
    # Get latest response
    cursor.execute("""
        SELECT response_id, raw_response FROM responses 
        WHERE raw_response IS NOT NULL
        ORDER BY response_id DESC 
        LIMIT 1
    """)
    row = cursor.fetchone()
    
    if not row:
        print("No responses with raw_response found in database")
        print("This is expected if no real API execution has been performed yet")
        conn.close()
        return None
    
    response_id = row[0]
    raw_response = row[1]
    
    print(f"\nResponse ID: {response_id}")
    
    try:
        raw = json.loads(raw_response)
        chunk_count = len(raw) if isinstance(raw, list) else 1
        print(f"Chunk count: {chunk_count}")
        
        if isinstance(raw, list) and len(raw) > 0:
            first = raw[0]
            has_debug = 'debug' in first
            print(f"\nFirst chunk has debug: {has_debug}")
            
            if has_debug:
                debug_payload = first['debug']
                echo_upstream = 'echo_upstream_body' in debug_payload
                print(f"\nDebug payload present:")
                print(f"  echo_upstream_body: {echo_upstream}")
                
                if echo_upstream:
                    echo_body = debug_payload['echo_upstream_body']
                    print(f"\nEcho upstream body keys: {list(echo_body.keys()) if isinstance(echo_body, dict) else 'N/A'}")
            
            conn.close()
            return {
                'chunk_count': chunk_count,
                'has_debug': has_debug,
                'echo_upstream_body': 'echo_upstream_body' in first.get('debug', {}) if isinstance(raw, list) else False
            }
        else:
            print("Response is not a list or is empty")
            conn.close()
            return {'chunk_count': chunk_count, 'has_debug': False, 'echo_upstream_body': False}
            
    except json.JSONDecodeError as e:
        print(f"Failed to parse raw_response as JSON: {e}")
        conn.close()
        return None

def check_existing_experiments():
    """Check if there are existing experiments."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n=== Existing Experiments Check ===")
    
    cursor.execute("SELECT experiment_id, name FROM experiments")
    experiments = cursor.fetchall()
    
    if not experiments:
        print("No experiments found in database")
        conn.close()
        return []
    
    print(f"\nFound {len(experiments)} experiment(s):")
    for exp in experiments:
        print(f"  - {exp[1]} (id: {exp[0]})")
        
        # Get runs for this experiment
        cursor.execute("SELECT run_id, status FROM runs WHERE experiment_id = ?", (exp[0],))
        runs = cursor.fetchall()
        if runs:
            print(f"    Runs: {len(runs)}")
            for run in runs:
                print(f"      - {run[0]} (status: {run[1]})")
        
        # Get model variants
        cursor.execute("SELECT variant_id, model_id FROM model_variants WHERE experiment_id = ?", (exp[0],))
        variants = cursor.fetchall()
        if variants:
            print(f"    Model variants: {len(variants)}")
            for var in variants:
                print(f"      - {var[1]} (id: {var[0]})")
        
        # Get question snapshots
        cursor.execute("SELECT COUNT(*) FROM question_snapshots WHERE experiment_id = ?", (exp[0],))
        snapshot_count = cursor.fetchone()[0]
        print(f"    Question snapshots: {snapshot_count}")
        
        # Get responses
        cursor.execute("SELECT COUNT(*) FROM responses WHERE run_id IN (SELECT run_id FROM runs WHERE experiment_id = ?)", (exp[0],))
        response_count = cursor.fetchone()[0]
        print(f"    Responses: {response_count}")
    
    conn.close()
    return experiments

def main():
    """Main validation routine."""
    print("=" * 60)
    print("Block 6e Validation Report")
    print("=" * 60)
    
    # Initialize schema if needed
    init_schema()
    
    # Check existing experiments
    experiments = check_existing_experiments()
    
    # Check schema compliance
    schema_result = check_schema()
    
    # Check debug capture
    debug_result = check_debug_capture()
    
    # Generate report
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    # Schema compliance
    schema_pass = (
        not schema_result['needs_review'] and
        schema_result['response_tokens'] and
        schema_result['review_status']
    )
    
    print(f"\nSchema Compliance: {'✅ PASS' if schema_pass else '❌ FAIL'}")
    if not schema_pass:
        if schema_result['needs_review']:
            print("  ⚠️ `needs_review` column still present (should be removed)")
        if not schema_result['response_tokens']:
            print("  ⚠️ `response_tokens` column missing")
        if not schema_result['review_status']:
            print("  ⚠️ `review_status` column missing")
    
    # Debug capture (only if data exists)
    if debug_result:
        debug_pass = debug_result['has_debug']
        print(f"\nDebug Chunk Capture: {'✅ PASS' if debug_pass else '⚠️ NO DATA (expected before real execution)'}")
        if debug_pass:
            print(f"  - Chunks captured: {debug_result['chunk_count']}")
            print(f"  - Debug field present: {debug_result['has_debug']}")
            print(f"  - echo_upstream_body: {debug_result['echo_upstream_body']}")
    else:
        print(f"\nDebug Chunk Capture: ⚠️ NO DATA (no responses with raw_response)")
    
    # Overall classification
    print("\n" + "=" * 60)
    print("CLASSIFICATION")
    print("=" * 60)
    
    if schema_pass:
        print("\n✅ **PASS** — Schema fixes validated")
        print("\n**Recommendation:**")
        print("- Block 6e ready for Essence Guardian Gate")
        print("- Resume Block 5 (Human-Driven Validation)")
        print("\n**Next Steps:**")
        if not experiments:
            print("1. Create experiment: `bcllm --create-experiment val_partial_exec`")
            print("2. Add model: `bcllm --experiment val_partial_exec --add-model <model_id>`")
            print("3. Add questions: `bcllm --experiment val_partial_exec --add-questions 1-3`")
            print("4. Create run: `bcllm --experiment val_partial_exec --create-run run_001`")
            print("5. Execute: `bcllm --experiment val_partial_exec --run run_001 --execute`")
        else:
            print("1. Execute: `bcllm --experiment <name> --run <run_id> --execute`")
            print("2. Re-run this validation script to verify debug capture")
    else:
        print("\n❌ **FAIL** — Schema issues remain")
        print("\n**Remaining Issues:**")
        if schema_result['needs_review']:
            print("- Remove `needs_review` column from INSERT statement")
        if not schema_result['response_tokens']:
            print("- Add `response_tokens` column to schema/code")
    
    return 0 if schema_pass else 1

if __name__ == '__main__':
    sys.exit(main())
