"""Canonical OpenRouter chat completion payload construction.

This module exists to eliminate the two independently-maintained payload
dicts that used to exist (one in ExecutionEngine, built only for the
`request_json` audit field and never sent; one in OpenRouterClient, built
separately from scalar kwargs and actually POSTed). A single call to
`build_chat_completion_payload` now produces the ONE dict that is both
serialized into `request_json` and handed unmodified to
`OpenRouterClient.chat_completion(payload=...)` for the real HTTP POST —
see docs/status/model-seed-checkpoint-b-design.md, Part 1.

The caller (ExecutionEngine) must construct the payload exactly once per
attempt and pass the same object to both destinations. This module does
not enforce that discipline itself (a plain dict cannot be made read-only
and still be handed directly to `json.dumps`/httpx's `json=` parameter) —
it is verified by tests/unit/core/test_request_fidelity.py instead.
"""

from __future__ import annotations

from typing import Any


def build_chat_completion_payload(
    model_id: str,
    messages: list[dict],
    *,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    repeat_penalty: float | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
    max_reasoning_tokens: int | None = None,
    stop: list[str] | None = None,
    response_format: dict[str, Any] | None = None,
    provider: dict[str, Any] | None = None,
    model_seed: int | None = None,
    debug_enabled: bool = False,
) -> dict[str, Any]:
    """Build the OpenRouter chat completion request payload.

    Fields are inserted in a logical order for human readability (also the
    order `request_json` is persisted in, since Python >=3.7 preserves
    dict insertion order):
    1. Identification & Content  -> model, messages
    2. Output Control            -> response_format, stream, max_tokens
    3. Generation Parameters     -> temperature, top_p, top_k,
                                     repetition_penalty, seed, stop
    4. Special Features          -> reasoning
    5. Provider Locking          -> provider
    6. Debug                     -> debug

    Every optional field is omitted entirely (never `null`) when its value
    is `None` — explicit `is not None` checks throughout, so `0` (for
    `model_seed`, `top_k`, etc.) is preserved, never dropped as falsy.

    Args:
        model_id: Model identifier (e.g. "openai/gpt-4").
        messages: List of message dicts with 'role' and 'content'.
        temperature: Sampling temperature.
        top_p: Nucleus sampling parameter.
        top_k: Top-K sampling parameter.
        repeat_penalty: Repetition penalty (sent as `repetition_penalty`).
        max_tokens: Maximum output tokens.
        reasoning_effort: Reasoning effort level.
        max_reasoning_tokens: Maximum reasoning tokens (mutually exclusive
            with reasoning_effort per OpenRouter contract; effort wins if
            both are set).
        stop: Stop sequences.
        response_format: Structured output format, e.g. {"type": "json_object"}.
        provider: Provider locking config, e.g. {"only": [...], "allow_fallbacks": False}.
        model_seed: Model Seed — sent as the API's "seed" field. Distinct
            from Randomization Seed, which is never sent to the API and
            must never be passed here.
        debug_enabled: When True, adds `debug: {"echo_upstream_body": true}`.

    Returns:
        The canonical request payload dict.
    """
    payload: dict[str, Any] = {
        # --- 1. Identification & Content ---
        "model": model_id,
        "messages": messages,
    }

    # --- 2. Output Control ---
    if response_format is not None:
        payload["response_format"] = response_format

    payload["stream"] = True

    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    # --- 3. Generation Parameters ---
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if top_k is not None:
        payload["top_k"] = top_k
    if repeat_penalty is not None:
        # OpenRouter API uses 'repetition_penalty' as field name
        payload["repetition_penalty"] = repeat_penalty
    if model_seed is not None:
        payload["seed"] = model_seed
    if stop is not None:
        payload["stop"] = stop

    # --- 4. Special Features: Reasoning ---
    # OpenRouter contract: ONLY ONE of effort or max_tokens can be sent.
    # If both are defined, prioritize effort.
    reasoning_config: dict[str, Any] = {}
    if reasoning_effort is not None:
        reasoning_config["effort"] = reasoning_effort
    elif max_reasoning_tokens is not None:
        reasoning_config["max_tokens"] = max_reasoning_tokens

    if reasoning_config:
        payload["reasoning"] = reasoning_config

    # --- 5. Provider Locking ---
    if provider is not None:
        payload["provider"] = provider

    # --- 6. Debug ---
    if debug_enabled:
        payload["debug"] = {"echo_upstream_body": True}

    return payload
