# Answer Parsing Architecture & Contracts

**Document Type:** TO-BE Architecture Specification  
**Version:** 1.0  
**Date:** 2026-03-29  
**Phase:** 10/12 — Answer Parsing Domain Documentation  
**Status:** ✅ **AUTHORITATIVE** — Source of truth for answer parsing  

---

## 1. Overview

### 1.1 Purpose

This document defines the **authoritative architecture and contracts** for the Answer Parsing domain in the Benchmark LLM system. It specifies how LLM responses are parsed to extract selected answers (A, B, C, D) and classify confidence levels for manual review routing.

### 1.2 Scope

This document covers:
- Parsing philosophy and design principles
- Pattern hierarchy contract (4 levels)
- Confidence level contract (4 values)
- Answer extraction rules
- Article filtering rules
- `needs_review` calculation
- Integration contracts with ExecutionEngine and ResultWriter

### 1.3 Out of Scope

- ExecutionEngine implementation details
- ResultWriter persistence logic
- Database schema definitions
- CLI interface specifications

---

## 2. Parsing Philosophy

### 2.1 Hierarchical Matching

Answer parsing uses a **hierarchical pattern matching** approach where patterns are evaluated in priority order from highest to lowest confidence:

```
Priority 1: Explicit Patterns (highest confidence)
    ↓ [no match]
Priority 2: Context Patterns
    ↓ [no match]
Priority 3: Structural Patterns
    ↓ [no match]
Priority 4: Fallback Patterns (lowest confidence)
```

**Rationale:**
- Higher-priority patterns represent more intentional answer declarations
- Lower-priority patterns capture incidental letter mentions
- Hierarchy minimizes false positives from casual letter mentions

### 2.2 Confidence-Based Routing

Parsed answers are classified into **four confidence levels** that determine whether manual review is required:

| Confidence | Review Required | Automation Safety |
|------------|-----------------|-------------------|
| `clear` | No | Safe for automatic processing |
| `ambiguous` | Yes | Requires human judgment |
| `no_answer` | Yes | Requires human judgment |
| `low_confidence` | Yes | Requires human judgment |

**Rationale:**
- Only `clear` confidence answers are safe for automatic processing
- All other levels indicate uncertainty requiring human review
- This minimizes incorrect answer recording while maximizing automation

### 2.3 Ambiguity Detection

The parser detects **ambiguity** when multiple **different** letters are found in a response:

**Examples:**
- ✅ `A resposta é B. Definitivamente B.` → Not ambiguous (same letter repeated)
- ❌ `A ou B estão corretas.` → Ambiguous (different letters)
- ❌ `Alternativas A e C.` → Ambiguous (different letters)

**Rationale:**
- LLMs sometimes mention multiple options in explanations
- Ambiguity detection prevents incorrect answer extraction
- Ambiguous responses require human review to determine intent

### 2.4 Article Filtering

The parser filters **Portuguese/Spanish article "A"** to prevent false positives:

**Examples:**
- `A resposta é B` → Article "A" filtered, answer "B" extracted
- `A alternativa correta é A` → Article "A" filtered, answer "A" extracted
- `A opção A está correta` → Article "A" filtered, answer "A" extracted

**Rationale:**
- Portuguese and Spanish use "A" as a definite article
- Without filtering, `A resposta` would incorrectly match answer "A"
- Context-aware filtering distinguishes articles from answers

---

## 3. Pattern Contract (4 Levels)

### 3.1 Level 1: Explicit Patterns

**Priority:** Highest  
**Confidence:** `clear`  
**Purpose:** Direct, unambiguous answer declarations

#### Pattern Definitions

| ID | Pattern | Regex | Examples |
|----|---------|-------|----------|
| E1 | Colon-separated answer | `(?:resposta|answer)\s*:\s*([A-D])` | `Resposta: B`, `Answer: C` |
| E2 | Correct answer declaration | `(?:alternativa\s+)?correta\s*(?:é|is)\s*([A-D])` | `A correta é D`, `alternativa correta é A` |

#### Matching Rules

- Case-insensitive matching (`re.IGNORECASE`)
- Multi-line support (`re.MULTILINE`)
- Bilingual (Portuguese/English)
- Optional "alternativa" prefix for E2
- Capture group extracts the letter

#### Acceptance Criteria

- ✅ `Resposta: B` → Match E1, answer=`B`, confidence=`clear`
- ✅ `Answer: C` → Match E1, answer=`C`, confidence=`clear`
- ✅ `A correta é D` → Match E2, answer=`D`, confidence=`clear`
- ✅ `A alternativa correta é A` → Match E2, answer=`A`, confidence=`clear`
- ✅ `resposta: b` → Match E1, answer=`B` (uppercase), confidence=`clear`

---

### 3.2 Level 2: Context Patterns

**Priority:** High  
**Confidence:** `clear`  
**Purpose:** Answer mentions within contextual phrases

#### Pattern Definitions

| ID | Pattern | Regex | Examples |
|----|---------|-------|----------|
| C1 | "The answer is" phrase | `a\s+resposta\s+(?:correta\s+)?(?:é|is)\s*([A-D])` | `A resposta é B`, `A resposta correta é C` |
| C2 | English equivalent | `the\s+correct\s+answer\s+(?:is)?\s*([A-D])` | `The correct answer is D` |
| C3 | Option reference | `(?:opção|option)\s*([A-D])` | `A opção D`, `Option A` |
| C4 | Letter reference | `(?:letra|letter)\s*([A-D])` | `A letra A`, `Letter B` |
| C5 | Alternative reference | `alternativa\s+([A-D])\b` | `alternativa B`, `alternativa C` |

#### Matching Rules

- Case-insensitive matching (`re.IGNORECASE`)
- Multi-line support (`re.MULTILINE`)
- Bilingual (Portuguese/English)
- Word boundary enforcement on C5
- Optional "correta" modifier in C1
- Optional "is" in C1 and C2

#### Acceptance Criteria

- ✅ `A resposta é B` → Match C1, answer=`B`, confidence=`clear`
- ✅ `A resposta correta é C` → Match C1, answer=`C`, confidence=`clear`
- ✅ `The correct answer is D` → Match C2, answer=`D`, confidence=`clear`
- ✅ `A opção D está correta` → Match C3, answer=`D`, confidence=`clear`
- ✅ `A letra A` → Match C4, answer=`A`, confidence=`clear`
- ✅ `alternativa B` → Match C5, answer=`B`, confidence=`clear`

---

### 3.3 Level 3: Structural Patterns

**Priority:** Medium  
**Confidence:** `clear`  
**Purpose:** Answer formatting markers and structural indicators

#### Pattern Definitions

| ID | Pattern | Regex | Examples |
|----|---------|-------|----------|
| S1 | Markdown bold (line start) | `^\s*\*\*([A-D])\*\*` | `**C**`, `**D**` |
| S2 | Letter colon (line start) | `^\s*([A-D])\s*:` | `D: Explicação...` |
| S3 | Letter parenthesis (line start) | `^\s*([A-D])\s*\)` | `A) Resposta...` |
| S4 | Parenthesized letter (line start) | `^\s*\(\s*([A-D])\s*\)` | `(B) Alternativa...` |
| S5 | Letter colon (anywhere) | `\b([A-D])\b\s*:` | `concluo que: A` |
| S6 | Letter parenthesis (anywhere) | `\b([A-D])\b\s*\)` | `alternativa B)` |

#### Matching Rules

- Case-insensitive matching (`re.IGNORECASE`)
- Multi-line support (`re.MULTILINE`)
- S1-S4: Line start anchoring (`^`)
- S5-S6: Word boundary matching (`\b`)
- Whitespace flexibility (`\s*`)

#### Acceptance Criteria

- ✅ `**C**` → Match S1, answer=`C`, confidence=`clear`
- ✅ `D: Explicação...` → Match S2, answer=`D`, confidence=`clear`
- ✅ `A) Resposta...` → Match S3, answer=`A`, confidence=`clear`
- ✅ `(B) Alternativa...` → Match S4, answer=`B`, confidence=`clear`
- ✅ `concluo que: A` → Match S5, answer=`A`, confidence=`clear`
- ✅ `alternativa B)` → Match S6, answer=`B`, confidence=`clear`

---

### 3.4 Level 4: Fallback Patterns

**Priority:** Lowest  
**Confidence:** `low_confidence`  
**Purpose:** Last-resort isolated letter detection

#### Pattern Definitions

| ID | Pattern | Regex | Examples |
|----|---------|-------|----------|
| F1 | Any isolated letter | `\b([A-D])\b` | `Eu acho que é B` |

#### Matching Rules

- Case-insensitive matching (`re.IGNORECASE`)
- Word boundary enforcement (`\b`)
- First match used if multiple found
- Subject to article filtering

#### Acceptance Criteria

- ✅ `Eu acho que é B` → Match F1, answer=`B`, confidence=`low_confidence`
- ✅ `Estudo ABC (2020)` → Match F1, answer=`C`, confidence=`low_confidence` (if "C" is only match)
- ⚠️ `A resposta` → No match (article "A" filtered)

---

## 4. Confidence Contract (4 Values)

### 4.1 Confidence Level Definitions

| Level | Condition | Review Required | Automation Safety |
|-------|-----------|-----------------|-------------------|
| `clear` | Single match from explicit/context/structural patterns | No | Safe |
| `ambiguous` | Multiple different letters detected | Yes | Unsafe |
| `no_answer` | No patterns matched | Yes | Unsafe |
| `low_confidence` | Only fallback pattern matched | Yes | Unsafe |

### 4.2 Validation Rules

**Invariant 1:** Confidence must be one of four values
```python
valid_confidence = {"clear", "ambiguous", "no_answer", "low_confidence"}
assert confidence in valid_confidence
```

**Invariant 2:** `clear` confidence implies non-NULL answer
```python
if confidence == "clear":
    assert answer is not None
    assert answer in ("A", "B", "C", "D")
```

**Invariant 3:** `ambiguous` and `no_answer` imply NULL answer
```python
if confidence in ("ambiguous", "no_answer"):
    assert answer is None
```

### 4.3 Confidence Assignment Logic

```
IF multiple different letters detected:
    confidence = "ambiguous"
    answer = NULL

ELSE IF explicit pattern matched:
    confidence = "clear"
    answer = matched_letter

ELSE IF context pattern matched:
    confidence = "clear"
    answer = matched_letter

ELSE IF structural pattern matched:
    confidence = "clear"
    answer = matched_letter

ELSE IF fallback pattern matched (after article filtering):
    confidence = "low_confidence"
    answer = first_matched_letter

ELSE:
    confidence = "no_answer"
    answer = NULL
```

---

## 5. Answer Extraction Rules

### 5.1 Extraction Flow

```
┌─────────────────────────────────────────┐
│ 1. Input Validation                     │
│    - Empty response? → no_answer        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│ 2. Find All Letter Matches              │
│    - Apply fallback pattern             │
│    - Convert to uppercase               │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│ 3. Filter Articles                      │
│    - Detect Portuguese/Spanish "A"      │
│    - Remove article matches             │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│ 4. Check Ambiguity                      │
│    - >1 unique letter? → ambiguous      │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
   [Ambiguous]         [Single/None]
        │                   │
        │         ┌─────────▼─────────┐
        │         │ 5. Try Patterns   │
        │         │    - Explicit     │
        │         │    - Context      │
        │         │    - Structural   │
        │         └─────────┬─────────┘
        │                   │
        │         ┌─────────┴─────────┐
        │         │                   │
        │    [Match Found]      [No Match]
        │         │                   │
        │         │         ┌─────────▼─────────┐
        │         │         │ 6. Fallback       │
        │         │         │    - Has matches? │
        │         │         └─────────┬─────────┘
        │         │                   │
        │         │         ┌─────────┴─────────┐
        │         │         │                   │
        │         │    [Yes: low_conf]    [No: no_answer]
```

### 5.2 Pattern Priority Rules

1. **Explicit patterns evaluated first** — Highest confidence declarations
2. **Context patterns evaluated second** — Clear contextual mentions
3. **Structural patterns evaluated third** — Formatting-based extraction
4. **Fallback patterns evaluated last** — Last-resort extraction

**Rule:** First matching pattern determines confidence level

### 5.3 Letter Extraction Rules

1. **Capture group extraction** — Use regex capture group if present
2. **Uppercase normalization** — Convert all letters to uppercase
3. **Validation** — Ensure letter is in ("A", "B", "C", "D")

### 5.4 Repeated Letter Rules

**Rule:** Repeated mentions of the **same letter** do not trigger ambiguity

**Examples:**
- ✅ `A resposta é A. Definitivamente A.` → `clear`, answer=`A`
- ✅ `**B** é a correta. Alternativa B.` → `clear`, answer=`B`

**Rationale:** Repetition reinforces intent, doesn't create ambiguity

---

## 6. Article Filtering Rules

### 6.1 Problem Statement

The letter "A" as a standalone word is often a **Portuguese/Spanish definite article**, not an answer:

- `A resposta` → article, not answer "A"
- `A alternativa` → article, not answer "A"
- `A opção` → article, not answer "A"

### 6.2 Article Detection Pattern

```python
article_pattern = re.compile(
    r'\b[Aa]\s+(?:alternativa|opção|opcoes|resposta|letra|questão|questao|correct|correcta|correta|melhor|mais|única|unica|primeira|segunda|terceira|última|ultima|explicação|explicacao|capital|cidade|pais|país|regiao|região|parte|maioria)\b',
    re.IGNORECASE
)
```

### 6.3 Noun List (24 nouns)

| Category | Nouns |
|----------|-------|
| Answer-related | `alternativa`, `opção`, `opcoes`, `resposta`, `letra`, `questão`, `questao` |
| Correctness | `correct`, `correcta`, `correta` |
| Superlative | `melhor`, `mais`, `única`, `unica`, `primeira`, `segunda`, `terceira`, `última`, `ultima` |
| Explanation | `explicação`, `explicacao` |
| Content | `capital`, `cidade`, `pais`, `país`, `regiao`, `região`, `parte`, `maioria` |

### 6.4 Filtering Logic

```python
def _filter_ambiguous_articles(text: str, matches: list[str]) -> list[str]:
    # Find all article positions
    article_matches = list(article_pattern.finditer(text))
    article_positions = set(match.start() for match in article_matches)
    
    # Filter matches
    filtered = []
    for match in fallback_pattern.finditer(text):
        letter = match.group(1).upper()
        # Only filter 'A', and only if it's at an article position
        if letter == "A" and match.start() in article_positions:
            continue  # Skip this 'A' - it's likely an article
        filtered.append(letter)
    
    return filtered
```

### 6.5 Filtering Examples

| Input | All Matches | Filtered Matches | Explanation |
|-------|-------------|------------------|-------------|
| `A resposta é B` | `['A', 'B']` | `['B']` | Article "A" filtered |
| `A alternativa correta é A` | `['A', 'A']` | `['A']` | Article "A" filtered, answer "A" kept |
| `A opção A está correta` | `['A', 'A']` | `['A']` | Article "A" filtered, answer "A" kept |
| `Resposta: A` | `['A']` | `['A']` | No article, answer "A" kept |

---

## 7. needs_review Calculation

### 7.1 Contract

The `needs_review` flag is **calculated by ResultWriter** based on `parse_confidence` and `selected_answer` from ExecutionEngine.

### 7.2 Calculation Formula

```python
needs_review = (
    parse_confidence in ('ambiguous', 'no_answer', 'low_confidence')
    OR selected_answer IS NULL
)
```

### 7.3 Truth Table

| `parse_confidence` | `selected_answer` | `needs_review` |
|--------------------|-------------------|----------------|
| `'clear'` | não-NULL | FALSE |
| `'clear'` | NULL | TRUE |
| `'ambiguous'` | qualquer | TRUE |
| `'no_answer'` | qualquer | TRUE |
| `'low_confidence'` | qualquer | TRUE |

### 7.4 Integration Contract

**ExecutionEngine → ResultWriter:**
- `parse_confidence`: Confidence level from AnswerParser
- `selected_answer`: Extracted letter (A, B, C, D) or NULL

**ResultWriter:**
- Calculates `needs_review` before INSERT
- Does not modify `parse_confidence` or `selected_answer`
- Persists all three fields to `responses` table

### 7.5 Manual Review Workflow

```
┌─────────────────────────────────────┐
│ ExecutionEngine                     │
│  - Parses response                  │
│  - Returns (parse_confidence,       │
│             selected_answer)        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ ResultWriter                        │
│  - Calculates needs_review          │
│  - Persists to responses table      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ Reviewer (Human)                    │
│  - Queries: WHERE needs_review=TRUE │
│  - Reviews and sets manual_answer   │
└─────────────────────────────────────┘
```

---

## 8. Data Structures

### 8.1 ParsedAnswer

```python
@dataclass
class ParsedAnswer:
    """Result of parsing an LLM response.

    Attributes:
        answer: The extracted answer letter (A, B, C, or D), or None if not found.
        confidence: Confidence level indicating if manual review is needed.
            - "clear": Single high/medium confidence match, safe to use automatically.
            - "ambiguous": Multiple different letters found, requires manual review.
            - "no_answer": No letter patterns found, requires manual review.
            - "low_confidence": Only fallback pattern matched, requires manual review.
        raw_matches: List of all letter matches found in the response text.
        reasoning_text: Extracted reasoning text if present (optional).
    """

    answer: Optional[str] = None
    confidence: str = "no_answer"
    raw_matches: list[str] = field(default_factory=list)
    reasoning_text: Optional[str] = None
```

### 8.2 Field Specifications

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `answer` | `Optional[str]` | No | Extracted letter (A, B, C, D) or None |
| `confidence` | `str` | Yes | Confidence level (default: "no_answer") |
| `raw_matches` | `list[str]` | Yes | All letter matches found (default: []) |
| `reasoning_text` | `Optional[str]` | No | Extracted reasoning text (optional) |

### 8.3 Invariants

1. `confidence` must be one of: `clear`, `ambiguous`, `no_answer`, `low_confidence`
2. If `confidence == "clear"`, then `answer` must be non-NULL and in ("A", "B", "C", "D")
3. If `confidence in ("ambiguous", "no_answer")`, then `answer` should be NULL
4. `raw_matches` contains uppercase letters only

---

## 9. Integration Contracts

### 9.1 ExecutionEngine → AnswerParser

**Contract:**
```python
parser = AnswerParser()
result = parser.parse(response_text)
```

**Input:**
- `response_text`: Full LLM response string

**Output:**
- `ParsedAnswer` object with extracted answer and confidence

### 9.2 ExecutionEngine → ResultWriter

**Contract:**
```python
result_writer.write_response(
    run_id=run_id,
    variant_id=variant_id,
    snapshot_id=snapshot_id,
    parse_confidence=parsed_answer.confidence,
    selected_answer=parsed_answer.answer,
    # ... other fields
)
```

**Input:**
- `parse_confidence`: From `ParsedAnswer.confidence`
- `selected_answer`: From `ParsedAnswer.answer`

**Output:**
- `needs_review`: Calculated by ResultWriter

### 9.3 ResultWriter → Database

**Contract:**
```sql
INSERT INTO responses (
    run_id, variant_id, snapshot_id,
    parse_confidence, selected_answer, needs_review,
    ...
) VALUES (
    :run_id, :variant_id, :snapshot_id,
    :parse_confidence, :selected_answer, :needs_review,
    ...
)
```

**Fields:**
- `parse_confidence`: From ExecutionEngine
- `selected_answer`: From ExecutionEngine
- `needs_review`: Calculated by ResultWriter

---

## 10. Error Handling

### 10.1 Empty Response

**Condition:** Response text is empty or whitespace-only

**Behavior:**
```python
if not response_text or not response_text.strip():
    return ParsedAnswer(confidence="no_answer")
```

**Result:** `confidence="no_answer"`, `answer=None`, `needs_review=TRUE`

### 10.2 Invalid Confidence

**Condition:** Confidence level is not one of four valid values

**Behavior:**
```python
valid_confidence = {"clear", "ambiguous", "no_answer", "low_confidence"}
if confidence not in valid_confidence:
    raise ValueError(f"Invalid confidence level: {confidence}")
```

**Result:** `ValueError` raised

### 10.3 Clear Confidence Without Answer

**Condition:** `confidence="clear"` but `answer=None`

**Behavior (recommended):**
```python
if confidence == "clear" and answer is None:
    raise ValueError("Clear confidence requires a valid answer")
```

**Result:** `ValueError` raised (invariant violation)

---

## 11. Quality Attributes

### 11.1 Determinism

**Requirement:** Same input → same output

**Verification:**
- Pattern matching is deterministic (no randomization)
- Confidence assignment is deterministic
- Article filtering is deterministic

### 11.2 Idempotency

**Requirement:** Multiple parses of same input → same result

**Verification:**
- No state is maintained between parse calls
- Patterns are compiled once at initialization
- Each parse is independent

### 11.3 Performance

**Requirement:** Parse latency < 10ms per response

**Optimization:**
- Patterns compiled at initialization (not per-parse)
- Short-circuit evaluation (first match wins)
- Efficient regex (compiled patterns)

### 11.4 Maintainability

**Requirement:** Pattern changes should be localized

**Design:**
- Patterns defined as class constants
- Pattern hierarchy is explicit
- Matching logic is separated from extraction logic

---

## 12. Summary

The Answer Parsing architecture defines:

1. **4-level pattern hierarchy**: Explicit → Context → Structural → Fallback
2. **4 confidence levels**: `clear`, `ambiguous`, `no_answer`, `low_confidence`
3. **Article filtering**: Portuguese/Spanish "A" detection and removal
4. **Ambiguity detection**: Multiple different letters trigger review
5. **Hierarchical flow**: Priority-based pattern evaluation
6. **needs_review calculation**: Derived from confidence and answer

**Key Invariants:**
- Only `clear` confidence is safe for automatic processing
- All other confidence levels require manual review
- Article "A" is filtered to prevent false positives
- Repeated same letter does not trigger ambiguity

---

**Related Documents:**
- `docs/architecture/contracts/result-writer.md` — Review fields contract
- `docs/architecture/contracts/domain-review-contract.md` — needs_review calculation
- `docs/architecture/v2-adaptation/08-answer-parsing-adaptation.md` — V2 Adaptation Guide
