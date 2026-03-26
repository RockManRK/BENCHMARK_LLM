"""Benchmark LLM - LEGACY CODE.

⚠️  THIS IS LEGACY CODE - NOT MAINTAINED ⚠️

This package contains the previous implementation of the benchmark_llm project.
It is preserved for historical reference only.

DO NOT USE FOR NEW DEVELOPMENT.

For the current implementation, see the `src/` directory.

Original Documentation (Historical):
    A Python-based benchmark tool for evaluating LLM performance.
    This package provided a comprehensive benchmark system for testing Large Language
    Models (LLMs) using a standardized questionnaire through the OpenRouter API.

Version:
    1.0.0 (Legacy)

Status:
    DEPRECATED - Use src/ instead
"""

__version__ = "1.0.0-legacy"
__version_info__ = (1, 0, 0)
__author__ = "Benchmark LLM Team"
__license__ = "MIT"
__description__ = "LEGACY: A benchmark tool for evaluating LLM performance (DEPRECATED)"
__status__ = "DEPRECATED"
__email__ = "benchmark-llm@example.com"


def get_version() -> str:
    """Get the package version string.

    Returns:
        Version string in semantic versioning format (MAJOR.MINOR.PATCH).

    Example:
        >>> get_version()
        '1.0.0-legacy'
    """
    return __version__


def get_version_info() -> tuple[int, int, int]:
    """Get the package version as a tuple.

    Returns:
        Tuple of (major, minor, patch) version numbers.

    Example:
        >>> get_version_info()
        (1, 0, 0)
    """
    return __version_info__
