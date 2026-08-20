"""Tests for Planner._build_model_config's MODEL_SEED mapping (Checkpoint B).

MODEL_SEED belongs to the model_variant config row, mapped straight onto
ModelConfig.model_seed — no resolution logic here (that already happened
at variant-creation time in ConfigResolver), just a pass-through read, the
same pattern as MODEL_REPEAT_PENALTY/BASE_URL/etc.
"""

import json
import sqlite3

import pytest

from src.core.planner import Planner


@pytest.fixture
def planner():
    # In-memory connection — _build_model_config never queries the DB,
    # this is just to satisfy Planner's constructor.
    conn = sqlite3.connect(":memory:")
    yield Planner(conn)
    conn.close()


class TestBuildModelConfigMapsModelSeed:
    def test_model_seed_present_in_config(self, planner):
        variant_row = {"config": json.dumps({"MODEL_SEED": 42})}
        model_config = planner._build_model_config(variant_row)
        assert model_config.model_seed == 42

    def test_model_seed_zero_preserved(self, planner):
        """0 is a valid Model Seed — must not be coerced to None."""
        variant_row = {"config": json.dumps({"MODEL_SEED": 0})}
        model_config = planner._build_model_config(variant_row)
        assert model_config.model_seed == 0

    def test_model_seed_absent_key_resolves_none(self, planner):
        variant_row = {"config": json.dumps({"MODEL_TEMPERATURE": 0.7})}
        model_config = planner._build_model_config(variant_row)
        assert model_config.model_seed is None

    def test_model_seed_explicit_null_resolves_none(self, planner):
        variant_row = {"config": json.dumps({"MODEL_SEED": None})}
        model_config = planner._build_model_config(variant_row)
        assert model_config.model_seed is None

    def test_model_seed_independent_of_other_fields(self, planner):
        """MODEL_SEED mapping doesn't interfere with any other ModelConfig field."""
        variant_row = {
            "config": json.dumps(
                {
                    "MODEL_TEMPERATURE": 0.7,
                    "MODEL_REPEAT_PENALTY": 1.1,
                    "MODEL_SEED": 7,
                    "PROVIDER": "deepinfra/turbo",
                }
            )
        }
        model_config = planner._build_model_config(variant_row)
        assert model_config.model_seed == 7
        assert model_config.temperature == 0.7
        assert model_config.repeat_penalty == 1.1
        assert model_config.base_url is None

    def test_model_seed_never_reads_randomization_seed_key(self, planner):
        """RANDOMIZATION_SEED (a Run-level key, never present on a real
        model_variant row) must never leak into model_seed even if present."""
        variant_row = {"config": json.dumps({"RANDOMIZATION_SEED": 7})}
        model_config = planner._build_model_config(variant_row)
        assert model_config.model_seed is None
