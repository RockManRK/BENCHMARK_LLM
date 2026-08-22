"""Centralized event-name vocabulary and depth-profile tiers for
structured logging.

No module constructs an `event_name` as an ad-hoc string literal anymore
— every event emitted through `src.utils.log_emitter.emit_event` uses a
constant from `Event` here. This is what makes the vocabulary a single
source of truth instead of free-text strings scattered across the
codebase (see docs/status/checkpoint-c-logging-observability-design.md).

Existing event names (already in use as free-text f-string prefixes
before this checkpoint) are migrated here **verbatim** — same string
value, now centralized — not renamed, to avoid an unrelated second rename
on top of an already-large diff.
"""

from __future__ import annotations

import enum


class LogProfile(enum.IntEnum):
    """Depth profiles, cumulative: NORMAL includes everything MINIMAL
    includes, DETAILED includes everything NORMAL includes, and so on.

    WARNING/ERROR/CRITICAL severity events are NEVER gated by profile —
    see log_emitter.py's severity-floor rule. The profile only ever
    decides whether an INFO/DEBUG-severity event is emitted.
    """

    MINIMAL = 0
    NORMAL = 1
    DETAILED = 2
    TRACE = 3

    @classmethod
    def from_str(cls, value: str) -> "LogProfile":
        """Parse a LOG_PROFILE env value. Raises ValueError for anything
        unrecognized — never silently falls back."""
        try:
            return cls[value.strip().upper()]
        except (KeyError, AttributeError):
            valid = ", ".join(member.name for member in cls)
            raise ValueError(
                f"Invalid LOG_PROFILE {value!r}. Valid values: {valid}"
            )


class Event:
    """Stable event_name constants, grouped by the module that emits them."""

    # --- Command lifecycle (bcllm.py) — MINIMAL ---
    COMMAND_START = "command_start"
    COMMAND_END = "command_end"
    COMMAND_INTERRUPTED = "command_interrupted"

    # --- bcllm.py, existing (migrated verbatim) ---
    APPLICATION_START = "application_start"
    PRECONDITION = "precondition"
    COMPOSITE_FLOW = "composite_flow"
    MODE_ROUTING = "mode_routing"

    # --- Entity creation — NORMAL, new ---
    EXPERIMENT_CREATED = "experiment_created"
    MODEL_ADDED = "model_added"
    RUN_CREATED = "run_created"
    QUESTIONS_ADDED = "questions_added"

    # --- Entity removal — NORMAL, new (marco 4B, 2026-08-20). Run has a
    # real soft-delete (status='removed'), unlike QuestionSnapshot. ---
    RUN_REMOVED = "run_removed"

    # --- Refused destructive/mutating commands — NORMAL, new (marco 4A,
    # 2026-08-20). Shared by --remove-experiment and --provider-lock on an
    # existing --experiment, both deliberately disabled to protect the
    # immutability contract — a `reason` field distinguishes which. ---
    MUTATION_REFUSED = "mutation_refused"

    # --- bcllm_provider.py — NORMAL, new (marco 4C, 2026-08-21). Closes
    # the highest-priority C2 gap identified in
    # docs/status/cli-output-classification.md: --resolve-providers
    # mutates model_variants.config (writes PROVIDER) with zero prior log
    # trace, and the module had no logger at all. ---
    PROVIDERS_RESOLVED = "providers_resolved"

    # --- bcllm_execute.py — NORMAL, new (marco 4C, 2026-08-21). Migrates
    # this module's own EXECUTE_START/EXECUTE_COMPLETE/EXECUTE_ERROR
    # old-style logger.info()/logger.error() pipe-delimited f-strings
    # (see cli-output-classification.md) to structured emit_event calls —
    # distinct from planner.py's PLAN_LOADED/execution_engine.py's
    # EXECUTION_START/EXECUTION_COMPLETE, which already existed and are
    # unaffected. ---
    EXECUTE_START = "execute_start"
    EXECUTE_COMPLETE = "execute_complete"
    EXECUTE_ERROR = "execute_error"

    # --- planner.py, existing (migrated verbatim) ---
    PLAN_BUILD_START = "plan_build_start"
    PLAN_LOADED = "plan_loaded"
    PLAN_BUILD_COMPLETE = "plan_build_complete"
    PLAN_VALIDATION_ERROR = "plan_validation_error"
    PLAN_SKIP_EXECUTED = "plan_skip_executed"

    # --- execution_engine.py, existing (migrated verbatim) ---
    EXECUTION_START = "execution_start"
    EXECUTION_COMPLETE = "execution_complete"
    PROGRESS_MILESTONE = "progress_milestone"
    ITEM_START = "item_start"
    ITEM_FAILED = "item_failed"
    ITEM_COMPLETE = "item_complete"
    PROVIDER_LOCKED = "provider_locked"
    REASONING_CONFLICT = "reasoning_conflict"
    MODEL_ERROR = "model_error"
    NO_CONTENT = "no_content"
    VISION_ENABLED = "vision_enabled"
    VISION_DISABLED = "vision_disabled"

    # --- Run/Variant rollups — NORMAL, new ---
    RUN_START = "run_start"
    RUN_COMPLETE = "run_complete"
    VARIANT_START = "variant_start"
    VARIANT_COMPLETE = "variant_complete"

    # --- Provider requested vs. effective — NORMAL, new ---
    PROVIDER_REQUESTED = "provider_requested"
    PROVIDER_EFFECTIVE = "provider_effective"

    # --- async_orchestrator.py, existing (migrated verbatim) ---
    ORCHESTRATOR_START = "orchestrator_start"
    ORCHESTRATOR_COMPLETE = "orchestrator_complete"
    WRITER_TASK_FAILED = "writer_task_failed"
    ABORT_DETECTED = "abort_detected"

    # --- retry.py, existing (migrated verbatim) ---
    RETRY_START = "retry_start"
    RETRY_SUCCESS = "retry_success"
    RETRY_ATTEMPT = "retry_attempt"
    RETRY_NON_RETRYABLE = "retry_non_retryable"
    RETRY_EXHAUSTED = "retry_exhausted"

    # --- client.py, existing (migrated verbatim) ---
    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    API_ERROR = "api_error"
    DEBUG_ENABLED = "debug_enabled"
    DEBUG_DISABLED = "debug_disabled"

    # --- run_finalizer.py, existing (migrated verbatim) ---
    RUN_FINALIZED = "run_finalized"

    # --- async_writer.py, existing (migrated verbatim) ---
    WRITE_OK = "write_ok"
    WRITE_FAIL = "write_fail"
    WRITE_RETRY = "write_retry"
    WRITE_ABORT = "write_abort"

    # --- async_writer.py — new (ADR-004 / ASY-01, 2026-08-22). A received
    # ExecutionResult that could not be persisted as a normal response must
    # still be traceable — these mark the best-effort errors-row audit
    # trail ADR-004 requires, distinct from the pre-existing WRITE_ABORT
    # (which only marks the triggering item's write failure, not whether an
    # auditable trace of it was actually recorded). ERROR/CRITICAL severity
    # — bypass LogProfile gating like WRITE_FAIL/WRITE_ABORT already do. ---
    WRITE_FAILURE_RECORDED = "write_failure_recorded"
    ITEM_ABANDONED_AFTER_WRITER_ABORT = "item_abandoned_after_writer_abort"
    WRITE_FAILURE_TRACE_FAILED = "write_failure_trace_failed"

    # --- result_writer.py, existing (migrated verbatim) ---
    WRITE_COMPLETE = "write_complete"
    WRITE_SKIP_IDEMPOTENT = "write_skip_idempotent"
    WRITE_ERROR = "write_error"

    # --- config_resolver.py — DETAILED, new (closes the zero-logging gap) ---
    CONFIG_RESOLVED = "config_resolved"
    INHERITANCE_DECISION = "inheritance_decision"
    SYSTEM_DEFAULT_APPLIED = "system_default_applied"

    # --- Parsing / randomization — DETAILED, new ---
    PARSE_DECISION = "parse_decision"
    RANDOMIZATION_APPLIED = "randomization_applied"

    # --- TRACE, new ---
    REQUEST_PAYLOAD_TRACE = "request_payload_trace"
    UPSTREAM_ECHO_TRACE = "upstream_echo_trace"
    STREAM_CHUNK_TRACE = "stream_chunk_trace"


# Minimum profile required for an event to be eligible for emission, when
# its severity is INFO/DEBUG (WARNING+ always bypasses this map — see
# log_emitter.py). An event not listed here defaults to LogProfile.NORMAL
# (today's baseline behavior) rather than silently becoming MINIMAL-only
# or TRACE-only.
EVENT_PROFILE: dict[str, LogProfile] = {
    # MINIMAL
    Event.COMMAND_START: LogProfile.MINIMAL,
    Event.COMMAND_END: LogProfile.MINIMAL,
    Event.COMMAND_INTERRUPTED: LogProfile.MINIMAL,
    # NORMAL
    Event.APPLICATION_START: LogProfile.NORMAL,
    Event.PRECONDITION: LogProfile.NORMAL,
    Event.COMPOSITE_FLOW: LogProfile.NORMAL,
    Event.MODE_ROUTING: LogProfile.NORMAL,
    Event.EXPERIMENT_CREATED: LogProfile.NORMAL,
    Event.MODEL_ADDED: LogProfile.NORMAL,
    Event.RUN_CREATED: LogProfile.NORMAL,
    Event.QUESTIONS_ADDED: LogProfile.NORMAL,
    Event.RUN_REMOVED: LogProfile.NORMAL,
    Event.MUTATION_REFUSED: LogProfile.NORMAL,
    Event.PROVIDERS_RESOLVED: LogProfile.NORMAL,
    Event.EXECUTE_START: LogProfile.NORMAL,
    Event.EXECUTE_COMPLETE: LogProfile.NORMAL,
    Event.PLAN_BUILD_START: LogProfile.NORMAL,
    Event.PLAN_LOADED: LogProfile.NORMAL,
    Event.PLAN_BUILD_COMPLETE: LogProfile.NORMAL,
    Event.EXECUTION_START: LogProfile.NORMAL,
    Event.EXECUTION_COMPLETE: LogProfile.NORMAL,
    Event.PROGRESS_MILESTONE: LogProfile.NORMAL,
    Event.ITEM_START: LogProfile.NORMAL,
    Event.ITEM_FAILED: LogProfile.NORMAL,
    Event.ITEM_COMPLETE: LogProfile.NORMAL,
    Event.RUN_START: LogProfile.NORMAL,
    Event.RUN_COMPLETE: LogProfile.NORMAL,
    Event.VARIANT_START: LogProfile.NORMAL,
    Event.VARIANT_COMPLETE: LogProfile.NORMAL,
    Event.PROVIDER_REQUESTED: LogProfile.NORMAL,
    Event.PROVIDER_EFFECTIVE: LogProfile.NORMAL,
    Event.PROVIDER_LOCKED: LogProfile.NORMAL,
    Event.ORCHESTRATOR_START: LogProfile.NORMAL,
    Event.ORCHESTRATOR_COMPLETE: LogProfile.NORMAL,
    Event.RETRY_START: LogProfile.NORMAL,
    Event.RETRY_SUCCESS: LogProfile.NORMAL,
    Event.RETRY_ATTEMPT: LogProfile.NORMAL,
    Event.API_REQUEST: LogProfile.NORMAL,
    Event.API_RESPONSE: LogProfile.NORMAL,
    Event.RUN_FINALIZED: LogProfile.NORMAL,
    Event.WRITE_OK: LogProfile.NORMAL,
    Event.WRITE_COMPLETE: LogProfile.NORMAL,
    Event.VISION_ENABLED: LogProfile.NORMAL,
    Event.VISION_DISABLED: LogProfile.NORMAL,
    Event.DEBUG_ENABLED: LogProfile.NORMAL,
    Event.DEBUG_DISABLED: LogProfile.NORMAL,
    # DETAILED
    Event.CONFIG_RESOLVED: LogProfile.DETAILED,
    Event.INHERITANCE_DECISION: LogProfile.DETAILED,
    Event.SYSTEM_DEFAULT_APPLIED: LogProfile.DETAILED,
    Event.PLAN_SKIP_EXECUTED: LogProfile.DETAILED,
    Event.WRITE_SKIP_IDEMPOTENT: LogProfile.DETAILED,
    Event.PARSE_DECISION: LogProfile.DETAILED,
    Event.RANDOMIZATION_APPLIED: LogProfile.DETAILED,
    # TRACE
    Event.REQUEST_PAYLOAD_TRACE: LogProfile.TRACE,
    Event.UPSTREAM_ECHO_TRACE: LogProfile.TRACE,
    Event.STREAM_CHUNK_TRACE: LogProfile.TRACE,
}
