import sys
sys.path.insert(0, '.')

from src.main import BenchmarkRunner
import argparse

args = argparse.Namespace(
    models=['Qwen'],
    questions=['Q001'],
    iterations=1,
    test_mode=True,
    verbose=False,  # Less verbose
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

runner = BenchmarkRunner(args)
exit_code = runner.run()
print(f"\n{'='*80}")
print(f"EXIT CODE: {exit_code}")
print(f"{'='*80}")
