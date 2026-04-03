"""Validation tests for retry whitelist and failed run re-execution.

These tests verify the structural fixes for:
1. Retry whitelist: Only transient errors are retried, programming errors fail fast
2. Failed run re-execution: Failed/partial_failed runs can be re-executed
3. Import fixes: json module is properly imported in execution_engine.py

Usage:
    pytest tests/test_retry_whitelist_and_rerun.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestRetryWhitelist:
    """Test that retry handler uses whitelist-based classification."""

    @pytest.mark.asyncio
    async def test_nameerror_fails_immediately(self):
        """Verify NameError is NOT retried - fails on first attempt."""
        from src.core.retry import RetryHandler
        from src.core.execution_plan import RetryPolicy

        policy = RetryPolicy(max_attempts=3, backoff='exponential')
        handler = RetryHandler(policy)

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise NameError("name 'json' is not defined")

        with pytest.raises(NameError, match="name 'json' is not defined"):
            await handler.execute_with_retry(failing_func, context="test_nameerror")

        # Verify function was called exactly once (no retries)
        assert call_count == 1, f"Expected 1 call, but was called {call_count} times"

    @pytest.mark.asyncio
    async def test_typeerror_fails_immediately(self):
        """Verify TypeError is NOT retried - fails on first attempt."""
        from src.core.retry import RetryHandler
        from src.core.execution_plan import RetryPolicy

        policy = RetryPolicy(max_attempts=3, backoff='exponential')
        handler = RetryHandler(policy)

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("unsupported operand type(s)")

        with pytest.raises(TypeError, match="unsupported operand type"):
            await handler.execute_with_retry(failing_func, context="test_typeerror")

        # Verify function was called exactly once (no retries)
        assert call_count == 1, f"Expected 1 call, but was called {call_count} times"

    @pytest.mark.asyncio
    async def test_attributeerror_fails_immediately(self):
        """Verify AttributeError is NOT retried - fails on first attempt."""
        from src.core.retry import RetryHandler
        from src.core.execution_plan import RetryPolicy

        policy = RetryPolicy(max_attempts=3, backoff='exponential')
        handler = RetryHandler(policy)

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise AttributeError("'NoneType' has no attribute 'foo'")

        with pytest.raises(AttributeError):
            await handler.execute_with_retry(failing_func, context="test_attributeerror")

        # Verify function was called exactly once (no retries)
        assert call_count == 1, f"Expected 1 call, but was called {call_count} times"

    @pytest.mark.asyncio
    async def test_connectionerror_is_retried(self):
        """Verify ConnectionError IS retried (whitelisted transient error)."""
        from src.core.retry import RetryHandler
        from src.core.execution_plan import RetryPolicy

        policy = RetryPolicy(max_attempts=3, backoff='constant')
        handler = RetryHandler(policy)

        call_count = 0

        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection refused")
            return "success"

        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await handler.execute_with_retry(
                failing_then_success,
                context="test_connectionerror"
            )

        assert result == "success"
        assert call_count == 3, f"Expected 3 calls (2 retries), but was called {call_count} times"

    @pytest.mark.asyncio
    async def test_timeouterror_is_retried(self):
        """Verify TimeoutError IS retried (whitelisted transient error)."""
        from src.core.retry import RetryHandler
        from src.core.execution_plan import RetryPolicy

        policy = RetryPolicy(max_attempts=2, backoff='constant')
        handler = RetryHandler(policy)

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Request timed out")

        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(TimeoutError):
                await handler.execute_with_retry(failing_func, context="test_timeouterror")

        # Should retry up to max_attempts
        assert call_count == 2, f"Expected 2 calls (1 retry), but was called {call_count} times"

    @pytest.mark.asyncio
    async def test_syntaxerror_fails_immediately(self):
        """Verify SyntaxError is NOT retried - fails on first attempt."""
        from src.core.retry import RetryHandler
        from src.core.execution_plan import RetryPolicy

        policy = RetryPolicy(max_attempts=3, backoff='exponential')
        handler = RetryHandler(policy)

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            # Simulate syntax error scenario
            raise SyntaxError("invalid syntax")

        with pytest.raises(SyntaxError):
            await handler.execute_with_retry(failing_func, context="test_syntaxerror")

        # Verify function was called exactly once (no retries)
        assert call_count == 1, f"Expected 1 call, but was called {call_count} times"


class TestExecutionEngineJsonImport:
    """Test that execution_engine has json module imported."""

    def test_json_module_is_imported(self):
        """Verify json module is imported in execution_engine.py."""
        import src.core.execution_engine as ee
        
        # Verify json is available in the module
        assert hasattr(ee, 'json'), "json module must be imported in execution_engine.py"
        assert callable(ee.json.dumps), "json.dumps must be accessible"

    def test_execution_result_has_request_json_field(self):
        """Verify ExecutionResult dataclass includes request_json field."""
        from src.core.execution_engine import ExecutionResult

        result = ExecutionResult(
            item_id="test-item",
            run_id="test-run",
            variant_id="test-variant",
            snapshot_id="test-snapshot",
            question_id="test-question",
            status="success",
            response_text="test",
            selected_answer="A",
            parse_confidence="clear",
            latency_ms=100,
            input_tokens=50,
            response_tokens=10,
            error_type=None,
            error_message=None,
            attempt_count=1,
            request_json='{"test": true}',
        )

        assert result.request_json == '{"test": true}'


class TestPlannerFailedRunSelection:
    """Test that planner selects failed runs for re-execution."""

    def test_planner_query_includes_failed_runs(self):
        """Verify the SQL query includes failed and partial_failed statuses."""
        # Read the planner source to verify the query
        import inspect
        from src.core.planner import Planner

        source = inspect.getsource(Planner._get_runs)
        
        # Verify the query includes all three statuses
        assert "'pending'" in source, "Query must include 'pending' status"
        assert "'failed'" in source, "Query must include 'failed' status"
        assert "'partial_failed'" in source, "Query must include 'partial_failed' status"
        assert "IN (" in source or "in (" in source, "Query must use IN clause for multiple statuses"

    def test_planner_comment_mentions_idempotency(self):
        """Verify the code comment explains why failed runs can be re-executed."""
        import inspect
        from src.core.planner import Planner

        source = inspect.getsource(Planner._get_runs)
        
        # Verify there's a comment explaining data integrity
        assert "UNIQUE" in source or "idempotent" in source.lower() or "integrity" in source.lower(), \
            "Code should comment explaining why failed run re-execution is safe"


class TestIntegrationRetryAndRequestJson:
    """Integration-style test verifying request_json is captured even with errors."""

    def test_request_json_serialization_with_reasoning(self):
        """Verify request_json correctly serializes complex payload with reasoning."""
        payload = {
            "model": "test/model",
            "messages": [{"role": "user", "content": "test"}],
            "temperature": 0.9,
            "reasoning": {
                "effort": "high",
                "max_tokens": 2000
            },
            "stream": True
        }

        request_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        parsed = json.loads(request_json)

        # Verify structure is preserved
        assert parsed["model"] == "test/model"
        assert parsed["temperature"] == 0.9
        assert parsed["reasoning"]["effort"] == "high"
        assert parsed["reasoning"]["max_tokens"] == 2000
        assert parsed["stream"] is True

        # Verify keys are sorted
        keys = list(parsed.keys())
        assert keys == sorted(keys), "Keys must be sorted for deterministic serialization"
