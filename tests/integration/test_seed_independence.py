"""Integration test: RANDOMIZATION_SEED and MODEL_SEED each affect only
their own responsibility (Checkpoint B — mandatory per
docs/status/model-seed-checkpoint-b-design.md, Part 4).

Full path: Experiment/Run/Variant/Snapshot rows in a real (in-memory)
SQLite DB -> Planner.build_plan -> ExecutionEngine. No CLI/subprocess
involved (that level is exercised separately by tests/cli_suite), but
this is the first genuinely end-to-end proof that the two seed concepts
never cross, through the real Planner + ExecutionEngine pipeline, not
just ExecutionEngine in isolation (see test_execution_engine_model_seed.py
for the unit-level version of the same claim).
"""

import asyncio
import json
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.api.client import CompletionResponse
from src.core.answer_parser import AnswerParser
from src.core.execution_engine import ExecutionEngine
from src.core.planner import Planner
from src.core.randomizer import AnswerRandomizer
from src.db.models import Experiment, ModelVariant, QuestionSnapshot, Run
from src.db.repository import (
    ExperimentRepository,
    RunRepository,
    SnapshotRepository,
    VariantRepository,
)


def _setup_experiment(conn, *, randomization_seed, model_seed):
    exp_id = f"exp_{uuid.uuid4().hex[:8]}"
    experiment = Experiment(
        experiment_id=exp_id,
        name=f"seed_independence_{uuid.uuid4().hex[:8]}",
        description="Seed independence integration test",
        config_json=json.dumps(
            {"SYSTEM_PROMPT": None, "USER_PROMPT": "Answer:"}
        ),
        config_hash="abc123",
    )
    ExperimentRepository(conn).save(experiment)

    variant_id = f"var_{uuid.uuid4().hex[:8]}"
    variant = ModelVariant(
        variant_id=variant_id,
        experiment_id=exp_id,
        model_id="openai/gpt-4",
        variant_signature=f"gpt-4|model_seed={model_seed}" if model_seed is not None else "gpt-4",
        config=json.dumps({"MODEL_SEED": model_seed}),
    )
    VariantRepository(conn).save(variant)

    snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
    snapshot = QuestionSnapshot(
        snapshot_id=snapshot_id,
        experiment_id=exp_id,
        json_question_id="Q01",
        question_position=1,
        question_payload=json.dumps(
            {
                "stem": "What is 2+2?",
                "options": ["3", "4", "5", "6"],
                "answer_key": "B",
            }
        ),
    )
    SnapshotRepository(conn).save(snapshot)

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    run = Run(run_id=run_id, experiment_id=exp_id, status="pending", duration=0)
    RunRepository(conn).save(run, config={"RANDOMIZATION_SEED": randomization_seed})

    return {
        "experiment_id": exp_id,
        "experiment_name": experiment.name,
        "variant_id": variant_id,
        "snapshot_id": snapshot_id,
        "run_id": run_id,
    }


def _make_mock_client():
    client = MagicMock()
    client.debug_enabled = False
    client.chat_completion = AsyncMock(
        return_value=CompletionResponse(
            content="The answer is (B).",
            model_id="openai/gpt-4",
            input_tokens=50,
            response_tokens=10,
            latency_ms=500,
        )
    )
    return client


def _execute(conn, experiment_name, run_id, mock_client):
    planner = Planner(conn)
    plan = planner.build_plan(experiment_name, run_ids=[run_id])

    async def _run():
        engine = ExecutionEngine(mock_client, AnswerRandomizer(seed=1), AnswerParser())
        return await engine.execute_async(plan, asyncio.Queue())

    return asyncio.run(_run()), plan


class TestSeedIndependence:
    def test_randomization_seed_and_model_seed_each_affect_only_their_own_responsibility(
        self, in_memory_db
    ):
        ctx = _setup_experiment(in_memory_db, randomization_seed=7, model_seed=42)
        mock_client = _make_mock_client()

        results, plan = _execute(in_memory_db, ctx["experiment_name"], ctx["run_id"], mock_client)

        assert len(results) == 1
        result = results[0]

        # 1) The option shuffle / letter map is determined solely by
        #    RANDOMIZATION_SEED=7 (present, so randomization IS enabled).
        assert result.randomization_enabled is True
        assert result.randomization_seed == 7
        assert result.option_letter_map is not None

        # 2) The API payload's "seed" field is exactly MODEL_SEED=42,
        #    and RANDOMIZATION_SEED (7) never appears in it.
        call_kwargs = mock_client.chat_completion.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["seed"] == 42
        assert "randomization_seed" not in payload
        assert "RANDOMIZATION_SEED" not in payload
        assert 7 not in [v for v in payload.values() if isinstance(v, int)]

        # 3) request_json agrees with the real payload (fidelity, once more)
        assert json.loads(result.request_json)["seed"] == 42

    def test_randomization_shuffle_identical_regardless_of_model_seed(self, in_memory_db):
        """Same RANDOMIZATION_SEED, different MODEL_SEED (None vs 42) ->
        byte-identical option shuffle. Proves MODEL_SEED cannot influence
        AnswerRandomizer even when both are configured together."""
        ctx_with_model_seed = _setup_experiment(
            in_memory_db, randomization_seed=7, model_seed=42
        )
        ctx_without_model_seed = _setup_experiment(
            in_memory_db, randomization_seed=7, model_seed=None
        )

        client1 = _make_mock_client()
        client2 = _make_mock_client()

        results1, _ = _execute(
            in_memory_db, ctx_with_model_seed["experiment_name"], ctx_with_model_seed["run_id"], client1
        )
        results2, _ = _execute(
            in_memory_db,
            ctx_without_model_seed["experiment_name"],
            ctx_without_model_seed["run_id"],
            client2,
        )

        assert results1[0].option_letter_map == results2[0].option_letter_map
        assert results1[0].options_presented == results2[0].options_presented
        assert results1[0].correct_option_presented == results2[0].correct_option_presented

    def test_model_seed_sent_identically_regardless_of_randomization_seed(self, in_memory_db):
        """Same MODEL_SEED, different RANDOMIZATION_SEED (7 vs None) ->
        byte-identical "seed" field sent to the API. Proves
        RANDOMIZATION_SEED cannot influence the API request."""
        ctx_randomized = _setup_experiment(in_memory_db, randomization_seed=7, model_seed=42)
        ctx_not_randomized = _setup_experiment(
            in_memory_db, randomization_seed=None, model_seed=42
        )

        client1 = _make_mock_client()
        client2 = _make_mock_client()

        results1, _ = _execute(
            in_memory_db, ctx_randomized["experiment_name"], ctx_randomized["run_id"], client1
        )
        results2, _ = _execute(
            in_memory_db,
            ctx_not_randomized["experiment_name"],
            ctx_not_randomized["run_id"],
            client2,
        )

        payload1 = client1.chat_completion.call_args.kwargs["payload"]
        payload2 = client2.chat_completion.call_args.kwargs["payload"]
        assert payload1["seed"] == payload2["seed"] == 42
