# Answer Parsing V2 Adaptation Guide

**Document Type:** V2 Adaptation Guide  
**Version:** 1.0  
**Date:** 2026-03-29  
**Phase:** 10/12 — Answer Parsing Domain Documentation  
**Status:** ✅ **IMPLEMENTATION READY**  

---

## 1. Overview

### 1.1 Purpose

This document guides the adaptation of the V2 Answer Parser to align with the TO-BE architecture specifications defined in `docs/architecture/to-be/08-answer-parsing-architecture.md`.

### 1.2 Current State Assessment

**V2 Parser Location:** `src/core/answer_parser.py`

**Assessment Summary:**
- ✅ **V1 Parity Confirmed** (Phase 3 validation)
- ✅ **Pattern Hierarchy**: 4 levels implemented correctly
- ✅ **Confidence Levels**: 4 values defined correctly
- ✅ **Article Filtering**: Portuguese/Spanish "A" filtering works
- ✅ **Ambiguity Detection**: Multiple letters trigger `ambiguous`
- ⚠️ **Logging**: Removed (quieter execution)
- ⚠️ **Reasoning Extraction**: Removed (unused feature)
- ⚠️ **Convenience Function**: Removed (minor API change)
- ⚠️ **Validation**: Slightly relaxed (edge case)

**Overall:** V2 is **production-ready** with minor non-functional differences from the architecture spec.

---

## 2. Target State (Architecture Specs)

The target state is defined by `docs/architecture/to-be/08-answer-parsing-architecture.md`:

### 2.1 Pattern Hierarchy

| Level | Name | Confidence | Patterns |
|-------|------|------------|----------|
| 1 | Explicit | `clear` | 2 patterns |
| 2 | Context | `clear` | 5 patterns |
| 3 | Structural | `clear` | 6 patterns |
| 4 | Fallback | `low_confidence` | 1 pattern |

**Total:** 14 patterns across 4 levels

### 2.2 Confidence Levels

| Level | Review Required | Automation Safety |
|-------|-----------------|-------------------|
| `clear` | No | Safe |
| `ambiguous` | Yes | Unsafe |
| `no_answer` | Yes | Unsafe |
| `low_confidence` | Yes | Unsafe |

### 2.3 Article Filtering

- **Noun List:** 24 nouns (deduplicated)
- **Pattern:** Portuguese/Spanish article "A" detection
- **Behavior:** Filter article "A", keep answer "A"

### 2.4 needs_review Calculation

```python
needs_review = (
    parse_confidence in ('ambiguous', 'no_answer', 'low_confidence')
    OR selected_answer IS NULL
)
```

**Location:** ResultWriter (calculated before INSERT)

---

## 3. Gap Analysis

### 3.1 Functional Gaps

| Gap | Current State | Target State | Severity | Action Required |
|-----|---------------|--------------|----------|-----------------|
| Pattern hierarchy | 4 levels | 4 levels | None | ✅ No action |
| Pattern definitions | 14 patterns | 14 patterns | None | ✅ No action |
| Confidence levels | 4 values | 4 values | None | ✅ No action |
| Article filtering | 24 nouns | 24 nouns | None | ✅ No action |
| Ambiguity detection | Implemented | Implemented | None | ✅ No action |

**Summary:** ✅ **No functional gaps**

---

### 3.2 Non-Functional Gaps

| Gap | Current State | Target State | Severity | Action Required |
|-----|---------------|--------------|----------|-----------------|
| Logging | Not implemented | Optional logging recommended | Low | Consider adding |
| Validation | Relaxed (no clear/NULL check) | Strict (clear requires answer) | Very Low | Consider adding |
| Convenience function | Not present | Optional | Low | No action needed |
| Reasoning extraction | Not present | Optional | None | No action needed |

**Summary:** ⚠️ **Minor non-functional gaps** (no blockers)

---

## 4. Implementation Considerations

### 4.1 Current Implementation Strengths

1. **Pattern Matching**: All 14 patterns implemented correctly
2. **Confidence Classification**: All 4 levels working correctly
3. **Article Filtering**: Portuguese/Spanish "A" filtering works
4. **Ambiguity Detection**: Multiple letters trigger `ambiguous`
5. **Pattern Compilation**: Efficient compilation at initialization
6. **Case Insensitivity**: `re.IGNORECASE` flag used correctly
7. **Multi-line Support**: `re.MULTILINE` flag used correctly

### 4.2 Areas for Improvement

#### 4.2.1 Logging (Optional)

**Current:** No logging

**Recommendation:** Add optional debug logging for troubleshooting

```python
import logging

logger = logging.getLogger(__name__)

def parse(self, response_text: str) -> ParsedAnswer:
    if not response_text or not response_text.strip():
        logger.debug("Empty response text")
        return ParsedAnswer(confidence="no_answer")
    
    # ... after finding matches
    logger.debug(f"All letter matches: {all_matches}, filtered: {filtered_matches}")
    
    # ... after ambiguity check
    if len(unique_letters) > 1:
        logger.debug(f"Ambiguous response: multiple letters {unique_letters}")
        return ParsedAnswer(confidence="ambiguous", ...)
    
    # ... after pattern match
    logger.debug(f"Matched {pattern_type} pattern: {pattern.pattern}")
```

**Benefit:** Easier debugging of parsing issues

---

#### 4.2.2 Validation (Optional)

**Current:** No validation for `clear` confidence requiring non-NULL answer

**Recommendation:** Add validation in `__post_init__`

```python
def __post_init__(self) -> None:
    """Validate confidence level."""
    valid_confidence = {"clear", "ambiguous", "no_answer", "low_confidence"}
    if self.confidence not in valid_confidence:
        raise ValueError(f"Invalid confidence level: {self.confidence}")
    
    # Add this validation
    if self.confidence == "clear" and self.answer is None:
        raise ValueError("Clear confidence requires a valid answer")
```

**Benefit:** Catches invariant violations early

---

#### 4.2.3 Convenience Function (Optional)

**Current:** No convenience function

**Recommendation:** Add optional convenience function

```python
def parse_answer(response_text: str) -> ParsedAnswer:
    """Parse an LLM response and extract the answer letter.
    
    Convenience function for simple usage without creating a parser instance.
    
    Args:
        response_text: Full text response from the LLM.
    
    Returns:
        ParsedAnswer object with extracted answer and confidence.
    
    Example:
        >>> result = parse_answer("A resposta correta é B)")
        >>> print(result.answer)
        B
        >>> print(result.confidence)
        clear
    """
    parser = AnswerParser()
    return parser.parse(response_text)
```

**Benefit:** Simpler API for one-off parsing

---

## 5. Migration Path

### 5.1 No Breaking Changes Required

**Assessment:** V2 is already aligned with the TO-BE architecture.

**Reason:** The architecture spec was written to match the V2 implementation (which has V1 parity).

### 5.2 Optional Enhancements

If desired, the following enhancements can be made:

#### Phase 1: Add Logging (Low Priority)

```python
# Add to src/core/answer_parser.py

import logging

logger = logging.getLogger(__name__)

class AnswerParser:
    def parse(self, response_text: str) -> ParsedAnswer:
        if not response_text or not response_text.strip():
            logger.debug("Empty response text")
            return ParsedAnswer(confidence="no_answer")
        
        # ... rest of implementation with logging
```

**Testing:**
- Verify logging doesn't affect parsing output
- Verify logging can be configured independently

---

#### Phase 2: Add Validation (Very Low Priority)

```python
# Add to src/core/answer_parser.py

@dataclass
class ParsedAnswer:
    def __post_init__(self) -> None:
        valid_confidence = {"clear", "ambiguous", "no_answer", "low_confidence"}
        if self.confidence not in valid_confidence:
            raise ValueError(f"Invalid confidence level: {self.confidence}")
        
        # Add this validation
        if self.confidence == "clear" and self.answer is None:
            raise ValueError("Clear confidence requires a valid answer")
```

**Testing:**
- Verify validation catches invalid states
- Verify normal flow doesn't trigger validation errors

---

#### Phase 3: Add Convenience Function (Low Priority)

```python
# Add to src/core/answer_parser.py

def parse_answer(response_text: str) -> ParsedAnswer:
    """Convenience function for simple usage."""
    parser = AnswerParser()
    return parser.parse(response_text)
```

**Testing:**
- Verify function returns same result as class instantiation
- Update any internal callers if desired

---

## 6. Validation Criteria

### 6.1 Functional Validation

Use these criteria to validate the Answer Parser:

- [x] **Pattern Hierarchy**: 4 levels (explicit, context, structural, fallback)
- [x] **Pattern Count**: 14 patterns total (2 + 5 + 6 + 1)
- [x] **Confidence Levels**: 4 values (clear, ambiguous, no_answer, low_confidence)
- [x] **Article Filtering**: Portuguese/Spanish "A" filtered correctly
- [x] **Ambiguity Detection**: Multiple different letters → `ambiguous`
- [x] **Case Insensitivity**: `resposta: b` → answer=`B`
- [x] **Empty Response**: Empty string → `no_answer`
- [x] **Repeated Letter**: `A resposta é A. Definitivamente A.` → `clear`, answer=`A`

### 6.2 Integration Validation

- [x] **ExecutionEngine Integration**: Parser returns `ParsedAnswer` correctly
- [x] **ResultWriter Integration**: `parse_confidence` and `selected_answer` passed correctly
- [x] **needs_review Calculation**: ResultWriter calculates correctly
- [x] **Database Persistence**: All fields persisted to `responses` table

### 6.3 Test Cases

#### Explicit Patterns

```python
assert parser.parse("Resposta: B").answer == "B"
assert parser.parse("Resposta: B").confidence == "clear"
assert parser.parse("Answer: C").answer == "C"
assert parser.parse("Answer: C").confidence == "clear"
assert parser.parse("A correta é D").answer == "D"
assert parser.parse("A correta é D").confidence == "clear"
assert parser.parse("A alternativa correta é A").answer == "A"
assert parser.parse("A alternativa correta é A").confidence == "clear"
```

#### Context Patterns

```python
assert parser.parse("A resposta é B").answer == "B"
assert parser.parse("A resposta é B").confidence == "clear"
assert parser.parse("A resposta correta é C").answer == "C"
assert parser.parse("The correct answer is D").answer == "D"
assert parser.parse("A opção D está correta").answer == "D"
assert parser.parse("A letra A").answer == "A"
assert parser.parse("alternativa B").answer == "B"
```

#### Structural Patterns

```python
assert parser.parse("**C**").answer == "C"
assert parser.parse("**C**").confidence == "clear"
assert parser.parse("D: Explicação...").answer == "D"
assert parser.parse("A) Resposta...").answer == "A"
assert parser.parse("(B) Alternativa...").answer == "B"
assert parser.parse("concluo que: A").answer == "A"
assert parser.parse("alternativa B)").answer == "B"
```

#### Fallback Pattern

```python
assert parser.parse("Eu acho que é B").answer == "B"
assert parser.parse("Eu acho que é B").confidence == "low_confidence"
```

#### Article Filtering

```python
assert parser.parse("A resposta é B").answer == "B"  # Article "A" filtered
assert parser.parse("A alternativa correta é A").answer == "A"  # Article "A" filtered, answer kept
assert parser.parse("A opção A está correta").answer == "A"  # Article "A" filtered, answer kept
```

#### Ambiguity Detection

```python
result = parser.parse("A ou B estão corretas")
assert result.confidence == "ambiguous"
assert result.answer is None
```

#### Empty Response

```python
result = parser.parse("")
assert result.confidence == "no_answer"
assert result.answer is None
```

#### Repeated Letter

```python
result = parser.parse("A resposta é A. Definitivamente A.")
assert result.confidence == "clear"
assert result.answer == "A"
```

#### needs_review Calculation

```python
# Clear confidence → needs_review = FALSE
assert calculate_needs_review("clear", "A") == False

# Ambiguous confidence → needs_review = TRUE
assert calculate_needs_review("ambiguous", None) == True

# No_answer confidence → needs_review = TRUE
assert calculate_needs_review("no_answer", None) == True

# Low_confidence → needs_review = TRUE
assert calculate_needs_review("low_confidence", "B") == True

# Clear with NULL answer → needs_review = TRUE (edge case)
assert calculate_needs_review("clear", None) == True
```

---

## 7. Monitoring and Observability

### 7.1 Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| `parse_latency_ms` | Time to parse a response | < 10ms |
| `confidence_distribution` | Count by confidence level | Majority `clear` |
| `ambiguity_rate` | Percentage of ambiguous responses | < 5% |
| `no_answer_rate` | Percentage of no_answer responses | < 5% |
| `low_confidence_rate` | Percentage of low_confidence responses | < 10% |
| `article_filter_rate` | Percentage of articles filtered | Varies by language |

### 7.2 Logging Recommendations

If logging is added, log these events:

```python
# Debug level
logger.debug(f"Parsing response: {response_text[:100]}...")
logger.debug(f"All letter matches: {all_matches}")
logger.debug(f"Filtered matches: {filtered_matches}")
logger.debug(f"Matched {pattern_type} pattern: {pattern.pattern}")

# Info level
logger.info(f"Parsed answer: {result.answer}, confidence: {result.confidence}")

# Warning level
logger.warning(f"Ambiguous response detected: {unique_letters}")
logger.warning(f"No answer pattern found in response")
```

### 7.3 Alerting

Consider alerting on:

- `ambiguity_rate` > 10% (may indicate LLM quality issues)
- `no_answer_rate` > 10% (may indicate prompt issues)
- `low_confidence_rate` > 20% (may indicate pattern coverage gaps)

---

## 8. Maintenance Guidelines

### 8.1 Adding New Patterns

When adding new patterns:

1. **Determine priority level** (explicit, context, structural, fallback)
2. **Add pattern to appropriate list** (EXPLICIT_PATTERNS, CONTEXT_PATTERNS, etc.)
3. **Update documentation** (this document and architecture spec)
4. **Add test cases** for new patterns
5. **Monitor confidence distribution** after deployment

**Example:**
```python
# Adding a new context pattern
CONTEXT_PATTERNS = [
    # ... existing patterns
    (r"a\s+alternativa\s+correta\s+é\s*([A-D])", True, "clear"),  # New pattern
]
```

### 8.2 Modifying Article Filter

When modifying the article filter:

1. **Identify new nouns** to add to the filter list
2. **Update article_pattern** in `_filter_ambiguous_articles`
3. **Test with examples** containing new nouns
4. **Verify no false negatives** (valid answers not filtered)

**Example:**
```python
# Adding "única" to the filter (already present, but as example)
article_pattern = re.compile(
    r'\b[Aa]\s+(?:...|única|...)\b',
    re.IGNORECASE
)
```

### 8.3 Handling Edge Cases

When encountering edge cases:

1. **Document the edge case** (input, expected output, actual output)
2. **Determine root cause** (pattern gap, article filter issue, etc.)
3. **Propose fix** (new pattern, pattern modification, filter update)
4. **Test fix** with edge case and regression tests
5. **Update documentation** with new edge case

---

## 9. Summary

### 9.1 Current State

- ✅ V2 Answer Parser is **production-ready**
- ✅ **V1 parity confirmed** (Phase 3 validation)
- ✅ **All functional requirements met**
- ⚠️ **Minor non-functional gaps** (logging, validation, convenience function)

### 9.2 Recommended Actions

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| None | Core functionality | N/A | Already complete |
| Low | Add optional logging | Low | Easier debugging |
| Very Low | Add validation | Very Low | Catch invariant violations |
| Low | Add convenience function | Very Low | Simpler API |

### 9.3 Migration Path

**No breaking changes required.** V2 is already aligned with the TO-BE architecture.

Optional enhancements can be added incrementally without affecting existing functionality.

### 9.4 Success Criteria

- [x] All 14 patterns working correctly
- [x] All 4 confidence levels classified correctly
- [x] Article filtering working correctly
- [x] Ambiguity detection working correctly
- [x] Integration with ExecutionEngine working
- [x] Integration with ResultWriter working
- [x] needs_review calculation correct
- [x] All test cases passing

---

**Related Documents:**
- `docs/architecture/to-be/08-answer-parsing-architecture.md` — Architecture & Contracts
- `docs/architecture/v2-current/08-answer-parsing.md` — V2 Current State
- `docs/architecture/gap-reports/08-answer-parsing-gap.md` — Gap Report
- `docs/architecture/contracts/result-writer.md` — Review fields contract
