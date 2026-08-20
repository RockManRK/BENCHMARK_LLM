"""Shared fixtures for benchmark_llm test suite.

This module provides common fixtures for unit and integration tests:
- in_memory_db: In-memory SQLite with TO-BE schema
- mock_api_client: Mocked OpenRouterClient
- randomizer: Seeded AnswerRandomizer for deterministic tests
- parser: AnswerParser instance
"""

import pytest
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock
from typing import Generator

# Import TO-BE schema creation
from src.db.schema import create_schema


@pytest.fixture
def in_memory_db() -> Generator[sqlite3.Connection, None, None]:
    """Create in-memory SQLite database with TO-BE schema.

    This fixture provides a fresh in-memory database for each test.
    The database is initialized with the full TO-BE schema containing:
    - experiments
    - model_variants
    - question_snapshots
    - runs
    - responses
    - errors

    Yields:
        sqlite3.Connection: Database connection with row_factory enabled

    Example:
        def test_repository_crud(in_memory_db):
            repo = ExperimentRepository(in_memory_db)
            experiment = repo.create(...)
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row

    # Execute full TO-BE schema
    create_schema(conn)

    # Verify tables were created
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    expected_tables = {'experiments', 'model_variants', 'question_snapshots', 'runs', 'responses', 'errors'}
    if not expected_tables.issubset(set(tables)):
        raise RuntimeError(
            f"Schema initialization failed. Expected tables: {expected_tables}, "
            f"got: {tables}"
        )

    yield conn

    # Cleanup
    try:
        conn.close()
    except Exception:
        pass


@pytest.fixture
def mock_api_client():
    """Mock OpenRouterClient for unit tests.

    This fixture creates a MagicMock with the OpenRouterClient spec,
    pre-configured to return a realistic CompletionResponse.

    Returns:
        MagicMock: Mocked API client

    Example:
        async def test_execution_engine_calls_api(mock_api_client):
            engine = ExecutionEngine(mock_api_client, randomizer, parser)
            results = await engine.execute_async(plan, queue)
            mock_api_client.chat_completion.assert_called_once()
    """
    # Import the real classes for spec (will exist in Phase 5)
    try:
        from src.api.client import OpenRouterClient, CompletionResponse
    except ImportError:
        # Fallback for Phase 4 when src doesn't exist yet
        # Define minimal spec classes
        class OpenRouterClient:
            async def chat_completion(self, model_id, messages, **kwargs):
                pass

        class CompletionResponse:
            def __init__(self, content, model_id, input_tokens, response_tokens, latency_ms):
                self.content = content
                self.model_id = model_id
                self.input_tokens = input_tokens
                self.response_tokens = response_tokens
                self.latency_ms = latency_ms

    client = MagicMock(spec=OpenRouterClient)
    client.debug_enabled = False
    client.chat_completion.return_value = CompletionResponse(
        content="The answer is (B).",
        model_id="openai/gpt-4",
        input_tokens=50,
        response_tokens=10,
        latency_ms=500,
    )
    return client


@pytest.fixture
def randomizer():
    """Create seeded AnswerRandomizer for deterministic tests.

    This fixture provides a randomizer with a fixed seed to ensure
    test reproducibility.

    Returns:
        AnswerRandomizer: Seeded randomizer instance

    Example:
        def test_randomizer_shuffles_deterministically(randomizer):
            options1 = randomizer.shuffle(['A', 'B', 'C', 'D'])
            options2 = randomizer.shuffle(['A', 'B', 'C', 'D'])
            assert options1 == options2  # Same seed = same result
    """
    try:
        from src.core.randomizer import AnswerRandomizer
        return AnswerRandomizer(seed=42)
    except ImportError:
        # Fallback for Phase 4 when src doesn't exist yet
        class AnswerRandomizer:
            def __init__(self, seed: int = 42):
                import random
                self._random = random.Random(seed)

            def shuffle(self, items: list) -> list:
                result = items.copy()
                self._random.shuffle(result)
                return result

        return AnswerRandomizer(seed=42)


@pytest.fixture
def parser():
    """Create AnswerParser instance for tests.

    Returns:
        AnswerParser: Parser instance

    Example:
        def test_parser_extracts_answer(parser):
            result = parser.parse("The answer is (B).")
            assert result.selected_answer == 'B'
            assert result.confidence == 'clear'
    """
    try:
        from src.core.answer_parser import AnswerParser
        return AnswerParser()
    except ImportError:
        # Fallback for Phase 4 when src doesn't exist yet
        import re
        from dataclasses import dataclass
        from typing import Literal, Optional

        @dataclass
        class ParseResult:
            selected_answer: Optional[str]
            confidence: Literal['clear', 'ambiguous', 'no_answer', 'low_confidence']

        class AnswerParser:
            def parse(self, response_text: str) -> ParseResult:
                # Strategy 1: Explicit letter pattern (e.g., "Answer: B")
                match = re.search(r'\b(?:answer(?:\s*:)?\s*)([A-D])\b', response_text, re.IGNORECASE)
                if match:
                    return ParseResult(selected_answer=match.group(1).upper(), confidence='clear')

                # Strategy 2: Letter in parentheses (e.g., "(B)")
                match = re.search(r'\(([A-D])\)', response_text, re.IGNORECASE)
                if match:
                    return ParseResult(selected_answer=match.group(1).upper(), confidence='clear')

                # Strategy 3: Standalone letter at line start
                match = re.search(r'^([A-D])\b', response_text, re.MULTILINE | re.IGNORECASE)
                if match:
                    return ParseResult(selected_answer=match.group(1).upper(), confidence='ambiguous')

                # No answer found
                return ParseResult(selected_answer=None, confidence='no_answer')

        return AnswerParser()


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers and settings."""
    # Domain rule tests (highest priority)
    config.addinivalue_line(
        "markers",
        "domain_rule: marks tests for core domain rules (critical)",
    )

    # Contract tests (second priority)
    config.addinivalue_line(
        "markers",
        "contract: marks tests for component contracts",
    )

    # Integration tests
    config.addinivalue_line(
        "markers",
        "integration: marks integration tests (slower, use real DB)",
    )

    # Slow tests
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
