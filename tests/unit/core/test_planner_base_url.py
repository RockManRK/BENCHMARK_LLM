"""Tests for Planner._build_model_config's BASE_URL propagation.

Context: the variant's resolved BASE_URL (config_resolver.py builds it as
CLI --url > experiment default > None) was being silently dropped when the
Planner translated a variant's config JSON into a ModelConfig for the
ExecutionEngine. That is the seam that made --url effectively a no-op at
execution time. This test isolates _build_model_config directly against a
minimal sqlite3.Row rather than exercising the full experiment/run schema
(tests/unit/core/test_planner.py's fixtures currently fail for an unrelated,
pre-existing reason — a schema/fixture drift on 'system_prompt').
"""

import json
import sqlite3

import pytest

from src.core.planner import Planner


def _variant_row(config: dict) -> sqlite3.Row:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (config TEXT)")
    conn.execute("INSERT INTO t (config) VALUES (?)", (json.dumps(config),))
    row = conn.execute("SELECT config FROM t").fetchone()
    conn.close()
    return row


@pytest.fixture
def planner():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return Planner(db_connection=conn)


class TestBuildModelConfigBaseUrl:
    def test_base_url_present_in_config_is_propagated(self, planner):
        row = _variant_row({"BASE_URL": "http://127.0.0.1:8080/v1"})

        model_config = planner._build_model_config(row)

        assert model_config.base_url == "http://127.0.0.1:8080/v1"

    def test_base_url_absent_from_config_is_none(self, planner):
        """Not specified must mean 'inherit / use provider default', same
        semantics as every other ModelConfig field."""
        row = _variant_row({"MODEL_TEMPERATURE": 0.7})

        model_config = planner._build_model_config(row)

        assert model_config.base_url is None

    def test_base_url_alongside_other_params(self, planner):
        row = _variant_row({
            "BASE_URL": "https://openrouter.ai/api/v1",
            "MODEL_TEMPERATURE": 0.5,
            "MODEL_REASONING_EFFORT": "high",
        })

        model_config = planner._build_model_config(row)

        assert model_config.base_url == "https://openrouter.ai/api/v1"
        assert model_config.temperature == 0.5
        assert model_config.reasoning_effort == "high"
