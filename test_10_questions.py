import sys
sys.path.insert(0, '.')

from src.main import BenchmarkRunner
import argparse

args = argparse.Namespace(
    models=['Qwen'],
    questions=['Q001-Q010'],  # 10 questões
    iterations=1,
    test_mode=True,
    verbose=False,
    dry_run=False,
    seed=42,  # Seed fixa para reprodutibilidade
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
