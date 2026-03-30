# V1 Review UI Analysis

**Document Type:** Legacy Analysis
**Domain:** Review UI
**Version:** 1.0
**Date:** 2026-03-29
**Status:** Historical Reference

---

## 1. Overview

The V1 Review UI was a **terminal-based, keyboard-driven interface** for manual classification of LLM responses that couldn't be automatically parsed with confidence. It was integrated directly into the CLI module (`src_legacy/cli/review_ui.py`) and provided an interactive, real-time review experience.

### 1.1 Key Characteristics

- **Keyboard-Driven:** All operations via single-key shortcuts (A/B/C/D/N/E/S/Q/Z)
- **Auto-Save:** Each classification saved immediately to database
- **Progress Tracking:** Real-time statistics (Pending, Processed, by-question, by-model)
- **Undo Support:** Z key undid last classification
- **Grouped Display:** Questions grouped with all iterations together
- **Portuguese Interface:** All UI text in Portuguese (contrasting with English CLI)

---

## 2. Architecture

### 2.1 Component Structure

```
src_legacy/cli/
├── review_ui.py             # Main review UI module (738 lines)
│   ├── ReviewItem           # Dataclass: response + question details
│   ├── ReviewStatistics     # Dataclass: review session statistics
│   └── ReviewUI             # Main class: interactive review interface
└── cli.py                   # Argument parsing (--review-experiment, --review-all)
```

### 2.2 Execution Flow

```
User Input (--review-experiment <name>)
    ↓
ReviewUI.__init__(db_manager)
    ↓
get_pending_by_experiment(experiment_id)
    ↓
Query: responses WHERE needs_review = TRUE
    ↓
Main Review Loop
    ├── _display_item()
    ├── _get_user_input()
    ├── _save_classification()
    └── Update statistics
    ↓
Database UPDATE (auto-save on each classification)
    ↓
Exit (Q key) → Save progress
```

---

## 3. Keyboard Interface

### 3.1 Classification Keys

| Key | Action | Database Effect |
|-----|--------|-----------------|
| **A** | Select alternative A | `manual_answer='A'`, `needs_review=FALSE`, `selected_answer='A'`, recalculate `is_correct` |
| **B** | Select alternative B | `manual_answer='B'`, `needs_review=FALSE`, `selected_answer='B'`, recalculate `is_correct` |
| **C** | Select alternative C | `manual_answer='C'`, `needs_review=FALSE`, `selected_answer='C'`, recalculate `is_correct` |
| **D** | Select alternative D | `manual_answer='D'`, `needs_review=FALSE`, `selected_answer='D'`, recalculate `is_correct` |
| **N** | No clear answer | `manual_answer=NULL`, `needs_review=FALSE`, `selected_answer=NULL`, `is_correct=FALSE` |
| **E** | Error not detected | `manual_answer=NULL`, `needs_review=FALSE`, `status='error'` |

### 3.2 Navigation Keys

| Key | Action | Behavior |
|-----|--------|----------|
| **S** | Skip | Advance to next item without saving |
| **Q** | Quit | Confirm and exit, saving progress |
| **Z** | Undo | Go back to previous item, decrement processed count |

### 3.3 Input Mechanism

**Cross-Platform Support:**

```python
if sys.platform == "win32":
    import msvcrt
    char = msvcrt.getwch().upper()  # Windows: msvcrt
else:
    import termios
    import tty
    # Linux: termios + tty (raw mode)
```

**Characteristics:**
- Single-character input (no Enter required)
- Case-insensitive (automatically uppercased)
- Immediate response (no echo delay)

---

## 4. Display Format

### 4.1 Screen Layout

```
================================================================================
REVIEW MANUAL DE RESPOSTAS  |  Item 1/23
================================================================================
Pendentes: 23  |  Processadas: 0
Pergunta: 1 (Iteração 1, Modelo: liquid/lfm-2.5-1.2b-thinking)
Resposta Correta: "A"
Status: AMBIGUOUS
================================================================================

ENUNCIADO:
--------------------------------------------------------------------------------
Homem de 45 anos foi encontrado inconsciente por familiares junto a uma escada...

ALTERNATIVAS:
--------------------------------------------------------------------------------
  A) tomografia de crânio, face e coluna cervical; radiografia de membros...
  B) radiografia de crânio e face; radiografia de membros; internar...
  C) radiografia de crânio, coluna cervical e membros em duas posições...
  D) tomografia de crânio, face e radiografia de membros; liberar...

RESPOSTA DA LLM:
--------------------------------------------------------------------------------
Okay, let me tackle this question. So the scenario is a 45-year-old man...
ANSWER: \boxed{C}

================================================================================
CLASSIFICAÇÃO:
--------------------------------------------------------------------------------
  [A]  [B]  [C]  [D]  [N]enhuma  [E]rro não detectado

  [S] Pular  |  [Q] Sair e salvar  |  [Z] Desfazer última
================================================================================
```

### 4.2 Display Components

| Section | Content | Formatting |
|---------|---------|------------|
| **Header** | Title, item number, progress | 80-char separator, bold |
| **Statistics** | Pending count, processed count | Inline summary |
| **Metadata** | Question ID, iteration, model, correct answer, status | Key-value pairs |
| **ENUNCIADO** | Question stem | Separator, full text |
| **ALTERNATIVAS** | Answer options (A, B, C, D) | Formatted list |
| **RESPOSTA DA LLM** | Full LLM response (truncated at 800 chars) | Dimmed text |
| **CLASSIFICAÇÃO** | Classification keys | Bold keys, action descriptions |
| **NAVIGAÇÃO** | Navigation keys (S, Q, Z) | Dimmed descriptions |

### 4.3 Response Truncation

```python
response_text = item.response.response_text
if len(response_text) > 800:
    response_text = response_text[:800] + "... (truncado)"
```

**Rationale:** Prevent excessive scrolling for long reasoning traces.

---

## 5. Progress Tracking

### 5.1 Real-Time Statistics

**Display Format:**
```
Pendentes: 23  |  Processadas: 0
```

**Calculated Fields:**
```python
@dataclass
class ReviewStatistics:
    total_pending: int       # Total items pending at session start
    total_processed: int     # Items processed in current session
    by_question: dict[str, int]  # Count per question ID
    by_model: dict[str, int]     # Count per model ID
    by_confidence: dict[str, int]  # Count per parse_confidence value
```

### 5.2 Statistics Calculation

```python
def _calculate_statistics(self, items: list[ReviewItem]) -> ReviewStatistics:
    stats = ReviewStatistics(total_pending=len(items))

    for item in items:
        # Group by question
        question_count = stats.by_question.get(item.response.question_id, 0)
        stats.by_question[item.response.question_id] = question_count + 1

        # Group by model
        model_count = stats.by_model.get(item.response.variant_id, 0)
        stats.by_model[item.response.variant_id] = model_count + 1

        # Group by confidence
        conf_count = stats.by_confidence.get(item.response.parse_confidence, 0)
        stats.by_confidence[item.response.parse_confidence] = conf_count + 1

    return stats
```

### 5.3 Progress Updates

**On Classification:**
```python
self._statistics.total_processed += 1
self._current_index += 1
```

**On Undo:**
```python
if self._current_index > 0:
    self._current_index -= 1
    self._statistics.total_processed -= 1
```

**On Skip:**
```python
self._current_index += 1
# total_processed NOT incremented
```

---

## 6. Auto-Save Mechanism

### 6.1 Save Trigger

**Automatic on Classification:**
- Every A/B/C/D/N/E key press triggers immediate save
- No "confirm" step
- No batch save at end

**Skip Does Not Save:**
- S key advances without saving
- Item remains in `needs_review = TRUE` state

### 6.2 Database Update

```python
def _save_classification(self, item: ReviewItem, classification: str) -> None:
    if classification == "S":
        return  # Skip - don't save

    # Update Response object
    if classification in ("A", "B", "C", "D"):
        item.response.manual_answer = classification
        item.response.needs_review = False
        item.response.selected_answer = classification
        item.response.is_correct = (classification == item.correct_answer)
    elif classification == "N":
        item.response.manual_answer = None
        item.response.needs_review = False
        item.response.selected_answer = None
        item.response.is_correct = False
    elif classification == "E":
        item.response.manual_answer = None
        item.response.needs_review = False
        item.response.status = "error"

    # Execute UPDATE
    cursor.execute("""
        UPDATE responses
        SET manual_answer = ?, needs_review = ?,
            selected_answer = ?, is_correct = ?, status = ?
        WHERE response_id = ?
    """, (
        item.response.manual_answer,
        0,  # needs_review = FALSE
        item.response.selected_answer,
        item.response.is_correct,
        item.response.status,
        item.response.response_id,
    ))
    conn.commit()
```

### 6.3 Idempotency

**Re-classification Allowed:**
- User can undo (Z) and re-classify
- Each classification overwrites previous
- No history tracking beyond single undo

---

## 7. Undo Functionality

### 7.1 Undo Mechanism

**History Tracking:**
```python
self._history: list[tuple[int, str]] = []  # (index, previous_status)
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
        if prev_index == self._current_index:
            # Could restore previous state (not implemented in V1)
```

### 7.2 Undo Limitations

| Limitation | Impact |
|------------|--------|
| Single-level undo | Only last classification can be undone |
| No database rollback | Undo only moves index, doesn't revert DB |
| No skip tracking | Skipped items not tracked in history |

---

## 8. Exit and Save

### 8.1 Exit Options

**Q Key (Quit):**
```python
elif user_input == "Q":
    print("\n\nSalvando progresso e saindo...")
    break  # Exit main loop
```

**Behavior:**
- No confirmation required (V1)
- Progress already saved (auto-save)
- Exit message displayed

### 8.2 Session Completion

**Normal Completion:**
```python
print(f"\nRevisão concluída! {self._statistics.total_processed} itens processados.")
```

**Summary Display:**
- Total processed count
- No detailed breakdown (V1)

---

## 9. Review Trigger Conditions

### 9.1 Query for Pending Items

```sql
SELECT r.response_id, r.run_id, r.snapshot_id, r.question_id, r.variant_id,
       r.iteration, r.selected_answer, r.response_text, r.is_correct,
       r.status, r.finish_reason, r.error_details, r.latency_ms,
       r.input_tokens, r.response_tokens, r.total_tokens, r.reasoning_tokens, r.effective_tokens,
       r.cost, r.raw_response_json, r.timestamp,
       r.parse_confidence, r.needs_review, r.manual_answer,
       json_extract(q.question_json, '$.stem') as stem,
       json_extract(q.question_json, '$.options') as options_json,
       json_extract(q.question_json, '$.answer_key') as answer_key
FROM responses r
JOIN question_snapshots q ON r.snapshot_id = q.snapshot_id
WHERE q.experiment_id = ?
  AND r.parse_confidence IN ('ambiguous', 'no_answer', 'low_confidence')
  AND r.needs_review = TRUE
ORDER BY r.question_id, r.iteration
```

### 9.2 Review Fields (V1)

| Field | Type | Purpose |
|-------|------|---------|
| `parse_confidence` | TEXT | Parser confidence level (`clear`, `ambiguous`, `no_answer`, `low_confidence`) |
| `selected_answer` | TEXT | Parsed answer (A/B/C/D or NULL) |
| `needs_review` | BOOLEAN | Calculated flag for human review |
| `manual_answer` | TEXT | Human-corrected answer (post-review) |

### 9.3 Review Trigger Logic

```python
needs_review = (
    parse_confidence in ('ambiguous', 'no_answer', 'low_confidence')
    OR selected_answer IS NULL
)
```

---

## 10. Review Commands

### 10.1 CLI Commands

| Command | Scope | Usage |
|---------|-------|-------|
| `--review-experiment <name>` | Single experiment | `bcllm --review-experiment exp-001` |
| `--review-all` | All experiments | `bcllm --review-all` |

### 10.2 Command Implementation

**Review Experiment:**
```python
def handle_review_experiment(args, conn) -> int:
    experiment_name = args.review_experiment
    ui = ReviewUI(conn)
    ui.start_review_by_experiment(experiment_name)
    return 0
```

**Review All:**
```python
def handle_review_all(args, conn) -> int:
    ui = ReviewUI(conn)
    ui.start_review_all()
    return 0
```

---

## 11. Language and Localization

### 11.1 Portuguese Interface

**All UI Text in Portuguese:**

| Element | Portuguese |
|---------|------------|
| Title | `REVIEW MANUAL DE RESPOSTAS` |
| Question | `Pergunta` |
| Correct Answer | `Resposta Correta` |
| Status | `Status` |
| Stem | `ENUNCIADO` |
| Options | `ALTERNATIVAS` |
| LLM Response | `RESPOSTA DA LLM` |
| Classification | `CLASSIFICAÇÃO` |
| Skip | `Pular` |
| Quit | `Sair e salvar` |
| Undo | `Desfazer última` |

### 11.2 Language Inconsistency

**Contrast with English CLI:**

| Component | Language |
|-----------|----------|
| CLI commands | English (`--review-experiment`) |
| CLI help text | English |
| Error messages | English |
| Review UI | Portuguese |

**Impact:**
- Inconsistent user experience
- Potential confusion for non-Portuguese speakers
- Historical artifact (early project development)

---

## 12. Key V1 Patterns Summary

### 12.1 UX Patterns

| Pattern | Implementation | Quality |
|---------|----------------|---------|
| **Keyboard-Driven** | Single-key shortcuts | High (fast, efficient) |
| **Auto-Save** | Immediate database update | High (no data loss) |
| **Progress Tracking** | Real-time statistics | High (user awareness) |
| **Undo Support** | Z key, single-level | Medium (limited depth) |
| **Grouped Display** | Questions with iterations | High (contextual) |
| **Response Truncation** | 800-char limit | Medium (may hide details) |

### 12.2 Technical Patterns

| Pattern | Implementation | Notes |
|---------|----------------|-------|
| **Tight Integration** | Part of `cli.py` module | Low separation of concerns |
| **Direct Database Access** | ReviewUI manages connection | No repository pattern |
| **Cross-Platform Input** | msvcrt (Windows) + termios (Linux) | Good portability |
| **In-Memory History** | `_history` list for undo | Limited to session |
| **No Confirmation** | Q key exits without confirm | Fast but error-prone |

### 12.3 Technical Debt

| Issue | Impact | Severity |
|-------|--------|----------|
| **Portuguese-only UI** | Limits accessibility | Medium |
| **No quit confirmation** | Accidental exits possible | Low |
| **Single-level undo** | Limited error recovery | Low |
| **No batch operations** | Must review one-by-one | Low |
| **No export/review later** | All-or-nothing workflow | Medium |

---

## 13. Files Analyzed

### 13.1 Core Files

| File | Lines | Purpose |
|------|-------|---------|
| `src_legacy/cli/review_ui.py` | 738 | Main review UI module |
| `src_legacy/cli/cli.py` | ~700 | Argument parsing (review commands) |
| `docs/architecture/legacy.ignore/legacy_ux_analysis.md` | ~500 | Existing UX analysis |
| `docs/architecture/to-be/comandos_simples.md` | ~300 | Review commands documentation |

---

## 14. Conclusion

The V1 Review UI was a **functional, keyboard-driven interface** that prioritized:

1. **Speed** — Single-key shortcuts for rapid classification
2. **Safety** — Auto-save prevented data loss
3. **Awareness** — Real-time progress tracking
4. **Recovery** — Undo support for mistakes

However, it suffered from:

1. **Language inconsistency** — Portuguese UI vs English CLI
2. **Tight coupling** — Integrated in CLI module, not separate
3. **Limited undo** — Single-level, no database rollback
4. **No confirmation** — Accidental exits possible

This analysis provides the foundation for understanding the V2 modular review system and identifying gaps between the two approaches.

---

**Next Document:** `docs/architecture/v2-current/04-review-ui.md` — V2 Current State Analysis
