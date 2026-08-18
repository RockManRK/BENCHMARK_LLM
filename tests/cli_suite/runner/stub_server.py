"""Minimal OpenAI/OpenRouter-compatible HTTP stub for the CLI test suite.

Started once per suite run (see run.py), bound to 127.0.0.1 on an ephemeral
port, and injected into every case's .env as BASE_URL (Fase 3's stub,
viable only because of Seam (b) — src/api/client.py now honors a per-call
base_url instead of always hitting openrouter.ai).

Scenario selection: the requested model_id's LAST path segment picks the
behavior, so a case just does `--add-model test/success`,
`--add-model test/auth-error`, etc.:

- test/success    -> 200, single clear answer (first option letter)
- test/ambiguous   -> 200, content mentioning two option letters (forces
                      AnswerParser confidence=ambiguous -> needs_review)
- test/rate-limit  -> 429 (recoverable, per RetryPolicy.retry_on)
- test/auth-error  -> 401 (non-recoverable)
- test/server-error -> 500 (recoverable)
- test/malformed   -> 200 with a body that is not valid SSE/JSON, to
                      exercise response-parsing error handling
- anything else    -> 200, same as test/success (safe default)

Note: this stub does not simulate a real network timeout (that would mean
literally hanging a thread for the case's whole timeout budget) — timeout
handling is exercised at the httpx/client layer via a case-specific short
`command.timeout` instead, not via this server.

httpx's `client.post(...)` fully buffers the response before
`response.aiter_lines()` is used by src/api/client.py, so a normal
(non-chunked) HTTP response body containing SSE-formatted `data: ` lines is
sufficient — no real server-sent-event streaming is needed here.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


@dataclass
class ReceivedRequest:
    path: str
    model: str
    payload: dict


class _Store:
    """Thread-safe log of every request the stub received, for Fase 3
    contract assertions (e.g. "system-default omits the parameter")."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: list[ReceivedRequest] = []

    def add(self, req: ReceivedRequest) -> None:
        with self._lock:
            self._requests.append(req)

    def all(self) -> list[ReceivedRequest]:
        with self._lock:
            return list(self._requests)

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()


def _sse_body(chunks: list[dict]) -> bytes:
    lines = [f"data: {json.dumps(c)}" for c in chunks]
    lines.append("data: [DONE]")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _scenario_for(model_id: str) -> str:
    return model_id.rsplit("/", 1)[-1]


class _Handler(BaseHTTPRequestHandler):
    store: _Store  # set by make_server()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # silence default stderr logging; the suite's own report covers this

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}

        model_id = payload.get("model", "")
        scenario = _scenario_for(model_id)
        self.store.add(ReceivedRequest(path=self.path, model=model_id, payload=payload))

        options = self._extract_option_letters(payload)
        first_letter = options[0] if options else "A"
        second_letter = options[1] if len(options) > 1 else "B"

        if scenario == "rate-limit":
            self._send(429, json.dumps({"error": {"message": "rate limited (stub)"}}).encode())
            return
        if scenario == "auth-error":
            self._send(401, json.dumps({"error": {"message": "invalid api key (stub)"}}).encode())
            return
        if scenario == "server-error":
            self._send(500, json.dumps({"error": {"message": "internal error (stub)"}}).encode())
            return
        if scenario == "malformed":
            self._send(200, b"not valid sse or json at all")
            return

        if scenario == "ambiguous":
            content = f"It could be {first_letter} or {second_letter}."
        else:
            content = f"The answer is ({first_letter})."

        body = _sse_body([
            {
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            },
        ])
        self._send(200, body)

    def _extract_option_letters(self, payload: dict) -> list[str]:
        # Best-effort: look for "A) ...", "B) ..." patterns in the user
        # message so the stub's "correct" answer is always a real option.
        import re
        text = ""
        for msg in payload.get("messages", []):
            content = msg.get("content", "")
            if isinstance(content, str):
                text += content
        return re.findall(r"\b([A-E])\)", text) or ["A", "B", "C", "D"]

    def _send(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@dataclass
class StubServer:
    server: ThreadingHTTPServer
    thread: threading.Thread
    store: _Store = field(default_factory=_Store)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def requests_log(self) -> list[ReceivedRequest]:
        return self.store.all()


def start_stub_server() -> StubServer:
    store = _Store()

    handler = type("_BoundHandler", (_Handler,), {"store": store})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return StubServer(server=server, thread=thread, store=store)


def dump_requests_log(stub: StubServer, path: Path) -> None:
    records = [
        {"path": r.path, "model": r.model, "payload": r.payload}
        for r in stub.requests_log()
    ]
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
