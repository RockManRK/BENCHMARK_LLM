# name: "cli_null_semantics.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

## Mini Design Doc — CLI Null Semantics

---

### **CLI Null Semantics — Design Contract**

#### **Purpose**
Define a consistent and explicit interpretation of `null` values passed via CLI arguments.

---

#### **Definition**
- The literal string `null` (case-insensitive) represents an explicit absence of value.
- It must be normalized to Python `None`.

---

#### **Normalization Rule**
All optional CLI arguments must pass through a normalization step:

```python
"null" → None
```

---

#### **Resolution Timing**

| Category | Resolution |
|--------|------------|
| Immediate resolution | At experiment creation |
| Deferred resolution | At model/run execution |
| Mandatory fields | Reject `null` |

---

#### **Mandatory Fields**
The following arguments must never accept `null`:
- `--url`
- `--dataset-path`

Passing `null` must raise an explicit error.

---

#### **Persistence Rule**
- `None` values must be serialized as JSON `null`
- Never as string `"null"`

---

#### **UX Guarantees**
- No silent ignores
- No implicit fallbacks
- All `null` behavior is explicit and documented

---

### Null Semantics — Core Principle

The system already defines behavior for missing values.

Passing `null` via CLI must not introduce new logic paths.
It must simply normalize to `None` and trigger the same resolution
mechanisms used when a value is absent from all sources (CLI, env, config).

`null` is an explicit override to "no value", not a new state.

---

#### Reserved Literal

Only the literal string `null` (case-insensitive) has special semantics.

The string `none` MUST be treated as a regular string value and MUST NOT
be normalized to Python None.

Examples:
- "--reasoning null" → None
- "--reasoning none" → "none"

---