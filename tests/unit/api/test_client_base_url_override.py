"""Tests for OpenRouterClient.chat_completion's per-call base_url override.

Context: one OpenRouterClient instance is shared across all variants within
a run (see src/core/execution_engine.py), but different variants may resolve
to different endpoints (OpenRouter, a local llama.cpp server, the CLI test
suite's HTTP stub) via their BASE_URL config. This is the seam that lets
per-variant BASE_URL reach the actual HTTP request instead of being silently
ignored (previously: the client always used the instance-level default).

Uses the same mocking pattern as
tests/unit/api/test_client.py::TestOpenRouterClientChatCompletion::test_chat_completion_with_options,
which inspects mock_post.call_args rather than asserting on aggregated
response content (a separate, pre-existing, unrelated issue in that file).
"""

import pytest
from unittest.mock import MagicMock, patch

from src.api.client import OpenRouterClient


def _mock_post_response():
    mock_response = MagicMock()
    mock_response.status_code = 200

    sse_chunks = [
        'data: {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], '
        '"usage": {"prompt_tokens": 1, "completion_tokens": 1}}',
        'data: [DONE]',
    ]

    async def mock_aiter_lines():
        for chunk in sse_chunks:
            yield chunk

    mock_response.aiter_lines = mock_aiter_lines
    return mock_response


class TestChatCompletionBaseUrlOverride:
    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_no_override_uses_instance_default(self):
        client = OpenRouterClient(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = _mock_post_response()

            await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
            )

            requested_url = mock_post.call_args.kwargs["url"]
            assert requested_url == "https://openrouter.ai/api/v1/chat/completions"

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_override_wins_over_instance_default(self):
        """A variant-resolved base_url must reach the actual HTTP request,
        not be silently discarded in favor of the client's default."""
        client = OpenRouterClient(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = _mock_post_response()

            await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
                base_url="http://127.0.0.1:8080/v1",
            )

            requested_url = mock_post.call_args.kwargs["url"]
            assert requested_url == "http://127.0.0.1:8080/v1/chat/completions"

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_override_none_falls_back_to_instance_default(self):
        """Explicit base_url=None (the default) must not clobber the
        client's own configured endpoint."""
        client = OpenRouterClient(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = _mock_post_response()

            await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
                base_url=None,
            )

            requested_url = mock_post.call_args.kwargs["url"]
            assert requested_url == "https://openrouter.ai/api/v1/chat/completions"

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_override_without_v1_suffix_gets_v1_appended(self):
        """Mirrors the existing endpoint-normalization rule (client.py's
        'base_url may or may not include /v1 suffix') for the override path."""
        client = OpenRouterClient(api_key="test-key")

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = _mock_post_response()

            await client.chat_completion(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Question?"}],
                base_url="http://127.0.0.1:8080",
            )

            requested_url = mock_post.call_args.kwargs["url"]
            assert requested_url == "http://127.0.0.1:8080/v1/chat/completions"
