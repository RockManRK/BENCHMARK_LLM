"""Unit tests for provider resolver.

Tests the ProviderResolver class for selecting OpenRouter providers.

The provider resolver's responsibility is to:
1. Query the OpenRouter API for available endpoints
2. Apply a strategy to select the best provider
3. Return the provider tag for use in API requests

Provider Resolution Strategies:
- "first": Use the first available provider
- "cheapest": Use provider with lowest pricing.prompt
- "fastest": Use provider with highest throughput_last_30m.p50
- "lowest-latency": Use provider with lowest latency_last_30m.p50

Important constraints:
- Status 0 is considered active (based on actual API responses)
- The resolver is synchronous (httpx.Client, not AsyncClient)
- HTTP errors are raised as-is (no translation)
- Empty endpoints raise NoProviderError
- Strategy data unavailability triggers fallback to "first" with warning
"""

import pytest
from unittest.mock import MagicMock, patch
import warnings

from src.api.provider_resolver import ProviderResolver, ProviderResolution
from src.api.errors import NoProviderError


@pytest.fixture
def mock_response_data():
    """Sample API response data with multiple providers."""
    return {
        "data": {
            "id": "meta-llama/llama-3.3-70b-instruct",
            "endpoints": [
                {
                    "name": "DeepInfra | meta-llama/llama-3.3-70b-instruct",
                    "model_id": "meta-llama/llama-3.3-70b-instruct",
                    "tag": "deepinfra/turbo",
                    "provider_name": "DeepInfra",
                    "pricing": {"prompt": "0.0000001", "completion": "0.00000032", "discount": 0},
                    "status": 0,
                    "latency_last_30m": {"p50": 227, "p75": 403.75, "p90": 924.5},
                    "throughput_last_30m": {"p50": 25, "p75": 30, "p90": 35}
                },
                {
                    "name": "Together | meta-llama/llama-3.3-70b-instruct",
                    "model_id": "meta-llama/llama-3.3-70b-instruct",
                    "tag": "togethercomputer/llama-3.3-70b",
                    "provider_name": "Together",
                    "pricing": {"prompt": "0.00000008", "completion": "0.00000028", "discount": 0},
                    "status": 0,
                    "latency_last_30m": {"p50": 150, "p75": 300, "p90": 800},
                    "throughput_last_30m": {"p50": 35, "p75": 40, "p90": 45}
                },
                {
                    "name": "Anyscale | meta-llama/llama-3.3-70b-instruct",
                    "model_id": "meta-llama/llama-3.3-70b-instruct",
                    "tag": "anyscale/llama-3.3-70b",
                    "provider_name": "Anyscale",
                    "pricing": {"prompt": "0.00000015", "completion": "0.0000004", "discount": 0},
                    "status": 0,
                    "latency_last_30m": {"p50": 300, "p75": 500, "p90": 1000},
                    "throughput_last_30m": {"p50": 20, "p75": 25, "p90": 30}
                }
            ]
        }
    }


@pytest.fixture
def resolver():
    """Create a ProviderResolver instance with mocked HTTP client."""
    with patch('src.api.provider_resolver.httpx.Client') as mock_client:
        resolver = ProviderResolver(api_key="test-api-key")
        yield resolver
        resolver.close()


class TestProviderResolverFirstStrategy:
    """Test cases for 'first' strategy."""

    @pytest.mark.domain_rule
    def test_first_strategy_returns_first_endpoint(self, resolver, mock_response_data):
        """When strategy='first', returns first endpoint's tag."""
        # Arrange
        with patch.object(resolver, '_fetch_endpoints', return_value=mock_response_data["data"]["endpoints"]):
            # Act
            result = resolver.resolve(
                model_id="meta-llama/llama-3.3-70b-instruct",
                strategy="first"
            )

            # Assert
            assert result.provider_slug == "deepinfra/turbo"
            assert result.was_fallback is False
            assert result.strategy_applied == "first"
            assert result.warning is None

    @pytest.mark.domain_rule
    def test_first_strategy_is_default(self, resolver, mock_response_data):
        """When strategy is not specified, defaults to 'first'."""
        # Arrange
        with patch.object(resolver, '_fetch_endpoints', return_value=mock_response_data["data"]["endpoints"]):
            # Act
            result = resolver.resolve(model_id="meta-llama/llama-3.3-70b-instruct")

            # Assert
            assert result.provider_slug == "deepinfra/turbo"
            assert result.was_fallback is False
            assert result.strategy_applied == "first"


class TestProviderResolverCheapestStrategy:
    """Test cases for 'cheapest' strategy."""

    @pytest.mark.domain_rule
    def test_cheapest_strategy_returns_lowest_pricing(self, resolver, mock_response_data):
        """When strategy='cheapest', returns endpoint with lowest pricing.prompt."""
        # Arrange
        with patch.object(resolver, '_fetch_endpoints', return_value=mock_response_data["data"]["endpoints"]):
            # Act
            result = resolver.resolve(
                model_id="meta-llama/llama-3.3-70b-instruct",
                strategy="cheapest"
            )

            # Assert
            # Together has lowest pricing: 0.00000008
            assert result.provider_slug == "togethercomputer/llama-3.3-70b"
            assert result.was_fallback is False
            assert result.strategy_applied == "cheapest"

    @pytest.mark.domain_rule
    def test_cheapest_strategy_fallback_on_missing_pricing(self, resolver, mock_response_data):
        """When pricing data is None, falls back to first with warning."""
        # Arrange
        endpoints = mock_response_data["data"]["endpoints"]
        # Remove pricing from first endpoint
        endpoints[0]["pricing"] = {}

        with patch.object(resolver, '_fetch_endpoints', return_value=endpoints):
            # Act
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = resolver.resolve(
                    model_id="meta-llama/llama-3.3-70b-instruct",
                    strategy="cheapest"
                )

                # Assert
                assert len(w) == 1
                assert "falling back to first" in str(w[0].message).lower()
                assert result.provider_slug == "deepinfra/turbo"
                assert result.was_fallback is True
                assert result.strategy_applied == "first"
                assert result.warning is not None


class TestProviderResolverFastestStrategy:
    """Test cases for 'fastest' strategy."""

    @pytest.mark.domain_rule
    def test_fastest_strategy_returns_highest_throughput(self, resolver, mock_response_data):
        """When strategy='fastest', returns endpoint with highest throughput."""
        # Arrange
        with patch.object(resolver, '_fetch_endpoints', return_value=mock_response_data["data"]["endpoints"]):
            # Act
            result = resolver.resolve(
                model_id="meta-llama/llama-3.3-70b-instruct",
                strategy="fastest"
            )

            # Assert
            # Together has highest throughput: 35
            assert result.provider_slug == "togethercomputer/llama-3.3-70b"
            assert result.was_fallback is False
            assert result.strategy_applied == "fastest"

    @pytest.mark.domain_rule
    def test_fastest_strategy_fallback_on_missing_throughput(self, resolver, mock_response_data):
        """When throughput data is None, falls back to first with warning."""
        # Arrange
        endpoints = mock_response_data["data"]["endpoints"]
        # Remove throughput from all endpoints
        for ep in endpoints:
            ep["throughput_last_30m"] = {}

        with patch.object(resolver, '_fetch_endpoints', return_value=endpoints):
            # Act
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = resolver.resolve(
                    model_id="meta-llama/llama-3.3-70b-instruct",
                    strategy="fastest"
                )

                # Assert
                assert len(w) == 1
                assert "falling back to first" in str(w[0].message).lower()
                assert result.provider_slug == "deepinfra/turbo"
                assert result.was_fallback is True
                assert result.strategy_applied == "first"


class TestProviderResolverLowestLatencyStrategy:
    """Test cases for 'lowest-latency' strategy."""

    @pytest.mark.domain_rule
    def test_lowest_latency_strategy_returns_lowest_latency(self, resolver, mock_response_data):
        """When strategy='lowest-latency', returns endpoint with lowest latency."""
        # Arrange
        with patch.object(resolver, '_fetch_endpoints', return_value=mock_response_data["data"]["endpoints"]):
            # Act
            result = resolver.resolve(
                model_id="meta-llama/llama-3.3-70b-instruct",
                strategy="lowest-latency"
            )

            # Assert
            # Together has lowest latency: 150
            assert result.provider_slug == "togethercomputer/llama-3.3-70b"
            assert result.was_fallback is False
            assert result.strategy_applied == "lowest-latency"

    @pytest.mark.domain_rule
    def test_lowest_latency_strategy_fallback_on_missing_latency(self, resolver, mock_response_data):
        """When latency data is None, falls back to first with warning."""
        # Arrange
        endpoints = mock_response_data["data"]["endpoints"]
        # Remove latency from all endpoints
        for ep in endpoints:
            ep["latency_last_30m"] = {}

        with patch.object(resolver, '_fetch_endpoints', return_value=endpoints):
            # Act
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = resolver.resolve(
                    model_id="meta-llama/llama-3.3-70b-instruct",
                    strategy="lowest-latency"
                )

                # Assert
                assert len(w) == 1
                assert "falling back to first" in str(w[0].message).lower()
                assert result.provider_slug == "deepinfra/turbo"
                assert result.was_fallback is True
                assert result.strategy_applied == "first"


class TestProviderResolverNoProviderError:
    """Test cases for NoProviderError scenarios."""

    @pytest.mark.domain_rule
    def test_empty_endpoints_raises_no_provider_error(self, resolver):
        """When endpoints list is empty, raises NoProviderError."""
        # Arrange
        with patch.object(resolver, '_fetch_endpoints', return_value=[]):
            # Act & Assert
            with pytest.raises(NoProviderError) as exc_info:
                resolver.resolve(model_id="meta-llama/llama-3.3-70b-instruct")

            assert "No providers available" in str(exc_info.value)
            assert exc_info.value.error_type == "no_provider"

    @pytest.mark.domain_rule
    def test_no_provider_error_includes_model_id(self, resolver):
        """NoProviderError message includes the model ID."""
        # Arrange
        model_id = "meta-llama/llama-3.3-70b-instruct"
        with patch.object(resolver, '_fetch_endpoints', return_value=[]):
            # Act & Assert
            with pytest.raises(NoProviderError) as exc_info:
                resolver.resolve(model_id=model_id)

            assert model_id in str(exc_info.value)


class TestProviderResolverHTTPErrorHandling:
    """Test cases for HTTP error handling."""

    @pytest.mark.domain_rule
    def test_http_error_is_raised(self, resolver):
        """When HTTP request fails, raises the HTTP error."""
        # Arrange
        import httpx
        with patch.object(resolver, '_fetch_endpoints') as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=MagicMock(status_code=400)
            )

            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError):
                resolver.resolve(model_id="meta-llama/llama-3.3-70b-instruct")

    @pytest.mark.domain_rule
    def test_timeout_error_is_raised(self, resolver):
        """When request times out, raises TimeoutError."""
        # Arrange
        import httpx
        with patch.object(resolver, '_fetch_endpoints') as mock_fetch:
            mock_fetch.side_effect = httpx.TimeoutException("Request timed out")

            # Act & Assert
            with pytest.raises(httpx.TimeoutException):
                resolver.resolve(model_id="meta-llama/llama-3.3-70b-instruct")


class TestProviderResolverFetchEndpoints:
    """Test cases for _fetch_endpoints method."""

    @pytest.mark.domain_rule
    def test_fetch_endpoints_makes_correct_request(self, resolver, mock_response_data):
        """_fetch_endpoints makes GET request to correct URL."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(resolver._client, 'get', return_value=mock_response) as mock_get:
            # Act
            result = resolver._fetch_endpoints("meta-llama/llama-3.3-70b-instruct")

            # Assert
            mock_get.assert_called_once_with(
                url="https://openrouter.ai/api/v1/models/meta-llama/llama-3.3-70b-instruct/endpoints",
                headers={
                    "Authorization": "Bearer test-api-key",
                    "Content-Type": "application/json",
                }
            )
            assert result == mock_response_data["data"]["endpoints"]

    @pytest.mark.domain_rule
    def test_fetch_endpoints_raises_on_http_error(self, resolver):
        """_fetch_endpoints raises HTTP error on failure."""
        # Arrange
        import httpx
        with patch.object(resolver._client, 'get') as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404)
            )

            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                resolver._fetch_endpoints("invalid-model-id")

            assert exc_info.value.response.status_code == 404


class TestProviderResolverUnknownStrategy:
    """Test cases for unknown strategy handling."""

    @pytest.mark.domain_rule
    def test_unknown_strategy_fallback_to_first(self, resolver, mock_response_data):
        """When strategy is unknown, falls back to first with warning."""
        # Arrange
        with patch.object(resolver, '_fetch_endpoints', return_value=mock_response_data["data"]["endpoints"]):
            # Act
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = resolver.resolve(
                    model_id="meta-llama/llama-3.3-70b-instruct",
                    strategy="unknown-strategy"
                )

                # Assert
                assert len(w) == 1
                assert "Unknown strategy" in str(w[0].message)
                assert result.provider_slug == "deepinfra/turbo"
                assert result.was_fallback is True
                assert result.strategy_applied == "first"
                assert result.warning is not None


class TestProviderResolverLogging:
    """Test cases for logging behavior."""

    @pytest.mark.domain_rule
    def test_resolution_started_logged(self, resolver, mock_response_data):
        """PROVIDER_RESOLUTION_STARTED is logged."""
        # Arrange
        import logging
        mock_logger = MagicMock(spec=logging.Logger)
        resolver._logger = mock_logger

        with patch.object(resolver, '_fetch_endpoints', return_value=mock_response_data["data"]["endpoints"]):
            # Act
            resolver.resolve(
                model_id="meta-llama/llama-3.3-70b-instruct",
                strategy="first"
            )

            # Assert
            mock_logger.info.assert_any_call(
                "PROVIDER_RESOLUTION_STARTED | model=meta-llama/llama-3.3-70b-instruct | strategy=first"
            )

    @pytest.mark.domain_rule
    def test_resolution_succeeded_logged(self, resolver, mock_response_data):
        """PROVIDER_RESOLUTION_SUCCEEDED is logged."""
        # Arrange
        import logging
        mock_logger = MagicMock(spec=logging.Logger)
        resolver._logger = mock_logger

        with patch.object(resolver, '_fetch_endpoints', return_value=mock_response_data["data"]["endpoints"]):
            # Act
            resolver.resolve(
                model_id="meta-llama/llama-3.3-70b-instruct",
                strategy="first"
            )

            # Assert
            mock_logger.info.assert_any_call(
                "PROVIDER_RESOLUTION_SUCCEEDED | model=meta-llama/llama-3.3-70b-instruct | provider=deepinfra/turbo | strategy=first | fallback=False"
            )

    @pytest.mark.domain_rule
    def test_resolution_failed_logged(self, resolver):
        """PROVIDER_RESOLUTION_FAILED is logged on error."""
        # Arrange
        import logging
        mock_logger = MagicMock(spec=logging.Logger)
        resolver._logger = mock_logger

        with patch.object(resolver, '_fetch_endpoints', return_value=[]):
            # Act & Assert
            with pytest.raises(NoProviderError):
                resolver.resolve(model_id="meta-llama/llama-3.3-70b-instruct")

            mock_logger.error.assert_called_with(
                "PROVIDER_RESOLUTION_FAILED | model=meta-llama/llama-3.3-70b-instruct | reason=no_endpoints"
            )


class TestProviderResolverClose:
    """Test cases for resource cleanup."""

    @pytest.mark.domain_rule
    def test_close_closes_http_client(self, resolver):
        """close() closes the HTTP client."""
        # Arrange
        with patch.object(resolver._client, 'close') as mock_close:
            # Act
            resolver.close()

            # Assert
            mock_close.assert_called_once()


class TestProviderResolutionDataclass:
    """Test cases for ProviderResolution structured return type."""

    @pytest.mark.domain_rule
    def test_successful_resolution_fields(self):
        """ProviderResolution has correct fields for successful resolution."""
        # Arrange & Act
        result = ProviderResolution(
            provider_slug="deepinfra/turbo",
            strategy_applied="cheapest",
            was_fallback=False,
            warning=None,
        )

        # Assert
        assert result.provider_slug == "deepinfra/turbo"
        assert result.strategy_applied == "cheapest"
        assert result.was_fallback is False
        assert result.warning is None

    @pytest.mark.domain_rule
    def test_fallback_result_fields(self):
        """ProviderResolution has correct fields for fallback resolution."""
        # Arrange & Act
        result = ProviderResolution(
            provider_slug="deepinfra/turbo",
            strategy_applied="first",
            was_fallback=True,
            warning="Strategy 'cheapest' unavailable for this model, falling back to first provider",
        )

        # Assert
        assert result.provider_slug == "deepinfra/turbo"
        assert result.strategy_applied == "first"
        assert result.was_fallback is True
        assert "cheapest" in result.warning
        assert "falling back to first" in result.warning

    @pytest.mark.domain_rule
    def test_dataclass_is_frozen(self):
        """ProviderResolution is frozen — fields cannot be modified."""
        # Arrange
        from dataclasses import FrozenInstanceError

        result = ProviderResolution(
            provider_slug="deepinfra/turbo",
            strategy_applied="first",
            was_fallback=False,
            warning=None,
        )

        # Act & Assert
        with pytest.raises(FrozenInstanceError):
            result.provider_slug = "other/provider"
