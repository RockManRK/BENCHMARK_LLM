"""Test script for question snapshots functionality.

This script validates the question snapshot implementation by:
1. Creating an in-memory database with the new schema
2. Creating question snapshots
3. Verifying snapshot immutability
4. Testing response creation with snapshot_id
"""

import json
import tempfile
from pathlib import Path

from src.db.models import Question, QuestionSnapshot, Response, Run
from src.db.repository import QuestionSnapshotRepository, ResponseRepository, RunRepository
from src.db.schema import DatabaseManager


def test_snapshot_creation():
    """Test basic snapshot creation and retrieval."""
    print("Testing snapshot creation...")
    
    # Create in-memory database
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    
    # Create repositories
    from src.db.repository import ExperimentRepository, ModelRepository, QuestionRepository
    from src.db.models import Experiment, Model
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    run_repo = RunRepository(db_manager)
    response_repo = ResponseRepository(db_manager)
    question_repo = QuestionRepository(db_manager)
    model_repo = ModelRepository(db_manager)
    experiment_repo = ExperimentRepository(db_manager)
    
    # Create experiment (required for snapshots)
    experiment = Experiment(
        name="test-exp-snapshot-creation",
        config_json='{"test": true}',
        config_hash="snapshot123",
    )
    experiment_repo.create(experiment)
    print(f"  Created experiment: {experiment.experiment_id}")
    
    # Create a test run
    run = Run(run_id="test-run-001", is_dev=True, experiment_id=experiment.experiment_id)
    run_repo.create(run)
    
    # Create a model
    model = Model(
        model_id="test-model",
        provider="test",
        model_name="Test Model",
    )
    model_repo.create(model)
    print(f"  Created model: {model.model_id}")
    
    # Create a question in canonical catalog
    question = Question(
        question_id="Q001",
        stem="Qual é a capital da França?",
        options_json=json.dumps({"A": "Paris", "B": "Londres", "C": "Berlim", "D": "Madrid"}),
        correct_answer="A",
        has_image=False,
    )
    question_repo.create(question)
    print(f"  Created canonical question: {question.question_id}")
    
    # Create question JSON for snapshot
    question_json = json.dumps({
        "id": question.question_id,
        "stem": question.stem,
        "options": json.loads(question.options_json),
        "answer_key": question.correct_answer,
        "has_image": question.has_image,
        "image_path": question.image_path,
    })
    
    # Create snapshot (first time)
    snapshot_id_1 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment.experiment_id,
        question_id=question.question_id,
        question_json=question_json,
    )
    print(f"  Created snapshot ID: {snapshot_id_1}")
    
    # Create snapshot again (should return same ID for same experiment+question)
    snapshot_id_2 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment.experiment_id,
        question_id=question.question_id,
        question_json=question_json,
    )
    print(f"  Second snapshot ID: {snapshot_id_2}")
    
    # Should reuse existing snapshot
    assert snapshot_id_1 == snapshot_id_2, "Should reuse existing snapshot for same experiment+question"
    
    # Retrieve snapshot
    snapshot = snapshot_repo.get_by_id(snapshot_id_1)
    assert snapshot is not None, "Snapshot should exist"
    assert snapshot.question_id == "Q001", "Question ID should match"
    print(f"  Retrieved snapshot: question_id={snapshot.question_id}")
    
    # Verify snapshot JSON
    snapshot_data = json.loads(snapshot.question_json)
    assert snapshot_data["id"] == "Q001", "Snapshot should contain correct question ID"
    assert snapshot_data["stem"] == "Qual é a capital da França?", "Snapshot should contain correct stem"
    print(f"  Snapshot JSON validated")
    
    # Create a response using snapshot_id
    response = Response(
        run_id="test-run-001",
        snapshot_id=snapshot_id_1,
        question_id="Q001",
        model_id="test-model",
        iteration=1,
        selected_answer="A",
        response_text="A resposta é Paris.",
        is_correct=True,
        status="success",
        latency_ms=1500,
        input_tokens=50,
        output_tokens=10,
        total_tokens=60,
    )
    response_repo.create(response)
    print(f"  Created response with snapshot_id={snapshot_id_1}")
    
    # Retrieve response and verify
    retrieved_response = response_repo.get_by_id(response.response_id)
    assert retrieved_response is not None, "Response should exist"
    assert retrieved_response.snapshot_id == snapshot_id_1, "Response should reference correct snapshot"
    assert retrieved_response.question_id == "Q001", "Response should have question_id"
    print(f"  Retrieved response: snapshot_id={retrieved_response.snapshot_id}, question_id={retrieved_response.question_id}")
    
    # Test getting responses by run
    responses = response_repo.get_by_run("test-run-001")
    assert len(responses) == 1, "Should have 1 response"
    print(f"  Retrieved {len(responses)} response(s) for run")
    
    print("✓ All snapshot tests passed!\n")
    return True


def test_experiment_snapshots():
    """Test snapshot deduplication within an experiment."""
    print("Testing experiment snapshot deduplication...")
    
    # Create in-memory database
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    
    # Create repositories
    from src.db.repository import ExperimentRepository, QuestionRepository
    from src.db.models import Experiment
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    question_repo = QuestionRepository(db_manager)
    experiment_repo = ExperimentRepository(db_manager)
    
    # Create canonical question first
    question = Question(
        question_id="Q001",
        stem="Test question",
        options_json=json.dumps({"A": "Option A", "B": "Option B"}),
        correct_answer="A",
        has_image=False,
    )
    question_repo.create(question)
    
    # Create experiment
    experiment = Experiment(
        name="test-exp-001",
        config_json='{"test": true}',
        config_hash="abc123",
    )
    experiment_repo.create(experiment)
    experiment_id = experiment.experiment_id
    print(f"  Created experiment: {experiment_id}")
    question_id = "Q001"
    question_json = json.dumps({
        "id": question_id,
        "stem": "Test question",
        "options": {"A": "Option A", "B": "Option B"},
        "answer_key": "A",
        "has_image": False,
    })
    
    # First call - should create snapshot
    snapshot_id_1 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment_id,
        question_id=question_id,
        question_json=question_json,
    )
    print(f"  First snapshot ID: {snapshot_id_1}")
    
    # Second call with same (experiment_id, question_id) - should return existing
    snapshot_id_2 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment_id,
        question_id=question_id,
        question_json=question_json,  # Same JSON
    )
    print(f"  Second snapshot ID: {snapshot_id_2}")
    
    assert snapshot_id_1 == snapshot_id_2, "Should return existing snapshot ID for same (experiment, question)"
    print(f"  ✓ Snapshot deduplication works correctly")
    
    # Get snapshots by experiment
    snapshots = snapshot_repo.get_by_experiment(experiment_id)
    assert len(snapshots) == 1, "Should have 1 snapshot for experiment"
    print(f"  Retrieved {len(snapshots)} snapshot(s) for experiment")
    
    # Get snapshots by question
    snapshots = snapshot_repo.get_by_question(question_id)
    assert len(snapshots) == 1, "Should have 1 snapshot for question"
    print(f"  Retrieved {len(snapshots)} snapshot(s) for question")
    
    print("✓ All experiment snapshot tests passed!\n")
    return True


def test_snapshot_requires_experiment_id():
    """Test that snapshot creation fails without experiment_id."""
    print("Testing snapshot requires experiment_id...")
    
    # Create in-memory database
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    
    # Create repository
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    
    question_json = json.dumps({
        "id": "Q001",
        "stem": "Test question",
        "options": {"A": "Option A", "B": "Option B"},
        "answer_key": "A",
        "has_image": False,
    })
    
    # Test that empty experiment_id raises error
    try:
        snapshot_id = snapshot_repo.create_if_not_exists(
            experiment_id="",  # Empty string should fail
            question_id="Q001",
            question_json=question_json,
        )
        print(f"  ✗ Should have raised ValueError for empty experiment_id")
        return False
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
        return True


def test_shadow_experiment_creation():
    """Test that shadow experiments are created for dev mode."""
    print("Testing shadow experiment creation...")
    
    from src.core.run_manager import RunManager
    from src.utils.config import Settings
    
    # Create in-memory database
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    
    # Create settings for dev mode (no experiment name)
    settings = Settings(
        openrouter_api_key="test-key",
        database_path=":memory:",
        execution_mode="dev",
    )
    
    # Create run manager
    run_manager = RunManager(db_manager, settings)
    
    # Initialize run (should create shadow experiment)
    config = {
        "models": ["test-model"],
        "iterations": 1,
    }
    run = run_manager.initialize_run(config)
    
    # Verify shadow experiment was created
    assert run.experiment_id is not None, "Run should have experiment_id"
    assert run.experiment_id.startswith("exp-"), "Experiment ID should have valid format"
    
    # Verify shadow experiment exists in database
    from src.db.repository import ExperimentRepository
    exp_repo = ExperimentRepository(db_manager)
    experiment = exp_repo.get_by_id(run.experiment_id)
    
    assert experiment is not None, "Shadow experiment should exist"
    assert "shadow" in experiment.name.lower(), f"Shadow experiment name should contain 'shadow': {experiment.name}"
    
    print(f"  ✓ Shadow experiment created: {experiment.name}")
    return True


def test_snapshot_consistency_validation():
    """Test that question_id matches snapshot JSON."""
    print("Testing snapshot consistency validation...")
    
    # Create in-memory database
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    
    # Create repositories
    from src.db.repository import ExperimentRepository, QuestionRepository
    from src.db.models import Experiment, Question
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    question_repo = QuestionRepository(db_manager)
    experiment_repo = ExperimentRepository(db_manager)
    
    # Create experiment
    experiment = Experiment(
        name="test-exp-validation",
        config_json='{"test": true}',
        config_hash="validation123",
    )
    experiment_repo.create(experiment)
    
    # Create question with matching ID
    question = Question(
        question_id="Q003",
        stem="Consistency test",
        options_json=json.dumps({"A": "Option A", "B": "Option B"}),
        correct_answer="A",
        has_image=False,
    )
    question_repo.create(question)
    
    # Create snapshot with CORRECT question_id
    correct_json = json.dumps({
        "id": "Q003",  # Matches question_id
        "stem": "Consistency test",
        "options": {"A": "Option A", "B": "Option B"},
        "answer_key": "A",
        "has_image": False,
    })
    
    snapshot_id = snapshot_repo.create_if_not_exists(
        experiment_id=experiment.experiment_id,
        question_id="Q003",
        question_json=correct_json,
    )
    
    # Validate - should pass
    is_valid, error = snapshot_repo.validate_snapshot_integrity(snapshot_id)
    assert is_valid, f"Valid snapshot should pass validation: {error}"
    print(f"  ✓ Valid snapshot passed validation")
    
    # Create question Q004 for mismatched test
    question_4 = Question(
        question_id="Q004",
        stem="Mismatched test question",
        options_json=json.dumps({"A": "Option A"}),
        correct_answer="A",
        has_image=False,
    )
    question_repo.create(question_4)
    
    # Create snapshot with MISMATCHED question_id (simulate data corruption)
    # Note: This bypasses the normal creation flow to test validation
    conn = db_manager.get_connection()
    try:
        cursor = conn.cursor()
        mismatched_json = json.dumps({
            "id": "Q999",  # DOES NOT match question_id
            "stem": "Mismatched test",
            "options": {"A": "Option A"},
            "answer_key": "A",
            "has_image": False,
        })
        cursor.execute(
            "INSERT INTO question_snapshots (experiment_id, question_id, question_json) VALUES (?, ?, ?)",
            (experiment.experiment_id, "Q004", mismatched_json)
        )
        conn.commit()
        mismatched_snapshot_id = cursor.lastrowid
    finally:
        if db_manager.should_close_connection():
            conn.close()
    
    # Validate - should fail
    is_valid, error = snapshot_repo.validate_snapshot_integrity(mismatched_snapshot_id)
    assert not is_valid, "Mismatched snapshot should fail validation"
    assert "mismatch" in error.lower(), f"Error should mention mismatch: {error}"
    print(f"  ✓ Invalid snapshot correctly rejected: {error}")
    
    return True


def test_incremental_execution_reuses_snapshots():
    """Test that second execution reuses existing snapshots."""
    print("Testing incremental execution reuses snapshots...")
    
    # Create in-memory database
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    
    # Create repositories
    from src.db.repository import ExperimentRepository, QuestionRepository
    from src.db.models import Experiment, Question
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    question_repo = QuestionRepository(db_manager)
    experiment_repo = ExperimentRepository(db_manager)
    
    # Create experiment
    experiment = Experiment(
        name="test-exp-incremental",
        config_json='{"test": true}',
        config_hash="incremental123",
    )
    experiment_repo.create(experiment)
    
    # Create question
    question = Question(
        question_id="Q005",
        stem="Incremental test",
        options_json=json.dumps({"A": "Option A", "B": "Option B"}),
        correct_answer="A",
        has_image=False,
    )
    question_repo.create(question)
    
    question_json = json.dumps({
        "id": "Q005",
        "stem": "Incremental test",
        "options": {"A": "Option A", "B": "Option B"},
        "answer_key": "A",
        "has_image": False,
    })
    
    # First execution - should create snapshot
    snapshot_id_1 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment.experiment_id,
        question_id="Q005",
        question_json=question_json,
    )
    print(f"  First execution: snapshot_id={snapshot_id_1}")
    
    # Second execution (same question, same experiment) - should REUSE
    snapshot_id_2 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment.experiment_id,
        question_id="Q005",
        question_json=question_json,
    )
    print(f"  Second execution: snapshot_id={snapshot_id_2}")
    
    assert snapshot_id_1 == snapshot_id_2, "Should reuse existing snapshot"
    print(f"  ✓ Snapshot correctly reused: ID={snapshot_id_1}")
    
    return True


def test_new_questions_create_new_snapshots():
    """Test that new questions in same experiment create new snapshots."""
    print("Testing new questions create new snapshots...")
    
    # Create in-memory database
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    
    # Create repositories
    from src.db.repository import ExperimentRepository, QuestionRepository
    from src.db.models import Experiment, Question
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    question_repo = QuestionRepository(db_manager)
    experiment_repo = ExperimentRepository(db_manager)
    
    # Create experiment
    experiment = Experiment(
        name="test-exp-new-questions",
        config_json='{"test": true}',
        config_hash="newquestions123",
    )
    experiment_repo.create(experiment)
    
    # Create questions
    question_1 = Question(
        question_id="Q006",
        stem="First question",
        options_json=json.dumps({"A": "Option A", "B": "Option B"}),
        correct_answer="A",
        has_image=False,
    )
    question_2 = Question(
        question_id="Q007",
        stem="Second question",
        options_json=json.dumps({"A": "Option A", "B": "Option B"}),
        correct_answer="A",
        has_image=False,
    )
    question_repo.create(question_1)
    question_repo.create(question_2)
    
    # First execution with Q006
    snapshot_id_1 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment.experiment_id,
        question_id="Q006",
        question_json=json.dumps({
            "id": "Q006",
            "stem": "First question",
            "options": {"A": "Option A", "B": "Option B"},
            "answer_key": "A",
            "has_image": False,
        }),
    )
    print(f"  Q006: snapshot_id={snapshot_id_1}")
    
    # Second execution with NEW question Q007 (same experiment)
    snapshot_id_2 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment.experiment_id,
        question_id="Q007",
        question_json=json.dumps({
            "id": "Q007",
            "stem": "Second question",
            "options": {"A": "Option A", "B": "Option B"},
            "answer_key": "A",
            "has_image": False,
        }),
    )
    print(f"  Q007: snapshot_id={snapshot_id_2}")
    
    assert snapshot_id_1 != snapshot_id_2, "Different questions should have different snapshots"
    print(f"  ✓ New question correctly created new snapshot")
    
    # Verify both snapshots exist for this experiment
    snapshots = snapshot_repo.get_by_experiment(experiment.experiment_id)
    assert len(snapshots) == 2, f"Should have 2 snapshots, got {len(snapshots)}"
    print(f"  ✓ Experiment has {len(snapshots)} snapshots as expected")
    
    return True


def test_snapshot_immutability():
    """Test that snapshots preserve original question data."""
    print("Testing snapshot immutability...")
    
    # Create in-memory database
    db_manager = DatabaseManager(Path(":memory:"))
    db_manager.initialize()
    
    # Create repositories
    from src.db.repository import ExperimentRepository, QuestionRepository
    from src.db.models import Experiment
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    question_repo = QuestionRepository(db_manager)
    experiment_repo = ExperimentRepository(db_manager)
    
    # Create canonical question first
    question = Question(
        question_id="Q002",
        stem="Original question text",
        options_json=json.dumps({"A": "Original A", "B": "Original B"}),
        correct_answer="A",
        has_image=False,
    )
    question_repo.create(question)
    
    # Create experiment
    experiment = Experiment(
        name="test-exp-002",
        config_json='{"test": true}',
        config_hash="def456",
    )
    experiment_repo.create(experiment)
    experiment_id = experiment.experiment_id
    print(f"  Created experiment: {experiment_id}")
    
    # Original question
    original_json = json.dumps({
        "id": "Q002",
        "stem": "Original question text",
        "options": {"A": "Original A", "B": "Original B"},
        "answer_key": "A",
        "has_image": False,
    })
    
    # Create snapshot
    snapshot_id = snapshot_repo.create_if_not_exists(
        experiment_id=experiment_id,
        question_id="Q002",
        question_json=original_json,
    )
    
    # Simulate question being updated in canonical catalog
    updated_json = json.dumps({
        "id": "Q002",
        "stem": "Updated question text (grammar fix)",
        "options": {"A": "Updated A", "B": "Updated B"},
        "answer_key": "A",
        "has_image": False,
    })
    
    # Try to create snapshot again with updated JSON
    # Should return existing snapshot ID (deduplication by experiment_id + question_id)
    snapshot_id_2 = snapshot_repo.create_if_not_exists(
        experiment_id=experiment_id,
        question_id="Q002",
        question_json=updated_json,
    )
    
    assert snapshot_id == snapshot_id_2, "Should return existing snapshot ID"
    
    # Retrieve snapshot - should have ORIGINAL data, not updated
    snapshot = snapshot_repo.get_by_id(snapshot_id)
    snapshot_data = json.loads(snapshot.question_json)
    
    assert snapshot_data["stem"] == "Original question text", "Snapshot should preserve original stem"
    assert snapshot_data["options"]["A"] == "Original A", "Snapshot should preserve original options"
    print(f"  Snapshot preserved original data: stem='{snapshot_data['stem']}'")
    print(f"  ✓ Snapshot immutability verified")
    
    print("✓ All immutability tests passed!\n")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Question Snapshots - Test Suite")
    print("=" * 60 + "\n")

    all_passed = True

    try:
        # Core functionality tests
        all_passed &= test_snapshot_creation()
        all_passed &= test_experiment_snapshots()
        all_passed &= test_snapshot_immutability()
        
        # New validation tests
        all_passed &= test_snapshot_requires_experiment_id()
        all_passed &= test_snapshot_consistency_validation()
        all_passed &= test_incremental_execution_reuses_snapshots()
        all_passed &= test_new_questions_create_new_snapshots()
        
        # Integration tests (require full system)
        all_passed &= test_shadow_experiment_creation()

        if all_passed:
            print("=" * 60)
            print("✓ ALL TESTS PASSED")
            print("=" * 60)
        else:
            print("=" * 60)
            print("✗ SOME TESTS FAILED")
            print("=" * 60)
            exit(1)

    except Exception as e:
        print(f"\n✗ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
