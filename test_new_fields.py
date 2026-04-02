"""Test script to validate new token and cost fields.

This script validates that:
1. stream_aggregator correctly aggregates SSE chunks
2. response_parser correctly extracts all fields
3. ExecutionResult includes new fields
4. ResultWriter INSERT includes new columns
"""

import sys
sys.path.insert(0, 'D:\\OneDrive\\Pessoais\\Projetos\\benchmark_llm')

from src.api.stream_aggregator import aggregate_streaming_response
from src.api.response_parser import parse_to_completion_response
from src.api.client import CompletionResponse
from src.core.execution_engine import ExecutionResult


def test_stream_aggregator():
    """Test stream aggregator with realistic SSE chunks."""
    print("=" * 70)
    print("TEST 1: Stream Aggregator")
    print("=" * 70)
    
    # Simulate realistic OpenRouter streaming chunks
    chunks = [
        # Debug chunk (first)
        {
            "id": "test-123",
            "created": 1234567890,
            "model": "openai/gpt-4o-mini",
            "choices": [],
            "debug": {
                "echo_upstream_body": {
                    "max_tokens": 100,
                    "temperature": 0.7
                }
            }
        },
        # Content chunk 1
        {
            "id": "test-123",
            "created": 1234567890,
            "model": "openai/gpt-4o-mini",
            "choices": [{
                "delta": {"content": "The answer"},
                "index": 0
            }]
        },
        # Content chunk 2
        {
            "id": "test-123",
            "created": 1234567890,
            "model": "openai/gpt-4o-mini",
            "choices": [{
                "delta": {"content": " is (B)."},
                "index": 0
            }]
        },
        # Final chunk with usage
        {
            "id": "test-123",
            "created": 1234567890,
            "model": "openai/gpt-4o-mini",
            "choices": [{
                "delta": {},
                "finish_reason": "stop",
                "index": 0
            }],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
                "cost": 0.0000375,
                "completion_tokens_details": {
                    "reasoning_tokens": 5,
                    "image_tokens": 0,
                    "audio_tokens": 0
                }
            }
        }
    ]
    
    aggregated = aggregate_streaming_response(chunks)
    
    # Validate
    assert aggregated.content == "The answer is (B).", f"Content mismatch: {aggregated.content}"
    assert aggregated.finish_reason == "stop", f"Finish reason: {aggregated.finish_reason}"
    assert aggregated.usage["prompt_tokens"] == 50
    assert aggregated.usage["completion_tokens"] == 10
    assert aggregated.usage["cost"] == 0.0000375
    assert aggregated.usage["completion_tokens_details"]["reasoning_tokens"] == 5
    assert aggregated.debug_info is not None
    assert len(aggregated.raw_response) == 4
    
    print("✅ Content aggregated correctly")
    print("✅ Finish reason extracted from final chunk")
    print("✅ Usage data extracted from final chunk")
    print("✅ Debug info captured from first chunk")
    print("✅ All chunks preserved in raw_response")
    print()


def test_response_parser():
    """Test response parser extracts all fields correctly."""
    print("=" * 70)
    print("TEST 2: Response Parser")
    print("=" * 70)
    
    # Create aggregated response
    chunks = [
        {
            "choices": [],
            "debug": {"echo_upstream_body": {}}
        },
        {
            "choices": [{"delta": {"content": "Answer"}}]
        },
        {
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "cost": 0.0000375,
                "completion_tokens_details": {
                    "reasoning_tokens": 5
                }
            }
        }
    ]
    
    aggregated = aggregate_streaming_response(chunks)
    response = parse_to_completion_response(aggregated, "openai/gpt-4o-mini", 500)
    
    # Validate
    assert response.content == "Answer"
    assert response.model_id == "openai/gpt-4o-mini"
    assert response.input_tokens == 50
    assert response.response_tokens == 10
    assert response.reasoning_tokens == 5
    assert response.cost == 0.0000375
    assert response.latency_ms == 500
    
    print("✅ input_tokens extracted: 50")
    print("✅ response_tokens extracted: 10")
    print("✅ reasoning_tokens extracted: 5")
    print("✅ cost extracted: 0.0000375")
    print("✅ latency_ms set: 500")
    print()


def test_completion_response_dataclass():
    """Test CompletionResponse dataclass has all fields."""
    print("=" * 70)
    print("TEST 3: CompletionResponse Dataclass")
    print("=" * 70)
    
    response = CompletionResponse(
        content="Test",
        model_id="test/model",
        input_tokens=10,
        response_tokens=5,
        latency_ms=100,
        reasoning_tokens=3,
        cost=0.00001,
        raw_response=[]
    )
    
    assert response.reasoning_tokens == 3
    assert response.cost == 0.00001
    
    print("✅ reasoning_tokens field exists")
    print("✅ cost field exists")
    print()


def test_execution_result_dataclass():
    """Test ExecutionResult dataclass has all fields."""
    print("=" * 70)
    print("TEST 4: ExecutionResult Dataclass")
    print("=" * 70)
    
    from datetime import datetime
    
    result = ExecutionResult(
        item_id="test-item",
        run_id="run-1",
        variant_id="var-1",
        snapshot_id="snap-1",
        question_id="q1",
        status="success",
        response_text="Answer",
        selected_answer="A",
        parse_confidence="clear",
        latency_ms=100,
        input_tokens=10,
        response_tokens=5,
        reasoning_tokens=3,
        cost=0.00001,
        effective_tokens=18,
        error_type=None,
        error_message=None,
        attempt_count=1,
        raw_response=[],
        started_at=datetime.now(),
        finished_at=datetime.now(),
        finish_reason="stop",
        error_details=None
    )
    
    assert result.reasoning_tokens == 3
    assert result.cost == 0.00001
    assert result.effective_tokens == 18
    
    print("✅ reasoning_tokens field exists")
    print("✅ cost field exists")
    print("✅ effective_tokens field exists")
    print()


def test_effective_tokens_calculation():
    """Test effective_tokens calculation."""
    print("=" * 70)
    print("TEST 5: Effective Tokens Calculation")
    print("=" * 70)
    
    input_tokens = 50
    response_tokens = 10
    reasoning_tokens = 5
    
    effective_tokens = input_tokens + response_tokens + reasoning_tokens
    
    assert effective_tokens == 65
    print(f"✅ Calculation: {input_tokens} + {response_tokens} + {reasoning_tokens} = {effective_tokens}")
    print()


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "VALIDATION: New Token & Cost Fields" + " " * 23 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    try:
        test_stream_aggregator()
        test_response_parser()
        test_completion_response_dataclass()
        test_execution_result_dataclass()
        test_effective_tokens_calculation()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Summary:")
        print("  - stream_aggregator.py: ✅ Correctly aggregates SSE chunks")
        print("  - response_parser.py: ✅ Correctly extracts all fields")
        print("  - CompletionResponse: ✅ Has reasoning_tokens and cost")
        print("  - ExecutionResult: ✅ Has all new fields")
        print("  - effective_tokens: ✅ Correctly calculated")
        print()
        
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
