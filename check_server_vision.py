import sys
sys.path.insert(0, '.')

from src.utils.config import get_settings
import httpx

settings = get_settings()

# Check server capabilities
response = httpx.get(f"{settings.openrouter_base_url}/models")
models = response.json()

print("Server Models:")
for model in models.get('data', []):
    print(f"\nModel: {model.get('id')}")
    print(f"  Owned by: {model.get('owned_by')}")
    
    # Check meta
    meta = model.get('meta', {})
    if meta:
        print(f"  Meta:")
        for key, value in meta.items():
            print(f"    {key}: {value}")
