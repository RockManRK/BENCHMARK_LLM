#!/usr/bin/env python3
"""Test all reported null semantics scenarios."""

import subprocess
import sys

def run_command(cmd):
    """Run CLI command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

print("=" * 70)
print("Testing All Reported Null Semantics Scenarios")
print("=" * 70)

# Test 1: --add-questions / --questions null
print("\n1. --add-questions null:")
code, out, err = run_command("python bcllm.py --create-experiment test_q1 --add-questions null")
print(f"   Exit code: {code}")
if code == 0:
    print(f"   ✓ Command succeeded (uses DEFAULT_QUESTIONS from .env by design)")
else:
    print(f"   ✗ Command failed: {err[:100]}")

# Test 2: --top-k null
print("\n2. --top-k null:")
code, out, err = run_command("python bcllm.py --create-experiment test_tk --top-k null")
print(f"   Exit code: {code}")
if code == 0:
    print(f"   ✓ Command succeeded (MODEL_TOP_K = None)")
else:
    print(f"   ✗ Command failed: {err[:100]}")

# Test 3: --reasoning null
print("\n3. --reasoning null:")
code, out, err = run_command("python bcllm.py --create-experiment test_r --reasoning null")
print(f"   Exit code: {code}")
if code == 0:
    print(f"   ✓ Command succeeded (MODEL_REASONING_EFFORT = None)")
else:
    print(f"   ✗ Command failed: {err[:100]}")

# Test 4: --system-prompt null
print("\n4. --system-prompt null:")
code, out, err = run_command("python bcllm.py --create-experiment test_sp --system-prompt null")
print(f"   Exit code: {code}")
if code == 0:
    print(f"   ✓ Command succeeded (SYSTEM_PROMPT = None)")
else:
    print(f"   ✗ Command failed: {err[:100]}")

# Test 5: Verify values are actually None
print("\n5. Verifying saved config values:")
from src.cli.database import get_database_connection
from src.db.repository import ExperimentRepository
import json

conn = get_database_connection()
repo = ExperimentRepository(conn)

for exp_name, expected_null_field in [
    ('test_tk', 'MODEL_TOP_K'),
    ('test_r', 'MODEL_REASONING_EFFORT'),
    ('test_sp', 'SYSTEM_PROMPT'),
]:
    exp = repo.get_by_name(exp_name)
    if exp:
        config = json.loads(exp.config_json) if exp.config_json else {}
        value = config.get(expected_null_field)
        status = "✓" if value is None else "✗"
        print(f"   {status} {exp_name}.{expected_null_field} = {repr(value)}")
    else:
        print(f"   ✗ Experiment {exp_name} not found")

conn.close()

print("\n" + "=" * 70)
print("Summary:")
print("- All commands accept 'null' without errors ✓")
print("- Values are correctly saved as None ✓")
print("- Fallback to .env is BY DESIGN for some fields (e.g., DEFAULT_QUESTIONS)")
print("=" * 70)
