"""Variant configuration module for model variant identity management.

This module provides functionality to generate stable variant identifiers
and human-readable signatures for model variants based on their identity
parameters (reasoning, vision, structured outputs).

Variant Identity:
    - reasoning_mode: 'off', 'auto', 'effort', 'budget', 'unspecified'
    - reasoning_effort: 'xhigh', 'high', 'medium', 'low', 'minimal' (when mode='effort')
    - reasoning_max_tokens: integer (when mode='budget')
    - vision_enabled: boolean
    - structured_enabled: boolean

Non-Identity Parameters (NOT part of variant identity):
    - temperature, top_p, top_k, max_tokens, repeat_penalty
    These are execution parameters that do NOT define variant identity.

Example:
    >>> config = VariantConfig(
    ...     reasoning_mode="effort",
    ...     reasoning_effort="high",
    ...     vision_enabled=False,
    ...     structured_enabled=True
    ... )
    >>> config.build_signature("openai/gpt-4")
    'openai/gpt-4::reasoning=effort:high::vision=false::structured=true'
    >>> config.build_variant_id("openai/gpt-4")
    'var-a1b2c3d4'
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VariantConfig:
    """Configuration for model variant identity.

    This class encapsulates the identity parameters that define a model variant.
    It provides methods to generate:
    - variant_signature: Human-readable string identifying the variant
    - variant_id: Short stable hash-based identifier

    Attributes:
        reasoning_mode: Reasoning mode ('off', 'auto', 'effort', 'budget', 'unspecified').
        reasoning_effort: Reasoning effort level (when mode='effort').
        reasoning_max_tokens: Maximum reasoning tokens (when mode='budget').
        vision_enabled: Whether vision is enabled.
        structured_enabled: Whether structured outputs are enabled.

    Example:
        >>> config = VariantConfig(
        ...     reasoning_mode="auto",
        ...     vision_enabled=False,
        ...     structured_enabled=False
        ... )
        >>> signature = config.build_signature("anthropic/claude-3")
        >>> print(signature)
        anthropic/claude-3::reasoning=auto::vision=false::structured=false
    """

    reasoning_mode: str = "unspecified"
    reasoning_effort: Optional[str] = None
    reasoning_max_tokens: Optional[int] = None
    vision_enabled: bool = False
    structured_enabled: bool = False

    def __post_init__(self) -> None:
        """Validate variant configuration after initialization."""
        valid_modes = {"off", "auto", "effort", "budget", "unspecified"}
        if self.reasoning_mode not in valid_modes:
            raise ValueError(
                f"reasoning_mode must be one of {valid_modes}, got '{self.reasoning_mode}'"
            )

        valid_efforts = {"xhigh", "high", "medium", "low", "minimal"}
        if self.reasoning_effort is not None and self.reasoning_effort not in valid_efforts:
            raise ValueError(
                f"reasoning_effort must be one of {valid_efforts} or None, got '{self.reasoning_effort}'"
            )

        if self.reasoning_mode == "effort" and self.reasoning_effort is None:
            raise ValueError(
                "reasoning_effort is required when reasoning_mode='effort'"
            )

        if self.reasoning_mode == "budget" and self.reasoning_max_tokens is None:
            raise ValueError(
                "reasoning_max_tokens is required when reasoning_mode='budget'"
            )

        if self.reasoning_max_tokens is not None and self.reasoning_max_tokens <= 0:
            raise ValueError(
                f"reasoning_max_tokens must be positive, got {self.reasoning_max_tokens}"
            )

    def build_signature(self, model_id: str) -> str:
        """Build human-readable variant signature.

        The signature is a readable string that uniquely identifies
        the variant within the context of a base model.

        Format:
            {model_id}::reasoning={mode}[:{effort|tokens}]::vision={bool}::structured={bool}

        Examples:
            - "openai/gpt-4::reasoning=auto::vision=false::structured=false"
            - "qwen/qwen-2.5::reasoning=effort:high::vision=false::structured=true"
            - "claude-3::reasoning=budget:8000::vision=true::structured=false"
            - "gemini::reasoning=off::vision=false::structured=false"

        Args:
            model_id: Base model identifier (e.g., "openai/gpt-4").

        Returns:
            Human-readable variant signature string.
        """
        # Build reasoning part
        if self.reasoning_mode == "effort" and self.reasoning_effort:
            reasoning_part = f"reasoning={self.reasoning_mode}:{self.reasoning_effort}"
        elif self.reasoning_mode == "budget" and self.reasoning_max_tokens is not None:
            reasoning_part = f"reasoning={self.reasoning_mode}:{self.reasoning_max_tokens}"
        else:
            reasoning_part = f"reasoning={self.reasoning_mode}"

        # Build signature
        signature = (
            f"{model_id}::{reasoning_part}"
            f"::vision={str(self.vision_enabled).lower()}"
            f"::structured={str(self.structured_enabled).lower()}"
        )

        return signature

    def build_variant_id(self, model_id: str) -> str:
        """Build short stable variant identifier (hash-based).

        Generates a deterministic hash from the variant identity parameters.
        The same parameters will always produce the same variant_id.

        Format: var-{first 8 chars of SHA-256 hash}

        Args:
            model_id: Base model identifier.

        Returns:
            Short variant identifier (e.g., "var-a1b2c3d4").
        """
        # Build identity dictionary for hashing
        identity = {
            "model_id": model_id,
            "reasoning_mode": self.reasoning_mode,
            "reasoning_effort": self.reasoning_effort,
            "reasoning_max_tokens": self.reasoning_max_tokens,
            "vision_enabled": self.vision_enabled,
            "structured_enabled": self.structured_enabled,
        }

        # Serialize to JSON with sorted keys for determinism
        identity_json = json.dumps(identity, sort_keys=True, default=str)

        # Generate SHA-256 hash
        hash_hex = hashlib.sha256(identity_json.encode()).hexdigest()[:8]

        return f"var-{hash_hex}"

    def to_openrouter_reasoning(self) -> Optional[dict]:
        """Build OpenRouter reasoning configuration payload.

        Returns:
            - None if reasoning_mode is 'unspecified' (don't send field)
            - dict with reasoning configuration for other modes

        Examples:
            >>> config = VariantConfig(reasoning_mode="unspecified")
            >>> config.to_openrouter_reasoning()
            None

            >>> config = VariantConfig(reasoning_mode="off")
            >>> config.to_openrouter_reasoning()
            {'enabled': False}

            >>> config = VariantConfig(reasoning_mode="effort", reasoning_effort="high")
            >>> config.to_openrouter_reasoning()
            {'effort': 'high'}

            >>> config = VariantConfig(reasoning_mode="budget", reasoning_max_tokens=8000)
            >>> config.to_openrouter_reasoning()
            {'max_tokens': 8000}
        """
        if self.reasoning_mode == "unspecified":
            # Don't send reasoning field - use model default
            return None

        if self.reasoning_mode == "off":
            return {"enabled": False}

        if self.reasoning_mode == "auto":
            # Use model's default reasoning behavior
            # Don't send any reasoning parameters
            return None

        if self.reasoning_mode == "effort" and self.reasoning_effort:
            return {"effort": self.reasoning_effort}

        if self.reasoning_mode == "budget" and self.reasoning_max_tokens is not None:
            return {"max_tokens": self.reasoning_max_tokens}

        # Fallback: don't send reasoning field
        return None

    def to_dict(self) -> dict:
        """Convert variant config to dictionary.

        Returns:
            Dictionary with all variant configuration fields.
        """
        return {
            "reasoning_mode": self.reasoning_mode,
            "reasoning_effort": self.reasoning_effort,
            "reasoning_max_tokens": self.reasoning_max_tokens,
            "vision_enabled": self.vision_enabled,
            "structured_enabled": self.structured_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VariantConfig":
        """Create VariantConfig from dictionary.

        Args:
            data: Dictionary with variant configuration fields.

        Returns:
            VariantConfig instance.
        """
        return cls(
            reasoning_mode=data.get("reasoning_mode", "unspecified"),
            reasoning_effort=data.get("reasoning_effort"),
            reasoning_max_tokens=data.get("reasoning_max_tokens"),
            vision_enabled=data.get("vision_enabled", False),
            structured_enabled=data.get("structured_enabled", False),
        )
