# Track: mock_testing_20260306

## Specification: Mock Testing for LLM API

### Overview
Implement mock testing infrastructure to enable fast, cost-free testing without real API calls. This allows developers to test system logic, database operations, and error handling without spending credits or requiring network connectivity.

### Current State Analysis

**What Works:**
- ✅ Real API calls to llama.cpp/OpenRouter
- ✅ Tests exist but require real server
- ✅ pytest already used in project

**Gaps Identified:**
- ❌ No mock testing infrastructure
- ❌ All tests require real API server
- ❌ Slow test feedback loop
- ❌ Costs money for testing

### Functional Requirements

#### FR1: Mock Infrastructure
- **FR1.1**: Install `responses` library for HTTP mocking
- **FR1.2**: Create pytest fixtures for mock responses
- **FR1.3**: Support both sync and async tests

#### FR2: Mock Responses
- **FR2.1**: Mock successful responses with various formats
- **FR2.2**: Mock error responses (500, 429, 404)
- **FR2.3**: Mock reasoning_content field
- **FR2.4**: Mock structured outputs

#### FR3: Test Coverage
- **FR3.1**: Test database save operations
- **FR3.2**: Test response parsing
- **FR3.3**: Test error handling
- **FR3.4**: Test question randomization

### Non-Functional Requirements

#### NFR1: Speed
- **NFR1.1**: Tests should run in < 5 seconds
- **NFR1.2**: No network calls

#### NFR2: Maintainability
- **NFR2.1**: Easy to add new mock scenarios
- **NFR2.2**: Clear documentation

### Acceptance Criteria

1. ✅ `pip install responses` works
2. ✅ Mock fixture available in tests
3. ✅ Test runs without API server
4. ✅ Test completes in < 5 seconds
5. ✅ Can simulate success and error scenarios
6. ✅ Existing tests still work

### Out of Scope

- Mock server for integration tests (future)
- Performance testing with mock (future)
- Load testing (future)

---

## Implementation Plan

### Phase 1: Setup and Basic Mock

- [ ] Task: Install dependencies
    - [ ] Add `responses` to requirements.txt
    - [ ] Add `pytest` to requirements.txt (if not already)
    - [ ] Update requirements-dev.txt if exists
- [ ] Task: Create basic mock fixture
    - [ ] Create `tests/conftest.py` if not exists
    - [ ] Add `mock_llm_response()` fixture
    - [ ] Support custom response content
- [ ] Task: Create first mock test
    - [ ] Test single question execution
    - [ ] Verify database save
    - [ ] Verify response parsing
- [ ] Task: Conductor - User Manual Verification 'Setup and Basic Mock' (Protocol in workflow.md)

### Phase 2: Mock Scenarios

- [ ] Task: Create mock response templates
    - [ ] Standard text response
    - [ ] Response with reasoning_content
    - [ ] Structured output response (JSON)
    - [ ] Error responses (500, 429, 404)
- [ ] Task: Create test scenarios
    - [ ] Test successful answer parsing
    - [ ] Test reasoning_content extraction
    - [ ] Test structured output parsing
    - [ ] Test API error handling
    - [ ] Test rate limit retry logic
- [ ] Task: Conductor - User Manual Verification 'Mock Scenarios' (Protocol in workflow.md)

### Phase 3: Integration with Existing Tests

- [ ] Task: Migrate existing tests to use mock
    - [ ] Identify tests that can use mock
    - [ ] Update tests to use fixtures
    - [ ] Ensure tests pass
- [ ] Task: Add test runner script
    - [ ] Create `run_tests.sh` or `.bat`
    - [ ] Add to README
- [ ] Task: Conductor - User Manual Verification 'Integration' (Protocol in workflow.md)

### Phase 4: Documentation

- [ ] Task: Document mock usage
    - [ ] Add to TESTING_GUIDE.md
    - [ ] Add examples in tests
    - [ ] Update MANUAL.md if needed
- [ ] Task: Conductor - User Manual Verification 'Documentation' (Protocol in workflow.md)

---

## Metadata

```json
{
  "track_id": "mock_testing_20260306",
  "type": "feature",
  "status": "new",
  "created_at": "2026-03-06T00:00:00Z",
  "description": "Implement mock testing infrastructure for fast, cost-free testing"
}
```
