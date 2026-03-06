# Track: reasoning_support_20260306

## Specification: Enhanced Reasoning Tokens Support

### Overview

Implement support for OpenRouter reasoning tokens following their API best practices. Focus on robust data collection and proper handling of reasoning parameters.

### Current State Analysis

**What Works:**
- ✅ Basic `reasoning_content` fallback in parser
- ✅ Captures reasoning from models that support it

**Gaps Identified:**
- ❌ No configuration for reasoning parameters (`effort`, `max_tokens`)
- ❌ No support for `reasoning_details` structured format
- ❌ No option to exclude reasoning from response
- ❌ No tracking of reasoning tokens in usage

### Functional Requirements

#### FR1: Reasoning Parameter Configuration (OpenRouter Standard)
- **FR1.1**: Support `reasoning.effort` parameter (xhigh, high, medium, low, minimal, none)
- **FR1.2**: Support `reasoning.max_tokens` parameter (direct token allocation)
- **FR1.3**: Support `reasoning.exclude` parameter (use internally, don't return)
- **FR1.4**: Support `reasoning.enabled` parameter (enable with defaults)

#### FR2: Configuration Methods
- **FR2.1**: Configure via `.env` file (global default)
- **FR2.2**: Override via CLI flags (per-execution)

#### FR3: Reasoning Details Handling
- **FR3.1**: Parse `reasoning_details` array from OpenRouter API response
- **FR3.2**: Extract reasoning type and content
- **FR3.3**: Store reasoning details in database metadata

#### FR4: Data Collection
- **FR4.1**: Track reasoning tokens separately from completion tokens
- **FR4.2**: Store reasoning metadata in database
- **FR4.3**: Log reasoning usage for analysis

### Non-Functional Requirements

#### NFR1: Robustness
- **NFR1.1**: Graceful fallback when reasoning not supported
- **NFR1.2**: No breaking changes to existing functionality
- **NFR1.3**: Proper error handling for reasoning parameters

#### NFR2: Data Integrity
- **NFR2.1**: All reasoning data captured correctly
- **NFR2.2**: Database schema supports reasoning fields
- **NFR2.3**: No data loss during reasoning parameter processing

### Acceptance Criteria

1. ✅ Can configure reasoning effort via `.env`: `REASONING_EFFORT=high`
2. ✅ Can configure reasoning max_tokens via `.env`: `REASONING_MAX_TOKENS=2000`
3. ✅ Can override via CLI: `--reasoning-effort high --reasoning-tokens 2000`
4. ✅ Can exclude reasoning from response: `REASONING_EXCLUDE=true`
5. ✅ Reasoning details parsed and stored in database
6. ✅ Reasoning tokens tracked in usage metadata
7. ✅ Graceful fallback for models without reasoning support
8. ✅ All existing tests pass (backward compatibility)

### Out of Scope

- Multi-turn conversation reasoning preservation
- Tool calling with reasoning
- Model-specific API research (OpenRouter handles abstraction)
- Cost analysis and warnings
- Extensive documentation

---

## Implementation Plan

### Phase 1: Analysis and Design
- [ ] Task: Review existing reasoning_content implementation
    - [ ] Analyze `src/api/parser.py` reasoning_content handling
    - [ ] Analyze `src/core/question_executor.py` reasoning usage
    - [ ] Document current reasoning flow
- [ ] Task: Research model-specific reasoning APIs
    - [ ] Document OpenAI reasoning API
    - [ ] Document Anthropic reasoning API
    - [ ] Document Gemini reasoning API
    - [ ] Document Qwen reasoning API
    - [ ] Document llama.cpp reasoning capabilities
- [ ] Task: Design reasoning configuration structure
    - [ ] Design .env configuration format
    - [ ] Design CLI argument format
    - [ ] Design internal data structures
- [ ] Task: Create test strategy
    - [ ] Define unit tests for reasoning parameters
    - [ ] Define integration tests with different models
    - [ ] Define backward compatibility tests

### Phase 2: Core Implementation - Reasoning Parameters
- [ ] Task: Add reasoning configuration to Settings
    - [ ] Add `reasoning_effort` field to `src/utils/config.py`
    - [ ] Add `reasoning_max_tokens` field to `src/utils/config.py`
    - [ ] Add `reasoning_exclude` field to `src/utils/config.py`
    - [ ] Add `reasoning_enabled` field to `src/utils/config.py`
    - [ ] Add validators for reasoning parameters
- [ ] Task: Add CLI flags for reasoning
    - [ ] Add `--reasoning-effort` flag to `src/cli/cli.py`
    - [ ] Add `--reasoning-tokens` flag to `src/cli/cli.py`
    - [ ] Add `--reasoning-exclude` flag to `src/cli/cli.py`
    - [ ] Update help text with reasoning examples
- [ ] Task: Update OpenRouterClient to support reasoning parameters
    - [ ] Add `reasoning` parameter to `chat_completion()` method
    - [ ] Build reasoning config object from parameters
    - [ ] Send reasoning config in API request
    - [ ] Handle reasoning-specific errors
- [ ] Task: Update QuestionExecutor to use reasoning parameters
    - [ ] Pass reasoning config to API client
    - [ ] Log reasoning configuration used
    - [ ] Handle reasoning parameter errors gracefully

### Phase 3: Enhanced Features - Reasoning Details
- [ ] Task: Implement reasoning_details parsing
    - [ ] Parse `reasoning_details` array from API response
    - [ ] Extract `reasoning.summary` type
    - [ ] Extract `reasoning.text` type
    - [ ] Handle `reasoning.encrypted` type (log only)
    - [ ] Store reasoning_details in response metadata
- [ ] Task: Update database schema for reasoning details
    - [ ] Add `reasoning_details` field to responses table (JSON)
    - [ ] Add `reasoning_tokens` field to responses table (integer)
    - [ ] Update Model dataclass if needed
    - [ ] Create database migration script
- [ ] Task: Update ResponseRepository
    - [ ] Add reasoning_details to create method
    - [ ] Add reasoning_tokens to create method
    - [ ] Update queries to include reasoning fields
- [ ] Task: Implement reasoning token tracking
    - [ ] Extract reasoning tokens from usage response
    - [ ] Log reasoning tokens separately
    - [ ] Include in cost calculation

### Phase 4: Testing and Validation
- [ ] Task: Unit tests for reasoning configuration
    - [ ] Test .env reasoning parameters loading
    - [ ] Test CLI reasoning flags parsing
    - [ ] Test reasoning config validation
    - [ ] Test reasoning config building
- [ ] Task: Integration tests with reasoning models
    - [ ] Test with OpenAI o-series (effort parameter)
    - [ ] Test with Anthropic Claude (max_tokens parameter)
    - [ ] Test with Gemini (reasoning parameter)
    - [ ] Test with Qwen (thinking_budget)
    - [ ] Test fallback for non-reasoning models
- [ ] Task: Backward compatibility tests
    - [ ] Test existing benchmarks without reasoning config
    - [ ] Test reasoning_content fallback still works
    - [ ] Test database queries still work
    - [ ] Test all existing tests pass
- [ ] Task: Performance tests
    - [ ] Measure reasoning parameter overhead
    - [ ] Test with high reasoning effort
    - [ ] Test with reasoning exclusion

### Phase 5: Documentation
- [ ] Task: Update .env.example
    - [ ] Add reasoning configuration section
    - [ ] Add examples for different model types
    - [ ] Add comments explaining reasoning parameters
- [ ] Task: Update MANUAL.md
    - [ ] Add reasoning configuration section
    - [ ] Add reasoning CLI flags documentation
    - [ ] Add model compatibility table
    - [ ] Add reasoning usage examples
- [ ] Task: Update README.md
    - [ ] Add reasoning support to overview
    - [ ] Add reasoning quick start example
- [ ] Task: Add troubleshooting section
    - [ ] Document reasoning-related errors
    - [ ] Document model compatibility issues
    - [ ] Document cost considerations
- [ ] Task: Create reasoning guide document
    - [ ] Explain reasoning tokens
    - [ ] Show cost/benefit analysis
    - [ ] Provide best practices

### Phase 6: Conductor - User Manual Verification
- [ ] Task: Conductor - User Manual Verification 'Analysis and Design' (Protocol in workflow.md)
- [ ] Task: Conductor - User Manual Verification 'Core Implementation' (Protocol in workflow.md)
- [ ] Task: Conductor - User Manual Verification 'Enhanced Features' (Protocol in workflow.md)
- [ ] Task: Conductor - User Manual Verification 'Testing and Validation' (Protocol in workflow.md)
- [ ] Task: Conductor - User Manual Verification 'Documentation' (Protocol in workflow.md)

---

## Metadata

```json
{
  "track_id": "reasoning_support_20260306",
  "type": "feature",
  "status": "new",
  "created_at": "2026-03-06T00:00:00Z",
  "description": "Implement comprehensive reasoning tokens support following OpenRouter best practices"
}
```
