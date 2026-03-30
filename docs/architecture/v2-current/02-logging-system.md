# V2 Logging System - Current State

**Document Type:** Current State Assessment  
**Domain:** Logging / Observability  
**Status:** ⚠️ CRITICAL GAP  

---

## 1. Executive Summary

**The V2 architecture currently has NO logging system.**

This is a **CRITICAL** gap that blocks production use. Without logging:
- No visibility into execution progress
- No debugging capability for failures
- No audit trail for reproducibility
- No crash recovery support
- No operational monitoring

---

## 2. Current State Analysis

### 2.1 Logging Infrastructure

| Component | Status | Notes |
|-----------|--------|-------|
| Logging configuration module | ❌ Missing | No `logging_config.py` in `src/utils/` |
| Root logger setup | ❌ Missing | No centralized logger configuration |
| File handlers | ❌ Missing | No log file output |
| Console handlers | ❌ Missing | No structured console output |
| Log rotation | ❌ Missing | No rotation policy |
| Environment configuration | ❌ Missing | No `LOG_LEVEL` or `LOG_FILE_PATH` support |

### 2.2 Source Code Analysis

**Search Results:**
- `import logging` in `src/`: **0 matches**
- `from logging` in `src/`: **0 matches**
- Files in `src/utils/`: Only `__init__.py` and `variant_signature.py`

**Conclusion:** The V2 codebase has no logging imports or logging infrastructure.

### 2.3 Current Debugging Mechanisms

V2 currently relies on **print statements** for all output:

**Print Statement Usage:**
- 204 `print()` calls found in `src/` directory
- Primary locations:
  - `src/cli/bcllm_execute.py` - Execution output and errors
  - `src/cli/bcllm_experiment.py` - Experiment commands output
  - `src/cli/bcllm_run.py` - Run commands output

**Example Print Patterns:**
```python
# Error output
print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)

# Success output
print(f"✓ Execution completed")
print(f"  Runs executed: {len(report.runs_updated)}")

# Summary output
print(f"  Success: {report.responses_written}")
print(f"  Failed: {report.errors_written}")
```

### 2.4 Problems with Print-Based Output

| Issue | Impact |
|-------|--------|
| No log levels | Cannot filter by severity |
| No timestamps | Cannot correlate events in time |
| No logger names | Cannot identify source module |
| No file output | Cannot review after execution completes |
| No rotation | Cannot manage disk space for long runs |
| No structure | Cannot parse programmatically |
| No flushing control | May lose output on crash |
| No hierarchy | Cannot configure per-module |

---

## 3. What Exists Instead of Logging

### 3.1 CLI Output

All user-facing output goes through `print()` statements:

**Success Messages:**
```python
print(f"✓ Experiment '{experiment.name}' created (ID: {experiment.experiment_id})")
print(f"✓ Model variant '{variant_signature}' added")
print(f"✓ Added question {source_id} (position {question_position})")
print(f"✓ Execution completed")
```

**Error Messages:**
```python
print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
print(f"Error: Invalid model ID format: {model_id}", file=sys.stderr)
print(f"Error: {error}", file=sys.stderr)
```

**Progress Messages:**
```python
print(f"  ({filtered_count} questions filtered out)")
print(f"\nSummary: {created_count} added")
```

### 3.2 Database as Audit Trail

V2 relies on database records for post-execution analysis:

- `responses` table - Execution results
- `errors` table - Execution errors
- `runs` table - Run status

**Limitations:**
- No visibility during execution
- No context for why decisions were made
- No API request/response details
- No retry history
- No stack traces

### 3.3 Return Values

Some functions return status information:

```python
# Execution report
ExecutionReport(
    runs_updated=[...],
    responses_written=50,
    errors_written=2,
    responses_skipped=0
)
```

**Limitations:**
- Only available after execution completes
- No intermediate state
- No diagnostic details

---

## 4. Missing Capabilities

### 4.1 Operational Visibility

**What V1 Had:**
- Real-time progress logging (25%, 50%, 75%, 100%)
- Execution milestone logging (plan start, run start, run complete)
- Model/iteration switch notifications
- Time remaining estimates

**V2 Current State:**
- ❌ No progress logging
- ❌ No milestone tracking
- ❌ No ETA estimates
- ❌ User must wait for completion or check database

### 4.2 Debugging Support

**What V1 Had:**
- DEBUG level for verbose diagnostics
- API request/response logging
- Retry attempt logging
- Full stack traces via `logger.exception()`
- Error response body preservation

**V2 Current State:**
- ❌ No debug mode
- ❌ No API visibility
- ❌ No retry history
- ❌ Stack traces only on unhandled exceptions
- ❌ No error context preservation

### 4.3 Audit Trail

**What V1 Had:**
- Initialization summary with full context
- Configuration resolution logging
- Seed, model, question logging
- Execution mode documentation

**V2 Current State:**
- ❌ No initialization summary
- ❌ No configuration audit
- ❌ Cannot reconstruct execution context months later

### 4.4 Crash Recovery

**What V1 Had:**
- Immediate flushing after each write
- Last completed item identifiable
- Partial execution state in logs

**V2 Current State:**
- ❌ Print statements may buffer
- ❌ No way to identify last completed item
- ❌ Must query database for partial state

### 4.5 Error Diagnosis

**What V1 Had:**
- Error classification (retryable vs non-retryable)
- HTTP status code logging
- Error response body preservation
- Error propagation chain logging

**V2 Current State:**
- ❌ Only final error message
- ❌ No error classification
- ❌ No response body preservation
- ❌ No propagation chain

---

## 5. Impact Assessment

### 5.1 Development Impact

| Scenario | V2 Experience |
|----------|---------------|
| Debugging API failure | Check stderr, no details, no retry history |
| Understanding execution flow | Query database after completion |
| Reproducing issue months later | No context, no configuration log |
| Monitoring long run | No progress, must check database |
| Crash recovery | Manual database inspection |

### 5.2 Production Impact

| Risk | Severity |
|------|----------|
| Cannot diagnose production failures | CRITICAL |
| Cannot monitor execution progress | HIGH |
| Cannot audit configuration | HIGH |
| Cannot recover from crashes efficiently | MEDIUM |
| Cannot parse logs programmatically | MEDIUM |

### 5.3 Comparison Matrix

| Capability | V1 | V2 |
|------------|----|----|
| Logging infrastructure | ✅ Complete | ❌ Missing |
| Log levels | ✅ DEBUG/INFO/WARNING/ERROR | ❌ None |
| File output | ✅ Rotating file handler | ❌ None |
| Console output | ✅ INFO+ only | ⚠️ Print statements |
| Timestamps | ✅ Every log line | ❌ None |
| Logger names | ✅ Module identification | ❌ None |
| Structured format | ✅ Consistent format | ❌ Ad-hoc |
| Immediate flushing | ✅ Crash-safe | ❌ Unknown |
| Log rotation | ✅ 10MB, 5 backups | ❌ None |
| Configuration via env | ✅ LOG_LEVEL, LOG_FILE_PATH | ❌ None |
| Initialization summary | ✅ Fixed-width context | ❌ None |
| Progress tracking | ✅ 25% milestones | ❌ None |
| Error chain logging | ✅ Full propagation | ❌ Final error only |
| Stack traces | ✅ logger.exception() | ⚠️ Only unhandled |
| API visibility | ✅ Request/response | ❌ None |
| Retry history | ✅ All attempts logged | ❌ None |

---

## 6. Print Statement Inventory

### 6.1 By File

| File | Print Count | Purpose |
|------|-------------|---------|
| `src/cli/bcllm_execute.py` | ~40 | Execution output and errors |
| `src/cli/bcllm_experiment.py` | ~60 | Experiment commands |
| `src/cli/bcllm_run.py` | ~30 | Run commands |
| `src/cli/bcllm_review.py` | ~20 | Review UI output |
| Other CLI files | ~54 | Various commands |

### 6.2 By Category

| Category | Count | Examples |
|----------|-------|----------|
| Error messages | ~80 | `print(f"Error: ...", file=sys.stderr)` |
| Success messages | ~40 | `print(f"✓ ...")` |
| Summary output | ~30 | `print(f"  Success: {count}")` |
| Help/usage | ~20 | Usage instructions |
| Debug output | ~34 | Intermediate state |

---

## 7. Files That Need Logging

Based on V2 architecture, these files will need logging integration:

### 7.1 Core Components

| File | Logging Needs |
|------|---------------|
| `src/core/execution_engine.py` | Execution milestones, item completion, errors |
| `src/core/result_writer.py` | Write operations, errors, summaries |
| `src/core/planner.py` | Plan generation, configuration resolution |
| `src/core/run_manager.py` | Run lifecycle, status updates |

### 7.2 API Layer

| File | Logging Needs |
|------|---------------|
| `src/api/client.py` | API requests, responses, errors |
| `src/api/retry_handler.py` | Retry attempts, delays, outcomes |
| `src/api/parser.py` | Parse operations, confidence levels |
| `src/api/error_handler.py` | Error classification, handling |

### 7.3 CLI Layer

| File | Logging Needs |
|------|---------------|
| `src/cli/bcllm_execute.py` | Command execution, validation |
| `src/cli/bcllm_experiment.py` | Experiment commands |
| `src/cli/bcllm_run.py` | Run commands |

### 7.4 Utilities

| File | Logging Needs |
|------|---------------|
| `src/utils/logging_config.py` | **CREATE NEW** - Main logging setup |
| `src/utils/progress.py` | Progress tracking, milestones |

---

## 8. Environment Variables Needed

Based on V1, these environment variables should be added:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LOG_LEVEL` | `"INFO"` | Global logging level |
| `LOG_FILE_PATH` | `"./logs/benchmark.log"` | Log file location |

---

## 9. Conclusion

**V2 has NO logging system.**

All output currently goes through `print()` statements, which provide:
- No log levels
- No timestamps
- No file output
- No rotation
- No structure
- No crash-safety guarantees

This is a **CRITICAL** infrastructure gap that must be addressed before V2 can be considered production-ready.

---

**Related Documents:**
- `docs/architecture/legacy-analysis/02-logging-system.md` - V1 analysis
- `docs/architecture/gap-reports/02-logging-system-gap.md` - Gap analysis
- `docs/architecture/to-be/02-logging-system-architecture.md` - Target architecture
- `docs/architecture/v2-adaptation/02-logging-system-adaptation.md` - Migration plan
