#!/usr/bin/env python
"""Test to inspect the FULL API response and check if temperature is echoed back."""

import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "http://192.168.1.107:8080/v1")
MODEL_ID = os.getenv("TEST_MODEL", "qwen/qwen-3.5-3b")

async def test_full_response():
    """Make a request and print the FULL response."""
    
    messages = [
        {"role": "system", "content": "Responda de forma curta."},
        {"role": "user", "content": "Quanto é 2+2? Responda apenas o número."}
    ]
    
    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "max_tokens": 50,
        "temperature": 0.5,
        "top_p": 0.9,
        "top_k": 40,
    }
    
    print("=" * 70)
    print("Testando resposta COMPLETA da API")
    print("=" * 70)
    print(f"\nPayload enviado:")
    print(json.dumps(payload, indent=2))
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload
        )
        
        print(f"\nStatus HTTP: {response.status_code}")
        print(f"\nHeaders da resposta:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\nCorpo COMPLETO da resposta (raw):")
        print("-" * 70)
        
        # Print raw response
        raw_data = response.json()
        print(json.dumps(raw_data, indent=2, ensure_ascii=False))
        
        print("-" * 70)
        
        # Check for temperature in response
        print("\n🔍 Campos verificados:")
        print(f"  'temperature' no root: {'temperature' in raw_data}")
        print(f"  'temperature' em choices[0]: {'temperature' in raw_data.get('choices', [{}])[0] if raw_data.get('choices') else False}")
        print(f"  'temperature' em usage: {'temperature' in raw_data.get('usage', {})}")
        print(f"  'temperature' em system_fingerprint: {'system_fingerprint' in raw_data}")
        
        # Check all keys at root level
        print(f"\n  Chaves no root do response: {list(raw_data.keys())}")
        
        # Check if there's any field mentioning temp
        print("\n🔍 Buscando campos com 'temp' no nome:")
        def find_temp_keys(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if "temp" in key.lower():
                        print(f"  {new_path}: {value}")
                    find_temp_keys(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    find_temp_keys(item, f"{path}[{i}]")
        
        find_temp_keys(raw_data)


if __name__ == "__main__":
    asyncio.run(test_full_response())
