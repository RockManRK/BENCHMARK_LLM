"""Test script for the new consolidate_streaming_response function."""

import json
import sys
from pathlib import Path

# Add project root to path so we can import the module
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.stream_aggregator import (
    AggregatedResponse,
    aggregate_streaming_response,
    consolidate_streaming_response,
)


def test_consolidation_with_raw_json():
    """Load json_raw.json and verify consolidate_streaming_response preserves all data."""
    raw_path = project_root / "json_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} raw chunks from json_raw.json")

    # Aggregate first
    aggregated = aggregate_streaming_response(chunks)

    # Consolidate
    result = consolidate_streaming_response(aggregated)

    # Print result as formatted JSON for visual inspection
    print("\n" + "=" * 80)
    print("CONSOLIDATED OUTPUT")
    print("=" * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 80)

    # ================================================================
    # Assertions
    # ================================================================
    errors = []

    # 1. usage must NOT be null
    if result.get("usage") is None:
        errors.append("FAIL: 'usage' is null — expected a full usage object")
    else:
        usage = result["usage"]
        # Verify key fields are present
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cost", "cost_details", "completion_tokens_details"):
            if key not in usage:
                errors.append(f"FAIL: 'usage.{key}' is missing")
        print(f"\n[PASS] usage is present with keys: {list(usage.keys())}")

    # 2. debug must NOT be null
    if result.get("debug") is None:
        errors.append("FAIL: 'debug' is null — expected debug object from first chunk")
    else:
        debug = result["debug"]
        if "echo_upstream_body" not in debug:
            errors.append("FAIL: 'debug.echo_upstream_body' is missing")
        print(f"[PASS] debug is present with keys: {list(debug.keys())}")

    # 3. content should be "D" (the single answer character from chunk 8)
    content = result.get("content", "")
    if content != "D":
        errors.append(f"FAIL: 'content' is '{content}' — expected 'D'")
    else:
        print(f"[PASS] content is '{content}'")

    # 4. chunk_count should be 10
    chunk_count = result.get("chunk_count")
    if chunk_count != 10:
        errors.append(f"FAIL: 'chunk_count' is {chunk_count} — expected 10")
    else:
        print(f"[PASS] chunk_count is {chunk_count}")

    # 5. Identity fields from first chunk
    for key in ("id", "object", "created", "model", "provider"):
        if key not in result:
            errors.append(f"FAIL: identity field '{key}' is missing")
        else:
            print(f"[PASS] identity field '{key}' = {result[key]}")

    # 6. reasoning should be non-empty (we have multiple reasoning chunks)
    reasoning = result.get("reasoning", "")
    if not reasoning:
        errors.append("FAIL: 'reasoning' is empty — expected concatenated reasoning text")
    else:
        print(f"[PASS] reasoning is present ({len(reasoning)} chars)")

    # 7. reasoning_details should be a non-empty array
    rd = result.get("reasoning_details")
    if not rd or not isinstance(rd, list) or len(rd) == 0:
        errors.append(f"FAIL: 'reasoning_details' is empty or missing — expected {len(rd) if rd else 0} items")
    else:
        print(f"[PASS] reasoning_details has {len(rd)} items")

    # 8. finish_reason should be "stop"
    fr = result.get("finish_reason")
    if fr != "stop":
        errors.append(f"FAIL: 'finish_reason' is '{fr}' — expected 'stop'")
    else:
        print(f"[PASS] finish_reason is '{fr}'")

    # 9. native_finish_reason should be "STOP"
    nfr = result.get("native_finish_reason")
    if nfr != "STOP":
        errors.append(f"FAIL: 'native_finish_reason' is '{nfr}' — expected 'STOP'")
    else:
        print(f"[PASS] native_finish_reason is '{nfr}'")

    # 10. streaming should be True
    if result.get("streaming") is not True:
        errors.append(f"FAIL: 'streaming' is {result.get('streaming')} — expected True")
    else:
        print(f"[PASS] streaming is True")

    # 11. note disclaimer should exist
    if "note" not in result:
        errors.append("FAIL: 'note' disclaimer is missing")
    else:
        print(f"[PASS] note disclaimer is present")

    # ================================================================
    # Summary
    # ================================================================
    print("\n" + "=" * 80)
    if errors:
        print(f"RESULTS: {len(errors)} FAILURE(S)")
        for err in errors:
            print(f"  ❌ {err}")
        return False
    else:
        print("RESULTS: ALL TESTS PASSED ✅")
        return True


if __name__ == "__main__":
    success = test_consolidation_with_raw_json()
    sys.exit(0 if success else 1)
