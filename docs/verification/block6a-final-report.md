<!-- Source: src/cli/bcllm_execute.py, src/api/client.py, src/core/execution_engine.py -->

# Block 6a Final Verification Report

**Session:** llmbc-v2-block6a-verify-001  
**Date:** 2026-03-30  
**Status:** COMPLETE

---

## Executive Summary

The V2 API Client implementation is **functionally complete** but **incorrectly wired**.

**Key Finding:** A legacy placeholder class in `bcllm_execute.py` shadows the real `OpenRouterClient` implementation, causing all executions to fail with "OpenRouterClient is not yet implemented" error.

**Root Cause:** `src/cli/bcllm_execute.py` contains a duplicate placeholder class (lines 77-92) that was intended for temporary use but was never replaced with the real implementation from `src/api/client.py`.

**Fix Required:** Remove placeholder class (15 lines), import real client, pass real API key from environment.

**Verification Effort:** 6 files inspected, 3 divergences confirmed.

---

## Compliance Summary

| Component | Contract Compliance | Status |
|-----------|---------------------|--------|
| `src/api/client.py` (OpenRouterClient) | ✅ Fully Compliant | Production-ready |
| `src/api/errors.py` (Error hierarchy) | ✅ Fully Compliant | Production-ready |
| `src/core/retry.py` (RetryHandler) | ✅ Fully Compliant | Production-ready |
| `src/core/execution_engine.py` (Integration) | ⚠️ Partially Compliant | Needs RetryPolicy wiring + stop parameter |
| `src/cli/bcllm_execute.py` (CLI entry) | ❌ Non-Compliant | **BLOCKS EXECUTION** |

---

## Critical Divergence (Must Fix)

### Placeholder Class in `bcllm_execute.py`

**File:** `src/cli/bcllm_execute.py`  
**Lines:** 77-92 (class definition), 370 (instantiation)

**Current Code:**
```python
# Placeholder for API client (to be implemented in Phase 8)
class OpenRouterClient:
    """Placeholder for OpenRouterClient.

    This is a stub that will be replaced with the real implementation
    from src.api.client in Phase 8.
    """

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1") -> None:
        """Initialize with API credentials."""
        self.api_key = api_key
        self.base_url = base_url

    async def chat_completion(self, model_id: str, messages: list[dict], **kwargs):
        """Call OpenRouter chat completion API."""
        # Placeholder - will be implemented in Phase 8
        raise NotImplementedError("OpenRouterClient is not yet implemented")
```

**Instantiation (line 370):**
```python
api_client = OpenRouterClient(api_key="test-key")
```

**Problem:** The placeholder class raises `NotImplementedError` on every `chat_completion()` call, causing immediate execution failure.

**Impact:** All executions fail with error message "OpenRouterClient is not yet implemented".

**Fix:**
1. **DELETE** lines 77-92 (placeholder class definition)
2. **ADD** import at line 32: `from src.api.client import OpenRouterClient`
3. **MODIFY** line 370 to use real API key from environment variable

---

## High-Priority Divergences (Should Fix)

### 1. Missing `stop` Parameter in ExecutionEngine

**File:** `src/core/execution_engine.py`  
**Lines:** ~267-275 (chat_completion call site)

**Problem:** The `chat_completion()` method call does not pass the `stop` parameter from `ModelConfig`, preventing models from using custom stop sequences.

**Current Code:**
```python
response = await self.api_client.chat_completion(
    model_id=variant.model_id,
    messages=messages,
    # stop parameter missing
)
```

**Fix:** Add `stop=variant.model_config.stop` if `ModelConfig` supports the `stop` attribute.

**Impact:** Models requiring custom stop sequences (e.g., to prevent over-generation) will not behave correctly.

---

### 2. Default RetryPolicy Instead of Plan's Policy

**File:** `src/core/execution_engine.py`  
**Lines:** 170-174

**Current Code:**
```python
self._retry_handler = retry_handler or RetryHandler(
    policy=RetryPolicy(),  # ← Uses default policy, ignores plan's policy
    logger=self._logger
)
```

**Problem:** The `ExecutionEngine` constructor uses a default `RetryPolicy()` instead of the `retry_policy` from the `ExecutionPlan` or `PlanRun`.

**Fix:** Pass `retry_policy` from `PlanRun` to `RetryHandler` constructor:
```python
self._retry_handler = retry_handler or RetryHandler(
    policy=plan_run.retry_policy,  # ← Use plan's policy
    logger=self._logger
)
```

**Impact:** Custom retry configurations (e.g., more retries for expensive models) are ignored; all executions use default retry behavior.

---

## Medium/Low Divergences (Optional Improvements)

| Priority | Component | Issue | Impact |
|----------|-----------|-------|--------|
| Medium | `bcllm_execute.py:370` | Hardcoded API key `"test-key"` | Won't work in production without env var |
| Low | `execution_engine.py` | No validation of `variant.model_config` before accessing properties | Potential AttributeError if config is None |

---

## Minimal Implementation Plan

**To unblock API client and achieve V2 compliance:**

| Step | File | Change | Lines | Type |
|------|------|--------|-------|------|
| 1 | `src/cli/bcllm_execute.py` | Remove placeholder class | 77-92 | DELETE |
| 2 | `src/cli/bcllm_execute.py` | Add import: `from src.api.client import OpenRouterClient` | ~32 | ADD |
| 3 | `src/cli/bcllm_execute.py` | Update instantiation to use env var for API key | 370 | MODIFY |
| 4 | `src/core/execution_engine.py` | Use plan's RetryPolicy in RetryHandler init | 170-174 | MODIFY |
| 5 | `src/core/execution_engine.py` | Pass `stop` parameter to `chat_completion()` | ~267-275 | MODIFY |

**Total:** 3 files, ~25 lines changed (mostly deletions + 2-3 additions)

**Estimated Effort:** 15-30 minutes implementation + validation

---

## Verification Methodology

This report was produced by:

1. **Static Analysis:** Read source files to verify contract compliance
2. **Line-Level Inspection:** Confirmed exact line numbers for all divergences
3. **Import Chain Validation:** Verified `src/api/client.py` exports `OpenRouterClient` correctly
4. **Execution Path Tracing:** Traced execution flow from CLI → ExecutionEngine → API client

**Files Inspected:**
- `src/cli/bcllm_execute.py` (446 lines)
- `src/api/client.py` (346 lines)
- `src/core/execution_engine.py` (696 lines)
- `src/api/errors.py` (error hierarchy)
- `src/core/retry.py` (RetryHandler)
- `src/core/execution_plan.py` (RetryPolicy, PlanRun)

---

## Recommendation

**Block 6a Status:** ✅ **COMPLETE**

**Next Block:** Create **Block 6b — API Client Wiring Fix** to implement the minimal changes identified above.

**After Block 6b:** Resume Block 5 (Human-Driven Validation) with real API calls.

**Risk Assessment:**
- **Low Risk:** All changes are surgical and localized
- **High Impact:** Unblocks entire execution pipeline
- **Reversible:** Changes can be rolled back independently

---

## Handoff Notes

**For Block 6b Implementation Agent:**

1. **Start with the critical fix** (placeholder removal) — this alone unblocks execution
2. **Test after each change** — verify with a minimal experiment (1 model, 1 question)
3. **Use existing test infrastructure** — run `pytest` to validate no regressions
4. **API key handling** — ensure `OPENROUTER_API_KEY` environment variable is used

**Validation Command:**
```bash
python bcllm.py --experiment <test_exp> --run <test_run> --execute
```

Expected outcome: Execution proceeds past API client initialization and attempts real API call.

---

**Awaiting User Instruction:** Do not proceed to implementation. This report is the Block 6a deliverable. Wait for user to approve Block 6b or provide alternative direction.
