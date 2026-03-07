#!/usr/bin/env python
"""Test script to verify temperature parameter is being sent correctly to the API."""

import asyncio
import httpx
import json
import os
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_ID = os.getenv("TEST_MODEL", "qwen/qwen-3.5-3b")

print("=" * 60)
print("Temperature Parameter Test")
print("=" * 60)
print(f"Model: {MODEL_ID}")
print(f"Base URL: {BASE_URL}")
print(f"API Key configured: {'Yes' if API_KEY else 'No'}")
print("=" * 60)

# Simple test question
TEST_QUESTION = {
    "question_id": "Q001",
    "stem": "Qual é a capital da França?",
    "options": {"A": "Paris", "B": "Londres", "C": "Berlim", "D": "Madrid"},
    "correct_answer": "A"
}

def build_messages(question):
    """Build messages for the API request."""
    options_str = "\n".join([f"{k}) {v}" for k, v in question["options"].items()])
    
    user_prompt = f"""Responda a seguinte questão de múltipla escolha.

Questão: {question['stem']}

Opções:
{options_str}

Forneça apenas a letra da resposta correta (A, B, C ou D)."""

    return [
        {"role": "system", "content": "Você é um assistente útil que responde questões de múltipla escolha."},
        {"role": "user", "content": user_prompt}
    ]


async def test_temperature(temperature: float, max_tokens: int = 100):
    """Test API request with specific temperature."""
    print(f"\n--- Teste com temperatura={temperature} ---")
    
    messages = build_messages(TEST_QUESTION)
    
    # Build request payload
    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    
    print(f"Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost",
                },
                json=payload
            )
            
            print(f"\nStatus HTTP: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Resposta recebida:")
                
                # Extract response
                choice = data["choices"][0]
                message = choice["message"]
                usage = data.get("usage", {})
                
                print(f"  Conteúdo: {message['content'][:200]}...")
                print(f"  Tokens de entrada: {usage.get('prompt_tokens', 'N/A')}")
                print(f"  Tokens de saída: {usage.get('completion_tokens', 'N/A')}")
                
                # Check if temperature is echoed back (some APIs do this)
                if "temperature" in data:
                    print(f"  Temperatura no response: {data['temperature']}")
                
                return {
                    "status": "success",
                    "content": message["content"],
                    "usage": usage
                }
            else:
                print(f"Erro: {response.status_code}")
                print(f"Resposta: {response.text[:500]}")
                return {
                    "status": "error",
                    "status_code": response.status_code,
                    "error": response.text[:500]
                }
                
    except httpx.RequestError as e:
        print(f"Erro de requisição: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


async def main():
    """Run temperature tests."""
    if not API_KEY:
        print("\n❌ ERRO: OPENROUTER_API_KEY não configurada!")
        print("Configure no arquivo .env ou defina a variável de ambiente.")
        return
    
    print("\n🚀 Iniciando testes de temperatura...\n")
    
    # Test 1: Temperature = 0 (deterministic)
    result_temp0 = await test_temperature(temperature=0.0)
    
    # Test 2: Temperature = 1 (creative)
    result_temp1 = await test_temperature(temperature=1.0)
    
    # Summary
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)
    
    print(f"\nTemperatura 0.0: {'✓ Sucesso' if result_temp0['status'] == 'success' else '✗ Erro'}")
    if result_temp0['status'] == 'error':
        print(f"  Erro: {result_temp0.get('error', 'Desconhecido')}")
    
    print(f"Temperatura 1.0: {'✓ Sucesso' if result_temp1['status'] == 'success' else '✗ Erro'}")
    if result_temp1['status'] == 'error':
        print(f"  Erro: {result_temp1.get('error', 'Desconhecido')}")
    
    # Check if both succeeded
    if result_temp0['status'] == 'success' and result_temp1['status'] == 'success':
        print("\n✓ Ambos os testes passaram!")
        print("  O modelo aceita parâmetros de temperatura via API.")
    elif result_temp0['status'] == 'error' or result_temp1['status'] == 'error':
        print("\n⚠ Um ou ambos os testes falharam.")
        print("  Verifique se o modelo suporta o parâmetro temperature.")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
