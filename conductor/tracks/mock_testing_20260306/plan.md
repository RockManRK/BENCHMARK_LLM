# Implementation Plan: Mock Testing Infrastructure

## Phase 1: Setup and Basic Mock

- [ ] Task: Install dependencies
    - [ ] Add `responses` to requirements.txt
    - [ ] Verify `pytest` is in requirements.txt
    - [ ] Run `pip install -r requirements.txt`
- [ ] Task: Create pytest configuration
    - [ ] Create `tests/conftest.py` with pytest fixtures
    - [ ] Add `mock_llm_response()` fixture
    - [ ] Add `sample_response()` fixture with standard response
- [ ] Task: Create first mock test
    - [ ] Create `tests/test_mock_basic.py`
    - [ ] Test single question with mock
    - [ ] Verify response parsing works
    - [ ] Verify database save works
- [ ] Task: Conductor - User Manual Verification 'Setup and Basic Mock' (Protocol in workflow.md)

## Phase 2: Mock Scenarios

- [ ] Task: Create response templates
    - [ ] Standard text response (no reasoning)
    - [ ] Response with reasoning_content
    - [ ] Structured output response (JSON)
    - [ ] Error response (500)
    - [ ] Rate limit response (429)
- [ ] Task: Create scenario tests
    - [ ] Test answer extraction (A, B, C, D formats)
    - [ ] Test reasoning_content extraction
    - [ ] Test structured output parsing
    - [ ] Test API error handling
    - [ ] Test retry logic (if exists)
- [ ] Task: Conductor - User Manual Verification 'Mock Scenarios' (Protocol in workflow.md)

## Phase 3: Documentation

- [ ] Task: Document mock usage
    - [ ] Add section to TESTING_GUIDE.md
    - [ ] Add examples in test files
    - [ ] Update MANUAL.md with test commands
- [ ] Task: Create test runner script
    - [ ] Create `run_tests.bat` for Windows
    - [ ] Create `run_tests.sh` for Linux/Mac
    - [ ] Add to README
- [ ] Task: Conductor - User Manual Verification 'Documentation' (Protocol in workflow.md)
