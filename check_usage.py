import json
import re

with open('logs/benchmark.log', 'r', encoding='utf-8') as f:
    content = f.read()

# Find JSON-like structures in logs
json_pattern = r'\{[^{}]*"usage"[^{}]*\{[^{}]*\}[^{}]*\}'
matches = re.findall(json_pattern, content, re.DOTALL)

print(f"Found {len(matches)} potential usage structures")
for i, match in enumerate(matches[-3:], 1):  # Last 3
    print(f"\n--- Match {i} ---")
    try:
        # Try to parse as JSON
        data = json.loads(match)
        if 'usage' in data:
            print(json.dumps(data['usage'], indent=2))
    except:
        print("Could not parse as JSON")
        print(match[:500])
