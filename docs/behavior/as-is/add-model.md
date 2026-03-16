# Comando: --add-model

## 1. Visão Geral

Este comando adiciona modelos (ou variantes de modelos) a um experimento existente. Modelos são registrados como "variantes" que incluem parâmetros de execução específicos.

O comando realiza três operações principais:
- Registra o modelo base no catálogo (se não existir)
- Cria uma variante de modelo com parâmetros específicos
- Associa a variante ao experimento

**Importante:** Este comando NÃO cria execuções (runs) e NÃO executa benchmarks. Ele apenas configura quais modelos estarão disponíveis para execução futura.

## 2. Pré-condições Observadas

- O experimento deve existir (verificado pelo nome)
- O banco de dados deve estar inicializado
- Pelo menos um modelo deve ser especificado via --add-model
- A chave de API do OpenRouter NÃO é necessária (não há chamadas à API neste comando)

## 3. Fluxo de Execução (Passo a Passo)

1. **Verificação do Experimento**
   - Busca o experimento pelo nome fornecido
   - Se não encontrado, interrompe com erro

2. **Processamento de Cada Modelo** (repetido para cada modelo na lista)

   a. **Extração de Provider e Nome**
      - Se o modelo contém "/", divide em provider e model_name
      - Ex: "openai/gpt-4" → provider="openai", model_name="gpt-4"
      - Se não contém "/", provider="unknown", model_name=completo

   b. **Registro do Modelo Base**
      - Verifica se o modelo já existe na tabela `models`
      - Se NÃO existir, cria registro com provider, model_name
      - Se já existir, pula esta etapa

   c. **Criação da Variante do Modelo**
      - Constrói configuração da variante com parâmetros:
        - reasoning_mode (padrão: "unspecified")
        - reasoning_effort (opcional, via --reasoning-effort)
        - reasoning_max_tokens (opcional)
        - vision_enabled (via --enable-vision)
        - structured_enabled (via --enable-structured)
      - Gera variant_signature (string legível que identifica a variante)
      - Gera variant_id (hash baseado na assinatura)
      - Verifica se variante já existe pelo variant_id
      - Se NÃO existir, cria registro na tabela `model_variants`
      - Se já existir, reutiliza a variante existente

   d. **Associação com o Experimento**
      - Tenta associar a variante ao experimento na tabela `experiment_models`
      - Se associação já existir, registra erro e continua

3. **Normalização de Reasoning Effort**
   - Se reasoning_effort = 'none', define reasoning_mode = 'off'
   - Se reasoning_effort especificado (não 'none'), define reasoning_mode = 'effort'
   - Se reasoning_effort não especificado, mantém reasoning_mode = 'unspecified'

4. **Exibição do Resumo**
   - Exibe mensagem de sucesso com:
     - Quantidade de variantes adicionadas
     - Lista de modelos e suas variantes criadas
     - Assinatura de cada variante
     - Próximos passos sugeridos
   - Exibe lista completa de modelos configurados no experimento

## 4. Decisões Implícitas (If / Else)

| Condição | Comportamento |
|----------|---------------|
| Experimento não encontrado | Interrompe com erro "Experiment 'X' not found" |
| Modelo já registrado | Reutiliza registro existente (idempotência) |
| Variante já existe | Reutiliza variante existente (não duplica) |
| Associação já existe | Registra erro e continua para próximo modelo |
| reasoning_effort = 'none' | Define reasoning_mode = 'off', reasoning_effort = None |
| reasoning_effort especificado | Define reasoning_mode = 'effort' |
| reasoning_effort não especificado | Mantém reasoning_mode = 'unspecified' |
| Modelo sem provider explícito | Define provider = "unknown" |
| Falha na associação | Registra erro no log mas não interrompe execução |

## 5. Efeitos Colaterais

### Leituras no Banco de Dados
- Verifica existência do experimento pelo nome
- Verifica existência de modelos base por model_id
- Verifica existência de variantes por variant_id
- Verifica associações existentes em experiment_models

### Escritas no Banco de Dados
- **Tabela `models`**: N registros inseridos (apenas modelos novos)
- **Tabela `model_variants`**: N registros inseridos (apenas variantes novas)
- **Tabela `experiment_models`**: N registros inseridos (associações)

### Entidades Criadas
- M Model (base, se não existirem)
- N ModelVariant (com parâmetros específicos)
- N ExperimentModel (associações)

### Estado do Sistema Após Execução
- Modelos base estão registrados no catálogo
- Variantes de modelos estão disponíveis
- Variantes estão associadas ao experimento
- Nenhum run foi criado
- Nenhuma execução foi realizada

## 6. Comportamentos Implícitos Observados

### ⚠️ NORMALIZAÇÃO DE REASONING_EFFORT (IMPORTANTE)

**Regra de normalização aplicada:**
```
reasoning_effort = 'none'  → reasoning_mode = 'off', reasoning_effort = NULL
reasoning_effort = 'low'   → reasoning_mode = 'effort', reasoning_effort = 'low'
reasoning_effort = 'high'  → reasoning_mode = 'effort', reasoning_effort = 'high'
reasoning_effort não especificado → reasoning_mode = 'unspecified'
```

**Impacto na identidade da variante:**
- `--reasoning-effort none` gera variante COM `reasoning_mode='off'`
- `--reasoning-effort low` gera variante COM `reasoning_mode='effort'`
- Ausência de `--reasoning-effort` gera variante COM `reasoning_mode='unspecified'`

**⚠️ RISCO DE INCONSISTÊNCIA:**
- Esta normalização ocorre **apenas** no contexto de --add-model
- Durante execução (--execute-run), a normalização **pode NÃO ocorrer**
- Pode gerar variantes diferentes para mesma intenção

### Identidade de Variantes
- Cada variante é única baseada em:
  - model_id (modelo base)
  - reasoning_mode
  - reasoning_effort (quando aplicável)
  - reasoning_max_tokens (quando aplicável)
  - vision_enabled (booleano)
  - structured_enabled (booleano)
- Mesma combinação → mesma variante (idempotência)

### Múltiplos Pontos de Criação de Variantes
- Variantes podem ser criadas em **dois contextos diferentes**:
  1. **Setup (--add-model):** com parâmetros explícitos do CLI (normalização aplicada)
  2. **Execução (--execute-run):** com parâmetros inferidos das settings (pode não aplicar normalização)
- **Risco:** identidade pode divergir entre contextos
- **Recomendação:** sempre usar --add-model antes de --execute-run

### Separação entre Modelo Base e Variante
- Modelo base: apenas identificação (provider, nome)
- Variante: parâmetros de execução específicos
- Múltiplas variantes podem existir para o mesmo modelo base
- Ex: "openai/gpt-4" pode ter variantes com diferentes reasoning_effort

### Associação Direta Experimento-Variante
- Variantes são associadas DIRETAMENTE ao experimento
- Não há intermediários ou cópias
- Runs futuros copiarão variantes do experimento

### Múltiplas Execuções do Comando
- Pode ser executado múltiplas vezes no mesmo experimento
- Modelos/variantes existentes são reutilizados
- Novos modelos são adicionados incrementalmente
- Não há limite máximo de modelos por experimento

### Parâmetros de Execução vs Identidade
- Parâmetros de identidade (definem a variante):
  - reasoning_mode, reasoning_effort, reasoning_max_tokens
  - vision_enabled, structured_enabled
- Parâmetros de execução (NÃO definem identidade):
  - temperature, top_p, top_k, max_tokens, repeat_penalty
  - Estes são configurados globalmente via .env ou CLI

### Validação de Integridade
- Variante deve referenciar modelo base existente
- Associação deve referenciar experimento e variante existentes
- Foreign keys garantem integridade referencial

### Feedback Visual
- Exibe resumo detalhado após cada execução
- Mostra variantes novas e existentes
- Indica próximos passos sugeridos
- Lista todos os modelos configurados no experimento
