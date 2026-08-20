"""Cross-module consistency guard for system-default classification.

There is no single central registry for SUPPORTED/FORBIDDEN dest-name sets
— each CLI module declares its own `SYSTEM_DEFAULT_SUPPORTED`/
`SYSTEM_DEFAULT_FORBIDDEN` constants next to its `create_parser()`. That
design let `--experiment` drift out of sync across modules (FORBIDDEN in
bcllm_experiment.py, unclassified everywhere else) — caught by Essence
Guardian review, 2026-08-19, entry [15] in
docs/essence-guardian-log/guardian_memory.md, fixed the same day.

This test is the guard against that class of drift recurring: for every
flag `dest` name declared in more than one module's SUPPORTED/FORBIDDEN
sets, the classification must be identical everywhere it appears. It
imports each module's real constants (not a hand-copied mirror of them),
so it fails the moment a future edit introduces a new inconsistency,
without anyone needing to remember to update this file too.
"""

from __future__ import annotations

from src.cli import bcllm_experiment, bcllm_model, bcllm_run, bcllm_provider


MODULES = {
    "bcllm_experiment": bcllm_experiment,
    "bcllm_model": bcllm_model,
    "bcllm_run": bcllm_run,
    "bcllm_provider": bcllm_provider,
}


def _classification_by_module() -> dict[str, dict[str, str]]:
    """dest -> {module_name: 'SUPPORTED' | 'FORBIDDEN'} for every dest
    classified by at least one module."""
    result: dict[str, dict[str, str]] = {}
    for mod_name, mod in MODULES.items():
        supported = getattr(mod, "SYSTEM_DEFAULT_SUPPORTED", set())
        forbidden = getattr(mod, "SYSTEM_DEFAULT_FORBIDDEN", set())
        overlap = supported & forbidden
        assert not overlap, f"{mod_name}: dest(s) {overlap} classified as BOTH SUPPORTED and FORBIDDEN"
        for dest in supported:
            result.setdefault(dest, {})[mod_name] = "SUPPORTED"
        for dest in forbidden:
            result.setdefault(dest, {})[mod_name] = "FORBIDDEN"
    return result


def test_shared_dest_names_have_identical_classification_across_modules():
    by_dest = _classification_by_module()
    inconsistent = {
        dest: modules
        for dest, modules in by_dest.items()
        if len(modules) > 1 and len(set(modules.values())) > 1
    }
    assert not inconsistent, (
        "The following flag dest names are classified inconsistently across "
        f"modules (must be identical everywhere they appear): {inconsistent}"
    )


def test_experiment_is_forbidden_in_every_module_that_classifies_it():
    """Direct regression for the specific Guardian finding: --experiment
    must be FORBIDDEN wherever it's classified at all."""
    by_dest = _classification_by_module()
    experiment_classification = by_dest.get("experiment", {})
    assert experiment_classification, "expected at least one module to classify 'experiment'"
    for mod_name, classification in experiment_classification.items():
        assert classification == "FORBIDDEN", f"{mod_name} classifies --experiment as {classification}, expected FORBIDDEN"


def test_every_module_with_experiment_required_true_classifies_it():
    """bcllm_model.py, bcllm_run.py, bcllm_provider.py all have a
    required=True --experiment flag; bcllm_experiment.py has an optional
    one in show-mode. All four must classify it (this test exists so a
    future new module with --experiment doesn't silently skip
    classification the way the original bug did)."""
    for mod_name, mod in MODULES.items():
        parser = mod.create_parser()
        dests = {a.dest for a in parser._actions}
        if "experiment" not in dests:
            continue
        supported = getattr(mod, "SYSTEM_DEFAULT_SUPPORTED", set())
        forbidden = getattr(mod, "SYSTEM_DEFAULT_FORBIDDEN", set())
        assert "experiment" in supported or "experiment" in forbidden, (
            f"{mod_name} declares --experiment but classifies it in neither "
            "SYSTEM_DEFAULT_SUPPORTED nor SYSTEM_DEFAULT_FORBIDDEN"
        )
