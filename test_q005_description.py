#!/usr/bin/env python3
"""Test Q005 with image description prompt."""

import sys
sys.path.insert(0, '.')

from src.main import BenchmarkRunner
import argparse

args = argparse.Namespace(
    models=['Qwen'],
    questions=['Q005'],  # Question with image
    iterations=1,
    test_mode=True,
    verbose=True,  # Verbose to see the prompt
    dry_run=False,
    seed=None,
    vary_seed=False,
    output_format='console',
    output_file=None,
    config=None,
    reasoning_effort=None,
    reasoning_tokens=None,
    reasoning_exclude=False,
)

print("="*80)
print("TEST: Q005 WITH IMAGE DESCRIPTION PROMPT")
print("="*80)
print()

runner = BenchmarkRunner(args)
exit_code = runner.run()

print()
print("="*80)
print(f"EXIT CODE: {exit_code}")
print("="*80)
