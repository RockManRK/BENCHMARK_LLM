"""Configuration hierarchy management for benchmark_llm.

This module provides clear hierarchy resolution and user feedback
for configuration values, following the pattern:
    1. CLI (highest priority)
    2. Environment (.env)
    3. Default internal (lowest priority)

Rules:
    - CLI values: No feedback needed (user explicitly set them)
    - .env values: Inform user "using default from environment (.env)"
    - Internal defaults: Inform user "using default (description)"
"""

import logging
from typing import Any, Optional

from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


class ConfigSource:
    """Configuration source enumeration."""
    CLI = "cli"
    ENV = "env"
    DEFAULT = "default"


def resolve_with_feedback(
    cli_value: Any,
    env_value: Any,
    default_value: Any,
    config_name: str,
    cli_flag_name: Optional[str] = None,
    show_cli: bool = False,
) -> tuple[Any, Optional[str]]:
    """Resolve configuration value with hierarchy and feedback.

    Args:
        cli_value: Value from CLI (None if not provided).
        env_value: Value from environment/.env (None if not set).
        default_value: Internal default value.
        config_name: Human-readable name for feedback (e.g., "Questions").
        cli_flag_name: CLI flag name for reference (e.g., "--questions").
        show_cli: If True, show feedback even for CLI values.

    Returns:
        Tuple of (resolved_value, feedback_message or None).

    Example:
        >>> value, msg = resolve_with_feedback(
        ...     cli_value=None,
        ...     env_value="Q001-Q010",
        ...     default_value="ALL",
        ...     config_name="Questions"
        ... )
        >>> print(msg)
        "Questions: using default from environment (.env)"
    """
    # Hierarchy: CLI > ENV > DEFAULT
    if cli_value is not None:
        source = ConfigSource.CLI
        value = cli_value
    elif env_value is not None:
        source = ConfigSource.ENV
        value = env_value
    else:
        source = ConfigSource.DEFAULT
        value = default_value

    # Generate feedback message
    message = _generate_feedback_message(
        config_name=config_name,
        source=source,
        cli_flag_name=cli_flag_name,
        show_cli=show_cli,
    )

    return value, message


def _generate_feedback_message(
    config_name: str,
    source: str,
    cli_flag_name: Optional[str] = None,
    show_cli: bool = False,
) -> Optional[str]:
    """Generate user feedback message based on configuration source.

    Args:
        config_name: Human-readable configuration name.
        source: Source of the value (CLI, ENV, or DEFAULT).
        cli_flag_name: CLI flag name for reference.
        show_cli: If True, show feedback for CLI values too.

    Returns:
        Feedback message string or None (no feedback for CLI by default).
    """
    if source == ConfigSource.CLI and not show_cli:
        # CLI values are explicit - no feedback needed
        return None

    elif source == ConfigSource.ENV:
        # Environment default - inform user
        return f"{config_name}: using default from environment (.env)"

    elif source == ConfigSource.DEFAULT:
        # Internal default - inform user
        # Special case: "Questions" should say "all available questions"
        if config_name == "Questions":
            return f"{config_name}: using all available questions (default)"
        else:
            return f"{config_name}: using default ({config_name.lower()})"

    return None


def format_config_summary(
    messages: list[Optional[str]],
    title: str = "Configuration",
) -> None:
    """Print configuration summary with feedback messages.

    Args:
        messages: List of feedback messages (None values are filtered).
        title: Optional title for the summary section.

    Example:
        >>> messages = [
        ...     "Questions: using all available questions (default)",
        ...     "Seed: using default from environment (.env)",
        ...     None,  # CLI value - no feedback
        ... ]
        >>> format_config_summary(messages, "Configuration")
    """
    # Filter out None messages
    valid_messages = [m for m in messages if m is not None]

    if not valid_messages:
        return

    console.print()
    console.print(f"[dim]{title}:[/dim]")
    for msg in valid_messages:
        console.print(f"  {msg}")
