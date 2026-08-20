"""Integration tests for CLI special-config-value normalization.

Tests the end-to-end behavior of `parse_args_normalized`/
`normalize_special_config_values` (src/core/special_config_values.py)
across realistic parser shapes mirroring bcllm_experiment.py/bcllm_run.py:
- SUPPORTED flags: 'system-default' -> FORCE_SYSTEM_DEFAULT, deprecated
  'null' rejected, 'none' preserved as literal, ordinary values preserved.
- FORBIDDEN flags: 'system-default' AND deprecated 'null' both rejected
  with a dedicated ArgumentError (exit 2 once caught by a module's
  main() -> parser.error()); ordinary values pass through untouched.
- Neither SUPPORTED nor FORBIDDEN (NOT_APPLICABLE): completely untouched,
  even a literal 'system-default' value stays the literal string.

Renamed 2026-08-19 from test_cli_null_semantics.py alongside the
null_semantics.py -> special_config_values.py module rename and the
`_is_nullable_arg` heuristic -> explicit opt-in redesign — see
docs/status/known-issues.md ("_is_nullable_arg's blanket sweep..." and
"bcllm_model.py's 7 numeric flags...") for the two bugs this redesign
fixes. The previous version of this file asserted the OLD, buggy
heuristic behavior as correct (e.g. `--create-experiment system-default`
silently becoming FORCE_SYSTEM_DEFAULT) — those assertions are inverted
here to match the fixed behavior.
"""

import argparse
import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.argv_utils import parse_args_normalized
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT


# =============================================================================
# Fixtures — mirror the real SUPPORTED/FORBIDDEN classification of
# bcllm_experiment.py / bcllm_run.py (see those modules' SYSTEM_DEFAULT_*
# constants and docs/contracts/system-default-semantics.md).
# =============================================================================

@pytest.fixture
def experiment_parser():
    """Parser + classification mirroring bcllm_experiment.py."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-experiment", metavar="NAME")
    parser.add_argument("--experiment", metavar="NAME")
    parser.add_argument("--randomization-seed", type=str, default=None, required=False)
    parser.add_argument("--vision", type=str, default=None, required=False)
    parser.add_argument("--structured", type=str, default=None, required=False)
    parser.add_argument("--add-questions", metavar="SPEC", default=None, required=False)
    parser.add_argument("--add-model", action="append", default=None, required=False)
    return parser


EXPERIMENT_SUPPORTED = {"randomization_seed", "vision", "structured", "add_questions"}
EXPERIMENT_FORBIDDEN = {"create_experiment", "experiment"}


@pytest.fixture
def run_parser():
    """Parser + classification mirroring bcllm_run.py's --run/--randomization-seed."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", metavar="NAME", required=True)
    parser.add_argument("--run", metavar="RUN_ID", default=None, required=False)
    parser.add_argument("--randomization-seed", type=str, default=None, required=False)
    return parser


RUN_SUPPORTED = {"randomization_seed"}
RUN_FORBIDDEN = {"run"}


# =============================================================================
# Part 1: SUPPORTED flags — --randomization-seed, --vision, --structured, --add-questions
# =============================================================================

class TestSupportedFlagsNormalizeSystemDefault:
    """SUPPORTED flags: 'system-default' -> FORCE_SYSTEM_DEFAULT, case-insensitive."""

    @pytest.mark.parametrize("case", ["system-default", "SYSTEM-DEFAULT", "System-Default", "SyStEm-DeFaUlT"])
    def test_randomization_seed_system_default_case_insensitive(self, experiment_parser, case):
        argv = ["--create-experiment", "test_exp", "--randomization-seed", case]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.randomization_seed is FORCE_SYSTEM_DEFAULT

    def test_randomization_seed_equals_syntax_system_default(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--randomization-seed=system-default"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.randomization_seed is FORCE_SYSTEM_DEFAULT

    @pytest.mark.parametrize("case", ["none", "NONE", "None", "NoNe"])
    def test_randomization_seed_none_preserved_as_literal(self, experiment_parser, case):
        """'none' is never special-cased — preserved verbatim (valid reasoning_effort value elsewhere)."""
        argv = ["--create-experiment", "test_exp", "--randomization-seed", case]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.randomization_seed == case

    def test_randomization_seed_numeric_value_preserved(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--randomization-seed", "42"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.randomization_seed == "42"

    def test_randomization_seed_not_provided_is_none(self, experiment_parser):
        argv = ["--create-experiment", "test_exp"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.randomization_seed is None

    @pytest.mark.parametrize("case", ["null", "NULL", "Null", "nUlL"])
    def test_randomization_seed_null_is_rejected(self, experiment_parser, case):
        argv = ["--create-experiment", "test_exp", "--randomization-seed", case]
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)

    def test_vision_system_default_becomes_force_system_default(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--vision", "system-default"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.vision is FORCE_SYSTEM_DEFAULT

    def test_vision_true_preserved(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--vision", "true"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.vision == "true"

    def test_structured_system_default_becomes_force_system_default(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--structured", "system-default"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.structured is FORCE_SYSTEM_DEFAULT

    def test_vision_null_structured_null_both_rejected(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--vision", "null", "--structured", "NULL"]
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated"):
            parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)

    def test_add_questions_system_default_becomes_force_system_default(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--add-questions", "system-default"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.add_questions is FORCE_SYSTEM_DEFAULT

    def test_add_questions_range_preserved(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--add-questions", "1-10"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.add_questions == "1-10"

    def test_add_questions_null_is_rejected(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--add-questions", "null"]
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)

    def test_all_supported_args_system_default(self, experiment_parser):
        argv = [
            "--create-experiment", "test_exp",
            "--randomization-seed", "system-default",
            "--vision", "SYSTEM-DEFAULT",
            "--structured", "System-Default",
            "--add-questions", "SyStEm-DeFaUlT",
        ]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.randomization_seed is FORCE_SYSTEM_DEFAULT
        assert result.vision is FORCE_SYSTEM_DEFAULT
        assert result.structured is FORCE_SYSTEM_DEFAULT
        assert result.add_questions is FORCE_SYSTEM_DEFAULT

    def test_mixed_system_default_none_literals(self, experiment_parser):
        argv = [
            "--create-experiment", "test_exp",
            "--randomization-seed", "system-default",
            "--vision", "none",
            "--structured", "true",
            "--add-questions", "1-10",
        ]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.randomization_seed is FORCE_SYSTEM_DEFAULT
        assert result.vision == "none"
        assert result.structured == "true"
        assert result.add_questions == "1-10"

    def test_all_supported_args_null_rejected(self, experiment_parser):
        argv = [
            "--create-experiment", "test_exp",
            "--randomization-seed", "null",
            "--vision", "NULL",
            "--structured", "Null",
            "--add-questions", "nUlL",
        ]
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated"):
            parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)


# =============================================================================
# Part 2: FORBIDDEN flags — --create-experiment, --experiment, --run
# =============================================================================

class TestForbiddenFlagsRejectSystemDefault:
    """FORBIDDEN flags: 'system-default'/'null' explicitly rejected; ordinary
    values (including one that happens to be a normal identifier) pass
    through untouched — these are identity/structural flags, not
    configuration values."""

    def test_create_experiment_system_default_is_rejected(self, experiment_parser):
        """Regression for the fixed bug: this USED to silently become
        FORCE_SYSTEM_DEFAULT under the old default=None heuristic — see
        docs/status/known-issues.md. Now explicitly rejected."""
        argv = ["--create-experiment", "system-default"]
        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)

    def test_create_experiment_null_is_also_rejected(self, experiment_parser):
        argv = ["--create-experiment", "null"]
        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)

    def test_create_experiment_ordinary_name_untouched(self, experiment_parser):
        argv = ["--create-experiment", "my_experiment"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.create_experiment == "my_experiment"

    def test_run_system_default_is_rejected(self, run_parser):
        """Regression for the fixed bug: --run system-default used to
        silently become the falsy FORCE_SYSTEM_DEFAULT sentinel and vanish
        from dispatch (`elif args.run:` never fired) — see
        docs/status/known-issues.md."""
        argv = ["--experiment", "test_exp", "--run", "system-default"]
        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            parse_args_normalized(run_parser, argv, supported=RUN_SUPPORTED, forbidden=RUN_FORBIDDEN)

    def test_run_literal_id_untouched(self, run_parser):
        argv = ["--experiment", "test_exp", "--run", "run_abc123"]
        result = parse_args_normalized(run_parser, argv, supported=RUN_SUPPORTED, forbidden=RUN_FORBIDDEN)
        assert result.run == "run_abc123"

    def test_run_case_insensitive_rejection(self, run_parser):
        argv = ["--experiment", "test_exp", "--run", "SYSTEM-DEFAULT"]
        with pytest.raises(argparse.ArgumentError, match="does not accept 'system-default' or 'null'"):
            parse_args_normalized(run_parser, argv, supported=RUN_SUPPORTED, forbidden=RUN_FORBIDDEN)


# =============================================================================
# Part 3: NOT_APPLICABLE — dest in neither set is completely untouched
# =============================================================================

class TestNotApplicableFlagsUntouched:
    """A dest not registered in either `supported` or `forbidden` is never
    inspected — even a literal 'system-default' value stays exactly as
    typed. This covers append-list flags (--add-model) and any flag simply
    not part of this mechanism."""

    def test_add_model_system_default_values_untouched(self, experiment_parser):
        """action='append' also structurally can't be swept (value is a
        list, never a bare str) — untouched regardless of registration."""
        argv = [
            "--create-experiment", "test_exp",
            "--add-model", "system-default",
            "--add-model", "openai/gpt-4",
        ]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=EXPERIMENT_FORBIDDEN)
        assert result.add_model == ["system-default", "openai/gpt-4"]

    def test_dest_not_in_either_set_untouched_even_with_literal_system_default(self, experiment_parser):
        """--experiment is deliberately left OUT of both sets here (unlike
        the real bcllm_experiment.py, where it's FORBIDDEN) to prove the
        baseline: an unregistered dest is genuinely never touched."""
        argv = ["--create-experiment", "test_exp", "--experiment", "system-default"]
        result = parse_args_normalized(experiment_parser, argv, supported=EXPERIMENT_SUPPORTED, forbidden=frozenset({"create_experiment"}))
        assert result.experiment == "system-default"


# =============================================================================
# Part 4: No sets passed at all — pure parse, zero normalization
# =============================================================================

class TestNoClassificationPassed:
    """Calling parse_args_normalized with no supported/forbidden (matches
    e.g. bcllm_provider.py, which has no special-value flags at all) does
    a pure parse — nothing is inspected or converted, regardless of
    default=None/required=False."""

    def test_randomization_seed_system_default_untouched_without_classification(self, experiment_parser):
        argv = ["--create-experiment", "test_exp", "--randomization-seed", "system-default"]
        result = parse_args_normalized(experiment_parser, argv)
        assert result.randomization_seed == "system-default"

    def test_null_is_not_rejected_without_classification(self, experiment_parser):
        """No ArgumentError — 'null' is just an ordinary literal string
        when the dest isn't registered as SUPPORTED."""
        argv = ["--create-experiment", "test_exp", "--randomization-seed", "null"]
        result = parse_args_normalized(experiment_parser, argv)
        assert result.randomization_seed == "null"
