"""Unit tests for `build_question_snapshot_payload` (src/core/question_loader.py).

Regression coverage for the "double-wrapped meta" bug: the composite flow
(`bcllm --create-experiment X --add-questions ...`) used to build
`question_payload` by copying every question key except a hand-picked
exclusion list that omitted `'meta'`, so the original `meta` dict survived
under a NEW top-level `meta` key -> `{"meta": {...original meta...}}`
instead of `{...original meta...}`. This silently broke
`Planner._build_items`'s `payload_data.get("meta", {}).get("has_image",
False)` lookup for any vision-enabled question added via that path (always
saw `has_image=False`).

Both real call sites (`src/cli/bcllm_experiment.py::_create_question_snapshots`
and `src/cli/bcllm_questions.py::add_questions_action`) now build the
payload exclusively through `build_question_snapshot_payload` — see
docs/status/known-issues.md.
"""

import json

from src.core.question_loader import build_question_snapshot_payload
from src.db.repository import SnapshotRepository
from tests.factories import ExperimentFactory, SnapshotFactory
from src.db.repository import ExperimentRepository


def _question(**overrides) -> dict:
    base = {
        "internal_id": 1,
        "source_id": "Q001",
        "stem": "What is X?",
        "options": {"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"},
        "answer_key": "B",
        "assets": [],
        "meta": {"has_table": False, "has_image": False, "status": "valid", "notes": ""},
    }
    base.update(overrides)
    return base


def test_meta_preserved_at_exactly_one_level_no_double_wrap():
    """meta must never end up nested under its own key."""
    question = _question(meta={"has_image": True, "status": "valid"})

    payload = build_question_snapshot_payload(question)

    assert payload["meta"] == {"has_image": True, "status": "valid"}
    assert "meta" not in payload["meta"]


def test_meta_has_image_directly_accessible():
    """Planner reads payload['meta']['has_image'] directly — must not require unwrapping."""
    question = _question(meta={"has_image": True, "status": "valid"})

    payload = build_question_snapshot_payload(question)

    assert payload["meta"]["has_image"] is True


def test_meta_missing_defaults_to_empty_dict():
    question = _question()
    del question["meta"]

    payload = build_question_snapshot_payload(question)

    assert payload["meta"] == {}


def test_meta_none_normalizes_to_empty_dict():
    question = _question(meta=None)

    payload = build_question_snapshot_payload(question)

    assert payload["meta"] == {}


def test_options_dict_normalized_to_list_preserving_order():
    question = _question(options={"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"})

    payload = build_question_snapshot_payload(question)

    assert payload["options"] == ["opt1", "opt2", "opt3", "opt4"]


def test_options_list_passthrough_unchanged():
    question = _question(options=["opt1", "opt2", "opt3", "opt4"])

    payload = build_question_snapshot_payload(question)

    assert payload["options"] == ["opt1", "opt2", "opt3", "opt4"]


def test_internal_id_and_source_id_preserved():
    question = _question(internal_id=7, source_id="Q007")

    payload = build_question_snapshot_payload(question)

    assert payload["internal_id"] == 7
    assert payload["source_id"] == "Q007"


def test_source_id_absent_maps_to_none_not_dropped():
    question = _question()
    del question["source_id"]

    payload = build_question_snapshot_payload(question)

    assert "source_id" in payload
    assert payload["source_id"] is None


def test_assets_preserved():
    question = _question(assets=["data/assets/image_Q001.png"])

    payload = build_question_snapshot_payload(question)

    assert payload["assets"] == ["data/assets/image_Q001.png"]


def test_stem_and_answer_key_preserved_verbatim():
    question = _question(stem="Original stem text?", answer_key="C")

    payload = build_question_snapshot_payload(question)

    assert payload["stem"] == "Original stem text?"
    assert payload["answer_key"] == "C"


def test_ensure_ascii_false_serialization_preserves_accented_characters():
    """Both real call sites serialize with json.dumps(payload, ensure_ascii=False) — prove
    the payload dict, once serialized that way, keeps accented characters literal rather
    than \\uXXXX-escaped."""
    question = _question(stem="Questão sobre hipertensão arterial sistêmica")

    payload = build_question_snapshot_payload(question)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "Questão" in serialized
    assert "hipertensão" in serialized
    assert "\\u" not in serialized


def test_existing_double_wrapped_snapshot_is_left_completely_unchanged(in_memory_db):
    """The fix applies only to NEW snapshots written through
    build_question_snapshot_payload. Old, already-persisted snapshots
    (including ones with the historical double-wrapped meta shape) are
    never migrated or rewritten — read them back byte-identical."""
    experiment = ExperimentFactory.create(name="legacy-exp")
    ExperimentRepository(in_memory_db).save(experiment)

    old_shaped_payload = {
        "stem": "Legacy question",
        "options": ["A", "B", "C", "D"],
        "answer_key": "A",
        "meta": {"meta": {"has_image": True, "status": "valid"}},
    }
    old_payload_json = json.dumps(old_shaped_payload)

    snapshot = SnapshotFactory.create(
        experiment_id=experiment.experiment_id,
        question_id="Q_LEGACY",
        question_payload=old_payload_json,
    )
    SnapshotRepository(in_memory_db).save(snapshot)

    fetched = SnapshotRepository(in_memory_db).get_by_experiment_and_question(
        experiment.experiment_id, "Q_LEGACY"
    )

    assert fetched.question_payload == old_payload_json
    refetched = json.loads(fetched.question_payload)
    assert refetched["meta"]["meta"]["has_image"] is True
