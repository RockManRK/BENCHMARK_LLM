"""Response parser for converting aggregated streaming responses to canonical format.

Este módulo é responsável por converter a resposta agregada do streaming
em um objeto canônico CompletionResponse, extraindo os campos relevantes
de forma tolerante e previsível.

Key Design Decisions:
- Parser tolerante: usa .get() para todos os campos, nunca assume estrutura idêntica
- Não depende de formato idêntico entre providers
- Não acessa streaming diretamente (trabalha apenas com AggregatedResponse)
- Não conhece banco de dados ou execução
- Campos ausentes retornam None, nunca levantam exceções

OpenRouter API Reference:
- usage.prompt_tokens: número de tokens de entrada
- usage.completion_tokens: número de tokens de saída
- usage.completion_tokens_details.reasoning_tokens: tokens de raciocínio
- usage.cost: custo da requisição em USD

Example:
    >>> aggregated = AggregatedResponse(
    ...     content="Answer is (B).",
    ...     finish_reason="stop",
    ...     usage={
    ...         "prompt_tokens": 50,
    ...         "completion_tokens": 10,
    ...         "cost": 0.0001,
    ...         "completion_tokens_details": {"reasoning_tokens": 5}
    ...     },
    ...     debug_info=None,
    ...     raw_response=[...]
    ... )
    >>> response = parse_to_completion_response(aggregated, "openai/gpt-4", 500)
    >>> response.input_tokens
    50
    >>> response.response_tokens
    10
    >>> response.reasoning_tokens
    5
    >>> response.cost
    0.0001
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.stream_aggregator import AggregatedResponse


def parse_to_completion_response(
    aggregated: AggregatedResponse,
    model_id: str,
    latency_ms: int,
) -> CompletionResponse:
    """Converte resposta agregada em CompletionResponse canônico.

    Esta função extrai todos os campos relevantes da resposta agregada,
    usando acesso tolerante (`.get()`) para lidar com variações no formato
    da API e campos opcionais.

    Args:
        aggregated: Resposta agregada do stream_aggregator
        model_id: Identificador do modelo que gerou a resposta
        latency_ms: Latência da requisição em milissegundos

    Returns:
        CompletionResponse com todos os campos canônicos preenchidos

    Example:
        >>> aggregated = AggregatedResponse(
        ...     content="Hello",
        ...     finish_reason="stop",
        ...     usage={"prompt_tokens": 10, "completion_tokens": 5},
        ...     debug_info=None,
        ...     raw_response=[]
        ... )
        >>> response = parse_to_completion_response(aggregated, "openai/gpt-4", 100)
        >>> response.content
        "Hello"
        >>> response.input_tokens
        10
        >>> response.response_tokens
        5
    """
    # Import here to avoid circular dependency
    from src.api.client import CompletionResponse

    usage = aggregated.usage or {}

    # Extrair tokens básicos
    input_tokens = usage.get("prompt_tokens", 0) or 0
    response_tokens = usage.get("completion_tokens", 0) or 0

    # Extrair campos opcionais/nested
    cost = usage.get("cost")

    # reasoning_tokens pode estar em completion_tokens_details (nested)
    reasoning_tokens: int | None = None
    completion_tokens_details = usage.get("completion_tokens_details")
    if completion_tokens_details:
        reasoning_tokens = completion_tokens_details.get("reasoning_tokens")
        # Garantir que None seja retornado se for 0 ou ausente
        if reasoning_tokens is not None:
            reasoning_tokens = reasoning_tokens or 0

    return CompletionResponse(
        content=aggregated.content,
        model_id=model_id,
        input_tokens=input_tokens,
        response_tokens=response_tokens,
        reasoning_tokens=reasoning_tokens,
        cost=cost,
        latency_ms=latency_ms,
        raw_response=aggregated.raw_response,
    )
