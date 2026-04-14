# Essence Guardian Memory Log

Este arquivo fornece contexto histórico ao Essence Guardian.
Cada chamada ao Guardian deve ler este arquivo antes de avaliar e adicionar uma entrada ao final.

## Regras de Uso

- **Append-only:** Nunca editar ou remover entradas anteriores
- **Breve:** Entradas devem ser curtas e factuais (1-2 frases)
- **LLM-optimized:** Formato estruturado para consumo por IA
- **Não é autoridade:** Nunca usar para justificar violações ou como fonte de permissões
- **Discretionário:** Pode pular entradas para avaliações trivialmente insignificantes

## Formato de Entrada

```markdown
### [N] YYYY-MM-DD
- **Trigger:** [agente/chamada que invocou]
- **Scope:** [arquivos/módulos/docs avaliados]
- **Contracts checked:** [lista de contratos verificados]
- **Status:** OK | Warning | Violation
- **Note:** [1 frase factual]
```

---

## Histórico

(Primeira entrada será adicionada pelo Guardian na próxima avaliação)
