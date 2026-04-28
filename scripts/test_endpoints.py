#!/usr/bin/env python3
"""Quick test of OpenRouter endpoints API."""
import requests
import os
import json
import sys

from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('OPENROUTER_API_KEY')
print(f'API_KEY present: {bool(api_key)}', flush=True)
if not api_key:
    print('ERROR: OPENROUTER_API_KEY not set', file=sys.stderr)
    sys.exit(1)

model = 'meta-llama/llama-3.3-70b-instruct'
url = f'https://openrouter.ai/api/v1/models/{model}/endpoints'
print(f'Calling: {url}', flush=True)

try:
    resp = requests.get(url, headers={'Authorization': f'Bearer {api_key}'}, timeout=30)
    print(f'Status: {resp.status_code}', flush=True)
    data = resp.json()
    
    if isinstance(data, dict) and 'data' in data:
        inner = data['data']
        if isinstance(inner, dict):
            endpoints = inner.get('endpoints', [])
            print(f'Endpoints count: {len(endpoints)}', flush=True)
            if endpoints:
                ep = endpoints[0]
                print(f'First endpoint:', flush=True)
                print(f'  name: {ep.get("name")}', flush=True)
                print(f'  provider_name: {ep.get("provider_name")}', flush=True)
                print(f'  pricing: {ep.get("pricing")}', flush=True)
                print(f'  latency: {ep.get("latency")}', flush=True)
                print(f'  throughput: {ep.get("throughput")}', flush=True)
                print(f'  status: {ep.get("status")}', flush=True)
                # Print full first endpoint
                print(f'\nFull first endpoint (JSON):', flush=True)
                print(json.dumps(ep, indent=2)[:1000], flush=True)
            else:
                print(f'No endpoints. Inner data keys: {list(inner.keys())}', flush=True)
                print(json.dumps(inner, indent=2)[:800], flush=True)
        else:
            print(f'inner is not a dict: {type(inner)}', flush=True)
            print(json.dumps(data, indent=2)[:800], flush=True)
    elif isinstance(data, list):
        print(f'data is a list with {len(data)} items', flush=True)
        print(json.dumps(data[0], indent=2)[:600] if data else 'empty list', flush=True)
    else:
        print(json.dumps(data, indent=2)[:800], flush=True)
except Exception as e:
    print(f'Exception: {e}', file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc()
