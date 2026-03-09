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
    from src.db.repository import ModelRepository, QuestionRepository
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    run_repo = RunRepository(db_manager)
    response_repo = ResponseRepository(db_manager)
    question_repo = QuestionRepository(db_manager)
    model_repo = ModelRepository(db_manager)
    
    # Create a test run
    run = Run(run_id="test-run-001", is_dev=True)
    run_repo.create(run)
    
    # Create a model
    from src.db.models import Model
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
        experiment_id=None,  # Dev mode
        question_id=question.question_id,
        question_json=question_json,
    )
    print(f"  Created snapshot ID: {snapshot_id_1}")
    
    # Create snapshot again (should return same ID for dev mode with same question)
    # Note: In dev mode (experiment_id=None), each call creates a new snapshot
    # This is expected behavior - snapshots are deduplicated by (experiment_id, question_id)
    snapshot_id_2 = snapshot_repo.create_if_not_exists(
        experiment_id=None,
        question_id=question.question_id,
        question_json=question_json,
    )
    print(f"  Second snapshot ID: {snapshot_id_2}")
    
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
        model_id="test-model",
        iteration=1,
        selected_answer="A",
        response_text="A resposta é Paris.",
        is_correct=True,
        status="success",
        latency_ms=1500,
        input_tokens=50,
        output_tokens=10,
    )
    response_repo.create(response)
    print(f"  Created response with snapshot_id={snapshot_id_1}")
    
    # Retrieve response and verify
    retrieved_response = response_repo.get_by_id(response.response_id)
    assert retrieved_response is not None, "Response should exist"
    assert retrieved_response.snapshot_id == snapshot_id_1, "Response should reference correct snapshot"
    print(f"  Retrieved response: snapshot_id={retrieved_response.snapshot_id}")
    
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
        all_passed &= test_snapshot_creation()
        all_passed &= test_experiment_snapshots()
        all_passed &= test_snapshot_immutability()
        
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
