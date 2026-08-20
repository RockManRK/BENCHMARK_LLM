---
type: status
audience: ai
last-validated: 2026-08-20
status: implemented
---

# Design: Checkpoint B — Model Seed (`MODEL_SEED`)

**Status: implemented and verified 2026-08-20.** This document is kept as
the design record (architecture, investigation findings, rationale) rather
than rewritten after the fact — for the completed implementation's final
symbol names, regression coverage, and verified baseline, see the Resolved
Issues entry "Model Seed implemented..." in `docs/status/known-issues.md`.
Checkpoint A (Randomization Seed vocabulary separation) is complete and out
of scope here — see `docs/status/seed-vocabulary-separation-investigation.md`.

---

## Part 1 — Single canonical payload (mandatory architectural adjustment)

### What exists today (confirmed by reading the code)

Three independent, hand-written implementations of "build the OpenRouter
chat completion request payload":

1. `src/core/execution_engine.py`'s `api_call_with_retry` builds a
   `request_payload` dict by hand, purely to derive `request_json` for
   audit — **never actually sent**. It then calls
   `self.api_client.chat_completion(model_id=..., temperature=..., ...)`
   with individual scalar kwargs, not this dict.
2. `src/api/client.py`'s `OpenRouterClient.chat_completion` receives those
   kwargs and builds its **own** separate `payload` dict — this is the one
   actually POSTed (`json=payload`).
3. `tests/test_request_config_application.py` re-implements the same
   conditional-omission logic a **third** time, independently, so it cannot
   detect (1) and (2) drifting apart.

### Rejected approach: "both call the same function separately"

My original proposal (two call sites calling `build_chat_completion_payload`
with the same arguments) was rejected as insufficient: even with a shared
builder, `ExecutionEngine` and `OpenRouterClient` would each invoke it once,
producing two separate dict *instances* with equal content — correct today,
but nothing stops a future edit to one call site's arguments from silently
diverging from the other's, since they'd still be two independent call
sites. The requirement is a single object, constructed once, used unmodified
for both purposes.

### Approved architecture

```
ModelConfig
  → build_chat_completion_payload(...)      [src/api/request_payload.py, pure function]
  → ONE payload dict (canonical, single construction)
      → request_json = serialize_json(payload)      [audit]
      → OpenRouterClient.chat_completion(payload=payload)  [transport: json=payload]
```

- **`src/api/request_payload.py`** (new, pure function, no class/staticmethod
  per your preference): `build_chat_completion_payload(model_id, messages,
  *, temperature=None, top_p=None, top_k=None, repeat_penalty=None,
  max_tokens=None, reasoning_effort=None, max_reasoning_tokens=None,
  stop=None, response_format=None, provider=None, model_seed=None,
  debug_enabled=False) -> dict[str, Any]`. Same field order, same
  None-omission semantics as today's two implementations (unchanged for the
  existing 11 fields), plus `seed` (Model Seed) and `debug` (see Part 2).
- **`ExecutionEngine.api_call_with_retry`** is now the **only** place that
  calls `build_chat_completion_payload`. It builds the payload exactly
  once per attempt, immediately derives `request_json` from that same
  object, and passes the **same object, by reference** to
  `self.api_client.chat_completion(payload=payload, base_url=...)`.
- **`CompletionProvider`/`OpenRouterClient.chat_completion` signature
  changes** from ~13 scalar kwargs to:
  ```python
  async def chat_completion(
      self,
      payload: dict[str, Any],
      base_url: str | None = None,
  ) -> CompletionResponse:
  ```
  The client **never reconstructs anything** — it reads `payload["model"]`
  for logging/response identity (removing the separate, now-redundant
  `model_id` param entirely — one less place for the two to disagree), and
  does `json=payload` directly in the `httpx` POST. `base_url` stays a
  separate parameter (it selects which server to talk to — transport
  routing, not part of the JSON body, same as today).
- **Mutability:** plain `dict[str, Any]`, not a frozen dataclass or
  `MappingProxyType`. Reasoning: the payload must be handed unmodified to
  both `serialize_json()` and `httpx`'s `json=` parameter, both of which
  require a plain JSON-serializable dict; wrapping it would require
  unwrapping right before the one step where fidelity matters most,
  defeating the purpose. Immutability here is enforced by construction
  discipline instead: exactly one call site builds it
  (`ExecutionEngine.api_call_with_retry`), nothing downstream (the builder,
  the client) mutates it — verified by the fidelity test in Part 3, which
  asserts the object handed to transport and the one serialized to
  `request_json` are the same content.
- **`tests/test_request_config_application.py`** rewritten to call
  `build_chat_completion_payload` directly, becoming a real regression
  guard.

This removes the entire class of "audited but not sent / sent but not
audited" risk structurally — there is no second construction to drift from
the first, because there is no second construction.

---

## Part 2 — `debug` field: investigation and final design

### Investigation performed (real, controlled, 2 calls total)

Per the standing real-API-testing authorization
(`docs/status/...`; memory-tracked), ran an isolated script — no DB, no
`.env`, no `bcllm.py` code path touched — directly against OpenRouter:
- Model: `google/gemini-2.5-flash-lite` (re-verified available via the
  public `/models` endpoint immediately before use)
- Provider pinned: `google-ai-studio` (re-verified via
  `/models/.../endpoints`, confirmed to list `seed` in
  `supported_parameters`)
- `MODEL_SEED=42`, `temperature=0`, `max_tokens=8`, one short custom
  question, one call with `debug` absent, one call with
  `debug: {"echo_upstream_body": true}` — otherwise byte-identical payloads.

**Observed, not assumed:**

| Question | Finding |
|---|---|
| Does `debug` provide cost/tokens? | **No.** `usage` (prompt_tokens=37, completion_tokens=1, cost=4.059e-06, full `cost_details`/`prompt_tokens_details`) was **identical** in both calls, present in the normal final chunk regardless of `debug`. Already extracted today by `response_parser.py` into `CompletionResponse.cost`/`.input_tokens`/etc. — **not gated by `debug` in any way.** |
| Does `debug` provide the provider actually used? | **No new info.** `"provider": "Google AI Studio"` appeared identically in both responses' top-level fields — already available without `debug`. |
| What does `debug` add? | Exactly one thing: a first SSE chunk with `"debug": {"echo_upstream_body": {...}}` — the request body **as transformed and sent to the upstream provider** (Gemini-native shape here: `contents`, `systemInstruction`, `safetySettings`, `generationConfig` incl. `seed`, `maxOutputTokens`, `temperature`). This is a **request-transformation artifact**, not response metadata. |
| Is `MODEL_SEED` visible in the echo? | **Yes** — our `"seed": 42` appeared as `generationConfig.seed: 42` in the echoed upstream body, confirming OpenRouter forwarded it. **No field anywhere confirms the provider honored it during generation** — the echo shows what was *requested* upstream, never a "seed used" confirmation. Per your rule 6, the system must only ever claim the request asked for a given seed, never that determinism was achieved. |
| Is streaming mandatory? | **Yes**, confirmed empirically (matches OpenRouter's own docs). **No impact on BCLLM** — `stream: true` is already unconditional in the current payload; no code path needs to change for this. |
| Extra cost/latency? | **None observed.** Identical token counts and cost in both calls; the debug chunk itself is not billed. (Single-sample evidence, not a claim about every provider/model.) |
| Is BCLLM's existing client/aggregator ready for this data? | **Mostly already built, unused.** `src/api/stream_aggregator.py::aggregate_streaming_response` already captures `debug_info` from the first chunk into `AggregatedResponse.debug_info`, and `consolidate_streaming_response` already re-derives and includes a `debug` key in its human-readable output — this scaffolding predates this checkpoint and was simply never exercised because nothing ever set `debug: true` in the real payload. `raw_response` (verbatim SSE chunks, unmodified) already flows into `ExecutionResult.raw_response` and is already persisted — so the debug chunk, once actually requested, is captured **losslessly today with zero new persistence**, satisfying "persistência nova só quando os campos atuais não forem suficientes." One real gap found: `src/api/response_parser.py::parse_to_completion_response` computes `aggregated.debug_info` but never attaches it to the returned `CompletionResponse` — harmless (nothing is lost, since `raw_response`/`raw_response_consolidated` already carry it), but means there's no direct, single-field way to read "was there a debug echo" without scanning `raw_response`. Not fixing this now — no consumer needs it yet, and adding a field nobody reads would be exactly the kind of premature persistence the rules above warn against. |

### Design decision: `debug` must flow through the *same* canonical payload

Per your explicit instruction ("Não mantenha deliberadamente a divergência
atual em que debug está no request real, mas ausente de request_json") this
is no longer optional — `build_chat_completion_payload(..., debug_enabled)`
adds `payload["debug"] = {"echo_upstream_body": True}` when enabled, as
part of the one canonical object. Since that same object produces both
`request_json` and the real POST body, `request_json` now **always**
accurately reflects whether debug was requested — by construction, not by
a second implementation kept in sync by hand.

`debug_enabled` itself remains a per-`OpenRouterClient`-instance setting
(`OPENROUTER_DEBUG_ENABLED` env var → `bcllm_execute.py` →
`OpenRouterClient(debug_enabled=...)`, unchanged). `OpenRouterClient` gains
a public read-only `debug_enabled` property (was private-only,
`_debug_enabled`); `ExecutionEngine` reads `self.api_client.debug_enabled`
once per attempt to decide whether to ask `build_chat_completion_payload`
for the `debug` field — the client's own constructed setting stays the
single source of truth, `ExecutionEngine` never duplicates or overrides it.

### Auditability rules applied

- **`request_json` = the canonical payload, verbatim** — including
  `"debug": {"echo_upstream_body": true}` when that was requested (that
  boolean instruction *is* part of our own outgoing request). It never
  contains the API key or `Authorization` header (already true today —
  those live in `httpx`'s `headers=`, never merged into the JSON body).
- **The echoed upstream body (returned in the response) is not
  `request_json`.** It is response data, already captured distinctly in
  `raw_response` (verbatim chunk list) and `raw_response_consolidated`
  (human-readable derived view, via the already-existing
  `consolidate_streaming_response`) — two DB columns already distinct from
  `request_json`. No new column needed; the "request vs. what was actually
  sent upstream, never conflated" requirement is already satisfied by the
  existing three-column shape (`request_json` / `raw_response` /
  `raw_response_consolidated`) once the request side correctly reflects
  `debug` (Part 1's fix) and the response side is correctly requested
  (this section).

### Recommendation: default OFF

`OPENROUTER_DEBUG_ENABLED` stays opt-in, default `false` — no change to
today's default. Reasons: (1) OpenRouter's own documentation states the
`debug` flag is "not for production" and may echo request content back
that wasn't intended to be visible elsewhere; BCLLM's real experiment runs
are this tool's production use, not a dev harness. (2) The echoed shape is
provider/upstream-API-specific (Gemini-native here; would look completely
different for an Anthropic- or OpenAI-shaped upstream) — turning it on
globally across a multi-provider benchmark would produce structurally
inconsistent audit data per model, which is of limited comparative
scientific value by default. It remains fully available, fully audited,
and fully persisted (no data loss) for the researcher who explicitly opts
in for a specific investigative run.

---

## Part 3 — Model Seed design (unchanged from the approved proposal)

Mirrors the existing `PROVIDER`/`MODEL_REPEAT_PENALTY` resolution pattern —
a plain model-variant parameter, no `.env` fallback at variant-creation
time, no `AUTO` state anywhere.

| Layer | Change |
|---|---|
| **CLI flag** | `--model-seed`, type `parse_int_or_system_default` (already exists, reused as-is). Added to `bcllm_model.py`'s `--add-model` parser and `bcllm_experiment.py`'s experiment-creation parser. |
| **`system-default` classification** | `'model_seed'` added to `SYSTEM_DEFAULT_SUPPORTED` in both modules (mirrors `--provider system-default`: breaks inheritance, resolves to `None`). |
| **Experiment creation** (`ConfigResolver.build_experiment_config_dict`) | `"MODEL_SEED": self._resolve_with_force_system_default(getattr(cli_args, 'model_seed', None), "MODEL_SEED", self._parse_int_env)` — CLI > `.env` > `None`. |
| **Model Variant creation** (`ConfigResolver.build_model_config_dict`) | `"MODEL_SEED": self._resolve_cli_or_experiment(getattr(cli_args, 'model_seed', None), exp_config, "MODEL_SEED", parse_int)` — CLI > experiment (inherited) > `None`. No `.env` consultation at this tier. |
| **`AddModelRequest`** (`bcllm_model.py`) | New field `model_seed: int \| ForceSystemDefault \| None = None`. |
| **`ModelConfig`** (`src/core/execution_plan.py`) | New field `model_seed: int \| None = None`. |
| **`Planner`**'s config-row → `ModelConfig` mapping | Add `model_seed=config.get("MODEL_SEED")`. |
| **`variant_signature`** (`src/utils/variant_signature.py`) | `('MODEL_SEED', 'model_seed')` added to `SIGNATURE_FIELD_ORDER` **directly after `MODEL_REPEAT_PENALTY`**: `reasoning, vision, structured, temp, top_p, top_k, repeat_penalty, model_seed, max_tokens, reasoning_tokens, provider, base_url`. Documented and tested as stable going forward. **No back-compat handling for pre-existing stored signatures** — this is pre-production, test-only data (per ADR-003); existing rows simply keep whatever signature they already have, no migration/backfill code is written, and no design justification is based on preserving them. |
| **Request payload** (`src/api/request_payload.py`) | `if model_seed is not None: payload["seed"] = model_seed` — explicit `is not None`, so `0` is sent. `None` omits the key entirely. |
| **`CompletionProvider`/`OpenRouterClient`** | `model_seed` flows in as part of `payload` (see Part 1) — no separate parameter. |
| **`ExecutionEngine`** | Reads `model_config.model_seed`, passes to the one `build_chat_completion_payload` call. `AnswerRandomizer` is untouched — `model_seed` and `run.randomization_seed_effective` are different fields on different objects with no shared code path; tested explicitly (Part 4). |
| **Backend/provider support** | **No filtering.** `model_seed` is sent whenever configured, exactly like every other optional model parameter today (temperature, top_p, ...) — BCLLM never pre-checks a model's `supported_parameters` before sending any of them. If a specific provider/local endpoint rejects `seed`, that surfaces as a normal API error through the existing `_handle_http_error`/error-classification path — never silently dropped. BCLLM never claims `model_seed` guarantees identical responses; it only records that the request asked for a given seed. |
| **`.env` / `.env.example`** | New `MODEL_SEED=` line in "MODEL DEFAULTS", next to `MODEL_REPEAT_PENALTY`, with a comment distinguishing it from `RANDOMIZATION_SEED`. |

### Requirements checklist

All items from your approval message map 1:1 onto the table above:
Experiment + model_variant ownership, never Run, CLI→`.env`→None at
Experiment level, CLI→Experiment(frozen)→None at variant level,
`system-default`→`None`, integer including `0` sent as `"seed"`, `None`
omits the key, no `AUTO` anywhere, mandatory `variant_signature`
participation at the confirmed position, total separation from
`RANDOMIZATION_SEED` (different config keys, different resolvers, never
appears in the same code path), no filtering/silent-dropping by backend,
no promise of deterministic output.

---

## Affected files

**New:**
- `src/api/request_payload.py`

**Payload centralization:**
- `src/api/client.py` — `chat_completion(payload, base_url)` signature;
  `debug_enabled` property; `CompletionProvider` abstract method updated
  identically.
- `src/core/execution_engine.py` — single `build_chat_completion_payload`
  call site; passes the same object to `request_json` and to
  `api_client.chat_completion(payload=...)`.
- `src/api/response_parser.py`, `src/api/stream_aggregator.py` — no
  functional change needed (already handle `debug_info` correctly); read
  during implementation to confirm, not modified unless the fidelity test
  finds a gap.
- `tests/test_request_config_application.py` — rewritten against the real
  function.

**Model Seed:**
- `src/core/config_resolver.py`, `src/core/execution_plan.py`,
  `src/core/planner.py`, `src/utils/variant_signature.py`,
  `src/cli/bcllm_model.py`, `src/cli/bcllm_experiment.py`, `.env`,
  `.env.example`.

**Documentation** (after implementation): `docs/contracts/configuration-hierarchy.md`,
`docs/contracts/determinism.md`, `docs/contracts/system-default-semantics.md`,
`docs/contracts/data-auditability.md` (debug/echo distinction),
`docs/reference/cli-commands.md`, `docs/reference/configuration-reference.md`,
`docs/reference/database-schema.md`, `docs/status/known-issues.md`.
Also, separately (per your "Extra" instruction, same implementation pass):
`docs/contracts/immutability.md` and any other doc still suggesting Run/Experiment
prompts or seeds are mutable after creation.

---

## Part 4 — Tests plan

**Payload centralization + fidelity (mandatory):**
- `tests/unit/api/test_request_payload.py` — unit tests of
  `build_chat_completion_payload`: every field's None-omission; `0`/falsy
  preserved (`model_seed=0`, `top_k=0`); field order; reasoning-conflict
  rule; provider-lock shape; `debug` field presence/absence.
- **`tests/unit/core/test_request_fidelity.py` (new, the mandatory
  fidelity test)** — intercepts the HTTP call (mock `httpx.AsyncClient`/
  transport at the `OpenRouterClient` boundary) and asserts
  `json.loads(request_json) == payload_actually_passed_as_json_to_post`,
  across: no optionals set; all optionals set; `model_seed=None`;
  `model_seed=0`; `model_seed=42`; provider lock present; reasoning
  present; structured output present; debug on vs. off (off: `"debug"` key
  absent from **both** `request_json` and the real payload; on: present
  and identical in both); secrets (API key, `Authorization` header) absent
  from `request_json` and from anything persisted; a synthetic
  debug-enabled mock response carrying an `echo_upstream_body` with
  `generationConfig.seed` — asserts this seed value matches what
  `payload["seed"]` sent, **and** that it lands in `raw_response`/
  `raw_response_consolidated`, never overwriting or merging into
  `request_json` (the two stay distinguishable); debug-related parsing
  failure (malformed/missing debug chunk) does not affect
  `selected_answer`/`is_correct`/any other normal-response field, and does
  not fail the item; persistence idempotency (re-processing the same
  `ExecutionResult` does not duplicate rows) unaffected by any of the
  above.
- `tests/test_request_config_application.py` rewritten to call the real
  builder.
- `tests/unit/api/test_client.py` — `chat_completion(payload=...)` posts
  exactly that payload; `debug_enabled` property reflects constructor arg.

**Model Seed:**
- `tests/test_config_resolver.py` — new test class: CLI > experiment >
  `None` at variant level; CLI > `.env` > `None` at experiment level;
  `system-default` → `None` even with an experiment value present; `0`
  preserved.
- `tests/test_variant_signature.py` — `MODEL_SEED` at the documented
  position; two variants differing only in `--model-seed` produce
  different signatures; the full fixed field order is asserted as a single
  stable list (regression guard for the order itself).
- `tests/unit/core/test_planner_model_seed.py` (new) — config row →
  `ModelConfig.model_seed` mapping; absent key → `None`.
- `tests/unit/core/test_execution_engine_model_seed.py` (new) —
  `model_seed` reaches both the real call and `request_json` identically
  (via the fidelity mechanism above); `randomization_seed`/
  `randomization_enabled` on `ExecutionResult` are unaffected by any
  `model_seed` value.
- **Integration test — seed independence (mandatory):** new test running
  an experiment with `RANDOMIZATION_SEED=7` and `MODEL_SEED=42`
  configured together, proving: the answer-option shuffle (letters
  presented, `option_letter_map`) is determined solely by
  `RANDOMIZATION_SEED=7` and is byte-identical to a run with
  `RANDOMIZATION_SEED=7` and `MODEL_SEED=None`; the API payload's `"seed"`
  field is `42` regardless of `RANDOMIZATION_SEED`'s value; `"seed": 42`
  never appears anywhere in the randomization code path or in
  `option_letter_map`/`options_presented`; `RANDOMIZATION_SEED` never
  appears in the API payload.
- `tests/cli_suite/cases/model.yaml` — `--model-seed 42`; `--model-seed 0`
  preserved; `--model-seed system-default` on an experiment with a
  configured `MODEL_SEED` resolves to `null`; invalid `--model-seed` → exit
  2.
- `tests/cli_suite/cases/experiment.yaml` — `--model-seed` at experiment
  creation, inherited by a variant that omits its own flag.

---

## Completion criteria (per your closing instruction)

On finishing implementation: full `pytest`, full `tests/cli_suite --profile
full --yes`, Essence Guardian review scoped to this checkpoint's diff
(request payload centralization, Model Seed resolution chain,
`variant_signature`), then present baseline + changes — as a checkpoint
separate from Checkpoint A, matching that precedent.
