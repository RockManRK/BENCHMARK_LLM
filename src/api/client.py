"""OpenRouter API client module for benchmark_llm project.

This module provides an async HTTP client for interacting with the OpenRouter API,
supporting both text-only and multimodal (text + image) messages.
"""

import base64
import logging
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class MessageBuilder:
    """Utility class for building API messages.

    This class provides static methods to construct properly formatted
    messages for the OpenRouter chat completion API, supporting both
    text-only and multimodal content.

    Example:
        >>> text_message = MessageBuilder.build_user_message("Hello!")
        >>> image_message = MessageBuilder.build_multimodal_message(
        ...     "What's in this image?",
        ...     Path("image.png")
        ... )
    """

    @staticmethod
    def build_user_message(content: str) -> dict[str, str]:
        """Build a text-only user message.

        Args:
            content: The text content of the message.

        Returns:
            A dictionary with 'role' and 'content' keys formatted for the API.

        Example:
            >>> msg = MessageBuilder.build_user_message("What is 2+2?")
            >>> msg
            {'role': 'user', 'content': 'What is 2+2?'}
        """
        return {"role": "user", "content": content}

    @staticmethod
    def build_multimodal_message(text: str, image_path: Path) -> dict[str, Any]:
        """Build a multimodal user message with text and image.

        Creates a message with both text and image content, encoding
        the image as base64 data URL for API transmission.

        Args:
            text: The text content of the message.
            image_path: Path to the image file to include.

        Returns:
            A dictionary with 'role' and 'content' keys, where content
            is a list containing text and image_url objects.

        Raises:
            FileNotFoundError: If the image file does not exist.
            ValueError: If the image format is not supported.

        Example:
            >>> msg = MessageBuilder.build_multimodal_message(
            ...     "Describe this image",
            ...     Path("chest_xray.png")
            ... )
        """
        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Read and encode image
        image_data = image_path.read_bytes()
        
        # Determine image format
        suffix = image_path.suffix.lower()
        format_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        
        if suffix not in format_map:
            logger.error(f"Invalid image format: {suffix}")
            raise ValueError(f"Invalid image format: {suffix}. Supported: {list(format_map.keys())}")
        
        mime_type = format_map[suffix]
        base64_image = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:{mime_type};base64,{base64_image}"

        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }


class OpenRouterClient:
    """Async HTTP client for OpenRouter API.

    This client handles authentication, request building, and response
    handling for the OpenRouter chat completion API.

    Attributes:
        api_key: The OpenRouter API key for authentication.
        base_url: The base URL for the OpenRouter API.
        _client: Internal httpx AsyncClient instance.

    Example:
        >>> async with OpenRouterClient(api_key="sk-...") as client:
        ...     response = await client.chat_completion(
        ...         model="openai/gpt-4",
        ...         messages=[{"role": "user", "content": "Hello!"}]
        ...     )
    """

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_TIMEOUT = 30.0  # seconds

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the OpenRouterClient.

        Args:
            api_key: The OpenRouter API key for authentication.
            base_url: Optional custom base URL for the API.
            timeout: Request timeout in seconds.

        Example:
            >>> client = OpenRouterClient(api_key="sk-...")
            >>> client = OpenRouterClient(
            ...     api_key="sk-...",
            ...     base_url="https://custom.api.com/v1",
            ...     timeout=60.0
            ... )
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        
        # Initialize httpx client with authentication headers
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self._timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/benchmark_llm",
                "X-Title": "benchmark_llm",
            },
        )
        logger.info(f"OpenRouterClient initialized with base_url={self.base_url}")

    @property
    def _client(self) -> httpx.AsyncClient:
        """Get the internal httpx client."""
        return self.__client

    @_client.setter
    def _client(self, value: httpx.AsyncClient) -> None:
        """Set the internal httpx client."""
        self.__client = value

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 100,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a chat completion request to OpenRouter API.

        Args:
            model: The model identifier (e.g., "openai/gpt-4").
            messages: List of message dictionaries with role and content.
            max_tokens: Maximum tokens to generate in the response.
            temperature: Sampling temperature (0.0 for deterministic).
            **kwargs: Additional parameters to pass to the API.

        Returns:
            The parsed JSON response from the API.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status code.
            httpx.TimeoutException: If the request times out.
            httpx.RequestError: If there's a network error.

        Example:
            >>> response = await client.chat_completion(
            ...     model="openai/gpt-4",
            ...     messages=[{"role": "user", "content": "Hello!"}],
            ...     max_tokens=50
            ... )
            >>> print(response["choices"][0]["message"]["content"])
        """
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        logger.debug(f"Sending chat completion request to {self.base_url}/chat/completions")
        logger.debug(f"Model: {model}, Messages: {len(messages)}")

        try:
            response = await self._client.post(
                "/chat/completions",
                json=payload,
            )
            
            # Handle error responses
            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                error_message = error_data.get("error", {}).get("message", "Unknown API error")
                
                logger.error(f"API error: {response.status_code} - {error_message}")
                
                if response.status_code == 401:
                    raise httpx.HTTPStatusError("Authentication failed: Invalid API key", request=response.request, response=response)
                elif response.status_code == 429:
                    raise httpx.HTTPStatusError("Rate limit exceeded", request=response.request, response=response)
                else:
                    raise httpx.HTTPStatusError(f"API error: {error_message}", request=response.request, response=response)

            response_data = response.json()
            logger.debug(f"Received response: id={response_data.get('id')}")
            return response_data

        except httpx.TimeoutException:
            logger.error("Request timed out")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise

    async def get_model_info(self, model_id: str) -> dict[str, Any]:
        """Get model information from the API.
        
        Queries the /v1/models endpoint to get detailed model information
        including architecture, context length, and other metadata.
        
        Args:
            model_id: The model identifier to query.
            
        Returns:
            Dictionary with model information:
            - id: Exact model ID from API
            - object: Type of object
            - created: Timestamp
            - owned_by: Provider name
            - meta: Metadata (n_params, size, n_ctx_train, etc.)
            - context_length: Context window size (if available)
            - max_completion_tokens: Max output tokens (if available)
            
        Example:
            >>> info = await client.get_model_info('Qwen')
            >>> print(info['meta']['n_params'])
            34660610688
        """
        try:
            # Get list of all models
            response = await self._client.get("/models")
            response.raise_for_status()
            data = response.json()
            
            # Search for matching model
            models_list = data.get("data", data.get("models", []))
            
            for model in models_list:
                model_id_field = model.get("id", model.get("model", ""))
                
                # Match by exact ID or by name contains
                if model_id_field == model_id or model_id in model_id_field:
                    # Build enriched model info
                    model_info = {
                        "id": model_id_field,
                        "object": model.get("object", "model"),
                        "created": model.get("created"),
                        "owned_by": model.get("owned_by", "unknown"),
                        "meta": model.get("meta", {}),
                        "context_length": model.get("context_length"),
                        "max_completion_tokens": model.get("max_completion_tokens"),
                    }
                    
                    logger.info(f"Found model info for {model_id}: {model_info['id']}")
                    return model_info
            
            # Model not found in list
            logger.warning(f"Model {model_id} not found in /v1/models list")
            return {"id": model_id, "object": "model"}
            
        except Exception as e:
            logger.error(f"Error fetching model info for {model_id}: {e}")
            # Fallback to provided ID
            return {"id": model_id, "object": "model"}

    async def close(self) -> None:
        """Close the HTTP client and release resources.

        This should be called when the client is no longer needed
        to properly close connections.

        Example:
            >>> await client.close()
        """
        await self._client.aclose()
        logger.info("OpenRouterClient closed")

    async def __aenter__(self) -> "OpenRouterClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
