"""Shared fixtures and helpers for integration tests.

This module provides:
- mock_api_client: Configurable mock API client
- full_experiment_setup: Helper to create experiment with models and snapshots
- Helper functions for parsing CLI output and verifying database state
"""

import pytest
import sqlite3
import sys
from pathlib import Path
from typing import Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# Add src_v2 to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src_v2.db.schema import create_schema
from src_v2.api.client import CompletionResponse


@pytest.fixture
def in_memory_db() -> Generator[sqlite3.Connection, None, None]:
    """Create in-memory SQLite database with full TO-BE schema.
    
    This fixture provides a fresh in-memory database for each test.
    The database is initialized with the full TO-BE schema containing:
    - experiments
    - model_variants
    - question_snapshots
    - runs
    - responses
    - errors
    
    Yields:
        sqlite3.Connection: Database connection with row_factory enabled
    
    Example:
        def test_repository_crud(in_memory_db):
            repo = ExperimentRepository(in_memory_db)
            experiment = repo.create(...)
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    
    # Execute full TO-BE schema
    create_schema(conn)
    
    # Verify tables were created
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = {'experiments', 'model_variants', 'question_snapshots', 'runs', 'responses', 'errors'}
    if not expected_tables.issubset(set(tables)):
        raise RuntimeError(
            f"Schema initialization failed. Expected tables: {expected_tables}, "
            f"got: {tables}"
        )
    
    yield conn
    
    # Cleanup
    try:
        conn.close()
    except Exception:
        pass


@pytest.fixture
def mock_api_client():
    """Create configurable mock API client for integration tests.
    
    This fixture creates a MagicMock with the OpenRouterClient spec,
    pre-configured to return a realistic CompletionResponse.
    
    The mock can be configured to:
    - Return successful responses
    - Raise API errors
    - Simulate timeouts
    - Track call count and arguments
    
    Returns:
        MagicMock: Mocked API client
    
    Example:
        def test_execution_with_api_error(mock_api_client):
            # Configure mock to raise error on first call
            mock_api_client.chat_completion.side_effect = [
                raise_api_error(),
                return_success()
            ]
    """
    from src_v2.api.client import OpenRouterClient
    
    client = MagicMock(spec=OpenRouterClient)
    client.chat_completion = AsyncMock(return_value=CompletionResponse(
        content="The answer is (B).",
        model_id="openai/gpt-4",
        input_tokens=50,
        output_tokens=10,
        latency_ms=500,
    ))
    return client


@pytest.fixture
def full_experiment_setup(in_memory_db):
    """Helper fixture to create a complete experiment setup.
    
    This fixture creates:
    - An experiment
    - One or more model variants
    - Question snapshots
    - A run in pending status
    
    Returns:
        dict: Contains IDs for all created entities
    
    Example:
        def test_full_workflow(full_experiment_setup, in_memory_db):
            exp_id = full_experiment_setup['experiment_id']
            run_id = full_experiment_setup['run_id']
            # Use IDs for further testing
    """
    from src_v2.db.repository import (
        ExperimentRepository,
        VariantRepository,
        SnapshotRepository,
        RunRepository,
    )
    import json
    import uuid
    
    exp_repo = ExperimentRepository(in_memory_db)
    var_repo = VariantRepository(in_memory_db)
    snap_repo = SnapshotRepository(in_memory_db)
    run_repo = RunRepository(in_memory_db)
    
    # Create experiment
    experiment_id = f"exp_{uuid.uuid4().hex[:8]}"
    from src_v2.db.models import Experiment
    experiment = Experiment(
        experiment_id=experiment_id,
        name="test-experiment",
        description="Test experiment for integration tests",
        config_json="{}",
        config_hash="",
        system_prompt="You are a helpful assistant.",
        user_prompt="Answer the following question.",
    )
    exp_repo.save(experiment)
    
    # Add model variant
    variant_id = f"var_{uuid.uuid4().hex[:8]}"
    from src_v2.db.models import ModelVariant
    variant = ModelVariant(
        variant_id=variant_id,
        experiment_id=experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
        reasoning_mode="off",
        reasoning_effort=None,
        max_output_tokens=None,
        vision_enabled=False,
        structured_output=False,
        web_access_enabled=False,
    )
    var_repo.save(variant)
    
    # Add question snapshots
    snapshot_ids = []
    for i in range(1, 4):  # 3 questions by default
        snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
        payload = {
            "stem": f"Question {i} stem",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer_key": "B",
        }
        from src_v2.db.models import QuestionSnapshot
        snapshot = QuestionSnapshot(
            snapshot_id=snapshot_id,
            experiment_id=experiment_id,
            question_id=f"Q{i:02d}",
            question_payload=json.dumps(payload),
        )
        snap_repo.save(snapshot)
        snapshot_ids.append(snapshot_id)
    
    # Create run
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    from src_v2.db.models import Run
    run = Run(
        run_id=run_id,
        experiment_id=experiment_id,
        seed=42,
        status="pending",
    )
    run_repo.save(run)
    
    return {
        'experiment_id': experiment_id,
        'experiment_name': 'test-experiment',
        'variant_id': variant_id,
        'snapshot_ids': snapshot_ids,
        'run_id': run_id,
    }


# =============================================================================
# Helper Functions
# =============================================================================

def extract_run_id(output: str) -> Optional[str]:
    """Parse run ID from CLI output.
    
    Args:
        output: CLI stdout output containing run creation message.
    
    Returns:
        Run ID if found, None otherwise.
    
    Example:
        output = "✓ Run created for 'test-exp' (ID: run_abc123, Seed: 42)"
        run_id = extract_run_id(output)  # Returns "run_abc123"
    """
    import re
    match = re.search(r'ID:\s*(run_\w+)', output)
    if match:
        return match.group(1)
    return None


def extract_experiment_id(output: str) -> Optional[str]:
    """Parse experiment ID from CLI output.
    
    Args:
        output: CLI stdout output containing experiment creation message.
    
    Returns:
        Experiment ID if found, None otherwise.
    """
    import re
    match = re.search(r'ID:\s*(exp_\w+)', output)
    if match:
        return match.group(1)
    return None


def extract_variant_id(output: str) -> Optional[str]:
    """Parse variant ID from CLI output.
    
    Args:
        output: CLI stdout output containing model addition message.
    
    Returns:
        Variant ID if found, None otherwise.
    """
    import re
    match = re.search(r'ID:\s*(var_\w+)', output)
    if match:
        return match.group(1)
    return None


def count_responses(conn: sqlite3.Connection, run_id: str) -> int:
    """Count responses for a specific run.
    
    Args:
        conn: Database connection.
        run_id: Run ID to count responses for.
    
    Returns:
        Number of responses for the run.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM responses WHERE run_id = ?",
        (run_id,)
    )
    return cursor.fetchone()[0]


def count_errors(conn: sqlite3.Connection, run_id: str) -> int:
    """Count errors for a specific run.
    
    Args:
        conn: Database connection.
        run_id: Run ID to count errors for.
    
    Returns:
        Number of errors for the run.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM errors WHERE run_id = ?",
        (run_id,)
    )
    return cursor.fetchone()[0]


def verify_run_status(
    conn: sqlite3.Connection,
    run_id: str,
    expected_status: str
) -> bool:
    """Verify run status matches expected value.
    
    Args:
        conn: Database connection.
        run_id: Run ID to check.
        expected_status: Expected status string.
    
    Returns:
        True if status matches, False otherwise.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM runs WHERE run_id = ?",
        (run_id,)
    )
    row = cursor.fetchone()
    if row is None:
        return False
    return row[0] == expected_status


def get_response_by_ids(
    conn: sqlite3.Connection,
    run_id: str,
    variant_id: str,
    snapshot_id: str
) -> Optional[sqlite3.Row]:
    """Get response by run, variant, and snapshot IDs.
    
    Args:
        conn: Database connection.
        run_id: Run ID.
        variant_id: Variant ID.
        snapshot_id: Snapshot ID.
    
    Returns:
        Response row if found, None otherwise.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM responses
        WHERE run_id = ? AND variant_id = ? AND snapshot_id = ?
    """, (run_id, variant_id, snapshot_id))
    return cursor.fetchone()


def create_mock_api_response(
    content: str = "The answer is (B).",
    model_id: str = "openai/gpt-4",
    input_tokens: int = 50,
    output_tokens: int = 10,
    latency_ms: int = 500,
) -> CompletionResponse:
    """Helper to create mock API responses with custom values.
    
    Args:
        content: Response content.
        model_id: Model identifier.
        input_tokens: Input token count.
        output_tokens: Output token count.
        latency_ms: API latency.
    
    Returns:
        CompletionResponse with specified values.
    """
    return CompletionResponse(
        content=content,
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )


def create_api_error_mock(error_message: str = "API Error"):
    """Create a mock that raises an API error.
    
    Args:
        error_message: Error message to raise.
    
    Returns:
        AsyncMock configured to raise the error.
    """
    from src_v2.api.errors import APIError
    
    async def raise_error(*args, **kwargs):
        raise APIError(error_message)
    
    return AsyncMock(side_effect=raise_error)
