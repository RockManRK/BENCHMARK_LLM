# name: "cli_null_semantics.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

## Mini Design Doc — CLI System Default (system-default) Semantics

---

### **CLI System Default (system-default) Semantics — Design Contract**

#### **Purpose**
Define a consistent and explicit interpretation of `"system-default"` values passed via CLI arguments.

---

#### **Definition**
- The literal string `"system-default"` (case-insensitive) represents an explicit instruction to force system default behavior.
- It must be normalized to Python `None` (which means "omit from API request").

---

#### **Normalization Rule**
All optional CLI arguments must pass through a normalization step:

```python
"system-default" → None
```

---

#### **Resolution Timing**

| Category | Resolution |
|--------|------------|
| Immediate resolution | At experiment creation |
| Deferred resolution | At model/run execution |
| Mandatory fields | Reject `"system-default"` |

---

#### **Mandatory Fields**
The following arguments must never accept `"system-default"`:
- `--url`
- `--dataset-path`
- `--create-experiment`
- `--add-model`
- `--remove-model`
- `--add-run`
- `--remove-run`
- `--execute`

Passing `"system-default"` must raise an explicit error.

---

#### **Persistence Rule**
- `None` values must be serialized as JSON `null`
- Never as string `"system-default"`

---

#### **UX Guarantees**
- No silent ignores
- No implicit fallbacks
- All `"system-default"` behavior is explicit and documented

---

### System Default (system-default) Semantics — Core Principle

The system already defines behavior for missing values.

Passing `"system-default"` via CLI must not introduce new logic paths.
It must simply normalize to `None` and trigger the same resolution
mechanisms used when a value is absent from all sources (CLI, env, config).

`"system-default"` is an explicit override to "no value", not a new state.

---

#### Reserved Literal

Only the literal string `"system-default"` (case-insensitive) has special semantics.

The string `"none"` MUST be treated as a regular string value and MUST NOT
be normalized to Python None.

Examples:
- "--reasoning system-default" → None
- "--reasoning none" → "none"

---

### Deprecation Notice

**Legacy `"null"` Literal**: The old `"null"` literal is deprecated and no longer supported. Users must migrate to `"system-default"`.

**Migration**: Replace all instances of `'null'` with `'system-default'` in your CLI commands.