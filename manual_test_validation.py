#!/usr/bin/env python3
"""Manual test: Verify precondition validation works."""
import os
import sys

# Test 1: Missing QUESTIONS_DATASET_PATH
print("=" * 80)
print("TEST: Missing QUESTIONS_DATASET_PATH with --add-questions")
print("=" * 80)

# Save original value
original_path = os.environ.get("QUESTIONS_DATASET_PATH")

# Remove it temporarily
os.environ.pop("QUESTIONS_DATASET_PATH", None)
os.environ["OPENROUTER_API_KEY"] = "test_key_for_validation"

# Simulate command line
sys.argv = ["bcllm.py", "--create-experiment", "test_manual_q", "--add-questions", "1-5"]

try:
    from bcllm import main
    main()
    print("❌ FAIL: Should have exited with error")
except SystemExit as e:
    if e.code == 1:
        print("✅ PASS: Correctly exited with code 1")
    else:
        print(f"⚠️  Exit code: {e.code}")
finally:
    # Restore
    if original_path:
        os.environ["QUESTIONS_DATASET_PATH"] = original_path

print()

# Test 2: Missing OPENROUTER_API_KEY
print("=" * 80)
print("TEST: Missing OPENROUTER_API_KEY")
print("=" * 80)

original_api_key = os.environ.get("OPENROUTER_API_KEY")
os.environ.pop("OPENROUTER_API_KEY", None)

sys.argv = ["bcllm.py", "--create-experiment", "test_manual_api", "--add-model", "openai/gpt-4o-mini"]

try:
    # Need to reload to pick up new env vars
    import importlib
    import bcllm
    importlib.reload(bcllm)
    from bcllm import main
    main()
    print("❌ FAIL: Should have exited with error")
except SystemExit as e:
    if e.code == 1:
        print("✅ PASS: Correctly exited with code 1")
    else:
        print(f"⚠️  Exit code: {e.code}")
finally:
    # Restore
    if original_api_key:
        os.environ["OPENROUTER_API_KEY"] = original_api_key

print()
print("=" * 80)
print("Manual tests complete!")
print("=" * 80)
