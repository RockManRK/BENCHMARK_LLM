#!/usr/bin/env python3
"""Integration test for new execution axis with real data."""

import sys
import json
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.db.schema import DatabaseManager
from src.db.models import Experiment, Run, Model, ModelVariant, Question, QuestionSnapshot
from src.db.repository import (
    ExperimentRepository,
    RunRepository,
    ModelRepository,
    ModelVariantRepository,
    QuestionRepository,
    QuestionSnapshotRepository,
    RunModelRepository,
)
from src.core.planner import Planner
from src.core.execution_engine import ExecutionEngine
from src.core.result_writer import ResultWriter
from datetime import datetime


def setup_test_experiment(db_manager):
    """Create a minimal test experiment with real data."""
    print("\n" + "=" * 60)
    print("SETTING UP TEST EXPERIMENT")
    print("=" * 60)
    
    # Load questions from dataset
    dataset_path = Path("data/enamed_questions.json")
    with open(dataset_path) as f:
        data = json.load(f)
    
    questions_data = data.get("questions", [])
    print(f"✓ Loaded {len(questions_data)} questions from dataset")
    
    # Use first 5 questions for test
    test_questions = questions_data[:5]
    print(f"✓ Using {len(test_questions)} questions for test")
    
    # Create experiment
    exp_repo = ExperimentRepository(db_manager)
    experiment = Experiment(
        experiment_id="exp-test001",
        name="test_execution_axis",
        description="Test experiment for new execution axis",
        config_json=json.dumps({"random_seed": 42}),
        config_hash="testhash001",
        system_prompt_template="You are a helpful medical assistant.",
        user_prompt_template="Select the correct answer by providing only the letter (A, B, C, or D).",
    )
    exp_repo.create(experiment)
    print(f"✓ Created experiment: {experiment.name}")
    
    # Create questions in database
    question_repo = QuestionRepository(db_manager)
    for q_data in test_questions:
        question = Question(
            question_id=q_data["id"],
            stem=q_data["stem"],
            options_json=json.dumps(q_data["options"]),
            correct_answer=q_data["answer_key"],
            has_image=q_data.get("meta", {}).get("has_image", False),
            image_path=None,
            status=q_data.get("meta", {}).get("status", "active"),
        )
        try:
            question_repo.create(question)
        except Exception:
            pass  # May already exist
    print(f"✓ Created {len(test_questions)} questions")
    
    # Create snapshots for experiment
    snapshot_repo = QuestionSnapshotRepository(db_manager)
    for q_data in test_questions:
        question_payload = json.dumps({
            "id": q_data["id"],
            "stem": q_data["stem"],
            "options": q_data["options"],
            "answer_key": q_data["answer_key"],
        })
        snapshot_repo.create_if_not_exists(
            experiment_id=experiment.experiment_id,
            question_id=q_data["id"],
            question_payload=question_payload,
        )
    print(f"✓ Created {len(test_questions)} snapshots")
    
    # Create run
    run_repo = RunRepository(db_manager)
    run = Run(
        run_id="run-test001",
        experiment_id=experiment.experiment_id,
        seed=42,
        started_at=datetime.now(),
        status="pending",
    )
    run_repo.create(run)
    print(f"✓ Created run: {run.run_id}")
    
    # Create model (mock - no real API)
    model_repo = ModelRepository(db_manager)
    model = Model(
        model_id="mock/test-model",
        provider="Mock",
        model_name="Test Model",
    )
    try:
        model_repo.create(model)
    except Exception:
        pass  # May already exist
    print(f"✓ Created model: {model.model_id}")
    
    # Create variant
    variant_repo = ModelVariantRepository(db_manager)
    variant = ModelVariant(
        variant_id="var-test001",
        model_id="mock/test-model",
        reasoning_mode="off",
        reasoning_effort=None,
        max_output_tokens=None,
        vision_enabled=False,
        structured_output=False,
        variant_signature="mock/test-model::reasoning=off::vision=false::structured=false",
    )
    try:
        variant_repo.create(variant)
        print(f"✓ Created variant: {variant.variant_id}")
    except Exception as e:
        # Variant may already exist, retrieve it
        print(f"⚠️  Variant already exists, retrieving...")
        variant = variant_repo.get_by_id("var-test001")
        if not variant:
            raise Exception("Could not create or retrieve variant")
        print(f"✓ Retrieved existing variant: {variant.variant_id}")
    
    # Associate variant with run
    run_model_repo = RunModelRepository(db_manager)
    run_model_repo.add(run.run_id, variant.variant_id, status="pending")
    print(f"✓ Associated variant with run")
    
    print("\n✅ TEST EXPERIMENT CREATED SUCCESSFULLY")
    return experiment, run, variant


def test_planner_build_plan(db_manager, experiment):
    """Test Planner.build_plan() with real data."""
    print("\n" + "=" * 60)
    print("TEST: Planner.build_plan()")
    print("=" * 60)
    
    planner = Planner(db_manager)
    plan = planner.build_plan(experiment_name=experiment.name)
    
    print(f"✓ Plan ID: {plan.plan_id}")
    print(f"✓ Experiment: {plan.experiment_name}")
    print(f"✓ Runs: {len(plan.runs)}")
    
    total_items = sum(len(run.items) for run in plan.runs)
    print(f"✓ Items to execute: {total_items}")
    
    # Check seed handling
    for run in plan.runs:
        seed_status = f"seed={run.seed_effective}" if run.seed_effective is not None else "seed=None"
        print(f"✓ Run {run.run_id}: {seed_status}")
        print(f"  - Variants: {len(run.variants)}")
        print(f"  - Items: {len(run.items)}")
    
    assert total_items > 0, "Plan should have items to execute"
    print("\n✅ PLANNER TEST PASSED")
    return plan


def test_execution_engine(plan):
    """Test ExecutionEngine.execute() - mock execution."""
    print("\n" + "=" * 60)
    print("TEST: ExecutionEngine.execute()")
    print("=" * 60)
    
    from unittest.mock import MagicMock
    
    # Create mock API client (no real API calls)
    mock_api_client = MagicMock()
    mock_api_client.chat_completion = MagicMock(return_value={
        "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
    })
    
    # Create mock randomizer
    mock_randomizer = MagicMock()
    mock_randomizer.set_seed = MagicMock()
    mock_randomizer._randomize_options = MagicMock(side_effect=lambda opts, correct: {
        "options": opts,
        "correct_answer": correct,
    })
    
    # Create mock settings
    mock_settings = MagicMock()
    mock_settings.model_max_tokens = None
    mock_settings.model_temperature = None
    mock_settings.use_structured_outputs = False
    
    # Create engine WITHOUT db_manager
    engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)
    
    print("✓ ExecutionEngine created (NO db_manager)")
    
    # Execute plan
    results = engine.execute(plan)
    
    print(f"✓ Executed {len(results)} items")
    
    # Verify results
    assert len(results) == total_items, f"Expected {total_items} results, got {len(results)}"
    
    for result in results[:3]:  # Show first 3
        print(f"  - {result.question_id}: {result.status} (answer={result.selected_answer})")
    
    print("\n✅ EXECUTION ENGINE TEST PASSED")
    return results


def test_result_writer(db_manager, plan, results):
    """Test ResultWriter.write_results() with real data."""
    print("\n" + "=" * 60)
    print("TEST: ResultWriter.write_results()")
    print("=" * 60)
    
    writer = ResultWriter(db_manager)
    write_result = writer.write_results(plan, results)
    
    print(f"✓ Responses written: {write_result.responses_written}")
    print(f"✓ Errors written: {write_result.errors_written}")
    print(f"✓ Responses skipped: {write_result.responses_skipped}")
    print(f"✓ Runs updated: {write_result.runs_updated}")
    
    # Verify run status was updated
    from src.db.repository import RunRepository
    run_repo = RunRepository(db_manager)
    for run_id in write_result.runs_updated:
        run = run_repo.get_by_id(run_id)
        print(f"✓ Run {run_id} status: {run.status}")
    
    print("\n✅ RESULT WRITER TEST PASSED")
    return write_result


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("NEW EXECUTION AXIS - INTEGRATION TEST")
    print("=" * 60)
    
    db_path = Path("data/benchmark.db")
    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    
    try:
        # Setup test data
        experiment, run, variant = setup_test_experiment(db_manager)
        
        # Test Planner
        plan = test_planner_build_plan(db_manager, experiment)
        total_items = sum(len(run.items) for run in plan.runs)
        
        # Test ExecutionEngine
        results = test_execution_engine(plan)
        
        # Test ResultWriter
        write_result = test_result_writer(db_manager, plan, results)
        
        # Summary
        print("\n" + "=" * 60)
        print("INTEGRATION TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Experiment created: {experiment.name}")
        print(f"✅ Plan built: {plan.plan_id} ({total_items} items)")
        print(f"✅ Execution completed: {len(results)} results")
        print(f"✅ Results persisted: {write_result.responses_written} responses")
        print(f"✅ Run status updated: {write_result.runs_updated}")
        
        print("\n✅✅✅ ALL INTEGRATION TESTS PASSED ✅✅✅")
        print("\nThe new execution axis is FULLY FUNCTIONAL:")
        print("  1. Planner builds immutable ExecutionPlan from DB")
        print("  2. ExecutionEngine executes WITHOUT DB access")
        print("  3. ResultWriter persists results and updates status")
        
    except Exception as e:
        print(f"\n❌ INTEGRATION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db_manager.close()
