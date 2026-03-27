# Manual Review Interface

## Overview

The Manual Review Interface provides a keyboard-driven CLI for reviewing and classifying LLM responses that couldn't be automatically parsed with high confidence.

## Usage

### Review Experiment

```bash
bcllm --review-experiment <experiment_name>
```

### Review All Pending

```bash
bcllm --review-all
```

## Keyboard Shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| **A** | Classify | Mark as correct answer |
| **B** | Classify | Mark as partial answer |
| **C** | Classify | Mark as wrong answer |
| **D** | Classify | Mark as empty answer |
| **N** | Classify | Mark as no clear answer |
| **E** | Classify | Mark as error (technical issue) |
| **S** | Skip | Skip to next item |
| **Q** | Quit | Quit and save progress |
| **Z** | Undo | Undo last classification |

## Classification Types

| Classification | Code | Description |
|---------------|------|-------------|
| Correct | A | Response correctly identifies the answer |
| Partial | B | Response partially addresses the question |
| Wrong | C | Response identifies incorrect answer |
| Empty | D | Response is empty or blank |
| None | N | No clear answer can be determined |
| Error | E | Technical error occurred (not detected by parser) |

## Interface Features

### Real-time Statistics

The interface displays:
- Total pending items
- Processed items count
- Classification breakdown (A/B/C/D/N/E counts)
- Current item progress

### Display Information

For each item, the interface shows:
- Question stem (enunciado)
- Answer options (A, B, C, D)
- Model response (truncated at 800 chars if longer)
- Current classification status
- Model identifier
- Parse confidence level

### Incremental Persistence

- Changes are saved immediately to the database
- Each classification updates the response record
- Progress is preserved on quit
- Supports resuming interrupted sessions

## Database Updates

When a classification is saved, the following fields are updated:

| Field | Description |
|-------|-------------|
| `manual_answer` | Human-classified answer (A/B/C/D or NULL) |
| `needs_review` | Set to FALSE after classification |
| `selected_answer` | Updated with manual classification |
| `is_correct` | Recalculated based on manual answer |

## Workflow

1. **Launch**: Start review with `--review-experiment` or `--review-all`
2. **Read**: Review the question, options, and model response
3. **Classify**: Press appropriate key (A/B/C/D/N/E)
4. **Advance**: Interface automatically moves to next item
5. **Undo**: Use Z to undo last classification if needed
6. **Quit**: Press Q to save progress and exit

## Cross-Platform Support

The interface uses the `rich` library for cross-platform terminal support:
- **Windows**: Uses `msvcrt` for keyboard input
- **Linux/Mac**: Uses `termios` for keyboard input

## Technical Implementation

### Files

- `src_v2/review/review_ui.py` - Main review UI implementation
- `src_v2/cli/bcllm_review.py` - CLI entry point
- `tests/unit/review/test_review_ui.py` - Unit tests

### Dependencies

- `rich` - Terminal UI rendering
- `msvcrt` (Windows) / `termios` (Linux) - Keyboard input

### Architecture

```
┌─────────────────────────────────────┐
│         CLI Entry Point             │
│      (bcllm_review.py)              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│          ReviewUI                   │
│  - Keyboard input handling          │
│  - Display rendering (rich)         │
│  - Classification logic             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│       Database (SQLite)             │
│  - responses table                  │
│  - question_snapshots table         │
└─────────────────────────────────────┘
```

## Example Session

```
================================================================================
REVIEW MANUAL DE RESPOSTAS  |  Item 1/23
================================================================================
Pendentes: 23  |  Processadas: 0
================================================================================

Pergunta: 1
Modelo: openai/gpt-4
Resposta Correta: B
Status: AMBIGUOUS

┌ ENUNCIADO ───────────────────────────────────────────────────────────────────┐
│ What is the capital of France?                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌ ALTERNATIVAS ────────────────────────────────────────────────────────────────┐
│ A) London                                                                    │
│ B) Paris                                                                     │
│ C) Berlin                                                                    │
│ D) Madrid                                                                    │
└──────────────────────────────────────────────────────────────────────────────┘

┌ RESPOSTA DA LLM ─────────────────────────────────────────────────────────────┐
│ The capital of France is Paris. This is a well-known fact...                │
│ ANSWER: \boxed{B}                                                            │
└──────────────────────────────────────────────────────────────────────────────┘

┌ CLASSIFICAÇÃO ───────────────────────────────────────────────────────────────┐
│ [A]  Correta                                                                 │
│ [B]  Parcial                                                                 │
│ [C]  Errada                                                                  │
│ [D]  Vazia                                                                   │
│ [N]  Nenhuma                                                                 │
│ [E]  Erro não detectado                                                      │
│                                                                              │
│ NAVIGAÇÃO                                                                    │
│ [S]  Pular                                                                   │
│ [Q]  Sair e salvar                                                          │
│ [Z]  Desfazer última                                                        │
└──────────────────────────────────────────────────────────────────────────────┘

Sua escolha: _
```

## Best Practices

1. **Review in batches**: Set aside dedicated time for review sessions
2. **Use undo liberally**: If you misclick, use Z to undo immediately
3. **Check low confidence first**: Items with `ambiguous` or `no_answer` confidence are most likely to need correction
4. **Skip uncertain items**: Use S to skip and return later if unsure
5. **Save progress**: Use Q to save and exit when needed

## Troubleshooting

### Keyboard input not working

- **Windows**: Ensure terminal supports `msvcrt` (standard Command Prompt or PowerShell)
- **Linux/Mac**: Ensure terminal supports `termios`

### Display issues

- Ensure terminal supports ANSI colors
- Try resizing terminal window if display is corrupted
- Minimum recommended: 80x24 characters

### Database errors

- Ensure database file is not locked by another process
- Check that database schema is initialized

## Related Documentation

- `docs/architecture/contracts/domain-review-contract.md` - Review domain contract
- `docs/architecture/to-be/comandos_simples.md` - CLI commands specification
