"""Message builder for OpenRouter API messages.

This module provides static methods to construct properly formatted
messages for the OpenRouter chat completion API, supporting both
text-only and multimodal (text + image) content.

Following OpenRouter specification:
- Text content comes FIRST in the content array
- Images come AFTER text (per OpenRouter recommendation)
- Images are base64-encoded as data URLs
- Supported formats: PNG, JPG, JPEG, GIF, WEBP

Example:
    >>> text_message = MessageBuilder.build_user_message("Hello!")
    >>> image_message = MessageBuilder.build_multimodal_message(
    ...     text="What's in this image?",
    ...     image_path=Path("image.png")
    ... )
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from src.utils.logging_config import get_logger

logger = get_logger('api.message_builder')

# Supported image formats and their MIME types
SUPPORTED_IMAGE_FORMATS: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class MessageBuilder:
    """Utility class for building API messages.

    This class provides static methods to construct properly formatted
    messages for the OpenRouter chat completion API, supporting both
    text-only and multimodal content.

    Example:
        >>> text_message = MessageBuilder.build_user_message("Hello!")
        >>> image_message = MessageBuilder.build_multimodal_message(
        ...     text="What's in this image?",
        ...     image_path=Path("image.png")
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

        Following OpenRouter recommendation:
        - Text comes FIRST in the content array
        - Images come AFTER text

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
            ...     text="Describe this image",
            ...     image_path=Path("chest_xray.png")
            ... )
        """
        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Determine image format
        suffix = image_path.suffix.lower()

        if suffix not in SUPPORTED_IMAGE_FORMATS:
            logger.error(
                f"Unsupported image format: {suffix}. "
                f"Supported formats: {list(SUPPORTED_IMAGE_FORMATS.keys())}"
            )
            raise ValueError(
                f"Unsupported image format: {suffix}. "
                f"Supported formats: {list(SUPPORTED_IMAGE_FORMATS.keys())}"
            )

        # Read and encode image
        image_data = image_path.read_bytes()
        mime_type = SUPPORTED_IMAGE_FORMATS[suffix]
        base64_image = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:{mime_type};base64,{base64_image}"

        logger.info(
            f"Multimodal message built | image={image_path} | "
            f"format={mime_type} | size={len(image_data)} bytes"
        )

        # Per OpenRouter recommendation: text FIRST, then images
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
