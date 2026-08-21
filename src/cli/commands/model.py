"""Typer command definition for the `bcllm_model.py` CLI surface
(--experiment, --add-model, --list-models, --remove-model, plus every
model-level config flag: --url, --max-tokens, --reasoning,
--repeat-penalty, --temperature, --top-k, --top-p, --reasoning-tokens,
--vision, --structured, --provider, --model-seed, --output) — CLI
migration marco 4B, second slice (2026-08-20).

External syntax is unchanged: same flag names, types, choices, and
special values (system-default/null) as the argparse implementation it
replaces. Only the internal parsing mechanism is new. Not registered as a
public Typer subcommand tree — invoked programmatically by
`bcllm_model.py`'s `parse_model_argv()`, mirroring
`src/cli/commands/{questions,experiment,run}.py`'s established pattern
exactly.

`--reasoning` is the one flag here with a real difference from its
`bcllm_experiment.py` counterpart: it has a `choices=` restriction
(`none`/`minimal`/`low`/`medium`/`high`/`xhigh`/`system-default`) in the
argparse version, so invalid values (including the deprecated `'null'`,
which is NOT one of the choices) are rejected by argparse's own
choice-validation — a DIFFERENT, earlier rejection path than
`normalize_special_config_values`'s generic deprecated-`'null'` message
used by every plain-string SUPPORTED flag. Replicated here via a real
`Enum` (Typer validates against enum values, producing the same
choice-restricted behavior), with `system-default` as one of the literal
enum values, converted to `FORCE_SYSTEM_DEFAULT` in the command body —
NOT via `typer_str_or_system_default`, which would accept any string.

`--max-reasoning` removed 2026-08-21 (user decision, reasoning
effort/tokens exclusivity checkpoint): it was a true, undocumented
synonym of `--reasoning-tokens` — identical help text, fed the exact
same `MODEL_MAX_TOKENS_REASONING` key via a since-removed `or` fallback
in `ConfigResolver` that also silently discarded a legitimate `0`/
`system-default` value. No alias, no deprecation shim — see
docs/status/known-issues.md.

`--reasoning` and `--reasoning-tokens` are mutually exclusive at THIS
layer (OpenRouter's `reasoning` object accepts only one of `effort`/
`max_tokens` — never both): passing both concretely on the same command
is a usage error (exit 2), checked in the command body below.
`--reasoning-tokens` also rejects 0 and negative values as a usage error
— Anthropic's own documented floor is 1024 tokens regardless of what's
requested, so persisting a literal `0` would misrepresent what actually
happens at execution; `--reasoning none` already exists as the clean way
to disable reasoning. Inheritance-level suppression (a concrete value at
this layer suppressing an inherited value for the OTHER field) is
handled downstream, in `ConfigResolver._resolve_reasoning_pair` — not
here, since it requires the experiment's config, which this module
doesn't have.

`--output` is parsed and validated (choices) for CLI compatibility only —
never read by any handler, matching the argparse version (a pre-existing,
documented dead flag, see docs/status/known-issues.md).
"""

from __future__ import annotations

import enum
import sys
from dataclasses import dataclass

import typer

from src.cli.param_types import (
    typer_float_or_system_default,
    typer_int_or_system_default,
    typer_reject_special_values,
    typer_str_or_system_default,
)
from src.core.argv_utils import ParserExit
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT, ForceSystemDefault


class OutputFormat(str, enum.Enum):
    console = "console"
    json = "json"
    csv = "csv"
    markdown = "markdown"


class ReasoningEffort(str, enum.Enum):
    none = "none"
    minimal = "minimal"
    low = "low"
    medium = "medium"
    high = "high"
    xhigh = "xhigh"
    system_default = "system-default"


IntOrSD = int | ForceSystemDefault | None
FloatOrSD = float | ForceSystemDefault | None
StrOrSD = str | ForceSystemDefault | None


@dataclass(frozen=True)
class ModelParsedArgs:
    """Typed replacement for argparse.Namespace — field names mirror the
    original argparse dest names exactly, so ConfigResolver.build_model_config_dict's
    duck-typed getattr() access works identically against this dataclass
    as it did against argparse.Namespace."""

    experiment: str
    add_model: str | None
    list_models: bool
    remove_model: str | None
    output: str
    url: str | None
    max_tokens: IntOrSD
    reasoning: StrOrSD
    repeat_penalty: FloatOrSD
    temperature: FloatOrSD
    top_k: IntOrSD
    top_p: FloatOrSD
    reasoning_tokens: IntOrSD
    vision: StrOrSD
    structured: StrOrSD
    provider: StrOrSD
    model_seed: IntOrSD


def _model_command(
    experiment: str = typer.Option(
        ..., "--experiment", callback=typer_reject_special_values, metavar="NAME",
        help="Experiment name",
    ),
    add_model: str = typer.Option(
        None, "--add-model", callback=typer_reject_special_values, metavar="MODEL_ID",
        help="Add model variant (format: provider/model-name)",
    ),
    list_models: bool = typer.Option(
        False, "--list-models", help="List all models in experiment",
    ),
    remove_model: str = typer.Option(
        None, "--remove-model", callback=typer_reject_special_values, metavar="VARIANT_ID",
        help="Remove model variant (hard delete — accepted as-is, see docs/status/known-issues.md)",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.console, "--output", help="Output format",
    ),
    url: str = typer.Option(
        None, "--url", callback=typer_reject_special_values, metavar="URL",
        help="BASE_URL - Model endpoint URL",
    ),
    max_tokens: str = typer.Option(
        None, "--max-tokens", callback=typer_int_or_system_default, metavar="N",
        help="MODEL_MAX_TOKENS_TOTAL - Maximum total tokens",
    ),
    reasoning: ReasoningEffort = typer.Option(
        None, "--reasoning",
        help="MODEL_REASONING_EFFORT - Reasoning effort level",
    ),
    repeat_penalty: str = typer.Option(
        None, "--repeat-penalty", callback=typer_float_or_system_default, metavar="N",
        help="MODEL_REPEAT_PENALTY - Repetition penalty",
    ),
    temperature: str = typer.Option(
        None, "--temperature", callback=typer_float_or_system_default, metavar="N",
        help="MODEL_TEMPERATURE - Sampling temperature",
    ),
    top_k: str = typer.Option(
        None, "--top-k", callback=typer_int_or_system_default, metavar="N",
        help="MODEL_TOP_K - Top-K sampling",
    ),
    top_p: str = typer.Option(
        None, "--top-p", callback=typer_float_or_system_default, metavar="N",
        help="MODEL_TOP_P - Top-P sampling",
    ),
    reasoning_tokens: str = typer.Option(
        None, "--reasoning-tokens", callback=typer_int_or_system_default, metavar="N",
        help="MODEL_MAX_TOKENS_REASONING - Maximum reasoning tokens (positive "
             "integer; mutually exclusive with --reasoning on this command)",
    ),
    vision: str = typer.Option(
        None, "--vision", callback=typer_str_or_system_default, metavar="VALUE",
        help="Enable vision. Valid values: true, false, null (case-insensitive). Default: false",
    ),
    structured: str = typer.Option(
        None, "--structured", callback=typer_str_or_system_default, metavar="VALUE",
        help="Enable structured outputs. Valid values: true, false, null (case-insensitive). Default: false",
    ),
    provider: str = typer.Option(
        None, "--provider", callback=typer_str_or_system_default, metavar="PROVIDER_SLUG",
        help="OpenRouter provider slug (e.g., deepinfra/turbo)",
    ),
    model_seed: str = typer.Option(
        None, "--model-seed", callback=typer_int_or_system_default, metavar="N",
        help="MODEL_SEED - Sent as the API request's 'seed' field for "
             "deterministic inference. Distinct from Randomization Seed "
             "(--randomization-seed on --add-run), which controls only "
             "answer-option shuffling and is never sent to the API.",
    ),
) -> ModelParsedArgs:
    """The Typer command body. Returns a ModelParsedArgs on success —
    Click threads this return value back through `.main()`. Only reached
    when per-option parsing/callbacks all succeeded; the cross-option
    mutex-group check below is the one usage-error class no single
    option's callback can express.
    """
    reasoning_resolved: StrOrSD
    if reasoning is None:
        reasoning_resolved = None
    elif reasoning is ReasoningEffort.system_default:
        reasoning_resolved = FORCE_SYSTEM_DEFAULT
    else:
        reasoning_resolved = reasoning.value

    # --reasoning-tokens rejects 0/negative as a usage error — see the
    # module docstring for why (Anthropic's real 1024-token floor makes
    # persisting a literal 0 misleading; --reasoning none already exists
    # to disable reasoning cleanly).
    if isinstance(reasoning_tokens, int) and reasoning_tokens <= 0:
        raise typer.BadParameter(
            f"--reasoning-tokens must be a positive integer, got {reasoning_tokens}. "
            "Use --reasoning none to disable reasoning, or omit --reasoning-tokens "
            "to use the provider default."
        )

    # OpenRouter's reasoning object accepts only ONE of effort/max_tokens
    # — a concrete value for BOTH on the same command is a usage error,
    # not something to silently resolve by priority (see module
    # docstring). Inheritance-level suppression is handled downstream in
    # ConfigResolver._resolve_reasoning_pair.
    reasoning_is_concrete = reasoning_resolved is not None and reasoning_resolved is not FORCE_SYSTEM_DEFAULT
    reasoning_tokens_is_concrete = reasoning_tokens is not None and reasoning_tokens is not FORCE_SYSTEM_DEFAULT
    if reasoning_is_concrete and reasoning_tokens_is_concrete:
        raise typer.BadParameter(
            "--reasoning and --reasoning-tokens are mutually exclusive — "
            "OpenRouter's reasoning object accepts only one of effort/max_tokens. "
            "Set --reasoning-tokens to system-default (or omit it) if you want "
            "--reasoning's effort level to apply."
        )

    group_flags_given = sum([
        add_model is not None,
        list_models,
        remove_model is not None,
    ])
    if group_flags_given == 0:
        raise typer.BadParameter(
            "one of the arguments --add-model --list-models --remove-model is required"
        )
    if group_flags_given > 1:
        raise typer.BadParameter(
            "--add-model, --list-models, and --remove-model are mutually exclusive"
        )

    return ModelParsedArgs(
        experiment=experiment,
        add_model=add_model,
        list_models=list_models,
        remove_model=remove_model,
        output=output.value,
        url=url,
        max_tokens=max_tokens,
        reasoning=reasoning_resolved,
        repeat_penalty=repeat_penalty,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
        reasoning_tokens=reasoning_tokens,
        vision=vision,
        structured=structured,
        provider=provider,
        model_seed=model_seed,
    )


_app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
_app.command()(_model_command)
_command = typer.main.get_command(_app)


def parse_model_argv(argv: list[str]) -> ModelParsedArgs:
    """argv -> ModelParsedArgs, the ONE parsing entry point for this
    module's CLI surface — replaces `create_parser()` +
    `parse_args_normalized()`. Raises ParserExit for any usage error or
    `--help`, exactly matching NonExitingArgumentParser's contract: on a
    non-zero status the error has ALREADY been written to stderr by this
    function (via Click's own UsageError.show()) — callers must not print
    it again, only translate `.status` into their return code.
    """
    try:
        result = _command.main(args=argv, standalone_mode=False, prog_name="bcllm")
    except typer._click.exceptions.UsageError as e:
        e.show(file=sys.stderr)
        raise ParserExit(e.exit_code, str(e)) from None
    except typer._click.exceptions.Exit as e:
        raise ParserExit(e.exit_code if hasattr(e, "exit_code") else 0, None) from None

    if not isinstance(result, ModelParsedArgs):
        # Click intercepted before the command body ran (e.g. --help) and
        # returned its own exit code directly instead of our dataclass.
        raise ParserExit(result if isinstance(result, int) else 0, None)

    return result
