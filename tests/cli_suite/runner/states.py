"""Result vocabulary for the CLI test suite.

Unifies the three incompatible vocabularies found across the draft docs
(docs/tests/BCLLM_Especificacao_Automacao_Testes.md: 8 English states,
docs/tests/BCLLM_Roteiro_Manual_Testes.md: 6 Portuguese states, and a
stray "DECISÃO PENDENTE" in docs/tests/plano-de-testes.cli.md) into one.

EXPECTED_FAILURE / UNEXPECTED_PASS exist because a real slice of the CLI is
currently dead by routing (Mode.INVALID has no entries in
src/core/mode_matrix.py's _VALID_COMBINATIONS — --help, --list-experiments,
--remove-experiment, --review-experiment and --review-all all exit 1 before
running any logic). Without these two states, the first suite run is a wall
of known-red and the useful signal gets lost; with them, a case that starts
passing again is a visible event instead of silence.
"""

from enum import Enum


class State(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    EXPECTED_FAILURE = "EXPECTED_FAILURE"
    UNEXPECTED_PASS = "UNEXPECTED_PASS"
    BLOCKED = "BLOCKED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    PENDING_SPEC = "PENDING_SPEC"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


# States that represent a genuine problem worth a human's attention.
# Used by report.py to decide what gets a "needs attention" section, and by
# run.py to decide the process exit code.
FAILING_STATES = frozenset({
    State.FAIL,
    State.PARTIAL,
    State.UNEXPECTED_PASS,  # a known-broken command started working — surface it
    State.ERROR,
})
