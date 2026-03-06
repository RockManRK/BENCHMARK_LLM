import sys
sys.path.insert(0, '.')

from src.core.loader import QuestionLoader
from src.api.client import MessageBuilder
from src.utils.config import get_settings
from pathlib import Path
import asyncio

settings = get_settings()
loader = QuestionLoader('data/enamed_questions.json')
questions = loader.load()

# Check Q005
q005 = [q for q in questions if q.question_id == 'Q005'][0]

print(f"Question Q005:")
print(f"  Has Image: {q005.has_image}")
print(f"  Image Path: {q005.image_path}")

# Build multimodal message
builder = MessageBuilder()
message = builder.build_multimodal_message(q005.question_text, Path(q005.image_path))

print(f"\nMessage built:")
print(f"  Role: {message.get('role')}")
print(f"  Content type: {type(message.get('content'))}")

if isinstance(message['content'], list):
    print(f"  Content is list with {len(message['content'])} items")
    for i, item in enumerate(message['content']):
        print(f"    [{i}] Type: {item.get('type', 'N/A')}")
        if 'image_url' in item:
            img_url = item['image_url']
            if isinstance(img_url, dict) and 'url' in img_url:
                url = img_url['url']
                print(f"        URL starts with: {url[:50]}...")
                print(f"        URL length: {len(url)} chars")
                print(f"        Is base64: {url.startswith('data:image')}")

# Try to send
print(f"\nSending to API...")
from src.api.client import OpenRouterClient
client = OpenRouterClient(settings.openrouter_api_key, settings.openrouter_base_url)

async def test():
    try:
        response = await client.chat_completion(
            model='Qwen',
            messages=[message],
            max_tokens=100,
        )
        print(f"✅ Success!")
        print(f"   Model: {response.get('model')}")
        print(f"   Finish: {response['choices'][0]['finish_reason']}")
        print(f"   Content: {response['choices'][0]['message']['content'][:100]}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
