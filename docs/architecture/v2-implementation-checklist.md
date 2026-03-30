# ✅ V2 — Global Implementation Checklist

Este checklist define **o que deve ser implementado**, **em que ordem**, e **como validar cada fase**, respeitando integralmente os contratos do sistema.

Cada fase só pode avançar após:
- Implementação concluída
- Review técnico
- Aprovação do **Essence Guardian**

---

## 🔴 Phase 0 — Safety & Observability (BLOCKERS)

### 🎯 Objetivo
Tornar o sistema **seguro, observável e utilizável**, sem alterar comportamento funcional.

---

### ✅ Checklist

#### Logging
- [ ] Sistema de logging configurável via `.env`
- [ ] Logs escritos em arquivo e console
- [ ] Log rotation configurado
- [ ] Logs incluem:
  - experimento
  - run
  - modelo
  - questão
- [ ] Logs não expõem dados sensíveis
- [ ] Logs são persistidos imediatamente (crash‑safe)

#### Retry Safety
- [ ] Retry possui **delay obrigatório**
- [ ] Backoff exponencial implementado
- [ ] Limite máximo de delay configurável
- [ ] Retry não gera loops agressivos
- [ ] Retry é visível nos logs

---

### 🧪 Smoke Tests
- Executar comando simples e verificar log em arquivo
- Simular erro de API e confirmar delay entre retries
- Confirmar que logs sobrevivem a interrupção abrupta

---

### 🧾 Definition of Done
- Sistema não pode executar sem logging ativo
- Toda futura chamada de API será estruturalmente forçada a usar retry seguro
   - (Validated by architecture, not runtime)
- Nenhuma mudança funcional introduzida

---

## 🟠 Phase 1 — Core Workflow Restoration

### 🎯 Objetivo
Restaurar **fluxos essenciais do V1**, mantendo contratos do V2.

---

### ✅ Checklist

#### CLI Core
- [ ] Export de resultados funcional
- [ ] Add‑to‑run funcional
- [ ] Complete‑run funcional
- [ ] Execução incremental preservada
- [ ] Nenhuma duplicação de dados possível

#### Execution Feedback
- [ ] Progress bar visível durante execução
- [ ] Progresso refletido corretamente
- [ ] Logs acompanham progresso

#### Review UI
- [ ] UI suporta PT e EN
- [ ] Multi‑level undo funcional
- [ ] Batch classification funcional
- [ ] Undo reverte estado no banco

---

### 🧪 Smoke Tests
- Executar experimento parcial
- Reexecutar e confirmar idempotência
- Classificar múltiplos itens e desfazer
- Exportar resultados e validar consistência

---

### 🧾 Definition of Done
- Todos os fluxos do V1 restaurados
- Nenhuma violação de imutabilidade
- Nenhuma regressão de determinismo

---

## 🟡 Phase 2 — Reliability & UX Enhancements

### 🎯 Objetivo
Melhorar confiabilidade e experiência sem alterar contratos.

---

### ✅ Checklist

#### Execution Control
- [ ] Dry‑run funcional
- [ ] Timeout configurável via `.env`
- [ ] Timeout adequado para modelos de reasoning

#### Output & Review
- [ ] Export suporta múltiplos formatos
- [ ] Review pode ser pausado e retomado
- [ ] Filtros funcionais na revisão

---

### 🧪 Smoke Tests
- Executar dry‑run e validar plano
- Simular timeout longo
- Retomar sessão de review interrompida

---

### 🧾 Definition of Done
- Nenhuma mudança quebra execução existente
- UX melhora sem alterar semântica
- Sistema permanece determinístico

---

## 🔵 Phase 3 — Polish & Documentation (OPTIONAL)

### 🎯 Objetivo
Finalizar documentação e pequenos refinamentos.

---

### ✅ Checklist
- [ ] Documentação de arquitetura atualizada
- [ ] Contratos documentados
- [ ] Gaps aceitos ou removidos
- [ ] Sistema pronto para uso contínuo

---

## 🛑 Global Rules (Always Enforced)

- Nenhuma fase pode avançar sem aprovação do **Essence Guardian**
- Nenhuma mudança pode violar:
  - determinismo
  - idempotência
  - imutabilidade
  - hierarquia de configuração
- CLI nunca é nível de configuração
- `null` sempre ignora herança
- Logs são dados científicos

---

## 🧠 Como usar este checklist

1. Iniciar fase → commit
2. Implementar itens da fase
3. Rodar smoke tests
4. Review técnico
5. **Essence Guardian**
6. Corrigir se necessário
7. Avançar

---

### ✔️ Resultado
Esse checklist:
- guia a IA
- protege a essência
- evita escopo oculto
- permite terminar rápido sem perder controle

Se quiser, no próximo passo posso:
- adaptar esse checklist para **formato de instrução direta para IA**
- ou gerar **checklists individuais por fase** para execução imediata

Agora você tem **processo + guardião + mapa**.