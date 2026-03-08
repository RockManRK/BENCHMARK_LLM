# Uso de Tokens e Custo no OpenRouter

O OpenRouter retorna automaticamente informações detalhadas de custo e uso em todas as respostas da API, sem necessidade de parâmetros adicionais [^1].

## Informações de Custo na Resposta

Toda resposta da API inclui um objeto `usage` com informações detalhadas de custo [^1]:

```json
{
  "usage": {
    "prompt_tokens": 194,
    "completion_tokens": 2,
    "total_tokens": 196,
    "cost": 0.00095,
    "prompt_tokens_details": {
      "cached_tokens": 0
    },
    "completion_tokens_details": {
      "reasoning_tokens": 0
    },
    "cost_details": {
      "upstream_inference_cost": 0.00019
    },
    "is_byok": false
  }
}
```

## Campos de Custo Disponíveis

### Campos Principais

- **`prompt_tokens`**: Número de tokens na entrada (prompt)
- **`completion_tokens`**: Número de tokens na saída (resposta)
- **`total_tokens`**: Soma de `prompt_tokens` + `completion_tokens`
- **`cost`**: **Custo final em créditos** cobrado da sua conta OpenRouter [^1]
- **`is_byok`**: Indica se a requisição usou "Bring Your Own Key" (BYOK)

### Campos Detalhados (Opcionais)

- **`prompt_tokens_details.cached_tokens`**: Tokens que foram lidos do cache (reduz custo)
- **`prompt_tokens_details.cache_write_tokens`**: Tokens escritos no cache
- **`completion_tokens_details.reasoning_tokens`**: Tokens usados para raciocínio interno do modelo
- **`cost_details.upstream_inference_cost`**: Custo real cobrado pelo provedor (apenas para requisições BYOK) [^1]

## Captura e Persistência no Benchmark LLM

O sistema `benchmark_llm` agora captura e persiste automaticamente:

- **`usage.cost`**: Custo final por requisição (armazenado na tabela `responses`)
- **`usage.total_tokens`**: Total de tokens (armazenado na tabela `responses`)
- **`usage.completion_tokens_details.reasoning_tokens`**: Tokens de raciocínio (quando disponível)

### Schema do Banco de Dados

A tabela `responses` inclui os seguintes campos de uso e custo:

```sql
CREATE TABLE responses (
    -- ... outros campos ...
    input_tokens INTEGER,      -- prompt_tokens
    output_tokens INTEGER,     -- completion_tokens
    total_tokens INTEGER,      -- total_tokens
    reasoning_tokens INTEGER,  -- reasoning_tokens (opcional)
    cost REAL,                 -- cost em créditos
    -- ... outros campos ...
);
```

### Importante

- **`usage.cost`** é o valor oficial a ser usado para cálculos de custo (o "recibo")
- **`usage.cost_details`** é informativo e **NÃO** deve ser usado para cálculos diretos
- Campos opcionais podem não estar presentes em todas as respostas
- O sistema trata campos opcionais como `None` quando não disponíveis

## Exemplo Prático

<CodeGroup>

```python title="Python"
import requests
import json

response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": "Bearer <OPENROUTER_API_KEY>",
        "Content-Type": "application/json",
    },
    data=json.dumps({
        "model": "openai/gpt-4o",
        "messages": [
            {"role": "user", "content": "Olá, como você está?"}
        ]
    })
)

data = response.json()
print(f"Resposta: {data['choices'][0]['message']['content']}")
print(f"Custo total: {data['usage']['cost']} créditos")
print(f"Tokens usados: {data['usage']['total_tokens']}")
print(f"Tokens de entrada: {data['usage']['prompt_tokens']}")
print(f"Tokens de saída: {data['usage']['completion_tokens']}")
```

```typescript title="TypeScript"
const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer <OPENROUTER_API_KEY>',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model: 'openai/gpt-4o',
    messages: [
      { role: 'user', content: 'Olá, como você está?' }
    ]
  })
});

const data = await response.json();
console.log('Resposta:', data.choices[0].message.content);
console.log('Custo total:', data.usage.cost, 'créditos');
console.log('Tokens usados:', data.usage.total_tokens);
console.log('Tokens de entrada:', data.usage.prompt_tokens);
console.log('Tokens de saída:', data.usage.completion_tokens);
```

</CodeGroup>

Você também pode consultar as informações de custo posteriormente usando o ID da geração retornado na resposta [^1]:

```python
# Use o ID retornado na resposta original
generation_id = data['id']

# Consulte as informações posteriormente
stats_response = requests.get(
    f"https://openrouter.ai/api/v1/generation/{generation_id}",
    headers={"Authorization": "Bearer <OPENROUTER_API_KEY>"}
)
```

As informações de custo são sempre incluídas automaticamente - não há necessidade de configurar parâmetros especiais ou fazer chamadas adicionais à API para obter esses dados.

[^1]: https://openrouter.ai/docs/guides/guides/usage-accounting