"""Pytest configuration for benchmark_llm project."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests",
    )


# =============================================================================
# Mock LLM Response Fixtures (using pytest-httpx)
# =============================================================================

def create_mock_response(
    content: str = "A",
    reasoning_content: str = None,
    model: str = "Qwen",
    finish_reason: str = "stop",
    usage: dict = None,
) -> dict:
    """Create a mock LLM response dictionary.
    
    Args:
        content: The response content (answer letter).
        reasoning_content: Optional reasoning/thinking content.
        model: Model identifier.
        finish_reason: Finish reason from API.
        usage: Token usage dictionary.
    
    Returns:
        Mock response dictionary matching OpenRouter format.
    """
    message = {
        "role": "assistant",
        "content": content,
    }
    
    if reasoning_content:
        message["reasoning_content"] = reasoning_content
    
    if usage is None:
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "total_tokens": 110,
        }
    
    return {
        "id": "chatcmpl-mock-12345",
        "model": model,
        "choices": [
            {
                "finish_reason": finish_reason,
                "index": 0,
                "message": message,
            }
        ],
        "usage": usage,
    }


@pytest.fixture
def mock_chat_completion(httpx_mock):
    """Fixture to mock chat completion API calls.
    
    Usage:
        def test_something(mock_chat_completion):
            mock_chat_completion(content="A", reasoning_content="Thinking...")
            # ... run test code
    """
    def _mock(
        content: str = "A",
        reasoning_content: str = None,
        model: str = "Qwen",
        finish_reason: str = "stop",
        usage: dict = None,
    ):
        response_data = create_mock_response(
            content=content,
            reasoning_content=reasoning_content,
            model=model,
            finish_reason=finish_reason,
            usage=usage,
        )
        
        httpx_mock.add_response(
            url="http://192.168.1.107:8080/v1/chat/completions",
            method="POST",
            json=response_data,
            status_code=200,
        )
        return response_data
    
    return _mock


@pytest.fixture
def mock_chat_completion_error(httpx_mock):
    """Fixture to mock API errors.
    
    Usage:
        def test_error_handling(mock_chat_completion_error):
            mock_chat_completion_error(status_code=500)
            # ... run test code
    """
    def _mock(status_code: int = 500, error_message: str = "API Error"):
        httpx_mock.add_response(
            url="http://192.168.1.107:8080/v1/chat/completions",
            method="POST",
            json={"error": {"message": error_message, "type": "server_error"}},
            status_code=status_code,
        )
    
    return _mock


@pytest.fixture
def mock_models_endpoint(httpx_mock):
    """Fixture to mock models endpoint.

    Usage:
        def test_model_info(mock_models_endpoint):
            mock_models_endpoint()
            # ... run test code
    """
    def _mock():
        httpx_mock.add_response(
            url="http://192.168.1.107:8080/v1/models",
            method="GET",
            json={
                "data": [
                    {
                        "id": "Qwen3.5-35B-A3B.q4km.gguf",
                        "object": "model",
                        "owned_by": "llamacpp",
                        "meta": {
                            "n_params": 34660610688,
                            "size": 21158128128,
                            "n_ctx_train": 262144,
                        },
                    }
                ]
            },
            status_code=200,
        )

    return _mock


# =============================================================================
# Model Variant Test Utilities
# =============================================================================

@pytest.fixture
def default_variant_id() -> str:
    """Default variant_id for tests (unspecified reasoning, no vision, no structured).
    
    Returns:
        Deterministic variant_id for default configuration.
    """
    from src.core.variant_config import VariantConfig
    config = VariantConfig(
        reasoning_mode="unspecified",
        vision_enabled=False,
        structured_enabled=False,
    )
    return config.build_variant_id("test-model")


@pytest.fixture
def variant_configs() -> dict:
    """Pre-built variant configurations for common test scenarios.
    
    Returns:
        Dictionary with variant configurations:
        - auto: Unspecified reasoning (default)
        - off: Reasoning disabled
        - high_effort: High reasoning effort
        - budget_8k: 8000 token reasoning budget
        - vision: Vision enabled
        - structured: Structured outputs enabled
    """
    from src.core.variant_config import VariantConfig
    
    return {
        "auto": VariantConfig(
            reasoning_mode="unspecified",
            vision_enabled=False,
            structured_enabled=False,
        ),
        "off": VariantConfig(
            reasoning_mode="off",
            vision_enabled=False,
            structured_enabled=False,
        ),
        "high_effort": VariantConfig(
            reasoning_mode="effort",
            reasoning_effort="high",
            vision_enabled=False,
            structured_enabled=False,
        ),
        "budget_8k": VariantConfig(
            reasoning_mode="budget",
            reasoning_max_tokens=8000,
            vision_enabled=False,
            structured_enabled=False,
        ),
        "vision": VariantConfig(
            reasoning_mode="unspecified",
            vision_enabled=True,
            structured_enabled=False,
        ),
        "structured": VariantConfig(
            reasoning_mode="unspecified",
            vision_enabled=False,
            structured_enabled=True,
        ),
    }
