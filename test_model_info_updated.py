from src.api.client import OpenRouterClient
from src.utils.config import get_settings
import asyncio

settings = get_settings()
client = OpenRouterClient(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url,
)

async def test():
    print('Testing get_model_info...')
    info = await client.get_model_info('Qwen')
    print(f'Model ID: {info.get("id")}')
    print(f'Owned by: {info.get("owned_by")}')
    print(f'Meta keys: {list(info.get("meta", {}).keys())}')
    print(f'Meta: {info.get("meta")}')
    print(f'Context length: {info.get("context_length")}')
    print(f'Max completion tokens: {info.get("max_completion_tokens")}')

asyncio.run(test())
