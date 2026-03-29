#!/usr/bin/env python3
"""Comprehensive null semantics test suite."""

import subprocess
import sys

def run_command(cmd):
    """Run CLI command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

print("=" * 70)
print("COMPREHENSIVE NULL SEMANTICS TEST SUITE")
print("=" * 70)

tests_passed = 0
tests_failed = 0

# Test 1: --questions null (should use ALL questions, no .env fallback)
print("\n1. --questions null (should use ALL questions):")
code, out, err = run_command("python bcllm.py --create-experiment test_final_q_null --questions null")
if code == 0 and "Using DEFAULT_QUESTIONS" not in out and "Summary: 92 added" in out:
    print("   ✓ PASS: No .env fallback, all questions selected")
    tests_passed += 1
else:
    print(f"   ✗ FAIL: {out[:200]}")
    tests_failed += 1

# Test 2: --questions 1-5 (should use only specified range)
print("\n2. --questions 1-5 (should use only 1-5):")
code, out, err = run_command("python bcllm.py --create-experiment test_final_q_1_5 --questions 1-5")
if code == 0 and "Summary: 5 added" in out:
    print("   ✓ PASS: Only questions 1-5 added")
    tests_passed += 1
else:
    print(f"   ✗ FAIL: {out[:200]}")
    tests_failed += 1

# Test 3: No --questions (should use DEFAULT_QUESTIONS from .env)
print("\n3. No --questions (should use .env DEFAULT_QUESTIONS):")
code, out, err = run_command("python bcllm.py --create-experiment test_final_q_default")
if code == 0 and "Using DEFAULT_QUESTIONS from .env" in out:
    print("   ✓ PASS: .env fallback works")
    tests_passed += 1
else:
    print(f"   ✗ FAIL: {out[:200]}")
    tests_failed += 1

# Test 4: --seed null (should be None, no .env fallback)
print("\n4. --seed null (should be None):")
code, out, err = run_command("python bcllm.py --create-experiment test_final_seed_null --seed null")
if code == 0:
    # Check database
    from src.cli.database import get_database_connection
    from src.db.repository import ExperimentRepository
    import json
    
    conn = get_database_connection()
    repo = ExperimentRepository(conn)
    exp = repo.get_by_name('test_final_seed_null')
    config = json.loads(exp.config_json) if exp.config_json else {}
    seed = config.get('RUN_RESPONSES_SEED')
    
    if seed == "OFF":  # None is serialized as "OFF"
        print("   ✓ PASS: seed = None (serialized as 'OFF')")
        tests_passed += 1
    else:
        print(f"   ✗ FAIL: seed = {seed}")
        tests_failed += 1
    conn.close()
else:
    print(f"   ✗ FAIL: {err[:200]}")
    tests_failed += 1

# Test 5: --top-k null (should be None)
print("\n5. --top-k null (should be None):")
code, out, err = run_command("python bcllm.py --create-experiment test_final_topk_null --top-k null")
if code == 0:
    from src.cli.database import get_database_connection
    from src.db.repository import ExperimentRepository
    import json
    
    conn = get_database_connection()
    repo = ExperimentRepository(conn)
    exp = repo.get_by_name('test_final_topk_null')
    config = json.loads(exp.config_json) if exp.config_json else {}
    top_k = config.get('MODEL_TOP_K')
    
    if top_k is None:
        print("   ✓ PASS: MODEL_TOP_K = None")
        tests_passed += 1
    else:
        print(f"   ✗ FAIL: MODEL_TOP_K = {top_k}")
        tests_failed += 1
    conn.close()
else:
    print(f"   ✗ FAIL: {err[:200]}")
    tests_failed += 1

# Test 6: --system-prompt null (should be None)
print("\n6. --system-prompt null (should be None):")
code, out, err = run_command("python bcllm.py --create-experiment test_final_sp_null --system-prompt null")
if code == 0:
    from src.cli.database import get_database_connection
    from src.db.repository import ExperimentRepository
    import json
    
    conn = get_database_connection()
    repo = ExperimentRepository(conn)
    exp = repo.get_by_name('test_final_sp_null')
    config = json.loads(exp.config_json) if exp.config_json else {}
    sp = config.get('SYSTEM_PROMPT')
    
    if sp is None:
        print("   ✓ PASS: SYSTEM_PROMPT = None")
        tests_passed += 1
    else:
        print(f"   ✗ FAIL: SYSTEM_PROMPT = {repr(sp)}")
        tests_failed += 1
    conn.close()
else:
    print(f"   ✗ FAIL: {err[:200]}")
    tests_failed += 1

# Test 7: --temperature null (should be None)
print("\n7. --temperature null (should be None):")
code, out, err = run_command("python bcllm.py --create-experiment test_final_temp_null --temperature null")
if code == 0:
    from src.cli.database import get_database_connection
    from src.db.repository import ExperimentRepository
    import json
    
    conn = get_database_connection()
    repo = ExperimentRepository(conn)
    exp = repo.get_by_name('test_final_temp_null')
    config = json.loads(exp.config_json) if exp.config_json else {}
    temp = config.get('MODEL_TEMPERATURE')
    
    if temp is None:
        print("   ✓ PASS: MODEL_TEMPERATURE = None")
        tests_passed += 1
    else:
        print(f"   ✗ FAIL: MODEL_TEMPERATURE = {temp}")
        tests_failed += 1
    conn.close()
else:
    print(f"   ✗ FAIL: {err[:200]}")
    tests_failed += 1

# Test 8: --reasoning null (should be None)
print("\n8. --reasoning null (should be None):")
code, out, err = run_command("python bcllm.py --create-experiment test_final_reasoning_null --reasoning null")
if code == 0:
    from src.cli.database import get_database_connection
    from src.db.repository import ExperimentRepository
    import json
    
    conn = get_database_connection()
    repo = ExperimentRepository(conn)
    exp = repo.get_by_name('test_final_reasoning_null')
    config = json.loads(exp.config_json) if exp.config_json else {}
    reasoning = config.get('MODEL_REASONING_EFFORT')
    
    if reasoning is None:
        print("   ✓ PASS: MODEL_REASONING_EFFORT = None")
        tests_passed += 1
    else:
        print(f"   ✗ FAIL: MODEL_REASONING_EFFORT = {reasoning}")
        tests_failed += 1
    conn.close()
else:
    print(f"   ✗ FAIL: {err[:200]}")
    tests_failed += 1

# Summary
print("\n" + "=" * 70)
print(f"TEST SUMMARY: {tests_passed} passed, {tests_failed} failed")
print("=" * 70)

if tests_failed > 0:
    sys.exit(1)
else:
    print("\n✅ ALL TESTS PASSED!")
    sys.exit(0)
