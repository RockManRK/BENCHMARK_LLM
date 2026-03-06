import sys
sys.path.insert(0, '.')

from src.api.client import OpenRouterClient
from src.utils.config import get_settings
import asyncio

settings = get_settings()
client = OpenRouterClient(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url,
)

async def test():
    print(f"Testing model info for 'Qwen'...")
    print(f"Base URL: {settings.openrouter_base_url}")
    print()
    
    try:
        model_info = await client.get_model_info('Qwen')
        print(f"✅ Model info retrieved:")
        print(f"   ID: {model_info.get('id', 'N/A')}")
        print(f"   Object: {model_info.get('object', 'N/A')}")
        print()
        print(f"Full response:")
        import json
        print(json.dumps(model_info, indent=2))
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"   Would fallback to provided name: 'Qwen'")

asyncio.run(test())
