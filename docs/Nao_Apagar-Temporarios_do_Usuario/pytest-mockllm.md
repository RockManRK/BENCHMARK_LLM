# Pergunta:
Existe alguma ferramenta que simule respostas da api da LLM para eu poder fazer testes do sistema sem precisar necessariamente conectar realmente a uma api de llm?

# Resposta:
Sim! Existem várias formas de simular (fazer um "mock") das respostas de uma API de LLM localmente. Essa é a melhor prática recomendada antes de colocar um benchmark para rodar, pois **evita que você gaste dinheiro (créditos) durante a fase de programação e caça aos bugs no código**.

Como a OpenRouter usa o **padrão exato da API da OpenAI**, qualquer simulador feito para OpenAI funcionará perfeitamente para o seu código. Aqui estão as três melhores soluções, da mais simples até a mais avançada:

## 1. Usar uma Biblioteca de Mock no Python (Recomendado)
Se você estiver programando em Python e quiser apenas testar a lógica do seu script, a maneira mais elegante é usar o **`pytest-mockllm`** (ou `responses` nativo). [markaicode](https://markaicode.com/mock-llm-api-calls-unit-testing/)
Ele intercepta a requisição HTTP que seu script faria para a OpenRouter e devolve uma resposta falsa instantaneamente, sem precisar subir nenhum servidor.

Exemplo de como seria no seu script:
```python
# O seu script acha que está chamando a API, mas não está gastando nada.
# Útil apenas para testar se o salvamento no SQLite e a leitura do JSON funcionam.
```
Essa abordagem é excelente se você souber um pouco de testes unitários em Python. [markaicode](https://markaicode.com/mock-llm-api-calls-unit-testing/)


# Pergunta:
Essa biblioteca python, você sabe dizer se ela é atualizada com os padrões atuais do mercado? Digo, ela me permite fazer testes adequados que sejam bons o suficiente?

# Resposta:
Você tocou em um ponto crucial e a sua intuição está certíssima: usar o mock direto no Python é de fato o melhor equilíbrio entre resultado profissional e baixa complexidade.

A resposta direta para a sua dúvida é: **Sim, ela é perfeitamente adequada aos padrões atuais, porque ela é imune à desatualização.**

Aqui está o porquê e como isso funciona na prática:

## O "Segredo" das Bibliotecas de Mock no Python
Bibliotecas consolidadas de testes em Python (como a `responses`, `requests-mock` ou a nativa `unittest.mock`) não tentam "adivinhar" como é a API do OpenRouter ou do GPT-5. Elas simplesmente interceptam a sua requisição de rede antes dela sair do seu computador e devolvem **o dicionário JSON que você mesmo escrever**.

Ou seja, se amanhã o OpenRouter inventar um campo novo ou mudar a forma como o `reasoning_content` é entregue, você não precisa esperar o criador da biblioteca lançar uma atualização. Basta você mesmo adicionar essa linha no seu JSON de teste.

## Como seria na prática (Exemplo Simples)
Se o seu script usa a biblioteca `requests` para chamar o OpenRouter, você usaria a biblioteca oficial `responses` (que você instala com `pip install responses`). 

Veja como ela simula exatamente o padrão de 2026 com o campo de raciocínio, sem conectar na internet e sem gastar 1 centavo:

```python
import requests
import responses

# O decorador avisa o Python: "intercepte qualquer chamada de rede nesta função"
@responses.activate
def testar_meu_benchmark():
    
    # 1. Você define o formato MAIS ATUAL da API que quer simular:
    resposta_falsa = {
        "id": "gen-12345",
        "model": "openai/gpt-5.2-pro", # Testa se o seu script salva o nome do modelo certo
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "A", # A resposta que você quer que o seu script valide
                "reasoning_content": "A dor de cabeça descrita indica a alternativa A..."
            }
        }]
    }

    # 2. Você avisa a biblioteca para interceptar a URL do OpenRouter e devolver a resposta falsa
    responses.add(
        responses.POST, 
        'https://openrouter.ai/api/v1/chat/completions',
        json=resposta_falsa, 
        status=200
    )

    # 3. AQUI VAI O SEU CÓDIGO REAL. 
    # Ele vai fazer o requests.post achando que está falando com a IA, 
    # mas vai receber instantaneamente o JSON falso acima.
    resposta = requests.post('https://openrouter.ai/api/v1/chat/completions').json()
    
    print(resposta['choices'][0]['message']['content']) # Imprime "A" instantaneamente
```

## Por que essa é a melhor escolha para o seu Benchmark?
1. **Velocidade:** Seu script pode rodar 100 perguntas em 1 segundo, pois não há tempo de rede ou processamento da IA. Ótimo para testar se o salvamento no banco de dados SQLite está funcionando.
2. **Controle de Erros:** Você pode testar como seu código reage a alucinações. Basta mudar o `"content": "A"` no mock para `"content": "Eu acho que é a letra H"` e ver se o seu sistema lida bem com isso.
3. **Simulação de Quedas:** Você pode configurar o mock para devolver um Erro 429 (Rate Limit) e testar se a sua lógica de "tentar novamente" (retry) está funcionando.

Essa abordagem te dá controle laboratorial absoluto sobre o sistema antes de gastar com as APIs reais.