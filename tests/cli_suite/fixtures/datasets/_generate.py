"""Regenerates the static dataset fixtures in this directory from the real
data/enamed_questions.json.

These files are checked into the repo (not generated at suite run time) so
fixture content is stable, diffable, and auditable — a case's expected
counts (e.g. "8 valid questions") don't silently shift if the real dataset
changes. Re-run this script only when deliberately updating fixtures:

    python tests/cli_suite/fixtures/datasets/_generate.py

Selection is a fixed, deterministic slice of real question IDs (not
random), so re-running this script is a no-op unless the source dataset's
content for those specific IDs changes.
"""

import copy
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE = REPO_ROOT / "data" / "enamed_questions.json"
OUT_DIR = Path(__file__).parent

# Fixed, deterministic selection (not random) — picked once, kept stable.
VALID_IDS = ["Q001", "Q003", "Q004", "Q006", "Q008", "Q011", "Q012", "Q013", "Q014", "Q016"]
ANNULLED_IDS = ["Q002", "Q007"]
IMAGE_IDS = ["Q005"]  # data/enamed_questions.json: Q005/Q053/Q096 have has_image=True


def _load_source() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def _by_id(questions: list[dict]) -> dict[str, dict]:
    return {q["id"]: q for q in questions}


def _write(name: str, dataset: dict) -> None:
    path = OUT_DIR / name
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def main() -> None:
    source = _load_source()
    by_id = _by_id(source["questions"])

    def pick(ids: list[str]) -> list[dict]:
        return [copy.deepcopy(by_id[i]) for i in ids]

    base_meta = {"name": "clitest-fixture", "version": "1.0", "language": "pt-BR", "source": "enamed_questions.json (subset)"}

    # dataset_small_valid: plain valid questions, no images — the default
    # fixture for cases that don't care about edge cases.
    _write("dataset_small_valid.json", {
        "dataset": base_meta,
        "questions": pick(VALID_IDS),
    })

    # dataset_filters: mixes status and has_image so --where/--exclude have
    # something real to filter on.
    _write("dataset_filters.json", {
        "dataset": base_meta,
        "questions": pick(VALID_IDS[:6] + ANNULLED_IDS + IMAGE_IDS),
    })

    # dataset_missing_image: has_image=True but the asset path doesn't
    # exist on disk — for the "declares image that doesn't exist" case.
    missing_image_q = copy.deepcopy(by_id[IMAGE_IDS[0]])
    missing_image_q["meta"]["has_image"] = True
    missing_image_q["assets"] = ["data/assets/does_not_exist.png"]
    _write("dataset_missing_image.json", {
        "dataset": base_meta,
        "questions": [missing_image_q],
    })

    # dataset_empty: structurally valid, zero questions.
    _write("dataset_empty.json", {
        "dataset": base_meta,
        "questions": [],
    })

    # dataset_invalid_schema: valid JSON, wrong shape (missing "questions").
    _write("dataset_invalid_schema.json", {
        "dataset": base_meta,
        "not_questions_at_all": pick(VALID_IDS[:2]),
    })

    # dataset_changed_v2: same IDs as dataset_small_valid, but with altered
    # content — used to prove a snapshot doesn't change if the source file
    # changes after the snapshot was taken.
    changed = pick(VALID_IDS)
    changed[0]["stem"] = "[CHANGED_V2] " + changed[0]["stem"]
    _write("dataset_changed_v2.json", {
        "dataset": base_meta,
        "questions": changed,
    })

    # dataset_invalid_json: not parsable at all (raw text).
    (OUT_DIR / "dataset_invalid_json.json").write_text(
        "{ this is not valid json,,, ]\n", encoding="utf-8"
    )
    print(f"wrote {(OUT_DIR / 'dataset_invalid_json.json').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
