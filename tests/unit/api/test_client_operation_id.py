"""Tests for operation_id threading and structured event emission in
OpenRouterClient.chat_completion (Checkpoint C)."""

from unittest.mock import MagicMock, patch

import pytest

from src.api.client import OpenRouterClient
from src.api.request_payload import build_chat_completion_payload
from src.utils.log_events import Event


def _mock_post_response():
    mock_response = MagicMock()
    mock_response.status_code = 200

    sse_chunks = [
        'data: {"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}], '
        '"usage": {"prompt_tokens": 1, "completion_tokens": 1}}',
        "data: [DONE]",
    ]

    async def mock_aiter_lines():
        for chunk in sse_chunks:
            yield chunk

    mock_response.aiter_lines = mock_aiter_lines
    return mock_response


class TestOperationIdInEvents:
    @pytest.mark.asyncio
    async def test_operation_id_appears_in_api_request_and_response_events(self):
        client = OpenRouterClient(api_key="test-key")
        payload = build_chat_completion_payload(model_id="openai/gpt-4", messages=[{"role": "user", "content": "hi"}])

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = _mock_post_response()
            with patch("src.api.client.emit_event") as spy:
                await client.chat_completion(payload=payload, operation_id="op_abc123")

        event_names = [call.args[1] for call in spy.call_args_list]
        assert Event.API_REQUEST in event_names
        assert Event.API_RESPONSE in event_names
        for call in spy.call_args_list:
            assert call.kwargs.get("operation_id") == "op_abc123"

    @pytest.mark.asyncio
    async def test_operation_id_none_when_not_provided(self):
        client = OpenRouterClient(api_key="test-key")
        payload = build_chat_completion_payload(model_id="openai/gpt-4", messages=[{"role": "user", "content": "hi"}])

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = _mock_post_response()
            with patch("src.api.client.emit_event") as spy:
                await client.chat_completion(payload=payload)

        for call in spy.call_args_list:
            assert call.kwargs.get("operation_id") is None

    @pytest.mark.asyncio
    async def test_debug_enabled_event_present_when_debug_in_payload(self):
        client = OpenRouterClient(api_key="test-key")
        payload = build_chat_completion_payload(
            model_id="openai/gpt-4", messages=[{"role": "user", "content": "hi"}], debug_enabled=True,
        )

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = _mock_post_response()
            with patch("src.api.client.emit_event") as spy:
                await client.chat_completion(payload=payload)

        event_names = [call.args[1] for call in spy.call_args_list]
        assert Event.DEBUG_ENABLED in event_names
        assert Event.DEBUG_DISABLED not in event_names

    @pytest.mark.asyncio
    async def test_debug_disabled_event_present_when_debug_absent(self):
        client = OpenRouterClient(api_key="test-key")
        payload = build_chat_completion_payload(model_id="openai/gpt-4", messages=[{"role": "user", "content": "hi"}])

        with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = _mock_post_response()
            with patch("src.api.client.emit_event") as spy:
                await client.chat_completion(payload=payload)

        event_names = [call.args[1] for call in spy.call_args_list]
        assert Event.DEBUG_DISABLED in event_names
        assert Event.DEBUG_ENABLED not in event_names
