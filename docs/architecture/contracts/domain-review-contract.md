# FINAL DOMAIN SIMPLIFICATION — Manual Review Contract

**Version:** 1.0 (Simplified)
**Date:** 2026-03-18
**Status:** APPROVED

---

## 1. DESIGN PRINCIPLE

**Manual review is a required part of the domain, but the schema should be MINIMAL.**

We only need to track:
1. Was the answer confidently parsed?
2. Does this response need manual review?
3. What is the final (possibly corrected) answer?

**We do NOT need:**
- Who reviewed it
- When it was reviewed
- Why it was reviewed
- Workflow status tracking

**The review contract MUST NOT introduce new schema fields beyond those explicitly listed here. Review logic must adapt to the existing schema, never the opposite.**
---

## 2. SIMPLIFIED REVIEW CONTRACT

### Fields Required

| Field | Type | Purpose | When Set |
|-------|------|---------|----------|
| `parse_confidence` | TEXT | How confident is the parser? | ExecutionEngine |
| `needs_review` | BOOLEAN | Does this need human review? | ResultWriter (derived) |
| `manual_answer` | TEXT | Human-corrected answer | Reviewer (optional) |

### Field Semantics

**`parse_confidence`** — Set by ExecutionEngine during answer parsing

| Value | Meaning | Action |
|-------|---------|--------|
| `'clear'` | Answer letter unambiguous | No review needed |
| `'ambiguous'` | Multiple letters detected | Review needed |
| `'no_answer'` | No letter found | Review needed |
| `'low_confidence'` | Weak pattern match | Review recommended |

**`needs_review`** — Derived flag (NOT NULL, default FALSE)

```python
needs_review = (
    parse_confidence != 'clear' 
    OR selected_answer IS NULL
)
```

**`manual_answer`** — Human override (NULL if not reviewed)

```python
# When manual_answer is set:
if response.manual_answer:
    is_correct = (manual_answer == correct_answer_from_snapshot)
else:
    is_correct = (selected_answer == correct_answer_from_snapshot)
    # May be NULL if selected_answer is NULL
```

---

## 3. PROPOSED SCHEMA CHANGES

### 3.1 Add Minimal Review Fields

```sql
-- How confident is the parser? (set by ExecutionEngine)
ALTER TABLE responses ADD COLUMN parse_confidence TEXT DEFAULT 'unknown';
-- Values: 'unknown', 'clear', 'ambiguous', 'no_answer', 'low_confidence'

-- Does this need human review? (derived, set by ResultWriter)
ALTER TABLE responses ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT FALSE;

-- Human-corrected answer (set by reviewer, NULL if not reviewed)
ALTER TABLE responses ADD COLUMN manual_answer TEXT;
```

### 3.2 Index for Review Queries

```sql
-- Find all responses needing review
CREATE INDEX IF NOT EXISTS idx_responses_needs_review
    ON responses(needs_review)
    WHERE needs_review = TRUE;
```

### 3.3 Remove Unnecessary Fields (NOT YET ADDED)

The following fields from the original proposal are **NOT needed**:

```sql
-- NOT NEEDED:
-- review_status      -- Replaced by: needs_review + (manual_answer IS NOT NULL)
-- reviewed_at        -- Not needed for current use case
-- reviewer_id        -- Not needed for current use case
-- review_notes       -- Not needed for current use case
```

---

## 4. DERIVED LOGIC

### `is_correct` Calculation

```python
def calculate_is_correct(response, correct_answer_from_snapshot):
    """
    is_correct is DERIVED, not stored independently.
    
    Priority:
    1. If manual_answer exists, use it
    2. Else if selected_answer exists, use it
    3. Else NULL (parsing failed, review pending)
    """
    if response.manual_answer is not None:
        return response.manual_answer == correct_answer_from_snapshot
    elif response.selected_answer is not None:
        return response.selected_answer == correct_answer_from_snapshot
    else:
        return None  # Review pending
```

### `needs_review` Calculation

```python
def calculate_needs_review(response):
    """
    needs_review is DERIVED from parse_confidence and selected_answer.
    """
    if response.parse_confidence in ('ambiguous', 'no_answer'):
        return True
    if response.parse_confidence == 'low_confidence':
        return True  # Recommended
    if response.selected_answer is None:
        return True  # Parsing failed
    return False
```

---

## 5. EXECUTION FLOW

### During Execution

```
ExecutionEngine._parse_answer(response_text)
    ↓
Returns: {
    "selected_answer": "B" | None,
    "parse_confidence": "clear" | "ambiguous" | "no_answer" | "low_confidence"
}
    ↓
ExecutionResult includes both fields
    ↓
ResultWriter.write_results()
    ↓
INSERT INTO responses (
    ..., 
    selected_answer, 
    parse_confidence, 
    needs_review  -- calculated before insert
)
```

### During Review

```
Query: SELECT * FROM responses WHERE needs_review = TRUE
    ↓
User provides manual_answer for each
    ↓
UPDATE responses 
SET manual_answer = ?
WHERE response_id = ?
    ↓
is_correct is automatically recalculated:
    is_correct = (manual_answer == correct_answer)
```

---

## 6. FINAL SCHEMA (responses table excerpt)

```sql
CREATE TABLE IF NOT EXISTS responses (
    response_id                TEXT PRIMARY KEY,
    run_id                     TEXT NOT NULL,
    variant_id                 TEXT NOT NULL,
    snapshot_id                TEXT NOT NULL,
    
    -- Reference
    model_id                   TEXT NOT NULL,
    question_id                TEXT NOT NULL,
    
    -- Result (from ExecutionEngine)
    response_text              TEXT,
    selected_answer            TEXT,  -- May be NULL if parsing failed
    is_correct                 BOOLEAN,  -- DERIVED, may be NULL
    
    -- Review (minimal)
    parse_confidence           TEXT DEFAULT 'unknown',  -- Set by Engine
    needs_review               BOOLEAN NOT NULL DEFAULT FALSE,  -- Derived
    manual_answer              TEXT,  -- Set by reviewer (NULL = not reviewed)
    
    -- ... other fields (latency, tokens, etc.)
    
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id),
    FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id)
);

CREATE INDEX IF NOT EXISTS idx_responses_needs_review
    ON responses(needs_review)
    WHERE needs_review = TRUE;
```

---

## 7. CONFIRMATION

### Fields in Final Contract

| Field | Included? | Reason |
|-------|-----------|--------|
| `parse_confidence` | ✅ YES | Needed to know parsing reliability |
| `needs_review` | ✅ YES | Needed to find responses requiring review |
| `manual_answer` | ✅ YES | Needed to store human-corrected answer |
| `review_status` | ❌ NO | Redundant: `needs_review + (manual_answer IS NOT NULL)` covers it |
| `reviewed_at` | ❌ NO | Not needed for current use case |
| `reviewer_id` | ❌ NO | Not needed for current use case |
| `review_notes` | ❌ NO | Not needed for current use case |

### Unnecessary Fields Removed

- ❌ `review_status` — Replaced by: `needs_review` + `(manual_answer IS NOT NULL)`
- ❌ `reviewed_at` — Timestamp not needed
- ❌ `reviewer_id` — Identity not needed
- ❌ `review_notes` — Notes not needed

---

## 8. SUMMARY

**The simplified review contract requires ONLY 3 fields:**

1. **`parse_confidence`** — How confident is the parser?
2. **`needs_review`** — Does this need human review?
3. **`manual_answer`** — What is the final (corrected) answer?

**Everything else is derived or unnecessary.**

---

**This is the FINAL review contract. Implementation is a separate cycle.**
