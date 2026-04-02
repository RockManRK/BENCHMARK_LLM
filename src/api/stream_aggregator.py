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
