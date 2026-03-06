"""
Test to check ALL possible sources of model information from llama.cpp server.
"""
import sys
sys.path.insert(0, '.')

import httpx
import json
from src.utils.config import get_settings

settings = get_settings()
base_url = settings.openrouter_base_url

print("=" * 80)
print("CHECKING ALL POSSIBLE MODEL INFO SOURCES")
print("=" * 80)
print(f"Base URL: {base_url}")
print()

# Test 1: GET /v1/models (list all)
print("1. GET /v1/models (list all models)...")
print("-" * 80)
try:
    response = httpx.get(f"{base_url}/models", timeout=10.0)
    response.raise_for_status()
    data = response.json()
    print(json.dumps(data, indent=2))
    
    # Check if there's more info in the list
    if 'data' in data:
        for model in data['data']:
            print(f"\nModel keys: {list(model.keys())}")
            print(f"Full model info: {json.dumps(model, indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print()
print()

# Test 2: GET /v1/models/Qwen (specific model)
print("2. GET /v1/models/Qwen (specific model)...")
print("-" * 80)
try:
    response = httpx.get(f"{base_url}/models/Qwen", timeout=10.0)
    response.raise_for_status()
    data = response.json()
    print(json.dumps(data, indent=2))
    print(f"\nResponse keys: {list(data.keys())}")
except Exception as e:
    print(f"Error: {e}")

print()
print()

# Test 3: Check chat completion response for model info
print("3. POST /v1/chat/completions (check response for model info)...")
print("-" * 80)
try:
    payload = {
        "model": "Qwen",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10,
    }
    response = httpx.post(f"{base_url}/chat/completions", json=payload, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    print(json.dumps(data, indent=2))
    
    # Check all keys at all levels
    print(f"\nTop-level keys: {list(data.keys())}")
    if 'choices' in data and len(data['choices']) > 0:
        print(f"Choice keys: {list(data['choices'][0].keys())}")
        if 'message' in data['choices'][0]:
            print(f"Message keys: {list(data['choices'][0]['message'].keys())}")
    if 'usage' in data:
        print(f"Usage keys: {list(data['usage'].keys())}")
except Exception as e:
    print(f"Error: {e}")

print()
print()

# Test 4: Check root endpoint
print("4. GET / (root endpoint)...")
print("-" * 80)
try:
    response = httpx.get(base_url.rstrip('/'), timeout=10.0)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    if 'application/json' in response.headers.get('content-type', ''):
        data = response.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"Content (first 500 chars): {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print()
print()

# Test 5: Check version endpoint
print("5. GET /v1/version (version endpoint)...")
print("-" * 80)
try:
    response = httpx.get(f"{base_url}/version", timeout=10.0)
    response.raise_for_status()
    data = response.json()
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")

print()
print()

# Test 6: Check props endpoint (llama.cpp specific)
print("6. GET /props (llama.cpp props endpoint)...")
print("-" * 80)
try:
    response = httpx.get(f"{base_url}/props", timeout=10.0)
    response.raise_for_status()
    data = response.json()
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print("Check all outputs above for detailed model information.")
print("Look for fields like: model_name, model_path, model_type, size, etc.")
