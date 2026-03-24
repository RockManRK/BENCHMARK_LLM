#!/usr/bin/env python3
"""Checkpoint B validation workflows.

This script executes 3 real validation workflows to verify:
1. Auto-snapshot creation (no --add-questions)
2. Specific range selection (--add-questions 1-10)
3. Invalid dataset path failure (fail loudly)

Each workflow runs in a separate Python subprocess with clean environment.

Usage:
    python tests/validation/checkpoint_b_workflows.py

Exit Codes:
    0: All workflows passed
    1: One or more workflows failed
"""

import sqlite3
import json
import subprocess
import sys
import os
import shutil
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add project root to sys.path for imports
sys.path.insert(0, str(PROJECT_ROOT))

# The CLI uses hardcoded path: ./data/bcllm.db
DB_PATH = PROJECT_ROOT / "data" / "bcllm.db"
DB_BACKUP_PATH = PROJECT_ROOT / "data" / "bcllm.db.backup"
BCLLM_SCRIPT = PROJECT_ROOT / "bcllm.py"
ENV_FILE = PROJECT_ROOT / ".env"


def run_command(cmd: str, cwd: Path = PROJECT_ROOT, env: dict = None) -> tuple[int, str, str]:
    """Run shell command and return (exit_code, stdout, stderr).

    Args:
        cmd: Command to execute.
        cwd: Working directory.
        env: Environment variables (if None, uses clean environment).
    """
    # Start with a clean environment that only has essential variables
    if env is None:
        run_env = {
            'PATH': os.environ.get('PATH', ''),
            'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
            'PYTHONPATH': str(PROJECT_ROOT),
        }
    else:
        run_env = os.environ.copy()
        run_env.update(env)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, env=run_env)
    return result.returncode, result.stdout, result.stderr


def query_db(query: str) -> list[dict]:
    """Query database and return results as dicts."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def reset_database() -> bool:
    """Drop and recreate database to ensure clean state.

    Returns:
        True if successful, False otherwise.
    """
    print("=" * 60)
    print("Pre-check: Creating fresh database")
    print("=" * 60)

    try:
        from src_v2.db.schema import create_schema, drop_all_tables

        # Backup existing database if it exists
        if DB_PATH.exists():
            shutil.copy2(str(DB_PATH), str(DB_BACKUP_PATH))
            print(f"  📦 Backed up existing database to {DB_BACKUP_PATH.name}")

        conn = sqlite3.connect(str(DB_PATH))
        drop_all_tables(conn)
        create_schema(conn)
        conn.close()
        print(f"  ✅ Database reset at {DB_PATH.name}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to reset database: {e}")
        return False


def restore_database() -> bool:
    """Restore database from backup."""
    try:
        if DB_BACKUP_PATH.exists():
            shutil.copy2(str(DB_BACKUP_PATH), str(DB_PATH))
            return True
    except Exception:
        pass
    return False


def cleanup_database():
    """Clean up - remove backup."""
    try:
        if DB_BACKUP_PATH.exists():
            DB_BACKUP_PATH.unlink()
    except Exception:
        pass


def backup_env() -> str:
    """Backup current .env file content."""
    if ENV_FILE.exists():
        return ENV_FILE.read_text(encoding='utf-8')
    return ""


def restore_env(content: str) -> None:
    """Restore .env file content."""
    ENV_FILE.write_text(content, encoding='utf-8')


def write_env_file(questions_path: str = None) -> str:
    """Write .env file with specific configuration and return content.

    Args:
        questions_path: Custom QUESTIONS_DATASET_PATH value

    Returns:
        The .env file content.
    """
    if questions_path is None:
        questions_path = r".\data\enamed_questions.json"

    content = f"""# System
EXECUTION_MODE=dev
OPENROUTER_DEBUG_ENABLED=true

# OpenRouter API Configuration
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Database Configuration
DATABASE_PATH=./data/benchmark.db

# Logging Configuration
LOG_LEVEL=DEBUG
LOG_FILE_PATH=./logs/benchmark.log

# Test Configuration
DEFAULT_ITERATIONS=1
DEFAULT_MODELS=

# Randomization Seed
RANDOM_SEED=AUTO

# Model Generation Parameters
MODEL_MAX_TOKENS=
MODEL_TEMPERATURE=
MODEL_TOP_P=
MODEL_TOP_K=
MODEL_REPEAT_PENALTY=

# Structured Outputs
USE_STRUCTURED_OUTPUTS=false

# Vision Support
ENABLE_VISION=true

# Prompt Templates
SYSTEM_PROMPT_TEMPLATE=
USER_PROMPT_TEMPLATE=

# Reasoning Tokens
REASONING_EFFORT=
REASONING_MAX_TOKENS=
REASONING_EXCLUDE=
REASONING_ENABLED=

DEFAULT_QUESTIONS=

# Question Dataset Path
QUESTIONS_DATASET_PATH={questions_path}
"""
    ENV_FILE.write_text(content, encoding='utf-8')
    return content


def validate_workflow_1() -> bool:
    """Workflow 1: Auto-snapshots (no --add-questions).

    Expected:
    - All questions from dataset snapshotted (10 in sample dataset)
    - Payload contains: stem, options, answer_key, meta, internal_id, source_id
    - No placeholder text (e.g., no "Question Q001 stem")
    - Different answer_key values across questions
    """
    print("=" * 60)
    print("Workflow 1: Auto-snapshots (no --add-questions)")
    print("=" * 60)

    # Write fresh .env with valid dataset path
    write_env_file(r".\data\enamed_questions.json")

    # Create experiment without --add-questions
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --create-experiment val_auto_snap')
    if code != 0:
        print(f"  ❌ Failed to create experiment: {err}")
        return False

    # Query snapshot count
    results = query_db("""
        SELECT COUNT(*) as count 
        FROM question_snapshots 
        WHERE experiment_id=(SELECT experiment_id FROM experiments WHERE name='val_auto_snap')
    """)
    count = results[0]['count']
    print(f"  Snapshot count: {count}")

    if count == 0:
        print("  ❌ No snapshots created")
        return False

    # Expected: 10 snapshots (sample dataset has 10 questions)
    if count != 10:
        print(f"  ⚠️  Expected 10 snapshots, got {count} (may be OK if dataset differs)")

    # Verify payload structure
    results = query_db("""
        SELECT question_payload 
        FROM question_snapshots 
        WHERE experiment_id=(SELECT experiment_id FROM experiments WHERE name='val_auto_snap')
        LIMIT 1
    """)
    payload = json.loads(results[0]['question_payload'])

    required_fields = ['stem', 'options', 'answer_key', 'meta', 'internal_id', 'source_id']
    missing = [f for f in required_fields if f not in payload]
    if missing:
        print(f"  ❌ Missing fields: {missing}")
        return False

    # Check for placeholder text
    if 'Question Q' in payload.get('stem', ''):
        print("  ❌ Placeholder text detected in stem")
        return False

    # Verify answer_key variation (not all the same)
    results = query_db("""
        SELECT DISTINCT json_extract(question_payload, '$.answer_key') as answer_key
        FROM question_snapshots 
        WHERE experiment_id=(SELECT experiment_id FROM experiments WHERE name='val_auto_snap')
    """)
    answer_keys = [r['answer_key'] for r in results]
    if len(answer_keys) == 1 and count > 1:
        print(f"  ❌ All questions have same answer_key: {answer_keys[0]} (placeholder data)")
        return False

    print(f"  Payload fields: {list(payload.keys())}")
    print(f"  Answer key variation: {len(answer_keys)} unique values")
    print("  ✅ Workflow 1 passed")
    return True


def validate_workflow_2() -> bool:
    """Workflow 2: Specific range (--add-questions 1-10).

    Expected:
    - Exactly 10 snapshots created
    - Internal IDs 1-10 snapshotted
    """
    print("=" * 60)
    print("Workflow 2: Specific range (--add-questions 1-10)")
    print("=" * 60)

    # Write fresh .env with valid dataset path
    write_env_file(r".\data\enamed_questions.json")

    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --create-experiment val_range --add-questions 1-10')
    if code != 0:
        print(f"  ❌ Failed to create experiment: {err}")
        return False

    results = query_db("""
        SELECT COUNT(*) as count 
        FROM question_snapshots 
        WHERE experiment_id=(SELECT experiment_id FROM experiments WHERE name='val_range')
    """)
    count = results[0]['count']
    print(f"  Snapshot count: {count}")

    if count != 10:
        print(f"  ❌ Expected 10 snapshots, got {count}")
        return False

    # Verify internal IDs are 1-10
    results = query_db("""
        SELECT json_extract(question_payload, '$.internal_id') as internal_id
        FROM question_snapshots 
        WHERE experiment_id=(SELECT experiment_id FROM experiments WHERE name='val_range')
        ORDER BY internal_id
    """)
    internal_ids = [r['internal_id'] for r in results]
    expected_ids = list(range(1, 11))

    if internal_ids != expected_ids:
        print(f"  ❌ Expected internal IDs {expected_ids}, got {internal_ids}")
        return False

    print(f"  Internal IDs: {internal_ids}")
    print("  ✅ Workflow 2 passed")
    return True


def validate_workflow_3() -> bool:
    """Workflow 3: Invalid dataset path (fail loudly).

    Expected:
    - Exit code = 1 (failure)
    - Error message printed
    - Experiment NOT created (or created without snapshots if experiment creation succeeds but snapshot creation fails)
    """
    print("=" * 60)
    print("Workflow 3: Invalid dataset path (fail loudly)")
    print("=" * 60)

    # Write .env with invalid path
    write_env_file(r".\data\nonexistent.json")

    # Try to create experiment
    code, out, err = run_command(f'python "{BCLLM_SCRIPT}" --create-experiment val_invalid 2>&1')

    print(f"  Exit code: {code} (expected non-zero)")

    # Combined output for error message check
    combined_output = out + err
    print(f"  Error message: {combined_output.strip()[:200]}...")

    if code == 0:
        print("  ❌ Expected non-zero exit code, got 0")
        return False

    # Check for meaningful error message
    if not any(keyword in combined_output.lower() for keyword in ['error', 'not found', 'file', 'dataset']):
        print("  ⚠️  Warning: Error message may not be descriptive")

    # Verify experiment was NOT created or has no snapshots
    results = query_db("""
        SELECT COUNT(*) as count 
        FROM question_snapshots 
        WHERE experiment_id=(SELECT experiment_id FROM experiments WHERE name='val_invalid')
    """)
    if results:
        count = results[0]['count']
        if count > 0:
            print(f"  ❌ Experiment created with {count} snapshots despite invalid dataset")
            return False
        print(f"  ✓ Experiment created but no snapshots (acceptable behavior)")

    print("  ✅ Workflow 3 passed")
    return True


def main() -> int:
    """Run all validation workflows."""
    print("\n" + "=" * 60)
    print("CHECKPOINT B: VALIDATION WORKFLOWS")
    print("=" * 60 + "\n")

    # Backup current .env
    env_backup = backup_env()

    try:
        # Reset database
        if not reset_database():
            print("\n❌ Database reset failed. Aborting.")
            return 1

        all_pass = True
        all_pass &= validate_workflow_1()
        all_pass &= validate_workflow_2()
        all_pass &= validate_workflow_3()

        print("\n" + "=" * 60)
        if all_pass:
            print("✅ All workflows passed")
            print("=" * 60)
            return 0
        else:
            print("❌ Some workflows failed")
            print("=" * 60)
            return 1

    finally:
        # Restore .env
        restore_env(env_backup)
        print("\n.env restored to original state")

        # Restore database
        restore_database()
        cleanup_database()
        print("Database restored to original state")


if __name__ == "__main__":
    sys.exit(main())
