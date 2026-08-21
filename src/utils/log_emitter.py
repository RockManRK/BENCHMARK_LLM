"""Central event-emission API — the single place every structured log
event passes through.

One internal event object, two serializations, never two independent
constructions — the same "single canonical construction, two
destinations" discipline Checkpoint B established for the API request
payload, applied here to log events (see
docs/status/checkpoint-c-logging-observability-design.md, §3.2):

    fields -> redact() -> {human line, JSONL line}

No log call site builds its own JSON, applies its own redaction, or
decides profile eligibility independently — `emit_event` is the only
function that does any of that.

Design constraints honored here:
- **Severity floor**: WARNING/ERROR/CRITICAL are NEVER suppressed by
  profile — only INFO/DEBUG-severity events are subject to the profile
  gate. This is enforced structurally in this one function, not by
  per-call-site discipline.
- **Redaction is unconditional**: every field passes through
  `src.utils.redaction.redact` before either output is constructed. No
  call site can opt out.
- **Logging failures never break execution**: any exception raised while
  emitting (redaction, serialization, handler I/O) is caught, logged as a
  best-effort fallback line if at all possible, and swallowed — a logging
  bug must never surface as an execution failure or a missing DB write
  (see docs/status/checkpoint-c-logging-observability-design.md, §8).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.utils.log_events import EVENT_PROFILE, LogProfile
from src.utils.redaction import redact

SCHEMA_VERSION = 1

JSONL_LOGGER_NAME = "benchmark_llm.jsonl"


def _current_profile() -> LogProfile:
    """Read LOG_PROFILE from the environment. Falls back to NORMAL for
    anything unset or invalid — validation with a visible, fail-fast
    error happens at `setup_logging()` time (LoggingConfig.validate());
    this fallback is only a defensive backstop so a bad env var can never
    make logging itself raise mid-execution."""
    raw = os.environ.get("LOG_PROFILE", "NORMAL")
    try:
        return LogProfile.from_str(raw)
    except ValueError:
        return LogProfile.NORMAL


def _should_emit(event_name: str, level: int) -> bool:
    if level >= logging.WARNING:
        return True
    required = EVENT_PROFILE.get(event_name, LogProfile.NORMAL)
    return _current_profile() >= required


def _get_jsonl_logger() -> logging.Logger:
    return logging.getLogger(JSONL_LOGGER_NAME)


def _format_human_line(event_name: str, operation_id: str | None, fields: dict[str, Any]) -> str:
    parts = [event_name.upper()]
    if operation_id is not None:
        parts.append(f"operation_id={operation_id}")
    parts.extend(f"{key}={value}" for key, value in fields.items())
    return " | ".join(parts)


def emit_event(
    logger: logging.Logger,
    event_name: str,
    *,
    level: int = logging.INFO,
    operation_id: str | None = None,
    **fields: Any,
) -> None:
    """Emit one structured event as both a human-readable log line and a
    JSONL line — the only entry point for structured logging in this
    codebase.

    Args:
        logger: The component logger (e.g. `get_logger('core.execution_engine')`)
            — used for the human-readable line, so it keeps going through
            the existing dual (file+console) handlers unchanged.
        event_name: A constant from `src.utils.log_events.Event` — never
            an ad-hoc string.
        level: A stdlib logging level (`logging.INFO` default). WARNING+
            always emits regardless of profile.
        operation_id: The current CLI invocation's correlation ID, when
            available. Omitted from events emitted before one exists.
        **fields: Event-family-specific fields (see
            docs/status/checkpoint-c-logging-observability-design.md, §3.3
            for the schema per family). Passed through `redact()` before
            either output is constructed.
    """
    try:
        if not _should_emit(event_name, level):
            return

        redacted_fields = redact(fields)

        logger.log(level, _format_human_line(event_name, operation_id, redacted_fields))

        envelope: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": logging.getLevelName(level),
            "event_name": event_name,
            "schema_version": SCHEMA_VERSION,
        }
        if operation_id is not None:
            envelope["operation_id"] = operation_id
        envelope.update(redacted_fields)

        _get_jsonl_logger().log(level, json.dumps(envelope, ensure_ascii=False, default=str))
    except Exception:
        # Logging must never break execution or hide a scientific result
        # (docs/status/checkpoint-c-logging-observability-design.md, §8).
        # Best-effort visibility, never a raise.
        try:
            logger.exception(f"LOG_EMIT_FAILED | event_name={event_name}")
        except Exception:
            pass
