# CLI System Architecture & Contracts

**Document Type:** Architecture Specification  
**Domain:** CLI System  
**Version:** 1.0  
**Date:** 2026-03-29  
**Status:** Authoritative  

---

## 1. CLI Philosophy

### 1.1 Core Principles

The V2 CLI system is built on these foundational principles:

1. **Explicit Over Implicit** — No hidden behavior, no magic
2. **Declarative Over Imperative** — Declare intent, don't script steps
3. **Modular Over Monolithic** — Small, focused modules
4. **Reproducible Over Fast** — Auditability > speed
5. **Null-Safe Over Convenient** — Explicit null semantics

### 1.2 Design Goals

| Goal | Description | Success Metric |
|------|-------------|----------------|
| **Clarity** | Every command's purpose is obvious | User can guess command without docs |
| **Consistency** | Same patterns across all commands | No special cases |
| **Composability** | Commands can be combined | Multi-step workflows work |
| **Idempotency** | Safe to repeat | Duplicate operations handled gracefully |
| **Auditability** | All actions traceable | Configuration hash, run logs |

---

## 2. Command Structure Contracts

### 2.1 Command Naming

**Pattern:** `--<action>-<entity>`

| Action | Entity | Example |
|--------|--------|---------|
| `create` | `experiment` | `--create-experiment <name>` |
| `add` | `model`, `run`, `questions` | `--add-model <model_id>` |
| `list` | `experiments`, `models`, `runs`, `questions` | `--list-experiments` |
| `remove` | `experiment`, `model`, `run`, `question` | `--remove-experiment <name>` |
| `show` | `experiment`, `run` | `--experiment <name>`, `--run <run_id>` |
| `execute` | (none) | `--execute` |
| `review` | `experiment`, `all` | `--review-experiment <name>` |

**Exceptions:**
- `--experiment <name>` (show experiment) — shorthand for `--show-experiment`
- `--run <run_id>` (show run) — shorthand for `--show-run`
- `--add-run` (create run) — uses "add" instead of "create" for consistency

### 2.2 Argument Patterns

**Required Arguments:**
```bash
--<command> <VALUE>
# Example: --create-experiment my_exp
```

**Optional Arguments:**
```bash
--<flag> <VALUE>
# Example: --seed 42
```

**Boolean Flags:**
```bash
--<flag>  # presence = true
# Example: --execute
```

**Repeatable Arguments:**
```bash
--<flag> <VALUE1> --<flag> <VALUE2>
# Example: --add-model model1 --add-model model2
```

**Array Arguments:**
```bash
--<flag> <VALUE1> <VALUE2> <VALUE3>
# Example: --questions Q001 Q002 Q003
```

### 2.3 Mutual Exclusivity

Commands that are mutually exclusive use `add_mutually_exclusive_group()`:

```python
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--create-experiment", metavar="NAME", ...)
group.add_argument("--experiment", metavar="NAME", ...)
group.add_argument("--list-experiments", action="store_true", ...)
group.add_argument("--remove-experiment", metavar="NAME", ...)
```

**Rule:** Only one command per invocation.

---

## 3. Argument Parsing Contracts

### 3.1 Type Converters

| Type | Converter | Behavior |
|------|-----------|----------|
| **String** | `str` (default) | Pass-through |
| **Integer** | `int` | Parse integer, error on invalid |
| **Float** | `float` | Parse float, error on invalid |
| **Nullable Int** | `nullable_int` | `"system-default"` → `None`, `"42"` → `42` |
| **Nullable Float** | `nullable_float` | `"system-default"` → `None`, `"0.5"` → `0.5` |
| **Custom** | Custom function | Validate and transform |

**Example:**
```python
parser.add_argument(
    "--max-reasoning",
    metavar="TOKENS",
    type=nullable_int,
    help="Max tokens for reasoning (model default)",
)
```

### 3.2 Custom Validators

**Reasoning Effort Validator:**
```python
def reasoning_effort_type(value: str) -> str:
    valid = {"xhigh", "high", "medium", "low", "minimal", "none"}
    if value.lower() not in valid:
        raise argparse.ArgumentTypeError(
            f"Invalid reasoning effort. Use one of: {', '.join(valid)}"
        )
    return value.lower()
```

**Model ID Validator:**
```python
from src.validators.model_id_validator import validate_model_id

if not validate_model_id(args.add_model):
    print(f"Error: Invalid model ID format: {args.add_model}", file=sys.stderr)
    print("Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)", file=sys.stderr)
    return 1
```

**Boolean Value Validator:**
```python
def _validate_bool_value(value: str) -> bool:
    if value is None:
        return True
    normalized = value.lower()
    return normalized in ('true', 'false', 'system-default')
```

### 3.3 Argument Normalization

**Pattern:** `parse_args_normalized()`

```python
from src.core.argv_utils import parse_args_normalized

args = parse_args_normalized(parser)
```

**Purpose:**
- Normalize `"system-default"` strings to `FORCE_SYSTEM_DEFAULT`
- Handle case-insensitive boolean values
- Apply consistent type conversion

---

## 4. Null Semantics Contract

### 4.1 FORCE_SYSTEM_DEFAULT Definition

```python
from src.core.null_semantics import FORCE_SYSTEM_DEFAULT

# Sentinel value
FORCE_SYSTEM_DEFAULT = object()
```

**Meaning:** User explicitly passed `"system-default"` to override .env defaults.

### 4.2 Normalization Rule

| CLI Input | Python Value | Resolution |
|-----------|--------------|------------|
| `--seed 42` | `42` | Use CLI value |
| `--seed system-default` | `FORCE_SYSTEM_DEFAULT` | Skip .env, use system default |
| `--seed` (not provided) | `None` | Check .env, then system default |

**Implementation:**
```python
from src.core.null_semantics import FORCE_SYSTEM_DEFAULT, normalize_system_default

add_questions_value = getattr(args, 'add_questions', None)

if add_questions_value is FORCE_SYSTEM_DEFAULT:
    # Explicitly system-default → use ALL questions (no .env fallback)
    selected_questions = questions
elif add_questions_value is not None:
    # User provided value → use it
    selected_questions = loader.parse_question_spec(add_questions_value, questions)
else:
    # Not specified → check .env
    default_questions = env_dict.get('DEFAULT_QUESTIONS')
    if default_questions:
        selected_questions = loader.parse_question_spec(default_questions, questions)
    else:
        selected_questions = questions
```

### 4.3 Mandatory Fields

**Fields that cannot accept `null`:**

| Field | Reason | Error Message |
|-------|--------|---------------|
| `--url` | Required for API calls | `Error: --url cannot be null` |
| `--dataset-path` | Required for questions | `Error: QUESTIONS_DATASET_PATH not set` |

**Validation:**
```python
if args.url is FORCE_SYSTEM_DEFAULT:
    print("Error: --url cannot be system-default", file=sys.stderr)
    return 1
```

### 4.4 Persistence Rule

**Rule:** `None` values serialized as JSON `null`, never string `"system-default"`.

```python
config_dict = {
    "seed": None,  # Serialized as null in JSON
    "temperature": 0.7,  # Serialized as 0.7
}

config_json = json.dumps(config_dict, indent=None, separators=(',', ':'))
# Result: {"seed":null,"temperature":0.7}
```

---

## 5. Configuration Hierarchy Contract

### 5.1 Resolution Order

```
┌─────────────────────────────────┐
│ CLI Arguments                   │ ← Highest precedence
│ (explicit user intent)          │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ Environment Variables (.env)    │ ← Project defaults
│ (team/project configuration)    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ NULL / System Defaults          │ ← Lowest precedence
│ (framework defaults)            │
└─────────────────────────────────┘
```

### 5.2 Resolution Timing

| Entity | Resolution Time | Immutability |
|--------|-----------------|--------------|
| **Experiment** | At creation | Immutable after creation |
| **Model Variant** | At creation | Immutable after creation |
| **Run** | At creation | Immutable after creation |
| **Execution** | At execution | Filters can vary |

### 5.3 Inheritance Rules

**Run Configuration:**
```
Run Configuration
    ├── Explicit run-level values (highest priority)
    ├── Experiment-level values (inherited)
    ├── .env values (inherited)
    └── System defaults (lowest priority)
```

**Model Variant Configuration:**
```
Variant Configuration
    ├── Explicit variant-level values (highest priority)
    ├── Experiment-level values (inherited)
    ├── .env values (inherited)
    └── Model defaults (lowest priority)
```

### 5.4 ConfigResolver Contract

**Interface:**
```python
from src.core.config_resolver import ConfigResolver

resolver = ConfigResolver()

# Load .env
env_dict = resolver.load_env()

# Build configuration dicts
experiment_config = resolver.build_experiment_config_dict(args)
model_config = resolver.build_model_config_dict(args, experiment)
run_config = resolver.build_run_config_dict(args, experiment)
```

**Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `load_env()` | Load .env file | `dict[str, str]` |
| `build_experiment_config_dict(args)` | Build experiment config | `dict[str, Any]` |
| `build_model_config_dict(args, experiment)` | Build model config | `dict[str, Any]` |
| `build_run_config_dict(args, experiment)` | Build run config | `dict[str, Any]` |

---

## 6. Error Communication Contract

### 6.1 Error Output Channel

**Rule:** All errors to `stderr`.

```python
print(f"Error: Experiment not found: {name}", file=sys.stderr)
```

**Rationale:**
- Separates error output from success output
- Script-friendly (can redirect stdout separately)
- Consistent with Unix conventions

### 6.2 Error Message Structure

**Pattern:**
```
Error: <specific description>
[Optional: Guidance on how to fix]
```

**Examples:**
```
Error: Experiment not found: my_exp
Error: Invalid model ID format: gpt-4
Expected: provider/model-name (e.g., openai/gpt-4, anthropic/claude-3)
Error: Invalid seed value: abc. Use AUTO, empty, or a number.
```

### 6.3 Error Categories

| Category | Exit Code | Output | Stack Trace |
|----------|-----------|--------|-------------|
| **Validation Error** | 1 | stderr | No |
| **System Error** | 1 | stderr + log | Yes (log only) |
| **User Interrupt** | 130 | stdout | No |

### 6.4 Guidance Inclusion Rules

**Include guidance when:**
- There's an obvious fix (invalid format, missing argument)
- The error is common (experiment not found)
- The correct syntax is non-obvious

**Do not include guidance when:**
- The error is self-explanatory (experiment already exists)
- The fix is obvious from context
- Multiple possible fixes exist

**Examples:**

| Error | Guidance | Rationale |
|-------|----------|-----------|
| `Invalid seed value: abc` | `Use AUTO, empty, or a number.` | Clear fix exists |
| `Experiment not found: my_exp` | (none) | User knows what to do |
| `Invalid model ID format` | `Expected: provider/model-name` | Format not obvious |

---

## 7. Help Text Standards

### 7.1 Help Text Structure

**Pattern:**
```python
parser = argparse.ArgumentParser(
    prog="bcllm",
    description="Benchmark LLM — Reproducible, experiment-driven LLM benchmarking",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  bcllm --create-experiment my_exp
  bcllm --experiment my_exp --add-model google/gemini-3.1-flash-lite-preview
  bcllm --experiment my_exp --add-questions 1-10
  bcllm --experiment my_exp --add-run
  bcllm --experiment my_exp --execute

Commands:
  Experiments: --create-experiment, --experiment, --list-experiments, --remove-experiment
  Models:      --add-model, --list-models, --remove-model
  Questions:   --add-questions, --list-questions, --remove-question
  Runs:        --create-run, --list-runs, --run, --remove-run
  Execution:   --execute
  Review:      --review-experiment, --review-all
    """,
)
```

### 7.2 Help Text Requirements

**Each module must include:**

1. **Description** — One-line purpose
2. **Examples** — At least 3 copy-paste examples
3. **Command List** — All commands in module
4. **Flag Descriptions** — All flags with valid values

**Example:**
```python
parser.add_argument(
    "--vision",
    type=str,
    metavar="VALUE",
    help="Enable vision. Valid values: true, false, null (case-insensitive). Default: false",
)
```

### 7.3 Example Quality

**Good Examples:**
- Copy-paste ready
- Show common use cases
- Include flag combinations
- Demonstrate null semantics

**Bad Examples:**
- Placeholder values (`<name>`, `<model_id>`)
- Incomplete commands
- Missing flag values

---

## 8. Module Contracts

### 8.1 Required Module Structure

**Every CLI module must have:**

```python
#!/usr/bin/env python3
"""Module description."""

import argparse
import sys

from src.core.mode import Mode
from src.cli.database import get_database_connection

def _validate_expected_mode(mode: Mode) -> None:
    """Validate mode."""
    VALID_MODES = [Mode.CREATE, Mode.MODIFY]
    if mode not in VALID_MODES:
        print(f"Error: Invalid mode", file=sys.stderr)
        sys.exit(1)

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(...)
    # Define arguments
    return parser

def handle_command(args, conn) -> int:
    """Handle command."""
    # Command logic
    return 0

def main(mode: Mode) -> int:
    """Main entry point."""
    _validate_expected_mode(mode)
    parser = create_parser()
    args = parser.parse_args()
    conn = get_database_connection()
    try:
        return handle_command(args, conn)
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
```

### 8.2 Mode Validation Contract

**Every module must validate mode:**

```python
def _validate_expected_mode(mode: Mode) -> None:
    VALID_MODES = [Mode.CREATE, Mode.MODIFY, Mode.INVALID]
    
    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"This indicates a dispatcher bug. Please report this issue.",
            file=sys.stderr
        )
        sys.exit(1)
```

**Mode Expectations by Module:**

| Module | Expected Modes |
|--------|----------------|
| `bcllm_main.py` | `INVALID` |
| `bcllm_experiment.py` | `CREATE`, `MODIFY`, `INVALID` |
| `bcllm_model.py` | `MODIFY`, `INVALID` |
| `bcllm_questions.py` | `MODIFY`, `INVALID` |
| `bcllm_run.py` | `MODIFY`, `EXECUTE`, `INVALID` |
| `bcllm_execute.py` | `EXECUTE` |
| `bcllm_review.py` | `INVALID` |

### 8.3 Database Connection Contract

**Every module must:**

1. Get connection via `get_database_connection()`
2. Use connection for repository operations
3. Close connection in `finally` block

```python
conn = get_database_connection()
try:
    # Use connection
    repo = SomeRepository(conn)
    result = repo.operation()
finally:
    conn.close()
```

---

## 9. Execution Flow Contract

### 9.1 Orchestration Pattern

**`bcllm_execute.py` pattern:**

```python
def handle_execute(args, conn) -> int:
    # Step 1: Validate experiment exists
    exp_repo = ExperimentRepository(conn)
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1
    
    # Step 2: Parse filters
    run_id = args.run
    question_ids = parse_question_ids(args.questions) if args.questions else None
    model_variant_ids = args.models if args.models else None
    
    # Step 3: Validate filters
    validation_errors = validate_filters(conn, experiment_id, run_id, question_ids, model_variant_ids)
    if validation_errors:
        for error in validation_errors:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    
    # Step 4: Build execution plan
    planner = Planner(conn)
    plan = planner.build_plan(
        args.experiment,
        run_ids=[run_id] if run_id else None,
        question_ids=question_ids,
        model_variant_ids=model_variant_ids,
    )
    
    # Step 5: Check if plan has work
    total_items = sum(len(run.items) for run in plan.runs)
    if not plan.runs or total_items == 0:
        print("No pending items to execute.", file=sys.stderr)
        return 0
    
    # Step 6: Execute plan
    engine = ExecutionEngine(api_client, randomizer, parser)
    results = engine.execute(plan)
    
    # Step 7: Write results
    writer = ResultWriter(conn)
    report = writer.write_results(results)
    
    # Step 8: Print summary
    print(f"✓ Execution completed")
    print(f"  Runs executed: {len(report.runs_updated)}")
    print(f"  Success: {report.responses_written}")
    print(f"  Failed: {report.errors_written}")
    
    return 0
```

### 9.2 Orchestration Constraints

**Orchestration modules must NOT:**
- Contain domain logic (retries in ExecutionEngine)
- Make inferences (explicit validation only)
- Mutate state directly (delegate to repositories)

**Domain logic belongs in:**
- `Planner` — Plan building
- `ExecutionEngine` — Execution, retries, error handling
- `ResultWriter` — Database writes

---

## 10. Repository Contract

### 10.1 Repository Interface

**Every repository must implement:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `save(entity)` | Create or update | `None` |
| `get_by_id(id)` | Get by ID | `Entity | None` |
| `get_by_name(name)` | Get by name | `Entity | None` |
| `list_all()` | List all | `list[Entity]` |
| `list_by_experiment(experiment_id)` | List by experiment | `list[Entity]` |
| `delete(id)` | Soft delete | `bool` |

### 10.2 Soft Delete Contract

**Rule:** Delete is soft delete (sets `deleted_at` or `is_active = false`).

```python
def delete(self, entity_id: str) -> bool:
    cursor = self.conn.cursor()
    cursor.execute(
        """
        UPDATE experiments
        SET deleted_at = CURRENT_TIMESTAMP
        WHERE experiment_id = ?
        """,
        (entity_id,),
    )
    self.conn.commit()
    return cursor.rowcount > 0
```

**Rationale:**
- Preserve historical data
- Enable audit trails
- Prevent accidental data loss

---

## 11. Exit Code Contract

### 11.1 Exit Code Definitions

| Exit Code | Meaning | When to Use |
|-----------|---------|-------------|
| `0` | Success | Operation completed successfully |
| `1` | Error | Validation error, system error |
| `130` | Interrupted | User pressed Ctrl+C |

### 11.2 Exit Code Pattern

```python
def main(mode: Mode) -> int:
    _validate_expected_mode(mode)
    parser = create_parser()
    args = parser.parse_args()
    
    conn = get_database_connection()
    try:
        if args.create_experiment:
            return handle_create_experiment(args, conn)
        elif args.experiment:
            return handle_show_experiment(args, conn)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.", file=sys.stderr)
        return 130
    finally:
        conn.close()
```

---

## 12. Summary

This document defines the **authoritative contracts** for the V2 CLI system:

1. **CLI Philosophy** — Explicit, declarative, modular
2. **Command Structure** — Consistent naming, argument patterns
3. **Argument Parsing** — Type converters, validators, normalization
4. **Null Semantics** — `FORCE_SYSTEM_DEFAULT`, resolution rules
5. **Configuration Hierarchy** — CLI > .env > NULL
6. **Error Communication** — stderr, structure, guidance
7. **Help Text** — Examples, descriptions, flag docs
8. **Module Contracts** — Required structure, mode validation
9. **Execution Flow** — Orchestration pattern, constraints
10. **Repository Contract** — Interface, soft delete
11. **Exit Codes** — Success, error, interrupt

All CLI modules must adhere to these contracts for consistency and maintainability.

---

**Next Document:** `docs/architecture/v2-adaptation/03-cli-system-adaptation.md` — V2 Adaptation Plan
