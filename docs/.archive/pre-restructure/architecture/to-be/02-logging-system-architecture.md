# Logging System Architecture (To-Be)

**Document Type:** Architecture & Contracts  
**Domain:** Logging / Observability  
**Version:** 2.0 (V2 Target)  
**Status:** 📋 Proposed  

---

## 1. Overview

This document defines the target logging architecture for V2, including philosophy, contracts, and design decisions.

### 1.1 Purpose

The V2 logging system provides:
- **Operational visibility** - Real-time insight into execution
- **Debugging support** - Diagnostics for failure analysis
- **Audit trail** - Reproducible execution records
- **Crash recovery** - Crash-safe logging for recovery

### 1.2 Scope

This architecture covers:
- Logging infrastructure (configuration, handlers, formatters)
- Log level semantics and usage guidelines
- Handler contracts (file, console)
- Configuration resolution
- Format contracts
- Integration patterns

---

## 2. Logging Philosophy

### 2.1 Core Principles

**1. Visibility First**
- Every significant event should be logged
- Users should never wonder "what is happening?"
- Execution progress should be observable without database queries

**2. Debugging Support**
- Failures should be diagnosable from logs alone
- API request/response details should be preserved
- Retry history should be complete

**3. Audit Trail**
- Execution context should be reconstructable months later
- Configuration should be auditable
- Seed, models, questions should be logged

**4. Crash-Safety**
- Logs should survive crashes and power failures
- Immediate flushing after each write
- Last completed item should be identifiable

**5. Separation of Concerns**
- File logs: Complete debugging information
- Console logs: User-facing operational output
- Different levels for different audiences

### 2.2 What Gets Logged

**High-Value Events (INFO level):**
- Component initialization
- Execution milestones (plan start, run start, run complete)
- API request/response summaries
- Progress milestones (25%, 50%, 75%, 100%)
- Configuration changes
- Retry attempts and outcomes
- Error summaries

**Diagnostic Details (DEBUG level):**
- Component initialization details
- Individual item execution
- API request/response bodies
- Progress tracking state
- Time estimates
- Cache operations
- Randomizer state

**Unexpected Events (WARNING level):**
- Non-retryable errors
- Missing resources (models, questions, images)
- Duplicate detection
- Invalid formats
- Configuration mismatches

**Failures (ERROR level):**
- API errors (status codes, response bodies)
- Request timeouts
- Max retries exceeded
- Authentication failures
- Database errors
- Command failures

**Exception Details (ERROR + stack trace):**
- Full stack traces for caught exceptions
- Error propagation chain
- Context at time of failure

### 2.3 What Does NOT Get Logged

**Considered Noise:**
- Individual calculation results (unless DEBUG)
- Intermediate state (unless DEBUG)
- Database query details (unless DEBUG)
- Cache hits (unless DEBUG)
- Successful existence checks (unless DEBUG)

---

## 3. Log Levels

### 3.1 Level Hierarchy

V2 uses Python's standard logging levels:

| Level | Numeric | Purpose | When to Use |
|-------|---------|---------|-------------|
| DEBUG | 10 | Detailed diagnostics | Debugging, verbose internal state |
| INFO | 20 | Operational events | Normal operation, milestones |
| WARNING | 30 | Unexpected but handled | Handled issues, may need investigation |
| ERROR | 40 | Operation failures | Failed operations, retryable errors |
| CRITICAL | 50 | Unrecoverable errors | System cannot continue (rarely used) |

### 3.2 DEBUG Level Contract

**Purpose:** Detailed diagnostic information for active debugging.

**When to Use:**
- Component initialization details
- Individual item execution (each question execution)
- API request/response full details
- Progress tracking state changes
- Time remaining estimates
- Cache operations (set, get, clear)
- Randomizer seed configuration
- Variant existence checks
- Run configuration details

**Example Messages:**
```
DEBUG - src.api.client - Sending chat completion request to /chat/completions
DEBUG - src.api.client - Request body: {"model": "openai/gpt-4", "messages": [...], "max_tokens": 2048}
DEBUG - src.api.client - Received response: id=chatcmpl-123, tokens=150
DEBUG - src.core.randomizer - Randomizer set seed=42 for run-001
DEBUG - src.utils.progress - Progress tracking started for run-001: total=100
DEBUG - src.utils.progress - Time remaining estimate: 120.5s (50 items at 0.42/s)
DEBUG - src.core.execution_engine - Executing item run-001::var-abc::123
```

**Characteristics:**
- Very verbose
- Only enabled during active debugging
- Includes internal IDs and technical details
- Not needed for routine monitoring

### 3.3 INFO Level Contract

**Purpose:** General operational events demonstrating normal operation.

**When to Use:**
- Component initialization (summary only)
- Execution milestones
  - Plan execution start
  - Run execution start
  - Run completion
  - Plan execution completion
- API request/response summaries
- Progress milestones (25%, 50%, 75%, 100%)
- Model/variant registration
- Experiment/run creation
- Seed initialization
- Configuration changes (from CLI)
- Retry success
- Retry attempts (with count and reason)
- Result writing summaries
- Execution phase transitions

**Example Messages:**
```
INFO - src.core.execution_engine - Starting execution of plan plan-20260329-001
INFO - src.core.execution_engine - Executing run run-001
INFO - src.api.client - Sending API request: model=openai/gpt-4, max_tokens=2048, temperature=0.7
INFO - src.api.client - API response: model=openai/gpt-4, tokens=150, finish_reason=stop, status=200
INFO - src.core.execution_engine - Item run-001::var-abc::123 completed: answer=B, correct=True, latency=1200ms
INFO - src.utils.progress - Progress: 25/100 (25.0%)
INFO - src.api.retry - Retry attempt 1/3 after 1.00s delay due to: Rate limit exceeded
INFO - src.api.retry - Operation succeeded after 1 retry attempt(s)
INFO - src.core.result_writer - Write completed: 50 responses, 2 errors, 0 responses skipped, 1 runs updated
INFO - src.core.execution_engine - Completed run run-001: 50 items executed
INFO - src.core.execution_engine - Execution completed: 150 total results for plan plan-20260329-001
```

**Characteristics:**
- Suitable for routine monitoring
- Shows what happened, not why
- Includes enough context to understand flow
- Default level for production operation

### 3.4 WARNING Level Contract

**Purpose:** Unexpected events that were handled but may indicate problems.

**When to Use:**
- Non-retryable errors (authentication, invalid request)
- Model not found in provider list
- Question not found in dataset
- Duplicate detection (variant already exists)
- Metadata filter not implemented
- Image not found or invalid format
- HTTP 200 with error in response body
- Potential error in response content
- Frozen experiment protocol mismatch
- Invalid seed value
- Unknown model capabilities

**Example Messages:**
```
WARNING - src.api.client - Non-retryable error: Authentication failed
WARNING - src.api.model_capabilities - Model openai/gpt-4 not found in /v1/models list
WARNING - src.core.planner - Question Q001 not found in dataset, skipping
WARNING - src.db.model_variants - Variant already exists: var-a1b2c3d4, skipping
WARNING - src.api.parser - Potential error in response content: "An error occurred..."
WARNING - src.core.planner - Frozen experiment protocol mismatch for 'test_exp'. CLI settings will override.
WARNING - src.core.randomizer - Invalid seed value: abc, using None
WARNING - src.api.model_capabilities - Unknown model: custom/model, assuming text-only
```

**Characteristics:**
- Something unexpected happened
- System continued operating (handled the issue)
- May warrant investigation later
- Not necessarily a problem requiring immediate action

### 3.5 ERROR Level Contract

**Purpose:** Serious problems that prevented an operation from completing.

**When to Use:**
- API errors (429, 401, 500, etc.)
- API error response body
- Request timeouts
- Request errors (connection refused, DNS failure)
- Max retries exceeded
- Authentication failures
- Database errors (constraint violations, connection lost)
- Schema file not found
- Configuration parsing errors
- Run failures
- Command failures

**Example Messages:**
```
ERROR - src.api.client - API error 429: model=openai/gpt-4, message=Rate limit exceeded
ERROR - src.api.client - Error response body: {"error": {"message": "Rate limit exceeded"}}
ERROR - src.api.client - Request timed out after 180s: model=openai/gpt-4
ERROR - src.api.client - Request error: model=openai/gpt-4, error=Connection refused
ERROR - src.api.retry - Max retries (3) exceeded
ERROR - src.core.execution_engine - Failed to execute item run-001::var-abc::123: Max retries exceeded
ERROR - src.core.execution_engine - {stack trace follows}
```

**Characteristics:**
- Operation failed
- May be retryable (depending on error type)
- Often accompanied by exception logging
- Requires investigation or automatic recovery

### 3.6 EXCEPTION Logging Contract

**Purpose:** Log full exception stack trace for debugging.

**Usage Pattern:**
```python
try:
    result = execute_item(item)
except Exception as e:
    logger.exception(f"Failed to execute item {item.id}: {e}")
    result_writer.write_error(item, e)
```

**When to Use:**
- Command handler failures
- Run command failures
- Review UI failures
- Export failures
- Benchmark failures
- Item execution failures
- Any caught exception that needs debugging

**Characteristics:**
- Always includes full stack trace
- Used in catch blocks before re-raising or returning error
- Critical for post-mortem debugging
- Logged at ERROR level with stack trace

---

## 4. Handler Contracts

### 4.1 Handler Overview

V2 uses a dual-handler strategy:

| Handler | Type | Level | Output | Purpose |
|---------|------|-------|--------|---------|
| File Handler | `FlushingRotatingFileHandler` | Configured (default: INFO) | Log file | Complete audit trail, debugging |
| Console Handler | `FlushingStreamHandler` | INFO | stdout | User-facing operational output |

### 4.2 File Handler Contract

**Type:** `FlushingRotatingFileHandler` (custom class)

**Configuration:**
- **Max Size:** 10 MB (`10 * 1024 * 1024` bytes)
- **Backup Count:** 5 files
- **Encoding:** UTF-8
- **Delay:** False (open file immediately)
- **Flush:** After every log record (crash-safe)

**Behavior:**
- Logs at configured level (default: INFO)
- Rotates when file exceeds 10 MB
- Keeps 5 backup files (`benchmark.log.1` through `benchmark.log.5`)
- Deletes oldest backup on rotation
- Flushes immediately after each write

**File Naming:**
- Current: `benchmark.log`
- Backup 1: `benchmark.log.1` (newest backup)
- Backup 2: `benchmark.log.2`
- Backup 3: `benchmark.log.3`
- Backup 4: `benchmark.log.4`
- Backup 5: `benchmark.log.5` (oldest, deleted on next rotation)

**Implementation:**
```python
class FlushingRotatingFileHandler(RotatingFileHandler):
    """A RotatingFileHandler that flushes after each write."""
    
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()  # Critical for crash-safety
```

### 4.3 Console Handler Contract

**Type:** `FlushingStreamHandler` (custom class)

**Configuration:**
- **Level:** INFO (hardcoded)
- **Output:** `sys.stdout`
- **Flush:** After every log record

**Behavior:**
- Shows INFO, WARNING, ERROR, CRITICAL only
- Suppresses DEBUG (prevents debug spam)
- Same format as file handler
- Flushes immediately after each write

**Rationale:**
- Users see operational output without verbose debug details
- Developers can enable DEBUG in file logs without console spam
- Consistent format between file and console

**Implementation:**
```python
class FlushingStreamHandler(logging.StreamHandler):
    """A StreamHandler that flushes after each write."""
    
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()
```

### 4.4 Handler Configuration Summary

| Aspect | File Handler | Console Handler |
|--------|--------------|-----------------|
| Type | FlushingRotatingFileHandler | FlushingStreamHandler |
| Level | Configured (default: INFO) | INFO (hardcoded) |
| Max Size | 10 MB | N/A |
| Backups | 5 files | N/A |
| Encoding | UTF-8 | N/A |
| Flush | After each write | After each write |
| Output | Log file | stdout |

---

## 5. Configuration

### 5.1 Configuration Mechanism

Logging configuration is managed through the `LoggingConfig` class:

```python
class LoggingConfig:
    """Configuration class for logging setup."""
    
    def __init__(
        self,
        log_file_path: Path,
        log_level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        self.log_file_path = log_file_path
        self.log_level = self._validate_log_level(log_level)
        self.max_bytes = self._validate_max_bytes(max_bytes)
        self.backup_count = self._validate_backup_count(backup_count)
```

### 5.2 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LOG_LEVEL` | `"INFO"` | Global logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE_PATH` | `"./logs/benchmark.log"` | Path to operational log file |

### 5.3 Configuration Resolution

**Order of Precedence:**
1. Environment variable (if set)
2. `.env` file (if exists)
3. Default value

**Resolution Flow:**
```
Application Startup
    ↓
Load Settings (pydantic-settings)
    ↓
Read LOG_LEVEL from environment
Read LOG_FILE_PATH from environment
    ↓
Create LoggingConfig
    ↓
Call setup_logging(config)
    ↓
Root logger configured
```

### 5.4 Configuration Validation

**Log Level Validation:**
- Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Case-insensitive (normalized to uppercase)
- Raises `ValueError` if invalid

**Max Bytes Validation:**
- Must be positive (> 0)
- Raises `ValueError` if not positive

**Backup Count Validation:**
- Must be non-negative (>= 0)
- Raises `ValueError` if negative

---

## 6. Format Contracts

### 6.1 Log Format

**Standard Format:**
```
%(asctime)s - %(levelname)s - %(name)s - %(message)s
```

**Date Format:**
```
%Y-%m-%d %H:%M:%S
```

**Example Output:**
```
2026-03-29 14:30:15 - INFO - src.core.execution_engine - Starting execution of plan plan-20260329-001
2026-03-29 14:30:16 - DEBUG - src.api.client - Sending API request: model=openai/gpt-4, max_tokens=2048
2026-03-29 14:30:18 - INFO - src.api.client - API response: model=openai/gpt-4, tokens=150, finish_reason=stop
2026-03-29 14:30:18 - WARNING - src.api.retry - Retry attempt 1/3 due to: Rate limit exceeded
2026-03-29 14:30:19 - ERROR - src.api.client - API error 429: model=openai/gpt-4, message=Rate limit exceeded
```

### 6.2 Format Elements

| Field | Format | Example | Purpose |
|-------|--------|---------|---------|
| `asctime` | `%Y-%m-%d %H:%M:%S` | `2026-03-29 14:30:15` | Timestamp of log event |
| `levelname` | String | `INFO`, `ERROR` | Log level |
| `name` | String | `src.core.execution_engine` | Logger name (module path) |
| `message` | String | `Starting execution of plan...` | Log message |

### 6.3 Message Format Guidelines

**Initialization Messages:**
- Pattern: `"{Component} initialized"`
- Examples:
  - `"BenchmarkRunner initialized"`
  - `"OpenRouterClient initialized with base_url={url}"`
  - `"ExecutionEngine initialized (NO DB ACCESS)"`

**Execution Messages:**
- Pattern: `"{Action} {entity}: {details}"`
- Examples:
  - `"Starting execution of plan {plan_id}"`
  - `"Executing run {run_id}"`
  - `"Completed run {run_id}: {count} items executed"`

**API Messages:**
- Pattern: `"{Direction} API {action}: {parameters}"`
- Examples:
  - `"Sending API request: model={model}, max_tokens={tokens}, temperature={temp}"`
  - `"API response: model={model}, tokens={count}, finish_reason={reason}, status={code}"`

**Error Messages:**
- Pattern: `"{Component} failed: {error}"` or `"{Error type}: {details}"`
- Examples:
  - `"API error {status}: model={model}, message={message}"`
  - `"Failed to execute item {item_id}: {error}"`

### 6.4 Initialization Summary Format

**Fixed-Width Format:**
```
============================================================
Benchmark LLM - Initialization
============================================================
Execution mode      : {mode} MODE
Experiment          : {experiment_name or 'None'}
Persist data        : {'YES' if persist_data else 'NO'}
Configuration       : {'FROZEN (config_hash={hash})' if frozen else 'MUTABLE (CLI/.env)'}
Seed                : {seed or 'None (original A,B,C,D order)'}
Models              : {comma-separated model list}
Questions           : {question range or list}
============================================================
```

**Example:**
```
============================================================
Benchmark LLM - Initialization
============================================================
Execution mode      : EXPERIMENT MODE
Experiment          : test_exp
Persist data        : YES
Configuration       : FROZEN (config_hash=8f3a9c2e)
Seed                : 42
Models              : openai/gpt-4, anthropic/claude-3
Questions           : Q001-Q010 (10 questions)
============================================================
```

---

## 7. Logger Hierarchy

### 7.1 Logger Structure

```
root (benchmark_llm)
├── src.main
├── src.api.client
├── src.api.retry_handler
├── src.api.parser
├── src.api.error_handler
├── src.api.model_capabilities
├── src.core.execution_engine
├── src.core.result_writer
├── src.core.planner
├── src.core.run_manager
├── src.core.answer_parser
├── src.core.randomizer
├── src.core.error_collector
├── src.cli.bcllm_execute
├── src.cli.bcllm_experiment
├── src.cli.bcllm_run
├── src.cli.bcllm_review
├── src.utils.logging_config
├── src.utils.progress
├── src.utils.config
├── src.db.schema
├── src.db.connection
└── src.validators.*
```

### 7.2 Logger Creation

**Module Loggers:**
```python
import logging

logger = logging.getLogger(__name__)
# Example: __name__ = "src.core.execution_engine"
```

**Component Loggers:**
```python
from src.utils.logging_config import get_structured_logger

logger = get_structured_logger('startup')
# Example: creates "benchmark_llm.startup"
```

### 7.3 Logger Inheritance

All loggers inherit from root:
- Handlers (file + console)
- Log level (if not explicitly set)
- Formatter
- Propagation behavior

**Implications:**
- Configure root logger once at startup
- All module loggers automatically use same handlers
- No need to configure each module separately

---

## 8. Integration Patterns

### 8.1 Component Initialization

**Pattern:**
```python
from src.utils.logging_config import setup_logging, LoggingConfig
from pathlib import Path

def main():
    # Configure logging FIRST
    config = LoggingConfig(
        log_file_path=Path("./logs/benchmark.log"),
        log_level="INFO"
    )
    setup_logging(config)
    
    logger = logging.getLogger(__name__)
    logger.info("Application starting...")
    
    # Rest of application
```

### 8.2 Module Logging

**Pattern:**
```python
# src/core/execution_engine.py
import logging

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def __init__(self):
        logger.info("ExecutionEngine initialized (NO DB ACCESS)")
    
    def execute(self, plan):
        logger.info(f"Starting execution of plan {plan.id}")
        # ... execution logic
```

### 8.3 Error Logging

**Pattern:**
```python
try:
    result = api_client.send_request(messages)
except APIError as e:
    logger.error(f"API error {e.status}: model={model}, message={e.message}")
    logger.error(f"Error response body: {e.response_body}")
    raise
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    raise
```

### 8.4 Progress Logging

**Pattern:**
```python
class ProgressTracker:
    def __init__(self, total: int, run_id: str):
        self.total = total
        self.count = 0
        self.run_id = run_id
        logger = logging.getLogger(__name__)
        logger.info(f"ProgressTracker initialized: total={total}, run={run_id}")
    
    def update(self):
        self.count += 1
        percentage = (self.count / self.total) * 100
        
        # Log milestones
        if self.count % (self.total // 4) == 0:
            logger.info(f"Progress: {self.count}/{self.total} ({percentage:.1f}%)")
```

### 8.5 Initialization Summary

**Pattern:**
```python
from src.utils.logging_config import get_structured_logger, log_initialization_summary

logger = get_structured_logger('startup')

log_initialization_summary(
    logger,
    execution_mode="experiment",
    experiment_name="test_exp",
    persist_data=True,
    config_frozen=True,
    config_hash="8f3a9c2e",
    seed=42,
    models=["openai/gpt-4", "anthropic/claude-3"],
    questions=["Q001", "Q002", "Q003"]
)
```

---

## 9. V2 Improvements Over V1

### 9.1 Context Injection (New)

**Feature:** Automatically include execution context in log messages.

**Implementation:**
```python
class ContextFilter(logging.Filter):
    """Add experiment_id, run_id, model_id to log records."""
    
    def __init__(self, experiment_id=None, run_id=None, model_id=None):
        self.experiment_id = experiment_id
        self.run_id = run_id
        self.model_id = model_id
    
    def filter(self, record):
        record.experiment_id = self.experiment_id or '-'
        record.run_id = self.run_id or '-'
        record.model_id = self.model_id or '-'
        return True

# Usage
filter = ContextFilter(experiment_id="test_exp", run_id="run-001")
logger.addFilter(filter)

# Format with context
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - [exp:%(experiment_id)s run:%(run_id)s] - %(message)s"
```

**Benefits:**
- Automatic context in every log line
- Easier to filter logs by experiment/run
- Better for log aggregation

### 9.2 Per-Module Log Levels (New)

**Feature:** Allow different log levels per module.

**Environment Variables:**
```
LOG_LEVEL=INFO
LOG_LEVEL_SRC_API=DEBUG
LOG_LEVEL_SRC_CORE=INFO
LOG_LEVEL_SRC_CLI=WARNING
```

**Implementation:**
```python
# After root logger setup
logging.getLogger('src.api').setLevel(logging.DEBUG)
logging.getLogger('src.core').setLevel(logging.INFO)
logging.getLogger('src.cli').setLevel(logging.WARNING)
```

**Benefits:**
- Fine-grained control
- Debug API without debug spam from other modules
- Better for troubleshooting specific components

### 9.3 JSON Format Option (New)

**Feature:** Optional JSON format for machine parsing.

**Environment Variable:**
```
LOG_FORMAT=json
```

**JSON Format:**
```json
{
  "timestamp": "2026-03-29T14:30:15",
  "level": "INFO",
  "logger": "src.core.execution_engine",
  "message": "Starting execution of plan plan-20260329-001",
  "context": {
    "experiment_id": "test_exp",
    "run_id": "run-001"
  }
}
```

**Benefits:**
- Machine-parseable
- Better for log aggregation (ELK, Splunk)
- Structured querying

---

## 10. Contracts Summary

### 10.1 LoggingConfig Contract

**Inputs:**
- `log_file_path: Path` - Path to log file
- `log_level: str` - Logging level (default: "INFO")
- `max_bytes: int` - Max file size (default: 10MB)
- `backup_count: int` - Number of backups (default: 5)

**Validation:**
- Log level must be valid (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Max bytes must be positive
- Backup count must be non-negative

**Output:**
- Validated configuration object

### 10.2 setup_logging() Contract

**Inputs:**
- `config: LoggingConfig` - Configuration object

**Effects:**
- Configures root logger
- Adds file handler (FlushingRotatingFileHandler)
- Adds console handler (FlushingStreamHandler)
- Sets log level
- Ensures log directory exists
- Clears existing handlers (avoids duplicates)

**Output:**
- None (configures global state)

### 10.3 get_structured_logger() Contract

**Inputs:**
- `component: str` - Component name (e.g., 'api', 'startup')

**Output:**
- Child logger instance under root namespace

**Example:**
- `get_structured_logger('api')` → logger named `benchmark_llm.api`

### 10.4 Handler Contract

**File Handler:**
- Type: FlushingRotatingFileHandler
- Level: Configured level
- Max size: 10MB
- Backups: 5
- Flush: After each write
- Encoding: UTF-8

**Console Handler:**
- Type: FlushingStreamHandler
- Level: INFO (hardcoded)
- Output: stdout
- Flush: After each write

### 10.5 Format Contract

**Standard Format:**
```
%(asctime)s - %(levelname)s - %(name)s - %(message)s
```

**Date Format:**
```
%Y-%m-%d %H:%M:%S
```

**Requirements:**
- Every log line must include timestamp
- Every log line must include level
- Every log line must include logger name
- Every log line must include message

---

## 11. Validation

### 11.1 Functional Validation

- [ ] `LoggingConfig` validates log level
- [ ] `LoggingConfig` validates max_bytes
- [ ] `LoggingConfig` validates backup_count
- [ ] `setup_logging()` configures root logger
- [ ] File handler created with correct settings
- [ ] Console handler created with INFO level
- [ ] Log directory created if not exists
- [ ] Handlers flush after each write

### 11.2 Integration Validation

- [ ] Module loggers inherit root configuration
- [ ] Component loggers created correctly
- [ ] Log messages appear in file
- [ ] Log messages appear on console (INFO+)
- [ ] DEBUG messages suppressed on console
- [ ] Log rotation works at 10MB
- [ ] Backup files named correctly

### 11.3 Operational Validation

- [ ] Run execution, verify logs appear
- [ ] Change LOG_LEVEL, verify output changes
- [ ] Verify initialization summary
- [ ] Verify progress milestones
- [ ] Verify error logging with stack traces
- [ ] Verify crash-safety (flush behavior)

---

## 12. Related Documents

- `docs/architecture/legacy-analysis/02-logging-system.md` - V1 analysis
- `docs/architecture/v2-current/02-logging-system.md` - V2 current state
- `docs/architecture/gap-reports/02-logging-system-gap.md` - Gap analysis
- `docs/architecture/v2-adaptation/02-logging-system-adaptation.md` - Migration plan
- `docs/architecture/contracts/result-writer.md` - Result Writer contract
- `docs/architecture/contracts/execution-engine.md` - Execution Engine contract

---

**Document History:**
- v1.0 (2026-03-29): Initial architecture proposal
