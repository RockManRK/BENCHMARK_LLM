# V2 Review UI Current State

**Document Type:** Current State Analysis
**Domain:** Review UI
**Version:** 1.0
**Date:** 2026-03-29
**Status:** As-Implemented

---

## 1. Overview

The V2 Review UI represents a **modular extraction** of the review functionality from the CLI module into a dedicated `src/review/` package. While maintaining the core keyboard-driven interaction model from V1, V2 introduces several architectural improvements including Rich console integration, enhanced statistics tracking, and explicit quit confirmation.

### 1.1 Key Characteristics

- **Module Extraction:** Dedicated `src/review/` package (separate from CLI)
- **Rich Console:** Full Rich library integration for formatted output
- **Enhanced Statistics:** Classification breakdown tracking (A:5, B:3, etc.)
- **Quit Confirmation:** Y/N confirmation before exiting
- **Cross-Platform:** Windows (msvcrt) + Linux (termios) support
- **Database Connection:** Direct SQLite connection (not DatabaseManager wrapper)

---

## 2. Architecture

### 2.1 Component Structure

```
src/
├── review/
│   ├── __init__.py              # Package initialization
│   └── review_ui.py             # Main review UI module (676 lines)
│       ├── ReviewItem           # Dataclass: response + question details
│       ├── ReviewStatistics     # Dataclass: enhanced statistics
│       └── ReviewUI             # Main class: interactive review interface
└── cli/
    └── bcllm_review.py          # CLI entry point for review commands
```

### 2.2 Module Separation

**V1 vs V2 Structure:**

| Aspect | V1 | V2 |
|--------|----|----|
| **Location** | `src_legacy/cli/review_ui.py` | `src/review/review_ui.py` |
| **Package** | Part of `cli` module | Dedicated `review` package |
| **CLI Entry** | Integrated in `main.py` | Separate `bcllm_review.py` |
| **Database** | `DatabaseManager` wrapper | Direct SQLite connection |

### 2.3 Execution Flow

```
User Input (bcllm --review-experiment <name>)
    ↓
src/cli/bcllm_review.py:main()
    ↓
get_database_connection()
    ↓
ReviewUI.__init__(conn)
    ↓
get_pending_by_experiment(experiment_id)
    ↓
Query: responses WHERE needs_review = 1
    ↓
Main Review Loop
    ├── _display_item() [Rich console]
    ├── _get_user_input()
    ├── _save_classification()
    └── Update statistics
    ↓
Database UPDATE (auto-save on each classification)
    ↓
Exit (Q key + confirmation) → Save progress
```

---

## 3. Current Implementation Status

### 3.1 Implemented Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Keyboard Input** | ✅ Implemented | A/B/C/D/N/E/S/Q/Z |
| **Auto-Save** | ✅ Implemented | Immediate database UPDATE |
| **Progress Tracking** | ✅ Enhanced | Classification breakdown added |
| **Undo Support** | ✅ Implemented | Single-level (same as V1) |
| **Quit Confirmation** | ✅ Implemented | Y/N confirmation (new in V2) |
| **Rich Console** | ✅ Implemented | Panels, tables, styled text |
| **Cross-Platform** | ✅ Implemented | Windows + Linux |
| **Review by Experiment** | ✅ Implemented | `--review-experiment <name>` |
| **Review All** | ✅ Implemented | `--review-all` |

### 3.2 Review Fields Implementation

**Database Schema (responses table):**

```sql
-- Parser confidence (set by ExecutionEngine)
parse_confidence TEXT DEFAULT 'unknown'
-- Values: 'unknown', 'clear', 'ambiguous', 'no_answer', 'low_confidence'

-- Review flag (derived by ResultWriter)
needs_review BOOLEAN NOT NULL DEFAULT FALSE

-- Human-corrected answer (set by reviewer)
manual_answer TEXT
```

**Review Trigger Logic:**

```python
# In ResultWriter, before INSERT
needs_review = (
    parse_confidence in ('ambiguous', 'no_answer', 'low_confidence')
    OR selected_answer IS NULL
)
```

---

## 4. CLI Integration

### 4.1 CLI Entry Point

**File:** `src/cli/bcllm_review.py`

```python
#!/usr/bin/env python3
"""CLI entry point for manual review interface.

Usage:
    bcllm --review-experiment <experiment_name>
    bcllm --review-all
"""

import argparse
import sys

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.review.review_ui import ReviewUI
```

### 4.2 Command Definitions

**Mutually Exclusive Group:**

```python
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bcllm_review.py",
        description="Manual review interface for LLM responses",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--review-experiment",
        metavar="NAME",
        help="Start review interface for an experiment",
    )
    group.add_argument(
        "--review-all",
        action="store_true",
        help="Start review interface for all pending responses",
    )

    return parser
```

### 4.3 Command Handlers

**Review Experiment:**

```python
def handle_review_experiment(args, conn) -> int:
    experiment_name = args.review_experiment

    if not experiment_name or not experiment_name.strip():
        print("Error: Experiment name cannot be empty.", file=sys.stderr)
        return 1

    try:
        ui = ReviewUI(conn)
        ui.start_review_by_experiment(experiment_name)
        return 0
    except KeyboardInterrupt:
        print("\n\n[yellow]Review interrupted by user.[/yellow]")
        return 0
    except Exception as e:
        print(f"Error during review: {e}", file=sys.stderr)
        return 1
```

**Review All:**

```python
def handle_review_all(args, conn) -> int:
    try:
        ui = ReviewUI(conn)
        ui.start_review_all()
        return 0
    except KeyboardInterrupt:
        print("\n\n[yellow]Review interrupted by user.[/yellow]")
        return 0
    except Exception as e:
        print(f"Error during review: {e}", file=sys.stderr)
        return 1
```

### 4.4 Mode Validation

**Dispatcher Integration:**

```python
def _validate_expected_mode(mode: Mode) -> None:
    VALID_MODES = [Mode.INVALID]

    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"This indicates a dispatcher bug. Please report this issue.",
            file=sys.stderr
        )
        sys.exit(1)
```

---

## 5. UI Implementation

### 5.1 Rich Console Integration

**Console Initialization:**

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

class ReviewUI:
    def __init__(self, conn) -> None:
        self.conn = conn
        self._response_repository = ResponseRepository(conn)
        self._console = Console()
```

### 5.2 Display Components

**Header Panel:**

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

    self._console.print(Panel(
        Text("\n").join([header_text, stats_text]),
        title=f"Experiment: {self._experiment_name}",
        border_style="blue",
    ))
```

**Info Table:**

```python
info_table = Table(show_header=False, box=None, padding=(0, 1))
info_table.add_column("Label", style="bold cyan")
info_table.add_column("Value", style="white")

info_table.add_row("Pergunta:", item.response.question_id)
info_table.add_row("Modelo:", item.response.model_id)
info_table.add_row("Resposta Correta:", item.correct_answer)
info_table.add_row("Status:", item.response.parse_confidence.upper())
```

**Question Panel:**

```python
question_panel = Panel(
    Text(item.question_stem, style="white"),
    title="[bold]ENUNCIADO[/bold]",
    border_style="cyan",
)
```

**Options Panel:**

```python
options_table = Table(show_header=False, box=None, padding=(0, 1))
options_table.add_column("Key", style="bold yellow", width=3)
options_table.add_column("Value", style="white")

for key, value in sorted(item.question_options.items()):
    options_table.add_row(f"{key})", value)

options_panel = Panel(
    options_table,
    title="[bold]ALTERNATIVAS[/bold]",
    border_style="yellow",
)
```

**Response Panel:**

```python
response_text = item.response.response_text or "(no response)"
if len(response_text) > 800:
    response_text = response_text[:800] + "\n\n... (truncado)"

response_panel = Panel(
    Text(response_text, style="dim white"),
    title="[bold]RESPOSTA DA LLM[/bold]",
    border_style="dim",
)
```

**Controls Panel:**

```python
classification_table = Table(show_header=False, box=None, padding=(0, 2))
classification_table.add_column("Key", style="bold green", width=10)
classification_table.add_column("Action", style="white")

classification_table.add_row("[A]", "Correta")
classification_table.add_row("[B]", "Parcial")
classification_table.add_row("[C]", "Errada")
classification_table.add_row("[D]", "Vazia")
classification_table.add_row("[N]", "Nenhuma")
classification_table.add_row("[E]", "Erro não detectado")

navigation_table = Table(show_header=False, box=None, padding=(0, 2))
navigation_table.add_column("Key", style="bold cyan")
navigation_table.add_column("Action", style="dim")

navigation_table.add_row("[S]", "Pular")
navigation_table.add_row("[Q]", "Sair e salvar")
navigation_table.add_row("[Z]", "Desfazer última")

controls_panel = Panel(
    Text("\n").join([
        Text("CLASSIFICAÇÃO:", style="bold"),
        classification_table,
        Text("\nNAVIGAÇÃO:", style="bold"),
        navigation_table,
    ]),
    border_style="green",
)
```

### 5.3 Screen Layout (V2)

```
╭──────────────────────────────────────────────────────────────────────────────╮
│ REVIEW MANUAL DE RESPOSTAS  |  Item 1/23                                    │
│                                                                              │
│ Pendentes: 23  |  Processadas: 0  |  A: 0, B: 0, C: 0                       │
╰──────────────────────────────────────────────────────────────────────────────╯

┌──────────────────────────────────────────────────────────────────────────────┐
│ Pergunta:       Q001                                                         │
│ Modelo:         liquid/lfm-2.5-1.2b-thinking                                 │
│ Resposta Correta: A                                                          │
│ Status:         AMBIGUOUS                                                    │
└──────────────────────────────────────────────────────────────────────────────┘

╭──────────────────────────────────────────────────────────────────────────────╮
│ ENUNCIADO                                                                    │
│                                                                              │
│ Homem de 45 anos foi encontrado inconsciente...                              │
╰──────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────╮
│ ALTERNATIVAS                                                                 │
│                                                                              │
│ A)  tomografia de crânio, face e coluna cervical...                          │
│ B)  radiografia de crânio e face...                                          │
│ C)  radiografia de crânio, coluna cervical...                                │
│ D)  tomografia de crânio, face e radiografia...                              │
╰──────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────╮
│ RESPOSTA DA LLM                                                              │
│                                                                              │
│ Okay, let me tackle this question...                                         │
│ ANSWER: \boxed{C}                                                            │
╰──────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────╮
│ CLASSIFICAÇÃO:                                                               │
│                                                                              │
│ [A]          Correta                                                         │
│ [B]          Parcial                                                         │
│ [C]          Errada                                                          │
│ [D]          Vazia                                                           │
│ [N]          Nenhuma                                                         │
│ [E]          Erro não detectado                                              │
│                                                                              │
│ NAVEGAÇÃO:                                                                   │
│                                                                              │
│ [S]          Pular                                                           │
│ [Q]          Sair e salvar                                                   │
│ [Z]          Desfazer última                                                 │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## 6. Enhanced Statistics

### 6.1 Statistics Dataclass

**V2 Enhancement:**

```python
@dataclass
class ReviewStatistics:
    total_pending: int = 0
    total_processed: int = 0
    by_classification: dict[str, int] = field(default_factory=dict)  # NEW in V2
    by_question: dict[str, int] = field(default_factory=dict)
    by_model: dict[str, int] = field(default_factory=dict)
```

### 6.2 Classification Tracking

**On Classification:**

```python
if user_input in ("A", "B", "C", "D", "N", "E"):
    class_count = self._statistics.by_classification.get(user_input, 0)
    self._statistics.by_classification[user_input] = class_count + 1
    self._statistics.total_processed += 1
    self._current_index += 1
```

**Display Format:**
```
Pendentes: 23  |  Processadas: 10  |  A: 5, B: 3, C: 2
```

### 6.3 Completion Summary

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

**Example Output:**
```
╭──────────────────────────────────────────────────────────────────────────────╮
│ Resumo                                                                       │
│                                                                              │
│ Revisão concluída!                                                           │
│                                                                              │
│ 10 itens processados.                                                        │
│                                                                              │
│ Classificações:                                                              │
│   A: 5                                                                       │
│   B: 3                                                                       │
│   C: 2                                                                       │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## 7. Quit Confirmation (V2 Enhancement)

### 7.1 Confirmation Dialog

**New in V2:**

```python
def _confirm_quit(self) -> bool:
    """Ask user to confirm quit.

    Returns:
        True if user confirms quit, False otherwise.
    """
    self._console.print()
    self._console.print("[yellow]Tem certeza que deseja sair? (y/n): [/yellow]", end="")

    char = self._get_user_input()
    self._console.print(char)

    return char == "Y"
```

### 7.2 Usage in Main Loop

```python
elif user_input == "Q":
    if self._confirm_quit():
        self._console.print("\n[yellow]Salvando progresso e saindo...[/yellow]")
        break
    # else: continue review loop
```

**Benefit:** Prevents accidental exits from losing review progress.

---

## 8. Database Integration

### 8.1 Connection Pattern

**V2 Pattern:**

```python
def __init__(self, conn) -> None:
    """Initialize the ReviewUI.

    Args:
        conn: SQLite database connection.
    """
    self.conn = conn
    self._response_repository = ResponseRepository(conn)
```

**Contrast with V1:**
- V1: `DatabaseManager` wrapper
- V2: Direct SQLite connection

### 8.2 Repository Usage

**ResponseRepository:**

```python
from src.db.repository import ResponseRepository

self._response_repository = ResponseRepository(conn)
```

**Note:** Current implementation uses direct SQL queries, not repository methods. Repository is initialized but not actively used for review operations.

### 8.3 Query for Pending Items

**By Experiment:**

```python
def get_pending_by_experiment(self, experiment_id: str) -> list[ReviewItem]:
    cursor = self.conn.cursor()
    cursor.execute("""
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
    """, (experiment_id,))
```

**All Pending:**

```python
def start_review_all(self) -> None:
    cursor = self.conn.cursor()
    cursor.execute("""
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
    """)
```

---

## 9. Save Mechanism

### 9.1 Classification Save

```python
def _save_classification(self, item: ReviewItem, classification: str) -> None:
    if classification == "S":
        return  # Skip - don't save

    cursor = self.conn.cursor()

    if classification in ("A", "B", "C", "D"):
        item.response.manual_answer = classification
        item.response.needs_review = False
        item.response.selected_answer = classification
        item.response.is_correct = (classification.upper() == item.correct_answer.upper())
    elif classification == "N":
        item.response.manual_answer = None
        item.response.needs_review = False
        item.response.selected_answer = None
        item.response.is_correct = False
    elif classification == "E":
        item.response.manual_answer = None
        item.response.needs_review = False
        item.response.selected_answer = None
        item.response.is_correct = False

    cursor.execute("""
        UPDATE responses
        SET manual_answer = ?, needs_review = ?,
            selected_answer = ?, is_correct = ?
        WHERE response_id = ?
    """, (
        item.response.manual_answer,
        0,  # needs_review = FALSE
        item.response.selected_answer,
        item.response.is_correct,
        item.response.response_id,
    ))
    self.conn.commit()

    classification_label = self.CLASSIFICATION_LABELS.get(classification, classification)
    self._console.print(f"[green]✓[/green] Classificado como [bold]{classification}[/bold] ({classification_label})")
```

### 9.2 Classification Labels

**V2 Enhancement:**

```python
CLASSIFICATION_LABELS = {
    "A": "Correct",
    "B": "Partial",
    "C": "Wrong",
    "D": "Empty",
    "N": "None",
    "E": "Error",
}
```

**Feedback Display:**
```
✓ Classificado como A (Correct)
```

---

## 10. Undo Mechanism

### 10.1 History Tracking

```python
def __init__(self, conn) -> None:
    self._history: list[tuple[int, str]] = []  # (index, previous_status)
```

**On Classification:**

```python
if user_input in ("A", "B", "C", "D", "N", "E"):
    previous_answer = item.response.manual_answer or item.response.selected_answer or "None"
    self._history.append((self._current_index, previous_answer))
```

**On Undo (Z key):**

```python
elif user_input == "Z":
    if self._current_index > 0:
        self._current_index -= 1
        self._statistics.total_processed -= 1

        if self._history:
            prev_index, prev_answer = self._history.pop()
            if prev_index == self._current_index:
                self._console.print(f"[yellow]Desfeito: classificação anterior era {prev_answer}[/yellow]")
    else:
        self._console.print("\n[yellow]Nada para desfazer.[/yellow]")
        input("Pressione Enter para continuar...")
```

---

## 11. Language Consistency

### 11.1 Current State

**UI Language:** Portuguese (same as V1)

| Element | Language |
|---------|----------|
| UI Text | Portuguese |
| CLI Commands | English |
| Error Messages | English |
| Classification Labels | English (in code), Portuguese (in display) |

### 11.2 Inconsistency Notes

**Mixed Language Example:**

```python
# Code labels (English)
CLASSIFICATION_LABELS = {
    "A": "Correct",
    "B": "Partial",
    "C": "Wrong",
}

# Display text (Portuguese)
classification_table.add_row("[A]", "Correta")
```

**Impact:**
- Internal consistency in code (English labels)
- User-facing UI remains Portuguese-only
- Same language inconsistency as V1

---

## 12. Key V2 Patterns Summary

### 12.1 Architectural Improvements

| Improvement | V1 | V2 | Benefit |
|-------------|----|----|---------|
| **Module Separation** | Part of CLI | Dedicated package | Separation of concerns |
| **CLI Entry Point** | Integrated in main.py | Separate bcllm_review.py | Clear responsibility |
| **Console Output** | Print statements | Rich library | Better formatting |
| **Statistics** | Basic counts | Classification breakdown | More insight |
| **Quit Confirmation** | None | Y/N confirmation | Prevents accidents |
| **Database Access** | DatabaseManager | Direct connection | Simpler dependency |

### 12.2 Unchanged from V1

| Aspect | Status | Notes |
|--------|--------|-------|
| **Keyboard Interface** | Unchanged | Same A/B/C/D/N/E/S/Q/Z |
| **Auto-Save** | Unchanged | Immediate database UPDATE |
| **Undo Depth** | Unchanged | Single-level only |
| **Language** | Unchanged | Portuguese UI |
| **Response Truncation** | Unchanged | 800-char limit |
| **Review Trigger** | Unchanged | `needs_review = 1` |

### 12.3 Technical Debt

| Issue | Status | Severity |
|-------|--------|----------|
| **Portuguese-only UI** | Unchanged | Medium |
| **Single-level undo** | Unchanged | Low |
| **No batch operations** | Unchanged | Low |
| **No export/review later** | Unchanged | Medium |
| **Repository not used** | New (potential issue) | Low |

---

## 13. Files Analyzed

### 13.1 Core Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/review/review_ui.py` | 676 | Main review UI module |
| `src/review/__init__.py` | 1 | Package initialization |
| `src/cli/bcllm_review.py` | ~150 | CLI entry point |
| `docs/architecture/contracts/result-writer.md` | ~200 | Review fields contract |
| `docs/architecture/contracts/domain-review-contract.md` | ~250 | Review domain contract |

---

## 14. Conclusion

The V2 Review UI represents a **modular extraction and incremental improvement** over V1:

**Improvements:**
1. **Separation of Concerns** — Dedicated `src/review/` package
2. **Enhanced UX** — Rich console formatting, classification breakdown
3. **Safety** — Quit confirmation prevents accidental exits
4. **Clear Entry Point** — Separate `bcllm_review.py` for review commands

**Unchanged:**
1. **Keyboard Interface** — Same efficient single-key shortcuts
2. **Auto-Save** — Immediate persistence on classification
3. **Language** — Portuguese UI remains
4. **Undo Limitations** — Single-level undo only

**Gaps to Address:**
1. **Internationalization** — Consider English option or full translation
2. **Undo Depth** — Multi-level undo with database rollback
3. **Batch Operations** — Select multiple for same classification
4. **Export/Import** — Review session export for later continuation

---

**Next Document:** `docs/architecture/gap-reports/04-review-ui-gap.md` — V1 vs V2 Gap Analysis
