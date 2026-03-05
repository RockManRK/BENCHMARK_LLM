"""Model capabilities module for OpenRouter API client.

This module provides functionality to check model capabilities,
particularly vision/image support, with caching for performance.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class VisionSupport(str, Enum):
    """Enum for vision support status."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass
class ModelCapabilities:
    """Capabilities information for a model.

    Attributes:
        model_id: The model identifier (e.g., "openai/gpt-4-vision").
        supports_vision: Whether the model supports image inputs.
        max_image_size_mb: Maximum image size in megabytes.
        supported_image_formats: List of supported image formats.

    Example:
        >>> capabilities = ModelCapabilities(
        ...     model_id="openai/gpt-4-vision",
        ...     supports_vision=True,
        ...     max_image_size_mb=20,
        ... )
    """

    model_id: str
    supports_vision: bool = False
    max_image_size_mb: int = 0
    supported_image_formats: list[str] = field(default_factory=list)


class ModelCapabilityChecker:
    """Checker for model capabilities with caching.

    This class provides methods to check if a model supports specific
    capabilities, particularly vision/image support. Results are cached
    for performance.

    Attributes:
        _cache: Internal cache of model capabilities.

    Example:
        >>> checker = ModelCapabilityChecker()
        >>> result = checker.check_vision_support("openai/gpt-4-vision")
        >>> print(result)
        VisionSupport.SUPPORTED
    """

    # Known vision-capable models
    VISION_MODELS = {
        # OpenAI
        "openai/gpt-4-vision",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "openai/gpt-4-turbo",
        "openai/gpt-4-turbo-preview",
        "openai/o1",
        "openai/o1-mini",
        "openai/o3-mini",
        
        # Anthropic Claude 3 family (all support vision)
        "anthropic/claude-3-opus",
        "anthropic/claude-3-opus:beta",
        "anthropic/claude-3-sonnet",
        "anthropic/claude-3-sonnet:beta",
        "anthropic/claude-3-haiku",
        "anthropic/claude-3-haiku:beta",
        "anthropic/claude-3-5-sonnet",
        "anthropic/claude-3-5-haiku",
        
        # Google Gemini
        "google/gemini-pro-vision",
        "google/gemini-1.5-pro",
        "google/gemini-1.5-flash",
        "google/gemini-2.0-flash",
        
        # Meta Llama 3.2 (vision variants)
        "meta-llama/llama-3.2-90b-vision-instruct",
        "meta-llama/llama-3.2-11b-vision-instruct",
    }

    # Known text-only models
    TEXT_ONLY_MODELS = {
        # OpenAI GPT-3.5
        "openai/gpt-3.5-turbo",
        "openai/gpt-3.5-turbo-16k",
        "openai/gpt-3.5-turbo-instruct",
        
        # OpenAI GPT-4 (non-vision)
        "openai/gpt-4",
        "openai/gpt-4-32k",
        "openai/gpt-4-base",
        
        # OpenAI o1 (base - may not support vision in all contexts)
        "openai/o1-preview",
        
        # Anthropic Claude 2 and earlier
        "anthropic/claude-2",
        "anthropic/claude-2.0",
        "anthropic/claude-2.1",
        "anthropic/claude-instant",
        "anthropic/claude-instant-1",
        
        # Meta Llama (non-vision)
        "meta-llama/llama-2-7b",
        "meta-llama/llama-2-13b",
        "meta-llama/llama-2-70b",
        "meta/llama-2-70b",  # Alternative naming
        "meta-llama/llama-3-8b",
        "meta-llama/llama-3-70b",
        "meta-llama/llama-3.1-8b",
        "meta-llama/llama-3.1-70b",
        "meta-llama/llama-3.1-405b",
        
        # Mistral
        "mistral/mistral-7b",
        "mistral/mistral-7b-instruct",
        "mistral/mixtral-8x7b",
        "mistral/mixtral-8x7b-instruct",
        "mistral/mistral-large",
        "mistral/mistral-medium",
        "mistral/mistral-small",
        
        # Other providers
        "cohere/command",
        "cohere/command-r",
        "cohere/command-r-plus",
        "databricks/dbrx-instruct",
        "deepseek/deepseek-chat",
        "deepseek/deepseek-coder",
        "qwen/qwen-2-72b",
        "x-ai/grok-beta",
    }

    def __init__(self) -> None:
        """Initialize the ModelCapabilityChecker.

        Creates an empty cache for storing model capabilities.

        Example:
            >>> checker = ModelCapabilityChecker()
        """
        self._cache: dict[str, ModelCapabilities] = {}

    def check_vision_support(self, model_id: str) -> VisionSupport:
        """Check if a model supports vision/image inputs.

        Args:
            model_id: The model identifier (e.g., "openai/gpt-4-vision").

        Returns:
            VisionSupport enum value indicating support status.

        Example:
            >>> checker = ModelCapabilityChecker()
            >>> result = checker.check_vision_support("openai/gpt-4-vision")
            >>> print(result)
            VisionSupport.SUPPORTED
        """
        # Check cache first
        if model_id in self._cache:
            capabilities = self._cache[model_id]
            if capabilities.supports_vision:
                return VisionSupport.SUPPORTED
            else:
                return VisionSupport.UNSUPPORTED

        # Check known vision models
        if self._is_vision_model(model_id):
            capabilities = self._create_vision_capabilities(model_id)
            self._cache[model_id] = capabilities
            return VisionSupport.SUPPORTED

        # Check known text-only models
        if self._is_text_only_model(model_id):
            capabilities = self._create_text_capabilities(model_id)
            self._cache[model_id] = capabilities
            return VisionSupport.UNSUPPORTED

        # Unknown model - return unknown status
        capabilities = ModelCapabilities(model_id=model_id)
        self._cache[model_id] = capabilities
        return VisionSupport.UNKNOWN

    def get_capabilities(self, model_id: str) -> ModelCapabilities:
        """Get full capabilities for a model.

        Args:
            model_id: The model identifier.

        Returns:
            ModelCapabilities object with detailed capability information.

        Example:
            >>> checker = ModelCapabilityChecker()
            >>> caps = checker.get_capabilities("openai/gpt-4-vision")
            >>> print(capabilities.supports_vision)
            True
        """
        # Check cache first
        if model_id in self._cache:
            return self._cache[model_id]

        # Determine capabilities
        if self._is_vision_model(model_id):
            capabilities = self._create_vision_capabilities(model_id)
        elif self._is_text_only_model(model_id):
            capabilities = self._create_text_capabilities(model_id)
        else:
            capabilities = ModelCapabilities(model_id=model_id)
            logger.warning(f"Unknown model: {model_id}, assuming text-only")

        self._cache[model_id] = capabilities
        return capabilities

    def is_model_compatible(self, model_id: str, has_image: bool = False) -> bool:
        """Check if a model is compatible with the given question type.

        Args:
            model_id: The model identifier.
            has_image: Whether the question includes an image.

        Returns:
            True if the model can handle the question type, False otherwise.

        Example:
            >>> checker = ModelCapabilityChecker()
            >>> checker.is_model_compatible("openai/gpt-4-vision", has_image=True)
            True
            >>> checker.is_model_compatible("openai/gpt-3.5-turbo", has_image=True)
            False
        """
        if not has_image:
            # All models can handle text-only questions
            return True

        # For vision questions, check if model supports vision
        vision_support = self.check_vision_support(model_id)
        
        if vision_support == VisionSupport.UNKNOWN:
            # Safe default: assume unknown models don't support vision
            logger.warning(
                f"Model {model_id} has unknown vision support, "
                "marking as incompatible with vision questions"
            )
            return False
        
        return vision_support == VisionSupport.SUPPORTED

    def clear_cache(self) -> None:
        """Clear the model capabilities cache.

        This can be useful when model capabilities may have changed
        or to free up memory.

        Example:
            >>> checker = ModelCapabilityChecker()
            >>> checker.check_vision_support("openai/gpt-4-vision")
            >>> checker.clear_cache()
        """
        self._cache.clear()
        logger.debug("Model capabilities cache cleared")

    def _is_vision_model(self, model_id: str) -> bool:
        """Check if model is in the known vision models list.

        Args:
            model_id: The model identifier.

        Returns:
            True if the model is known to support vision.
        """
        # Exact match
        if model_id in self.VISION_MODELS:
            return True
        
        # Check for vision-related keywords in model name
        vision_keywords = ["vision", "4o", "o1", "o3", "3.5-sonnet", "3-5-sonnet", "3-haiku", "3.5-haiku", "gemini-1.5", "gemini-2"]
        for keyword in vision_keywords:
            if keyword in model_id.lower():
                return True
        
        return False

    def _is_text_only_model(self, model_id: str) -> bool:
        """Check if model is in the known text-only models list.

        Args:
            model_id: The model identifier.

        Returns:
            True if the model is known to be text-only.
        """
        # Exact match
        if model_id in self.TEXT_ONLY_MODELS:
            return True
        
        # Check provider prefixes for known text-only providers
        text_only_prefixes = ["mistral/", "cohere/", "databricks/", "deepseek/"]
        for prefix in text_only_prefixes:
            if model_id.startswith(prefix):
                # Exclude any that might have vision variants
                if "vision" not in model_id.lower():
                    return True
        
        return False

    def _create_vision_capabilities(self, model_id: str) -> ModelCapabilities:
        """Create capabilities object for a vision model.

        Args:
            model_id: The model identifier.

        Returns:
            ModelCapabilities configured for vision support.
        """
        return ModelCapabilities(
            model_id=model_id,
            supports_vision=True,
            max_image_size_mb=20,  # Common default
            supported_image_formats=["png", "jpg", "jpeg", "gif", "webp"],
        )

    def _create_text_capabilities(self, model_id: str) -> ModelCapabilities:
        """Create capabilities object for a text-only model.

        Args:
            model_id: The model identifier.

        Returns:
            ModelCapabilities configured for text-only support.
        """
        return ModelCapabilities(
            model_id=model_id,
            supports_vision=False,
            max_image_size_mb=0,
            supported_image_formats=[],
        )
