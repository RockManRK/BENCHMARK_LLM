"""Tests for src.utils.redaction — the central redaction policy
(Checkpoint C). Covers: secret-shaped keys (flat and nested), headers,
URLs, exception strings, payloads, upstream echo shapes, response
metadata. Also asserts the original object is never mutated.
"""

import copy

import pytest

from src.utils.redaction import redact, REDACTED


class TestFlatStringSecrets:
    def test_bearer_token_in_string_redacted(self):
        result = redact("Authorization header: Bearer sk-abc123XYZ")
        assert "sk-abc123XYZ" not in result
        assert REDACTED in result

    def test_url_credentials_redacted(self):
        result = redact("connecting to https://user:hunter2@db.example.com/mydb")
        assert "hunter2" not in result
        assert "user" not in result
        assert REDACTED in result

    def test_inline_kv_secret_redacted(self):
        result = redact("request failed: api_key=sk-live-abcdef1234 was rejected")
        assert "sk-live-abcdef1234" not in result

    def test_plain_string_untouched(self):
        assert redact("hello world") == "hello world"


class TestDictKeys:
    def test_top_level_secret_key_redacted(self):
        result = redact({"api_key": "sk-abc123", "model": "openai/gpt-4"})
        assert result["api_key"] == REDACTED
        assert result["model"] == "openai/gpt-4"

    def test_case_insensitive_key_match(self):
        result = redact({"API_KEY": "sk-abc123", "Authorization": "Bearer xyz"})
        assert result["API_KEY"] == REDACTED
        assert result["Authorization"] == REDACTED

    def test_nested_dict_secret_redacted(self):
        obj = {
            "headers": {"Authorization": "Bearer sk-abc123", "Content-Type": "application/json"},
            "payload": {"model": "openai/gpt-4"},
        }
        result = redact(obj)
        assert result["headers"]["Authorization"] == REDACTED
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["payload"]["model"] == "openai/gpt-4"

    def test_deeply_nested_secret_redacted(self):
        obj = {"a": {"b": {"c": {"api_key": "secretvalue"}}}}
        result = redact(obj)
        assert result["a"]["b"]["c"]["api_key"] == REDACTED

    def test_various_secret_key_names(self):
        obj = {
            "cookie": "sessionid=abc",
            "set-cookie": "sessionid=abc",
            "token": "tok_123",
            "secret": "shh",
            "password": "hunter2",
            "x-api-key": "sk-abc",
            "client_secret": "cs_abc",
        }
        result = redact(obj)
        assert all(v == REDACTED for v in result.values())

    def test_non_secret_keys_untouched(self):
        obj = {"model": "openai/gpt-4", "temperature": 0.7, "seed": 42}
        result = redact(obj)
        assert result == obj


class TestListsAndTuples:
    def test_list_of_dicts_redacted(self):
        obj = [{"api_key": "sk-1"}, {"api_key": "sk-2"}]
        result = redact(obj)
        assert result[0]["api_key"] == REDACTED
        assert result[1]["api_key"] == REDACTED

    def test_tuple_preserved_as_tuple(self):
        obj = ("safe", {"token": "tok_abc"})
        result = redact(obj)
        assert isinstance(result, tuple)
        assert result[1]["token"] == REDACTED


class TestPayloadAndUpstreamEchoShapes:
    def test_real_request_payload_shape(self):
        payload = {
            "model": "openai/gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
            "seed": 42,
        }
        result = redact(payload)
        assert result == payload  # nothing secret-shaped in here

    def test_upstream_echo_with_safety_settings_shape(self):
        echo = {
            "generationConfig": {"seed": 42, "temperature": 0},
            "systemInstruction": {"role": "system", "parts": [{"text": "hi"}]},
        }
        result = redact(echo)
        assert result == echo  # unchanged, nothing secret-shaped

    def test_response_metadata_with_incidental_secret_leak(self):
        """Even if some future response metadata field happened to be
        named like a secret, it must still be redacted — the policy
        doesn't distinguish request-side from response-side data."""
        metadata = {"id": "gen-123", "provider": "Google AI Studio", "token": "leaked-value"}
        result = redact(metadata)
        assert result["token"] == REDACTED
        assert result["id"] == "gen-123"


class TestExceptionMessages:
    def test_exception_str_redacted(self):
        try:
            raise ConnectionError("failed with Authorization: Bearer sk-abc123XYZ")
        except ConnectionError as e:
            result = redact(str(e))
            assert "sk-abc123XYZ" not in result

    def test_exception_with_url_credentials_redacted(self):
        try:
            raise OSError("could not connect to https://admin:s3cr3t@internal.host/api")
        except OSError as e:
            result = redact(str(e))
            assert "s3cr3t" not in result
            assert "admin" not in result


class TestNoMutation:
    def test_original_dict_not_mutated(self):
        original = {"api_key": "sk-abc123", "model": "gpt-4"}
        snapshot = copy.deepcopy(original)
        redact(original)
        assert original == snapshot

    def test_original_nested_dict_not_mutated(self):
        original = {"headers": {"Authorization": "Bearer sk-abc"}}
        snapshot = copy.deepcopy(original)
        redact(original)
        assert original == snapshot

    def test_original_list_not_mutated(self):
        original = [{"token": "tok_abc"}]
        snapshot = copy.deepcopy(original)
        redact(original)
        assert original == snapshot


class TestNonStringScalarsPassThrough:
    @pytest.mark.parametrize("value", [42, 0, 3.14, True, False, None])
    def test_scalar_passthrough(self, value):
        assert redact(value) is value or redact(value) == value
