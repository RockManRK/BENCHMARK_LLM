# Logging System V2 Adaptation

**Document Type:** Migration Plan  
**Domain:** Logging / Observability  
**Version:** 1.0  
**Status:** 📋 Proposed  

---

## 1. Overview

This document defines the migration plan for implementing the logging system in V2, based on V1 analysis and the target architecture.

### 1.1 Objective

Implement a comprehensive logging system for V2 that:
- Provides operational visibility
- Supports debugging and diagnostics
- Creates an audit trail for reproducibility
- Ensures crash-safety
- Improves upon V1 where appropriate

### 1.2 Scope

This migration covers:
- Creating logging infrastructure (`logging_config.py`)
- Integrating logging into all V2 components
- Replacing print statements with proper logging
- Configuring environment variables
- Testing and validation

### 1.3 Migration Strategy

**Approach:** Incremental integration with validation at each step

**Phases:**
1. Create logging infrastructure
2. Configure root logger at startup
3. Integrate into core components
4. Integrate into API layer
5. Integrate into CLI layer
6. Testing and validation

**Duration:** 14-20 hours estimated

---

## 2. Pre-Migration Checklist

### 2.1 Prerequisites

- [ ] Architecture approved (`docs/architecture/to-be/02-logging-system-architecture.md`)
- [ ] Gap analysis reviewed (`docs/architecture/gap-reports/02-logging-system-gap.md`)
- [ ] V1 analysis understood (`docs/architecture/legacy-analysis/02-logging-system.md`)
- [ ] Development environment ready
- [ ] Branch created for logging implementation

### 2.2 Files to Read Before Implementation

**V1 Reference:**
- `src_legacy/utils/logging_config.py` - Main logging implementation
- `docs/architecture/legacy.ignore/legacy_logging_system.md` - Existing legacy doc

**V2 Context:**
- `docs/architecture/v2-current/02-logging-system.md` - Current state (no logging)
- `docs/architecture/to-be/02-logging-system-architecture.md` - Target architecture

### 2.3 Files That Will Be Created

| File | Purpose |
|------|---------|
| `src/utils/logging_config.py` | Main logging configuration module |

### 2.4 Files That Will Be Modified

| File | Changes |
|------|---------|
| `src/main.py` (or entry point) | Add `setup_logging()` call |
| `.env.example` | Add `LOG_LEVEL`, `LOG_FILE_PATH` |
| `src/core/execution_engine.py` | Add logging throughout |
| `src/core/result_writer.py` | Add logging for write operations |
| `src/core/planner.py` | Add logging for plan generation |
| `src/api/client.py` | Add logging for API operations |
| `src/api/retry_handler.py` | Add logging for retries |
| `src/cli/bcllm_execute.py` | Replace print with logging |
| `src/cli/bcllm_experiment.py` | Replace print with logging |
| Other CLI files | Replace error print with logging |

---

## 3. Migration Steps

### Step 1: Create Logging Infrastructure

**Objective:** Create `src/utils/logging_config.py` based on V1, improved for V2.

**Files Created:**
- `src/utils/logging_config.py`

**Implementation Details:**

1. **Import required modules:**
   ```python
   import logging
   import sys
   from logging.handlers import RotatingFileHandler
   from pathlib import Path
   from typing import Optional
   ```

2. **Define constants:**
   ```python
   DEFAULT_LOG_LEVEL = "INFO"
   DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
   DEFAULT_BACKUP_COUNT = 5
   LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
   DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
   ```

3. **Create custom handler classes:**
   - `FlushingRotatingFileHandler` - RotatingFileHandler with immediate flush
   - `FlushingStreamHandler` - StreamHandler with immediate flush

4. **Create `LoggingConfig` class:**
   - Constructor with validation
   - `_validate_log_level()` method
   - `_validate_max_bytes()` method
   - `_validate_backup_count()` method
   - `__repr__()` method

5. **Create `setup_logging()` function:**
   - Configure root logger
   - Clear existing handlers
   - Create file handler with rotation
   - Create console handler (INFO level)
   - Set formatters
   - Ensure log directory exists

6. **Create `get_structured_logger()` function:**
   - Get root logger
   - Return child logger for component

7. **Create `log_initialization_summary()` function:**
   - Fixed-width format
   - Log execution mode, experiment, seed, models, questions
   - Handle both int and str seed values

8. **Create `flush_all_handlers()` function:**
   - Force flush all handlers for crash-safety

**V2 Improvements to Consider:**
- Add optional JSON format support
- Add context filter for experiment_id/run_id injection
- Add per-module log level support via environment variables

**Validation:**
- [ ] File created successfully
- [ ] No syntax errors
- [ ] Can import module
- [ ] `LoggingConfig` validates correctly
- [ ] `setup_logging()` configures root logger
- [ ] Log file created in correct location
- [ ] Console output works

---

### Step 2: Configure Root Logger at Startup

**Objective:** Integrate `setup_logging()` into V2 application entry point.

**Files Modified:**
- `src/main.py` (or primary entry point)
- `.env.example`

**Implementation Details:**

1. **Add environment variables to `.env.example`:**
   ```bash
   # Logging Configuration
   LOG_LEVEL=INFO
   LOG_FILE_PATH=./logs/benchmark.log
   ```

2. **Update entry point to configure logging:**
   ```python
   from src.utils.logging_config import setup_logging, LoggingConfig
   from pathlib import Path
   import os
   
   def main():
       # Configure logging FIRST (before any other logging calls)
       log_file_path = Path(os.getenv("LOG_FILE_PATH", "./logs/benchmark.log"))
       log_level = os.getenv("LOG_LEVEL", "INFO")
       
       config = LoggingConfig(
           log_file_path=log_file_path,
           log_level=log_level
       )
       setup_logging(config)
       
       logger = logging.getLogger(__name__)
       logger.info("Application starting...")
       
       # Rest of application
   ```

3. **Ensure logging is configured before any other imports** that might log

**Validation:**
- [ ] `.env.example` updated
- [ ] Entry point calls `setup_logging()` early
- [ ] Log file created on application start
- [ ] Console output appears
- [ ] No errors during initialization

---

### Step 3: Integrate Logging into Core Components

**Objective:** Add logging to all core components (execution_engine, result_writer, planner, run_manager).

**Files Modified:**
- `src/core/execution_engine.py`
- `src/core/result_writer.py`
- `src/core/planner.py`
- `src/core/run_manager.py`

**Implementation Pattern:**

```python
# At top of file
import logging

logger = logging.getLogger(__name__)

# In class methods
class ExecutionEngine:
    def __init__(self):
        logger.info("ExecutionEngine initialized (NO DB ACCESS)")
    
    def execute(self, plan):
        logger.info(f"Starting execution of plan {plan.id}")
        # ... execution logic
        
        for item in plan.items:
            logger.debug(f"Executing item {item.id}")
            # ... item execution
            
        logger.info(f"Completed run {run.id}: {count} items executed")
```

**Logging Points by Component:**

#### 3.1 Execution Engine

| Location | Level | Message |
|----------|-------|---------|
| `__init__` | INFO | `"ExecutionEngine initialized (NO DB ACCESS)"` |
| `execute()` start | INFO | `"Starting execution of plan {plan_id}"` |
| Run start | INFO | `"Executing run {run_id}"` |
| Item execution | DEBUG | `"Executing item {item_id}"` |
| Item complete | INFO | `"Item {item_id} completed: answer={answer}, correct={correct}, latency={latency}ms"` |
| Run complete | INFO | `"Completed run {run_id}: {count} items executed"` |
| Plan complete | INFO | `"Execution completed: {total} total results for plan {plan_id}"` |
| Error | ERROR | `"Failed to execute item {item_id}: {error}"` |
| Exception | ERROR | `logger.exception(f"Failed to execute item {item_id}: {e}")` |

#### 3.2 Result Writer

| Location | Level | Message |
|----------|-------|---------|
| `__init__` | INFO | `"ResultWriter initialized"` |
| Write response | DEBUG | `"Writing response: run={run_id}, variant={variant_id}, question={question_id}"` |
| Write complete | INFO | `"Write completed: {responses} responses, {errors} errors, {skipped} skipped"` |
| Write error | ERROR | `"Failed to write response: {error}"` |
| Update run status | DEBUG | `"Updating run {run_id} status to {status}"` |

#### 3.3 Planner

| Location | Level | Message |
|----------|-------|---------|
| `__init__` | INFO | `"Planner initialized"` |
| Generate plan | INFO | `"Generating execution plan for experiment {experiment_name}"` |
| Plan created | INFO | `"Created plan {plan_id} with {item_count} items"` |
| Configuration resolution | DEBUG | `"Resolved configuration: seed={seed}, models={models}"` |
| Warning | WARNING | `"Question {question_id} not found in dataset, skipping"` |

#### 3.4 Run Manager

| Location | Level | Message |
|----------|-------|---------|
| Create run | INFO | `"Created run {run_id} for experiment {experiment_name}"` |
| Update status | DEBUG | `"Updating run {run_id} status from {old} to {new}"` |
| Get run | DEBUG | `"Getting run {run_id}"` |
| Run not found | WARNING | `"Run {run_id} not found"` |

**Validation:**
- [ ] All core components have `import logging`
- [ ] All core components create logger with `logging.getLogger(__name__)`
- [ ] Logging calls added at identified points
- [ ] Run execution, verify logs appear in file
- [ ] Verify log messages are clear and informative

---

### Step 4: Integrate Logging into API Layer

**Objective:** Add logging to all API layer components (client, retry_handler, parser, error_handler).

**Files Modified:**
- `src/api/client.py`
- `src/api/retry_handler.py`
- `src/api/parser.py`
- `src/api/error_handler.py`

**Logging Points by Component:**

#### 4.1 API Client

| Location | Level | Message |
|----------|-------|---------|
| `__init__` | INFO | `"OpenRouterClient initialized with base_url={url}"` |
| Send request | INFO | `"Sending API request: model={model}, max_tokens={tokens}, temperature={temp}"` |
| Request details | DEBUG | `"Request body: {body}"` |
| Response received | INFO | `"API response: model={model}, tokens={count}, finish_reason={reason}, status={code}"` |
| Response details | DEBUG | `"Response body: {body}"` |
| API error | ERROR | `"API error {status}: model={model}, message={message}"` |
| Error body | ERROR | `"Error response body: {body}"` |
| Timeout | ERROR | `"Request timed out after {seconds}s: model={model}"` |

#### 4.2 Retry Handler

| Location | Level | Message |
|----------|-------|---------|
| Retry attempt | INFO | `"Retry attempt {attempt}/{max} after {delay}s delay due to: {reason}"` |
| Retry success | INFO | `"Operation succeeded after {count} retry attempt(s)"` |
| Max retries exceeded | ERROR | `"Max retries ({max}) exceeded"` |
| Non-retryable error | WARNING | `"Non-retryable error: {error}"` |

#### 4.3 Parser

| Location | Level | Message |
|----------|-------|---------|
| Parse response | DEBUG | `"Parsing response: {response_text}"` |
| Parse success | DEBUG | `"Parsed answer: {answer}, confidence: {confidence}"` |
| Parse failure | WARNING | `"Failed to parse answer, confidence: low"` |
| Potential error | WARNING | `"Potential error in response content: {snippet}"` |

#### 4.4 Error Handler

| Location | Level | Message |
|----------|-------|---------|
| Classify error | DEBUG | `"Classifying error: {error_type}"` |
| Retryable error | DEBUG | `"Error classified as retryable: {error_type}"` |
| Non-retryable error | WARNING | `"Error classified as non-retryable: {error_type}"` |
| Handle error | ERROR | `"Handling error: {error}"` |

**Validation:**
- [ ] All API components have logging
- [ ] API requests logged at INFO level
- [ ] API responses logged at INFO level
- [ ] API errors logged at ERROR level with response body
- [ ] Retry attempts logged
- [ ] Run execution with API failure, verify error logging

---

### Step 5: Integrate Logging into CLI Layer

**Objective:** Replace print statements with logging in CLI layer, keeping user-facing success messages.

**Files Modified:**
- `src/cli/bcllm_execute.py`
- `src/cli/bcllm_experiment.py`
- `src/cli/bcllm_run.py`
- `src/cli/bcllm_review.py`

**Strategy:**

**Keep as print()** (user-facing success messages):
```python
print(f"✓ Experiment '{experiment.name}' created (ID: {experiment.experiment_id})")
print(f"✓ Model variant '{variant_signature}' added")
print(f"✓ Execution completed")
```

**Replace with logging** (errors, debug, operational):
```python
# Before (error)
print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)

# After (error)
logger.error(f"Experiment not found: {args.experiment}")
print(f"Error: {e}", file=sys.stderr)  # Keep user-facing message

# Before (debug/operational)
print(f"  ({filtered_count} questions filtered out)")

# After (debug)
logger.debug(f"Filtered out {filtered_count} questions")
```

**Logging Points by File:**

#### 5.1 bcllm_execute

| Location | Level | Message |
|----------|-------|---------|
| Command start | INFO | `"Execute command started"` |
| Experiment not found | ERROR | `"Experiment not found: {name}"` |
| Invalid question spec | ERROR | `"Invalid question specification: {error}"` |
| Invalid retry policy | ERROR | `"Invalid retry policy: {error}"` |
| No pending items | WARNING | `"No pending items to execute. All items completed."` |
| Execution error | ERROR | `"Execution failed: {error}"` |
| Missing config | ERROR | `"Missing required configuration: {detail}"` |
| Execution report | DEBUG | `"Execution report: {report}"` |

#### 5.2 bcllm_experiment

| Location | Level | Message |
|----------|-------|---------|
| Create experiment | INFO | `"Creating experiment: {name}"` |
| Experiment exists | ERROR | `"Experiment already exists: {name}"` |
| Invalid model ID | ERROR | `"Invalid model ID format: {model_id}"` |
| Variant exists | WARNING | `"Variant already exists: {signature}"` |
| Add questions | INFO | `"Adding questions to experiment {name}"` |
| Question not found | WARNING | `"Question {id} not found in dataset"` |
| Invalid filter | ERROR | `"Invalid filter: {error}"` |

#### 5.3 bcllm_run

| Location | Level | Message |
|----------|-------|---------|
| Create run | INFO | `"Creating run for experiment {name}"` |
| Run exists | ERROR | `"Run already exists: {name}"` |
| Run not found | ERROR | `"Run not found: {name}"` |
| Run command error | ERROR | `"Run command failed: {error}"` |

**Validation:**
- [ ] Error messages use `logger.error()` + user-facing print
- [ ] Debug/operational messages use logging
- [ ] Success messages remain as print()
- [ ] Run commands, verify error logging
- [ ] Verify console output is clean (INFO+ only)

---

### Step 6: Testing and Validation

**Objective:** Comprehensive testing of logging functionality.

**Test Scenarios:**

#### 6.1 Basic Logging Tests

**Test 1: Log file creation**
```bash
# Run any command
python -m src.cli.bcllm_experiment --list-experiment

# Verify log file created
ls -la ./logs/benchmark.log
```

**Expected:** Log file exists with entries

**Test 2: Console output**
```bash
# Run with default LOG_LEVEL=INFO
python -m src.cli.bcllm_experiment --list-experiment
```

**Expected:** Console shows INFO and above, no DEBUG

**Test 3: Debug mode**
```bash
# Run with LOG_LEVEL=DEBUG
$env:LOG_LEVEL="DEBUG"
python -m src.cli.bcllm_experiment --list-experiment
```

**Expected:** Console still shows INFO+, file shows DEBUG+

#### 6.2 Log Level Tests

**Test 4: Change log level**
```bash
# Test different log levels
$env:LOG_LEVEL="WARNING"
python -m src.cli.bcllm_experiment --list-experiment
```

**Expected:** Only WARNING and above logged

#### 6.3 Rotation Tests

**Test 5: Log rotation**
```python
# Generate large log file
import logging
from src.utils.logging_config import setup_logging, LoggingConfig
from pathlib import Path

config = LoggingConfig(
    log_file_path=Path("./logs/test_rotation.log"),
    max_bytes=1024 * 1024,  # 1MB for testing
    backup_count=3
)
setup_logging(config)

logger = logging.getLogger(__name__)
for i in range(10000):
    logger.info(f"Test log message {i} with some extra content to fill space")
```

**Expected:** Log file rotates at 1MB, backups created

#### 6.4 Integration Tests

**Test 6: Full execution**
```bash
# Run a small execution
python -m src.cli.bcllm_execute --experiment test_exp --execute

# Check log file
cat ./logs/benchmark.log
```

**Expected:**
- Initialization summary logged
- Execution milestones logged
- API requests/responses logged
- Progress milestones logged
- Completion summary logged

**Test 7: Error scenario**
```bash
# Run with invalid API key (or no API key)
unset OPENROUTER_API_KEY
python -m src.cli.bcllm_execute --experiment test_exp --execute
```

**Expected:**
- Error logged at ERROR level
- Stack trace logged
- Error response body logged (if available)
- User-facing error message printed

**Test 8: Crash recovery**
```python
# Simulate crash after logging
import logging
from src.utils.logging_config import setup_logging, LoggingConfig, flush_all_handlers
from pathlib import Path

config = LoggingConfig(log_file_path=Path("./logs/crash_test.log"))
setup_logging(config)

logger = logging.getLogger(__name__)
logger.info("Before crash - this should be saved")

# Force flush
flush_all_handlers(logger)

# Simulate crash (don't do this in production!)
import os
os._exit(1)
```

**Expected:** "Before crash" message preserved in log file

#### 6.5 Validation Checklist

- [ ] Log file created on application start
- [ ] Log directory created if not exists
- [ ] Console output shows INFO and above
- [ ] DEBUG suppressed on console
- [ ] Log file contains all levels (DEBUG+)
- [ ] Timestamps present in all log lines
- [ ] Logger names present in all log lines
- [ ] Log level format consistent
- [ ] Initialization summary logged
- [ ] Execution milestones logged
- [ ] API requests/responses logged
- [ ] Errors logged with stack traces
- [ ] Error response bodies logged
- [ ] Retry attempts logged
- [ ] Progress milestones logged
- [ ] Log rotation works
- [ ] Backup files named correctly
- [ ] Flush behavior works (crash-safety)
- [ ] Environment variables respected
- [ ] Per-module log levels work (if implemented)

---

## 4. Post-Migration

### 4.1 Documentation Updates

**Update these files:**
- [ ] `README.md` - Add logging section
- [ ] `.env.example` - Document LOG_LEVEL, LOG_FILE_PATH
- [ ] `docs/architecture/v2-current/02-logging-system.md` - Update to reflect implementation
- [ ] `docs/architecture/TODO.md` - Remove logging TODO

### 4.2 Operational Runbook

**For users:**
- Log file location: `./logs/benchmark.log`
- How to enable debug mode: Set `LOG_LEVEL=DEBUG`
- How to change log file: Set `LOG_FILE_PATH=/path/to/log.log`
- Log rotation: Automatic at 10MB, 5 backups retained
- How to view logs: `cat ./logs/benchmark.log` or `tail -f ./logs/benchmark.log`

### 4.3 Troubleshooting Guide

**Common Issues:**

**Issue: No logs in file**
- Check `LOG_FILE_PATH` environment variable
- Check file permissions
- Check disk space

**Issue: Too much console output**
- Check `LOG_LEVEL` (should be INFO, not DEBUG)
- Console shows INFO+ by default

**Issue: Log file growing too large**
- Check rotation settings (10MB default)
- Check backup count (5 default)
- Consider reducing max_bytes or backup_count

**Issue: Missing log messages**
- Check log level (DEBUG messages need LOG_LEVEL=DEBUG)
- Check logger name (module logger may have different level)
- Check flush behavior (may need `flush_all_handlers()`)

---

## 5. Rollback Plan

If logging implementation causes issues:

### 5.1 Immediate Rollback

1. **Revert code changes:**
   ```bash
   git checkout <previous-commit>
   ```

2. **Remove logging configuration:**
   - Delete `src/utils/logging_config.py`
   - Remove `setup_logging()` call from entry point
   - Remove `LOG_LEVEL`, `LOG_FILE_PATH` from `.env`

3. **Restore print statements:**
   - Revert CLI files to use print()

### 5.2 Partial Rollback

If only certain components have issues:
- Comment out logging in problematic component
- Keep logging in other components
- Fix issues incrementally

### 5.3 Fallback Mode

Consider adding a fallback mode:
```python
try:
    from src.utils.logging_config import setup_logging, LoggingConfig
    # Use logging
except ImportError:
    # Fall back to print statements
    pass
```

---

## 6. Success Criteria

### 6.1 Functional Criteria

- [ ] All 5 logging documents created
- [ ] `src/utils/logging_config.py` implemented
- [ ] Root logger configured at startup
- [ ] All core components use logging
- [ ] All API components use logging
- [ ] CLI errors use logging
- [ ] User-facing messages remain clear

### 6.2 Operational Criteria

- [ ] Log file created and populated
- [ ] Console output clean (INFO+ only)
- [ ] Debug mode works (LOG_LEVEL=DEBUG)
- [ ] Log rotation works
- [ ] Crash-safety verified (flush behavior)

### 6.3 Quality Criteria

- [ ] Log messages clear and informative
- [ ] Log levels used appropriately
- [ ] Error logging includes stack traces
- [ ] API logging includes request/response
- [ ] Initialization summary logged
- [ ] Progress milestones logged

---

## 7. Timeline

| Step | Description | Estimated Time |
|------|-------------|----------------|
| 1 | Create logging infrastructure | 2-3 hours |
| 2 | Configure root logger at startup | 1 hour |
| 3 | Integrate into core components | 4-6 hours |
| 4 | Integrate into API layer | 3-4 hours |
| 5 | Integrate into CLI layer | 2-3 hours |
| 6 | Testing and validation | 2-3 hours |
| **Total** | | **14-20 hours** |

---

## 8. Risks and Mitigations

### Risk 1: Logging impacts performance

**Mitigation:**
- Use async handlers if needed (future improvement)
- Log at appropriate levels (DEBUG for verbose)
- Profile logging overhead

### Risk 2: Log files fill disk

**Mitigation:**
- Rotation enabled (10MB default)
- Limited backups (5 default)
- Monitor log size during long runs

### Risk 3: Sensitive data in logs

**Mitigation:**
- Do not log API keys
- Do not log full request bodies with credentials
- Review log messages for sensitive data

### Risk 4: Breaking existing functionality

**Mitigation:**
- Test thoroughly before deployment
- Keep print statements for user-facing messages
- Rollback plan ready

---

## 9. Related Documents

- `docs/architecture/legacy-analysis/02-logging-system.md` - V1 analysis
- `docs/architecture/v2-current/02-logging-system.md` - V2 current state
- `docs/architecture/gap-reports/02-logging-system-gap.md` - Gap analysis
- `docs/architecture/to-be/02-logging-system-architecture.md` - Target architecture

---

**Document History:**
- v1.0 (2026-03-29): Initial migration plan
