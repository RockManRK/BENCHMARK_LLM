# Implementation Plan: Enhanced Reasoning Tokens Support

## Phase 1: Core Implementation - Reasoning Parameters

- [ ] Task: Add reasoning configuration to Settings
    - [ ] Add `reasoning_effort` field to `src/utils/config.py`
    - [ ] Add `reasoning_max_tokens` field to `src/utils/config.py`
    - [ ] Add `reasoning_exclude` field to `src/utils/config.py`
    - [ ] Add validators for reasoning parameters
- [ ] Task: Add CLI flags for reasoning
    - [ ] Add `--reasoning-effort` flag to `src/cli/cli.py`
    - [ ] Add `--reasoning-tokens` flag to `src/cli/cli.py`
    - [ ] Add `--reasoning-exclude` flag to `src/cli/cli.py`
- [ ] Task: Update OpenRouterClient to support reasoning parameters
    - [ ] Add `reasoning` parameter to `chat_completion()` method
    - [ ] Build reasoning config object from parameters
    - [ ] Send reasoning config in API request
    - [ ] Handle reasoning-specific errors
- [ ] Task: Update QuestionExecutor to use reasoning parameters
    - [ ] Pass reasoning config to API client
    - [ ] Log reasoning configuration used
- [ ] Task: Conductor - User Manual Verification 'Core Implementation' (Protocol in workflow.md)

## Phase 2: Data Collection - Reasoning Details

- [ ] Task: Implement reasoning_details parsing
    - [ ] Parse `reasoning_details` array from API response
    - [ ] Extract reasoning content
    - [ ] Store reasoning_details in response metadata
- [ ] Task: Update database schema for reasoning details
    - [ ] Add `reasoning_details` field to responses table (JSON TEXT)
    - [ ] Add `reasoning_tokens` field to responses table (INTEGER)
    - [ ] Create migration script
    - [ ] Update `src/db/schema.py` with new fields
- [ ] Task: Update Response dataclass and repository
    - [ ] Add reasoning fields to Response dataclass
    - [ ] Update ResponseRepository to handle reasoning fields
    - [ ] Update queries to include reasoning fields
- [ ] Task: Implement reasoning token tracking
    - [ ] Extract reasoning tokens from usage response
    - [ ] Include reasoning tokens in metadata
- [ ] Task: Conductor - User Manual Verification 'Data Collection' (Protocol in workflow.md)

## Phase 3: Testing and Validation

- [ ] Task: Basic unit tests
    - [ ] Test .env reasoning parameters loading
    - [ ] Test CLI reasoning flags parsing
    - [ ] Test reasoning config validation
- [ ] Task: Backward compatibility tests
    - [ ] Test existing benchmarks without reasoning config
    - [ ] Test reasoning_content fallback still works
    - [ ] Test all existing tests pass
- [ ] Task: Manual test with local server
    - [ ] Test with Qwen local (verify graceful fallback)
    - [ ] Verify no errors when reasoning not supported
- [ ] Task: Conductor - User Manual Verification 'Testing and Validation' (Protocol in workflow.md)

## Phase 4: Minimal Documentation

- [ ] Task: Update .env.example
    - [ ] Add reasoning configuration section with examples
- [ ] Task: Update MANUAL.md
    - [ ] Add reasoning CLI flags to reference table
    - [ ] Add brief example of reasoning usage
- [ ] Task: Conductor - User Manual Verification 'Documentation' (Protocol in workflow.md)
