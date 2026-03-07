#!/usr/bin/env python
"""Test to verify if llama.cpp actually uses the temperature parameter.

This test sends the same question multiple times with different temperatures
and checks if there's variation in responses (which would indicate temperature is working).
"""

import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_ID = os.getenv("TEST_MODEL", "qwen/qwen-3.5-3b")

print("=" * 70)
print("Temperature EFFECTIVENESS Test - llama.cpp")
print("=" * 70)
print(f"Model: {MODEL_ID}")
print(f"Base URL: {BASE_URL}")
print("=" * 70)

# Open-ended question to encourage variation
TEST_QUESTION = """Você é um assistente criativo. Gere uma descrição curta e criativa (2-3 frases) sobre um gato explorando o espaço.
Seja imaginativo e variado na sua resposta."""

async def make_request(temperature: float, request_num: int):
    """Make a single API request."""
    messages = [
        {"role": "system", "content": "Você é um assistente criativo e imaginativo."},
        {"role": "user", "content": TEST_QUESTION}
    ]
    
    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "max_tokens": 150,
        "temperature": temperature,
        "top_p": 0.9,  # Keep top_p constant
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Log the EXACT payload sent
                print(f"\n[Temp={temperature}] Request {request_num}:")
                print(f"  Payload temperature: {payload['temperature']}")
                print(f"  Payload top_p: {payload['top_p']}")
                print(f"  Resposta: {content[:100]}...")
                
                return {
                    "temperature": temperature,
                    "request_num": request_num,
                    "content": content,
                    "payload_temp": payload["temperature"]
                }
            else:
                print(f"\n[Temp={temperature}] Erro {response.status_code}: {response.text[:200]}")
                return None
                
    except Exception as e:
        print(f"\n[Temp={temperature}] Exceção: {e}")
        return None


async def test_temperature_variation(temperature: float, num_requests: int = 5):
    """Test if temperature causes variation in responses."""
    print(f"\n{'='*70}")
    print(f"Testando temperatura={temperature} ({num_requests} requisições)")
    print(f"{'='*70}")
    
    results = []
    for i in range(num_requests):
        result = await make_request(temperature, i + 1)
        if result:
            results.append(result)
        await asyncio.sleep(0.5)  # Small delay between requests
    
    return results


def analyze_variation(results: list[dict], temperature: float) -> dict:
    """Analyze variation in responses."""
    if len(results) < 2:
        return {"variation": "insufficient_data"}
    
    contents = [r["content"] for r in results]
    unique_contents = set(contents)
    
    # Check payload temperatures
    payload_temps = [r["payload_temp"] for r in results]
    all_payloads_correct = all(t == temperature for t in payload_temps)
    
    return {
        "total_requests": len(results),
        "unique_responses": len(unique_contents),
        "all_same": len(unique_contents) == 1,
        "all_different": len(unique_contents) == len(results),
        "payload_temp_correct": all_payloads_correct,
        "variation_ratio": len(unique_contents) / len(results) * 100
    }


async def main():
    """Run the temperature effectiveness test."""
    if not API_KEY:
        print("\n❌ ERRO: OPENROUTER_API_KEY não configurada!")
        return
    
    print("\n📋 METODOLOGIA:")
    print("  1. Enviar 5 requisições com temperatura=0 (esperado: respostas iguais)")
    print("  2. Enviar 5 requisições com temperatura=1 (esperado: respostas variadas)")
    print("  3. Comparar variação entre os dois grupos")
    print("\n  Se llama.cpp respeita a temperatura:")
    print("    - Temp 0: baixa variação (respostas similares/iguais)")
    print("    - Temp 1: alta variação (respostas diferentes)")
    print("\n  Se llama.cpp IGNORA a temperatura:")
    print("    - Ambos os grupos terão variação similar")
    
    # Test with temperature = 0
    results_temp0 = await test_temperature_variation(temperature=0.0, num_requests=5)
    analysis_temp0 = analyze_variation(results_temp0, 0.0)
    
    # Test with temperature = 1
    results_temp1 = await test_temperature_variation(temperature=1.0, num_requests=5)
    analysis_temp1 = analyze_variation(results_temp1, 1.0)
    
    # Summary
    print("\n" + "=" * 70)
    print("ANÁLISE DE VARIAÇÃO")
    print("=" * 70)
    
    print(f"\n📊 Temperatura 0.0:")
    print(f"   Requisições: {analysis_temp0.get('total_requests', 0)}")
    print(f"   Respostas únicas: {analysis_temp0.get('unique_responses', 0)}")
    print(f"   Todas iguais: {analysis_temp0.get('all_same', False)}")
    print(f"   Payload correto: {analysis_temp0.get('payload_temp_correct', False)}")
    print(f"   Variação: {analysis_temp0.get('variation_ratio', 0):.1f}%")
    
    print(f"\n📊 Temperatura 1.0:")
    print(f"   Requisições: {analysis_temp1.get('total_requests', 0)}")
    print(f"   Respostas únicas: {analysis_temp1.get('unique_responses', 0)}")
    print(f"   Todas diferentes: {analysis_temp1.get('all_different', False)}")
    print(f"   Payload correto: {analysis_temp1.get('payload_temp_correct', False)}")
    print(f"   Variação: {analysis_temp1.get('variation_ratio', 0):.1f}%")
    
    # Conclusion
    print("\n" + "=" * 70)
    print("CONCLUSÃO")
    print("=" * 70)
    
    var_ratio_0 = analysis_temp0.get('variation_ratio', 0)
    var_ratio_1 = analysis_temp1.get('variation_ratio', 0)
    
    if analysis_temp0.get('payload_temp_correct') and analysis_temp1.get('payload_temp_correct'):
        print("\n✓ Payloads enviados corretamente em ambos os casos")
        
        if var_ratio_0 < var_ratio_1:
            print(f"\n✓ Temperatura FUNCIONA no llama.cpp!")
            print(f"  Temp 0: {var_ratio_0:.1f}% variação < Temp 1: {var_ratio_1:.1f}% variação")
            print("  O modelo está respeitando o parâmetro de temperatura.")
        elif var_ratio_0 > var_ratio_1:
            print(f"\n⚠ Comportamento INESPERADO!")
            print(f"  Temp 0: {var_ratio_0:.1f}% variação > Temp 1: {var_ratio_1:.1f}% variação")
            print("  Isso é contrário ao esperado. Pode haver um bug.")
        else:
            print(f"\n⚠ Temperatura pode estar sendo IGNORADA!")
            print(f"  Temp 0: {var_ratio_0:.1f}% variação == Temp 1: {var_ratio_1:.1f}% variação")
            print("  Variação idêntica sugere que o parâmetro não está sendo usado.")
            print("  Verifique se o llama.cpp está configurado para aceitar parâmetros via API.")
    else:
        print("\n⚠ Erro ao enviar payloads. Verifique logs acima.")
    
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
