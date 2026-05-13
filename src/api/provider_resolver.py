"""Provider resolution for OpenRouter models.

This module provides the ProviderResolver class for selecting which provider
to use for a given OpenRouter model. It queries the OpenRouter API for
available endpoints and applies a strategy to select the best provider.

Key Components:
- ProviderResolution: Structured result of provider resolution
- ProviderResolver: Queries OpenRouter API and selects provider based on strategy

The resolver is synchronous (uses httpx.Client) because it's called from CLI
commands, not from async execution paths.

Example:
    >>> from src.api.provider_resolver import ProviderResolver
    >>>
    >>> resolver = ProviderResolver(api_key="your-api-key")
    >>> result = resolver.resolve(
    ...     model_id="meta-llama/llama-3.3-70b-instruct",
    ...     strategy="cheapest",
    ... )
    >>> print(result.provider_slug)  # e.g., "deepinfra/turbo"
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from logging import Logger
from typing import Any

import httpx

from src.api.errors import NoProviderError
from src.utils.logging_config import get_logger


@dataclass(frozen=True)
class ProviderResolution:
    """Result of provider resolution."""
    provider_slug: str        # The resolved provider tag (e.g., "deepinfra/turbo")
    strategy_applied: str     # The strategy that was actually used (may differ from requested if fallback)
    was_fallback: bool        # True if the requested strategy fell back to "first"
    warning: str | None       # Warning message if fallback occurred, None otherwise


class ProviderResolver:
    """Resolves which provider to use for an OpenRouter model.

    This class queries the OpenRouter API for available endpoints and
    applies a strategy to select the best provider based on criteria
    like cost, speed, or latency.

    Attributes:
        api_key: API key for authentication
        base_url: Base URL for API endpoints

    Example:
        >>> resolver = ProviderResolver(api_key="your-api-key")
        >>> result = resolver.resolve("meta-llama/llama-3.3-70b-instruct", "first")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        logger: Logger | None = None,
    ) -> None:
        """Initialize provider resolver.

        Args:
            api_key: API key for authentication
            base_url: Base URL for API endpoints. Defaults to OpenRouter production.
            logger: Optional logger instance. If not provided, uses get_logger('api.provider_resolver').
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self._logger = logger or get_logger('api.provider_resolver')
        self._client = httpx.Client(timeout=30)

    def resolve(self, model_id: str, strategy: str = "first") -> ProviderResolution:
        """Resolve provider for a model using the specified strategy.

        Args:
            model_id: OpenRouter model identifier (e.g., "meta-llama/llama-3.3-70b-instruct")
            strategy: Provider selection strategy. One of:
                     - "first": Use first available provider (default)
                     - "cheapest": Use provider with lowest pricing
                     - "fastest": Use provider with highest throughput
                     - "lowest-latency": Use provider with lowest latency

        Returns:
            ProviderResolution with resolved provider and metadata

        Raises:
            NoProviderError: No endpoints found for the model
            httpx.HTTPError: HTTP request failures

        Example:
            >>> resolver.resolve("meta-llama/llama-3.3-70b-instruct", "cheapest")
            ProviderResolution(provider_slug='deepinfra/turbo', strategy_applied='cheapest', was_fallback=False, warning=None)
        """
        self._logger.info(
            f"PROVIDER_RESOLUTION_STARTED | model={model_id} | strategy={strategy}"
        )

        try:
            endpoints = self._fetch_endpoints(model_id)
        except httpx.HTTPError as e:
            self._logger.error(
                f"PROVIDER_RESOLUTION_FAILED | model={model_id} | error={str(e)}"
            )
            raise

        if not endpoints:
            error_msg = f"No providers available for model: {model_id}"
            self._logger.error(
                f"PROVIDER_RESOLUTION_FAILED | model={model_id} | reason=no_endpoints"
            )
            raise NoProviderError(error_msg)

        try:
            provider_tag = self._apply_strategy(endpoints, strategy)
            resolution = ProviderResolution(
                provider_slug=provider_tag,
                strategy_applied=strategy,
                was_fallback=False,
                warning=None,
            )
        except ValueError as e:
            # Strategy data unavailable or unknown, fallback to first
            is_unknown = "Unknown strategy" in str(e)
            if is_unknown:
                warning_msg = f"Unknown strategy '{strategy}' — falling back to first provider"
            else:
                warning_msg = f"Strategy '{strategy}' unavailable for this model, falling back to first provider"
            warnings.warn(warning_msg)
            provider_tag = self._select_first(endpoints)
            resolution = ProviderResolution(
                provider_slug=provider_tag,
                strategy_applied="first",
                was_fallback=True,
                warning=warning_msg,
            )

        self._logger.info(
            f"PROVIDER_RESOLUTION_SUCCEEDED | model={model_id} | provider={resolution.provider_slug} | strategy={resolution.strategy_applied} | fallback={resolution.was_fallback}"
        )

        return resolution

    def _fetch_endpoints(self, model_id: str) -> list[dict[str, Any]]:
        """Fetch endpoints from OpenRouter API.

        Args:
            model_id: OpenRouter model identifier

        Returns:
            List of endpoint dictionaries

        Raises:
            httpx.HTTPError: HTTP request failures
        """
        url = f"{self.base_url}/models/{model_id}/endpoints"

        response = self._client.get(
            url=url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()

        data = response.json()
        return data.get("data", {}).get("endpoints", [])

    def _apply_strategy(
        self, endpoints: list[dict[str, Any]], strategy: str
    ) -> str:
        """Apply strategy to select provider from endpoints.

        Args:
            endpoints: List of endpoint dictionaries from API
            strategy: Provider selection strategy

        Returns:
            Selected provider tag

        Raises:
            ValueError: Strategy data unavailable (triggers fallback)
        """
        if strategy == "first":
            return self._select_first(endpoints)
        elif strategy == "cheapest":
            return self._select_cheapest(endpoints)
        elif strategy == "fastest":
            return self._select_fastest(endpoints)
        elif strategy == "lowest-latency":
            return self._select_lowest_latency(endpoints)
        else:
            # Unknown strategy, fallback to first
            raise ValueError(f"Unknown strategy '{strategy}'")

    def _select_first(self, endpoints: list[dict[str, Any]]) -> str:
        """Select the first available provider.

        Args:
            endpoints: List of endpoint dictionaries

        Returns:
            First provider's tag
        """
        return endpoints[0]["tag"]

    def _select_cheapest(self, endpoints: list[dict[str, Any]]) -> str:
        """Select provider with lowest pricing.

        Args:
            endpoints: List of endpoint dictionaries

        Returns:
            Provider tag with lowest pricing.prompt

        Raises:
            ValueError: Pricing data unavailable
        """
        def get_prompt_price(ep: dict[str, Any]) -> float:
            pricing = ep.get("pricing", {})
            prompt_price = pricing.get("prompt")
            if prompt_price is None:
                raise ValueError("Pricing data unavailable")
            return float(prompt_price)

        sorted_endpoints = sorted(endpoints, key=get_prompt_price)
        return sorted_endpoints[0]["tag"]

    def _select_fastest(self, endpoints: list[dict[str, Any]]) -> str:
        """Select provider with highest throughput.

        Args:
            endpoints: List of endpoint dictionaries

        Returns:
            Provider tag with highest throughput_last_30m.p50

        Raises:
            ValueError: Throughput data unavailable
        """
        def get_throughput(ep: dict[str, Any]) -> float:
            throughput = ep.get("throughput_last_30m", {})
            p50 = throughput.get("p50")
            if p50 is None:
                raise ValueError("Throughput data unavailable")
            return float(p50)

        sorted_endpoints = sorted(endpoints, key=get_throughput, reverse=True)
        return sorted_endpoints[0]["tag"]

    def _select_lowest_latency(self, endpoints: list[dict[str, Any]]) -> str:
        """Select provider with lowest latency.

        Args:
            endpoints: List of endpoint dictionaries

        Returns:
            Provider tag with lowest latency_last_30m.p50

        Raises:
            ValueError: Latency data unavailable
        """
        def get_latency(ep: dict[str, Any]) -> float:
            latency = ep.get("latency_last_30m", {})
            p50 = latency.get("p50")
            if p50 is None:
                raise ValueError("Latency data unavailable")
            return float(p50)

        sorted_endpoints = sorted(endpoints, key=get_latency)
        return sorted_endpoints[0]["tag"]

    def close(self) -> None:
        """Close the HTTP client.

        Should be called when the resolver is no longer needed to
        release resources.
        """
        self._client.close()
