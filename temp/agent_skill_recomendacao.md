Eu mudaria a arquitetura.

O seu `essence-guardian` antigo fazia três coisas diferentes ao mesmo tempo:

1. definia a **identidade/comportamento** do Guardian;
2. descrevia a **base normativa do projeto**;
3. definia **como e quando ele deveria ser chamado**.

Isso funcionava no Qwen porque você tinha folga de contexto. No Codex, eu separaria essas responsabilidades para economizar contexto e tokens.

E há uma notícia muito boa: **o Codex atual já tem exatamente os mecanismos necessários para isso**. Ele suporta Skills com *progressive disclosure*, subagentes e agentes personalizados com modelo, nível de raciocínio e sandbox próprios. ([OpenAI Developers][1])

## O que eu mudaria

### 1. O `essence-guardian` deveria virar um **Custom Agent**, não apenas uma Skill

Seu Guardian não é apenas uma "habilidade".

Ele tem uma identidade muito específica:

> "Eu sou o gatekeeper. Não implemento. Só avalio."

Isso aparece logo no início do arquivo que você enviou, inclusive com a regra explícita de ser usado **depois da implementação como quality gate**. 

E depois você reforça isso várias vezes: ele não pode escrever código, não pode propor refatorações e não pode relaxar contratos. 

Isso se encaixa **perfeitamente** no conceito atual de Custom Agent do Codex.

Hoje você pode ter algo como:

```text
.codex/
└── agents/
    └── essence-guardian.toml
```

E esse agente pode ter:

```toml
name = "essence_guardian"
description = "Read-only gatekeeper that verifies project contracts after significant changes."
model = "gpt-5.6-luna"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"

developer_instructions = """
You are the Essence Guardian...

Do not modify files.
Do not implement fixes.
Evaluate only.

...
"""
```

O Codex permite exatamente esse tipo de agente personalizado, inclusive com **modelo diferente do agente principal** e `sandbox_mode = "read-only"`. ([OpenAI Developers][2])

Isso é uma evolução muito boa do que você fazia no Qwen.

---

# 2. Eu NÃO colocaria toda a essência do projeto dentro do agente

Aqui está, para mim, a maior oportunidade de economia.

Seu arquivo atual contém os sete contratos fundamentais diretamente no próprio Guardian. Por exemplo, determinismo, imutabilidade, hierarquia de configuração etc. 

Eu faria:

```text
docs/
└── contracts/
    ├── configuration-hierarchy.md
    ├── data-auditability.md
    ├── determinism.md
    ├── idempotency.md
    ├── immutability.md
    ├── interaction-contracts.md
    ├── README.md
    ├── system-default-semantics.md
    └── ...
```

como você já faz hoje, **mas criaria uma camada intermediária extremamente curta**:

```text
docs/
└── essence/
    └── essence-card.md
```

Algo como:

```markdown
# System Essence

## Purpose
This is a research system.
Traceability, reproducibility and scientific integrity take precedence over convenience.

## Invariants
1. Deterministic execution
2. Logical immutability
3. Hierarchical configuration
4. Idempotent execution
5. Immediate persistence / auditability
6. Controlled evolution
7. Documentation accompanies behavioral changes

## Authority
contracts/ = normative
architecture/ = conceptual
reference/ = implementation detail
archive/ = historical only

## Guardian rule
When uncertain, inspect the relevant normative contract.
Do not infer or relax a contract.
```

Isso seria talvez **algumas centenas de tokens**, não milhares.

O Guardian primeiro lê essa "Essence Card".

Depois:

> "A mudança parece envolver determinismo."

Só então ele abre:

```text
docs/contracts/determinism.md
```

E não:

```text
docs/contracts/
docs/architecture/
docs/reference/
docs/status/
...
```

Seu próprio Guardian antigo já tinha essa filosofia — ele dizia explicitamente que não precisava memorizar todos os detalhes, mas precisava saber **onde procurar**. 

Só que podemos aplicá-la de maneira muito mais agressiva.

---

# 3. O `AGENTS.md` deve conter apenas as regras que precisam estar sempre presentes

Aqui eu mudaria outra coisa importante.

O Codex lê `AGENTS.md` no início da execução e combina os arquivos encontrados na hierarquia; existe inclusive um limite padrão de **32 KiB** para essa cadeia de instruções. ([OpenAI Developers][3])

Portanto, eu **não colocaria seus sete contratos completos no `AGENTS.md`**.

Colocaria apenas algo parecido com:

```markdown
# Project Instructions

This is a research-oriented system.

## Non-negotiable principles

- Preserve determinism.
- Preserve logical immutability.
- Preserve idempotency.
- Preserve configuration hierarchy.
- Preserve data traceability and auditability.
- Do not weaken guarantees for convenience.
- Behavioral changes require documentation updates.

## Authority

- docs/contracts/ = normative authority
- docs/architecture/ = conceptual authority
- docs/reference/ = implementation reference
- docs/archive/ = historical only

## Essence Guardian

After any significant implementation, architectural change,
or change affecting a system invariant:

1. Spawn the `essence_guardian` custom agent.
2. Guardian must inspect the diff and relevant authoritative documents.
3. Guardian is read-only.
4. Do not proceed to the next implementation phase until the Guardian returns.
5. Do not invoke the Guardian for trivial changes unless an invariant may be affected.
```

Isso é pequeno.

E, mais importante, **não precisa ser re-enviado como uma montanha de documentação toda vez**. O Codex constrói essa cadeia de instruções ao iniciar a sessão. ([OpenAI Developers][3])

---

# 4. O Guardian deve analisar o `git diff`, não receber o projeto inteiro

Esse talvez seja o ganho de eficiência mais importante.

Seu Guardian antigo tinha como metodologia:

> ler memória → entender escopo → mapear contratos → verificar documentação → encontrar violações → avaliar severidade → escrever memória. 

Eu manteria quase exatamente isso.

Mas o **escopo deve começar pelo diff**.

Algo como:

```text
git diff
git diff --stat
git status
```

Depois:

```text
"Quais contratos podem ser afetados por esses arquivos?"
```

Só então ele abre os arquivos relevantes.

Isso é muito mais eficiente do que:

> "Leia o projeto e descubra se existe algum problema."

O próprio guia de subagentes do Codex recomenda trabalhos de exploração **read-heavy e delimitados**, e observa que subagentes consomem mais tokens do que uma execução single-agent. ([OpenAI Developers][2])

---

# 5. Eu colocaria o Guardian em **Luna + medium** inicialmente

Essa é uma mudança que eu acho especialmente boa para o seu caso.

O trabalho dele é:

> **verificação especializada, read-heavy, narrow scope.**

E a documentação atual do Codex recomenda Luna justamente para agentes rápidos, de escopo estreito, repetíveis ou de alto volume. Terra é indicado para scans e revisões maiores; esforços maiores aumentam consumo de tokens. ([OpenAI Developers][2])

Então eu começaria com:

```toml
model = "gpt-5.6-luna"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
```

E só migraria para:

```toml
model = "gpt-5.6-terra"
model_reasoning_effort = "high"
```

quando a mudança fosse realmente complexa.

Por exemplo:

> "Alterei o mecanismo de resolução de configuração."

→ **Terra/high**

Enquanto:

> "Adicionei um novo endpoint seguindo o padrão existente."

→ **Luna/medium**

Isso é exatamente o tipo de diferenciação que o mecanismo de Custom Agents do Codex suporta. ([OpenAI Developers][2])

---

# 6. Eu eliminaria várias coisas do seu Guardian antigo

Algumas partes fazem sentido no Qwen, mas não precisam sobreviver na mesma forma.

Por exemplo, o Guardian antigo tinha:

```text
AskUserQuestion
Edit
WriteFile
SaveMemory
WebSearch
WebFetch
...
```

mas ao mesmo tempo dizia:

> **"You NEVER write or modify code."** 

Eu deixaria o agente realmente **read-only**.

O `sandbox_mode = "read-only"` do Custom Agent ajuda a transformar isso em uma restrição operacional, não apenas uma instrução textual. ([OpenAI Developers][2])

E eu provavelmente **tiraria WebSearch/WebFetch do Guardian por padrão**.

O Guardian deveria avaliar **a integridade do projeto**, não sair pesquisando a internet para descobrir o que fazer.

Só precisaria de documentação externa se um contrato explicitamente dependesse de comportamento externo.

---

# 7. A memória também pode ficar muito mais barata

Você tinha uma boa ideia aqui.

O Guardian lê:

```text
docs/essence-guardian-log/guardian_memory.md
```

antes de cada avaliação e adiciona uma entrada depois. 

Eu manteria.

Mas tornaria essa memória **extremamente curta**.

Por exemplo:

```markdown
### 18 [2026-08-15]
- Scope: config resolver
- Contracts: configuration hierarchy, determinism
- Status: Warning
- Note: CLI override path may bypass experiment freeze.
```

Fim.

O Guardian não precisa ler 300 avaliações antigas.

Eu provavelmente faria:

```text
guardian_memory.md
```

→ últimas 10–20 avaliações.

E talvez:

```text
guardian_patterns.md
```

→ somente problemas recorrentes e decisões consolidadas.

Isso evita transformar a memória em mais uma fonte crescente de contexto.

---

# 8. E tem um detalhe importante: eu NÃO faria o Guardian ser chamado depois de cada pequena alteração

Aqui eu discordo um pouco da filosofia literal do seu arquivo antigo.

Seu arquivo diz:

> "Be thorough — Check all 7 contracts even if the change seems minor." 

**Isso eu mudaria no Codex.**

Com a franquia limitada, fazer:

```text
muda uma linha
↓
Guardian
↓
lê diff
↓
lê contratos
↓
faz relatório
```

a cada cinco minutos seria desperdício.

Eu usaria três níveis.

### Alteração trivial

```text
typo
renomeação local
comentário
formatação
```

→ **sem Guardian**

### Alteração significativa

```text
nova funcionalidade
refatoração
alteração de fluxo
mudança de persistência
alteração de configuração
```

→ **Guardian**

### Alteração estrutural/crítica

```text
arquitetura
contratos
persistência
reprodutibilidade
modelo de dados
configuração
execução
```

→ **Guardian + Terra/high**, talvez até uma segunda revisão independente em casos excepcionais.

Isso preserva a finalidade do Guardian sem transformar cada mudança em duas chamadas completas.

---

# E há uma coisa que eu acho que você vai gostar muito

O Codex atual permite exatamente que o **AGENTS.md ou uma Skill peça a delegação para um subagente**. A documentação diz explicitamente que os agentes locais podem ser acionados quando instruções aplicáveis do `AGENTS.md` ou de uma Skill solicitam a delegação. ([OpenAI Developers][2])

Então você pode chegar muito perto do seu antigo:

```text
AGENT PRINCIPAL
    │
    ├── implementa
    │
    ├── implementação significativa
    │
    └── spawn essence_guardian
              │
              ▼
       ESSENCE GUARDIAN
       Luna / Medium
       Read-only
              │
       ┌──────┴──────┐
       │             │
     diff       contratos relevantes
       │             │
       └──────┬──────┘
              ▼
          VERDICT
              │
       ┌──────┴──────┐
       ▼             ▼
      OK          Warning/Violation
       │             │
       ▼             ▼
  prossegue       volta ao principal
```

E isso é **conceitualmente praticamente o mesmo sistema que você já tinha construído.**

---

# E eu faria uma mudança conceitual ainda mais interessante

Seu `essence-guardian` atualmente funciona como:

> **"leia os contratos e veja se foram respeitados."**

Eu faria o Guardian trabalhar principalmente com **evidências**.

Por exemplo:

```text
Change:
src/config/resolver.py

Relevant contracts:
configuration-hierarchy.md
system-default-semantics.md

Evidence:
- resolver.py:142 reads ENV when experiment config is absent
- contract section 3 says ENV must not be consulted at run resolution

Verdict:
Violation
```

Isso é muito melhor do que fazer o Guardian recontar a filosofia inteira do projeto.

E combina perfeitamente com o seu relatório atual, que já é bastante estruturado e factual. 

---

# Minha arquitetura recomendada

Eu acabaria com algo parecido com:

```text
project/
│
├── AGENTS.md
│
├── .codex/
│   ├── config.toml
│   └── agents/
│       └── essence-guardian.toml
│
├── docs/
│   ├── essence/
│   │   └── essence-card.md
│   │
│   ├── contracts/
│   │   ├── README.md
│   │   ├── determinism.md
│   │   ├── immutability.md
│   │   ├── idempotency.md
│   │   └── ...
│   │
│   └── essence-guardian-log/
│       └── guardian_memory.md
```

E a responsabilidade de cada camada seria:

**`AGENTS.md`**
→ regras que todo agente precisa conhecer.

**`essence-card.md`**
→ essência compacta do projeto.

**`contracts/*.md`**
→ verdade normativa detalhada.

**`essence-guardian.toml`**
→ personalidade, limites e comportamento do Guardian.

**`guardian_memory.md`**
→ histórico mínimo.

Isso é, na minha opinião, **muito mais eficiente que transportar seu Skill do Qwen quase intacto**.

---

## E uma ressalva importante sobre seu medo de tokens

Você está certo em se preocupar.

A própria documentação atual do Codex avisa explicitamente que **subagentes gastam mais tokens do que executar a mesma tarefa com um único agente**, porque cada subagente possui seu próprio trabalho de modelo e ferramentas. ([OpenAI Developers][2])

Por isso eu **não faria um Guardian "inteligente demais"**.

O objetivo dele não deve ser:

> "Entenda profundamente o projeto inteiro."

Deve ser:

> **"Descubra quais contratos são relevantes para este diff e procure violações. Só leia o necessário."**

Essa diferença pode ser enorme no consumo.

E tem uma coincidência muito boa aqui: **o desenho que você criou originalmente já contém a semente dessa otimização**. Seu próprio documento diz que o Guardian não deve memorizar cada detalhe, mas saber onde encontrá-lo. 

Eu simplesmente levaria esse princípio às últimas consequências.

### Minha recomendação final

**Não tente portar o `essence-guardian.md` diretamente para o Codex.**

Eu o transformaria em **um Custom Agent read-only**, colocaria **uma essência extremamente pequena no `AGENTS.md`**, criaria uma **Essence Card compacta**, manteria os contratos completos como fontes normativas e faria o Guardian consultar **somente os contratos relevantes ao diff**.

Para o seu orçamento de uso, eu começaria com **Luna + medium**, e só escalaria para Terra/high em mudanças arquiteturalmente importantes.

Isso preservaria praticamente toda a ideia que você tinha no Qwen, mas com uma arquitetura muito mais adequada ao Codex atual. ([OpenAI Developers][2])

E, sinceramente, **acho que vale muito a pena fazer essa migração direito**. A sua ideia do Guardian é boa; eu não jogaria fora só porque mudou de ferramenta.

[1]: https://developers.openai.com/codex/skills "Build skills | ChatGPT Learn"
[2]: https://developers.openai.com/codex/subagents "Subagents | ChatGPT Learn"
[3]: https://developers.openai.com/codex/guides/agents-md "Custom instructions with AGENTS.md | ChatGPT Learn"
