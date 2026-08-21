"""Tests for the PROVIDERS_RESOLVED structured logging event as wired
into bcllm_provider.py's handle_resolve_providers (Checkpoint C2 map
applied incrementally, marco 4C first slice, 2026-08-21) — the
highest-priority gap identified in
docs/status/cli-output-classification.md: --resolve-providers mutates
model_variants.config (writes PROVIDER) and previously had ZERO log
trace anywhere, in a module that had no logger at all.

Isolation: hermetic, in-memory SQLite. No real .env/production DB or
OpenRouter API touched — ProviderResolver.resolve is monkeypatched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.logging_config import LoggingConfig, setup_logging


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "plog_test.db"))
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "test.log"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-not-real")
    setup_logging(LoggingConfig(log_file_path=Path(tmp_path / "test.log")))
    yield


def _read_jsonl(tmp_path):
    jsonl_path = tmp_path / "test.jsonl"
    if not jsonl_path.exists():
        return []
    return [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_experiment_with_variant(conn, name="exp_plog"):
    from src.db.repository import ExperimentRepository, VariantRepository
    from src.db.models import Experiment, ModelVariant
    import uuid

    exp_repo = ExperimentRepository(conn)
    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=name,
        config_json=json.dumps({"PROVIDER_SELECTION_STRATEGY": "first"}),
        config_hash="deadbeef",
    )
    exp_repo.save(experiment)

    var_repo = VariantRepository(conn)
    variant = ModelVariant(
        variant_id=f"var_{uuid.uuid4().hex[:8]}",
        experiment_id=experiment.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="sig-001",
        config="{}",
    )
    var_repo.save(variant)
    return experiment


class TestProvidersResolvedEvent:
    def test_emits_event_with_correct_counts_on_success(self, tmp_path, monkeypatch):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_provider import handle_resolve_providers
        from src.api.provider_resolver import ProviderResolver, ProviderResolution

        conn = get_database_connection()
        experiment = _make_experiment_with_variant(conn)

        monkeypatch.setattr(
            ProviderResolver, "resolve",
            lambda self, model_id, strategy: ProviderResolution(
                provider_slug="deepinfra/turbo", strategy_applied=strategy,
                was_fallback=False, warning=None,
            ),
        )
        monkeypatch.setattr(ProviderResolver, "close", lambda self: None)

        exit_code = handle_resolve_providers(experiment.name, conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        resolved = [e for e in events if e["event_name"] == "providers_resolved"]
        assert len(resolved) == 1
        assert resolved[0]["experiment"] == experiment.name
        assert resolved[0]["resolved_count"] == 1
        assert resolved[0]["skipped_count"] == 0
        assert resolved[0]["failed_count"] == 0

    def test_does_not_emit_when_experiment_not_found(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_provider import handle_resolve_providers

        conn = get_database_connection()
        exit_code = handle_resolve_providers("nonexistent_experiment", conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        resolved = [e for e in events if e["event_name"] == "providers_resolved"]
        assert len(resolved) == 0

    def test_does_not_emit_when_no_variants(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_provider import handle_resolve_providers
        from src.db.repository import ExperimentRepository
        from src.db.models import Experiment
        import uuid

        conn = get_database_connection()
        experiment = Experiment(
            experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
            name="exp_no_variants",
            config_json="{}",
            config_hash="deadbeef",
        )
        ExperimentRepository(conn).save(experiment)

        exit_code = handle_resolve_providers(experiment.name, conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        resolved = [e for e in events if e["event_name"] == "providers_resolved"]
        assert len(resolved) == 0
