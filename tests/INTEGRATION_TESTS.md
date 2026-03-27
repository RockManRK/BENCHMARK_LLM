# CLI Integration Test Suite

## Overview

This directory contains comprehensive integration tests for the bcllm CLI system. The tests validate end-to-end workflows from experiment creation through execution and review.

## Test Files

### `tests/test_cli_integration.py` (New - Phase 8)

Comprehensive integration test suite with 24 tests covering:

1. **Full Workflow Integration** (3 tests)
   - Complete happy path: create experiment → add models → add questions → create run → execute → verify
   - Multiple models in a single run
   - Multiple runs with isolated results

2. **Model ID Validation** (6 tests)
   - All spec examples from the CLI specification:
     - `google/gemini-3.1-flash-lite-preview`
     - `openai/gpt-4.1-mini`
     - `anthropic/claude-3.5-sonnet`
     - `stepfun/step-3.5-flash:free`
     - `nvidia/nemotron-3-super-120b-a12b:free`
   - Invalid format rejection

3. **Structured Output Persistence** (2 tests)
   - `--structured-output` flag persistence
   - `--vision` flag persistence

4. **Partial Execution Scenarios** (3 tests)
   - Execute specific run with `--run` filter
   - Execute specific questions with `--questions` filter
   - Execute when all items already completed

5. **Idempotent Operations** (3 tests)
   - Re-adding same model variant (rejected)
   - Re-adding same question snapshot (skipped)
   - Re-creating same experiment (rejected)

6. **Error Scenarios** (6 tests)
   - Experiment not found
   - Run not found
   - Invalid question specification
   - Create run without models
   - Create run without questions
   - Variant not in experiment

7. **Cross-Invocation State Persistence** (1 test)
   - Verifies state persists across multiple CLI invocations

## Test Design

### Database Strategy

Tests use **temporary file databases** instead of in-memory databases to properly simulate the CLI's persistent database behavior:

```python
@pytest.fixture
def temp_db_file():
    """Create a temporary database file for CLI tests."""
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield Path(temp_path)
    os.unlink(temp_path)
```

### Database Path Patching

Tests patch the database path to use the temporary file:

```python
def patch_database_path(temp_db_path: Path):
    """Patch get_database_path to use temporary file."""
    from src.cli import database as db_module
    return patch.object(db_module, 'get_database_path', return_value=temp_db_path)
```

### Test Pattern

```python
def test_example(self, temp_db_file, capsys):
    with patch_database_path(temp_db_file):
        # All CLI invocations share the same database file
        with patch.object(sys, "argv", ["bcllm_experiment.py", "--create-experiment", "test"]):
            result = experiment_main()
            assert result == 0
    
    # Verify in database after CLI invocations
    conn = sqlite3.connect(str(temp_db_file))
    # ... assertions
    conn.close()
```

## Running Tests

```bash
# Run all integration tests
pytest tests/test_cli_integration.py -v

# Run specific test class
pytest tests/test_cli_integration.py::TestFullWorkflowIntegration -v

# Run specific test
pytest tests/test_cli_integration.py::TestModelIDValidation::test_model_id_google_gemini -v

# Run with coverage
pytest tests/test_cli_integration.py --cov=src/cli --cov-report=html
```

## Test Markers

All tests are marked with `@pytest.mark.integration` for selective execution:

```bash
# Run only integration tests
pytest -m integration -v

# Skip integration tests (fast unit tests only)
pytest -m "not integration" -v
```

## Exit Codes

All tests verify CLI exit codes:
- `0`: Success
- `1`: Validation error (not found, invalid input, collision)

## Output Validation

Tests validate both:
- **stdout**: Success messages, table output, IDs
- **stderr**: Error messages for failure scenarios

Example:
```python
captured = capsys.readouterr()
assert "created" in captured.out.lower()  # Success message
assert "not found" in captured.err.lower()  # Error message
```

## Database Assertions

Tests verify database state after CLI operations:

```python
conn = sqlite3.connect(str(temp_db_file))
conn.row_factory = sqlite3.Row

resp_repo = ResponseRepository(conn)
responses = resp_repo.list_by_run(run_id)

assert len(responses) == 3
assert responses[0].selected_answer == "B"
assert responses[0].needs_review == False

conn.close()
```

## Coverage Goals

The test suite aims to cover:
- [x] All CLI commands (experiment, model, questions, run, execute)
- [x] All model ID formats from specification
- [x] Flag persistence (structured, vision)
- [x] Filter functionality (run, questions, models)
- [x] Idempotent operations
- [x] Error handling
- [x] Cross-invocation state persistence
- [ ] Review interface (manual review workflow - future)
- [ ] Retry policy configuration (future)

## Known Limitations

1. **No real API calls**: All API interactions are mocked
2. **No parallel execution**: Tests run sequentially
3. **No review UI testing**: Manual review interface not tested (future)

## Troubleshooting

### "Cannot operate on a closed database"

This error occurs if tests try to use in-memory databases with CLI modules. Always use `temp_db_file` fixture and `patch_database_path()`.

### Test isolation issues

Each test gets its own temporary database file. If tests are failing due to shared state, verify the fixture is creating a new file per test.

### Question ID format

Question IDs are normalized to 3 digits (Q001, Q002, not Q01, Q02). Tests should use the correct format in assertions.
