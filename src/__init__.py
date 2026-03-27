"""Benchmark LLM - A Python-based benchmark tool for evaluating LLM performance.

This package provides a comprehensive benchmark system for testing Large Language
Models (LLMs) using a standardized 100-question medical questionnaire through the
OpenRouter API.

Features:
    - Multi-model benchmarking with configurable iterations
    - Comprehensive metrics collection (accuracy, latency, token usage)
    - SQLite database for persistent storage of experimental data
    - Support for both text-only and multimodal (text + image) questions
    - Answer randomization for reproducibility
    - Detailed error tracking and logging

Example:
    >>> from src.main import main
    >>> # Run via command line:
    >>> # python -m src.main --models openai/gpt-4 --iterations 3

Version:
    1.0.0

Author:
    Benchmark LLM Team

License:
    MIT
"""

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)
__author__ = "Benchmark LLM Team"
__license__ = "MIT"
__description__ = "A benchmark tool for evaluating LLM performance"
__email__ = "benchmark-llm@example.com"


def get_version() -> str:
    """Get the package version string.

    Returns:
        Version string in semantic versioning format (MAJOR.MINOR.PATCH).

    Example:
        >>> get_version()
        '1.0.0'
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
