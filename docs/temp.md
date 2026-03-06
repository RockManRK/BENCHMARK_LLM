***

# Structured Outputs

OpenRouter supports structured outputs for compatible models, ensuring responses follow a specific JSON Schema format. This feature is particularly useful when you need consistent, well-formatted responses that can be reliably parsed by your application.

## Overview

Structured outputs allow you to:

* Enforce specific JSON Schema validation on model responses
* Get consistent, type-safe outputs
* Avoid parsing errors and hallucinated fields
* Simplify response handling in your application

## Using Structured Outputs

To use structured outputs, include a `response_format` parameter in your request, with `type` set to `json_schema` and the `json_schema` object containing your schema:

```typescript
{
  "messages": [
    { "role": "user", "content": "What's the weather like in London?" }
  ],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "weather",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "City or location name"
          },
          "temperature": {
            "type": "number",
            "description": "Temperature in Celsius"
          },
          "conditions": {
            "type": "string",
            "description": "Weather conditions description"
          }
        },
        "required": ["location", "temperature", "conditions"],
        "additionalProperties": false
      }
    }
  }
}
```

The model will respond with a JSON object that strictly follows your schema:

```json
{
  "location": "London",
  "temperature": 18,
  "conditions": "Partly cloudy with light drizzle"
}
```

## Model Support

Structured outputs are supported by select models.

You can find a list of models that support structured outputs on the [models page](https://openrouter.ai/models?order=newest\&supported_parameters=structured_outputs).

* OpenAI models (GPT-4o and later versions) [Docs](https://platform.openai.com/docs/guides/structured-outputs)
* Google Gemini models [Docs](https://ai.google.dev/gemini-api/docs/structured-output)
* Anthropic models (Sonnet 4.5 and Opus 4.1) [Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs)
* Most open-source models
* All Fireworks provided models [Docs](https://docs.fireworks.ai/structured-responses/structured-response-formatting#structured-response-modes)

To ensure your chosen model supports structured outputs:

1. Check the model's supported parameters on the [models page](https://openrouter.ai/models)
2. Set `require_parameters: true` in your provider preferences (see [Provider Routing](/docs/features/provider-routing))
3. Include `response_format` and set `type: json_schema` in the required parameters

## Best Practices

1. **Include descriptions**: Add clear descriptions to your schema properties to guide the model

2. **Use strict mode**: Always set `strict: true` to ensure the model follows your schema exactly

## Example Implementation

Here's a complete example using the Fetch API:

<Template
  data={{
  API_KEY_REF,
  MODEL: 'openai/gpt-4'
}}
>
  <CodeGroup>
    ```typescript title="TypeScript SDK"
    import { OpenRouter } from '@openrouter/sdk';

    const openRouter = new OpenRouter({
      apiKey: '{{API_KEY_REF}}',
    });

    const response = await openRouter.chat.send({
      model: '{{MODEL}}',
      messages: [
        { role: 'user', content: 'What is the weather like in London?' },
      ],
      responseFormat: {
        type: 'json_schema',
        jsonSchema: {
          name: 'weather',
          strict: true,
          schema: {
            type: 'object',
            properties: {
              location: {
                type: 'string',
                description: 'City or location name',
              },
              temperature: {
                type: 'number',
                description: 'Temperature in Celsius',
              },
              conditions: {
                type: 'string',
                description: 'Weather conditions description',
              },
            },
            required: ['location', 'temperature', 'conditions'],
            additionalProperties: false,
          },
        },
      },
      stream: false,
    });

    const weatherInfo = response.choices[0].message.content;
    ```

    ```python title="Python"
    import requests
    import json

    response = requests.post(
      "https://openrouter.ai/api/v1/chat/completions",
      headers={
        "Authorization": f"Bearer {{API_KEY_REF}}",
        "Content-Type": "application/json",
      },

      json={
        "model": "{{MODEL}}",
        "messages": [
          {"role": "user", "content": "What is the weather like in London?"},
        ],
        "response_format": {
          "type": "json_schema",
          "json_schema": {
            "name": "weather",
            "strict": True,
            "schema": {
              "type": "object",
              "properties": {
                "location": {
                  "type": "string",
                  "description": "City or location name",
                },
                "temperature": {
                  "type": "number",
                  "description": "Temperature in Celsius",
                },
                "conditions": {
                  "type": "string",
                  "description": "Weather conditions description",
                },
              },
              "required": ["location", "temperature", "conditions"],
              "additionalProperties": False,
            },
          },
        },
      },
    )

    data = response.json()
    weather_info = data["choices"][0]["message"]["content"]
    ```

    ```typescript title="TypeScript (fetch)"
    const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer {{API_KEY_REF}}',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: '{{MODEL}}',
        messages: [
          { role: 'user', content: 'What is the weather like in London?' },
        ],
        response_format: {
          type: 'json_schema',
          json_schema: {
            name: 'weather',
            strict: true,
            schema: {
              type: 'object',
              properties: {
                location: {
                  type: 'string',
                  description: 'City or location name',
                },
                temperature: {
                  type: 'number',
                  description: 'Temperature in Celsius',
                },
                conditions: {
                  type: 'string',
                  description: 'Weather conditions description',
                },
              },
              required: ['location', 'temperature', 'conditions'],
              additionalProperties: false,
            },
          },
        },
      }),
    });

    const data = await response.json();
    const weatherInfo = data.choices[0].message.content;
    ```
  </CodeGroup>
</Template>

## Streaming with Structured Outputs

Structured outputs are also supported with streaming responses. The model will stream valid partial JSON that, when complete, forms a valid response matching your schema.

To enable streaming with structured outputs, simply add `stream: true` to your request:

```typescript
{
  "stream": true,
  "response_format": {
    "type": "json_schema",
    // ... rest of your schema
  }
}
```

## Error Handling

When using structured outputs, you may encounter these scenarios:

1. **Model doesn't support structured outputs**: The request will fail with an error indicating lack of support
2. **Invalid schema**: The model will return an error if your JSON Schema is invalid



***

# Response Healing

The Response Healing plugin automatically validates and repairs malformed JSON responses from AI models. When models return imperfect formatting – missing brackets, trailing commas, markdown wrappers, or mixed text – this plugin attempts to repair the response so you receive valid, parseable JSON.

## Overview

Response Healing provides:

* **Automatic JSON repair**: Fixes missing brackets, commas, quotes, and other syntax errors
* **Markdown extraction**: Extracts JSON from markdown code blocks

## How It Works

The plugin activates for non-streaming requests when you use `response_format` with either `type: "json_schema"` or `type: "json_object"`, and include the response-healing plugin in your `plugins` array. See the [Complete Example](#complete-example) below for a full implementation.

## What Gets Fixed

The Response Healing plugin handles common issues in LLM responses:

### JSON Syntax Errors

**Input:** Missing closing bracket

```text
{"name": "Alice", "age": 30
```

**Output:** Fixed

```json
{"name": "Alice", "age": 30}
```

### Markdown Code Blocks

**Input:** Wrapped in markdown

````text
```json
{"name": "Bob"}
```
````

**Output:** Extracted

```json
{"name": "Bob"}
```

### Mixed Text and JSON

**Input:** Text before JSON

```text
Here's the data you requested:
{"name": "Charlie", "age": 25}
```

**Output:** Extracted

```json
{"name": "Charlie", "age": 25}
```

### Trailing Commas

**Input:** Invalid trailing comma

```text
{"name": "David", "age": 35,}
```

**Output:** Fixed

```json
{"name": "David", "age": 35}
```

### Unquoted Keys

**Input:** JavaScript-style

```text
{name: "Eve", age: 40}
```

**Output:** Fixed

```json
{"name": "Eve", "age": 40}
```

## Complete Example

<Template
  data={{
  API_KEY_REF,
  MODEL: 'google/gemini-2.5-flash'
}}
>
  <CodeGroup>
    ```typescript title="TypeScript"
    const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer {{API_KEY_REF}}',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: '{{MODEL}}',
        messages: [
          {
            role: 'user',
            content: 'Generate a product listing with name, price, and description'
          }
        ],
        response_format: {
          type: 'json_schema',
          json_schema: {
            name: 'Product',
            schema: {
              type: 'object',
              properties: {
                name: {
                  type: 'string',
                  description: 'Product name'
                },
                price: {
                  type: 'number',
                  description: 'Price in USD'
                },
                description: {
                  type: 'string',
                  description: 'Product description'
                }
              },
              required: ['name', 'price']
            }
          }
        },
        plugins: [
          { id: 'response-healing' }
        ]
      }),
    });

    const data = await response.json();
    const product = JSON.parse(data.choices[0].message.content);
    // The plugin attempts to repair malformed JSON syntax
    console.log(product.name, product.price);
    ```

    ```python title="Python"
    import requests
    import json

    response = requests.post(
      "https://openrouter.ai/api/v1/chat/completions",
      headers={
        "Authorization": f"Bearer {{API_KEY_REF}}",
        "Content-Type": "application/json",
      },
      json={
        "model": "{{MODEL}}",
        "messages": [
          {
            "role": "user",
            "content": "Generate a product listing with name, price, and description"
          }
        ],
        "response_format": {
          "type": "json_schema",
          "json_schema": {
            "name": "Product",
            "schema": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "description": "Product name"
                },
                "price": {
                  "type": "number",
                  "description": "Price in USD"
                },
                "description": {
                  "type": "string",
                  "description": "Product description"
                }
              },
              "required": ["name", "price"]
            }
          }
        },
        "plugins": [
          {"id": "response-healing"}
        ]
      }
    )

    data = response.json()
    product = json.loads(data["choices"][0]["message"]["content"])
    # The plugin attempts to repair malformed JSON syntax
    print(product["name"], product["price"])
    ```
  </CodeGroup>
</Template>

## Limitations

<Warning title="Non-Streaming Requests Only">
  Response Healing only applies to non-streaming requests.
</Warning>

<Warning title="Will not repair all JSON">
  Some malformed JSON responses may still be unrepairable. In particular, if the response is truncated by `max_tokens`, the plugin will not be able to repair it.
</Warning>
