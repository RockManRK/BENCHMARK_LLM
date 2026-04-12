# name: "responses.md"
# version: 0.8
# Atenção!: nunca fazer alterações

---

## 🗄️ `responses` — TO‑BE FINAL

### Propósito
Registrar **uma execução concreta** de:
- um run
- uma variante
- uma pergunta (snapshot)

Com auditoria completa e deduplicação garantida.

---

### Schema proposto

```text
responses
─────────
response_id              TEXT PRIMARY KEY
run_id                   TEXT NOT NULL
variant_id               TEXT NOT NULL
snapshot_id              INTEGER NOT NULL

# Referência legível
model_id                 TEXT NOT NULL
question_id              TEXT NOT NULL

# Resultado
response_text            TEXT
selected_answer          TEXT
is_correct               BOOLEAN
finish_reason            TEXT

# Performance
latency_ms               INTEGER
input_tokens             INTEGER
output_tokens            INTEGER
total_tokens             INTEGER
cost                      REAL

# Auditoria mínima (SEMPRE)
provider_model_resolved  TEXT NOT NULL

# Auditoria estendida (OPCIONAL)
provider_parameters_effective JSON
provider_thinking_level  TEXT
provider_debug_payload   JSON

# Estado
status                   TEXT NOT NULL DEFAULT 'success'
created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

### 🔒 Constraint crítica de unicidade

```sql
UNIQUE (run_id, variant_id, snapshot_id)
```

📌 Isso garante:
- idempotência
- reexecução segura
- zero duplicação
- deduplicação correta

---

### Sobre `response_id`

👉 **Não usar INTEGER autoincrement.**

Opções boas:
- UUID v4
- Hash determinístico:

```text
response_id = hash(run_id + variant_id + snapshot_id)
```

📌 Isso elimina:
- colisões
- recriação de IDs
- bugs de limpeza de banco

---

## 🧠 O que esse design resolve

- Elimina confusão RUN vs iteration
- Simplifica o ExecutionPlan
- Simplifica o ResultWriter
- Simplifica queries
- Facilita auditoria
- Facilita comparação histórica
- Facilita retry

E o mais importante:

> **O banco passa a refletir exatamente o modelo mental do sistema.**

---