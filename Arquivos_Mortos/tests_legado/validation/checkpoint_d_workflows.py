#!/usr/bin/env python3
"""Checkpoint D validation — Variant Identity.

Validates that the variant identity system works correctly:
1. Same model + different config → different signatures
2. Same model + same config → same signature (collision)
3. Config stored correctly in DB
4. Signatures are deterministic
"""

import sqlite3
import json
import subprocess
import sys
import os
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = "data/bcllm.db"


def run_command(cmd: str) -> tuple[int, str, str]:
    """Run shell command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def query_db(query: str) -> list[dict]:
    """Query database and return results as dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def reset_database():
    """Drop and recreate database."""
    db_path = Path(DB_PATH)
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    if db_path.exists():
        # Close any connections and wait a bit
        try:
            # Try to get a connection and close it properly
            conn = sqlite3.connect(DB_PATH)
            conn.close()
            del conn
        except Exception:
            pass
        
        import time
        time.sleep(0.5)  # Give Windows time to release the lock
        
        try:
            db_path.unlink()
        except PermissionError:
            # Database might be locked - try to drop tables instead
            print("  Note: Database exists, dropping tables instead...")
            conn = sqlite3.connect(DB_PATH)
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.executescript("""
                DROP TABLE IF EXISTS errors;
                DROP TABLE IF EXISTS responses;
                DROP TABLE IF EXISTS runs;
                DROP TABLE IF EXISTS question_snapshots;
                DROP TABLE IF EXISTS model_variants;
                DROP TABLE IF EXISTS experiments;
            """)
            conn.commit()
            conn.close()
            # Recreate schema
            from src.db.schema import create_schema
            conn = sqlite3.connect(DB_PATH)
            create_schema(conn)
            conn.close()
            print("✓ Database reset (tables dropped and recreated)")
            return
    
    from src.db.schema import create_schema
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    conn.close()
    print("✓ Database reset")


def test_workflow_1():
    """Workflow 1: Same model, different reasoning → different signatures."""
    print("=" * 60)
    print("Workflow 1: Same model, different reasoning")
    print("=" * 60)
    
    # Create experiment
    code, out, err = run_command("python bcllm.py --create-experiment var_test")
    if code != 0:
        print(f"❌ Failed to create experiment: {err}")
        return False
    
    # Add model with low reasoning
    code, out, err = run_command(
        "python bcllm.py --experiment var_test --add-model google/gemini-3.1-flash-lite-preview --reasoning low"
    )
    if code != 0 and "already exists" not in err and "already exists" not in out:
        print(f"❌ Failed to add model with low reasoning: {err}")
        return False
    
    # Add model with high reasoning
    code, out, err = run_command(
        "python bcllm.py --experiment var_test --add-model google/gemini-3.1-flash-lite-preview --reasoning high"
    )
    if code != 0 and "already exists" not in err and "already exists" not in out:
        print(f"❌ Failed to add model with high reasoning: {err}")
        return False
    
    # Query signatures
    results = query_db("""
        SELECT variant_signature, config 
        FROM model_variants 
        WHERE experiment_id=(SELECT experiment_id FROM experiments WHERE name='var_test')
        ORDER BY created_at
    """)
    
    if len(results) != 2:
        print(f"❌ Expected 2 variants, got {len(results)}")
        return False
    
    sig1, sig2 = results[0]['variant_signature'], results[1]['variant_signature']
    
    if sig1 == sig2:
        print(f"❌ Signatures should be different: {sig1} == {sig2}")
        return False
    
    # Verify signatures contain reasoning
    sigs_have_reasoning = (
        ('reasoning=low' in sig1 and 'reasoning=high' in sig2) or
        ('reasoning=high' in sig1 and 'reasoning=low' in sig2)
    )
    
    if not sigs_have_reasoning:
        print(f"❌ Signatures don't contain reasoning: {sig1}, {sig2}")
        return False
    
    print(f"  Signature 1: {sig1}")
    print(f"  Signature 2: {sig2}")
    print("  ✅ Workflow 1 passed")
    return True


def test_workflow_2():
    """Workflow 2: Same model, same config → collision."""
    print("=" * 60)
    print("Workflow 2: Same model, same config (collision expected)")
    print("=" * 60)
    
    # Try to add same model with same reasoning again
    code, out, err = run_command(
        "python bcllm.py --experiment var_test --add-model google/gemini-3.1-flash-lite-preview --reasoning low"
    )
    
    if "already exists" not in err and "already exists" not in out:
        print(f"❌ Expected collision error, got: stdout={out} stderr={err}")
        return False
    
    print(f"  Collision detected correctly")
    print("  ✅ Workflow 2 passed")
    return True


def test_workflow_3():
    """Workflow 3: Verify config stored correctly."""
    print("=" * 60)
    print("Workflow 3: Verify config stored correctly")
    print("=" * 60)
    
    results = query_db("""
        SELECT variant_signature, config 
        FROM model_variants 
        WHERE experiment_id=(SELECT experiment_id FROM experiments WHERE name='var_test')
    """)
    
    for result in results:
        sig = result['variant_signature']
        config_str = result['config']
        
        try:
            config = json.loads(config_str)
        except json.JSONDecodeError as e:
            print(f"❌ Config is not valid JSON: {config_str} - {e}")
            return False
        
        # Verify config has expected fields when signature has reasoning
        if 'reasoning=' in sig:
            if 'reasoning_effort' not in config:
                print(f"❌ Signature has reasoning but config doesn't have reasoning_effort: {sig}")
                return False
    
    print(f"  All configs are valid JSON")
    print("  ✅ Workflow 3 passed")
    return True


def test_workflow_4():
    """Workflow 4: Signature determinism."""
    print("=" * 60)
    print("Workflow 4: Signature determinism (same inputs → same output)")
    print("=" * 60)
    
    from src.utils.variant_signature import generate_variant_signature
    
    config = {"reasoning_effort": "low", "vision": True}
    sig1 = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
    sig2 = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
    
    if sig1 != sig2:
        print(f"❌ Signatures not deterministic: {sig1} != {sig2}")
        return False
    
    print(f"  Signature: {sig1}")
    print("  ✅ Workflow 4 passed")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("CHECKPOINT D: VALIDATION WORKFLOWS")
    print("=" * 60)
    
    # Reset database
    reset_database()
    
    all_pass = True
    all_pass &= test_workflow_1()
    all_pass &= test_workflow_2()
    all_pass &= test_workflow_3()
    all_pass &= test_workflow_4()
    
    print("\n" + "=" * 60)
    if all_pass:
        print("✅ All workflows passed")
        print("✅ Variant identity system working correctly")
        sys.exit(0)
    else:
        print("❌ Some workflows failed")
        sys.exit(1)
