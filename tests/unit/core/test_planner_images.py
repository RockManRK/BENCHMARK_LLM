"""Unit tests for Planner image field extraction.

Tests cover:
- Extraction of has_image and image_path from question snapshots
- Backward compatibility (missing meta/assets fields -> defaults)
"""

import json
import pytest
import uuid
from src.core.planner import Planner


def _setup_basic_experiment_data(conn):
    """Insert minimal experiment, variant, run, and snapshot for planner to build a plan.
    
    Returns dict with IDs for further customization.
    """
    experiment_id = f"exp-{uuid.uuid4().hex[:8]}"
    variant_id = f"var-{uuid.uuid4().hex[:8]}"
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
    
    config_json = json.dumps({
        "SYSTEM_PROMPT": "You are a helpful assistant.",
        "USER_PROMPT": "Answer the question.",
    })
    
    cursor = conn.cursor()
    
    # Insert experiment
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, config_json, config_hash)
        VALUES (?, ?, ?, ?)
    """, (experiment_id, "test-experiment", config_json, "test-hash"))
    
    # Insert variant
    variant_config = json.dumps({
        "vision": False,
        "structured": False,
        "reasoning_effort": "none",
    })
    cursor.execute("""
        INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config)
        VALUES (?, ?, ?, ?, ?)
    """, (variant_id, experiment_id, "openai/gpt-4", "openai_gpt4", variant_config))
    
    # Insert run
    run_config = json.dumps({
        "RANDOMIZATION_SEED": 42,
    })
    cursor.execute("""
        INSERT INTO runs (run_id, experiment_id, config, status)
        VALUES (?, ?, ?, ?)
    """, (run_id, experiment_id, run_config, "pending"))
    
    conn.commit()
    
    return {
        "experiment_id": experiment_id,
        "variant_id": variant_id,
        "run_id": run_id,
        "snapshot_id": snapshot_id,
    }


def _insert_snapshot_with_payload(conn, experiment_id: str, snapshot_id: str, question_id: str, payload: dict):
    """Insert a question snapshot with the given payload."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload)
        VALUES (?, ?, ?, ?, ?)
    """, (
        snapshot_id,
        experiment_id,
        question_id,
        1,
        json.dumps(payload),
    ))
    conn.commit()


class TestPlannerImageExtraction:
    """Tests for Planner image field extraction from question snapshots."""

    def test_planner_extracts_image_fields(self, in_memory_db):
        """Planner extracts has_image and image_path from snapshot with meta/assets."""
        # Arrange
        ids = _setup_basic_experiment_data(in_memory_db)
        
        payload_with_image = {
            "stem": "What is in this X-ray?",
            "options": ["Pneumonia", "Fracture", "Normal", "Tumor"],
            "answer_key": "A",
            "meta": {
                "has_table": False,
                "has_image": True,
                "status": "valid",
            },
            "assets": ["data/assets/image_Q005.png"],
        }
        _insert_snapshot_with_payload(
            in_memory_db,
            ids["experiment_id"],
            ids["snapshot_id"],
            "q005",
            payload_with_image,
        )

        # Act
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment")

        # Assert
        item = plan.runs[0].items[0]
        assert item.question_payload.has_image is True
        assert item.question_payload.image_path == "data/assets/image_Q005.png"

    def test_planner_handles_missing_image_fields_backward_compat(self, in_memory_db):
        """Planner handles snapshots without meta/assets fields (backward compatibility)."""
        # Arrange
        ids = _setup_basic_experiment_data(in_memory_db)
        
        payload_without_image = {
            "stem": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "answer_key": "B",
        }
        _insert_snapshot_with_payload(
            in_memory_db,
            ids["experiment_id"],
            ids["snapshot_id"],
            "q001",
            payload_without_image,
        )

        # Act
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment")

        # Assert
        item = plan.runs[0].items[0]
        assert item.question_payload.has_image is False
        assert item.question_payload.image_path is None

    def test_planner_handles_has_image_false_with_assets(self, in_memory_db):
        """Planner ignores assets when has_image is False."""
        # Arrange
        ids = _setup_basic_experiment_data(in_memory_db)
        
        payload = {
            "stem": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "answer_key": "B",
            "meta": {"has_image": False},
            "assets": ["data/assets/some_image.png"],
        }
        _insert_snapshot_with_payload(
            in_memory_db,
            ids["experiment_id"],
            ids["snapshot_id"],
            "q002",
            payload,
        )

        # Act
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment")

        # Assert
        item = plan.runs[0].items[0]
        assert item.question_payload.has_image is False
        assert item.question_payload.image_path is None

    def test_planner_handles_empty_assets_array(self, in_memory_db):
        """Planner handles has_image=True but empty assets array."""
        # Arrange
        ids = _setup_basic_experiment_data(in_memory_db)
        
        payload = {
            "stem": "What is in this image?",
            "options": ["A", "B", "C", "D"],
            "answer_key": "A",
            "meta": {"has_image": True},
            "assets": [],
        }
        _insert_snapshot_with_payload(
            in_memory_db,
            ids["experiment_id"],
            ids["snapshot_id"],
            "q003",
            payload,
        )

        # Act
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment")

        # Assert
        item = plan.runs[0].items[0]
        assert item.question_payload.has_image is True
        assert item.question_payload.image_path is None

    def test_planner_extracts_first_asset_only(self, in_memory_db):
        """Planner extracts only the first asset from assets array."""
        # Arrange
        ids = _setup_basic_experiment_data(in_memory_db)
        
        payload = {
            "stem": "Compare these two images.",
            "options": ["A", "B", "C", "D"],
            "answer_key": "A",
            "meta": {"has_image": True},
            "assets": ["data/assets/image_1.png", "data/assets/image_2.png"],
        }
        _insert_snapshot_with_payload(
            in_memory_db,
            ids["experiment_id"],
            ids["snapshot_id"],
            "q004",
            payload,
        )

        # Act
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment")

        # Assert
        item = plan.runs[0].items[0]
        assert item.question_payload.has_image is True
        assert item.question_payload.image_path == "data/assets/image_1.png"

    def test_planner_handles_meta_but_no_has_image_field(self, in_memory_db):
        """Planner handles meta object without has_image field."""
        # Arrange
        ids = _setup_basic_experiment_data(in_memory_db)
        
        payload = {
            "stem": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "answer_key": "B",
            "meta": {"has_table": True, "status": "valid"},
        }
        _insert_snapshot_with_payload(
            in_memory_db,
            ids["experiment_id"],
            ids["snapshot_id"],
            "q006",
            payload,
        )

        # Act
        planner = Planner(in_memory_db)
        plan = planner.build_plan("test-experiment")

        # Assert
        item = plan.runs[0].items[0]
        assert item.question_payload.has_image is False
        assert item.question_payload.image_path is None
