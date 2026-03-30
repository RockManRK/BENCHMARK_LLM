# V2 Implementation Plan

**Document Type:** Implementation Roadmap
**Project:** Benchmark LLM V2
**Version:** 1.0
**Date:** 2026-03-29
**Status:** Actionable
**Plan Checklist:** @docs\architecture\v2-implementation-checklist.md

---

## 1. Executive Summary

### 1.1 Current State Overview

The Benchmark LLM V2 system is **well-architected but incomplete**. The current implementation has:

**Strengths:**
- ✅ Well-structured modular architecture
- ✅ Clear separation of concerns (ExecutionEngine, ResultWriter, Planner)
- ✅ Immutable ExecutionPlan design
- ✅ Idempotent result persistence
- ✅ Explicit configuration semantics (EXPLICIT_NULL)
- ✅ Comprehensive error handling components (standalone)

**Critical Gaps:**
- ❌ **No logging system** — 18 gaps, blocks production deployment
- ❌ **No retry delay** — CRITICAL bug, API abuse risk
- ❌ **RetryHandler not integrated** — Duplicate logic, inconsistency
- ❌ **ErrorClassifier not integrated** — Imprecise classification
- ❌ **Missing CLI commands** — Broken workflows (export, add-to-run, complete-run)
- ❌ **Review UI limitations** — Portuguese-only, single-level undo, no batch ops

**Overall Assessment:** ❌ **NOT READY FOR PRODUCTION**

---

### 1.2 Target State Vision

The target V2 system will be:

1. **Production-Ready**
   - Comprehensive logging with file rotation
   - Safe retry behavior with exponential backoff
   - Full error visibility and debugging capability
   - Audit trail for reproducibility

2. **Feature-Complete**
   - All V1 CLI commands restored
   - Enhanced Review UI with multi-level undo
   - Multi-language support (Portuguese + English)
   - Batch classification for efficiency

3. **Well-Documented**
   - Complete architecture reference
   - Configuration key inventory
   - Developer guides and examples
   - User-facing documentation

4. **Maintainable**
   - Clear domain boundaries
   - Consistent error handling
   - Comprehensive test coverage
   - Explicit contracts between components

---

### 1.3 Implementation Approach

**Strategy:** Phased rollout by priority

| Phase | Focus | Duration | Effort |
|-------|-------|----------|--------|
| **Phase 0** | Critical Fixes (Blockers) | 2-3 days | ~18 hours |
| **Phase 1** | High Priority (Workflow) | 1-2 weeks | ~31 hours |
| **Phase 2** | Medium Priority (Features) | 2-3 weeks | ~33 hours |
| **Phase 3** | Low Priority (Polish) | 2-3 weeks | ~27 hours |
| **TOTAL** | | **7-11 weeks** | **~109 hours** |

**Key Principles:**
1. **Logging First** — Enables debugging for all other phases
2. **Safety First** — Fix retry delay before any production use
3. **Workflow Restoration** — Restore V1 commands before enhancements
4. **Incremental Validation** — Test each phase before proceeding
5. **No Breaking Changes** — Maintain backward compatibility where possible

---

### 1.4 Total Effort Estimate

| Phase | Duration | Effort (hours) | Team Size |
|-------|----------|----------------|-----------|
| **Phase 0** (Critical) | 2-3 days | 18h | 1-2 developers |
| **Phase 1** (High) | 1-2 weeks | 31h | 2 developers |
| **Phase 2** (Medium) | 2-3 weeks | 33h | 2 developers |
| **Phase 3** (Low) | 2-3 weeks | 27h | 1-2 developers |
| **TOTAL** | **7-11 weeks** | **109h** | **1-2 developers** |

**Note:** Effort estimates are conservative. Actual time may vary based on:
- Developer familiarity with codebase
- Testing requirements
- Code review cycles
- Unexpected dependencies

---

## 2. Implementation Principles

### 2.1 Guiding Principles

**1. Explicit Over Implicit**
- Configuration resolution must be explicit (CLI > .env > NULL) - CLI overrides configuration hierarchy; null bypasses inheritance.
- No hidden behavior or magic defaults
- All decisions traceable to source

**2. Safety Over Speed**
- Fix retry delay immediately (prevents API abuse)
- Add logging before debugging complex issues
- Test error handling thoroughly

**3. Reproducibility Over Convenience**
- All executions must be reproducible
- Seed resolution must be deterministic
- Configuration captured at entity creation

**4. Separation of Concerns**
- ExecutionEngine: Pure execution (NO DB access)
- ResultWriter: Idempotent persistence
- Planner: Read-only plan generation
- RetryHandler: Policy-driven retry logic

**5. Incremental Validation**
- Each phase validated before next begins
- Tests written alongside implementation
- No phase skipped or combined

---

### 2.2 What to Implement vs What to Defer

**Implement Now (Phase 0-2):**
- ✅ Logging infrastructure (CRITICAL)
- ✅ Retry delay fix (CRITICAL)
- ✅ RetryHandler integration (HIGH)
- ✅ ErrorClassifier integration (HIGH)
- ✅ CLI export/add-to-run/complete-run (HIGH)
- ✅ Progress bar (HIGH)
- ✅ Review UI English option (HIGH)
- ✅ Multi-level undo (HIGH)
- ✅ Batch classification (HIGH)
- ✅ Dry run command (MEDIUM)
- ✅ Output formats (MEDIUM)
- ✅ API timeout fix (MEDIUM)

**Defer to Phase 3 or Later:**
- ⏸️ Custom classification labels (LOW)
- ⏸️ Review queue reordering (LOW)
- ⏸️ Keyboard shortcuts customization (LOW)
- ⏸️ Theme options (LOW)
- ⏸️ Stack trace capture (LOW)
- ⏸️ Error details JSON column (LOW)
- ⏸️ ErrorCategory enum (LOW)
- ⏸️ Rich CLI formatting (LOW)

**Intentionally Removed (V2 Simplifications):**
- ❌ Repository pattern for database (direct SQLite is simpler)
- ❌ Protocol hash for experiments (not needed for current use cases)
- ❌ Reasoning extraction from responses (unused feature)
- ❌ Convenience function for parsing (minor API change)
- ❌ Global model variants (experiment-scoped is better design)

---

### 2.3 Quality Gates

**Before Phase 0 Complete:**
- [ ] All components log to file and console
- [ ] Retry delay prevents API abuse
- [ ] Logs show retry attempts, errors, progress
- [ ] Initialization summary appears
- [ ] Log rotation works

**Before Phase 1 Complete:**
- [ ] RetryHandler used by ExecutionEngine
- [ ] ErrorClassifier used consistently
- [ ] Export results command works
- [ ] Incremental workflow restored
- [ ] Progress bar visible during execution
- [ ] English UI available
- [ ] Multi-level undo works
- [ ] Batch classification works

**Before Phase 2 Complete:**
- [ ] Dry run validates without executing
- [ ] Export supports multiple formats
- [ ] Review sessions can be paused/resumed
- [ ] Pending items can be filtered
- [ ] Timeout supports slow reasoning models
- [ ] All MEDIUM gaps closed or accepted

**Before Phase 3 Complete:**
- [ ] All documentation gaps filled
- [ ] All LOW gaps closed or deferred
- [ ] Final validation passed
- [ ] Production deployment approved

---

## 3. Phase 0: Critical Fixes (IMMEDIATE)

**Duration:** 2-3 days
**Effort:** ~18 hours
**Priority:** 🔴 CRITICAL (Blockers for Production)
**Owner:** Backend Developer

### 3.1 Why First

These gaps **block all other work**:
- Without logging, cannot debug issues in other phases
- Without retry delay, risk API abuse and rate limiting
- These are **production blockers** — system cannot be used safely without them

---

### 3.2 Gap: LOG-001 to LOG-018 — Logging System

**Severity:** 🔴 CRITICAL
**Effort:** 14-20 hours
**Files to Create:**
- `src/utils/logging_config.py` — Main logging configuration

**Files to Modify:**
- `src/main.py` (or entry point) — Add `setup_logging()` call
- `.env.example` — Add `LOG_LEVEL`, `LOG_FILE_PATH`
- `src/core/execution_engine.py` — Add logging throughout
- `src/core/result_writer.py` — Add logging for write operations
- `src/core/planner.py` — Add logging for plan generation
- `src/api/client.py` — Add logging for API operations
- `src/api/retry.py` — Add logging for retries
- `src/cli/bcllm_execute.py` — Replace print with logging
- Other CLI files — Replace error print with logging

**Implementation Steps:**

1. **Create logging infrastructure** (2-3h)
   ```python
   # src/utils/logging_config.py
   - LoggingConfig class with validation
   - setup_logging() function
   - get_structured_logger() function
   - Custom flushing handlers (crash-safety)
   - Log rotation (10MB, 5 backups)
   ```

2. **Configure root logger at startup** (1h)
   ```python
   # src/main.py
   from src.utils.logging_config import setup_logging, LoggingConfig

   config = LoggingConfig(
       log_file_path=Path("./logs/benchmark.log"),
       log_level=os.getenv("LOG_LEVEL", "INFO")
   )
   setup_logging(config)
   ```

3. **Integrate into core components** (4-6h)
   - ExecutionEngine: Log execution start/complete, item progress, errors
   - ResultWriter: Log write start/complete, idempotency skips
   - Planner: Log plan build start/complete, validation errors

4. **Integrate into API layer** (3-4h)
   - OpenRouterClient: Log requests, responses, errors
   - RetryHandler: Log retry attempts with delays

5. **Integrate into CLI layer** (2-3h)
   - Replace error prints with `logger.error()`
   - Keep user-facing success messages as `print()`

6. **Testing and validation** (2-3h)
   - Verify log file creation
   - Verify console output (INFO+)
   - Verify debug mode (LOG_LEVEL=DEBUG)
   - Verify log rotation

**Acceptance Criteria:**
- [ ] Logs written to file immediately (crash-safe)
- [ ] Console output shows INFO and above
- [ ] Debug mode available via `LOG_LEVEL=DEBUG`
- [ ] Log rotation works automatically (10MB, 5 backups)
- [ ] Initialization summary logged
- [ ] Error logging with stack traces
- [ ] API request/response logging
- [ ] Retry attempt logging with delays

**Risks:**
- Logging impacts performance → Mitigation: Use appropriate log levels, profile overhead
- Log files fill disk → Mitigation: Rotation enabled, monitor size
- Sensitive data in logs → Mitigation: Do not log API keys or tokens

---

### 3.3 Gap: ERR-002 — No Retry Backoff Delay

**Severity:** 🔴 CRITICAL
**Effort:** 1 hour
**Files to Modify:**
- `src/core/execution_engine.py` — Add delay between retries

**Current Code (BUGGY):**
```python
for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return ExecutionResult(...)
    except Exception as e:
        last_error_type = self._classify_error(e)
        last_error_message = str(e)
        if attempt < max_attempts:
            continue  # NO DELAY!
```

**Fix (IMMEDIATE):**
```python
import asyncio

for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return ExecutionResult(...)
    except Exception as e:
        if attempt < max_attempts:
            # CRITICAL FIX: Add delay before retry
            delay = 2 ** attempt  # Exponential backoff
            await asyncio.sleep(delay)
            continue
```

**Better Fix (use RetryPolicy):**
```python
# Add to RetryPolicy in src/core/execution_plan.py
def backoff_delay(self, attempt: int) -> float:
    """Calculate delay for a given attempt (1-indexed)."""
    delay = self.base_delay * (2.0 ** (attempt - 1))
    return min(delay, self.max_delay)

# Use in ExecutionEngine
for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return ExecutionResult(...)
    except Exception as e:
        if attempt < max_attempts:
            delay = run.retry_policy.backoff_delay(attempt)
            await asyncio.sleep(delay)
            continue
```

**Acceptance Criteria:**
- [ ] Delay added between retry attempts
- [ ] Exponential backoff (1s, 2s, 4s, 8s)
- [ ] Max delay cap (60s)
- [ ] Tests verify delay behavior
- [ ] No API abuse (monitor rate limits)

**Risks:**
- None — This is a simple, safe fix

---

### 3.4 Phase 0 Validation

**Run these tests:**

1. **Log file creation:**
   ```bash
   python -m src.cli.bcllm_experiment --list-experiments
   ls -la ./logs/benchmark.log
   # Expected: Log file exists with entries
   ```

2. **Console output:**
   ```bash
   # Run with default LOG_LEVEL=INFO
   python -m src.cli.bcllm_experiment --list-experiments
   # Expected: Console shows INFO and above, no DEBUG
   ```

3. **Debug mode:**
   ```bash
   $env:LOG_LEVEL="DEBUG"
   python -m src.cli.bcllm_experiment --list-experiments
   # Expected: File shows DEBUG+, console still INFO+
   ```

4. **Retry delay:**
   ```bash
   # Simulate transient error (e.g., invalid API key temporarily)
   # Check logs for:
   # - "Retry attempt 1/3 after 1.00s delay"
   # - "Retry attempt 2/3 after 2.00s delay"
   # Expected: Delays are applied (not instant retries)
   ```

5. **Log rotation:**
   ```python
   # Generate large log file
   import logging
   from src.utils.logging_config import setup_logging, LoggingConfig

   config = LoggingConfig(
       log_file_path=Path("./logs/test_rotation.log"),
       max_bytes=1024 * 1024,  # 1MB for testing
       backup_count=3
   )
   setup_logging(config)

   logger = logging.getLogger(__name__)
   for i in range(10000):
       logger.info(f"Test log message {i}")

   # Expected: Log file rotates at 1MB, backups created
   ```

---

## 4. Phase 1: High Priority (Week 1-2)

**Duration:** 1-2 weeks
**Effort:** ~31 hours
**Priority:** 🟠 HIGH (Core Workflow Restoration)
**Owner:** Backend + Frontend Developers

### 4.1 Why Second

These gaps **block critical workflows**:
- Cannot export results for analysis
- Cannot add models to existing runs (broken multi-day workflow)
- No progress visibility during long executions
- Review UI accessibility barriers (Portuguese-only)
- Review UI inefficiency (single-level undo, no batch ops)

---

### 4.2 Gap: CLI-001 — Export Results Command

**Severity:** 🟠 HIGH
**Effort:** 3-4 hours
**Files to Create/Modify:**
- `src/cli/bcllm_execute.py` or new `src/cli/bcllm_export.py`

**Specification:**
```bash
bcllm --export-results <run_id>
bcllm --experiment <name> --export-results <run_id> --output json
```

**Implementation:**
```python
def handle_export_results(args, conn) -> int:
    run_id = args.export_results

    # Fetch responses
    response_repo = ResponseRepository(conn)
    responses = response_repo.get_by_run(run_id)

    if not responses:
        print(f"No responses found for run {run_id}", file=sys.stderr)
        return 1

    # Build export data
    export_data = []
    for r in responses:
        final_answer = r.manual_answer if r.manual_answer else r.selected_answer
        answer_source = "manual" if r.manual_answer else "automatic"

        export_data.append({
            "response_id": r.response_id,
            "question_id": r.question_id,
            "variant_id": r.variant_id,
            "model_id": r.model_id,
            "iteration": r.iteration,
            "selected_answer": r.selected_answer,
            "manual_answer": r.manual_answer,
            "final_answer": final_answer,
            "answer_source": answer_source,
            "is_correct": r.is_correct,
            "parse_confidence": r.parse_confidence,
            "latency_ms": r.latency_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
        })

    # Output JSON
    output = {
        "run_id": run_id,
        "total_responses": len(responses),
        "manual_answers": sum(1 for r in responses if r.manual_answer),
        "automatic_answers": sum(1 for r in responses if not r.manual_answer),
        "responses": export_data,
    }

    print(json.dumps(output, indent=2, default=str))
    return 0
```

**Acceptance Criteria:**
- [ ] Command exports results for run_id
- [ ] JSON output includes all required fields
- [ ] Supports `--output-file` flag
- [ ] Tests verify export accuracy

---

### 4.3 Gap: CLI-002 / CLI-003 — Add-to-Run and Complete-Run

**Severity:** 🟠 HIGH
**Effort:** 5 hours
**Files to Modify:**
- `src/cli/bcllm_run.py` or `src/cli/bcllm_model.py`

**Specification:**
```bash
bcllm --add-to-run <run_id> --add-models <model1> <model2>
bcllm --complete-run <run_id>
```

**Implementation (Add-to-Run):**
```python
def handle_add_to_run(args, conn) -> int:
    run_id = args.add_to_run
    model_ids = args.add_models

    # Validate run exists
    run_repo = RunRepository(conn)
    run = run_repo.get_by_id(run_id)
    if not run:
        print(f"Error: Run not found: {run_id}", file=sys.stderr)
        return 1

    # Validate run status
    if run.status != 'running':
        print(f"Error: Run '{run_id}' is not in 'running' status (current: {run.status})", file=sys.stderr)
        return 1

    # Add models to run
    run_model_repo = RunModelRepository(conn)
    added_count = 0

    for model_id in model_ids:
        # Check if model already in run
        existing = run_model_repo.get_by_run_and_model(run_id, model_id)
        if existing:
            print(f"Model '{model_id}' already in run '{run_id}' (skipped)")
            continue

        # Add model to run
        run_model_repo.add(run_id, model_id, status='pending')
        added_count += 1
        print(f"✓ Model '{model_id}' added to run '{run_id}'")

    print(f"\nSummary: {added_count} model(s) added to run '{run_id}'")
    return 0
```

**Implementation (Complete-Run):**
```python
def handle_complete_run(args, conn) -> int:
    run_id = args.complete_run

    # Validate run exists
    run_repo = RunRepository(conn)
    run = run_repo.get_by_id(run_id)
    if not run:
        print(f"Error: Run not found: {run_id}", file=sys.stderr)
        return 1

    # Validate run status
    if run.status not in ('running', 'partial_failed'):
        print(f"Error: Run '{run_id}' cannot be completed (current status: {run.status})", file=sys.stderr)
        return 1

    # Update status
    run_repo.update_status(run_id, 'completed')
    print(f"✓ Run '{run_id}' marked as completed")
    print(f"  No more models can be added to this run.")
    return 0
```

**Acceptance Criteria:**
- [ ] `--add-to-run` adds models to running run
- [ ] `--complete-run` marks run as completed
- [ ] Cannot add models to completed run
- [ ] Tests verify lifecycle management

---

### 4.4 Gap: CLI-005 — Progress Bar During Execution

**Severity:** 🟠 HIGH
**Effort:** 3 hours
**Files to Modify:**
- `src/cli/bcllm_execute.py`

**Implementation:**
```python
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn

# In handle_execute:
with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeRemainingColumn(),
) as progress:
    task = progress.add_task("Benchmark Execution", total=total_items)

    for item in items:
        # Execute item
        result = engine.execute_item(item)

        # Update progress
        progress.update(task, advance=1)

        # Log milestone
        current = progress.tasks[task].completed
        if current % (total_items // 4) == 0:
            percent = (current / total_items) * 100
            logger.info(f"Progress: {current}/{total_items} ({percent:.1f}%)")
```

**Acceptance Criteria:**
- [ ] Progress bar shows during execution
- [ ] Milestone logging at 25% intervals
- [ ] ETA calculation displayed
- [ ] Tests verify progress tracking

---

### 4.5 Gap: UI-001 — Portuguese-Only UI

**Severity:** 🟠 HIGH
**Effort:** 4 hours
**Files to Create:**
- `src/review/localization/pt.json`
- `src/review/localization/en.json`
- `src/review/localization/i18n.py`

**Files to Modify:**
- `src/review/review_ui.py`
- `src/cli/bcllm_review.py`

**Implementation:**
```python
# src/review/localization/i18n.py
import json
from pathlib import Path

class Localization:
    def __init__(self, language: str = "pt") -> None:
        self.language = language
        self._strings = self._load_strings(language)

    def _load_strings(self, language: str) -> dict:
        path = Path(__file__).parent / f"{language}.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get(self, key: str, **kwargs) -> str:
        """Get localized string with optional formatting."""
        string = self._strings.get(key, key)
        return string.format(**kwargs) if kwargs else string

# CLI flag
parser.add_argument(
    "--language",
    choices=["pt", "en"],
    default="pt",
    help="UI language (Portuguese or English)"
)
```

**Acceptance Criteria:**
- [ ] All UI strings extracted to localization file
- [ ] English translations added
- [ ] `--language` flag works
- [ ] Default language is Portuguese

---

### 4.6 Gap: UI-002 — Multi-Level Undo

**Severity:** 🟠 HIGH
**Effort:** 4 hours
**Files to Modify:**
- `src/review/review_ui.py`

**Implementation:**
```python
@dataclass
class ClassificationHistory:
    """History entry for undo operations."""
    response_id: str
    previous_manual_answer: Optional[str]
    previous_selected_answer: Optional[str]
    previous_is_correct: Optional[bool]
    previous_needs_review: bool
    new_manual_answer: Optional[str]
    new_selected_answer: Optional[str]
    new_is_correct: Optional[bool]
    new_needs_review: bool


class ReviewUI:
    def __init__(self, conn) -> None:
        self._undo_stack: list[ClassificationHistory] = []
        self._max_undo_depth = 50

    def _save_classification(self, item: ReviewItem, classification: str) -> None:
        # Save previous state for undo
        history = ClassificationHistory(...)

        # Execute UPDATE
        # ...

        # Add to undo stack
        self._undo_stack.append(history)

        # Enforce max depth
        if len(self._undo_stack) > self._max_undo_depth:
            self._undo_stack.pop(0)

    def _undo_last_classification(self) -> None:
        if not self._undo_stack:
            self._console.print("[yellow]Nada para desfazer.[/yellow]")
            return

        history = self._undo_stack.pop()

        # Rollback database
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE responses
            SET manual_answer = ?, selected_answer = ?,
                is_correct = ?, needs_review = ?
            WHERE response_id = ?
        """, (
            history.previous_manual_answer,
            history.previous_selected_answer,
            history.previous_is_correct,
            history.previous_needs_review,
            history.response_id,
        ))
        self.conn.commit()

        # Decrement index
        self._current_index -= 1
        self._statistics.total_processed -= 1

        self._console.print(
            f"[yellow]Desfeito: classificação anterior era {history.previous_manual_answer or 'None'}[/yellow]"
        )
```

**Acceptance Criteria:**
- [ ] Multi-level undo supported (up to 50 items)
- [ ] Database rollback on undo
- [ ] Undo stack limit enforced
- [ ] UI shows undo depth

---

### 4.7 Gap: UI-003 — Batch Classification

**Severity:** 🟠 HIGH
**Effort:** 6 hours
**Files to Modify:**
- `src/review/review_ui.py`

**Implementation:**
```python
class ReviewUI:
    def __init__(self, conn) -> None:
        self._multi_select_mode = False
        self._selected_indices: set[int] = set()

    def _toggle_multi_select(self) -> None:
        """Toggle multi-select mode (M key)."""
        self._multi_select_mode = not self._multi_select_mode
        self._selected_indices.clear()
        mode_text = "ON" if self._multi_select_mode else "OFF"
        self._console.print(f"[cyan]Multi-select mode: {mode_text}[/cyan]")

    def _select_current_item(self) -> None:
        """Select/deselect current item in multi-select mode (Space key)."""
        if self._current_index in self._selected_indices:
            self._selected_indices.remove(self._current_index)
        else:
            self._selected_indices.add(self._current_index)

    def _classify_selected(self, classification: str) -> None:
        """Classify all selected items with same classification."""
        indices = sorted(self._selected_indices)

        for index in indices:
            item = self._pending_items[index]
            self._save_classification(item, classification)

        self._statistics.total_processed += len(indices)
        self._selected_indices.clear()
        self._multi_select_mode = False

        self._console.print(
            f"[green]✓ Classificados {len(indices)} itens como {classification}[/green]"
        )
```

**New Keyboard Shortcuts:**

| Key | Action | Mode |
|-----|--------|------|
| **M** | Toggle multi-select mode | All |
| **Space** | Select/deselect current item | Multi-select |
| **Enter** | Classify all selected (prompts for classification) | Multi-select |

**Acceptance Criteria:**
- [ ] Multi-select mode works
- [ ] "Classify next N" command works
- [ ] Filter-then-classify workflow works
- [ ] Batch confirmation dialog appears

---

### 4.8 Gap: ERR-003 / EXE-002 — RetryHandler Integration

**Severity:** 🟠 HIGH
**Effort:** 4 hours
**Files to Modify:**
- `src/core/execution_engine.py`
- `src/api/retry.py` (verify)

**Current State:**
```python
# ExecutionEngine has inline retry
for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return result
    except Exception as e:
        if attempt < max_attempts:
            continue
```

**Target State:**
```python
from src.api.retry import RetryHandler

class ExecutionEngine:
    def _execute_item(self, item: PlanItem, run: PlanRun) -> ExecutionResult:
        # Create retry handler for this item
        retry_handler = RetryHandler(run.retry_policy)

        async def execute_api_call():
            response = self._call_api_sync(...)
            return response

        try:
            response = await retry_handler.execute_with_retry(execute_api_call)
            return ExecutionResult(status="success", ...)
        except Exception as e:
            return ExecutionResult(
                status="failure",
                error_type=self._classify_error(e),
                error_message=str(e),
                attempt_count=run.retry_policy.max_attempts,
                ...
            )
```

**Acceptance Criteria:**
- [ ] ExecutionEngine uses RetryHandler
- [ ] Inline retry loop removed
- [ ] RetryPolicy passed from PlanRun
- [ ] Tests verify retry behavior matches V1

---

### 4.9 Gap: ERR-004 / EXE-003 — ErrorClassifier Integration

**Severity:** 🟠 HIGH
**Effort:** 2 hours
**Files to Modify:**
- `src/core/execution_engine.py`

**Current Code:**
```python
def _classify_error(self, error: Exception) -> str:
    error_str = str(error).lower()
    if "timeout" in error_str:
        return "timeout"
    if "429" in error_str:
        return "http_429"
    # ... simplified string matching
```

**Target Code:**
```python
from src.api.errors import ErrorClassifier, APIError

def _classify_error(self, error: Exception) -> str:
    """Classify an error type using ErrorClassifier."""
    # If it's an APIError, use its error_type
    if isinstance(error, APIError):
        return error.error_type

    # Use ErrorClassifier for other exceptions
    if isinstance(error, httpx.TimeoutException):
        return ErrorClassifier.classify_timeout(str(error)).error_type

    if isinstance(error, (httpx.ConnectError, httpx.NetworkError)):
        return ErrorClassifier.classify_network(str(error)).error_type

    if isinstance(error, httpx.HTTPStatusError):
        return ErrorClassifier.classify_http(
            error.response.status_code,
            error.response.text
        ).error_type

    # Fallback
    return "api_error"
```

**Acceptance Criteria:**
- [ ] ExecutionEngine uses ErrorClassifier
- [ ] Classification matches OpenRouterClient
- [ ] Tests verify classification accuracy

---

### 4.10 Phase 1 Validation

**Run these tests:**

1. **Export results:**
   ```bash
   bcllm --export-results run-001 --output-file results.json
   # Expected: JSON file with all responses
   ```

2. **Add-to-run:**
   ```bash
   bcllm --add-to-run run-001 --add-models gpt-4 claude-3
   # Expected: Models added as 'pending'
   ```

3. **Complete-run:**
   ```bash
   bcllm --complete-run run-001
   # Expected: Run status updated to 'completed'
   ```

4. **Progress bar:**
   ```bash
   bcllm --experiment test_exp --execute
   # Expected: Progress bar visible during execution
   ```

5. **English UI:**
   ```bash
   bcllm --review-experiment test_exp --language en
   # Expected: All UI text in English
   ```

6. **Multi-level undo:**
   ```bash
   # Classify 5 items, then press Z (undo) 5 times
   # Expected: All 5 classifications reverted
   ```

7. **Batch classification:**
   ```bash
   # Press M (multi-select), Space (select 3 items), Enter, A (classify as A)
   # Expected: All 3 items classified as A
   ```

---

## 5. Phase 2: Medium Priority (Week 3-5)

**Duration:** 2-3 weeks
**Effort:** ~33 hours
**Priority:** 🟡 MEDIUM (Feature Parity + UX Improvements)
**Owner:** Backend + Frontend Developers

### 5.1 Why Third

These gaps **enhance functionality** but are not blockers:
- Dry run validates before long executions (convenience)
- Output formats enable different analysis workflows (enhancement)
- Session resume enables multi-day review (efficiency)
- Search/filter improves review flexibility (UX)
- API timeout fix prevents reasoning model failures (reliability)

---

### 5.2 Gap: CLI-004 — Dry Run Command

**Severity:** 🟡 MEDIUM
**Effort:** 2 hours
**Files to Modify:**
- `src/cli/bcllm_execute.py`

**Specification:**
```bash
bcllm --experiment <name> --execute --dry-run
```

**Implementation:**
```python
def handle_execute(args, conn) -> int:
    # ... existing validation ...

    # Check dry run
    if args.dry_run:
        print("Dry run mode - validation only")

        # Build plan to show what would be executed
        planner = Planner(conn)
        plan = planner.build_plan(
            args.experiment,
            run_ids=[run_id] if run_id else None,
            question_ids=question_ids,
            model_variant_ids=model_variant_ids,
        )

        # Show summary
        total_items = sum(len(run.items) for run in plan.runs)
        print(f"\nConfiguration validated successfully.")
        print(f"  Would execute: {total_items} items")
        print(f"  Runs: {len(plan.runs)}")
        for run_plan in plan.runs:
            print(f"    - {run_plan.run_id}: {len(run_plan.items)} items")

        return 0

    # ... normal execution ...
```

**Acceptance Criteria:**
- [ ] Validates all configuration
- [ ] Builds execution plan (doesn't execute)
- [ ] Shows what would be executed
- [ ] Returns 0 on successful validation

---

### 5.3 Gap: CLI-007 — Output Format Options

**Severity:** 🟡 MEDIUM
**Effort:** 4 hours
**Files to Create:**
- `src/cli/output_formatter.py` (reuse V1)

**Files to Modify:**
- `src/cli/bcllm_execute.py`

**Specification:**
- `--output console` (default) — Rich table
- `--output json` — JSON export
- `--output csv` — CSV export
- `--output markdown` — Markdown table

**Implementation:**
Reuse V1 `OutputFormatter` class from `src_legacy/cli/output_formatter.py`:
```python
from src.cli.output_formatter import create_formatter

formatter = create_formatter(args.output)

if args.output == 'json':
    print(formatter.to_json(statistics))
elif args.output == 'csv':
    print(formatter.to_csv(statistics))
elif args.output == 'markdown':
    print(formatter.to_markdown(statistics))
else:
    formatter.display_table(statistics)
```

**Acceptance Criteria:**
- [ ] Supports console, json, csv, markdown
- [ ] Default is console
- [ ] Consistent output across formats

---

### 5.4 Gap: UI-004 — Review Session Resume

**Severity:** 🟡 MEDIUM
**Effort:** 6 hours
**Files to Create:**
- `src/review/session.py` — Session management
- Database table: `review_sessions`

**Files to Modify:**
- `src/cli/bcllm_review.py` — Add session commands

**Schema:**
```sql
CREATE TABLE review_sessions (
    session_id TEXT PRIMARY KEY,
    experiment_id TEXT,
    pending_items_json TEXT NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    history_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);
```

**CLI Commands:**
```bash
# Save session
bcllm --review-experiment exp-001 --save-session

# Resume session
bcllm --resume-session <session_id>

# List sessions
bcllm --list-sessions
```

**Acceptance Criteria:**
- [ ] Sessions persist across process restarts
- [ ] Resume restores exact state (index, history, statistics)
- [ ] Old sessions cleaned up automatically

---

### 5.5 Gap: UI-005 — Search/Filter Pending Items

**Severity:** 🟡 MEDIUM
**Effort:** 4 hours
**Files to Modify:**
- `src/review/review_ui.py`
- `src/cli/bcllm_review.py`

**Specification:**
- `--filter-by-model <model_id>` — Filter by model
- `--filter-by-confidence <level>` — Filter by parse confidence
- Interactive filter mode

**Implementation:**
```python
def get_pending_by_experiment(conn, experiment_name, filters=None):
    query = """
        SELECT ... FROM responses
        WHERE review_status = 'needs_review'
        AND experiment_id = ?
    """
    params = [experiment_name]

    if filters and 'model_id' in filters:
        query += " AND model_id = ?"
        params.append(filters['model_id'])

    if filters and 'parse_confidence' in filters:
        query += " AND parse_confidence = ?"
        params.append(filters['parse_confidence'])

    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()
```

**Acceptance Criteria:**
- [ ] Filters correctly limit review queue
- [ ] Multiple filters combine correctly
- [ ] Empty filter results handled gracefully

---

### 5.6 Gap: EXE-001 — API Timeout Configuration

**Severity:** 🟡 MEDIUM
**Effort:** 1 hour
**Files to Modify:**
- `src/api/client.py`

**Current Code:**
```python
class OpenRouterClient:
    def __init__(self, api_key: str, timeout: int = 120):
        self.timeout = timeout  # 120 seconds
```

**Fix:**
```python
class OpenRouterClient:
    def __init__(self, api_key: str, timeout: int = 180):
        self.timeout = timeout  # 180 seconds (for reasoning models)
```

**Alternative (configurable per model):**
```python
class OpenRouterClient:
    def __init__(self, api_key: str, timeout: int = 180):
        self.default_timeout = timeout
        self.model_timeouts = {
            "openai/o1": 300,  # 5 minutes for o1
            "anthropic/claude": 180,
        }

    async def chat_completion(self, model_id: str, ...):
        timeout = self.model_timeouts.get(model_id, self.default_timeout)
        # Use timeout for this request
```

**Acceptance Criteria:**
- [ ] Default timeout increased to 180s
- [ ] Or timeout configurable per model
- [ ] Tests verify timeout behavior

---

### 5.7 Gap: EXE-005 — Multimodal Support Verification

**Severity:** 🟡 MEDIUM
**Effort:** 3 hours
**Files to Read:**
- `src/api/client.py`

**Verification Checklist:**
- [ ] `build_multimodal_message()` exists in OpenRouterClient
- [ ] Image encoding (base64) implemented
- [ ] Image format detection (PNG, JPG, etc.)
- [ ] Image path validation (file exists)
- [ ] Multimodal messages sent correctly to API

**Test Cases:**
```python
def test_multimodal_message():
    from pathlib import Path
    from src.api.client import MessageBuilder

    image_path = Path("test.png")
    message = MessageBuilder.build_multimodal_message(
        "What's in this image?",
        image_path,
    )
    assert "content" in message
    assert isinstance(message["content"], list)
    assert len(message["content"]) == 2  # text + image
```

**Acceptance Criteria:**
- [ ] Multimodal support verified
- [ ] Test with image-based question
- [ ] API receives image correctly

---

### 5.8 Gap: ERR-005 — ErrorCollector Implementation

**Severity:** 🟡 MEDIUM
**Effort:** 3 hours
**Files to Create:**
- `src/api/error_collector.py` (optional)

**Purpose:** Aggregate errors for analysis and reporting

**Implementation:**
```python
@dataclass
class ErrorSummary:
    error_type: str
    count: int
    models: set[str]
    last_occurrence: str


class ErrorCollector:
    def __init__(self):
        self.errors: list[ErrorRecord] = []

    def add_error(self, error: ErrorRecord) -> None:
        self.errors.append(error)

    def get_summary(self) -> list[ErrorSummary]:
        # Aggregate by error_type
        pass

    def get_by_model(self, model_id: str) -> list[ErrorRecord]:
        # Filter by model
        pass
```

**Acceptance Criteria:**
- [ ] Errors aggregated by type
- [ ] Summary available for CLI reporting
- [ ] Can filter by model

---

### 5.9 Phase 2 Validation

**Run these tests:**

1. **Dry run:**
   ```bash
   bcllm --experiment test_exp --execute --dry-run
   # Expected: Configuration validated, no execution
   ```

2. **Output formats:**
   ```bash
   bcllm --export-results run-001 --output csv
   bcllm --export-results run-001 --output markdown
   # Expected: CSV and Markdown output
   ```

3. **Session resume:**
   ```bash
   # Start review, --save-session, exit
   # Resume: bcllm --resume-session <session_id>
   # Expected: Exact state restored
   ```

4. **Filter by model:**
   ```bash
   bcllm --review-experiment test_exp --filter-by-model gpt-4
   # Expected: Only gpt-4 responses in queue
   ```

5. **Timeout fix:**
   ```bash
   # Run with slow reasoning model
   # Expected: No timeout errors (180s timeout)
   ```

---

## 6. Phase 3: Low Priority (Week 6-8)

**Duration:** 2-3 weeks
**Effort:** ~27 hours
**Priority:** 🟢 LOW (Polish + Documentation)
**Owner:** Technical Writer + Developers

### 6.1 Why Last

These gaps are **nice-to-have enhancements**:
- Documentation gaps (can be addressed incrementally)
- UI customizations (non-breaking changes)
- Debugging enhancements (helpful but not required)
- Error analysis features (optional)

---

### 6.2 Documentation Gaps (CLI-DOC-*)

**Severity:** 🟢 LOW
**Effort:** 8 hours
**Files to Create:**
- `docs/architecture/v2-current/dispatcher.md`
- `docs/architecture/v2-current/mode-system.md`
- `docs/architecture/contracts/configuration-reference.md`
- `docs/architecture/contracts/repository-interface.md`
- `docs/architecture/contracts/error-message-style.md`

**Content:**
- How `bcllm` command invokes modules
- Mode determination logic
- Complete configuration key inventory
- Repository method signatures
- Error message style guide

**Acceptance Criteria:**
- [ ] All documentation gaps filled
- [ ] Examples included for all keys
- [ ] Developer guides complete

---

### 6.3 CLI UX Regressions (CLI-RISK-*)

**Severity:** 🟢 LOW
**Effort:** 10 hours
**Files to Modify:**
- `src/cli/bcllm_execute.py`
- `src/cli/bcllm_experiment.py`
- Other CLI files

**Enhancements:**
- Rich formatting for CLI output
- Enhanced help text with examples
- Error message style guide implementation

**Acceptance Criteria:**
- [ ] CLI output is formatted and colorful
- [ ] Help text includes 5+ examples per module
- [ ] Error messages follow style guide

---

### 6.4 Review UI Enhancements (UI-007 to UI-010)

**Severity:** 🟢 LOW
**Effort:** 10 hours
**Files to Modify:**
- `src/review/review_ui.py`

**Enhancements:**
- Custom classification labels
- Review queue reordering
- Keyboard shortcuts customization
- Theme options (dark/light)

**Acceptance Criteria:**
- [ ] Custom classification labels supported
- [ ] Review queue can be reordered
- [ ] Keyboard shortcuts customizable
- [ ] Theme options available

---

### 6.5 Error Handling Enhancements (ERR-008 to ERR-010)

**Severity:** 🟢 LOW
**Effort:** 4 hours
**Files to Modify:**
- `src/core/execution_engine.py`
- `src/db/schema.py`

**Enhancements:**
- Stack trace capture
- Error details JSON column
- ErrorCategory enum

**Acceptance Criteria:**
- [ ] Stack traces captured for debugging
- [ ] Error details stored as JSON
- [ ] ErrorCategory enum for grouping

---

### 6.6 Logging Enhancements (LOG-016 to LOG-018)

**Severity:** 🟢 LOW
**Effort:** 3 hours
**Files to Modify:**
- `src/utils/logging_config.py`

**Enhancements:**
- Debug mode improvements
- Configuration resolution logging
- Error response body preservation

**Acceptance Criteria:**
- [ ] Debug mode enhanced
- [ ] Configuration resolution logged
- [ ] Error response bodies preserved

---

### 6.7 Phase 3 Validation

**Run these tests:**

1. **Documentation review:**
   ```bash
   # Review all documentation files
   # Expected: Clear, complete, with examples
   ```

2. **CLI UX:**
   ```bash
   bcllm --help
   bcllm --experiment --help
   # Expected: Help text with examples
   ```

3. **Review UI enhancements:**
   ```bash
   # Test custom labels, reordering, shortcuts, themes
   # Expected: All enhancements working
   ```

4. **Error enhancements:**
   ```bash
   # Simulate error, check stack trace capture
   # Expected: Stack trace available for debugging
   ```

---

## 7. Dependency Graph

### 7.1 What Must Be Implemented First

**Phase 0 (Foundation):**
```
Logging Infrastructure (LOG-001)
    ↓
Retry Delay Fix (ERR-002)
    ↓
Logging Integration (LOG-009 to LOG-018)
```

**Phase 1 (Core Workflow):**
```
Logging Complete (Phase 0)
    ↓
RetryHandler Integration (ERR-003)
ErrorClassifier Integration (ERR-004)
    ↓
CLI Export (CLI-001)
CLI Add-to-Run (CLI-002)
CLI Complete-Run (CLI-003)
    ↓
Progress Bar (CLI-005)
Review UI English (UI-001)
Review UI Undo (UI-002)
Review UI Batch (UI-003)
```

**Phase 2 (Features):**
```
Phase 1 Complete
    ↓
Dry Run (CLI-004)
Output Formats (CLI-007)
    ↓
Session Resume (UI-004)
Search/Filter (UI-005)
    ↓
Timeout Fix (EXE-001)
Multimodal Verify (EXE-005)
```

**Phase 3 (Polish):**
```
Phase 2 Complete
    ↓
Documentation (CLI-DOC-*)
CLI UX (CLI-RISK-*)
UI Enhancements (UI-007 to UI-010)
Error Enhancements (ERR-008 to ERR-010)
```

---

### 7.2 What Can Be Parallelized

**Phase 0:**
- ❌ Sequential (logging must be first, then retry delay)

**Phase 1:**
- ✅ Parallel:
  - Backend: RetryHandler, ErrorClassifier integration
  - Frontend: Review UI enhancements (English, Undo, Batch)
  - Backend: CLI commands (Export, Add-to-Run, Complete-Run)

**Phase 2:**
- ✅ Parallel:
  - Backend: Dry run, Output formats
  - Full Stack: Session resume, Search/filter
  - Backend: Timeout fix, Multimodal verify

**Phase 3:**
- ✅ Parallel:
  - Technical Writer: Documentation
  - Frontend: CLI UX, UI enhancements
  - Backend: Error enhancements, Logging enhancements

---

### 7.3 Critical Path

**Critical Path (Longest Path):**
```
Phase 0: Logging (18h)
    ↓
Phase 1: RetryHandler + ErrorClassifier (6h) + CLI Commands (8h) + Review UI (14h)
    ↓
Phase 2: Session Resume (6h) + Output Formats (4h)
    ↓
Phase 3: Documentation (8h)
```

**Total Critical Path:** ~54 hours (minimum time to production-ready)

**Non-Critical (Can Be Deferred):**
- Phase 3 enhancements (documentation, UI polish)
- Phase 2 features (session resume, search/filter)
- Some Phase 1 features (batch classification, multi-level undo)

---

## 8. Risk Mitigation

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Logging impacts performance** | Medium | Medium | Use appropriate log levels, profile overhead |
| **Log files fill disk** | Low | Medium | Rotation enabled (10MB, 5 backups), monitor size |
| **Sensitive data in logs** | Medium | High | Do not log API keys or tokens, review log messages |
| **Retry integration introduces bugs** | Medium | High | Comprehensive tests, incremental rollout |
| **Review UI schema changes needed** | Low | High | Verify database schema before session resume implementation |
| **Breaking changes to CLI** | Low | Medium | Backward-compatible implementations, clear migration guide |

---

### 8.2 Mitigation Strategies

**Logging Performance:**
- Use `INFO` level by default (suppresses `DEBUG`)
- Profile logging overhead with realistic workloads
- Consider async handlers if needed (future improvement)

**Disk Space:**
- Rotation enabled by default (10MB, 5 backups = 50MB max)
- Monitor log size during long runs
- Document how to change rotation settings

**Sensitive Data:**
- Code review all log messages for sensitive data
- Do not log API keys, tokens, or full request bodies
- Use structured logging with explicit field names

**Retry Bugs:**
- Write comprehensive unit tests for retry behavior
- Test with simulated failures (timeout, 429, 500)
- Verify delays are applied correctly
- Monitor rate limits during testing

**Schema Changes:**
- Review database schema before implementing session resume
- If schema changes needed, create migration script
- Test migration with production-like data

**CLI Compatibility:**
- Keep existing commands backward-compatible
- Document any breaking changes clearly
- Provide migration guide for users

---

### 8.3 Rollback Plans

**If Phase 0 Fails:**
```bash
# Revert logging changes
git checkout <previous-commit>

# Remove logging configuration
rm src/utils/logging_config.py

# Restore print statements in CLI
git checkout src/cli/
```

**If Phase 1 Fails:**
```bash
# Revert specific phase
git checkout <phase-0-commit> -- src/core/execution_engine.py
git checkout <phase-0-commit> -- src/review/
```

**If Phase 2/3 Fails:**
```bash
# Defer to later sprint
# Document what was learned
# Keep stable implementation
```

---

## 9. Validation Criteria

### 9.1 How to Verify Each Phase is Complete

**Phase 0 Validation:**
- [ ] All components log to file and console
- [ ] Retry delay prevents API abuse (verify with logs)
- [ ] Logs show retry attempts, errors, progress
- [ ] Initialization summary logged
- [ ] Log rotation works (test with large log file)

**Phase 1 Validation:**
- [ ] RetryHandler used by ExecutionEngine (code review)
- [ ] ErrorClassifier used consistently (code review)
- [ ] Export results command works (test export)
- [ ] Incremental workflow restored (test add-to-run, complete-run)
- [ ] Progress bar visible during execution (test execution)
- [ ] English UI available (test with `--language en`)
- [ ] Multi-level undo works (test undo 5+ times)
- [ ] Batch classification works (test multi-select)

**Phase 2 Validation:**
- [ ] Dry run validates without executing (test dry run)
- [ ] Export supports multiple formats (test JSON, CSV, Markdown)
- [ ] Review sessions can be paused/resumed (test session resume)
- [ ] Pending items can be filtered (test filters)
- [ ] Timeout supports slow reasoning models (test with slow model)
- [ ] All MEDIUM gaps closed or accepted (gap report review)

**Phase 3 Validation:**
- [ ] All documentation gaps filled (documentation review)
- [ ] All LOW gaps closed or deferred (gap report review)
- [ ] Final validation passed (comprehensive testing)
- [ ] Production deployment approved (stakeholder sign-off)

---

### 9.2 Testing Requirements

**Unit Tests:**
- [ ] Logging configuration tests
- [ ] Retry delay tests
- [ ] RetryHandler tests
- [ ] ErrorClassifier tests
- [ ] CLI command tests
- [ ] Review UI tests

**Integration Tests:**
- [ ] End-to-end execution test
- [ ] Error handling test
- [ ] Idempotency test
- [ ] Review workflow test

**Performance Tests:**
- [ ] Logging overhead test
- [ ] Retry delay timing test
- [ ] Large log rotation test
- [ ] Review UI performance test (1000+ items)

---

### 9.3 Acceptance Criteria

**Functional Acceptance:**
- [ ] All CRITICAL gaps closed (Phase 0)
- [ ] All HIGH gaps closed (Phase 1)
- [ ] All MEDIUM gaps closed or accepted (Phase 2)
- [ ] All LOW gaps closed or deferred (Phase 3)

**Quality Acceptance:**
- [ ] >80% test coverage
- [ ] No critical bugs
- [ ] No performance regressions
- [ ] Documentation complete

**Operational Acceptance:**
- [ ] Logging provides full visibility
- [ ] Retry behavior is safe (no API abuse)
- [ ] All workflows restored (export, add-to-run, complete-run)
- [ ] Review UI accessible and efficient

---

## 10. Next Steps

### 10.1 Immediate Actions (Phase 0)

**Day 1:**
1. Create `src/utils/logging_config.py` (2-3h)
2. Add retry delay to `ExecutionEngine` (1h)
3. Configure root logger at startup (1h)

**Day 2:**
4. Integrate logging into core components (4-6h)
5. Integrate logging into API layer (3-4h)

**Day 3:**
6. Integrate logging into CLI layer (2-3h)
7. Test and validate logging (3h)

**Validation:**
- Run all Phase 0 validation tests
- Verify no API abuse from retries
- Verify logs show all required information

---

### 10.2 Resource Requirements

**Team Composition:**
- **Phase 0:** 1-2 backend developers
- **Phase 1:** 2 developers (1 backend, 1 frontend/full-stack)
- **Phase 2:** 2 developers (1 backend, 1 full-stack)
- **Phase 3:** 1-2 developers + technical writer

**Infrastructure:**
- Development environment with API access
- Test database (SQLite)
- Log file storage (50MB+ for testing)
- Version control (Git)

**Tools:**
- Python 3.10+
- pytest for testing
- Rich library for CLI/Review UI
- Logging (standard library)

---

### 10.3 Success Metrics

**Quantitative Metrics:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| **Gap Closure** | 100% CRITICAL/HIGH | Gap report |
| **Test Coverage** | >80% | Coverage report |
| **Performance** | No regression | Benchmark comparison |
| **Documentation** | 100% complete | Documentation review |

**Qualitative Metrics:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| **Production Readiness** | Approved | Stakeholder sign-off |
| **User Satisfaction** | Improved | User feedback |
| **Developer Experience** | Improved | Developer feedback |
| **Operational Visibility** | Full | Logging review |

---

### 10.4 Timeline Summary

```
Week 1: Phase 0 (Critical Fixes)
Week 2-3: Phase 1 (High Priority)
Week 4-6: Phase 2 (Medium Priority)
Week 7-9: Phase 3 (Low Priority)

Total: 7-11 weeks (~109 hours)
```

**Milestones:**
- **Week 1:** Phase 0 complete — Production-ready foundation
- **Week 3:** Phase 1 complete — Core workflows restored
- **Week 6:** Phase 2 complete — Feature parity achieved
- **Week 9:** Phase 3 complete — Polish and documentation

---

## Appendix A: Gap ID Reference

### Logging System (LOG)
- LOG-001 to LOG-018: 18 gaps

### Error Handling (ERR)
- ERR-001 to ERR-010: 10 gaps

### CLI System (CLI)
- CLI-001 to CLI-015: 15 gaps

### Review UI (UI)
- UI-001 to UI-010: 10 gaps

### Execution Core (EXE)
- EXE-001 to EXE-007: 7 gaps

### Configuration (CFG)
- CFG-001 to CFG-005: 5 gaps

### Database (DB)
- DB-001 to DB-003: 3 gaps

### Answer Parsing (PARSE)
- PARSE-001 to PARSE-005: 5 gaps

**Total:** 73 gaps (56 unique after deduplication)

---

## Appendix B: Files Reference

### Files to Create
- `src/utils/logging_config.py` — Logging infrastructure
- `src/review/localization/pt.json` — Portuguese strings
- `src/review/localization/en.json` — English strings
- `src/review/localization/i18n.py` — Localization framework
- `src/review/session.py` — Session management
- `src/cli/output_formatter.py` — Output formatting
- `src/api/error_collector.py` — Error aggregation (optional)
- `docs/architecture/v2-current/dispatcher.md` — Dispatcher documentation
- `docs/architecture/v2-current/mode-system.md` — Mode system documentation
- `docs/architecture/contracts/configuration-reference.md` — Configuration reference
- `docs/architecture/contracts/repository-interface.md` — Repository interface
- `docs/architecture/contracts/error-message-style.md` — Error message style

### Files to Modify
- `src/main.py` (or entry point) — Add `setup_logging()` call
- `.env.example` — Add `LOG_LEVEL`, `LOG_FILE_PATH`
- `src/core/execution_engine.py` — Add logging, retry delay, integrate RetryHandler/ErrorClassifier
- `src/core/result_writer.py` — Add logging
- `src/core/planner.py` — Add logging
- `src/api/client.py` — Add logging, increase timeout
- `src/api/retry.py` — Add logging
- `src/cli/bcllm_execute.py` — Add logging, export results, dry run, progress bar
- `src/cli/bcllm_experiment.py` — Add logging, enhance help text
- `src/cli/bcllm_run.py` — Add add-to-run, complete-run commands
- `src/cli/bcllm_review.py` — Add language flag, session commands, filters
- `src/review/review_ui.py` — Add i18n, multi-level undo, batch classification

---

## Appendix C: Validation Commands

### Phase 0 Validation
```bash
# Log file creation
python -m src.cli.bcllm_experiment --list-experiments
ls -la ./logs/benchmark.log

# Console output
python -m src.cli.bcllm_experiment --list-experiments

# Debug mode
$env:LOG_LEVEL="DEBUG"
python -m src.cli.bcllm_experiment --list-experiments

# Retry delay
# Check logs for: "Retry attempt 1/3 after 1.00s delay"

# Log rotation
# Generate large log file, verify rotation
```

### Phase 1 Validation
```bash
# Export results
bcllm --export-results run-001 --output-file results.json

# Add-to-run
bcllm --add-to-run run-001 --add-models gpt-4 claude-3

# Complete-run
bcllm --complete-run run-001

# Progress bar
bcllm --experiment test_exp --execute

# English UI
bcllm --review-experiment test_exp --language en

# Multi-level undo
# Classify 5 items, press Z (undo) 5 times

# Batch classification
# Press M, Space (select 3 items), Enter, A
```

### Phase 2 Validation
```bash
# Dry run
bcllm --experiment test_exp --execute --dry-run

# Output formats
bcllm --export-results run-001 --output csv
bcllm --export-results run-001 --output markdown

# Session resume
bcllm --review-experiment test_exp --save-session
bcllm --resume-session <session_id>

# Filter by model
bcllm --review-experiment test_exp --filter-by-model gpt-4

# Timeout fix
# Run with slow reasoning model
```

### Phase 3 Validation
```bash
# Documentation review
# Review all documentation files

# CLI UX
bcllm --help
bcllm --experiment --help

# Review UI enhancements
# Test custom labels, reordering, shortcuts, themes

# Error enhancements
# Simulate error, check stack trace capture
```

---

**Document Version:** 1.0
**Last Updated:** 2026-03-29
**Next Review:** After Phase 0 implementation
**Owner:** Technical Lead
**Status:** Actionable

---

## Handoff Report

### Task Report

- **Status**: success
- **Objective Achieved**: Created comprehensive V2 Implementation Plan with all 10 sections, including executive summary, implementation principles, 4-phase roadmap (Phase 0-3), dependency graph, risk mitigation, validation criteria, and next steps.
- **Files Created**:
  - `@docs\architecture\v2-implementation-plan.md` — Complete V2 implementation roadmap (~1800 lines)
- **Files Modified**: none
- **Files Deleted**: none
- **Decisions Made**:
  - Organized by priority (CRITICAL → HIGH → MEDIUM → LOW) — Rationale: Matches severity-based implementation order
  - Included detailed implementation code snippets — Rationale: Enables immediate implementation without reference hopping
  - Added validation commands for each phase — Rationale: Clear acceptance criteria
  - Included effort estimates per gap — Rationale: Enables sprint planning
- **Validation**: skipped (document creation, no code changes)
- **Validation Output**: N/A
- **Errors**: none
- **Scope Deviations**: none

### Downstream Context

- **Key Interfaces Introduced**: Gap ID naming convention (DOMAIN-NNN format) for tracking across phases
- **Patterns Established**:
  - Phased rollout by priority (Phase 0-3)
  - Dependency-aware implementation ordering
  - Validation commands for each phase
- **Integration Points**:
  - References all 8 domain adaptation plans
  - References consolidated gap analysis (99-consolidated-gap-analysis.md)
  - Future implementation should reference gap IDs from this document
- **Assumptions**:
  - Effort estimates are conservative and may vary
  - Single developer or small team (1-3 people) available
  - No major architectural changes during migration
- **Warnings**:
  - **ERR-002 (retry delay missing) is CRITICAL** — Must be fixed immediately to prevent API abuse
  - Logging is a prerequisite for debugging all other phases — Implement first
  - Review UI enhancements (UI-002, UI-003) may require database schema changes — Verify before implementation
