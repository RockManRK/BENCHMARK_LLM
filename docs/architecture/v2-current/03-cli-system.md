# V2 CLI System — Current State

**Document Type:** Current State Analysis  
**Domain:** CLI System  
**Version:** 1.0  
**Date:** 2026-03-29  
**Status:** Living Document  

---

## 1. Overview

The V2 CLI system represents a **modular, distributed architecture** where each command domain has its own entry point module. This contrasts sharply with V1's monolithic `main.py` approach, embracing the Unix philosophy of small, focused tools.

### 1.1 Key Characteristics

- **Modular Entry Points:** One file per command domain (`bcllm_experiment.py`, `bcllm_model.py`, etc.)
- **Dispatcher Pattern:** `bcllm_main.py` routes to appropriate module based on command
- **Explicit Null Semantics:** `EXPLICIT_NULL` constant for distinguishing "not set" from "explicitly null"
- **Configuration Hierarchy:** CLI > .env > system defaults with `ConfigResolver`
- **Mode-Based Execution:** `Mode.CREATE`, `Mode.MODIFY`, `Mode.EXECUTE`, `Mode.INVALID`

### 1.2 Command Structure

```
bcllm --<command> [arguments]

# Examples:
bcllm --create-experiment my_exp
bcllm --experiment my_exp --add-model google/gemini-3.1-flash-lite-preview
bcllm --experiment my_exp --add-questions 1-10
bcllm --experiment my_exp --add-run
bcllm --experiment my_exp --execute
```

---

## 2. Architecture

### 2.1 Component Structure

```
src/cli/
├── bcllm_main.py           # Dispatcher/help entry point
├── bcllm_experiment.py     # Experiment lifecycle (CREATE, MODIFY)
├── bcllm_model.py          # Model variant management (MODIFY)
├── bcllm_questions.py      # Question snapshot management (MODIFY)
├── bcllm_run.py            # Run lifecycle management (MODIFY, EXECUTE)
├── bcllm_execute.py        # Execution orchestration (EXECUTE)
├── bcllm_review.py         # Manual review interface (INVALID)
└── database.py             # Persistent database connection utility
```

### 2.2 Execution Flow

```
User Input: bcllm --create-experiment my_exp
    ↓
bcllm_main.py (dispatcher)
    ↓
Mode validation → Mode.CREATE
    ↓
Module dispatch → bcllm_experiment.py
    ↓
Mode validation in module → _validate_expected_mode(Mode.CREATE)
    ↓
Command handler → handle_create_experiment(args, conn)
    ↓
Database operations via repositories
    ↓
Console output (print statements)
```

### 2.3 Mode System

V2 uses a **mode-based routing system** defined in `src/core/mode.py`:

```python
class Mode(Enum):
    CREATE = "create"     # Creation operations
    MODIFY = "modify"     # Modification operations
    EXECUTE = "execute"   # Execution operations
    INVALID = "invalid"   # Invalid/standalone operations
```

**Module Mode Expectations:**

| Module | Expected Modes | Purpose |
|--------|----------------|---------|
| `bcllm_main.py` | `INVALID` | Dispatcher/help only |
| `bcllm_experiment.py` | `CREATE`, `MODIFY`, `INVALID` | Experiment CRUD |
| `bcllm_model.py` | `MODIFY`, `INVALID` | Model variant management |
| `bcllm_questions.py` | `MODIFY`, `INVALID` | Question snapshots |
| `bcllm_run.py` | `MODIFY`, `EXECUTE`, `INVALID` | Run lifecycle |
| `bcllm_execute.py` | `EXECUTE` | Execution orchestration |
| `bcllm_review.py` | `INVALID` | Manual review |

**Mode Validation Pattern:**
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

---

## 3. Modular CLI Paradigm

### 3.1 One File Per Command

Each V2 CLI module is **self-contained** with:

1. **Own argument parser** — `create_parser()` function
2. **Own command handlers** — `handle_*` functions
3. **Own mode validation** — `_validate_expected_mode()` function
4. **Own entry point** — `main(mode: Mode) -> int` function

**Example Module Structure:**
```python
#!/usr/bin/env python3
"""Module description."""

import argparse
import sys

from src.core.mode import Mode
from src.cli.database import get_database_connection

def _validate_expected_mode(mode: Mode) -> None:
    VALID_MODES = [Mode.CREATE, Mode.MODIFY]
    if mode not in VALID_MODES:
        print(f"Error: Invalid mode", file=sys.stderr)
        sys.exit(1)

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(...)
    # Define arguments
    return parser

def handle_command(args, conn) -> int:
    # Command logic
    return 0

def main(mode: Mode) -> int:
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

### 3.2 Dispatcher Pattern

`bcllm_main.py` serves as a **help dispatcher**:

```python
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bcllm",
        description="Benchmark LLM — Reproducible, experiment-driven LLM benchmarking",
        epilog="""
Commands:
  Experiments: --create-experiment, --experiment, --list-experiments, --remove-experiment
  Models:      --add-model, --list-models, --remove-model
  Questions:   --add-questions, --list-questions, --remove-question
  Runs:        --create-run, --list-runs, --run, --remove-run
  Execution:   --execute
  Review:      --review-experiment, --review-all
        """,
    )
    # Arguments defined for help display only
    return parser
```

**Note:** The actual dispatch mechanism (how `bcllm --create-experiment` invokes `bcllm_experiment.py`) is implemented outside these modules (likely in a wrapper script or entry point configuration).

---

## 4. Argument Parsing with Null Semantics

### 4.1 EXPLICIT_NULL Constant

V2 introduces **explicit null semantics** via `src/core/null_semantics.py`:

```python
EXPLICIT_NULL = object()  # Sentinel value

def normalize_nulls(value: str | None) -> str | None | type(EXPLICIT_NULL):
    """Normalize CLI null values.
    
    - "null" (case-insensitive) → EXPLICIT_NULL
    - None (not provided) → None
    - Any other string → string value
    """
    if value is None:
        return None
    if value.lower() == "null":
        return EXPLICIT_NULL
    return value
```

**Purpose:** Distinguish between:
- `--seed` not provided → `None` → use .env or default
- `--seed null` explicitly → `EXPLICIT_NULL` → force system default (skip .env)

### 4.2 Nullable Type Converters

Custom type converters for nullable arguments:

```python
from src.core.null_semantics import nullable_int, nullable_float

parser.add_argument(
    "--max-reasoning",
    metavar="TOKENS",
    type=nullable_int,
    help="Max tokens for reasoning (model default)",
)

parser.add_argument(
    "--temperature",
    metavar="VALUE",
    type=nullable_float,
    help="Temperature (model default)",
)
```

**Behavior:**
- `--max-reasoning 1000` → `1000`
- `--max-reasoning null` → `None` (use model default)
- `--max-reasoning` (not provided) → `None` (use .env or model default)

### 4.3 Boolean Value Validation

Boolean CLI arguments accept `true`, `false`, or `null`:

```python
def _validate_bool_value(value: str) -> bool:
    if value is None:
        return True
    normalized = value.lower()
    return normalized in ('true', 'false', 'null')

# Usage:
parser.add_argument(
    "--vision",
    type=str,
    metavar="VALUE",
    help="Enable vision. Valid values: true, false, null (case-insensitive). Default: false",
)
```

**Valid Values:**
- `--vision true` → vision enabled
- `--vision false` → vision disabled
- `--vision null` → use system default
- `--vision TRUE`, `--vision False`, `--vision NULL` → case-insensitive

---

## 5. Configuration Hierarchy Integration

### 5.1 ConfigResolver Class

V2 uses `ConfigResolver` from `src/core/config_resolver.py`:

```python
from src.core.config_resolver import ConfigResolver

resolver = ConfigResolver()
env_dict = resolver.load_env()

# Build configuration from CLI > .env > NULL
config_dict = resolver.build_experiment_config_dict(args)
config_dict = resolver.build_model_config_dict(args, experiment)
config_dict = resolver.build_run_config_dict(args, experiment)
```

### 5.2 Hierarchy Resolution

**Three-Tier Hierarchy:**

```
CLI Arguments (highest precedence)
    ↓
Environment Variables (.env)
    ↓
NULL / System Defaults (lowest precedence)
```

**Resolution Behavior:**

| Source | Behavior |
|--------|----------|
| **CLI provided** | Use CLI value, no fallback |
| **CLI null** | Skip .env, use system default |
| **CLI not provided** | Check .env, then system default |

### 5.3 Configuration Summary

```python
config_json = json.dumps(config_dict, indent=None, separators=(',', ':'))
config_hash = hashlib.sha256(config_json.encode('utf-8')).hexdigest()
```

**Persistence:**
- Configuration serialized as compact JSON
- SHA-256 hash provides immutable identity
- Hash used for experiment fingerprinting

---

## 6. Command Coverage

### 6.1 Experiment Commands

**Module:** `bcllm_experiment.py`

| Command | Flags | Status |
|---------|-------|--------|
| `--create-experiment <name>` | `--seed`, `--add-questions`, `--add-model`, `--system-prompt`, `--user-prompt` | ✅ Implemented |
| `--experiment <name>` | (show details) | ✅ Implemented |
| `--list-experiments` | (list all) | ✅ Implemented |
| `--remove-experiment <name>` | (soft delete) | ✅ Implemented |

**Features:**
- Question snapshotting at creation time
- Model variant registration at creation time
- Configuration hash generation
- Seed generation (`AUTO` mode based on experiment name hash)

### 6.2 Model Commands

**Module:** `bcllm_model.py`

| Command | Flags | Status |
|---------|-------|--------|
| `--add-model <model_id>` | `--reasoning`, `--max-tokens`, `--temperature`, `--vision`, `--structured`, etc. | ✅ Implemented |
| `--list-models` | (list variants) | ✅ Implemented |
| `--remove-model <variant_id>` | (soft delete) | ✅ Implemented |

**Features:**
- Model ID validation (`provider/model-name` format)
- Variant signature generation
- Duplicate detection via signature
- 10 model-level configuration keys supported

### 6.3 Question Commands

**Module:** `bcllm_questions.py`

| Command | Flags | Status |
|---------|-------|--------|
| `--add-questions <spec>` | `--where`, `--exclude`, `--source-file` | ✅ Implemented |
| `--list-questions` | (list snapshots) | ✅ Implemented |
| `--remove-question <snapshot_id>` | (soft delete) | ✅ Implemented |

**Features:**
- Question spec parsing (`"1, 3, 5"`, `"1-10"`, `"1, 3-5, Q010"`)
- Metadata filtering (`--where status=valid`, `--exclude status=annulled`)
- Idempotent snapshot creation (skip existing)
- Nested field access for filters (`meta.status=valid`)

### 6.4 Run Commands

**Module:** `bcllm_run.py`

| Command | Flags | Status |
|---------|-------|--------|
| `--add-run` | `--seed`, `--system-prompt`, `--user-prompt` | ✅ Implemented |
| `--list-runs` | (list all runs) | ✅ Implemented |
| `--run <run_id>` | (show details) | ✅ Implemented |
| `--remove-run <run_id>` | (soft delete) | ✅ Implemented |

**Features:**
- Run configuration inheritance from experiment
- Seed specification (`AUTO`, number, or empty)
- Custom prompt override at run level
- Status tracking (`pending`, `running`, `completed`, `failed`)

### 6.5 Execution Commands

**Module:** `bcllm_execute.py`

| Command | Flags | Status |
|---------|-------|--------|
| `--execute` | `--run`, `--questions`, `--models`, `--retry-policy` | ✅ Implemented |

**Features:**
- Filter support (run, questions, models)
- Retry policy configuration
- Orchestration: Planner → ExecutionEngine → ResultWriter
- Partial execution support (pending items only)

**Orchestration Flow:**
```python
# Step 1: Build execution plan
planner = Planner(conn)
plan = planner.build_plan(experiment_name, run_ids=..., question_ids=..., model_variant_ids=...)

# Step 2: Execute plan
engine = ExecutionEngine(api_client, randomizer, parser)
results = engine.execute(plan)

# Step 3: Write results
writer = ResultWriter(conn)
report = writer.write_results(results)

# Step 4: Print summary
print(f"✓ Execution completed")
print(f"  Runs executed: {len(report.runs_updated)}")
print(f"  Success: {report.responses_written}")
print(f"  Failed: {report.errors_written}")
```

### 6.6 Review Commands

**Module:** `bcllm_review.py`

| Command | Flags | Status |
|---------|-------|--------|
| `--review-experiment <name>` | (start review UI) | ✅ Implemented |
| `--review-all` | (review all pending) | ✅ Implemented |

**Features:**
- Delegates to `ReviewUI` class (in `src/review/review_ui.py`)
- Keyboard-based classification (A/B/C/D/N/E/S/Q/Z)
- Progress tracking
- Auto-save on classification

---

## 7. Current Command Coverage Matrix

### 7.1 V1 vs V2 Comparison

| Command Category | V1 Command | V2 Command | Status | Notes |
|------------------|------------|------------|--------|-------|
| **Create Experiment** | `--create-experiment` | `--create-experiment` | ✅ Parity | V2 has better null semantics |
| **Show Experiment** | `--experiment` | `--experiment` | ✅ Parity | Similar output |
| **List Experiments** | (via `--experiment` alone) | `--list-experiments` | ✅ Improved | Dedicated command |
| **Remove Experiment** | (not in V1) | `--remove-experiment` | ✅ New | Soft delete |
| **Add Model** | `--add-model` | `--add-model` | ✅ Parity | V2 has variant signatures |
| **List Models** | (in experiment view) | `--list-models` | ✅ Improved | Dedicated command |
| **Remove Model** | `--remove-model` | `--remove-model` | ✅ Parity | V2 uses variant_id |
| **Add Questions** | `--add-questions` | `--add-questions` | ✅ Parity | V2 has better filtering |
| **List Questions** | (in experiment view) | `--list-questions` | ✅ Improved | Dedicated command |
| **Remove Question** | (not in V1) | `--remove-question` | ✅ New | Soft delete |
| **Create Run** | `--create-run` | `--add-run` | ✅ Parity | Renamed flag |
| **List Runs** | (in experiment view) | `--list-runs` | ✅ Improved | Dedicated command |
| **Show Run** | `--run` | `--run` | ✅ Parity | Similar output |
| **Remove Run** | (not in V1) | `--remove-run` | ✅ New | Soft delete |
| **Execute** | `--run --execute` | `--execute` | ✅ Improved | Standalone command |
| **Review Experiment** | `--review-experiment` | `--review-experiment` | ✅ Parity | Same UI |
| **Review All** | `--review-all` | `--review-all` | ✅ Parity | Same UI |
| **Export Results** | `--export-results` | (missing) | ⚠️ Regression | Not in V2 yet |
| **Add to Run** | `--add-to-run` | (missing) | ⚠️ Regression | Not in V2 yet |
| **Complete Run** | `--complete-run` | (missing) | ⚠️ Regression | Not in V2 yet |

### 7.2 Feature Coverage

| Feature | V1 | V2 | Status |
|---------|-----|-----|--------|
| **Null Semantics** | Basic | `EXPLICIT_NULL` | ✅ Improved |
| **Configuration Hierarchy** | CLI > .env > default | CLI > .env > NULL | ✅ Improved |
| **Variant Signatures** | No | Yes | ✅ New |
| **Question Filtering** | Basic | Nested field access | ✅ Improved |
| **Retry Policy** | Per-experiment | Per-execution | ✅ Improved |
| **Progress Bar** | Rich progress | (missing) | ⚠️ Regression |
| **Initialization Summary** | Fixed-width header | (missing) | ⚠️ Regression |
| **Milestone Logging** | 25%, 50%, 75%, 100% | (missing) | ⚠️ Regression |
| **Dry Run** | `--dry-run` | (missing) | ⚠️ Regression |
| **Output Formats** | console/json/csv/markdown | console only | ⚠️ Regression |

---

## 8. Output Patterns

### 8.1 Console Output

V2 uses **plain `print()` statements** instead of Rich:

```python
print(f"✓ Experiment '{experiment.name}' created (ID: {experiment.experiment_id})")
print(f"✓ Model variant '{variant_signature}' added")
print(f"✓ Added question {source_id} (position {question_position})")
```

**Characteristics:**
- No Rich library dependency
- Plain text output (script-friendly)
- Green checkmark (✓) for success
- No colored output or formatting

### 8.2 Error Output

```python
print(f"Error: Experiment already exists: {name}", file=sys.stderr)
print(f"Error: Invalid model ID format: {model_id}", file=sys.stderr)
```

**Characteristics:**
- All errors to `stderr`
- Plain text format
- No stack traces (logged separately)

### 8.3 Success Summaries

```
✓ Experiment 'my_exp' created (ID: exp_abc123)
✓ Model variant 'google/gemini-3.1-flash-lite-preview' added

Summary: 10 added
  Skipped 2 existing snapshot(s)
```

---

## 9. Database Integration

### 9.1 Persistent Connection

`src/cli/database.py` provides shared connection management:

```python
def get_database_connection() -> sqlite3.Connection:
    db_path = get_database_path()  # ./data/bcllm.db
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Initialize schema (idempotent)
    create_schema(conn)
    
    return conn
```

**Characteristics:**
- Persistent database file (`./data/bcllm.db`)
- Automatic directory creation
- Idempotent schema initialization
- Foreign keys enabled for CASCADE delete
- Caller responsible for closing connection

### 9.2 Repository Pattern

V2 uses repository classes for database operations:

```python
from src.db.repository import ExperimentRepository, VariantRepository, SnapshotRepository

exp_repo = ExperimentRepository(conn)
experiment = exp_repo.get_by_name(name)

var_repo = VariantRepository(conn)
var_repo.save(variant)

snap_repo = SnapshotRepository(conn)
snapshots = snap_repo.list_by_experiment(experiment_id)
```

---

## 10. Key V2 Features

### 10.1 Null Semantics

**Core Principle:** `null` is an explicit override to "no value", not a new state.

**Implementation:**
```python
# In bcllm_experiment.py
from src.core.null_semantics import EXPLICIT_NULL

add_questions_value = getattr(args, 'add_questions', None)

if add_questions_value is EXPLICIT_NULL:
    # User explicitly passed --add-questions null → use ALL questions (no .env fallback)
    selected_questions = questions
elif add_questions_value is not None:
    # User provided a value → use it
    selected_questions = loader.parse_question_spec(add_questions_value, questions)
else:
    # Not specified → fallback to DEFAULT_QUESTIONS from .env
    default_questions = env_dict.get('DEFAULT_QUESTIONS')
    if default_questions:
        selected_questions = loader.parse_question_spec(default_questions, questions)
    else:
        selected_questions = questions
```

### 10.2 Variant Signatures

**Purpose:** Unique identification of model variants based on configuration.

**Implementation:**
```python
from src.utils.variant_signature import generate_variant_signature

config = resolver.build_model_config_dict(args, experiment)
variant_signature = generate_variant_signature(model_id, config)

# Check for duplicates
existing = var_repo.get_by_signature(experiment.experiment_id, variant_signature)
if existing:
    print(f"Error: Variant '{variant_signature}' already exists", file=sys.stderr)
    return 1
```

**Signature Components:**
- Model ID
- Reasoning effort
- Vision enabled
- Structured enabled
- Other generation parameters

### 10.3 Question Spec Parsing

**Supported Formats:**
```python
# Individual
--questions "1"

# Comma-separated
--questions "1, 3, 5"

# Range
--questions "1-10"

# Mixed
--questions "1, 3-5, Q010"
```

**Implementation:**
```python
from src.core import QuestionLoader

loader = QuestionLoader()
questions = loader.load_dataset(dataset_path)
questions = loader.assign_internal_ids(questions)

selected = loader.parse_question_spec(spec, questions)
```

### 10.4 Metadata Filtering

**Filter Syntax:**
```bash
# Include filter
--where status=valid

# Exclude filter
--exclude status=annulled

# Multiple filters
--where status=valid has_image=false

# Nested field access
--where meta.status=valid
```

**Implementation:**
```python
def matches_filters(
    question: dict,
    include_filters: list[tuple[str, str]] | None = None,
    exclude_filters: list[tuple[str, str]] | None = None,
) -> bool:
    # Check exclude filters first
    if exclude_filters:
        for field, value in exclude_filters:
            if _get_nested_field(question, field) == value:
                return False
    
    # Then check include filters
    if include_filters:
        for field, value in include_filters:
            if _get_nested_field(question, field) != value:
                return False
    
    return True
```

---

## 11. Files Analyzed

### 11.1 Core Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/cli/bcllm_main.py` | ~100 | Dispatcher/help entry point |
| `src/cli/bcllm_experiment.py` | ~600 | Experiment lifecycle |
| `src/cli/bcllm_model.py` | ~250 | Model variant management |
| `src/cli/bcllm_questions.py` | ~400 | Question snapshot management |
| `src/cli/bcllm_run.py` | ~250 | Run lifecycle management |
| `src/cli/bcllm_execute.py` | ~350 | Execution orchestration |
| `src/cli/bcllm_review.py` | ~150 | Manual review interface |
| `src/cli/database.py` | ~50 | Database connection utility |

### 11.2 Supporting Files

| File | Purpose |
|------|---------|
| `src/cli/__init__.py` | Package initialization |
| `src/cli/bcllm_execute.txt` | (unknown - not analyzed) |

### 11.3 Documentation Files

| File | Purpose |
|------|---------|
| `docs/architecture/to-be/comandos_simples.md` | CLI specification (Portuguese) |
| `docs/architecture/to-be/comandos_tobe.md` | CLI to-be specification |
| `docs/architecture/contracts/cli_null_semantics.md` | Null semantics contract |

---

## 12. Conclusion

The V2 CLI system represents a **significant architectural improvement** over V1:

### 12.1 Strengths

1. **Modular Design** — Each command domain is isolated and maintainable
2. **Explicit Null Semantics** — Clear distinction between "not set" and "explicitly null"
3. **Configuration Hierarchy** — Well-defined CLI > .env > NULL resolution
4. **Variant Signatures** — Cryptographic identification of model configurations
5. **Question Filtering** — Advanced metadata filtering with nested field access
6. **Repository Pattern** — Clean separation of database logic

### 12.2 Gaps from V1

1. **Output Formatting** — Lost Rich library formatting (progress bars, tables, colors)
2. **Initialization Summary** — No fixed-width header showing configuration
3. **Execution Visibility** — No milestone logging or ETA during execution
4. **Export Results** — Missing `--export-results` command
5. **Incremental Flow** — Missing `--add-to-run` and `--complete-run` commands
6. **Dry Run** — Missing `--dry-run` validation mode
7. **Output Formats** — Only console output, no JSON/CSV/Markdown export

### 12.3 Technical Debt

1. **Dispatcher Implementation** — How `bcllm` invokes modules is unclear
2. **Error Guidance** — Some errors lack fix suggestions (same as V1)
3. **Testing Coverage** — No visible test suite for CLI modules
4. **Documentation** — Help text minimal compared to V1 epilog

---

**Next Document:** `docs/architecture/gap-reports/03-cli-system-gap.md` — Gap Analysis Report
