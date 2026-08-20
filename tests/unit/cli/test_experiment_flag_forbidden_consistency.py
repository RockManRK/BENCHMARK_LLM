"""Regression test for an Essence Guardian finding (2026-08-19, entry [15]
in docs/essence-guardian-log/guardian_memory.md): the first version of the
system-default SUPPORTED/FORBIDDEN/NOT_APPLICABLE fix classified
`--experiment` as FORBIDDEN in bcllm_experiment.py (its own optional
show-mode flag) but left it unclassified (NOT_APPLICABLE) in
bcllm_model.py, bcllm_run.py, and bcllm_provider.py — even though it is
the same identity-selector flag (`required=True` in those three modules).

`required=True` alone protected these from the OLD blanket-sweep bug (the
sweep already excluded required arguments), but the broader principle this
whole fix is built on — identity selectors get 'system-default' explicitly
rejected, never silently treated as a literal — applies uniformly, not
only to flags the old bug happened to touch. Fixed by adding 'experiment'
to each module's SYSTEM_DEFAULT_FORBIDDEN set (bcllm_provider.py gained
one for the first time, since it previously classified nothing).
"""

from __future__ import annotations

import argparse

import pytest

from src.core.argv_utils import parse_args_normalized


class TestExperimentForbiddenAcrossAllModules:
    def test_bcllm_model_experiment_system_default_rejected(self):
        from src.cli.bcllm_model import create_parser, SYSTEM_DEFAULT_SUPPORTED, SYSTEM_DEFAULT_FORBIDDEN

        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            parse_args_normalized(
                create_parser(), ["--experiment", "system-default", "--list-models"],
                supported=SYSTEM_DEFAULT_SUPPORTED, forbidden=SYSTEM_DEFAULT_FORBIDDEN,
            )

    def test_bcllm_run_experiment_system_default_rejected(self):
        from src.cli.bcllm_run import create_parser, SYSTEM_DEFAULT_SUPPORTED, SYSTEM_DEFAULT_FORBIDDEN

        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            parse_args_normalized(
                create_parser(), ["--experiment", "system-default", "--list-runs"],
                supported=SYSTEM_DEFAULT_SUPPORTED, forbidden=SYSTEM_DEFAULT_FORBIDDEN,
            )

    def test_bcllm_provider_experiment_system_default_rejected(self):
        from src.cli.bcllm_provider import create_parser, SYSTEM_DEFAULT_FORBIDDEN

        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            parse_args_normalized(
                create_parser(), ["--experiment", "system-default", "--resolve-providers"],
                forbidden=SYSTEM_DEFAULT_FORBIDDEN,
            )

    def test_bcllm_experiment_experiment_system_default_still_rejected(self):
        """Confirm the original (already-correct) module wasn't disturbed."""
        from src.cli.bcllm_experiment import create_parser, SYSTEM_DEFAULT_SUPPORTED, SYSTEM_DEFAULT_FORBIDDEN

        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            parse_args_normalized(
                create_parser(), ["--experiment", "system-default"],
                supported=SYSTEM_DEFAULT_SUPPORTED, forbidden=SYSTEM_DEFAULT_FORBIDDEN,
            )

    def test_ordinary_experiment_names_still_work_in_all_modules(self):
        """Non-regression: a real experiment name must pass through untouched."""
        from src.cli.bcllm_model import create_parser as model_parser, SYSTEM_DEFAULT_SUPPORTED as MODEL_SUP, SYSTEM_DEFAULT_FORBIDDEN as MODEL_FORB
        from src.cli.bcllm_run import create_parser as run_parser, SYSTEM_DEFAULT_SUPPORTED as RUN_SUP, SYSTEM_DEFAULT_FORBIDDEN as RUN_FORB
        from src.cli.bcllm_provider import create_parser as provider_parser, SYSTEM_DEFAULT_FORBIDDEN as PROVIDER_FORB

        args = parse_args_normalized(model_parser(), ["--experiment", "my_exp", "--list-models"], supported=MODEL_SUP, forbidden=MODEL_FORB)
        assert args.experiment == "my_exp"

        args = parse_args_normalized(run_parser(), ["--experiment", "my_exp", "--list-runs"], supported=RUN_SUP, forbidden=RUN_FORB)
        assert args.experiment == "my_exp"

        args = parse_args_normalized(provider_parser(), ["--experiment", "my_exp", "--resolve-providers"], forbidden=PROVIDER_FORB)
        assert args.experiment == "my_exp"
