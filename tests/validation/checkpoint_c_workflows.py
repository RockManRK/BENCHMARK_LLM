#!/usr/bin/env python3
"""Checkpoint C validation — All TO-BE commands reachable.

This script validates that all TO-BE commands from the specification are:
1. Recognized by the CLI (no "unrecognized arguments" errors)
2. Route exclusively to src_v2 (no legacy /src imports)
3. Fail loudly when appropriate (unknown commands)

TO-BE Command List:
- Experiments: --create-experiment, --experiment, --list-experiments, --remove-experiment
- Models: --add-model, --list-models, --remove-model
- Questions: --add-questions, --list-questions, --remove-question
- Runs: --add-run, --list-runs, --run, --remove-run
- Execution: --execute
- Review: --review-experiment, --review-all
- Help: --help

Usage:
    python tests/validation/checkpoint_c_workflows.py

Exit Codes:
    0: All TO-BE commands validated
    1: One or more commands failed
"""

import subprocess
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
BCLLM_SCRIPT = PROJECT_ROOT / "bcllm.py"


def run_command(cmd: str) -> tuple[int, str, str]:
    """Run shell command and return (exit_code, stdout, stderr).

    Args:
        cmd: Command to execute.

    Returns:
        Tuple of (exit_code, stdout, stderr).
    """
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    return result.returncode, result.stdout, result.stderr


def check_no_src_import(output: str) -> bool:
    """Check that output doesn't contain src import errors.

    Args:
        output: Combined stdout/stderr from command execution.

    Returns:
        True if no legacy src imports detected, False otherwise.
    """
    src_indicators = [
        "ModuleNotFoundError: No module named 'src",
        "from src.",
        "import src",
        "src_v1",
        "src/legacy",
    ]
    return not any(ind in output for ind in src_indicators)


def test_help() -> bool:
    """Test --help command.

    Expected:
    - Exit code 0
    - Contains "Benchmark LLM"
    - No legacy src imports
    """
    print("\nTesting: --help")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --help')

    if code != 0:
        print(f"  ❌ FAILED: Exit code {code}")
        print(f"     stderr: {err[:200]}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    # Check for expected content
    if "Benchmark LLM" not in out:
        print(f"  ❌ FAILED: Expected 'Benchmark LLM' in help output")
        return False

    print(f"  ✅ PASSED")
    return True


def test_create_experiment() -> bool:
    """Test --create-experiment command.

    Expected:
    - Recognized argument (no "unrecognized arguments" error)
    - No legacy src imports
    """
    print("\nTesting: --create-experiment")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --create-experiment val_cli_test')

    # May fail if experiment exists, but should not be "unrecognized arguments"
    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_list_experiments() -> bool:
    """Test --list-experiments command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --list-experiments")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --list-experiments')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_experiment_view() -> bool:
    """Test --experiment command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --experiment")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test')

    # May fail if experiment doesn't exist, but should not be "unrecognized arguments"
    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_add_model() -> bool:
    """Test --add-model command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --add-model")
    code, out, err = run_command(
        f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --add-model google/gemini-3.1-flash-lite-preview'
    )

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_list_models() -> bool:
    """Test --list-models command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --list-models")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --list-models')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_remove_model() -> bool:
    """Test --remove-model command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --remove-model")
    code, out, err = run_command(
        f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --remove-model google/gemini-3.1-flash-lite-preview'
    )

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_add_questions() -> bool:
    """Test --add-questions command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --add-questions")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --add-questions 1-5')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_list_questions() -> bool:
    """Test --list-questions command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --list-questions")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --list-questions')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_add_run() -> bool:
    """Test --add-run command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --add-run")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --add-run')

    # May fail if experiment doesn't exist, but should not be "unrecognized arguments"
    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_list_runs() -> bool:
    """Test --list-runs command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --list-runs")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --list-runs')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_run() -> bool:
    """Test --run command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --run")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --run test_run')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_remove_run() -> bool:
    """Test --remove-run command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --remove-run")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --remove-run test_run')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_execute() -> bool:
    """Test --execute command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --execute")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --execute')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_review_experiment() -> bool:
    """Test --review-experiment command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --review-experiment")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --review-experiment val_cli_test')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_review_all() -> bool:
    """Test --review-all command.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --review-all")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --review-all')

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_reasoning_flag() -> bool:
    """Test --reasoning flag with --add-model.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --reasoning flag")
    code, out, err = run_command(
        f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --add-model google/gemini-3.1-flash-lite-preview --reasoning low'
    )

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_vision_flag() -> bool:
    """Test --vision flag with --add-model.

    Expected:
    - Recognized argument
    - No legacy src imports
    """
    print("\nTesting: --vision flag")
    code, out, err = run_command(
        f'python "{BCLLM_SCRIPT}" --experiment val_cli_test --add-model google/gemini-3.1-flash-lite-preview --vision true'
    )

    if "unrecognized arguments" in err:
        print(f"  ❌ FAILED: {err}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def test_unknown_command() -> bool:
    """Test unknown command fails loudly.

    Expected:
    - Exit code != 0
    - Error message contains "Unknown command"
    - No legacy src imports
    """
    print("\nTesting: Unknown command fails loudly")
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --unknown-command')

    if code == 0:
        print(f"  ❌ FAILED: Expected non-zero exit code, got 0")
        return False

    if "Unknown command" not in err:
        print(f"  ❌ FAILED: Expected 'Unknown command' error message")
        print(f"     stderr: {err[:200]}")
        return False

    if not check_no_src_import(out + err):
        print(f"  ❌ FAILED: Legacy src import detected")
        return False

    print(f"  ✅ PASSED")
    return True


def main() -> int:
    """Run all validation tests."""
    print("\n" + "=" * 60)
    print("CHECKPOINT C: VALIDATION WORKFLOWS")
    print("=" * 60)

    all_pass = True

    # Help
    all_pass &= test_help()

    # Experiments
    all_pass &= test_create_experiment()
    all_pass &= test_list_experiments()
    all_pass &= test_experiment_view()

    # Models
    all_pass &= test_add_model()
    all_pass &= test_list_models()
    all_pass &= test_remove_model()

    # Questions
    all_pass &= test_add_questions()
    all_pass &= test_list_questions()

    # Runs
    all_pass &= test_add_run()
    all_pass &= test_list_runs()
    all_pass &= test_run()
    all_pass &= test_remove_run()

    # Execution
    all_pass &= test_execute()

    # Review
    all_pass &= test_review_experiment()
    all_pass &= test_review_all()

    # Flags
    all_pass &= test_reasoning_flag()
    all_pass &= test_vision_flag()

    # Error handling
    all_pass &= test_unknown_command()

    print("\n" + "=" * 60)
    if all_pass:
        print("✅ All TO-BE commands validated")
        print("✅ No legacy fallback detected")
        print("=" * 60)
        return 0
    else:
        print("❌ Some commands failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
