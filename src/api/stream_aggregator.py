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
    """Produce a clean, human-readable representation of a streaming response.

    The raw SSE chunks contain valuable data spread across multiple fragments:
    - reasoning text accumulated across many chunks
    - content text accumulated across many chunks
    - metadata (id, provider, model) repeated identically in every chunk
    - finish_reason, native_finish_reason, usage only in final chunks

    This function produces a single dict that:
    - Keeps all unique metadata once (from first chunk)
    - Concatenates ALL delta.content across chunks
    - Concatenates ALL delta.reasoning across chunks
    - Concatenates ALL delta.reasoning_details text entries across chunks
    - Preserves final finish_reason, native_finish_reason, usage
    - Preserves debug info from first chunk
    - NO data is lost — only deduplicated where identically repeated

    This is NOT used for API parsing — it is purely for observability,
    stored in the responses.raw_response column for human inspection.

    Args:
        aggregated: AggregatedResponse from aggregate_streaming_response()

    Returns:
        A clean dict preserving ALL meaningful data from the stream.
    """
    chunks = aggregated.raw_response
    if not chunks:
        return {
            "content": "",
            "finish_reason": None,
            "usage": None,
            "debug": None,
            "streaming": True,
            "chunk_count": 0,
        }

    # Extract metadata once from first chunk (repeated identically in all)
    first = chunks[0]
    metadata = {}
    for key in ("id", "object", "created", "model", "provider"):
        if key in first:
            metadata[key] = first[key]

    # Concatenate content and reasoning across ALL chunks
    concatenated_content: str = ""
    concatenated_reasoning: str = ""
    concatenated_reasoning_details: list[dict] = []

    # Track the last non-null finish_reason and native_finish_reason
    last_finish_reason: str | None = None
    last_native_finish_reason: str | None = None

    for chunk in chunks:
        choices = chunk.get("choices", [])
        if not choices:
            continue

        choice = choices[0]
        delta = choice.get("delta", {})
        finish = choice.get("finish_reason")
        native_finish = choice.get("native_finish_reason")

        # Accumulate content
        content = delta.get("content")
        if content:
            concatenated_content += content

        # Accumulate reasoning text
        reasoning = delta.get("reasoning")
        if reasoning:
            concatenated_reasoning += reasoning

        # Accumulate reasoning_details
        details = delta.get("reasoning_details")
        if details:
            for detail in details:
                if isinstance(detail, dict):
                    detail_text = detail.get("text", "")
                    if detail_text:
                        concatenated_reasoning_details.append({
                            "text": detail_text,
                            "type": detail.get("type"),
                            "format": detail.get("format"),
                            "index": detail.get("index"),
                        })

        # Track final finish reasons (search all chunks, not just reversed)
        if finish is not None:
            last_finish_reason = finish
        if native_finish is not None:
            last_native_finish_reason = native_finish

    # Build consolidated response
    result: dict[str, Any] = {}

    # Metadata (only once, not repeated per chunk)
    if metadata:
        result.update(metadata)

    # Concatenated content — the final visible text
    result["content"] = concatenated_content

    # Concatenated reasoning — the full thinking process across all chunks
    if concatenated_reasoning:
        result["reasoning"] = concatenated_reasoning

    # Concatenated reasoning details — structured reasoning entries
    if concatenated_reasoning_details:
        result["reasoning_details"] = concatenated_reasoning_details

    # Final state
    result["finish_reason"] = last_finish_reason
    if last_native_finish_reason is not None:
        result["native_finish_reason"] = last_native_finish_reason

    # Usage from the last chunk that had it
    result["usage"] = aggregated.usage if aggregated.usage else None

    # Debug info from first chunk
    result["debug"] = aggregated.debug_info

    # Streaming marker
    result["streaming"] = True
    result["chunk_count"] = len(chunks)

    return result
