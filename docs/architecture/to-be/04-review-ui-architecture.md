# Review UI Architecture & Contracts

**Document Type:** Target Architecture
**Domain:** Review UI
**Version:** 1.0
**Date:** 2026-03-29
**Status:** Proposed

---

## 1. Overview

This document defines the target architecture and contracts for the Review UI domain. It specifies the review workflow, field contracts, status values, idempotency guarantees, undo mechanism, and progress tracking requirements.

### 1.1 Design Principles

| Principle | Description |
|-----------|-------------|
| **Explicit Intent** | All review actions are intentional and auditable |
| **Immediate Persistence** | Each classification saved immediately (auto-save) |
| **Idempotent Operations** | Re-classification allowed, last-write-wins |
| **Minimal Schema** | Only essential fields in database |
| **Derived Logic** | `is_correct` and `needs_review` calculated, not stored independently |
| **Keyboard-First** | Optimized for rapid keyboard-driven classification |

---

## 2. Review Workflow

### 2.1 Workflow States

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         REVIEW WORKFLOW STATE MACHINE                        │
└──────────────────────────────────────────────────────────────────────────────┘

     ┌─────────────┐
     │  EXECUTION  │
     │  COMPLETE   │
     └──────┬──────┘
            │
            │ ResultWriter calculates needs_review
            │
            ▼
     ┌─────────────────────────────────────────────────────────────────────┐
     │                     RESPONSES TABLE                                 │
     │                                                                     │
     │  needs_review = TRUE  ──────────────┐  needs_review = FALSE        │
     │  (pending review)                   │  (no review needed)          │
     └──────────────┬──────────────────────┘                              │
                    │                                                     │
                    │ ReviewUI queries:                                   │
                    │ WHERE needs_review = TRUE                           │
                    │                                                     │
                    ▼                                                     │
     ┌─────────────────────────┐                                          │
     │   REVIEW QUEUE          │                                          │
     │   (ordered by question, │                                          │
     │    model, created_at)   │                                          │
     └───────────┬─────────────┘                                          │
                 │                                                        │
                 │ User classifies (A/B/C/D/N/E)                          │
                 │                                                        │
                 ▼                                                        │
     ┌─────────────────────────┐                                          │
     │   UPDATE RESPONSE       │                                          │
     │   - manual_answer       │                                          │
     │   - selected_answer     │                                          │
     │   - needs_review=FALSE  │◄─────────────────────────────────────────┘
     │   - is_correct          │
     └───────────┬─────────────┘
                 │
                 │ Commit
                 │
                 ▼
     ┌─────────────────────────┐
     │   REVIEW COMPLETE       │
     │   (response excluded    │
     │    from future queues)  │
     └─────────────────────────┘
```

### 2.2 Workflow Steps

**Step 1: Execution Complete**
- ExecutionEngine processes all items
- ResultWriter persists results
- `needs_review` calculated during INSERT

**Step 2: Review Queue Population**
- Query: `SELECT * FROM responses WHERE needs_review = TRUE`
- Join with `question_snapshots` for question details
- Order by: `question_id, model_id, created_at`

**Step 3: Review Session Start**
- Load all pending items into memory
- Calculate initial statistics
- Display welcome panel with counts

**Step 4: Classification Loop**
- Display current item (question, options, response)
- Wait for user input (A/B/C/D/N/E/S/Q/Z)
- Process classification
- Save to database immediately
- Update statistics
- Advance to next item

**Step 5: Session Complete**
- All items processed OR user quits
- Display summary panel
- Return to CLI

---

## 3. Review Status Values

### 3.1 needs_review Field

**Schema:**
```sql
needs_review BOOLEAN NOT NULL DEFAULT FALSE
```

**Values:**

| Value | Meaning | Set By | When |
|-------|---------|--------|------|
| `TRUE` (1) | Response requires manual review | ResultWriter | During INSERT, if `parse_confidence != 'clear'` OR `selected_answer IS NULL` |
| `FALSE` (0) | Response does not require review | ResultWriter or ReviewUI | During INSERT (auto) or UPDATE (manual classification) |

**Calculation Logic:**
```python
def calculate_needs_review(parse_confidence: str, selected_answer: Optional[str]) -> bool:
    if parse_confidence in ('ambiguous', 'no_answer', 'low_confidence'):
        return True
    if selected_answer is None:
        return True
    return False
```

### 3.2 review_status Field (NOT USED)

**Note:** Per `docs/architecture/contracts/domain-review-contract.md`, the `review_status` field is **NOT** part of the simplified schema.

**Instead, review state is derived from:**
```python
def get_review_status(response) -> str:
    if response.manual_answer is not None:
        return "reviewed"  # Manually reviewed
    elif not response.needs_review:
        return "auto"  # Auto-classified, no review needed
    else:
        return "needs_review"  # Pending review
```

### 3.3 Status Transitions

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        REVIEW STATUS TRANSITIONS                             │
└──────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────┐
  │  EXECUTION  │
  │  (running)  │
  └──────┬──────┘
         │
         │ ResultWriter persists response
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                                                                      │
  │  ┌──────────────────┐              ┌──────────────────┐             │
  │  │ needs_review=1   │              │ needs_review=0   │             │
  │  │ selected_answer= │              │ selected_answer= │             │
  │  │   NULL or low    │              │   confident      │             │
  │  │                  │              │                  │             │
  │  │ → PENDING REVIEW │              │ → AUTO           │             │
  │  └──────────────────┘              └──────────────────┘             │
  │                                                                      │
  └──────────────────────────────────────────────────────────────────────┘
                  │
                  │ ReviewUI: user classifies
                  │
                  ▼
         ┌──────────────────┐
         │ needs_review=0   │
         │ manual_answer=A  │
         │ selected_answer=A│
         │                  │
         │ → REVIEWED       │
         └──────────────────┘
```

---

## 4. Classification Values

### 4.1 Valid Classifications

| Value | Meaning | `manual_answer` | `selected_answer` | `is_correct` |
|-------|---------|-----------------|-------------------|--------------|
| **A** | Alternative A selected | `'A'` | `'A'` | `manual_answer == correct_answer` |
| **B** | Alternative B selected | `'B'` | `'B'` | `manual_answer == correct_answer` |
| **C** | Alternative C selected | `'C'` | `'C'` | `manual_answer == correct_answer` |
| **D** | Alternative D selected | `'D'` | `'D'` | `manual_answer == correct_answer` |
| **N** | No clear answer | `NULL` | `NULL` | `FALSE` |
| **E** | Error not detected | `NULL` | `NULL` | `FALSE` (status='error') |

### 4.2 Classification Semantics

**A/B/C/D (Answer Classification):**
- User identified the correct alternative
- `manual_answer` set to classification
- `selected_answer` updated to match
- `is_correct` recalculated based on `correct_answer` from snapshot
- `needs_review` set to `FALSE`

**N (No Clear Answer):**
- LLM response does not contain a clear answer
- `manual_answer` set to `NULL`
- `selected_answer` set to `NULL`
- `is_correct` set to `FALSE`
- `needs_review` set to `FALSE`

**E (Error Not Detected):**
- LLM response indicates technical error not caught by execution
- `manual_answer` set to `NULL`
- `selected_answer` set to `NULL`
- `is_correct` set to `FALSE`
- `status` set to `'error'`
- `needs_review` set to `FALSE`

### 4.3 Classification Labels

**Internal Labels (for feedback):**
```python
CLASSIFICATION_LABELS = {
    "A": "Correct",      # User believes this is correct answer
    "B": "Partial",      # Partially correct (use case dependent)
    "C": "Wrong",        # Incorrect answer
    "D": "Empty",        # Empty or nearly empty response
    "N": "None",         # No clear answer in response
    "E": "Error",        # Technical error detected
}
```

**Note:** Labels are for user feedback only. Actual correctness calculated from `correct_answer` in snapshot.

---

## 5. Idempotency Guarantees

### 5.1 Re-classification Allowed

**Principle:** Users can re-classify any response any number of times. Last write wins.

**Example:**
```
User classifies as A → UPDATE responses SET manual_answer='A' ...
User undoes (Z) → index decremented
User re-classifies as B → UPDATE responses SET manual_answer='B' ...
```

**Final State:** `manual_answer='B'` (last write)

### 5.2 No History Tracking (Beyond Session)

**Current Limitation:**
- Only current session tracks undo history
- No database-level audit trail
- Previous classifications not stored

**Future Enhancement:**
```sql
CREATE TABLE review_history (
    review_id TEXT PRIMARY KEY,
    response_id TEXT NOT NULL,
    previous_manual_answer TEXT,
    new_manual_answer TEXT,
    classified_at TEXT NOT NULL,
    session_id TEXT,
    FOREIGN KEY (response_id) REFERENCES responses(response_id)
);
```

### 5.3 Idempotent Save Operation

**Save Logic:**
```python
def _save_classification(self, item: ReviewItem, classification: str) -> None:
    if classification == "S":
        return  # Skip - no change

    # Calculate new values
    if classification in ("A", "B", "C", "D"):
        manual_answer = classification
        selected_answer = classification
        is_correct = (classification.upper() == item.correct_answer.upper())
        needs_review = False
    elif classification == "N":
        manual_answer = None
        selected_answer = None
        is_correct = False
        needs_review = False
    elif classification == "E":
        manual_answer = None
        selected_answer = None
        is_correct = False
        needs_review = False
        status = "error"

    # UPDATE (idempotent - overwrites previous values)
    cursor.execute("""
        UPDATE responses
        SET manual_answer = ?, needs_review = ?,
            selected_answer = ?, is_correct = ?, status = ?
        WHERE response_id = ?
    """, (manual_answer, needs_review, selected_answer, is_correct, status, item.response_id))
    conn.commit()
```

---

## 6. Undo Mechanism

### 6.1 Current Implementation (Single-Level)

**In-Memory History:**
```python
self._history: list[tuple[int, str]] = []  # (index, previous_answer)
```

**On Classification:**
```python
previous_answer = item.response.manual_answer or item.response.selected_answer or "None"
self._history.append((self._current_index, previous_answer))
```

**On Undo (Z key):**
```python
if self._current_index > 0:
    self._current_index -= 1
    self._statistics.total_processed -= 1

    if self._history:
        prev_index, prev_answer = self._history.pop()
        self._console.print(f"[yellow]Desfeito: classificação anterior era {prev_answer}[/yellow]")
```

**Limitations:**
- ❌ Only undoes index movement, not database changes
- ❌ Single-level only (cannot undo multiple items)
- ❌ History lost on session exit
- ❌ No database rollback

### 6.2 Target Implementation (Multi-Level)

**Enhanced History:**
```python
@dataclass
class ClassificationHistory:
    response_id: str
    previous_manual_answer: Optional[str]
    previous_selected_answer: Optional[str]
    previous_is_correct: Optional[bool]
    previous_needs_review: bool
    new_manual_answer: Optional[str]
    new_selected_answer: Optional[str]
    new_is_correct: Optional[bool]
    new_needs_review: bool
```

**Undo Stack:**
```python
self._undo_stack: list[ClassificationHistory] = []
```

**On Classification:**
```python
# Save previous state
history = ClassificationHistory(
    response_id=item.response.response_id,
    previous_manual_answer=item.response.manual_answer,
    previous_selected_answer=item.response.selected_answer,
    previous_is_correct=item.response.is_correct,
    previous_needs_review=item.response.needs_review,
    new_manual_answer=classification,
    new_selected_answer=classification,
    new_is_correct=(classification == item.correct_answer),
    new_needs_review=False,
)
self._undo_stack.append(history)
```

**On Undo (Z key):**
```python
if self._undo_stack:
    history = self._undo_stack.pop()

    # Rollback database
    cursor.execute("""
        UPDATE responses
        SET manual_answer = ?, selected_answer = ?,
            is_correct = ?, needs_review = ?
        WHERE response_id = ?
    """, (
        history.previous_manual_answer,
        history.previous_selected_answer,
        history.previous_is_correct,
        history.previous_needs_review,
        history.response_id,
    ))
    conn.commit()

    self._console.print(f"[yellow]Desfeito: classificação anterior era {history.previous_manual_answer or 'None'}[/yellow]")
```

**Stack Limit:**
```python
MAX_UNDO_DEPTH = 50

if len(self._undo_stack) >= MAX_UNDO_DEPTH:
    self._undo_stack.pop(0)  # Remove oldest
```

---

## 7. Progress Tracking

### 7.1 Statistics Dataclass

```python
@dataclass
class ReviewStatistics:
    """Statistics for a review session.

    Attributes:
        total_pending: Total number of items pending review at session start.
        total_processed: Total number of items processed in this session.
        by_classification: Count by classification (A, B, C, D, N, E).
        by_question: Count of pending items grouped by question ID.
        by_model: Count of pending items grouped by model ID.
        by_confidence: Count of pending items grouped by parse confidence.
    """

    total_pending: int = 0
    total_processed: int = 0
    by_classification: dict[str, int] = field(default_factory=dict)
    by_question: dict[str, int] = field(default_factory=dict)
    by_model: dict[str, int] = field(default_factory=dict)
    by_confidence: dict[str, int] = field(default_factory=dict)
```

### 7.2 Real-Time Updates

**On Classification:**
```python
self._statistics.total_processed += 1

class_count = self._statistics.by_classification.get(user_input, 0)
self._statistics.by_classification[user_input] = class_count + 1
```

**Display Format:**
```
Pendentes: 23  |  Processadas: 10  |  A: 5, B: 3, C: 2
```

### 7.3 Progress Indicators

**Header Display:**
```python
def _display_header(self, item_number: int, total: int) -> None:
    header_text = Text()
    header_text.append("REVIEW MANUAL DE RESPOSTAS", style="bold blue")
    header_text.append(f"  |  Item {item_number}/{total}", style="dim")

    stats_text = Text()
    stats_text.append(f"Pendentes: {self._statistics.total_pending - self._statistics.total_processed}", style="yellow")
    stats_text.append("  |  ", style="dim")
    stats_text.append(f"Processadas: {self._statistics.total_processed}", style="green")

    if self._statistics.by_classification:
        stats_text.append("  |  ", style="dim")
        class_parts = []
        for cls, count in sorted(self._statistics.by_classification.items()):
            if count > 0:
                class_parts.append(f"{cls}: {count}")
        if class_parts:
            stats_text.append(", ".join(class_parts), style="cyan")
```

### 7.4 Completion Summary

```python
self._console.print(Panel(
    f"[bold green]Revisão concluída![/bold green]\n\n"
    f"[bold]{self._statistics.total_processed}[/bold] itens processados.\n\n"
    f"Classificações:\n" +
    "\n".join([f"  {k}: {v}" for k, v in sorted(self._statistics.by_classification.items()) if v > 0]),
    title="Resumo",
    border_style="green",
))
```

---

## 8. Review Field Contract

### 8.1 Schema Definition

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
    needs_review               BOOLEAN NOT NULL DEFAULT FALSE,  -- Derived by ResultWriter
    manual_answer              TEXT,  -- Set by reviewer (NULL = not reviewed)

    -- Status
    status                     TEXT DEFAULT 'success',

    -- ... other fields (latency, tokens, etc.)

    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id),
    FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id)
);

CREATE INDEX IF NOT EXISTS idx_responses_needs_review
    ON responses(needs_review)
    WHERE needs_review = TRUE;
```

### 8.2 Field Semantics

| Field | Type | Nullable | Default | Set By | Purpose |
|-------|------|----------|---------|--------|---------|
| `parse_confidence` | TEXT | Yes | `'unknown'` | ExecutionEngine | Parser confidence level |
| `needs_review` | BOOLEAN | No | `FALSE` | ResultWriter (derived) | Flag for human review |
| `manual_answer` | TEXT | Yes | `NULL` | Reviewer (human) | Human-corrected answer |
| `selected_answer` | TEXT | Yes | `NULL` | ExecutionEngine / ReviewUI | Current answer (auto or manual) |
| `is_correct` | BOOLEAN | Yes | `NULL` | Derived | Correctness based on answer |

### 8.3 Field Values

**parse_confidence:**

| Value | Meaning |
|-------|---------|
| `'unknown'` | Confidence not calculated |
| `'clear'` | Answer unambiguously detected |
| `'ambiguous'` | Multiple answers detected |
| `'no_answer'` | No answer detected |
| `'low_confidence'` | Weak pattern match |

**manual_answer:**

| Value | Meaning |
|-------|---------|
| `'A'` | Human classified as A |
| `'B'` | Human classified as B |
| `'C'` | Human classified as C |
| `'D'` | Human classified as D |
| `NULL` | Not yet reviewed OR classified as N/E |

---

## 9. is_correct Calculation

### 9.1 Derivation Logic

```python
def calculate_is_correct(
    manual_answer: Optional[str],
    selected_answer: Optional[str],
    correct_answer_from_snapshot: str
) -> Optional[bool]:
    """
    Calculate is_correct based on answer priority.

    Priority:
    1. If manual_answer exists, use it
    2. Else if selected_answer exists, use it
    3. Else NULL (parsing failed, review pending)
    """
    if manual_answer is not None:
        return manual_answer.upper() == correct_answer_from_snapshot.upper()
    elif selected_answer is not None:
        return selected_answer.upper() == correct_answer_from_snapshot.upper()
    else:
        return None  # Review pending
```

### 9.2 Update Triggers

**On Manual Classification:**
```python
if classification in ("A", "B", "C", "D"):
    item.response.manual_answer = classification
    item.response.selected_answer = classification
    item.response.is_correct = (classification.upper() == item.correct_answer.upper())
```

**On N (No Clear Answer):**
```python
elif classification == "N":
    item.response.manual_answer = None
    item.response.selected_answer = None
    item.response.is_correct = False
```

**On E (Error):**
```python
elif classification == "E":
    item.response.manual_answer = None
    item.response.selected_answer = None
    item.response.is_correct = False
    item.response.status = "error"
```

---

## 10. Query Contracts

### 10.1 Get Pending by Experiment

```sql
SELECT r.response_id, r.run_id, r.variant_id, r.snapshot_id,
       r.model_id, r.question_id, r.selected_answer,
       r.response_text, r.is_correct,
       r.parse_confidence, r.needs_review, r.manual_answer,
       r.latency_ms, r.input_tokens, r.output_tokens, r.created_at,
       json_extract(q.question_payload, '$.stem') as stem,
       json_extract(q.question_payload, '$.options') as options_json,
       json_extract(q.question_payload, '$.answer_key') as answer_key
FROM responses r
JOIN question_snapshots q ON r.snapshot_id = q.snapshot_id
JOIN runs run ON r.run_id = run.run_id
WHERE run.experiment_id = ?
  AND r.needs_review = 1
ORDER BY r.question_id, r.model_id, r.created_at
```

**Parameters:**
- `experiment_id` (TEXT)

**Returns:**
- List of ReviewItem objects

### 10.2 Get Pending All

```sql
SELECT r.response_id, r.run_id, r.variant_id, r.snapshot_id,
       r.model_id, r.question_id, r.selected_answer,
       r.response_text, r.is_correct,
       r.parse_confidence, r.needs_review, r.manual_answer,
       r.latency_ms, r.input_tokens, r.output_tokens, r.created_at,
       json_extract(q.question_payload, '$.stem') as stem,
       json_extract(q.question_payload, '$.options') as options_json,
       json_extract(q.question_payload, '$.answer_key') as answer_key,
       run.experiment_id
FROM responses r
JOIN question_snapshots q ON r.snapshot_id = q.snapshot_id
JOIN runs run ON r.run_id = run.run_id
WHERE r.needs_review = 1
ORDER BY run.experiment_id, r.question_id, r.model_id, r.created_at
```

**Parameters:**
- None (all experiments)

**Returns:**
- List of ReviewItem objects

### 10.3 Update Classification

```sql
UPDATE responses
SET manual_answer = ?, needs_review = ?,
    selected_answer = ?, is_correct = ?, status = ?
WHERE response_id = ?
```

**Parameters:**
- `manual_answer` (TEXT or NULL)
- `needs_review` (BOOLEAN, always 0)
- `selected_answer` (TEXT or NULL)
- `is_correct` (BOOLEAN or NULL)
- `status` (TEXT)
- `response_id` (TEXT)

---

## 11. Interface Contracts

### 11.1 ReviewUI Public API

```python
class ReviewUI:
    """CLI-based interface for manual review of LLM responses."""

    def __init__(self, conn) -> None:
        """Initialize the ReviewUI.

        Args:
            conn: SQLite database connection.
        """

    def get_pending_by_experiment(self, experiment_id: str) -> list[ReviewItem]:
        """Get pending review items for an experiment.

        Args:
            experiment_id: ID of the experiment to review.

        Returns:
            List of ReviewItem objects pending review.
        """

    def start_review_by_experiment(self, experiment_name: str) -> None:
        """Start the manual review interface for an experiment.

        Args:
            experiment_name: Name of the experiment to review.
        """

    def start_review_all(self) -> None:
        """Start the manual review interface for all pending items.
        """
```

### 11.2 CLI Commands

```python
# Review experiment
bcllm --review-experiment <experiment_name>

# Review all pending
bcllm --review-all
```

### 11.3 Keyboard Interface

| Key | Action | Method |
|-----|--------|--------|
| A/B/C/D | Classify | `_save_classification(classification)` |
| N | No clear answer | `_save_classification('N')` |
| E | Error not detected | `_save_classification('E')` |
| S | Skip | Advance index without save |
| Q | Quit | `_confirm_quit()` → exit loop |
| Z | Undo | Decrement index, pop history |

---

## 12. Error Handling

### 12.1 Error Categories

| Error Type | Handling | User Message |
|------------|----------|--------------|
| **Experiment Not Found** | Return early | `Erro: Experimento não encontrado: {name}` |
| **Database Error** | Propagate exception | `Error during review: {error}` |
| **Keyboard Interrupt** | Catch, exit gracefully | `Review interrupted by user.` |
| **Input Error** | Log, continue | `Error getting user input: {error}` |
| **Empty Review Queue** | Inform user, exit | `Nenhuma resposta pendente de revisão.` |

### 12.2 Error Recovery

**Auto-Save Guarantee:**
- Each classification saved immediately
- Interrupted session: progress not lost
- Unsaved state: only current item (if skipped)

**Undo Limitation:**
- Undo does not rollback database (current)
- Future: multi-level undo with rollback

---

## 13. Validation Criteria

### 13.1 Functional Validation

| Criterion | Expected Behavior |
|-----------|-------------------|
| **Review Trigger** | `needs_review = TRUE` correctly calculated |
| **Classification Save** | Database updated immediately |
| **Progress Tracking** | Statistics accurate after each action |
| **Undo** | Index decremented, history tracked |
| **Quit** | Confirmation required, progress saved |
| **Completion** | Summary displayed with breakdown |

### 13.2 Data Integrity Validation

| Criterion | Expected Behavior |
|-----------|-------------------|
| **Idempotency** | Re-classification overwrites previous |
| **Correctness** | `is_correct` matches `manual_answer == correct_answer` |
| **Review Exclusion** | Classified responses excluded from future queues |
| **Null Handling** | N/E classifications set `manual_answer = NULL` |

### 13.3 UX Validation

| Criterion | Expected Behavior |
|-----------|-------------------|
| **Response Time** | < 100ms for classification save |
| **Screen Refresh** | < 500ms for full redraw |
| **Input Latency** | < 50ms for key press to feedback |
| **Error Visibility** | Errors clearly displayed in red |

---

## 14. Conclusion

This document defines the target architecture and contracts for the Review UI domain. Key aspects include:

**Workflow:**
- Clear state machine from execution → review queue → classification → complete
- Auto-save on each classification
- Idempotent operations (re-classification allowed)

**Fields:**
- Minimal schema (3 review fields: `parse_confidence`, `needs_review`, `manual_answer`)
- Derived logic (`is_correct`, `needs_review`)
- Clear field semantics and values

**Contracts:**
- Query contracts for pending items
- Update contract for classification
- Interface contract for ReviewUI class
- CLI command contract

**Validation:**
- Functional validation criteria
- Data integrity validation
- UX performance targets

---

**Next Document:** `docs/architecture/v2-adaptation/04-review-ui-adaptation.md` — V2 Adaptation Plan
