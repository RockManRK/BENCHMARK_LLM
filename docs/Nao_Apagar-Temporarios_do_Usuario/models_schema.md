# Schema da API de Models - OpenRouter

**Referência:** Documentação oficial do OpenRouter

## Visão Geral

A API de Models do OpenRouter fornece informações detalhadas sobre todos os modelos disponíveis, incluindo capacidades, preços e limites.

## Estrutura da Resposta

### Objeto Raiz

```json
{
  "data": [
    /* Array de objetos Model */
  ]
}
```

### Objeto Model

Cada modelo na lista `data` contém:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | `string` | Identificador único do modelo (ex: `"google/gemini-2.5-pro-preview"`) |
| `canonical_slug` | `string` | Slug permanente que nunca muda |
| `name` | `string` | Nome legível para exibição |
| `created` | `number` | Timestamp Unix de quando o modelo foi adicionado |
| `description` | `string` | Descrição detalhada das capacidades |
| `context_length` | `number` | Tamanho máximo da janela de contexto em tokens |
| `architecture` | `Architecture` | Objeto com capacidades técnicas |
| `pricing` | `Pricing` | Estrutura de preços mais baixa |
| `top_provider` | `TopProvider` | Detalhes do provedor primário |
| `per_request_limits` | `object \\| null` | Limites de rate limiting |
| `supported_parameters` | `string[]` | Parâmetros da API suportados |

---

## Schema de Resposta de Chat Completions

Quando você faz uma requisição para `/v1/chat/completions`, a resposta segue este schema:

### Objeto de Resposta

```typescript
type Response = {
  id: string;
  choices: (NonStreamingChoice | StreamingChoice | NonChatChoice)[];
  created: number; // Unix timestamp
  model: string;
  object: 'chat.completion' | 'chat.completion.chunk';
  system_fingerprint?: string; // Apenas se suportado pelo provedor
  usage?: ResponseUsage;
};
```

### Objeto ResponseUsage (Detalhado)

```typescript
type ResponseUsage = {
  // Contagem de tokens
  prompt_tokens: number;                    // Tokens de entrada (incluindo imagens, áudio, tools)
  completion_tokens: number;                // Tokens gerados na resposta
  total_tokens: number;                     // Soma de prompt_tokens + completion_tokens
  
  // Detalhes dos tokens de prompt (opcional)
  prompt_tokens_details?: {
    cached_tokens: number;                  // Tokens em cache
    cache_write_tokens?: number;            // Tokens escritos no cache
    audio_tokens?: number;                  // Tokens de áudio de entrada
    video_tokens?: number;                  // Tokens de vídeo de entrada
  };
  
  // Detalhes dos tokens de completion (opcional)
  completion_tokens_details?: {
    reasoning_tokens?: number;              // Tokens de raciocínio interno
    audio_tokens?: number;                  // Tokens de áudio de saída
    image_tokens?: number;                  // Tokens de imagem de saída
  };
  
  // Custo (campo PRINCIPAL para billing)
  cost?: number;                            // Custo final em créditos OpenRouter
  is_byok?: boolean;                        // Se usou "Bring Your Own Key"
  
  // Detalhes do custo (informativo, não usar para cálculos diretos)
  cost_details?: {
    upstream_inference_cost?: number;       // Custo do provedor (apenas BYOK)
    upstream_inference_prompt_cost: number;
    upstream_inference_completions_cost: number;
  };
  
  // Uso de ferramentas do servidor (opcional)
  server_tool_use?: {
    web_search_requests?: number;           // Número de buscas web realizadas
  };
};
```

---

## Campos do Usage - Guia de Uso

### ✅ Campos Essenciais (Sempre Capturar)

| Campo | Uso no Benchmark | Notas |
|-------|------------------|-------|
| `prompt_tokens` | **Sim** → `input_tokens` | Tokens de entrada |
| `completion_tokens` | **Sim** → `output_tokens` | Tokens de saída |
| `total_tokens` | **Sim** → `total_tokens` | Total (ou calcular: input + output) |
| `cost` | **Sim** → `cost` | **Custo final oficial** |

### ℹ️ Campos Opcionais (Capturar se Disponível)

| Campo | Uso no Benchmark | Notas |
|-------|------------------|-------|
| `completion_tokens_details.reasoning_tokens` | **Sim** → `reasoning_tokens` | Tokens de raciocínio |
| `prompt_tokens_details.cached_tokens` | Não | Opcional, não crítico |

### ❌ Campos para Ignorar (Neste Contexto)

| Campo | Motivo |
|-------|--------|
| `cost_details` | Informativo, não é custo final |
| `server_tool_use.web_search_requests` | Apenas para modo experimental com web search |
| `is_byok` | Informativo, não afeta billing |

---

## Implementação no Benchmark LLM

### Schema do Banco de Dados

A tabela `responses` armazena os campos de uso e custo:

```sql
CREATE TABLE responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 1,
    
    -- Resposta
    selected_answer TEXT,
    response_text TEXT,
    is_correct BOOLEAN,
    status TEXT NOT NULL DEFAULT 'pending',
    
    -- Métricas de performance
    latency_ms INTEGER,
    
    -- Uso de tokens (OpenRouter usage)
    input_tokens INTEGER,       -- prompt_tokens
    output_tokens INTEGER,      -- completion_tokens
    total_tokens INTEGER,       -- total_tokens
    reasoning_tokens INTEGER,   -- reasoning_tokens (opcional)
    
    -- Custo
    cost REAL,                  -- usage.cost (créditos OpenRouter)
    
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys...
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE RESTRICT,
    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE RESTRICT
);
```

### Fluxo de Captura

1. **Requisição API** → `POST /v1/chat/completions`
2. **Resposta** → Parse do objeto `usage`
3. **Extração**:
   - `usage.prompt_tokens` → `input_tokens`
   - `usage.completion_tokens` → `output_tokens`
   - `usage.total_tokens` → `total_tokens`
   - `usage.cost` → `cost`
   - `usage.completion_tokens_details.reasoning_tokens` → `reasoning_tokens`
4. **Persistência** → INSERT na tabela `responses`

---

## Exemplo de Resposta Completa

```json
{
  "id": "gen-abc123",
  "model": "openai/gpt-4",
  "created": 1709500000,
  "object": "chat.completion",
  "choices": [{
    "finish_reason": "stop",
    "native_finish_reason": "stop",
    "message": {
      "role": "assistant",
      "content": "A resposta correta é A."
    }
  }],
  "usage": {
    "prompt_tokens": 194,
    "completion_tokens": 2,
    "total_tokens": 196,
    "prompt_tokens_details": {
      "cached_tokens": 0
    },
    "completion_tokens_details": {
      "reasoning_tokens": 0
    },
    "cost": 0.00095,
    "is_byok": false
  }
}
```

---

## Referências

- [OpenRouter Models](https://openrouter.ai/models)
- [API Reference - Models](https://openrouter.ai/docs/api-reference/models/get-models)
- [Usage Accounting](https://openrouter.ai/docs/guides/guides/usage-accounting)

---

**Nota:** Este documento é uma referência técnica. Para mudanças no schema do banco de dados, consulte `src/db/schema.sql`.

