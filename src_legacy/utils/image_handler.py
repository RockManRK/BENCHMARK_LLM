"""Image handler module for benchmark_llm project.

This module provides functionality to load, validate, and encode images
for use with LLM APIs that support image input.
"""

import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from PIL import Image

logger = logging.getLogger(__name__)

# Maximum image size in bytes (10 MB)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# Supported image formats
SUPPORTED_FORMATS = {"PNG", "JPEG", "JPG", "WEBP", "GIF"}


class ImageHandler:
    """Handler for image loading, validation, and encoding.

    This class provides methods to load images from disk, validate their
    format and size, and encode them to base64 for transmission to LLM APIs.

    Example:
        >>> handler = ImageHandler()
        >>> base64_data = handler.encode_to_base64("data/assets/image_Q005.png")
        >>> if base64_data:
        ...     print(f"Image encoded successfully")
    """

    def __init__(
        self,
        max_size_bytes: int = MAX_IMAGE_SIZE_BYTES,
        supported_formats: Optional[set[str]] = None,
    ) -> None:
        """Initialize the ImageHandler.

        Args:
            max_size_bytes: Maximum allowed image size in bytes. Defaults to 10 MB.
            supported_formats: Set of supported image formats. Defaults to common formats.
        """
        self.max_size_bytes = max_size_bytes
        self.supported_formats = supported_formats or SUPPORTED_FORMATS
        logger.debug(
            f"ImageHandler initialized: max_size={max_size_bytes} bytes, "
            f"formats={self.supported_formats}"
        )

    def load_image(self, image_path: str) -> Optional[Image.Image]:
        """Load an image from file.

        Args:
            image_path: Path to the image file.

        Returns:
            PIL Image object if successful, None if the file cannot be loaded.

        Example:
            >>> handler = ImageHandler()
            >>> img = handler.load_image("data/assets/image_Q005.png")
            >>> if img:
            ...     print(f"Image size: {img.size}")
        """
        path = Path(image_path)

        if not path.exists():
            logger.warning(f"Image file not found: {image_path}")
            return None

        try:
            img = Image.open(path)
            img.load()  # Force load to catch corrupted files
            logger.debug(f"Loaded image: {image_path} ({img.size[0]}x{img.size[1]})")
            return img
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None

    def encode_to_base64(
        self,
        image_path: str,
        format: Optional[str] = None,
    ) -> Optional[str]:
        """Encode an image to base64 string.

        Args:
            image_path: Path to the image file.
            format: Output format (PNG, JPEG, etc.). If None, uses original format.

        Returns:
            Base64-encoded string of the image, or None if encoding fails.

        Example:
            >>> handler = ImageHandler()
            >>> base64_str = handler.encode_to_base64("data/assets/image_Q005.png")
            >>> if base64_str:
            ...     print(f"Encoded length: {len(base64_str)}")
        """
        img = self.load_image(image_path)
        if img is None:
            return None

        try:
            buffer = BytesIO()

            # Convert to RGB if necessary (for JPEG format)
            output_format = format or img.format or "PNG"
            if output_format.upper() in ("JPEG", "JPG") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img.save(buffer, format=output_format)
            base64_string = base64.b64encode(buffer.getvalue()).decode("utf-8")

            logger.debug(
                f"Encoded image to base64: {len(base64_string)} characters"
            )
            return base64_string
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            return None

    def validate_format(self, image_path: str) -> bool:
        """Validate that an image has a supported format.

        Args:
            image_path: Path to the image file.

        Returns:
            True if the format is supported, False otherwise.

        Example:
            >>> handler = ImageHandler()
            >>> if handler.validate_format("image.png"):
            ...     print("Format is supported")
        """
        path = Path(image_path)

        if not path.exists():
            logger.warning(f"Cannot validate format - file not found: {image_path}")
            return False

        try:
            with Image.open(path) as img:
                img_format = img.format
                if img_format is None:
                    logger.warning(f"Could not determine format for {image_path}")
                    return False

                is_supported = img_format.upper() in self.supported_formats
                if not is_supported:
                    logger.warning(
                        f"Unsupported image format: {img_format}. "
                        f"Supported: {self.supported_formats}"
                    )
                return is_supported
        except Exception as e:
            logger.error(f"Error validating format for {image_path}: {e}")
            return False

    def validate_size(self, image_path: str) -> bool:
        """Validate that an image file is within size limits.

        Args:
            image_path: Path to the image file.

        Returns:
            True if the file size is within limits, False otherwise.

        Example:
            >>> handler = ImageHandler()
            >>> if handler.validate_size("image.png"):
            ...     print("Size is acceptable")
        """
        path = Path(image_path)

        if not path.exists():
            logger.warning(f"Cannot validate size - file not found: {image_path}")
            return False

        try:
            file_size = path.stat().st_size
            is_valid = file_size <= self.max_size_bytes

            if not is_valid:
                logger.warning(
                    f"Image too large: {file_size} bytes (max: {self.max_size_bytes})"
                )
            else:
                logger.debug(f"Image size OK: {file_size} bytes")

            return is_valid
        except Exception as e:
            logger.error(f"Error validating size for {image_path}: {e}")
            return False

    def get_image_info(self, image_path: str) -> Optional[dict[str, Any]]:
        """Get information about an image file.

        Args:
            image_path: Path to the image file.

        Returns:
            Dictionary with image information, or None if cannot be loaded.
            Contains: format, size, width, height, mode, file_size.

        Example:
            >>> handler = ImageHandler()
            >>> info = handler.get_image_info("data/assets/image_Q005.png")
            >>> if info:
            ...     print(f"Format: {info['format']}, Size: {info['width']}x{info['height']}")
        """
        path = Path(image_path)

        if not path.exists():
            logger.warning(f"Image file not found: {image_path}")
            return None

        try:
            file_size = path.stat().st_size

            with Image.open(path) as img:
                info = {
                    "format": img.format,
                    "size": img.size,
                    "width": img.size[0],
                    "height": img.size[1],
                    "mode": img.mode,
                    "file_size": file_size,
                }
                logger.debug(f"Image info for {image_path}: {info}")
                return info
        except Exception as e:
            logger.error(f"Error getting image info for {image_path}: {e}")
            return None

    def process_image(self, image_path: str) -> Optional[dict[str, Any]]:
        """Process an image and return encoded data with metadata.

        This is a convenience method that validates and encodes an image
        in a single call.

        Args:
            image_path: Path to the image file.

        Returns:
            Dictionary with processing results, or None if processing fails.
            Contains: base64, format, valid, width, height, file_size.

        Example:
            >>> handler = ImageHandler()
            >>> result = handler.process_image("data/assets/image_Q005.png")
            >>> if result and result["valid"]:
            ...     print(f"Image ready: {len(result['base64'])} chars")
        """
        path = Path(image_path)

        if not path.exists():
            logger.warning(f"Image file not found: {image_path}")
            return None

        # Validate format and size
        format_valid = self.validate_format(image_path)
        size_valid = self.validate_size(image_path)
        is_valid = format_valid and size_valid

        # Get image info
        info = self.get_image_info(image_path)
        if info is None:
            return None

        # Encode to base64
        base64_data = None
        if is_valid:
            base64_data = self.encode_to_base64(image_path)

        result = {
            "base64": base64_data,
            "format": info["format"],
            "valid": is_valid,
            "width": info["width"],
            "height": info["height"],
            "file_size": info["file_size"],
        }

        logger.debug(
            f"Processed image {image_path}: valid={is_valid}, format={info['format']}"
        )
        return result

    def resize_image(
        self,
        image_path: str,
        max_width: int,
        max_height: int,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """Resize an image to fit within specified dimensions.

        Args:
            image_path: Path to the source image.
            max_width: Maximum width in pixels.
            max_height: Maximum height in pixels.
            output_path: Path for the resized image. If None, returns in-memory.

        Returns:
            Path to resized image if output_path provided, otherwise base64 string.
            Returns None if processing fails.

        Example:
            >>> handler = ImageHandler()
            >>> resized_path = handler.resize_image(
            ...     "large_image.png",
            ...     max_width=800,
            ...     max_height=600,
            ...     output_path="resized.png"
            ... )
        """
        img = self.load_image(image_path)
        if img is None:
            return None

        try:
            # Calculate new size maintaining aspect ratio
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            if output_path:
                img.save(output_path)
                logger.debug(f"Resized image saved to {output_path}")
                return output_path
            else:
                buffer = BytesIO()
                img.save(buffer, format=img.format or "PNG")
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Error resizing image {image_path}: {e}")
            return None
