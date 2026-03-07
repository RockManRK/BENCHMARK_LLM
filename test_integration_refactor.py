#!/usr/bin/env python
"""Integration test for benchmark_llm refactoring."""

from src.utils.config import Settings, ExecutionMode
from src.db.schema import DatabaseManager
from src.core.run_manager import RunManager
from pathlib import Path


def test_settings():
    """Test settings with execution mode."""
    print("=== Test 1: Settings ===")
    settings = Settings()
    print(f"Default mode: {settings.execution_mode}")
    print(f"Is dev mode: {settings.is_dev_mode}")
    print(f"Should persist: {settings.should_persist_data}")
    assert settings.execution_mode == ExecutionMode.DEV
    assert settings.is_dev_mode is True
    assert settings.should_persist_data is True
    print("✓ Settings test passed\n")


def test_database_schema():
    """Test database schema creation."""
    print("=== Test 2: Database Schema ===")
    db = DatabaseManager(Path(":memory:"))
    db.initialize()
    conn = db.get_connection()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    table_names = [t[0] for t in tables]
    print(f"Tables created: {table_names}")
    assert "experiments" in table_names
    assert "runs" in table_names
    assert "models" in table_names
    assert "questions" in table_names
    assert "responses" in table_names
    assert "errors" in table_names
    print("✓ Database schema test passed\n")


def test_run_manager():
    """Test RunManager with settings."""
    print("=== Test 3: RunManager ===")
    db = DatabaseManager(Path(":memory:"))
    db.initialize()
    settings = Settings()
    run_manager = RunManager(db, settings)
    run = run_manager.initialize_run({"models": ["gpt-4"], "seed": 42})
    print(f"Run created: {run.run_id}")
    print(f"Is dev: {run.is_dev}")
    print(f"Experiment ID: {run.experiment_id}")
    assert run.is_dev is True
    assert run.experiment_id is None
    print("✓ RunManager test passed\n")


def test_experiment_mode():
    """Test experiment mode settings."""
    print("=== Test 4: Experiment Mode ===")
    settings = Settings()
    settings.execution_mode = ExecutionMode.EXPERIMENT
    settings.experiment_name = "test_experiment"
    print(f"Mode: {settings.execution_mode}")
    print(f"Experiment: {settings.experiment_name}")
    print(f"Config frozen: {settings.is_config_frozen}")
    print(f"Config hash: {settings.get_config_hash()}")
    assert settings.is_experiment_mode is True
    assert settings.is_config_frozen is True
    assert settings.get_config_hash() is not None
    print("✓ Experiment mode test passed\n")


if __name__ == "__main__":
    print("Running Integration Tests\n")
    test_settings()
    test_database_schema()
    test_run_manager()
    test_experiment_mode()
    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)
