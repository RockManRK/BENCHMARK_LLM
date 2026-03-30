# Answer Parsing — V1 Analysis

**Document Type:** Legacy Analysis (Read-Only)  
**Source:** `src_legacy/core/answer_parser.py`  
**Date:** 2026-03-29  
**Phase:** 10/12 — Answer Parsing Domain Documentation  

---

## 1. Overview

The V1 Answer Parser implements a **hierarchical pattern matching strategy** to extract answer letters (A, B, C, D) from LLM response text. The parser classifies confidence levels to route responses for manual review when necessary.

### Core Philosophy

- **Hierarchical matching**: Patterns are evaluated in priority order (explicit → context → structural → fallback)
- **Confidence-based routing**: Low-confidence matches are flagged for human review
- **Article filtering**: Portuguese/Spanish article "A" is filtered to prevent false positives
- **Ambiguity detection**: Multiple different letters trigger ambiguous classification

---

## 2. Pattern Hierarchy (4 Levels)

The V1 parser uses **four levels** of pattern matching, from highest to lowest priority:

### Level 1: Explicit Patterns (Highest Priority)

**Confidence:** `clear`

**Purpose:** Direct, unambiguous answer declarations

| Pattern | Example | Description |
|---------|---------|-------------|
| `(?:resposta|answer)\s*:\s*([A-D])` | `Resposta: B`, `Answer: C` | Colon-separated answer |
| `(?:alternativa\s+)?correta\s*(?:é|is)\s*([A-D])` | `A correta é D`, `alternativa correta é A` | "Correct answer is" declaration |

**Characteristics:**
- Highest confidence assignment
- Bilingual support (Portuguese/English)
- Optional "alternativa" prefix
- Case-insensitive matching

---

### Level 2: Context Patterns (Medium Priority)

**Confidence:** `clear`

**Purpose:** Answer mentions within contextual phrases

| Pattern | Example | Description |
|---------|---------|-------------|
| `a\s+resposta\s+(?:correta\s+)?(?:é|is)\s*([A-D])` | `A resposta é B`, `A resposta correta é C` | "The answer is" phrase |
| `the\s+correct\s+answer\s+(?:is)?\s*([A-D])` | `The correct answer is D` | English equivalent |
| `(?:opção|option)\s*([A-D])` | `A opção D`, `Option A` | Option reference |
| `(?:letra|letter)\s*([A-D])` | `A letra A`, `Letter B` | Letter reference |
| `alternativa\s+([A-D])\b` | `alternativa B`, `alternativa C` | Alternative reference |

**Characteristics:**
- Clear confidence (same as explicit)
- Bilingual support
- Word boundary enforcement on last pattern

---

### Level 3: Structural Patterns (Medium-Low Priority)

**Confidence:** `clear`

**Purpose:** Answer formatting markers and structural indicators

| Pattern | Example | Description |
|---------|---------|-------------|
| `^\s*\*\*([A-D])\*\*` | `**C**`, `**D**` | Markdown bold (line start) |
| `^\s*([A-D])\s*:` | `D: Explicação...` | Letter colon (line start) |
| `^\s*([A-D])\s*\)` | `A) Resposta...` | Letter parenthesis (line start) |
| `^\s*\(\s*([A-D])\s*\)` | `(B) Alternativa...` | Parenthesized letter (line start) |
| `\b([A-D])\b\s*:` | `concluo que: A` | Letter colon (anywhere) |
| `\b([A-D])\b\s*\)` | `alternativa B)` | Letter parenthesis (anywhere) |

**Characteristics:**
- Clear confidence
- Mix of line-start and anywhere matching
- Markdown support
- Parenthesis variations

---

### Level 4: Fallback Patterns (Lowest Priority)

**Confidence:** `low_confidence`

**Purpose:** Last-resort isolated letter detection

| Pattern | Example | Description |
|---------|---------|-------------|
| `\b([A-D])\b` | `Eu acho que é B` | Any isolated letter |

**Characteristics:**
- **Always** triggers `low_confidence` (requires manual review)
- Word boundary enforcement
- First match used if multiple found
- Filtered by article detection

---

## 3. Confidence Levels (4 Values)

The V1 parser defines **four confidence levels**:

### `clear`

**Meaning:** Single match from explicit, context, or structural patterns

**Characteristics:**
- Safe to use automatically
- No human review required
- Requires exactly one unique letter (A, B, C, or D)
- Repeated same letter is acceptable (e.g., "A resposta é A. Definitivamente A." → `clear`)

**Examples:**
- ✅ `Resposta: B` → `clear`, answer=`B`
- ✅ `A opção D está correta` → `clear`, answer=`D`
- ✅ `**C**` → `clear`, answer=`C`

---

### `ambiguous`

**Meaning:** Multiple **different** letters detected in response

**Characteristics:**
- Requires manual review
- `selected_answer` = `NULL`
- Triggers `needs_review = TRUE`
- All matched letters preserved in `raw_matches`

**Examples:**
- ❌ `A ou B estão corretas` → `ambiguous`, answer=`NULL`, matches=`['A', 'B']`
- ❌ `Alternativas A e C` → `ambiguous`, answer=`NULL`, matches=`['A', 'C']`

---

### `no_answer`

**Meaning:** No letter patterns found in response

**Characteristics:**
- Requires manual review
- `selected_answer` = `NULL`
- Triggers `needs_review = TRUE`
- May occur with empty responses or explanation-only text

**Examples:**
- ❌ `Justificativa: A alternativa está correta porque...` → `no_answer`
- ❌ `(empty response)` → `no_answer`

---

### `low_confidence`

**Meaning:** Only fallback pattern matched (isolated letter)

**Characteristics:**
- Requires manual review
- `selected_answer` may have value
- Triggers `needs_review = TRUE`
- Answer may be accidental mention

**Examples:**
- ⚠️ `Estudo ABC (2020) menciona...` → `low_confidence` (if "C" is only match)
- ⚠️ `Eu acho que é B` → `low_confidence`, answer=`B`

---

## 4. Article Filtering (Portuguese/Spanish "A")

### Problem

The letter "A" as a standalone word is often a **Portuguese/Spanish article**, not an answer:

- `A resposta` → article, not answer "A"
- `A alternativa correta` → article, not answer "A"
- `A opção` → article, not answer "A"

### Solution

V1 implements **context-aware article filtering**:

**Article Pattern:**
```python
r'\b[Aa]\s+(?:alternativa|opção|opcoes|resposta|letra|questão|questao|correct|correcta|correta|melhor|mais|única|unica|primeira|segunda|terceira|última|ultima|explicação|explicacao|capital|cidade|pais|país|regiao|região|parte|maioria|unica|primeira)\b'
```

**Filtering Logic:**
1. Detect "A" or "a" followed by noun indicators
2. Mark position as article
3. Exclude from filtered matches

**Examples:**
- `A resposta é B` → filtered: `['B']` (article "A" removed)
- `A alternativa correta é A` → filtered: `['A']` (article "A" removed, answer "A" kept)
- `A opção A está correta` → filtered: `['A']` (article "A" removed, answer "A" kept)

---

## 5. Answer Extraction Flow

### Step-by-Step Flow

```
1. Input Validation
   └─ Empty response? → return ParsedAnswer(confidence="no_answer")

2. Find All Letter Matches
   └─ Apply fallback pattern to find all [A-D] letters
   └─ Convert to uppercase

3. Filter Articles
   └─ Detect Portuguese/Spanish articles
   └─ Remove article "A" from matches

4. Check Ambiguity
   └─ Multiple different letters? → return ParsedAnswer(confidence="ambiguous")

5. Try Explicit Patterns
   └─ Match found? → return ParsedAnswer(confidence="clear", answer=letter)

6. Try Context Patterns
   └─ Match found? → return ParsedAnswer(confidence="clear", answer=letter)

7. Try Structural Patterns
   └─ Match found? → return ParsedAnswer(confidence="clear", answer=letter)

8. Fallback
   └─ Filtered matches exist? → return ParsedAnswer(confidence="low_confidence", answer=first_match)
   └─ No matches? → return ParsedAnswer(confidence="no_answer")
```

### Flow Diagram

```
                    ┌─────────────────┐
                    │  Response Text  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Empty Check    │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
         [Empty]                       [Not Empty]
              │                             │
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ no_answer       │           │ Find All Matches│
    │ answer=None     │           └────────┬────────┘
    └─────────────────┘                    │
                                   ┌───────▼───────┐
                                   │ Filter Articles│
                                   └───────┬───────┘
                                           │
                                   ┌───────▼───────┐
                                   │ >1 Unique Letter?
                                   └───────┬───────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        │                                     │
                   [Yes: Ambiguous]                      [No: Single/None]
                        │                                     │
                        ▼                                     ▼
              ┌─────────────────┐                   ┌─────────────────┐
              │ ambiguous       │                   │ Try Explicit    │
              │ answer=None     │                   └────────┬────────┘
              └─────────────────┘                            │
                                              ┌─────────────┴─────────────┐
                                              │                           │
                                         [Match]                     [No Match]
                                              │                           │
                                              ▼                           ▼
                                    ┌─────────────────┐         ┌─────────────────┐
                                    │ clear           │         │ Try Context     │
                                    │ answer=letter   │         └────────┬────────┘
                                    └─────────────────┘                  │
                                                            ┌───────────┴───────────┐
                                                            │                       │
                                                       [Match]                 [No Match]
                                                            │                       │
                                                            ▼                       ▼
                                                  ┌─────────────────┐     ┌─────────────────┐
                                                  │ clear           │     │ Try Structural  │
                                                  │ answer=letter   │     └────────┬────────┘
                                                  └─────────────────┘              │
                                                                     ┌────────────┴────────────┐
                                                                     │                         │
                                                                [Match]                  [No Match]
                                                                     │                         │
                                                                     ▼                         ▼
                                                           ┌─────────────────┐     ┌─────────────────┐
                                                           │ clear           │     │ Has Fallback?   │
                                                           │ answer=letter   │     └────────┬────────┘
                                                           └─────────────────┘              │
                                                                                  ┌────────┴────────┐
                                                                                  │                 │
                                                                             [Yes]             [No]
                                                                                  │                 │
                                                                                  ▼                 ▼
                                                                        ┌─────────────────┐ ┌─────────────────┐
                                                                        │ low_confidence  │ │ no_answer       │
                                                                        │ answer=letter   │ │ answer=None     │
                                                                        └─────────────────┘ └─────────────────┘
```

---

## 6. Edge Cases Handled

| Edge Case | V1 Behavior | Example |
|-----------|-------------|---------|
| **Portuguese/Spanish articles** | Filter article "A" when followed by nouns | `A resposta` → no match |
| **Repeated same letter** | Treated as `clear` (same letter) | `A resposta é A. Definitivamente A.` → `clear`, answer=`A` |
| **Multiple different letters** | Treated as `ambiguous` | `A ou B` → `ambiguous` |
| **Letter in explanation** | May be `low_confidence` or `no_answer` | `Estudo ABC (2020)` → depends on context |
| **Markdown variations** | All recognized (`**A**`, `__A__`, `**a)**`) | `**C**` → `clear`, answer=`C` |
| **Case insensitivity** | All matching is case-insensitive | `resposta: b` → `clear`, answer=`B` |
| **Reasoning models** | Reasoning text extraction available | `extract_reasoning_text()` method |
| **Empty response** | Returns `no_answer` | `""` → `no_answer` |

---

## 7. Data Structures

### ParsedAnswer Dataclass

```python
@dataclass
class ParsedAnswer:
    answer: Optional[str] = None           # Extracted letter (A, B, C, D) or None
    confidence: str = "no_answer"          # Confidence level
    raw_matches: list[str] = field(default_factory=list)  # All matches found
    reasoning_text: Optional[str] = None   # Extracted reasoning (optional)
```

**Validation:**
- `confidence` must be one of: `clear`, `ambiguous`, `no_answer`, `low_confidence`
- `clear` confidence requires non-NULL `answer`

---

## 8. Implementation Details

### Pattern Compilation

All patterns are compiled at initialization for efficiency:

```python
self._explicit_regex = [
    (re.compile(pattern, re.IGNORECASE | re.MULTILINE), has_group, conf)
    for pattern, has_group, conf in self.EXPLICIT_PATTERNS
]
```

**Flags:**
- `re.IGNORECASE`: Case-insensitive matching
- `re.MULTILINE`: Multi-line matching support

### Matching Flags

| Flag | Purpose |
|------|---------|
| `re.IGNORECASE` | Match "resposta" and "Resposta" equally |
| `re.MULTILINE` | Support `^` and `$` anchors per line |

---

## 9. Logging

V1 Answer Parser uses structured logging:

```python
logger = logging.getLogger(__name__)
```

**Log Points:**
- Empty response detection (DEBUG)
- All letter matches found (DEBUG)
- Filtered matches (DEBUG)
- Ambiguous response detection (DEBUG)
- Pattern match type (explicit/context/structural/fallback) (DEBUG)
- No match found (DEBUG)

---

## 10. Convenience Function

V1 provides a convenience function for simple usage:

```python
def parse_answer(response_text: str) -> ParsedAnswer:
    """Parse an LLM response and extract the answer letter."""
    parser = AnswerParser()
    return parser.parse(response_text)
```

---

## 11. Summary

The V1 Answer Parser implements:

1. **4-level pattern hierarchy**: Explicit → Context → Structural → Fallback
2. **4 confidence levels**: `clear`, `ambiguous`, `no_answer`, `low_confidence`
3. **Article filtering**: Portuguese/Spanish "A" detection and removal
4. **Ambiguity detection**: Multiple different letters trigger review
5. **Hierarchical flow**: Priority-based pattern evaluation
6. **Edge case handling**: Markdown, case insensitivity, repeated letters
7. **Reasoning extraction**: Optional reasoning text separation

**Key Characteristics:**
- Deterministic pattern matching
- Bilingual support (Portuguese/English)
- Confidence-based review routing
- Idempotent parsing (same input → same output)

---

**Related Documents:**
- `docs/architecture/legacy.ignore/legacy_execution_core.md` — Answer parsing section
- `docs/architecture/contracts/result-writer.md` — Review fields contract
- `docs/architecture/contracts/domain-review-contract.md` — needs_review calculation
