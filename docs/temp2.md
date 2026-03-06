Sim, existem algumas maneiras de verificar se um modelo suporta structured outputs ao acessar via API:

## Verificação através da página de modelos

A forma mais direta é consultar a [página de modelos do OpenRouter](https://openrouter.ai/models?order=newest&supported_parameters=structured_outputs) com o filtro para modelos que suportam structured outputs [^1].

## Verificação programática

Você pode usar o endpoint `/api/v1/models` para obter informações sobre os modelos disponíveis, incluindo seus parâmetros suportados:

```typescript
const response = await fetch('https://openrouter.ai/api/v1/models', {
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY'
  }
});

const models = await response.json();
// Verificar se o modelo suporta structured_outputs nos parâmetros
```

## Garantindo suporte através de Provider Routing

Para garantir que apenas modelos com suporte a structured outputs sejam utilizados, você pode configurar o `require_parameters` nas preferências do provider [^1]:

```typescript
{
  "model": "openai/gpt-4",
  "provider": {
    "require_parameters": true
  },
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      // seu schema aqui
    }
  }
}
```

## Modelos que suportam Structured Outputs

Segundo a documentação, os seguintes tipos de modelos suportam structured outputs [^1]:

- **OpenAI models** (GPT-4o e versões posteriores)
- **Google Gemini models**
- **Anthropic models** (Sonnet 4.5 e Opus 4.1)
- **A maioria dos modelos open-source**
- **Todos os modelos fornecidos pela Fireworks**

## Tratamento de erros

Se você tentar usar structured outputs com um modelo que não suporta, a requisição falhará com um erro indicando a falta de suporte [^1].

[^1]: https://openrouter.ai/docs/guides/features/structured-outputs