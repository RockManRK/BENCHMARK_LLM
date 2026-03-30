# Legacy Logging System Analysis

**Document Type:** Architectural Extraction (Read-Only)  
**Source:** `src_legacy/utils/logging_config.py`  
**Domain:** Logging / Observability  
**Status:** ✅ Complete  

---

## 1. Overview

The V1 logging system provided comprehensive operational visibility for the benchmark_llm application. It was built on Python's standard `logging` module with custom enhancements for crash-safety and dual-output strategy.

### 1.1 Primary File

| File | Purpose |
|------|---------|
| `src_legacy/utils/logging_config.py` | Main logging configuration module |

### 1.2 Key Characteristics

- **Dual-handler strategy**: File (complete logs) + Console (user-facing only)
- **Crash-safe**: Immediate flushing after every log write
- **Rotation**: 10MB max file size, 5 backup files retained
- **Hierarchical**: Root logger + module loggers + component loggers
- **Configurable**: Log level and path via environment variables

---

## 2. Logging Philosophy

### 2.1 Purpose and Intent

The logging system was designed to serve four distinct purposes:

**1. Operational Visibility**
- Provide real-time visibility into benchmark execution progress
- Enable monitoring of long-running executions without database inspection
- Support progress tracking with milestones (25%, 50%, 75%, 100%)

**2. Debugging and Diagnostics**
- Capture sufficient detail to diagnose failures post-mortem
- Preserve API request/response details for troubleshooting
- Record retry attempts and error propagation chains

**3. Audit and Reproducibility**
- Document exact configuration at initialization
- Record seed values, model variants, and question sets
- Enable reconstruction of execution context months later

**4. User Feedback**
- Distinguish between console output (user-facing) and file logs (debugging)
- Prevent debug spam on console while maintaining complete file logs
- Provide clear initialization summaries for execution context

### 2.2 What Was Considered Important

**High-Value Logging Events:**
- Component initialization (client, engine, writer, planner)
- Configuration resolution (seed, prompts, model parameters)
- Execution milestones (plan start, run start, run complete, plan complete)
- API interactions (request sent, response received, errors)
- Retry attempts with delay information
- Progress milestones (25%, 50%, 75%, 100%)
- Status transitions (run status updates, variant completion)
- All errors and exceptions with full stack traces

**What Was Considered Noise:**
- Individual item execution details (logged at DEBUG level only)
- Randomizer seed resets (logged at DEBUG level)
- Cache operations (logged at DEBUG level)
- Database query details (not logged by default)
- Intermediate calculation results (not logged)

### 2.3 Logging Principles

**Hierarchical Structure:**
- Root logger configured with file and console handlers
- Module loggers created with `logging.getLogger(__name__)`
- Component loggers created with `get_structured_logger(component)`
- All loggers inherit from root, ensuring consistent output

**Dual-Handler Strategy:**
- File handler: Logs everything at configured level (DEBUG by default)
- Console handler: Only shows INFO and above (prevents debug spam)
- Both handlers use same formatter for consistency

**Immediate Flushing:**
- Custom handler classes (`FlushingRotatingFileHandler`, `FlushingStreamHandler`) flush after each write
- Prevents log loss in case of crashes or power failures
- Critical for debugging long-running executions

**Structured Context:**
- Every log message includes timestamp, level, logger name, and message
- Initialization summaries use fixed-width formatting for readability
- Identifiers (experiment, run, model, question) included in relevant messages

---

## 3. Log Levels

### 3.1 Level Hierarchy

The system used Python's standard logging levels:

| Level | Numeric Value | Purpose |
|-------|---------------|---------|
| DEBUG | 10 | Detailed diagnostic information |
| INFO | 20 | General operational events |
| WARNING | 30 | Unexpected but handled events |
| ERROR | 40 | Serious problems that prevented operation |
| CRITICAL | 50 | Unrecoverable errors (not commonly used) |

### 3.2 DEBUG Level Usage

**Purpose:** Detailed diagnostic information not needed for normal operation.

**Typical Events:**
- Component initialization details
- Randomizer seed configuration
- Individual item execution
- API request/response details
- Progress tracking state changes
- Time remaining estimates
- Variant existence checks
- Cache operations
- Run configuration details

**Characteristics:**
- Very verbose
- Only enabled during active debugging
- Often includes internal IDs and technical details
- Not needed for routine monitoring

### 3.3 INFO Level Usage

**Purpose:** General operational events that demonstrate normal operation.

**Typical Events:**
- Component initialization
- Execution flow milestones (plan start, run start, run complete, plan complete)
- API request/response summaries
- Progress milestones (25%, 50%, 75%, 100%)
- Model/variant registration
- Experiment/run creation
- Seed initialization
- Configuration changes
- Retry success/attempts
- Result writing summaries
- Execution phase transitions

**Characteristics:**
- Suitable for routine monitoring
- Shows what happened, not why
- Includes enough context to understand flow
- Default level for production operation

### 3.4 WARNING Level Usage

**Purpose:** Unexpected events that were handled but may indicate problems.

**Typical Events:**
- Non-retryable errors
- Model not found
- Question not found
- Duplicate detection
- Metadata filter issues
- Image not found or invalid format
- HTTP 200 with error in body
- Potential error in response content
- Frozen experiment protocol mismatch
- Invalid seed value
- Unknown model capabilities

**Characteristics:**
- Something unexpected happened
- System continued operating (handled the issue)
- May warrant investigation later
- Not necessarily a problem requiring immediate action

### 3.5 ERROR Level Usage

**Purpose:** Serious problems that prevented an operation from completing.

**Typical Events:**
- API errors (429, 401, 500, etc.)
- API error response body
- Request timeouts
- Request errors (connection refused)
- Max retries exceeded
- Authentication failures
- Database errors
- Schema file not found
- Configuration parsing errors
- Run failures
- Command failures

**Characteristics:**
- Operation failed
- May be retryable (depending on error type)
- Often accompanied by exception logging
- Requires investigation or automatic recovery

### 3.6 EXCEPTION Logging

**Purpose:** Log full exception stack trace for debugging.

**Usage Pattern:**
```python
try:
    # Operation
except Exception as e:
    logger.exception(f"Operation failed: {e}")
    raise  # or return error code
```

**Characteristics:**
- Always includes full stack trace
- Used in catch blocks before re-raising or returning error
- Critical for post-mortem debugging
- Logged at ERROR level with stack trace

---

## 4. Configuration

### 4.1 Configuration Mechanism

Logging configuration was managed through the `LoggingConfig` class and `setup_logging()` function.

**Configuration Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `log_file_path` | Path | `./logs/benchmark.log` | Path to operational log file |
| `log_level` | str | `"INFO"` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `max_bytes` | int | `10485760` (10 MB) | Maximum file size before rotation |
| `backup_count` | int | `5` | Number of backup log files to keep |

### 4.2 Configuration Source

Logging configuration came from the `Settings` class (pydantic-settings):

**Environment Variables:**
- `LOG_LEVEL`: Logging level (default: "INFO")
- `LOG_FILE_PATH`: Path to log file (default: "./logs/benchmark.log")

**Configuration Flow:**
1. `Settings` class loaded environment variables
2. `BenchmarkRunner` created `LoggingConfig` from settings
3. `setup_logging()` configured root logger with config
4. All module loggers inherited configuration automatically

### 4.3 Global vs Per-Module Configuration

**Global Configuration:**
- Root logger configured with file and console handlers
- All loggers inherited from root
- Single log level applied to entire application
- No per-module log level configuration

**Logger Hierarchy:**
```
root (benchmark_llm)
├── src.main
├── src.api.client
├── src.api.retry
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
├── src.cli.experiment_commands
├── src.cli.review_ui
├── src.utils.progress
├── src.utils.config
├── src.utils.logging_config
└── src.db.schema
```

**Component-Specific Loggers:**
- `get_structured_logger(component)` created child loggers
- Example: `get_structured_logger('startup')` → `benchmark_llm.startup`
- Used for specialized logging (e.g., initialization summaries)
- Inherited all handlers from root

### 4.4 Handler Configuration

**File Handler (FlushingRotatingFileHandler):**
- Type: RotatingFileHandler with automatic flushing
- Level: Configured log level (default: INFO)
- Max size: 10 MB
- Backup count: 5 files
- Encoding: UTF-8
- Delay: False (open file immediately)

**Console Handler (FlushingStreamHandler):**
- Type: StreamHandler with automatic flushing
- Level: INFO (hardcoded, prevented debug spam)
- Output: sys.stdout
- Same formatter as file handler

**Flushing Behavior:**
- Custom handler classes overrode `emit()` method
- Called `flush()` after each log record
- Ensured logs written to disk immediately
- Critical for crash debugging

---

## 5. Structure and Format

### 5.1 Log Format

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
2026-03-28 14:30:15 - INFO - src.main - BenchmarkRunner initialized
2026-03-28 14:30:15 - DEBUG - src.main - Arguments: Namespace(models=['gpt-4'], iterations=3)
2026-03-28 14:30:16 - INFO - src.api.client - OpenRouterClient initialized with base_url=https://openrouter.ai/api/v1
2026-03-28 14:30:16 - INFO - src.core.execution_engine - Starting execution of plan plan-20260328-001
2026-03-28 14:30:17 - INFO - src.api.client - Sending API request: model=openai/gpt-4, max_tokens=2048, temperature=0.7
2026-03-28 14:30:19 - INFO - src.api.client - API response: model=openai/gpt-4, tokens=150, finish_reason=stop, status=200
2026-03-28 14:30:19 - INFO - src.core.execution_engine - Item run-001::var-abc::123 completed: answer=B, correct=True, latency=1200ms
2026-03-28 14:30:20 - INFO - src.utils.progress - Progress: 25/100 (25.0%)
```

### 5.2 Structured Elements

**Fixed-Width Initialization Summary:**
```
============================================================
Benchmark LLM - Initialization
============================================================
Execution mode      : EXPERIMENT MODE
Experiment          : test_exp
Persist data        : YES
Configuration       : FROZEN (config_hash=8f3a9c2e)
System prompt       : You are a helpful assistant.
Seed                : 42
Models              : openai/gpt-4, anthropic/claude-3
Questions           : Q001-Q010 (10 questions)
============================================================
```

**Identifier Patterns:**
- Experiment: `experiment_name` (e.g., "test_exp")
- Run: `run-{timestamp}-{hash}` (e.g., "run-20260328-abc123")
- Plan: `plan-{timestamp}-{hash}` (e.g., "plan-20260328-001-a1b2c3d4")
- Variant: `var-{hash}` (e.g., "var-a1b2c3d4")
- Item: `{run_id}::{variant_id}::{snapshot_id}` (e.g., "run-001::var-abc::123")
- Question: `Q{number}` (e.g., "Q001", "Q010")
- Model: `{provider}/{model}` (e.g., "openai/gpt-4", "anthropic/claude-3")

### 5.3 Message Consistency

**Initialization Messages:**
- Pattern: `"{Component} initialized"`
- Examples:
  - "BenchmarkRunner initialized"
  - "OpenRouterClient initialized with base_url={url}"
  - "ExecutionEngine initialized (NO DB ACCESS)"
  - "Planner initialized"
  - "ResultWriter initialized"

**Execution Messages:**
- Pattern: `"{Action} {entity}: {details}"`
- Examples:
  - "Starting execution of plan {plan_id}"
  - "Executing run {run_id}"
  - "Completed run {run_id}: {count} items executed"
  - "Item {item_id} completed: answer={answer}, correct={correct}, latency={latency}ms"

**API Messages:**
- Pattern: `"{Direction} API {action}: {parameters}"`
- Examples:
  - "Sending API request: model={model}, max_tokens={tokens}, temperature={temp}"
  - "API response: model={model}, tokens={count}, finish_reason={reason}, status={code}"
  - "API error {status}: model={model}, message={message}"

**Error Messages:**
- Pattern: `"{Component} failed: {error}"`
- Examples:
  - "Experiment command failed: {error}"
  - "Run command failed: {error}"
  - "Review failed: {error}"
  - "Export failed: {error}"

---

## 6. Operational Usefulness

### 6.1 Debugging Support

**Failure Diagnosis:**
- Full stack traces logged via `logger.exception()`
- Error response bodies preserved in logs
- Retry attempts logged with delay and reason
- API request parameters logged for reproduction

**Example Debugging Flow:**
1. Check console output for high-level error message
2. Open log file for detailed error with stack trace
3. Find API request that triggered error (logged at INFO level)
4. Check API response body (logged at ERROR level)
5. Trace retry attempts (logged at INFO level)
6. Identify root cause from stack trace

### 6.2 Long-Running Execution Support

**Progress Tracking:**
- Progress logged at 25% milestones (25%, 50%, 75%, 100%)
- Time remaining estimates logged at DEBUG level
- Model and iteration switches logged at INFO level
- Execution status included run, model, iteration, count, percentage, ETA

**Monitoring Without Database:**
- All execution outcomes logged (answer, correctness, latency)
- Run status updates logged
- Variant completion logged
- Final summary logged (responses written, errors written, runs updated)

**Crash Recovery:**
- Immediate flushing prevented log loss
- Last completed item identifiable from logs
- Partial execution state reconstructable from logs
- Retry state preserved in logs

### 6.3 Failure Diagnosis

**Error Classification:**
- Retryable vs non-retryable errors distinguished
- Error types logged (authentication, rate_limit, server_error, etc.)
- HTTP status codes logged
- Error response bodies preserved

**Error Propagation Chain:**
1. API client logs error at ERROR level
2. Retry handler logs retry attempt at INFO level
3. Execution engine catches exception, logs at EXCEPTION level
4. Result writer logs error write at INFO level
5. Run manager updates run status, logs at INFO level

### 6.4 Log Rotation and Retention

**Rotation Policy:**
- Max file size: 10 MB
- Backup count: 5 files
- Total retention: ~50 MB of logs
- Rotation triggered when file exceeds max_bytes

**File Naming:**
- Current: `benchmark.log`
- Backup 1: `benchmark.log.1`
- Backup 2: `benchmark.log.2`
- Backup 3: `benchmark.log.3`
- Backup 4: `benchmark.log.4`
- Backup 5: `benchmark.log.5` (oldest, deleted on next rotation)

**Retention Implications:**
- Long-running executions could lose old logs
- Critical to monitor log size during multi-day runs
- No automatic log archival (manual process required)
- No log aggregation or centralization

---

## 7. Key Functions

### 7.1 `LoggingConfig` Class

Encapsulates all logging configuration parameters with validation.

```python
class LoggingConfig:
    def __init__(
        self,
        log_file_path: Path,
        log_level: str = DEFAULT_LOG_LEVEL,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
    ) -> None:
        # Validates and stores configuration
```

### 7.2 `setup_logging()` Function

Configures the root logger with file and console handlers.

```python
def setup_logging(config: LoggingConfig) -> None:
    # Configures root logger with rotating file handler and console handler
    # Clears existing handlers to avoid duplicates
    # Ensures log directory exists
```

### 7.3 `get_structured_logger()` Function

Creates component-specific child loggers.

```python
def get_structured_logger(component: str) -> logging.Logger:
    # Returns child logger under root namespace
    # Example: get_structured_logger('api') → benchmark_llm.api
```

### 7.4 `log_initialization_summary()` Function

Logs a standardized initialization header with execution context.

```python
def log_initialization_summary(
    logger: logging.Logger,
    execution_mode: str,
    experiment_name: Optional[str],
    persist_data: bool,
    config_frozen: bool,
    config_hash: Optional[str],
    seed: Optional[int | str],
    models: list[str],
    questions: list[str],
    system_prompt: Optional[str] = None,
) -> None:
    # Logs fixed-width initialization summary
```

### 7.5 `flush_all_handlers()` Function

Forces flush of all logger handlers.

```python
def flush_all_handlers(logger: logging.Logger) -> None:
    # Ensures all pending log messages are written to disk
```

---

## 8. Custom Handler Classes

### 8.1 `FlushingRotatingFileHandler`

A `RotatingFileHandler` that flushes after each write.

```python
class FlushingRotatingFileHandler(RotatingFileHandler):
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()  # Critical for crash-safety
```

### 8.2 `FlushingStreamHandler`

A `StreamHandler` that flushes after each write.

```python
class FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()
```

---

## 9. Summary

The V1 logging system was characterized by:

1. **Hierarchical logger structure** - Root logger with file and console handlers, module loggers inheriting configuration

2. **Dual-handler strategy** - File handler logged everything at configured level, console handler showed only INFO and above

3. **Standard log levels** - DEBUG, INFO, WARNING, ERROR, CRITICAL with clear usage guidelines

4. **Free-form text format** - Timestamp, level, logger name, message (no JSON or structured logging)

5. **Immediate flushing** - Custom handler classes flushed after each write to prevent log loss

6. **Rich context in messages** - Experiment, run, model, question identifiers included throughout

7. **Comprehensive error logging** - Full stack traces, error response bodies, retry history

8. **Progress tracking** - Milestone logging at 25% intervals with time estimates

9. **Log rotation** - 10 MB max file size, 5 backup files retained

10. **Global configuration** - Single log level applied to entire application, no per-module configuration

---

**Related Documents:**
- `docs/architecture/v2-current/02-logging-system.md` - V2 current state
- `docs/architecture/gap-reports/02-logging-system-gap.md` - Gap analysis
- `docs/architecture/to-be/02-logging-system-architecture.md` - Target architecture
- `docs/architecture/v2-adaptation/02-logging-system-adaptation.md` - Migration plan
