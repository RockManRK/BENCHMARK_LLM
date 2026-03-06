"""
Test to verify what error llama.cpp returns when sending images to non-vision models.
"""
import sys
sys.path.insert(0, '.')

from src.utils.config import get_settings
from src.api.client import OpenRouterClient
from src.api.client import MessageBuilder
from pathlib import Path
import asyncio
import httpx

settings = get_settings()
client = OpenRouterClient(settings.openrouter_api_key, settings.openrouter_base_url)

async def test_image_support():
    """Test if server supports vision by sending an image."""
    
    # Create a small test image (1x1 pixel PNG)
    test_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    # Build message with image
    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "What is in this image?"},
            {"type": "image_url", "image_url": {"url": test_image_base64}}
        ]
    }
    
    print("Testing vision support...")
    print(f"Server: {settings.openrouter_base_url}")
    print(f"Model: Qwen")
    print()
    
    try:
        response = await client.chat_completion(
            model='Qwen',
            messages=[message],
            max_tokens=50,
        )
        
        print(f"✅ SUCCESS - Server supports vision!")
        print(f"   Status: {response.get('model')}")
        print(f"   Finish: {response['choices'][0]['finish_reason']}")
        print(f"   Response: {response['choices'][0]['message']['content'][:100]}")
        return True
        
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP ERROR {e.response.status_code}")
        print(f"   Error: {e.response.text[:200]}")
        
        # Check error details
        try:
            error_json = e.response.json()
            print(f"   Error JSON: {error_json}")
        except:
            pass
        
        return False
        
    except Exception as e:
        print(f"❌ OTHER ERROR: {type(e).__name__}: {e}")
        return False

async def test_text_only():
    """Test if server works with text only."""
    
    message = {
        "role": "user",
        "content": "Hello, this is a text-only message."
    }
    
    print("\nTesting text-only support...")
    
    try:
        response = await client.chat_completion(
            model='Qwen',
            messages=[message],
            max_tokens=20,
        )
        
        print(f"✅ SUCCESS - Text works!")
        print(f"   Response: {response['choices'][0]['message']['content'][:50]}")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

async def main():
    print("="*80)
    print("VISION SUPPORT TEST")
    print("="*80)
    print()
    
    # Test 1: Text only (should work)
    text_works = await test_text_only()
    
    # Test 2: With image (will tell us if vision is supported)
    vision_works = await test_image_support()
    
    print()
    print("="*80)
    print("RESULTS")
    print("="*80)
    print(f"Text-only: {'✅ Works' if text_works else '❌ Failed'}")
    print(f"Vision: {'✅ Supported' if vision_works else '❌ Not supported'}")
    print()
    
    if text_works and not vision_works:
        print("CONCLUSION: Server does NOT support vision.")
        print("Error 500 is returned when sending images to non-vision models.")
    elif text_works and vision_works:
        print("CONCLUSION: Server supports vision!")
    else:
        print("CONCLUSION: Server has issues.")

asyncio.run(main())
