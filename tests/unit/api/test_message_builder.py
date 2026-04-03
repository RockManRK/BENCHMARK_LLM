"""Unit tests for MessageBuilder.

Tests cover:
- Text-only message building
- Multimodal message building for each supported format
- FileNotFoundError for missing image
- ValueError for unsupported image format
"""

import base64
from pathlib import Path

import pytest

from src.api.message_builder import MessageBuilder, SUPPORTED_IMAGE_FORMATS


class TestBuildUserMessage:
    """Tests for build_user_message static method."""

    def test_build_user_message_text_only(self):
        """Text-only message returns correct dict structure."""
        content = "What is 2+2?"
        result = MessageBuilder.build_user_message(content)

        assert result == {"role": "user", "content": content}

    def test_build_user_message_empty_string(self):
        """Empty string content is still valid."""
        result = MessageBuilder.build_user_message("")
        assert result == {"role": "user", "content": ""}

    def test_build_user_message_multiline(self):
        """Multiline content is preserved."""
        content = "Line 1\nLine 2\nLine 3"
        result = MessageBuilder.build_user_message(content)
        assert result["content"] == content


class TestBuildMultimodalMessage:
    """Tests for build_multimodal_message static method."""

    @pytest.fixture
    def tmp_image_file(self, tmp_path: Path) -> Path:
        """Create a temporary PNG image file for testing."""
        # Minimal valid PNG (1x1 pixel)
        # This is a real minimal PNG header + IHDR + IDAT + IEND
        png_header = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk length + type
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # width=1, height=1
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # bit depth=8, color=RGB
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # CRC + IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0x0F, 0x00, 0x00,  # IDAT data
            0x01, 0x01, 0x01, 0x00, 0x18, 0xDD, 0x8D, 0xB4,  # IDAT CRC
            0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,  # IEND chunk
            0xAE, 0x42, 0x60, 0x82,  # IEND CRC
        ])
        image_file = tmp_path / "test_image.png"
        image_file.write_bytes(png_header)
        return image_file

    def test_build_multimodal_message_png(self, tmp_image_file: Path):
        """PNG image produces correct multimodal message."""
        text = "What is in this image?"
        result = MessageBuilder.build_multimodal_message(text, tmp_image_file)

        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 2

        # Text part comes first (per OpenRouter recommendation)
        text_part = result["content"][0]
        assert text_part["type"] == "text"
        assert text_part["text"] == text

        # Image part
        image_part = result["content"][1]
        assert image_part["type"] == "image_url"
        assert "url" in image_part["image_url"]

        # Verify data URL format
        data_url = image_part["image_url"]["url"]
        assert data_url.startswith("data:image/png;base64,")

        # Verify base64 encoding is correct
        encoded_data = data_url.split(",", 1)[1]
        decoded = base64.b64decode(encoded_data)
        assert decoded == tmp_image_file.read_bytes()

    def test_build_multimodal_message_jpg(self, tmp_path: Path):
        """JPG image produces correct multimodal message."""
        jpg_file = tmp_path / "test_image.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0fake_jpeg_data")

        text = "Describe this JPG image."
        result = MessageBuilder.build_multimodal_message(text, jpg_file)

        data_url = result["content"][1]["image_url"]["url"]
        assert data_url.startswith("data:image/jpeg;base64,")

    def test_build_multimodal_message_jpeg(self, tmp_path: Path):
        """JPEG image (with .jpeg extension) produces correct MIME type."""
        jpeg_file = tmp_path / "test_image.jpeg"
        jpeg_file.write_bytes(b"\xFF\xD8\xFF\xE0fake_jpeg_data")

        text = "Describe this JPEG image."
        result = MessageBuilder.build_multimodal_message(text, jpeg_file)

        data_url = result["content"][1]["image_url"]["url"]
        assert data_url.startswith("data:image/jpeg;base64,")

    def test_build_multimodal_message_gif(self, tmp_path: Path):
        """GIF image produces correct multimodal message."""
        gif_file = tmp_path / "test_image.gif"
        gif_file.write_bytes(b"GIF89afake_gif_data")

        text = "What is in this GIF?"
        result = MessageBuilder.build_multimodal_message(text, gif_file)

        data_url = result["content"][1]["image_url"]["url"]
        assert data_url.startswith("data:image/gif;base64,")

    def test_build_multimodal_message_webp(self, tmp_path: Path):
        """WEBP image produces correct multimodal message."""
        webp_file = tmp_path / "test_image.webp"
        webp_file.write_bytes(b"RIFFfake_webp_data")

        text = "Describe this WEBP image."
        result = MessageBuilder.build_multimodal_message(text, webp_file)

        data_url = result["content"][1]["image_url"]["url"]
        assert data_url.startswith("data:image/webp;base64,")

    def test_build_multimodal_message_missing_file_raises_error(self, tmp_path: Path):
        """Missing image file raises FileNotFoundError."""
        missing_file = tmp_path / "nonexistent.png"
        text = "What is in this image?"

        with pytest.raises(FileNotFoundError, match="Image file not found"):
            MessageBuilder.build_multimodal_message(text, missing_file)

    def test_build_multimodal_message_unsupported_format_raises_error(self, tmp_path: Path):
        """Unsupported image format raises ValueError."""
        bmp_file = tmp_path / "test_image.bmp"
        bmp_file.write_bytes(b"BMfake_bmp_data")

        text = "What is in this BMP?"

        with pytest.raises(ValueError, match="Unsupported image format"):
            MessageBuilder.build_multimodal_message(text, bmp_file)

    def test_build_multimodal_message_text_comes_first(self, tmp_image_file: Path):
        """Text content appears before image content in the message (OpenRouter recommendation)."""
        text = "Test text ordering."
        result = MessageBuilder.build_multimodal_message(text, tmp_image_file)

        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "image_url"

    def test_all_supported_formats(self):
        """Verify SUPPORTED_IMAGE_FORMATS contains all expected formats."""
        expected_formats = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        assert set(SUPPORTED_IMAGE_FORMATS.keys()) == expected_formats
