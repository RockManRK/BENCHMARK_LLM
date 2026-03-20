"""Integration tests for benchmark_llm TO-BE architecture.

This module contains end-to-end integration tests that verify complete
workflows across all layers (CLI → Core → API → DB).

Test Categories:
- Full experiment lifecycle workflows
- Execution flow (Planner → Engine → Writer)
- Review workflow (needs_review calculation, manual override)
- Error handling (validation errors, API errors, retry behavior)

All tests use:
- Mocked API client (no real API calls)
- In-memory SQLite database with full TO-BE schema
- CLI entry points where possible (verifies full integration)
"""
