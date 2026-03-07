"""Basic mock tests for benchmark_llm.

These tests verify that the system works with mocked API responses,
without requiring a real API server.
"""

import pytest
from src.api.client import OpenRouterClient
from src.utils.config import get_settings


class TestMockBasic:
    """Test basic mock functionality."""
    
    def test_mock_chat_completion(self, mock_chat_completion):
        """Test that mock chat completion works."""
        # Setup mock
        mock_chat_completion(content="A", reasoning_content="This is the reasoning...")
        
        # Create client
        settings = get_settings()
        client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        
        # Make request (will be intercepted by mock)
        import asyncio
        
        async def call_api():
            return await client.chat_completion(
                model='Qwen',
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10,
            )
        
        response = asyncio.run(call_api())
        
        # Verify response
        assert response["choices"][0]["message"]["content"] == "A"
        assert response["choices"][0]["message"]["reasoning_content"] == "This is the reasoning..."
        assert response["model"] == "Qwen"
    
    def test_mock_error_response(self, mock_chat_completion_error):
        """Test that mock error responses work."""
        # Setup mock error
        mock_chat_completion_error(status_code=500, error_message="Server Error")
        
        # Create client
        settings = get_settings()
        client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        
        # Make request (will return error)
        import asyncio
        import httpx
        
        async def call_api():
            try:
                return await client.chat_completion(
                    model='Qwen',
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=10,
                )
            except httpx.HTTPStatusError as e:
                return e
        
        result = asyncio.run(call_api())
        
        # Verify error
        assert isinstance(result, httpx.HTTPStatusError)
        assert result.response.status_code == 500
    
    def test_mock_models_endpoint(self, mock_models_endpoint):
        """Test that mock models endpoint works."""
        # Setup mock
        mock_models_endpoint()
        
        # Create client
        settings = get_settings()
        client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        
        # Make request
        import asyncio
        import httpx
        
        async def call_api():
            return await client.get_model_info('Qwen')
        
        result = asyncio.run(call_api())
        
        # Verify response
        assert result["id"] == "Qwen3.5-35B-A3B.q4km.gguf"
        assert result["owned_by"] == "llamacpp"
        assert result["meta"]["n_params"] == 34660610688
