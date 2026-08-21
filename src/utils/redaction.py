"""Central redaction policy for logging/diagnostic output.

Applied inside the single event-emission path (`src.utils.log_emitter`)
before either the human line or the JSONL line is constructed — no log
call site is allowed to bypass it. This mirrors the "one canonical
construction" discipline already used for the request payload (Checkpoint
B) and for events themselves (Checkpoint C): redaction is not a
per-caller responsibility.

Redaction applies ONLY to what is about to be written to a log handler.
It never touches the in-memory objects being logged (`redact()` returns a
new, redacted copy — it never mutates its input) and never touches
anything persisted to the database (DB columns are written from the
original, unredacted objects — see docs/status/model-seed-checkpoint-b-design.md
and docs/status/checkpoint-c-logging-observability-design.md for the full
"logs are a third, distinct record" principle).
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "***REDACTED***"

# Case-insensitive match on dict keys that are secret-shaped by name alone
# — the value is redacted regardless of its own shape.
_SECRET_KEY_PATTERN = re.compile(
    r"^(api[_-]?key|apikey|authorization|cookie|set-cookie|token|secret|"
    r"password|passwd|x-api-key|client[_-]?secret|private[_-]?key)$",
    re.IGNORECASE,
)

# `Authorization: Bearer <token>` (or a bare "Bearer <token>" fragment)
# found inside a string — covers a secret accidentally interpolated into
# free text, not only structured dict values.
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)

# Credentials embedded in a URL: https://user:pass@host/...
_URL_CREDENTIALS_PATTERN = re.compile(r"(https?://)([^\s/@]+):([^\s/@]+)@")

# A generic "key=value"/"key: value" fragment inside free text, where key
# is secret-shaped — covers exception messages like
# "connection failed: api_key=sk-abc123 invalid".
_INLINE_KV_PATTERN = re.compile(
    r"\b(api[_-]?key|apikey|authorization|token|secret|password|passwd|"
    r"x-api-key)\s*[=:]\s*\S+",
    re.IGNORECASE,
)


def _redact_string(value: str) -> str:
    value = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", value)
    value = _URL_CREDENTIALS_PATTERN.sub(rf"\1{REDACTED}:{REDACTED}@", value)
    value = _INLINE_KV_PATTERN.sub(
        lambda m: f"{m.group(1)}={REDACTED}", value
    )
    return value


def redact(obj: Any) -> Any:
    """Return a redacted COPY of obj. Never mutates the input.

    Recurses through dicts (keys checked by name, values recursed),
    lists, and tuples. Strings are scanned for secret-shaped patterns
    (Bearer tokens, URL credentials, inline key=value fragments). Every
    other type (int, float, bool, None, and anything not otherwise
    handled) is returned as-is.

    Args:
        obj: Any value about to be written to a log handler — a payload
             dict, a headers dict, an exception's str(), a plain message
             string, etc.

    Returns:
        A redacted copy. `obj` itself is never modified.
    """
    if isinstance(obj, dict):
        result: dict[Any, Any] = {}
        for key, value in obj.items():
            if isinstance(key, str) and _SECRET_KEY_PATTERN.match(key.strip()):
                result[key] = REDACTED
            else:
                result[key] = redact(value)
        return result
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(redact(item) for item in obj)
    if isinstance(obj, str):
        return _redact_string(obj)
    return obj
