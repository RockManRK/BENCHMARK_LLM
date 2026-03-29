#!/usr/bin/env python3
"""Test ConfigResolver with EXPLICIT_NULL."""

from src.core.config_resolver import ConfigResolver
from src.core.null_semantics import EXPLICIT_NULL

resolver = ConfigResolver()
resolver.load_env()
resolver.env_dict['RANDOM_SEED'] = '42'
resolver.env_dict['MODEL_TOP_K'] = '50'
resolver.env_dict['SYSTEM_PROMPT'] = 'Default system prompt'

print("=" * 60)
print("ConfigResolver with EXPLICIT_NULL Tests")
print("=" * 60)

# Test 1: Seed resolution
print("\n1. Seed Resolution:")
result1 = resolver.resolve_seed(None, 'RANDOM_SEED', 'test')
print(f"   None (not specified):     seed = {result1}")  # Should be 42

result2 = resolver.resolve_seed(EXPLICIT_NULL, 'RANDOM_SEED', 'test')
print(f"   EXPLICIT_NULL (explicit): seed = {result2}")  # Should be None

result3 = resolver.resolve_seed('123', 'RANDOM_SEED', 'test')
print(f"   '123' (CLI value):        seed = {result3}")  # Should be 123

# Test 2: Prompt resolution
print("\n2. Prompt Resolution:")
result4 = resolver.resolve_prompt(None, 'SYSTEM_PROMPT', None)
print(f"   None (not specified):     prompt = {repr(result4)}")  # Should be 'Default system prompt'

result5 = resolver.resolve_prompt(EXPLICIT_NULL, 'SYSTEM_PROMPT', None)
print(f"   EXPLICIT_NULL (explicit): prompt = {repr(result5)}")  # Should be None

result6 = resolver.resolve_prompt('Custom prompt', 'SYSTEM_PROMPT', None)
print(f"   'Custom prompt' (CLI):    prompt = {repr(result6)}")  # Should be 'Custom prompt'

# Test 3: Helper method
print("\n3. Helper Method (_resolve_with_explicit_null):")
result7 = resolver._resolve_with_explicit_null(None, 'MODEL_TOP_K', resolver._parse_int_env)
print(f"   None (not specified):     top_k = {result7}")  # Should be 50

result8 = resolver._resolve_with_explicit_null(EXPLICIT_NULL, 'MODEL_TOP_K', resolver._parse_int_env)
print(f"   EXPLICIT_NULL (explicit): top_k = {result8}")  # Should be None

result9 = resolver._resolve_with_explicit_null('75', 'MODEL_TOP_K', resolver._parse_int_env)
print(f"   '75' (CLI value):         top_k = {result9}")  # Should be 75

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
