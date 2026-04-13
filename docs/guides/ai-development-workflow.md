---
type: operational
audience: ai
last-validated: 2026-04-11
status: active
---

# AI Development Workflow

**Purpose:** Guide for AI agents working on this codebase  
**Scope:** Navigation, contracts, validation, Maestro orchestration, invariants

---

## How to Navigate This Codebase

### Entry Points

| When You Need To... | Start Here |
|---------------------|------------|
| Understand system purpose | `docs/architecture/overview.md` |
| Understand entities | `docs/architecture/conceptual-model.md` |
| Understand execution | `docs/architecture/execution-architecture.md` |
| Check invariants | `docs/contracts/` (all files) |
| See current implementation | `docs/reference/` (all files) |
| Check what's done vs planned | `docs/status/` (all files) |
| Find code | `src/` directory (see `docs/reference/module-structure.md`) |

### Code Organization

```
bcllm.py (CLI entry point)
    ↓
src/cli/ (CLI command modules — orchestration only)
    ↓
src/core/ (Business logic — Planner, Engine, Writer, Config)
    ↓
src/api/ (External API communication)
src/db/ (Database layer)
src/review/ (Manual review UI)
```

See `docs/reference/module-structure.md` for complete module map.

---

## Where Contracts Live

All system contracts are in `docs/contracts/`:

| Contract | What It Guarantees |
|----------|-------------------|
| `determinism.md` | Same config → same requests |
| `idempotency.md` | No duplicate data |
| `immutability.md` | Snapshots, plans, history cannot change |
| `configuration-hierarchy.md` | Config resolution order |
| `system-default-semantics.md` | "system-default" bypasses inheritance |
| `data-auditability.md` | Full traceability |
| `interaction-contracts.md` | Event emission, UI boundaries (placeholder) |

**Rule:** Contracts are **normative** — they are constraints, not suggestions.

---

## What Invariants Must Never Be Violated

### Absolute Invariants

1. **Determinism:** Same configuration must always produce the same set of API requests
2. **Idempotency:** Never generate duplicate data for same experiment/run/model/question
3. **Immutability:** Snapshots, execution plans, and historical data cannot be modified
4. **Explicit Over Implicit:** No inference, no ad-hoc execution, no hidden behavior
5. **Auditability:** All data must be traceable to its origin

### If You Detect a Violation

1. **Stop** — Do not proceed
2. **Document** — Show the violation explicitly (contract text + conflicting code)
3. **Flag** — Present to human for decision
4. **Wait** — Do not assume correctness
5. **Record** — If human clarifies, create ADR if architectural

---

## How to Validate Changes

### Before Committing

1. **Run tests:**
   ```bash
   pytest
   ```

2. **Check for linting:**
   ```bash
   # If linting is configured
   pylint src/
   ```

3. **Verify contracts:**
   - Does your change violate any contract in `docs/contracts/`?
   - If yes, stop and flag for human review

4. **Update reference docs (if implementation changed):**
   - `docs/reference/cli-commands.md` (if CLI changed)
   - `docs/reference/configuration-reference.md` (if .env settings changed)
   - `docs/reference/database-schema.md` (if schema changed)
   - `docs/reference/module-structure.md` (if modules added/removed)
   - `docs/reference/api-integration.md` (if API layer changed)

5. **Update status docs (if behavior changed):**
   - `docs/status/implementation-status.md`
   - `docs/status/known-issues.md`

---

## How to Use Maestro Orchestration

### When to Use Maestro

Maestro is used for **multi-phase, multi-agent implementations tasks**.

**Use Maestro when:**
- Implementing a new capability from the implementation checklist
- Task requires 2+ agents (e.g., architect + coder + reviewer)
- Task has clear phases (design → plan → execute → complete)

**Do NOT use Maestro when:**
- Fixing a simple bug (use direct implementation)
- Updating documentation (use direct implementation)
- Running tests or validation (use direct commands)

### Maestro Workflow

1. **Classify task complexity** (simple, medium, complex)
2. **Simple tasks** → Express workflow (1 agent, 1 phase)
3. **Medium/Complex** → Standard workflow (4 phases: Design, Plan, Execute, Complete)
4. **Follow implementation checklist** (`docs/architecture/v2-implementation-checklist.md`)
5. **Review with essence-guardian** before marking complete

### Maestro State

Maestro state files are in `docs/maestro/` and are **not part of the documentation system**. Do not modify them unless explicitly working on Maestro orchestration.

---

## What NOT to Do

### Never

- ❌ Assume behavior — if ambiguous, ask human
- ❌ Bypass contracts — they are constraints, not suggestions
- ❌ Introduce mutable global state — scope state to explicit entities
- ❌ Add implicit behavior — everything must be explicit and auditable
- ❌ Modify historical data — append-only for results
- ❌ Delete experiments, runs, or snapshots — soft delete only
- ❌ Change frozen configuration — experiments and runs are frozen
- ❌ Create duplicate data — use UNIQUE constraints + INSERT OR IGNORE
- ❌ Skip documentation updates — if code changes, update reference docs
- ❌ Use `system-default` incorrectly — it bypasses inheritance, doesn't inherit

### Before Making Changes

1. Read relevant contracts
2. Check if change violates any invariant
3. Review architecture docs for context
4. Check if similar code already exists
5. Plan your approach before coding

---

## Documentation Update Protocol

When you change code, update docs in this order:

1. **Reference docs** (describe what exists):
   - `docs/reference/cli-commands.md`
   - `docs/reference/configuration-reference.md`
   - `docs/reference/database-schema.md`
   - `docs/reference/module-structure.md`
   - `docs/reference/api-integration.md`

2. **Status docs** (track current condition):
   - `docs/status/implementation-status.md`
   - `docs/status/known-issues.md`

3. **Architecture docs** (only if concepts changed):
   - `docs/architecture/overview.md`
   - `docs/architecture/conceptual-model.md`
   - `docs/architecture/execution-architecture.md`
   - `docs/architecture/design-principles.md`

4. **Contracts** (only if invariants changed — rare):
   - Requires ADR
   - Requires human approval

---

## Code Style and Conventions

### General

- Python 3.10+
- Type hints required
- Docstrings for public APIs
- No mutable global state
- Explicit over implicit

### Testing

- Write tests for new functionality
- Maintain or improve coverage
- Tests are permanent artifacts

### Commits

- Clear, descriptive messages
- One logical change per commit
- Include test updates

---

## Related Documents

- [contracts/](../contracts/README.md) — System invariants
- [architecture/design-principles.md](../architecture/design-principles.md) — Philosophy
- [status/implementation-status.md](../status/implementation-status.md) — What exists
- [status/known-issues.md](../status/known-issues.md) — What needs attention

---

**This guide is for AI agents working on this codebase. If anything is unclear, flag it for human review.**
