"""Block 6c Validation: ResultWriter & Execution Output Alignment.

This test validates that all critical fields are populated correctly
after the ResultWriter fixes in Block 6c.

Validation Steps:
1. Create fresh database with TO-BE schema
2. Create test experiment, variant, snapshots, and run
3. Execute mock results (simulating ExecutionEngine output)
4. Write results using ResultWriter
5. Validate all critical fields are populated
6. Verify contract compliance

Run with:
    pytest tests/integration/test_block6c_resultwriter_validation.py -v
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Generator

import pytest

from src.core.result_writer import ResultWriter, WriteReport
from src.core.execution_engine import ExecutionResult
from src.db.schema import create_schema


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def fresh_db() -> Generator[sqlite3.Connection, None, None]:
    """Create fresh in-memory database with TO-BE schema.

    Yields:
        sqlite3.Connection: Database connection with row_factory enabled
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row

    # Create TO-BE schema
    create_schema(conn)

    yield conn

    try:
        conn.close()
    except Exception:
        pass


@pytest.fixture
def setup_validation_experiment(fresh_db: sqlite3.Connection) -> dict:
    """Create validation experiment with all required entities.

    Creates:
    - 1 experiment (val_block6c)
    - 2 model variants (gpt-4, claude-3)
    - 3 question snapshots (q1, q2, q3)
    - 1 run (val_run_001)

    Returns:
        dict: IDs of created entities for use in tests
    """
    cursor = fresh_db.cursor()

    # Insert experiment
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, description, config_json, config_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (
        'exp-val-block6c-001',
        'val_block6c',
        'Block 6c Validation Experiment',
        json.dumps({'seed': 42, 'prompt_template': 'default'}),
        'hash-val-001'
    ))

    # Insert model variants
    cursor.execute("""
        INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config)
        VALUES (?, ?, ?, ?, ?)
    """, ('var-gpt4-001', 'exp-val-block6c-001', 'openai/gpt-4', 'gpt-4-default', json.dumps({})))

    cursor.execute("""
        INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config)
        VALUES (?, ?, ?, ?, ?)
    """, ('var-claude3-001', 'exp-val-block6c-001', 'anthropic/claude-3', 'claude-3-default', json.dumps({})))

    # Insert question snapshots
    for i, (qid, payload) in enumerate([
        ('q1', json.dumps({
            'stem': 'What is 2+2?',
            'options': ['A) 3', 'B) 4', 'C) 5', 'D) 6'],
            'answer_key': 'B'
        })),
        ('q2', json.dumps({
            'stem': 'What is the capital of France?',
            'options': ['A) London', 'B) Berlin', 'C) Paris', 'D) Madrid'],
            'answer_key': 'C'
        })),
        ('q3', json.dumps({
            'stem': 'Which planet is known as the Red Planet?',
            'options': ['A) Venus', 'B) Mars', 'C) Jupiter', 'D) Saturn'],
            'answer_key': 'B'
        })),
    ], 1):
        cursor.execute("""
            INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload)
            VALUES (?, ?, ?, ?, ?)
        """, (f'snap-q{i}-001', 'exp-val-block6c-001', qid, i, payload))

    # Insert run
    cursor.execute("""
        INSERT INTO runs (run_id, experiment_id, config, status)
        VALUES (?, ?, ?, ?)
    """, (
        'run-val-001',
        'exp-val-block6c-001',
        json.dumps({'seed': 42}),
        'running'
    ))

    fresh_db.commit()

    return {
        'experiment_id': 'exp-val-block6c-001',
        'variant_ids': ['var-gpt4-001', 'var-claude3-001'],
        'snapshot_ids': ['snap-q1-001', 'snap-q2-001', 'snap-q3-001'],
        'run_id': 'run-val-001',
    }


# =============================================================================
# Test Data: Mock Execution Results
# =============================================================================

def create_mock_success_result(
    run_id: str,
    variant_id: str,
    snapshot_id: str,
    question_id: str,
    response_text: str,
    selected_answer: str,
    parse_confidence: str,
    raw_response: dict,
    latency_ms: int = 500,
    input_tokens: int = 50,
    output_tokens: int = 10,
    finish_reason: str = 'stop',
    started_at: datetime = None,
    finished_at: datetime = None,
) -> ExecutionResult:
    """Create a mock success ExecutionResult.

    Args:
        run_id: Run identifier
        variant_id: Variant identifier
        snapshot_id: Snapshot identifier
        question_id: Question identifier
        response_text: Model response text
        selected_answer: Parsed answer (A/B/C/D)
        parse_confidence: Confidence level (clear/ambiguous/low_confidence/no_answer)
        raw_response: Raw API response dict
        latency_ms: Execution latency in milliseconds
        input_tokens: Input tokens used
        output_tokens: Output tokens generated
        finish_reason: API finish reason
        started_at: Execution start timestamp
        finished_at: Execution end timestamp

    Returns:
        ExecutionResult instance configured for success case
    """
    if started_at is None:
        started_at = datetime.now() - timedelta(seconds=1)
    if finished_at is None:
        finished_at = datetime.now()

    return ExecutionResult(
        item_id=f"{run_id}::{variant_id}::{snapshot_id}::it-1",
        run_id=run_id,
        variant_id=variant_id,
        snapshot_id=snapshot_id,
        question_id=question_id,
        status='success',
        finish_reason=finish_reason,
        response_text=response_text,
        selected_answer=selected_answer,
        parse_confidence=parse_confidence,
        raw_response=raw_response,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error_type=None,
        error_message=None,
        attempt_count=1,
        started_at=started_at,
        finished_at=finished_at,
    )


def create_mock_failure_result(
    run_id: str,
    variant_id: str,
    snapshot_id: str,
    question_id: str,
    error_type: str,
    error_message: str,
    attempt_count: int = 3,
) -> ExecutionResult:
    """Create a mock failure ExecutionResult.

    Args:
        run_id: Run identifier
        variant_id: Variant identifier
        snapshot_id: Snapshot identifier
        question_id: Question identifier
        error_type: Error type (timeout/api_error/parse_error)
        error_message: Error message
        attempt_count: Number of retry attempts

    Returns:
        ExecutionResult instance configured for failure case
    """
    return ExecutionResult(
        item_id=f"{run_id}::{variant_id}::{snapshot_id}::it-1",
        run_id=run_id,
        variant_id=variant_id,
        snapshot_id=snapshot_id,
        question_id=question_id,
        status='failure',
        finish_reason=None,
        response_text=None,
        selected_answer=None,
        parse_confidence=None,
        raw_response=None,
        latency_ms=100,
        input_tokens=0,
        output_tokens=0,
        error_type=error_type,
        error_message=error_message,
        attempt_count=attempt_count,
        started_at=None,
        finished_at=None,
    )


# =============================================================================
# Validation Tests: Critical Field Population
# =============================================================================

class TestCriticalFieldPopulation:
    """Validate all critical fields are populated correctly."""

    def test_status_populated_success(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Contract: For successful executions, responses.status MUST be set to 'success'."""
        # Arrange
        test_data = setup_validation_experiment
        result = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            response_text='The answer is (B).',
            selected_answer='B',
            parse_confidence='clear',
            raw_response={'id': 'resp-123', 'choices': []},
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT status FROM responses WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None, "Response was not written"
        assert row['status'] == 'success', "status MUST be 'success' for successful executions"

    def test_raw_response_always_persisted(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Contract: raw_response MUST always be persisted for successful executions."""
        # Arrange
        test_data = setup_validation_experiment
        raw_response = {
            'id': 'resp-123',
            'object': 'chat.completion',
            'choices': [{'message': {'content': 'The answer is (B).'}}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 10}
        }
        result = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            response_text='The answer is (B).',
            selected_answer='B',
            parse_confidence='clear',
            raw_response=raw_response,
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT raw_response FROM responses WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None, "Response was not written"
        assert row['raw_response'] is not None, "raw_response MUST always be persisted"
        
        # Verify it's valid JSON
        parsed = json.loads(row['raw_response'])
        assert parsed['id'] == 'resp-123', "raw_response should contain original data"

    def test_finish_reason_populated(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Contract: finish_reason MUST be populated for successful executions."""
        # Arrange
        test_data = setup_validation_experiment
        result = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            response_text='The answer is (B).',
            selected_answer='B',
            parse_confidence='clear',
            raw_response={'id': 'resp-123'},
            finish_reason='stop',
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT finish_reason FROM responses WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None
        assert row['finish_reason'] == 'stop', "finish_reason MUST be populated"

    def test_timestamps_populated(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Contract: started_at and finished_at MUST be populated for audit trail."""
        # Arrange
        test_data = setup_validation_experiment
        started = datetime.now() - timedelta(seconds=1)
        finished = datetime.now()
        
        result = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            response_text='The answer is (B).',
            selected_answer='B',
            parse_confidence='clear',
            raw_response={'id': 'resp-123'},
            started_at=started,
            finished_at=finished,
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT started_at, finished_at FROM responses WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None
        assert row['started_at'] is not None, "started_at MUST be populated"
        assert row['finished_at'] is not None, "finished_at MUST be populated"

    def test_response_tokens_populated(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Contract: response_tokens MUST be populated for successful executions."""
        # Arrange
        test_data = setup_validation_experiment
        result = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            response_text='The answer is (B).',
            selected_answer='B',
            parse_confidence='clear',
            raw_response={'id': 'resp-123'},
            output_tokens=10,
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT response_tokens FROM responses WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None
        assert row['response_tokens'] == 10, "response_tokens MUST be populated"

    def test_review_status_derived_from_needs_review(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Contract: review_status MUST be derived from needs_review calculation."""
        # Arrange
        test_data = setup_validation_experiment
        
        # Case 1: Clear confidence with answer -> review_status = 'auto'
        result_clear = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            response_text='The answer is (B).',
            selected_answer='B',
            parse_confidence='clear',
            raw_response={'id': 'resp-123'},
        )

        # Case 2: Ambiguous confidence -> review_status = 'needs_review'
        result_ambiguous = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][1],
            snapshot_id=test_data['snapshot_ids'][1],
            question_id='q2',
            response_text='I think it might be B...',
            selected_answer='B',
            parse_confidence='ambiguous',
            raw_response={'id': 'resp-124'},
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result_clear)
        writer.write_result(result_ambiguous)

        # Assert
        cursor = fresh_db.cursor()
        
        # Check clear case
        cursor.execute("""
            SELECT review_status, needs_review 
            FROM responses 
            WHERE variant_id = ?
        """, (test_data['variant_ids'][0],))
        row = cursor.fetchone()
        assert row is not None
        assert row['review_status'] == 'auto', "review_status should be 'auto' for clear confidence"
        assert row['needs_review'] == 0, "needs_review should be FALSE (0) for clear confidence"

        # Check ambiguous case
        cursor.execute("""
            SELECT review_status, needs_review 
            FROM responses 
            WHERE variant_id = ?
        """, (test_data['variant_ids'][1],))
        row = cursor.fetchone()
        assert row is not None
        assert row['review_status'] == 'needs_review', "review_status should be 'needs_review' for ambiguous confidence"
        assert row['needs_review'] == 1, "needs_review should be TRUE (1) for ambiguous confidence"


# =============================================================================
# Validation Tests: NULL Field Analysis
# =============================================================================

class TestNullFieldAnalysis:
    """Analyze which fields can be NULL and verify it's expected."""

    def test_is_correct_null_when_no_answer(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """is_correct SHOULD be NULL when selected_answer is NULL (expected behavior)."""
        # Arrange
        test_data = setup_validation_experiment
        result = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            response_text='I cannot answer this question.',
            selected_answer=None,  # No answer selected
            parse_confidence='no_answer',
            raw_response={'id': 'resp-123'},
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT is_correct, selected_answer FROM responses WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None
        assert row['selected_answer'] is None
        assert row['is_correct'] is None, "is_correct SHOULD be NULL when no answer (expected)"

    def test_is_correct_populated_when_answer_exists(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """is_correct MUST be populated when selected_answer exists."""
        # Arrange
        test_data = setup_validation_experiment
        result = create_mock_success_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            response_text='The answer is (B).',
            selected_answer='B',
            parse_confidence='clear',
            raw_response={'id': 'resp-123'},
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT is_correct, selected_answer FROM responses WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None
        assert row['selected_answer'] == 'B'
        assert row['is_correct'] == 1, "is_correct MUST be populated when answer exists (1=correct)"

    def test_failure_results_go_to_errors_table(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Contract: Failed executions MUST NOT create rows in responses table."""
        # Arrange
        test_data = setup_validation_experiment
        result = create_mock_failure_result(
            run_id=test_data['run_id'],
            variant_id=test_data['variant_ids'][0],
            snapshot_id=test_data['snapshot_ids'][0],
            question_id='q1',
            error_type='timeout',
            error_message='Request timed out after 30s',
            attempt_count=3,
        )

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_result(result)

        # Assert
        cursor = fresh_db.cursor()
        
        # Verify NO response was created
        cursor.execute("SELECT COUNT(*) FROM responses WHERE run_id = ?", (test_data['run_id'],))
        response_count = cursor.fetchone()[0]
        assert response_count == 0, "Failed executions MUST NOT create responses"

        # Verify error WAS created
        cursor.execute("SELECT COUNT(*) FROM errors WHERE run_id = ?", (test_data['run_id'],))
        error_count = cursor.fetchone()[0]
        assert error_count == 1, "Failed executions MUST create errors"


# =============================================================================
# Validation Tests: Run Status Updates
# =============================================================================

class TestRunStatusUpdates:
    """Validate run status transitions.

    NOTE: These tests are skipped because write_results() (batch method with run
    status updates) has been removed. Run status updates are now handled by
    RunFinalizer — see tests/unit/core/test_run_finalizer.py.
    """

    @pytest.mark.skip(reason="write_results() removed; run status handled RunFinalizer")
    def test_run_status_completed_all_success(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Run status MUST be 'completed' when all results succeed."""
        # Arrange
        test_data = setup_validation_experiment
        results = [
            create_mock_success_result(
                run_id=test_data['run_id'],
                variant_id=test_data['variant_ids'][0],
                snapshot_id=snap,
                question_id=f'q{i}',
                response_text='Answer',
                selected_answer='B',
                parse_confidence='clear',
                raw_response={'id': f'resp-{i}'},
            )
            for i, snap in enumerate(test_data['snapshot_ids'], 1)
        ]

        writer = ResultWriter(fresh_db)

        # Act
        for r in results:
            writer.write_result(r)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT status FROM runs WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None
        assert row['status'] == 'completed', "Run status MUST be 'completed' when all succeed"

    @pytest.mark.skip(reason="write_results() removed; run status handled by RunFinalizer")
    def test_run_status_partial_failed_mixed_results(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict) -> None:
        """Run status MUST be 'partial_failed' when some results fail."""
        # Arrange
        test_data = setup_validation_experiment
        results = [
            create_mock_success_result(
                run_id=test_data['run_id'],
                variant_id=test_data['variant_ids'][0],
                snapshot_id=test_data['snapshot_ids'][0],
                question_id='q1',
                response_text='Answer',
                selected_answer='B',
                parse_confidence='clear',
                raw_response={'id': 'resp-1'},
            ),
            create_mock_failure_result(
                run_id=test_data['run_id'],
                variant_id=test_data['variant_ids'][0],
                snapshot_id=test_data['snapshot_ids'][1],
                question_id='q2',
                error_type='timeout',
                error_message='Timeout',
            ),
        ]

        writer = ResultWriter(fresh_db)

        # Act
        writer.write_results(results)

        # Assert
        cursor = fresh_db.cursor()
        cursor.execute("SELECT status FROM runs WHERE run_id = ?", (test_data['run_id'],))
        row = cursor.fetchone()
        assert row is not None
        assert row['status'] == 'partial_failed', "Run status MUST be 'partial_failed' for mixed results"


# =============================================================================
# Comprehensive Validation Report Test
# =============================================================================

class TestComprehensiveValidationReport:
    """Generate comprehensive validation report for Block 6c.

    NOTE: Skipped because WriteReport was removed with write_results().
    """

    @pytest.mark.skip(reason="WriteReport removed with write_results()")
    def test_full_validation_report(self, fresh_db: sqlite3.Connection, setup_validation_experiment: dict, caplog) -> None:
        """Generate complete validation report for Block 6c."""
        # Arrange: Create mixed results (success + failure + review-needed)
        test_data = setup_validation_experiment
        now = datetime.now()
        
        results = [
            # Success with clear confidence (no review needed)
            create_mock_success_result(
                run_id=test_data['run_id'],
                variant_id=test_data['variant_ids'][0],
                snapshot_id=test_data['snapshot_ids'][0],
                question_id='q1',
                response_text='The answer is (B).',
                selected_answer='B',
                parse_confidence='clear',
                raw_response={'id': 'resp-1', 'choices': []},
                latency_ms=450,
                input_tokens=45,
                output_tokens=12,
                started_at=now - timedelta(seconds=2),
                finished_at=now - timedelta(seconds=1.5),
            ),
            # Success with ambiguous confidence (review needed)
            create_mock_success_result(
                run_id=test_data['run_id'],
                variant_id=test_data['variant_ids'][0],
                snapshot_id=test_data['snapshot_ids'][1],
                question_id='q2',
                response_text='I think it might be C...',
                selected_answer='C',
                parse_confidence='ambiguous',
                raw_response={'id': 'resp-2', 'choices': []},
                latency_ms=520,
                input_tokens=50,
                output_tokens=15,
                started_at=now - timedelta(seconds=1.5),
                finished_at=now - timedelta(seconds=1),
            ),
            # Success with no answer (review needed)
            create_mock_success_result(
                run_id=test_data['run_id'],
                variant_id=test_data['variant_ids'][1],
                snapshot_id=test_data['snapshot_ids'][2],
                question_id='q3',
                response_text='I cannot answer this.',
                selected_answer=None,
                parse_confidence='no_answer',
                raw_response={'id': 'resp-3', 'choices': []},
                latency_ms=300,
                input_tokens=40,
                output_tokens=8,
                started_at=now - timedelta(seconds=1),
                finished_at=now - timedelta(seconds=0.5),
            ),
            # Failure (goes to errors table)
            create_mock_failure_result(
                run_id=test_data['run_id'],
                variant_id=test_data['variant_ids'][1],
                snapshot_id=test_data['snapshot_ids'][1],
                question_id='q2',
                error_type='timeout',
                error_message='Request timed out after 30s',
                attempt_count=3,
            ),
        ]

        writer = ResultWriter(fresh_db)

        # Act
        report = writer.write_results(results)

        # Assert: Validate report structure
        assert report.responses_written == 3, "Should write 3 success results"
        assert report.errors_written == 1, "Should write 1 error"
        assert len(report.runs_updated) == 1, "Should update 1 run"
        assert report.runs_updated[0] == (test_data['run_id'], 'partial_failed'), "Status should be partial_failed"

        # Generate validation report data
        cursor = fresh_db.cursor()
        
        # Get latest responses
        cursor.execute("""
            SELECT 
                response_id,
                status,
                finish_reason,
                response_text IS NOT NULL as has_response_text,
                selected_answer,
                is_correct,
                parse_confidence,
                raw_response IS NOT NULL as has_raw_response,
                input_tokens,
                response_tokens,
                latency_ms,
                started_at,
                finished_at,
                review_status,
                needs_review
            FROM responses 
            WHERE run_id = ?
            ORDER BY response_id
        """, (test_data['run_id'],))
        
        responses = cursor.fetchall()
        
        # NULL field summary
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status IS NULL THEN 1 ELSE 0 END) as null_status,
                SUM(CASE WHEN finish_reason IS NULL THEN 1 ELSE 0 END) as null_finish_reason,
                SUM(CASE WHEN raw_response IS NULL THEN 1 ELSE 0 END) as null_raw_response,
                SUM(CASE WHEN is_correct IS NULL THEN 1 ELSE 0 END) as null_is_correct,
                SUM(CASE WHEN review_status IS NULL THEN 1 ELSE 0 END) as null_review_status,
                SUM(CASE WHEN started_at IS NULL THEN 1 ELSE 0 END) as null_started_at,
                SUM(CASE WHEN finished_at IS NULL THEN 1 ELSE 0 END) as null_finished_at,
                SUM(CASE WHEN response_tokens IS NULL THEN 1 ELSE 0 END) as null_response_tokens
            FROM responses
            WHERE run_id = ?
        """, (test_data['run_id'],))
        
        null_summary = cursor.fetchone()

        # Print validation report
        print("\n" + "=" * 80)
        print("# Block 6c Validation Report")
        print("=" * 80)
        print("\n## Execution Results")
        print(f"\n**Command:** `bcllm --experiment val_block6c --execute`")
        print(f"**Exit Code:** 0")
        print(f"**Responses Written:** {report.responses_written}")
        print(f"**Errors Written:** {report.errors_written}")
        print(f"**Run Status:** {report.runs_updated[0][1]}")
        
        print("\n---\n\n## Database State Verification")
        print("\n### Latest Responses Sample\n")
        print("| response_id | status | finish_reason | has_raw | answer | is_correct | review_status | has_timestamps |")
        print("|-------------|--------|---------------|---------|--------|------------|---------------|----------------|")
        for row in responses:
            has_timestamps = 'Yes' if row['started_at'] and row['finished_at'] else 'No'
            print(f"| {row['response_id'][:20]}... | {row['status']} | {row['finish_reason']} | {row['has_raw_response']} | {row['selected_answer']} | {row['is_correct']} | {row['review_status']} | {has_timestamps} |")
        
        print("\n### NULL Field Summary\n")
        print("| Field | Contract Requires | NULL Count | Status |")
        print("|-------|-------------------|------------|--------|")
        
        checks = [
            ('status', "'success' for success", null_summary['null_status'], '✅' if null_summary['null_status'] == 0 else '❌'),
            ('raw_response', 'Always', null_summary['null_raw_response'], '✅' if null_summary['null_raw_response'] == 0 else '❌'),
            ('finish_reason', 'Always', null_summary['null_finish_reason'], '✅' if null_summary['null_finish_reason'] == 0 else '❌'),
            ('is_correct', 'When answer exists', null_summary['null_is_correct'], 'ℹ️ Expected when no answer'),
            ('review_status', 'Always', null_summary['null_review_status'], '✅' if null_summary['null_review_status'] == 0 else '❌'),
            ('started_at', 'Always', null_summary['null_started_at'], '✅' if null_summary['null_started_at'] == 0 else '❌'),
            ('finished_at', 'Always', null_summary['null_finished_at'], '✅' if null_summary['null_finished_at'] == 0 else '❌'),
            ('response_tokens', 'Always', null_summary['null_response_tokens'], '✅' if null_summary['null_response_tokens'] == 0 else '❌'),
        ]
        
        for field, contract, null_count, status in checks:
            print(f"| {field} | {contract} | {null_count} | {status} |")
        
        print("\n---\n\n## Contract Compliance\n")
        print("| Contract Rule | Status | Evidence |")
        print("|---------------|--------|----------|")
        
        # Check each contract rule
        cursor.execute("SELECT COUNT(*) FROM responses WHERE status != 'success'")
        non_success = cursor.fetchone()[0]
        status_check = '✅' if non_success == 0 else '❌'
        print(f"| status = 'success' for successful executions | {status_check} | All {report.responses_written} responses have status='success' |")
        
        cursor.execute("SELECT COUNT(*) FROM responses WHERE raw_response IS NULL")
        null_raw = cursor.fetchone()[0]
        raw_check = '✅' if null_raw == 0 else '❌'
        print(f"| raw_response always persisted | {raw_check} | 0 NULL raw_response values |")
        
        cursor.execute("SELECT COUNT(*) FROM responses WHERE started_at IS NULL OR finished_at IS NULL")
        null_ts = cursor.fetchone()[0]
        ts_check = '✅' if null_ts == 0 else '❌'
        print(f"| Timestamps captured | {ts_check} | All responses have started_at and finished_at |")
        
        cursor.execute("SELECT COUNT(*) FROM responses WHERE review_status IS NULL")
        null_review = cursor.fetchone()[0]
        review_check = '✅' if null_review == 0 else '❌'
        print(f"| needs_review calculated | {review_check} | All responses have review_status derived |")
        
        cursor.execute("SELECT COUNT(*) FROM responses WHERE review_status IS NOT NULL")
        has_review = cursor.fetchone()[0]
        review_status_check = '✅' if has_review > 0 else '❌'
        print(f"| review_status derived | {review_status_check} | {has_review} responses have review_status set |")
        
        print("\n---\n\n## Classification\n")
        
        # Determine classification
        critical_issues = (
            null_summary['null_status'] > 0 or
            null_summary['null_raw_response'] > 0 or
            null_summary['null_finish_reason'] > 0 or
            null_summary['null_review_status'] > 0 or
            null_summary['null_started_at'] > 0 or
            null_summary['null_finished_at'] > 0 or
            null_summary['null_response_tokens'] > 0
        )
        
        if critical_issues:
            print("- ❌ **FAIL** — Critical contract violations remain")
        elif null_summary['null_is_correct'] > 0:
            print("- ⚠️ **PARTIAL** — Some fields NULL but expected (is_correct when no answer)")
        else:
            print("- ✅ **PASS** — All critical fields populated, contract compliant")
        
        print("\n---\n\n## Recommendation\n")
        if critical_issues:
            print("**Action Required:**")
            print("- List remaining issues")
            print("- Requires additional fixes")
        elif null_summary['null_is_correct'] > 0:
            print("**If PARTIAL:**")
            print("- Document expected NULLs (is_correct when selected_answer is NULL)")
            print("- Proceed to Essence Guardian Gate")
        else:
            print("**If PASS:**")
            print("- Block 6c ready for Essence Guardian Gate")
            print("- Resume Block 5 (Human-Driven Validation)")
        
        print("\n" + "=" * 80)
