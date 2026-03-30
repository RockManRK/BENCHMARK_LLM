# Review UI V2 Adaptation Plan

**Document Type:** V2 Adaptation
**Domain:** Review UI
**Version:** 1.0
**Date:** 2026-03-29
**Status:** Proposed

---

## 1. Overview

This document provides a comprehensive adaptation plan for evolving the V2 Review UI from its current state to the target architecture defined in `docs/architecture/to-be/04-review-ui-architecture.md`. It includes current state assessment, gap analysis, implementation considerations, migration path, and validation criteria.

---

## 2. Current State Assessment

### 2.1 Architecture Summary

**Current Structure:**
```
src/
├── review/
│   ├── __init__.py              # Package initialization
│   └── review_ui.py             # Main review UI module (676 lines)
└── cli/
    └── bcllm_review.py          # CLI entry point for review commands
```

**Current Features:**
- ✅ Keyboard-driven interface (A/B/C/D/N/E/S/Q/Z)
- ✅ Auto-save on each classification
- ✅ Progress tracking with classification breakdown
- ✅ Quit confirmation (Y/N dialog)
- ✅ Rich console formatting
- ✅ Cross-platform support (Windows + Linux)
- ✅ Review by experiment or all pending

### 2.2 Current Limitations

| Limitation | Impact | Severity |
|------------|--------|----------|
| **Single-Level Undo** | Cannot undo multiple classifications | Medium |
| **No Database Rollback** | Undo only moves index, doesn't revert DB | Medium |
| **Portuguese-Only UI** | Limits accessibility for non-Portuguese speakers | High |
| **No Session Persistence** | Cannot pause and resume review sessions | Medium |
| **No Batch Operations** | Must classify one-by-one | Low |
| **No Search/Filter** | Fixed review order | Low |
| **Repository Not Used** | Direct SQL in UI class | Low |

### 2.3 Current Compliance with Contracts

| Contract | Compliance | Notes |
|----------|------------|-------|
| **Review Fields** | ✅ Full | `parse_confidence`, `needs_review`, `manual_answer` |
| **Review Trigger** | ✅ Full | `needs_review = 1` query |
| **Classification Values** | ✅ Full | A/B/C/D/N/E all supported |
| **Idempotency** | ✅ Full | Re-classification allowed |
| **Auto-Save** | ✅ Full | Immediate database UPDATE |
| **Undo Mechanism** | ⚠️ Partial | Single-level, no DB rollback |
| **Progress Tracking** | ✅ Full | Real-time statistics |

---

## 3. Target State (Per Architecture)

### 3.1 Target Architecture

**Target Structure:**
```
src/
├── review/
│   ├── __init__.py
│   ├── review_ui.py             # Main UI class
│   ├── models.py                # ReviewItem, ReviewStatistics, ClassificationHistory
│   ├── repository.py            # ReviewRepository (dedicated)
│   ├── services.py              # ClassificationService, UndoService
│   └── localization/            # i18n support
│       ├── en.json
│       └── pt.json
└── cli/
    └── bcllm_review.py
```

### 3.2 Target Features

| Feature | Current | Target | Gap |
|---------|---------|--------|-----|
| **Multi-Level Undo** | ❌ | ✅ | High |
| **Database Rollback** | ❌ | ✅ | High |
| **English UI Option** | ❌ | ✅ | High |
| **Session Persistence** | ❌ | ✅ | Medium |
| **Batch Classification** | ❌ | ✅ | Medium |
| **Search/Filter** | ❌ | ✅ | Low |
| **Review Notes** | ❌ | ✅ | Low |
| **Export Results** | ❌ | ✅ | Low |

### 3.3 Target Contracts

**Review Fields:**
- ✅ Already compliant (no changes needed)

**Classification Logic:**
- ✅ Already compliant (no changes needed)

**Undo Mechanism:**
- ⚠️ Needs enhancement (multi-level + rollback)

**Localization:**
- ❌ Needs implementation (i18n framework)

---

## 4. Gap Analysis

### 4.1 Feature Gaps

| Feature | Current State | Target State | Gap | Priority |
|---------|---------------|--------------|-----|----------|
| **Undo Depth** | Single-level | Multi-level (50 items) | High | High |
| **Undo Rollback** | None | Database rollback | High | High |
| **UI Language** | Portuguese only | Portuguese + English | High | High |
| **Session Resume** | Not supported | Supported via session state | Medium | Medium |
| **Batch Classify** | Not supported | Supported (multi-select) | Medium | Medium |
| **Search/Filter** | Not supported | Supported (by model, confidence) | Low | Low |
| **Review Notes** | Not supported | Supported (optional notes) | Low | Low |
| **Export** | Not supported | JSON/CSV export | Low | Low |

### 4.2 Architectural Gaps

| Aspect | Current | Target | Gap | Priority |
|--------|---------|--------|-----|----------|
| **Module Structure** | Single file | Multi-module package | Medium | Medium |
| **Repository Pattern** | Not used | Dedicated ReviewRepository | Low | Low |
| **Service Layer** | None | ClassificationService, UndoService | Medium | Medium |
| **Localization** | None | i18n framework | High | High |
| **Session State** | None | Session persistence | Medium | Medium |

### 4.3 Code Quality Gaps

| Aspect | Current | Target | Gap | Priority |
|--------|---------|--------|-----|----------|
| **Test Coverage** | None | 80%+ unit test coverage | High | High |
| **Type Hints** | Full | Full + strict mode | Low | Low |
| **Docstrings** | Full | Full + examples | Low | Low |
| **Error Handling** | Basic | Comprehensive + recovery | Medium | Medium |

---

## 5. Implementation Considerations

### 5.1 Multi-Level Undo

**Implementation Approach:**

```python
@dataclass
class ClassificationHistory:
    """History entry for undo operations."""
    response_id: str
    previous_manual_answer: Optional[str]
    previous_selected_answer: Optional[str]
    previous_is_correct: Optional[bool]
    previous_needs_review: bool
    new_manual_answer: Optional[str]
    new_selected_answer: Optional[str]
    new_is_correct: Optional[bool]
    new_needs_review: bool


class ReviewUI:
    def __init__(self, conn) -> None:
        self._undo_stack: list[ClassificationHistory] = []
        self._max_undo_depth = 50

    def _save_classification(self, item: ReviewItem, classification: str) -> None:
        # Save previous state for undo
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

        # Execute UPDATE
        # ...

        # Add to undo stack
        self._undo_stack.append(history)

        # Enforce max depth
        if len(self._undo_stack) > self._max_undo_depth:
            self._undo_stack.pop(0)

    def _undo_last_classification(self) -> None:
        if not self._undo_stack:
            self._console.print("[yellow]Nada para desfazer.[/yellow]")
            return

        history = self._undo_stack.pop()

        # Rollback database
        cursor = self.conn.cursor()
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
        self.conn.commit()

        # Decrement index
        self._current_index -= 1
        self._statistics.total_processed -= 1

        self._console.print(
            f"[yellow]Desfeito: classificação anterior era {history.previous_manual_answer or 'None'}[/yellow]"
        )
```

**Considerations:**
- Memory usage: 50 history entries max
- Performance: Single UPDATE per undo
- Edge cases: Empty stack, stack underflow

### 5.2 Localization (i18n)

**Implementation Approach:**

```python
# src/review/localization/i18n.py
import json
from pathlib import Path

class Localization:
    def __init__(self, language: str = "pt") -> None:
        self.language = language
        self._strings = self._load_strings(language)

    def _load_strings(self, language: str) -> dict:
        path = Path(__file__).parent / f"{language}.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get(self, key: str, **kwargs) -> str:
        """Get localized string with optional formatting."""
        string = self._strings.get(key, key)
        return string.format(**kwargs) if kwargs else string


# src/review/localization/pt.json
{
    "title": "REVIEW MANUAL DE RESPOSTAS",
    "item_progress": "Item {current}/{total}",
    "pending": "Pendentes: {count}",
    "processed": "Processadas: {count}",
    "question": "Pergunta:",
    "model": "Modelo:",
    "correct_answer": "Resposta Correta:",
    "status": "Status:",
    "stem_title": "ENUNCIADO",
    "options_title": "ALTERNATIVAS",
    "response_title": "RESPOSTA DA LLM",
    "classification_title": "CLASSIFICAÇÃO:",
    "navigation_title": "NAVIGAÇÃO:",
    "classify_a": "Correta",
    "classify_b": "Parcial",
    "classify_c": "Errada",
    "classify_d": "Vazia",
    "classify_n": "Nenhuma",
    "classify_e": "Erro não detectado",
    "nav_skip": "Pular",
    "nav_quit": "Sair e salvar",
    "nav_undo": "Desfazer última",
    "confirm_quit": "Tem certeza que deseja sair? (y/n): ",
    "saving_exiting": "Salvando progresso e saindo...",
    "nothing_to_undo": "Nada para desfazer.",
    "undone_previous": "Desfeito: classificação anterior era {answer}",
    "review_complete": "Revisão concluída!",
    "items_processed": "{count} itens processados.",
    "classifications": "Classificações:",
    "no_pending": "Nenhuma resposta pendente de revisão.",
    "experiment_not_found": "Erro: Experimento não encontrado: {name}",
    "review_interrupted": "Review interrupted by user.",
    "error_during_review": "Error during review: {error}"
}


# src/review/localization/en.json
{
    "title": "MANUAL ANSWER REVIEW",
    "item_progress": "Item {current}/{total}",
    "pending": "Pending: {count}",
    "processed": "Processed: {count}",
    "question": "Question:",
    "model": "Model:",
    "correct_answer": "Correct Answer:",
    "status": "Status:",
    "stem_title": "QUESTION",
    "options_title": "OPTIONS",
    "response_title": "LLM RESPONSE",
    "classification_title": "CLASSIFICATION:",
    "navigation_title": "NAVIGATION:",
    "classify_a": "Correct",
    "classify_b": "Partial",
    "classify_c": "Wrong",
    "classify_d": "Empty",
    "classify_n": "None",
    "classify_e": "Error not detected",
    "nav_skip": "Skip",
    "nav_quit": "Quit and save",
    "nav_undo": "Undo last",
    "confirm_quit": "Are you sure you want to quit? (y/n): ",
    "saving_exiting": "Saving progress and exiting...",
    "nothing_to_undo": "Nothing to undo.",
    "undone_previous": "Undone: previous classification was {answer}",
    "review_complete": "Review complete!",
    "items_processed": "{count} items processed.",
    "classifications": "Classifications:",
    "no_pending": "No responses pending review.",
    "experiment_not_found": "Error: Experiment not found: {name}",
    "review_interrupted": "Review interrupted by user.",
    "error_during_review": "Error during review: {error}"
}
```

**Usage in ReviewUI:**
```python
class ReviewUI:
    def __init__(self, conn, language: str = "pt") -> None:
        self.conn = conn
        self._i18n = Localization(language)
        # ...

    def _display_header(self, item_number: int, total: int) -> None:
        header_text = Text()
        header_text.append(
            self._i18n.get("title"),
            style="bold blue"
        )
        header_text.append(
            f"  |  {self._i18n.get('item_progress', current=item_number, total=total)}",
            style="dim"
        )
        # ...
```

**CLI Flag:**
```python
# bcllm_review.py
parser.add_argument(
    "--language",
    choices=["pt", "en"],
    default="pt",
    help="UI language (Portuguese or English)"
)
```

### 5.3 Session Persistence

**Implementation Approach:**

```python
# src/review/session.py
@dataclass
class ReviewSession:
    """Persistent review session state."""
    session_id: str
    experiment_id: Optional[str]
    pending_items: list[str]  # response_ids
    current_index: int
    processed_count: int
    history: list[ClassificationHistory]
    created_at: str
    updated_at: str


class SessionManager:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create_session(self, experiment_id: Optional[str], pending_items: list[str]) -> ReviewSession:
        session = ReviewSession(
            session_id=generate_session_id(),
            experiment_id=experiment_id,
            pending_items=pending_items,
            current_index=0,
            processed_count=0,
            history=[],
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        self._save_session(session)
        return session

    def save_session(self, session: ReviewSession) -> None:
        session.updated_at = datetime.utcnow().isoformat()
        self._save_session(session)

    def _save_session(self, session: ReviewSession) -> None:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO review_sessions
            (session_id, experiment_id, pending_items_json, current_index,
             processed_count, history_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.session_id,
            session.experiment_id,
            json.dumps(session.pending_items),
            session.current_index,
            session.processed_count,
            json.dumps([h.__dict__ for h in session.history]),
            session.created_at,
            session.updated_at,
        ))
        self.conn.commit()

    def load_session(self, session_id: str) -> Optional[ReviewSession]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM review_sessions WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        if not row:
            return None

        return ReviewSession(
            session_id=row["session_id"],
            experiment_id=row["experiment_id"],
            pending_items=json.loads(row["pending_items_json"]),
            current_index=row["current_index"],
            processed_count=row["processed_count"],
            history=[ClassificationHistory(**h) for h in json.loads(row["history_json"])],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
```

**Schema:**
```sql
CREATE TABLE review_sessions (
    session_id TEXT PRIMARY KEY,
    experiment_id TEXT,
    pending_items_json TEXT NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    history_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);
```

**CLI Commands:**
```python
# Save session
bcllm --review-experiment exp-001 --save-session

# Resume session
bcllm --resume-session <session_id>

# List sessions
bcllm --list-sessions
```

### 5.4 Batch Classification

**Implementation Approach:**

```python
class ReviewUI:
    def __init__(self, conn) -> None:
        self._multi_select_mode = False
        self._selected_indices: set[int] = set()

    def _toggle_multi_select(self) -> None:
        """Toggle multi-select mode (M key)."""
        self._multi_select_mode = not self._multi_select_mode
        self._selected_indices.clear()

        mode_text = "ON" if self._multi_select_mode else "OFF"
        self._console.print(f"[cyan]Multi-select mode: {mode_text}[/cyan]")

    def _select_current_item(self) -> None:
        """Select/deselect current item in multi-select mode (Space key)."""
        if self._current_index in self._selected_indices:
            self._selected_indices.remove(self._current_index)
        else:
            self._selected_indices.add(self._current_index)

    def _classify_selected(self, classification: str) -> None:
        """Classify all selected items with same classification."""
        indices = sorted(self._selected_indices)

        for index in indices:
            item = self._pending_items[index]
            self._save_classification(item, classification)

        self._statistics.total_processed += len(indices)
        self._selected_indices.clear()
        self._multi_select_mode = False

        self._console.print(
            f"[green]✓ Classificados {len(indices)} itens como {classification}[/green]"
        )
```

**New Keyboard Shortcuts:**

| Key | Action | Mode |
|-----|--------|------|
| **M** | Toggle multi-select mode | All |
| **Space** | Select/deselect current item | Multi-select |
| **Enter** | Classify all selected (prompts for classification) | Multi-select |

---

## 6. Migration Path

### 6.1 Phase 1: Foundation (Week 1)

**Tasks:**
1. Extract localization strings to JSON files
2. Implement i18n framework
3. Add `--language` flag to CLI
4. Test Portuguese and English UIs

**Deliverables:**
- `src/review/localization/pt.json`
- `src/review/localization/en.json`
- `src/review/localization/i18n.py`
- Updated `ReviewUI.__init__` with language parameter

**Validation:**
- UI displays correctly in both languages
- All strings localized
- No hardcoded Portuguese strings

### 6.2 Phase 2: Undo Enhancement (Week 2)

**Tasks:**
1. Implement `ClassificationHistory` dataclass
2. Add undo stack to ReviewUI
3. Implement database rollback on undo
4. Add undo depth limit (50 items)
5. Test undo with multiple classifications

**Deliverables:**
- Updated `ReviewUI._save_classification` with history tracking
- New `ReviewUI._undo_last_classification` with rollback
- Unit tests for undo functionality

**Validation:**
- Multi-level undo works correctly
- Database state matches UI state after undo
- Undo depth limit enforced

### 6.3 Phase 3: Session Persistence (Week 3)

**Tasks:**
1. Create `review_sessions` table
2. Implement `SessionManager` class
3. Add `--save-session` and `--resume-session` flags
4. Implement session cleanup (auto-delete old sessions)
5. Test session save/resume

**Deliverables:**
- `src/review/session.py` with `ReviewSession` and `SessionManager`
- Database migration script
- Updated CLI with session commands

**Validation:**
- Sessions persist across process restarts
- Resume restores exact state (index, history, statistics)
- Old sessions cleaned up automatically

### 6.4 Phase 4: Batch Operations (Week 4)

**Tasks:**
1. Implement multi-select mode
2. Add batch classification logic
3. Add keyboard shortcuts (M, Space, Enter)
4. Test batch classification with various scenarios

**Deliverables:**
- Updated `ReviewUI` with multi-select support
- Unit tests for batch classification

**Validation:**
- Multi-select mode toggles correctly
- Batch classification applies to all selected items
- Statistics updated correctly

### 6.5 Phase 5: Search/Filter (Week 5)

**Tasks:**
1. Add `--filter-by-model` flag
2. Add `--filter-by-confidence` flag
3. Implement interactive filter mode
4. Test filtering with various criteria

**Deliverables:**
- Updated `ReviewUI.get_pending_by_experiment` with filter support
- CLI flags for filtering

**Validation:**
- Filters correctly limit review queue
- Multiple filters combine correctly
- Empty filter results handled gracefully

### 6.6 Phase 6: Polish & Testing (Week 6)

**Tasks:**
1. Write comprehensive unit tests (80%+ coverage)
2. Write integration tests
3. Performance testing (1000+ items)
4. Documentation updates
5. Bug fixes

**Deliverables:**
- Test suite with 80%+ coverage
- Performance benchmarks
- Updated documentation

**Validation:**
- All tests pass
- Performance meets targets (< 100ms save, < 500ms refresh)
- Documentation complete

---

## 7. Validation Criteria

### 7.1 Functional Validation

| Criterion | Test | Expected Result |
|-----------|------|-----------------|
| **Multi-Level Undo** | Classify 10 items, undo 5 times | Last 5 classifications reverted |
| **Database Rollback** | Classify, undo, query DB | DB state matches pre-classification |
| **Language Switch** | Run with `--language en` | All UI text in English |
| **Session Save** | Start review, `--save-session`, exit | Session persisted to DB |
| **Session Resume** | `--resume-session`, verify state | Exact state restored |
| **Batch Classify** | Select 5 items, classify as A | All 5 updated to A |
| **Filter by Model** | `--filter-by-model gpt-4` | Only gpt-4 responses shown |

### 7.2 Performance Validation

| Criterion | Test | Target |
|-----------|------|--------|
| **Classification Save** | Time to save single classification | < 100ms |
| **Screen Refresh** | Time to redraw screen | < 500ms |
| **Input Latency** | Key press to feedback | < 50ms |
| **Session Load** | Load session with 1000 items | < 1s |
| **Undo Latency** | Undo classification | < 100ms |

### 7.3 Data Integrity Validation

| Criterion | Test | Expected Result |
|-----------|------|-----------------|
| **Idempotency** | Classify same item 3 times | Last classification wins |
| **Correctness** | Classify as A (correct=B) | `is_correct = FALSE` |
| **Review Exclusion** | Classify item, restart review | Item not in queue |
| **Null Handling** | Classify as N | `manual_answer = NULL`, `is_correct = FALSE` |

### 7.4 UX Validation

| Criterion | Test | Expected Result |
|-----------|------|-----------------|
| **Language Consistency** | Review all UI text | All strings localized |
| **Error Visibility** | Trigger error | Error displayed in red |
| **Progress Accuracy** | Classify 10 items | Statistics show 10 processed |
| **Quit Confirmation** | Press Q | Y/N confirmation shown |
| **Undo Feedback** | Undo classification | Message shows previous classification |

---

## 8. Risk Assessment

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Undo Rollback Bugs** | Medium | High | Comprehensive tests, manual testing |
| **Session Corruption** | Low | High | Validation on load, backup sessions |
| **Performance Degradation** | Medium | Medium | Performance testing, optimization |
| **Localization Gaps** | High | Low | String audit, user feedback |

### 8.2 User Experience Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Language Confusion** | Medium | Low | Clear language flag, defaults |
| **Undo Confusion** | Low | Medium | Clear feedback messages |
| **Batch Mode Confusion** | Medium | Low | Clear mode indicator, help text |

### 8.3 Migration Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Data Loss** | Low | High | Backup before migration, rollback plan |
| **Breaking Changes** | Low | Medium | Backward-compatible CLI flags |
| **Timeline Slip** | Medium | Medium | Phased rollout, prioritize high-value features |

---

## 9. Success Metrics

### 9.1 Adoption Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Language Usage** | 20%+ use English | CLI telemetry |
| **Session Resume** | 30%+ sessions resumed | Session table |
| **Batch Operations** | 40%+ reviews use batch | Usage telemetry |
| **Undo Usage** | 50%+ reviews use undo | Undo stack telemetry |

### 9.2 Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Test Coverage** | 80%+ | Coverage report |
| **Bug Rate** | < 1 bug per 100 reviews | Issue tracker |
| **Performance** | All targets met | Performance tests |
| **User Satisfaction** | 4.5/5 stars | User survey |

### 9.3 Efficiency Metrics

| Metric | Baseline | Target | Improvement |
|--------|----------|--------|-------------|
| **Review Time per Item** | 10 seconds | 5 seconds | 50% faster |
| **Session Completion Rate** | 70% | 90% | 20% improvement |
| **Error Rate** | 5% | 2% | 60% reduction |

---

## 10. Conclusion

This V2 Adaptation Plan provides a comprehensive roadmap for evolving the Review UI from its current state to the target architecture. Key initiatives include:

**High Priority:**
1. Multi-level undo with database rollback
2. English UI option (i18n)
3. Session persistence (save/resume)

**Medium Priority:**
1. Batch classification
2. Service layer extraction

**Low Priority:**
1. Search/filter
2. Review notes
3. Export functionality

**Timeline:** 6 weeks (6 phases)

**Success Criteria:**
- All validation criteria met
- 80%+ test coverage
- Performance targets achieved
- Positive user feedback

---

**Document Complete**

All 5 Review UI domain documents have been created:
1. ✅ `docs/architecture/legacy-analysis/04-review-ui.md` — V1 Analysis
2. ✅ `docs/architecture/v2-current/04-review-ui.md` — V2 Current State
3. ✅ `docs/architecture/gap-reports/04-review-ui-gap.md` — Gap Report
4. ✅ `docs/architecture/to-be/04-review-ui-architecture.md` — Architecture & Contracts
5. ✅ `docs/architecture/v2-adaptation/04-review-ui-adaptation.md` — V2 Adaptation Plan
