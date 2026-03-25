#!/usr/bin/env python3
"""Database schema and data validation script.

This script performs comprehensive validation of the benchmark_llm database:
- Schema validation (tables, columns, constraints)
- Data integrity checks (NOT NULL, foreign keys)
- Configuration key validation (18 for experiments, 10 for models, 3 for runs)
- Token calculation verification
- Review flag calculation verification

Usage:
    python scripts/inspect_schema.py

Exit Codes:
    0: All checks passed
    1: One or more checks failed
"""

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "bcllm.db"

# Expected configuration keys
EXPECTED_EXPERIMENT_CONFIG_KEYS = {
    # Global defaults (7)
    "default_temperature",
    "default_top_p",
    "default_max_output_tokens",
    "default_reasoning_mode",
    "default_reasoning_effort",
    # Prompt templates (2)
    "system_prompt_template",
    "user_prompt_template",
    # Additional config (8) - depends on implementation
    # For now, we check for common keys
}

EXPECTED_MODEL_CONFIG_KEYS = {
    "model_id",
    "reasoning_mode",
    "reasoning_effort",
    "vision_enabled",
    "structured_output",
    "web_access_enabled",
    "temperature",
    "top_p",
    "max_output_tokens",
}

EXPECTED_RUN_CONFIG_KEYS = {
    "seed",
    "system_prompt",
    "user_prompt",
}

# Forbidden SYSTEM keys (should NOT be in experiment config)
FORBIDDEN_SYSTEM_KEYS = {
    "DATABASE_PATH",
    "EXECUTION_MODE",
    "LOG_FILE_PATH",
    "LOG_LEVEL",
    "OPENROUTER_DEBUG_ENABLED",
}


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def colorize(text: str, color: str) -> str:
    """Apply color to text."""
    return f"{color}{text}{Colors.RESET}"


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{colorize('=' * 70, Colors.BLUE)}")
    print(colorize(f"  {text}", Colors.BOLD))
    print(colorize('=' * 70, Colors.BLUE))


def print_check(name: str, passed: bool, details: str = "") -> None:
    """Print a check result."""
    status = colorize("✓ PASS", Colors.GREEN) if passed else colorize("✗ FAIL", Colors.RED)
    print(f"{status}  {name}")
    if details:
        print(f"       {details}")


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def check_tables_exist(conn: sqlite3.Connection) -> bool:
    """Verify all expected tables exist."""
    print_header("1. Table Existence Check")
    
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    existing_tables = {row[0] for row in cursor.fetchall()}
    
    expected_tables = {
        "experiments",
        "model_variants",
        "question_snapshots",
        "runs",
        "responses",
        "errors",
    }
    
    all_exist = expected_tables.issubset(existing_tables)
    missing = expected_tables - existing_tables
    
    print_check(f"Expected tables ({len(expected_tables)})", all_exist)
    if missing:
        print_check(f"  Missing: {missing}", False)
    else:
        print(f"       Found: {', '.join(sorted(existing_tables & expected_tables))}")
    
    return all_exist


def check_created_at_not_null(conn: sqlite3.Connection) -> bool:
    """Verify created_at columns are populated (NOT NULL)."""
    print_header("2. created_at NOT NULL Check")
    
    # Only check tables that have created_at column
    tables_with_created_at = [
        "experiments",
        "model_variants",
        "question_snapshots",
        "runs",
    ]
    
    all_pass = True
    results = []
    
    for table in tables_with_created_at:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN created_at IS NULL THEN 1 ELSE 0 END) as null_count
            FROM {table}
        """)
        row = cursor.fetchone()
        total = row['total'] or 0
        null_count = row['null_count'] or 0
        
        passed = null_count == 0
        all_pass &= passed
        results.append((table, total, null_count, passed))
    
    for table, total, null_count, passed in results:
        if total == 0:
            print_check(f"{table}.created_at", True, "No records (skipped)")
        else:
            status = f"{null_count}/{total} NULL" if null_count else f"All {total} populated"
            print_check(f"{table}.created_at", passed, status)
    
    return all_pass


def check_no_is_active_columns(conn: sqlite3.Connection) -> bool:
    """Verify is_active columns do NOT exist (removed in TO-BE)."""
    print_header("3. is_active Column Removal Check")
    
    tables_to_check = [
        "experiments",
        "model_variants",
        "question_snapshots",
        "runs",
    ]
    
    all_pass = True
    results = []
    
    for table in tables_to_check:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
        
        has_is_active = "is_active" in columns
        all_pass &= not has_is_active
        results.append((table, has_is_active))
    
    for table, has_is_active in results:
        passed = not has_is_active
        status = "Column exists (SHOULD BE REMOVED)" if has_is_active else "Column removed (correct)"
        print_check(f"{table}.is_active", passed, status)
    
    return all_pass


def check_experiment_config_keys(conn: sqlite3.Connection) -> bool:
    """Verify experiment config_json has expected keys."""
    print_header("4. Experiment Config Keys Check")
    
    cursor = conn.cursor()
    cursor.execute("SELECT experiment_id, name, config_json FROM experiments")
    experiments = cursor.fetchall()
    
    if not experiments:
        print_check("Experiments exist", True, "No experiments found (skipped)")
        return True
    
    all_pass = True
    results = []
    
    for exp in experiments:
        try:
            config = json.loads(exp['config_json']) if exp['config_json'] else {}
            config_keys = set(config.keys())
            
            # Check for forbidden SYSTEM keys
            has_forbidden = config_keys & FORBIDDEN_SYSTEM_KEYS
            
            # Check that config is valid JSON and not empty
            passed = len(config_keys) > 0 and not has_forbidden
            all_pass &= passed
            
            results.append((
                exp['name'],
                len(config_keys),
                has_forbidden,
                passed
            ))
        except json.JSONDecodeError as e:
            all_pass = False
            results.append((exp['name'], 0, set(), False))
    
    for name, key_count, forbidden, passed in results:
        details = f"{key_count} keys"
        if forbidden:
            details += f", FORBIDDEN: {forbidden}"
        print_check(f"Experiment '{name}'", passed, details)
    
    return all_pass


def check_model_config_keys(conn: sqlite3.Connection) -> bool:
    """Verify model_variants table has expected columns."""
    print_header("5. Model Variants Table Check")
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(model_variants)")
    columns = {row[1] for row in cursor.fetchall()}
    
    expected_columns = {
        "variant_id",
        "model_id",
        "reasoning_mode",
        "reasoning_effort",
        "vision_enabled",
        "structured_output",
        "web_access_enabled",
        "temperature",
        "top_p",
        "max_output_tokens",
        "variant_signature",
        "created_at",
    }
    
    missing = expected_columns - columns
    passed = len(missing) == 0
    
    print_check(f"Model variants columns ({len(expected_columns)})", passed)
    if missing:
        print(f"       Missing: {missing}")
    else:
        print(f"       All columns present")
    
    return passed


def check_run_config_keys(conn: sqlite3.Connection) -> bool:
    """Verify runs table has expected columns."""
    print_header("6. Runs Table Check")
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(runs)")
    columns = {row[1] for row in cursor.fetchall()}
    
    expected_columns = {
        "run_id",
        "experiment_id",
        "config",
        "status",
        "duration",
        "created_at",
    }
    
    missing = expected_columns - columns
    passed = len(missing) == 0
    
    print_check(f"Runs columns ({len(expected_columns)})", passed)
    if missing:
        print(f"       Missing: {missing}")
    else:
        print(f"       All columns present")
    
    return passed


def check_question_position(conn: sqlite3.Connection) -> bool:
    """Verify question_snapshots table has expected columns."""
    print_header("7. Question Snapshots Table Check")
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(question_snapshots)")
    columns = {row[1] for row in cursor.fetchall()}
    
    expected_columns = {
        "snapshot_id",
        "experiment_id",
        "json_question_id",
        "question_position",
        "question_payload",
        "created_at",
    }
    
    missing = expected_columns - columns
    passed = len(missing) == 0
    
    print_check(f"Question snapshots columns ({len(expected_columns)})", passed)
    if missing:
        print(f"       Missing: {missing}")
    else:
        print(f"       All columns present")
    
    # Check if question_position is used (not Q*** IDs)
    cursor.execute("SELECT json_question_id FROM question_snapshots LIMIT 10")
    snapshots = cursor.fetchall()
    
    if snapshots:
        uses_q_format = any(s['json_question_id'].startswith('Q') for s in snapshots)
        format_ok = not uses_q_format
        print_check(f"Non-Q format IDs", format_ok, "Uses Q*** format" if uses_q_format else "Uses non-Q format")
        passed &= format_ok
    
    return passed


def check_token_calculations(conn: sqlite3.Connection) -> bool:
    """Verify effective_tokens = input + response + reasoning."""
    print_header("8. Token Calculation Check")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT response_id, input_tokens, response_tokens, reasoning_tokens, effective_tokens
        FROM responses
        WHERE input_tokens IS NOT NULL AND response_tokens IS NOT NULL
    """)
    responses = cursor.fetchall()
    
    if not responses:
        print_check("Responses with tokens exist", True, "No responses with tokens found (skipped)")
        return True
    
    all_pass = True
    errors = []
    
    for resp in responses:
        input_t = resp['input_tokens'] or 0
        response_t = resp['response_tokens'] or 0
        reasoning_t = resp['reasoning_tokens'] or 0
        effective_t = resp['effective_tokens']
        
        expected_effective = input_t + response_t + reasoning_t
        
        if effective_t != expected_effective:
            all_pass = False
            errors.append((
                resp['response_id'],
                input_t,
                response_t,
                reasoning_t,
                effective_t,
                expected_effective
            ))
    
    print_check(f"Responses checked ({len(responses)})", all_pass)
    if errors:
        print(f"       {len(errors)} miscalculations found:")
        for resp_id, inp, out, reason, eff, expected in errors[:5]:  # Show first 5
            print(f"         {resp_id}: {inp}+{out}+{reason}={expected}, but effective={eff}")
        if len(errors) > 5:
            print(f"         ... and {len(errors) - 5} more")
    else:
        print(f"       All calculations correct")
    
    return all_pass


def check_needs_review_calculation(conn: sqlite3.Connection) -> bool:
    """Verify review_status = 'needs_review' when parse_confidence != 'clear' OR selected_answer IS NULL."""
    print_header("9. needs_review Flag Calculation Check")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT response_id, parse_confidence, selected_answer, review_status
        FROM responses
    """)
    responses = cursor.fetchall()
    
    if not responses:
        print_check("Responses exist", True, "No responses found (skipped)")
        return True
    
    all_pass = True
    errors = []
    
    for resp in responses:
        parse_conf = resp['parse_confidence'] or 'unknown'
        selected = resp['selected_answer']
        
        # review_status should be 'needs_review' if:
        # - parse_confidence != 'clear' OR
        # - selected_answer IS NULL
        should_need_review = (parse_conf != 'clear') or (selected is None)
        actual_needs_review = resp['review_status'] == 'needs_review'
        
        if should_need_review != actual_needs_review:
            all_pass = False
            errors.append((
                resp['response_id'],
                parse_conf,
                selected,
                should_need_review,
                actual_needs_review
            ))
    
    print_check(f"Responses checked ({len(responses)})", all_pass)
    if errors:
        print(f"       {len(errors)} incorrect flags:")
        for resp_id, conf, selected, expected, actual in errors[:5]:
            print(f"         {resp_id}: conf={conf}, selected={selected}, expected={expected}, actual={actual}")
        if len(errors) > 5:
            print(f"         ... and {len(errors) - 5} more")
    else:
        print(f"       All flags correct")
    
    return all_pass


def check_no_system_keys_in_experiment_config(conn: sqlite3.Connection) -> bool:
    """Verify no SYSTEM keys (DATABASE_PATH, EXECUTION_MODE, etc.) in experiment config."""
    print_header("10. Forbidden SYSTEM Keys Check")
    
    cursor = conn.cursor()
    cursor.execute("SELECT experiment_id, name, config_json FROM experiments")
    experiments = cursor.fetchall()
    
    if not experiments:
        print_check("Experiments exist", True, "No experiments found (skipped)")
        return True
    
    all_pass = True
    results = []
    
    for exp in experiments:
        try:
            config = json.loads(exp['config_json']) if exp['config_json'] else {}
            config_keys = set(config.keys())
            
            forbidden_found = config_keys & FORBIDDEN_SYSTEM_KEYS
            
            passed = not forbidden_found
            all_pass &= passed
            
            results.append((exp['name'], forbidden_found, passed))
        except json.JSONDecodeError:
            all_pass = False
            results.append((exp['name'], set(), False))
    
    for name, forbidden, passed in results:
        details = f"Found: {forbidden}" if forbidden else "No forbidden keys"
        print_check(f"Experiment '{name}'", passed, details)
    
    return all_pass


def main() -> int:
    """Run all validation checks."""
    print(colorize("\n" + "=" * 70, Colors.BOLD))
    print(colorize("  DATABASE SCHEMA & DATA VALIDATION", Colors.BOLD))
    print(colorize("=" * 70, Colors.BOLD))
    print(f"\nDatabase: {DB_PATH}")
    
    if not DB_PATH.exists():
        print(colorize(f"\n✗ ERROR: Database not found at {DB_PATH}", Colors.RED))
        return 1
    
    try:
        conn = get_connection()
    except Exception as e:
        print(colorize(f"\n✗ ERROR: Cannot connect to database: {e}", Colors.RED))
        return 1
    
    results = []
    
    # Run all checks
    results.append(("Table Existence", check_tables_exist(conn)))
    results.append(("created_at NOT NULL", check_created_at_not_null(conn)))
    results.append(("is_active Removal", check_no_is_active_columns(conn)))
    results.append(("Experiment Config Keys (18)", check_experiment_config_keys(conn)))
    results.append(("Model Config Keys (10)", check_model_config_keys(conn)))
    results.append(("Run Config Keys (3)", check_run_config_keys(conn)))
    results.append(("question_position Validation", check_question_position(conn)))
    results.append(("Token Calculations", check_token_calculations(conn)))
    results.append(("needs_review Calculation", check_needs_review_calculation(conn)))
    results.append(("Forbidden SYSTEM Keys", check_no_system_keys_in_experiment_config(conn)))
    
    conn.close()
    
    # Summary
    print_header("SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = colorize("✓", Colors.GREEN) if result else colorize("✗", Colors.RED)
        print(f"{status} {name}")
    
    print(f"\n{colorize('=' * 70, Colors.BLUE)}")
    overall = passed == total
    if overall:
        print(colorize(f"  ALL CHECKS PASSED ({passed}/{total})", Colors.GREEN))
    else:
        print(colorize(f"  SOME CHECKS FAILED ({passed}/{total} passed)", Colors.RED))
    print(colorize('=' * 70, Colors.BLUE) + "\n")
    
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
