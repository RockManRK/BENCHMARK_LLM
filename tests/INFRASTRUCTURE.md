# Test Infrastructure (Phase 4)

This directory contains the test infrastructure for the benchmark_llm refactoring project.

## Overview

This infrastructure supports **test-first development** for Phases 5+ of the refactoring. It provides:

- Shared fixtures for unit and integration tests
- Factory classes for creating test data
- Minimal pytest configuration
- File size checking (warnings only in Phase 1)

## Directory Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── factories/
│   ├── __init__.py
│   ├── experiment.py              # ExperimentFactory
│   ├── variant.py                 # VariantFactory
│   ├── snapshot.py                # SnapshotFactory
│   └── run.py                     # RunFactory
├── unit/
│   ├── __init__.py
│   └── core/                      # Core domain tests (Phase 5+)
│       └── __init__.py
├── test_infrastructure.py         # Smoke tests (verify infrastructure works)
└── ...                            # Legacy tests (to be migrated/removed)
```

## Fixtures

### `in_memory_db`

Creates an in-memory SQLite database with the TO-BE schema.

```python
def test_repository_crud(in_memory_db):
    """Example: Use in_memory_db for repository tests."""
    cursor = in_memory_db.cursor()
    cursor.execute(
        "INSERT INTO experiments (experiment_id, name, system_prompt, user_prompt) VALUES (?, ?, ?, ?)",
        ("exp-1", "test", "prompt", "prompt"),
    )
    in_memory_db.commit()
    
    cursor.execute("SELECT COUNT(*) FROM experiments")
    assert cursor.fetchone()[0] == 1
```

**Schema includes**:
- `experiments`
- `model_variants`
- `question_snapshots`
- `runs`

### `mock_api_client`

Mocked OpenRouterClient for unit tests.

```python
def test_execution_engine_calls_api(mock_api_client):
    """Example: Use mock_api_client for unit tests."""
    engine = ExecutionEngine(mock_api_client, randomizer, parser)
    results = engine.execute(plan)
    
    # Verify API was called
    assert mock_api_client.chat_completion.called
```

### `randomizer`

Seeded AnswerRandomizer for deterministic tests.

```python
def test_randomizer_shuffles(randomizer):
    """Example: Use randomizer for shuffling tests."""
    options = ['A', 'B', 'C', 'D']
    shuffled = randomizer.shuffle(options)
    
    assert len(shuffled) == 4
    assert set(shuffled) == set(options)
```

### `parser`

AnswerParser instance for parsing tests.

```python
def test_parser_extracts_answer(parser):
    """Example: Use parser for answer extraction tests."""
    result = parser.parse("The answer is (B).")
    
    assert result.selected_answer == 'B'
    assert result.confidence == 'clear'
```

## Factories

Factories create dataclass instances (not database records) with sensible defaults.

### ExperimentFactory

```python
from tests.factories import ExperimentFactory

# Basic usage
experiment = ExperimentFactory.create(name="my-experiment")

# With overrides
experiment = ExperimentFactory.create(
    name="custom-exp",
    system_prompt="Custom prompt",
    is_active=False,
)
```

### VariantFactory

```python
from tests.factories import VariantFactory

# Requires experiment_id
variant = VariantFactory.create(
    experiment_id="exp-123",
    model_id="openai/gpt-4",
)
```

### SnapshotFactory

```python
from tests.factories import SnapshotFactory
import json

# Basic usage (auto-generates payload)
snapshot = SnapshotFactory.create(
    experiment_id="exp-123",
    question_id="q1",
)

# With custom payload
payload = json.dumps({
    "stem": "What is 2+2?",
    "options": ["3", "4", "5", "6"],
    "answer_key": "B",
})
snapshot = SnapshotFactory.create(
    experiment_id="exp-123",
    question_id="q1",
    question_payload=payload,
)
```

### RunFactory

```python
from tests.factories import RunFactory

# Pending run (default)
run = RunFactory.create(experiment_id="exp-123")

# Completed run with seed
run = RunFactory.create(
    experiment_id="exp-123",
    seed=42,
    status="completed",
)
```

## Running Tests

### Run all tests

```bash
pytest
```

### Run specific test file

```bash
pytest tests/test_infrastructure.py -v
```

### Run tests by marker

```bash
# Domain rule tests only
pytest -m domain_rule

# Integration tests
pytest -m integration
```

### Run with coverage

```bash
pytest --cov=src --cov-report=term-missing
```

## File Size Checking

Phase 1: Warnings only (exit code 0 always)

```bash
python scripts/check_file_size.py src
python scripts/check_file_size.py tests
```

**Limits**:
- Files: ≤500 lines
- Functions: ≤50 lines
- Classes: ≤200 lines

## Pytest Configuration

See `pytest.ini` for:
- Test discovery paths
- Python path setup
- Markers (domain_rule, contract, integration, slow)
- Verbosity settings

## Test Organization (Phase 5+)

```
tests/
├── unit/
│   ├── core/
│   │   ├── test_planner.py
│   │   ├── test_execution_engine.py
│   │   ├── test_result_writer.py
│   │   └── ...
│   ├── api/
│   │   ├── test_client.py
│   │   ├── test_retry.py
│   │   └── ...
│   ├── db/
│   │   ├── test_repository.py
│   │   └── ...
│   └── cli/
│       ├── test_experiment.py
│       ├── test_model.py
│       └── ...
└── integration/
    ├── test_end_to_end.py
    └── ...
```

## Migration Notes

Legacy tests in the root `tests/` directory will be:
- Migrated to the new structure (if still relevant)
- Removed (if superseded by TO-BE architecture)

The `test_infrastructure.py` file contains smoke tests that verify the infrastructure works. These can be removed once the infrastructure is stable.
