#!/usr/bin/env python3
"""Test script for new execution axis end-to-end flow."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.db.schema import DatabaseManager
from src.db.repository import ExperimentRepository, RunRepository
from src.core.planner import Planner
from src.core.result_writer import ResultWriter

def test_planner_build_plan():
    """Test that Planner can build a plan from existing database."""
    print("=" * 60)
    print("TEST 1: Planner.build_plan()")
    print("=" * 60)
    
    db_path = Path("data/benchmark.db")
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    
    try:
        # List experiments
        exp_repo = ExperimentRepository(db_manager)
        experiments = exp_repo.get_all()
        
        if not experiments:
            print("⚠️  No experiments found in database (expected for fresh DB)")
            print("   Create one with: bcllm.py --create-experiment test_exp --questions Q001-Q005")
            # This is OK - fresh database won't have experiments yet
            return True
        
        print(f"✓ Found {len(experiments)} experiment(s):")
        for exp in experiments:
            print(f"  - {exp.name} (id={exp.experiment_id})")
        
        # Try to build plan for first experiment
        planner = Planner(db_manager)
        test_exp_name = experiments[0].name
        
        print(f"\n✓ Building plan for experiment '{test_exp_name}'...")
        plan = planner.build_plan(experiment_name=test_exp_name)
        
        print(f"✓ Plan built successfully:")
        print(f"  - Plan ID: {plan.plan_id}")
        print(f"  - Experiment: {plan.experiment_name}")
        print(f"  - Runs: {len(plan.runs)}")
        
        total_items = sum(len(run.items) for run in plan.runs)
        print(f"  - Items to execute: {total_items}")
        
        if total_items == 0:
            print("⚠️  No items to execute (all already answered or no runs)")
        else:
            print(f"✓ Plan has {total_items} items to execute")
        
        # Check seed handling
        for run in plan.runs:
            seed_status = f"seed={run.seed_effective}" if run.seed_effective is not None else "seed=None (no randomization)"
            print(f"  - Run {run.run_id}: {seed_status}")
        
        print("\n✅ TEST 1 PASSED: Planner.build_plan() works correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db_manager.close()


def test_result_writer():
    """Test that ResultWriter can be initialized."""
    print("\n" + "=" * 60)
    print("TEST 2: ResultWriter initialization")
    print("=" * 60)
    
    db_path = Path("data/benchmark.db")
    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    
    try:
        writer = ResultWriter(db_manager)
        print("✓ ResultWriter initialized successfully")
        print("✅ TEST 2 PASSED: ResultWriter can be created")
        return True
        
    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db_manager.close()


def test_execution_engine_no_db():
    """Test that ExecutionEngine has no db_manager attribute."""
    print("\n" + "=" * 60)
    print("TEST 3: ExecutionEngine has no DB access")
    print("=" * 60)
    
    from src.core.execution_engine import ExecutionEngine
    from unittest.mock import MagicMock
    
    # Create mock dependencies
    mock_api_client = MagicMock()
    mock_randomizer = MagicMock()
    mock_settings = MagicMock()
    
    engine = ExecutionEngine(mock_api_client, mock_randomizer, mock_settings)
    
    # Verify no db_manager
    has_db = hasattr(engine, 'db_manager') and engine.db_manager is not None
    
    if has_db:
        print("❌ TEST 3 FAILED: ExecutionEngine has db_manager (should be None)")
        return False
    else:
        print("✓ ExecutionEngine has no db_manager attribute")
        print("✅ TEST 3 PASSED: ExecutionEngine is DB-free")
        return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("NEW EXECUTION AXIS - END-TO-END VALIDATION")
    print("=" * 60)
    
    results = []
    
    # Test 1: Planner
    results.append(("Planner.build_plan()", test_planner_build_plan()))
    
    # Test 2: ResultWriter
    results.append(("ResultWriter", test_result_writer()))
    
    # Test 3: ExecutionEngine
    results.append(("ExecutionEngine (no DB)", test_execution_engine_no_db()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - New execution axis is functional")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED - Review errors above")
        sys.exit(1)
