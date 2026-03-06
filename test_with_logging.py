import sys
sys.path.insert(0, '.')

# Setup logging first
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)

from src.main import BenchmarkRunner
import argparse

args = argparse.Namespace(
    models=['Qwen'],
    questions=['Q001'],
    iterations=1,
    test_mode=True,
    verbose=True,
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

print("Starting runner...")
runner = BenchmarkRunner(args)
print("Running...")
exit_code = runner.run()
print(f"Exit code: {exit_code}")
