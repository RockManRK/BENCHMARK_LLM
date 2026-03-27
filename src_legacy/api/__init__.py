"""API module for OpenRouter integration.

This module provides components for interacting with the OpenRouter API:
- OpenRouterClient: Async HTTP client for API calls
- MessageBuilder: Utility for building text and multimodal messages
- RetryHandler: Retry logic with exponential backoff
- ResponseParser: Parse API responses and extract answers
- ModelCapabilityChecker: Check model capabilities (vision support)
"""

from src.api.client import MessageBuilder, OpenRouterClient
from src.api.model_capabilities import ModelCapabilities, ModelCapabilityChecker, VisionSupport
from src.api.parser import ParseError, ParsedResponse, ResponseParser
from src.api.retry import RetryConfig, RetryError, RetryHandler

__all__ = [
    # Client
    "OpenRouterClient",
    "MessageBuilder",
    # Retry
    "RetryConfig",
    "RetryHandler",
    "RetryError",
    # Parser
    "ResponseParser",
    "ParsedResponse",
    "ParseError",
    # Model Capabilities
    "ModelCapabilityChecker",
    "ModelCapabilities",
    "VisionSupport",
]
