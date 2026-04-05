"""Streaming response aggregator for SSE (Server-Sent Events) responses.

Este módulo existe porque, a partir da V2, o sistema passou a consumir
respostas em modo streaming real (SSE) usando aiter_lines().

No streaming, cada chunk repete o schema completo, com campos finais
(finish_reason, usage, debug) aparecendo como null até o último chunk.

Na V1, response.json() retornava uma resposta já agregada, escondendo
essa complexidade.

Este agregador reintroduz explicitamente essa agregação, preservando
o raw_response completo para debug e auditoria, enquanto fornece
uma visão lógica única da resposta.

Key Design Decisions:
- NÃO modifica o JSON bruto (preservado para auditoria)
- Preserva TODOS os chunks em raw_response
- Extrai apenas o ÚLTIMO valor não-null de finish_reason e usage
- Captura debug.echo_upstream_body apenas do primeiro chunk
- Não conhece banco de dados, execução ou CLI

Example:
    >>> chunks = [
    ...     {"choices": [], "debug": {...}},  # Debug chunk (vazio)
    ...     {"choices": [{"delta": {"content": "Hello"}}]},
    ...     {"choices": [{"delta": {"content": " world"}}]},
    ...     {"choices": [{"finish_reason": "stop"}], "usage": {...}},  # Final
    ... ]
    >>> aggregated = aggregate_streaming_response(chunks)
    >>> aggregated.content
    "Hello world"
    >>> aggregated.finish_reason
    "stop"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AggregatedResponse:
    """Resultado da agregação de chunks SSE.

    Esta dataclass representa uma visão lógica única de uma resposta
    streaming que originalmente chegou como múltiplos chunks SSE.

    Attributes:
        content: Conteúdo completo concatenado de todos os deltas
        finish_reason: Razão de término (do último chunk não-null)
        usage: Dados de uso/tokens (do último chunk com usage)
        debug_info: Informações de debug (do primeiro chunk apenas)
        raw_response: Lista completa de TODOS os chunks originais

    Example:
        >>> aggregated = AggregatedResponse(
        ...     content="Answer is (B).",
        ...     finish_reason="stop",
        ...     usage={"prompt_tokens": 50, "completion_tokens": 10},
        ...     debug_info=None,
        ...     raw_response=[...],  # Todos os chunks
        ... )
    """

    content: str
    finish_reason: str | None
    usage: dict[str, Any]
    debug_info: dict[str, Any] | None
    raw_response: list[dict[str, Any]]


def aggregate_streaming_response(chunks: list[dict[str, Any]]) -> AggregatedResponse:
    """Agrega múltiplos chunks SSE em uma resposta lógica única.

    Esta função percorre todos os chunks do streaming e:
    1. Concatena todo o conteúdo (delta.content)
    2. Encontra o último finish_reason não-null
    3. Encontra o último usage não-null
    4. Captura debug_info do primeiro chunk

    Args:
        chunks: Lista de chunks SSE recebidos da API

    Returns:
        AggregatedResponse com dados consolidados e raw_response completo

    Example:
        >>> chunks = [
        ...     {"choices": [], "debug": {"echo_upstream_body": {...}}},
        ...     {"choices": [{"delta": {"content": "Hello"}}]},
        ...     {"choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}],
        ...      "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
        ... ]
        >>> result = aggregate_streaming_response(chunks)
        >>> result.content
        "Hello world"
        >>> result.finish_reason
        "stop"
        >>> result.usage
        {"prompt_tokens": 10, "completion_tokens": 5}
    """
    if not chunks:
        return AggregatedResponse(
            content="",
            finish_reason=None,
            usage={},
            debug_info=None,
            raw_response=chunks,
        )

    # 1. Concatenar todo o conteúdo dos deltas
    aggregated_content: str = ""
    for chunk in chunks:
        choices = chunk.get("choices", [])
        if choices and len(choices) > 0:
            choice = choices[0]
            delta = choice.get("delta", {})
            content = delta.get("content", "")
            if content:
                aggregated_content += content

    # 2. Extrair debug_info do PRIMEIRO chunk (se existir)
    debug_info: dict[str, Any] | None = None
    first_chunk = chunks[0]
    if "debug" in first_chunk:
        debug_info = first_chunk["debug"]

    # 3. Encontrar o último finish_reason não-null e último usage
    #    (iterando de trás para frente)
    last_finish_reason: str | None = None
    last_usage: dict[str, Any] = {}

    for chunk in reversed(chunks):
        # Verificar finish_reason
        if last_finish_reason is None:
            choices = chunk.get("choices", [])
            if choices and len(choices) > 0:
                choice = choices[0]
                finish_reason = choice.get("finish_reason")
                if finish_reason is not None:
                    last_finish_reason = finish_reason

        # Verificar usage
        if not last_usage:
            usage = chunk.get("usage")
            if usage and len(usage) > 0:
                last_usage = usage

        # Se já encontramos ambos, podemos parar
        if last_finish_reason is not None and last_usage:
            break

    return AggregatedResponse(
        content=aggregated_content,
        finish_reason=last_finish_reason,
        usage=last_usage,
        debug_info=debug_info,
        raw_response=chunks,
    )


def consolidate_streaming_response(aggregated: AggregatedResponse) -> dict[str, Any]:
    """Produce a human-readable consolidated view of a streaming response.

    This is a DERIVED convenience layer for human readability ONLY.
    It is NOT authoritative — raw_response holds the canonical data.

    Design goals:
    - Preserve ALL information from raw chunks (usage, debug, etc.)
    - Concatenate content and reasoning into single readable strings
    - Keep reasoning_details as a structured array
    - Schema-agnostic pass-through for any provider-specific fields
    - Clearly mark this as a derived view

    Args:
        aggregated: AggregatedResponse from aggregate_streaming_response()

    Returns:
        A dict optimized for human reading, with maximal data preservation.
    """
    chunks = aggregated.raw_response
    if not chunks:
        return {
            "note": "Human-readable derived view. Full fidelity in raw_response.",
            "streaming": True,
            "chunk_count": 0,
        }

    # ================================================================
    # 1. Extract identity fields from first chunk
    # ================================================================
    first_chunk = chunks[0]
    result: dict[str, Any] = {}

    for key in ("id", "object", "created", "model", "provider"):
        if key in first_chunk:
            result[key] = first_chunk[key]

    # ================================================================
    # 2. Collect content, reasoning, and reasoning_details across chunks
    # ================================================================
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    all_reasoning_details: list[dict[str, Any]] = []

    for chunk in chunks:
        choices = chunk.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            continue

        choice = choices[0]
        if not isinstance(choice, dict):
            continue

        delta = choice.get("delta")
        if not isinstance(delta, dict):
            continue

        # Content: concatenate non-empty text
        content = delta.get("content")
        if content:
            content_parts.append(content)

        # Reasoning: concatenate text
        reasoning = delta.get("reasoning")
        if reasoning:
            reasoning_parts.append(reasoning)

        # Reasoning details: merge arrays from all chunks
        rd = delta.get("reasoning_details")
        if rd and isinstance(rd, list):
            all_reasoning_details.extend(rd)

        # Also check top-level reasoning_details on the chunk itself
        # (some providers may place it outside delta)
        chunk_rd = chunk.get("reasoning_details")
        if chunk_rd and isinstance(chunk_rd, list):
            all_reasoning_details.extend(chunk_rd)

    # ================================================================
    # 3. Extract finish_reason and native_finish_reason from last chunk
    #    (scan reversed, take first non-null found)
    # ================================================================
    last_finish_reason: str | None = None
    last_native_finish_reason: str | None = None

    for chunk in reversed(chunks):
        choices = chunk.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            continue

        choice = choices[0]
        if not isinstance(choice, dict):
            continue

        if last_finish_reason is None:
            fr = choice.get("finish_reason")
            if fr is not None:
                last_finish_reason = fr

        if last_native_finish_reason is None:
            nfr = choice.get("native_finish_reason")
            if nfr is not None:
                last_native_finish_reason = nfr

        if last_finish_reason is not None and last_native_finish_reason is not None:
            break

    # ================================================================
    # 4. Extract usage from the chunk where it appears
    #    (scan reversed, take last non-null/non-empty — consistent
    #     with finish_reason extraction; providers emit usage in the
    #     final chunk, so this is the most complete)
    # ================================================================
    usage: dict[str, Any] | None = None
    for chunk in reversed(chunks):
        u = chunk.get("usage")
        if u and isinstance(u, dict) and len(u) > 0:
            usage = u
            break

    # ================================================================
    # 5. Extract debug from first chunk (if present)
    # ================================================================
    debug: dict[str, Any] | None = None
    if "debug" in first_chunk:
        debug = first_chunk["debug"]

    # ================================================================
    # 6. Schema-agnostic pass-through: collect any other field that
    #    appears in any chunk and is not already handled.
    #    First-write-wins policy: correct for identity/metadata fields
    #    (system_fingerprint, etc.) which are constant across chunks.
    # ================================================================
    handled_keys = {
        "id", "object", "created", "model", "provider",
        "choices", "usage", "debug",
        "reasoning_details",  # top-level, already merged
    }

    for chunk in chunks:
        for key, value in chunk.items():
            if key not in handled_keys and key not in result:
                result[key] = value

    # ================================================================
    # 7. Assemble final result
    # ================================================================
    # Add concatenated text fields
    result["content"] = "".join(content_parts)
    result["reasoning"] = "".join(reasoning_parts)

    # Add reasoning_details as structured array (only if non-empty)
    if all_reasoning_details:
        result["reasoning_details"] = all_reasoning_details

    # Add finish_reason fields (only if found)
    if last_finish_reason is not None:
        result["finish_reason"] = last_finish_reason
    if last_native_finish_reason is not None:
        result["native_finish_reason"] = last_native_finish_reason

    # Add usage (only if found)
    if usage is not None:
        result["usage"] = usage

    # Add debug (only if found)
    if debug is not None:
        result["debug"] = debug

    # Add metadata
    result["chunk_count"] = len(chunks)
    result["streaming"] = True

    # Add disclaimer note
    result["note"] = "Human-readable derived view. Full fidelity in raw_response."

    return result
