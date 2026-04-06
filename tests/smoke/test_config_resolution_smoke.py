"""Integration smoke test for configuration resolution across separate CLI invocations.

This test validates that the configuration resolver correctly inherits from
experiment.config_json (NOT from .env) when --add-model and --add-run are
executed in separate CLI invocations from --create-experiment.

The original bug: when commands are executed separately, .env values at the
time of --add-model/--add-run would override the frozen experiment config,
instead of inheriting from the experiment's config_json.

Usage:
    python tests/smoke/test_config_resolution_smoke.py

Exit code:
    0 if all tests pass
    1 if any test fails
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BCLLM = str(PROJECT_ROOT / "bcllm.py")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_env(env_vars: dict[str, str]) -> str:
    """Write a temporary .env file and return its absolute path."""
    fd, path = tempfile.mkstemp(suffix=".env", prefix="smoke_env_")
    with os.fdopen(fd, "w") as f:
        for key, value in env_vars.items():
            f.write(f'{key}={value}\n')
    return path


def _run_bcllm(args: list[str], env_path: str, db_path: str) -> subprocess.CompletedProcess:
    """Run bcllm.py with a custom .env and DATABASE_PATH.

    The DATABASE_PATH env var is read by the test's monkey-patch of
    get_database_path() — but since we're running a subprocess, we need
    the DB path to be wired differently.

    Strategy: we create a small wrapper script that:
    1. Sets the .env path
    2. Patches get_database_path before calling main()

    However, the simpler approach for this smoke test is to:
    1. Copy the temp DB to the expected location before each invocation
    2. Read it back after

    Even simpler: we use a wrapper Python script that patches the DB path
    at import time and then calls bcllm.main().
    """
    # Build a wrapper that patches the database path
    wrapper_fd, wrapper_path = tempfile.mkstemp(suffix="_wrapper.py", prefix="smoke_")
    wrapper_code = f'''
import sys
sys.path.insert(0, {str(PROJECT_ROOT)!r})

from pathlib import Path
from unittest.mock import patch

# Patch DB path before any import of database module
with patch("src.cli.database.get_database_path", return_value=Path({db_path!r})):
    # Load the specified .env file
    from dotenv import load_dotenv
    load_dotenv({env_path!r}, override=True)

    # Also patch os.environ so ConfigResolver sees the right values
    import os as _os
    from dotenv import dotenv_values
    env_values = dotenv_values({env_path!r})
    for k, v in env_values.items():
        if v is not None:
            _os.environ[k] = v

    # Now import and run bcllm
    from bcllm import main as bcllm_main
    sys.argv = ["bcllm"] + {args!r}
    exit_code = bcllm_main()
    sys.exit(exit_code)
'''
    with os.fdopen(wrapper_fd, "w") as f:
        f.write(wrapper_code)

    try:
        result = subprocess.run(
            [sys.executable, wrapper_path],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )
        return result
    finally:
        os.unlink(wrapper_path)


def _get_db_connection(db_path: str) -> sqlite3.Connection:
    """Get a direct SQLite connection to the temp database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_experiment(conn, name: str) -> sqlite3.Row | None:
    """Fetch an experiment by name."""
    cur = conn.execute(
        "SELECT * FROM experiments WHERE name = ?", (name,)
    )
    return cur.fetchone()


def _get_model_variants(conn, experiment_id: str) -> list[sqlite3.Row]:
    """Fetch all model variants for an experiment."""
    cur = conn.execute(
        "SELECT * FROM model_variants WHERE experiment_id = ?", (experiment_id,)
    )
    return cur.fetchall()


def _get_runs(conn, experiment_id: str) -> list[sqlite3.Row]:
    """Fetch all runs for an experiment."""
    cur = conn.execute(
        "SELECT * FROM runs WHERE experiment_id = ?", (experiment_id,)
    )
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------


class SmokeTestResult:
    """Tracks pass/fail for individual smoke test steps."""

    def __init__(self):
        self.results: list[dict] = []

    def record(self, step: str, passed: bool, detail: str = ""):
        self.results.append({"step": step, "passed": passed, "detail": detail})
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {step}")
        if detail and not passed:
            print(f"         Detail: {detail}")

    @property
    def all_passed(self) -> bool:
        return all(r["passed"] for r in self.results)


def run_smoke_tests() -> SmokeTestResult:
    """Execute all smoke test steps and return results."""
    results = SmokeTestResult()

    # ------------------------------------------------------------------
    # Setup: create temp DB and .env
    # ------------------------------------------------------------------
    print("=" * 70)
    print("CONFIGURATION RESOLUTION SMOKE TEST")
    print("=" * 70)

    # Temp database
    fd_db, temp_db_path = tempfile.mkstemp(suffix=".db", prefix="smoke_benchmark_")
    os.close(fd_db)  # Close the fd so sqlite3 can open it

    # Initial .env with known baseline values
    temp_env_path = _make_temp_env({
        "OPENROUTER_API_KEY": "sk-dummy-key-for-smoke-test",
        "MODEL_TEMPERATURE": "0.5",
        "SYSTEM_PROMPT": "from_env_prompt",
        "QUESTIONS_DATASET_PATH": "./data/questions.json",
    })

    print(f"\nTemp DB : {temp_db_path}")
    print(f"Temp ENV: {temp_env_path}")
    print()

    try:
        # ================================================================
        # Step 1 — Create experiment with known config
        # ================================================================
        print("-" * 70)
        print("STEP 1: Create experiment with --temperature 0.9 --system-prompt from_cli_prompt")
        print("-" * 70)

        result = _run_bcllm(
            args=[
                "--create-experiment", "smoke_test",
                "--temperature", "0.9",
                "--system-prompt", "from_cli_prompt",
            ],
            env_path=temp_env_path,
            db_path=temp_db_path,
        )

        if result.returncode != 0:
            results.record(
                "Step 1: Create experiment",
                passed=False,
                detail=f"CLI exited with code {result.returncode}\nSTDERR: {result.stderr}",
            )
            return results  # Cannot continue without experiment

        # Verify experiment config in DB
        conn = _get_db_connection(temp_db_path)
        try:
            exp = _get_experiment(conn, "smoke_test")
            if exp is None:
                results.record(
                    "Step 1: Create experiment",
                    passed=False,
                    detail="Experiment 'smoke_test' not found in database",
                )
                return results

            config = json.loads(exp["config_json"])
            temp_ok = config.get("MODEL_TEMPERATURE") == 0.9
            prompt_ok = config.get("SYSTEM_PROMPT") == "from_cli_prompt"

            if temp_ok and prompt_ok:
                results.record("Step 1: Create experiment", passed=True)
            else:
                results.record(
                    "Step 1: Create experiment",
                    passed=False,
                    detail=(
                        f"Expected MODEL_TEMPERATURE=0.9, got {config.get('MODEL_TEMPERATURE')!r}; "
                        f"Expected SYSTEM_PROMPT='from_cli_prompt', got {config.get('SYSTEM_PROMPT')!r}"
                    ),
                )
                return results
        finally:
            conn.close()

        # ================================================================
        # Step 2 — --add-model separately (THE MAIN BUG)
        # ================================================================
        print()
        print("-" * 70)
        print("STEP 2: --add-model separately (main bug — should inherit from experiment, NOT .env)")
        print("        .env changed: MODEL_TEMPERATURE=0.3, SYSTEM_PROMPT=changed_env_prompt")
        print("-" * 70)

        # Change .env to different values — the model should NOT pick these up
        os.unlink(temp_env_path)
        temp_env_path = _make_temp_env({
            "OPENROUTER_API_KEY": "sk-dummy-key-for-smoke-test",
            "MODEL_TEMPERATURE": "0.3",
            "SYSTEM_PROMPT": "changed_env_prompt",
            "QUESTIONS_DATASET_PATH": "./data/questions.json",
        })

        result = _run_bcllm(
            args=[
                "--experiment", "smoke_test",
                "--add-model", "openai/gpt-4o-mini",
            ],
            env_path=temp_env_path,
            db_path=temp_db_path,
        )

        if result.returncode != 0:
            results.record(
                "Step 2: --add-model inherits from experiment",
                passed=False,
                detail=f"CLI exited with code {result.returncode}\nSTDERR: {result.stderr}",
            )
        else:
            conn = _get_db_connection(temp_db_path)
            try:
                exp = _get_experiment(conn, "smoke_test")
                variants = _get_model_variants(conn, exp["experiment_id"])

                if not variants:
                    results.record(
                        "Step 2: --add-model inherits from experiment",
                        passed=False,
                        detail="No model variant found in database",
                    )
                else:
                    v = variants[0]
                    vconfig = json.loads(v["config"])
                    temp_val = vconfig.get("MODEL_TEMPERATURE")
                    # Should be 0.9 from experiment, NOT 0.3 from .env
                    temp_ok = temp_val == 0.9

                    if temp_ok:
                        results.record("Step 2: --add-model inherits from experiment", passed=True)
                    else:
                        results.record(
                            "Step 2: --add-model inherits from experiment",
                            passed=False,
                            detail=(
                                f"MODEL_TEMPERATURE should be 0.9 (from experiment), "
                                f"but got {temp_val!r} — config inherited from .env instead of experiment"
                            ),
                        )
            finally:
                conn.close()

        # ================================================================
        # Step 3a — --add-run with explicit CLI override
        # ================================================================
        print()
        print("-" * 70)
        print("STEP 3a: --add-run with explicit --system-prompt override")
        print("-" * 70)

        result = _run_bcllm(
            args=[
                "--experiment", "smoke_test",
                "--add-run",
                "--system-prompt", "run_custom_prompt",
            ],
            env_path=temp_env_path,
            db_path=temp_db_path,
        )

        if result.returncode != 0:
            results.record(
                "Step 3a: --add-run with CLI override",
                passed=False,
                detail=f"CLI exited with code {result.returncode}\nSTDERR: {result.stderr}",
            )
        else:
            conn = _get_db_connection(temp_db_path)
            try:
                exp = _get_experiment(conn, "smoke_test")
                runs = _get_runs(conn, exp["experiment_id"])

                if not runs:
                    results.record(
                        "Step 3a: --add-run with CLI override",
                        passed=False,
                        detail="No run found in database",
                    )
                else:
                    r = runs[0]
                    rconfig = json.loads(r["config"])
                    prompt_val = rconfig.get("SYSTEM_PROMPT")

                    if prompt_val == "run_custom_prompt":
                        results.record("Step 3a: --add-run with CLI override", passed=True)
                    else:
                        results.record(
                            "Step 3a: --add-run with CLI override",
                            passed=False,
                            detail=(
                                f"SYSTEM_PROMPT should be 'run_custom_prompt', got {prompt_val!r}"
                            ),
                        )
            finally:
                conn.close()

        # ================================================================
        # Step 3b — --add-run without override (should inherit from experiment)
        # ================================================================
        print()
        print("-" * 70)
        print("STEP 3b: --add-run without --system-prompt (should inherit from experiment)")
        print("-" * 70)

        result = _run_bcllm(
            args=[
                "--experiment", "smoke_test",
                "--add-run",
            ],
            env_path=temp_env_path,
            db_path=temp_db_path,
        )

        if result.returncode != 0:
            results.record(
                "Step 3b: --add-run inherits from experiment",
                passed=False,
                detail=f"CLI exited with code {result.returncode}\nSTDERR: {result.stderr}",
            )
        else:
            conn = _get_db_connection(temp_db_path)
            try:
                exp = _get_experiment(conn, "smoke_test")
                runs = _get_runs(conn, exp["experiment_id"])

                if len(runs) < 2:
                    results.record(
                        "Step 3b: --add-run inherits from experiment",
                        passed=False,
                        detail=f"Expected 2 runs, found {len(runs)}",
                    )
                else:
                    # The second run (index 1) is the one without override
                    r = runs[1]
                    rconfig = json.loads(r["config"])
                    prompt_val = rconfig.get("SYSTEM_PROMPT")

                    # Should be "from_cli_prompt" from experiment, NOT "changed_env_prompt" from .env
                    if prompt_val == "from_cli_prompt":
                        results.record("Step 3b: --add-run inherits from experiment", passed=True)
                    else:
                        results.record(
                            "Step 3b: --add-run inherits from experiment",
                            passed=False,
                            detail=(
                                f"SYSTEM_PROMPT should be 'from_cli_prompt' (from experiment), "
                                f"got {prompt_val!r}"
                            ),
                        )
            finally:
                conn.close()

        # ================================================================
        # Step 4 — system-default skips inheritance
        # ================================================================
        print()
        print("-" * 70)
        print("STEP 4: Create new experiment with --temperature system-default")
        print("        (MODEL_TEMPERATURE should be null, NOT from .env)")
        print("-" * 70)

        # Note: --add-model in bcllm_model.py uses type=float for --temperature,
        # which rejects "system-default". However, --create-experiment in
        # bcllm_experiment.py uses type=nullable_float which DOES accept it.
        # This test uses the experiment creation path to validate system-default
        # behavior. The model parser gap is a separate finding (not this test's scope).

        result = _run_bcllm(
            args=[
                "--create-experiment", "smoke_test_sysdefault",
                "--temperature", "system-default",
                "--system-prompt", "from_cli_prompt",
            ],
            env_path=temp_env_path,
            db_path=temp_db_path,
        )

        if result.returncode != 0:
            results.record(
                "Step 4: --temperature system-default yields null",
                passed=False,
                detail=f"CLI exited with code {result.returncode}\nSTDERR: {result.stderr}",
            )
        else:
            conn = _get_db_connection(temp_db_path)
            try:
                exp = _get_experiment(conn, "smoke_test_sysdefault")
                if exp is None:
                    results.record(
                        "Step 4: --temperature system-default yields null",
                        passed=False,
                        detail="Experiment 'smoke_test_sysdefault' not found in database",
                    )
                else:
                    config = json.loads(exp["config_json"])
                    temp_val = config.get("MODEL_TEMPERATURE")

                    if temp_val is None:
                        results.record("Step 4: --temperature system-default yields null", passed=True)
                    else:
                        results.record(
                            "Step 4: --temperature system-default yields null",
                            passed=False,
                            detail=(
                                f"MODEL_TEMPERATURE should be null (system-default), got {temp_val!r}"
                            ),
                        )
            finally:
                conn.close()

    finally:
        # Cleanup
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)
        if os.path.exists(temp_env_path):
            os.unlink(temp_env_path)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run smoke tests and return exit code."""
    results = run_smoke_tests()

    print()
    print("=" * 70)
    if results.all_passed:
        print("ALL SMOKE TESTS PASSED")
        print("=" * 70)
        return 0
    else:
        failed = [r for r in results.results if not r["passed"]]
        print(f"SMOKE TESTS FAILED: {len(failed)} of {len(results.results)} steps failed")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
