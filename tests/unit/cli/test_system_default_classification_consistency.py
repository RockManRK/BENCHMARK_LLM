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

from src.cli import bcllm_experiment, bcllm_model, bcllm_run, bcllm_provider, bcllm_questions, bcllm_execute


MODULES = {
    "bcllm_experiment": bcllm_experiment,
    "bcllm_model": bcllm_model,
    "bcllm_run": bcllm_run,
    "bcllm_provider": bcllm_provider,
    # Added 2026-08-20 (marco 4A pre-4B diff audit, Essence Guardian
    # finding): bcllm_questions.py's SYSTEM_DEFAULT_FORBIDDEN also
    # classifies 'experiment' (shared with the 4 modules above) — this
    # guard's whole purpose is catching exactly that kind of shared-dest
    # drift, so it must cover every module that classifies a dest, not
    # only the ones present when the guard was first written.
    "bcllm_questions": bcllm_questions,
    # Added 2026-08-21 (marco 4C): bcllm_execute.py had ZERO system-default
    # classification of any kind before this marco (its pre-conversion
    # main() called plain parser.parse_args(), never
    # parse_args_normalized) — --experiment/--run are now FORBIDDEN like
    # every other module's identity selectors.
    "bcllm_execute": bcllm_execute,
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


def declared_dests(mod_name: str, mod) -> set[str]:
    """Test-infrastructure-only helper (2026-08-20, CLI Typer migration
    marco 4A) — resolves a module's declared flag `dest` names whether
    it's still argparse-based (`mod.create_parser()`, `.dest` per action)
    or has been converted to a Typer command
    (`src/cli/commands/<name>.py`'s `_command.params`, `.name` per
    param — Click's equivalent of argparse's `dest`, verified identical
    in meaning during the conversion). Deliberately NOT exposed outside
    this test file — production code never needs to know which modules
    are Typer vs. argparse; only this cross-module consistency check
    does, and only until all 4 modules here have migrated (4B/4C)."""
    if hasattr(mod, "create_parser"):
        parser = mod.create_parser()
        return {a.dest for a in parser._actions}

    import importlib

    short_name = mod_name.removeprefix("bcllm_")
    cmd_module = importlib.import_module(f"src.cli.commands.{short_name}")
    return {p.name for p in cmd_module._command.params}


def test_every_module_with_experiment_required_true_classifies_it():
    """bcllm_model.py, bcllm_run.py, bcllm_provider.py all have a
    required=True --experiment flag; bcllm_experiment.py has an optional
    one in show-mode. All four must classify it (this test exists so a
    future new module with --experiment doesn't silently skip
    classification the way the original bug did)."""
    for mod_name, mod in MODULES.items():
        dests = declared_dests(mod_name, mod)
        if "experiment" not in dests:
            continue
        supported = getattr(mod, "SYSTEM_DEFAULT_SUPPORTED", set())
        forbidden = getattr(mod, "SYSTEM_DEFAULT_FORBIDDEN", set())
        assert "experiment" in supported or "experiment" in forbidden, (
            f"{mod_name} declares --experiment but classifies it in neither "
            "SYSTEM_DEFAULT_SUPPORTED nor SYSTEM_DEFAULT_FORBIDDEN"
        )
