# Legacy Logging System Architecture

**Document Type:** Architectural Extraction (Read-Only)  
**Source:** `src_legacy/` directory  
**Focus:** Logging and observability  
**Purpose:** Document the logging architecture for historical reference

---

## 1. Logging Philosophy

### 1.1 Purpose and Intent

The logging system was designed to serve multiple distinct purposes:

**Operational Visibility:**
- Provide real-time visibility into benchmark execution progress
- Enable monitoring of long-running executions without database inspection
- Support progress tracking with time estimates and milestone reporting

**Debugging and Diagnostics:**
- Capture sufficient detail to diagnose failures after the fact
- Preserve API request/response details for troubleshooting
- Record retry attempts and error propagation chains

**Audit and Reproducibility:**
- Document exact configuration at initialization
- Record seed values, model variants, and question sets
- Enable reconstruction of execution context months later

**User Feedback:**
- Distinguish between console output (user-facing) and file logs (debugging)
- Prevent debug spam on console while maintaining complete file logs
- Provide clear initialization summaries for execution context

### 1.2 What Was Considered Important

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

### 1.3 Logging Principles

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

## 2. Log Levels

### 2.1 Level Hierarchy

The system used Python's standard logging levels:

1. **DEBUG** (10): Detailed diagnostic information
2. **INFO** (20): General operational events
3. **WARNING** (30): Unexpected but handled events
4. **ERROR** (40): Serious problems that prevented operation
5. **CRITICAL** (50): Unrecoverable errors (not commonly used)

### 2.2 DEBUG Level Usage

**Purpose:** Detailed diagnostic information not needed for normal operation.

**Typical Events:**
- Component initialization details (e.g., "ExecutionEngine initialized (NO DB ACCESS)")
- Randomizer seed configuration (e.g., "Randomizer set seed=42")
- Individual item execution (e.g., "Executing item run-001::var-abc::123")
- API request details (e.g., "Sending chat completion request to /chat/completions")
- API response details (e.g., "Received response: id=chatcmpl-123")
- Progress tracking state changes (e.g., "Progress tracking started for run-123")
- Time remaining estimates (e.g., "Time remaining estimate: 120.5s (50 items at 0.42/s)")
- Variant existence checks (e.g., "Variant already exists: var-a1b2c3d4")
- Cache operations (e.g., "Model capabilities cache cleared")
- Run configuration details (e.g., "Run configuration: experiment_id=exp-abc, is_dev=True")

**Characteristics:**
- Very verbose
- Only enabled during active debugging
- Often includes internal IDs and technical details
- Not needed for routine monitoring

### 2.3 INFO Level Usage

**Purpose:** General operational events that demonstrate normal operation.

**Typical Events:**
- Component initialization (e.g., "BenchmarkRunner initialized", "Planner initialized")
- Execution flow milestones:
  - "Starting execution of plan plan-20260318-001"
  - "Executing run run-001"
  - "Completed run run-001: 50 items executed"
  - "Execution completed: 150 total results for plan plan-20260318-001"
- API request summaries (e.g., "Sending API request: model=openai/gpt-4, max_tokens=2048, temperature=0.7")
- API response summaries (e.g., "API response: model=openai/gpt-4, tokens=150, finish_reason=stop, status=200")
- Progress milestones (e.g., "Progress: 25/100 (25.0%)")
- Model/variant registration (e.g., "Registered variant: var-abc123 for model openai/gpt-4")
- Experiment creation (e.g., "Created experiment: test_exp (hash=8f3a9c2e)")
- Run creation (e.g., "Created run run-20260318-abc for experiment test_exp")
- Seed initialization (e.g., "Run initialized with seed: 42 (policy=FIXED)")
- Configuration changes (e.g., "Set model_temperature from CLI: 0.7")
- Retry success (e.g., "Operation succeeded after 1 retry attempt(s)")
- Retry attempts (e.g., "Retry attempt 1/3 after 1.00s delay due to: Rate limit exceeded")
- Result writing summaries (e.g., "Write completed: 50 responses, 2 errors, 0 responses skipped, 1 runs updated")
- Execution phase transitions (e.g., "Switched to model claude-3 (2/3)", "Starting iteration 2/3")
- Execution completion (e.g., "Execution completed for run run-123")

**Characteristics:**
- Suitable for routine monitoring
- Shows what happened, not why
- Includes enough context to understand flow
- Default level for production operation

### 2.4 WARNING Level Usage

**Purpose:** Unexpected events that were handled but may indicate problems.

**Typical Events:**
- Non-retryable errors (e.g., "Non-retryable error: Authentication failed")
- Model not found (e.g., "Model openai/gpt-4 not found in /v1/models list")
- Question not found (e.g., "Question Q001 not found in dataset, skipping")
- Duplicate detection (e.g., "Variant already exists: var-a1b2c3d4, skipping")
- Metadata filter issues (e.g., "Metadata filter 'status=valid' not yet implemented, skipping")
- Image not found (e.g., "Image not found for question Q001: /path/to/missing.png")
- Invalid image format (e.g., "Invalid image format: .bmp. Supported: ['.png', '.jpg', '.jpeg', '.gif', '.webp']")
- HTTP 200 with error in body (e.g., "HTTP 200 with error in body: Provider error")
- Potential error in response content (e.g., "Potential error in response content: An error occurred...")
- Frozen experiment protocol mismatch (e.g., "Frozen experiment protocol mismatch for 'test_exp'. CLI settings will override frozen protocol.")
- Invalid seed value (e.g., "Invalid seed value: abc, using None")
- Run not found (e.g., "Run run-123 not found for status update")
- Unknown model capabilities (e.g., "Unknown model: custom/model, assuming text-only")

**Characteristics:**
- Something unexpected happened
- System continued operating (handled the issue)
- May warrant investigation later
- Not necessarily a problem requiring immediate action

### 2.5 ERROR Level Usage

**Purpose:** Serious problems that prevented an operation from completing.

**Typical Events:**
- API errors (e.g., "API error 429: model=openai/gpt-4, message=Rate limit exceeded")
- API error response body (e.g., "Error response body: {"error": {"message": "Rate limit exceeded"}}")
- Request timeouts (e.g., "Request timed out after 180s: model=openai/gpt-4")
- Request errors (e.g., "Request error: model=openai/gpt-4, error=Connection refused")
- Max retries exceeded (e.g., "Max retries (3) exceeded")
- Authentication failures (e.g., "Authentication failed: Invalid API key")
- Database errors (e.g., "Failed to write response: Constraint violation")
- Schema file not found (e.g., "Schema file not found at /path/to/schema.sql")
- Configuration parsing errors (e.g., "Failed to parse frozen config for 'test_exp'")
- Run failures (e.g., "Run run-123 failed: Database connection lost")
- Command failures (e.g., "Experiment command failed: ValueError: Experiment not found")

**Characteristics:**
- Operation failed
- May be retryable (depending on error type)
- Often accompanied by exception logging
- Requires investigation or automatic recovery

### 2.6 EXCEPTION Logging

**Purpose:** Log full exception stack trace for debugging.

**Usage Pattern:**
```python
try:
    # Operation
except Exception as e:
    logger.exception(f"Operation failed: {e}")
    raise  # or return error code
```

**Typical Events:**
- Command handler failures (e.g., "Experiment command failed: {stack trace}")
- Run command failures (e.g., "Run command failed: {stack trace}")
- Review UI failures (e.g., "Review failed: {stack trace}")
- Export failures (e.g., "Export failed: {stack trace}")
- Benchmark failures (e.g., "Benchmark failed: {stack trace}")
- Item execution failures (e.g., "Failed to execute item run-001::var-abc::123: {stack trace}")

**Characteristics:**
- Always includes full stack trace
- Used in catch blocks before re-raising or returning error
- Critical for post-mortem debugging
- Logged at ERROR level with stack trace

---

## 3. Configuration

### 3.1 Configuration Mechanism

Logging configuration was managed through the `LoggingConfig` class and `setup_logging()` function in `src/utils/logging_config.py`.

**Configuration Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `log_file_path` | Path | `./logs/benchmark.log` | Path to operational log file |
| `log_level` | str | `"INFO"` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `max_bytes` | int | `10485760` (10 MB) | Maximum file size before rotation |
| `backup_count` | int | `5` | Number of backup log files to keep |

### 3.2 Configuration Source

Logging configuration came from the `Settings` class (pydantic-settings):

**Environment Variables:**
- `LOG_LEVEL`: Logging level (default: "INFO")
- `LOG_FILE_PATH`: Path to log file (default: "./logs/benchmark.log")

**Configuration Flow:**
1. `Settings` class loaded environment variables
2. `BenchmarkRunner` created `LoggingConfig` from settings
3. `setup_logging()` configured root logger with config
4. All module loggers inherited configuration automatically

### 3.3 Global vs Per-Module Configuration

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

### 3.4 Handler Configuration

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

## 4. Structure and Format

### 4.1 Log Format

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
2026-03-28 14:30:15 - INFO - src.api.client - OpenRouterClient initialized with base_url=https://openrouter.ai/api/v1
2026-03-28 14:30:16 - INFO - src.core.execution_engine - Starting execution of plan plan-20260328-001
2026-03-28 14:30:16 - INFO - src.core.execution_engine - Executing run run-001
2026-03-28 14:30:17 - INFO - src.api.client - Sending API request: model=openai/gpt-4, max_tokens=2048, temperature=0.7
2026-03-28 14:30:19 - INFO - src.api.client - API response: model=openai/gpt-4, tokens=150, finish_reason=stop, status=200
2026-03-28 14:30:19 - INFO - src.core.execution_engine - Item run-001::var-abc::123 completed: answer=B, correct=True, latency=1200ms
2026-03-28 14:30:20 - INFO - src.utils.progress - Progress: 25/100 (25.0%)
```

### 4.2 Structured Elements

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

**Consistency:**
- All log messages used same format string
- Logger name always included (module path)
- Timestamps always in local time with seconds precision
- No JSON or structured logging (free-form text)

### 4.3 Message Consistency

**Initialization Messages:**
- Pattern: `"{Component} initialized"`
- Examples:
  - "BenchmarkRunner initialized"
  - "OpenRouterClient initialized with base_url={url}"
  - "ExecutionEngine initialized (NO DB ACCESS)"
  - "Planner initialized"
  - "ResultWriter initialized"
  - "ProgressTracker initialized: total={total}, run={run}, model={model}, iteration={iteration}"

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
  - "Benchmark failed: {error}"

---

## 5. Operational Usefulness

### 5.1 Debugging Support

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

**Key Debugging Information:**
- Request payload (model, messages, parameters)
- Response status and body
- Retry count and delays
- Exception stack trace
- Component state at time of failure

### 5.2 Long-Running Execution Support

**Progress Tracking:**
- Progress logged at 25% milestones (25%, 50%, 75%, 100%)
- Time remaining estimates logged at DEBUG level
- Model and iteration switches logged at INFO level
- Execution status included run, model, iteration, count, percentage, ETA

**Progress Log Example:**
```
2026-03-28 14:30:15 - INFO - src.utils.progress - ProgressTracker initialized: total=300, run=run-001, model=openai/gpt-4, iteration=1
2026-03-28 14:30:15 - DEBUG - src.utils.progress - Progress tracking started for run-001
2026-03-28 14:35:20 - INFO - src.utils.progress - Progress: 75/300 (25.0%)
2026-03-28 14:40:25 - INFO - src.utils.progress - Progress: 150/300 (50.0%)
2026-03-28 14:45:30 - INFO - src.utils.progress - Progress: 225/300 (75.0%)
2026-03-28 14:50:35 - INFO - src.utils.progress - Progress complete for run-001: 300 items processed in 1200.0s
```

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

### 5.3 Failure Diagnosis

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

**Example Error Chain:**
```
2026-03-28 14:30:17 - ERROR - src.api.client - API error 429: model=openai/gpt-4, message=Rate limit exceeded
2026-03-28 14:30:17 - ERROR - src.api.client - Error response body: {"error": {"message": "Rate limit exceeded"}}
2026-03-28 14:30:17 - INFO - src.api.retry - Retry attempt 1/3 after 1.00s delay due to: Rate limit exceeded
2026-03-28 14:30:18 - ERROR - src.api.client - API error 429: model=openai/gpt-4, message=Rate limit exceeded
2026-03-28 14:30:18 - INFO - src.api.retry - Retry attempt 2/3 after 2.00s delay due to: Rate limit exceeded
2026-03-28 14:30:19 - ERROR - src.api.client - API error 429: model=openai/gpt-4, message=Rate limit exceeded
2026-03-28 14:30:19 - ERROR - src.api.retry - Max retries (3) exceeded
2026-03-28 14:30:19 - ERROR - src.core.execution_engine - Failed to execute item run-001::var-abc::123: Max retries exceeded
2026-03-28 14:30:19 - ERROR - src.core.execution_engine - {stack trace}
2026-03-28 14:30:19 - INFO - src.core.result_writer - Wrote error: run=run-001, variant=var-abc, question=Q001, error=Max retries exceeded
```

**Post-Mortem Analysis:**
- Full execution flow reconstructable from logs
- Error context preserved (model, question, variant, run)
- Retry history available
- API response bodies available for debugging
- Stack traces preserved for code-level debugging

### 5.4 Log Rotation and Retention

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

## 6. Summary

The legacy logging system was characterized by:

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

This document captures the logging architecture without proposing improvements or comparing to newer implementations.
