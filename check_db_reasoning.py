import sqlite3
import json

conn = sqlite3.connect('data/benchmark.db')
cur = conn.cursor()

# Check recent responses
cur.execute('''
    SELECT response_id, model_id, input_tokens, response_tokens, 
           total_tokens, reasoning_tokens, effective_tokens, 
           raw_response_json
    FROM responses 
    ORDER BY response_id DESC 
    LIMIT 3
''')

rows = cur.fetchall()

print("Recent responses:")
print("=" * 100)
for r in rows:
    print(f"ID: {r[0]}, Model: {r[1]}")
    print(f"  Input: {r[2]}, Response: {r[3]}, Total: {r[4]}, Reasoning: {r[5]}, Effective: {r[6]}")
    
    # Check raw response if reasoning_tokens is NULL
    if r[5] is None and r[7]:
        try:
            raw = json.loads(r[7])
            usage = raw.get('usage', {})
            print(f"  Raw usage structure: {json.dumps(usage, indent=4)}")
        except:
            print(f"  Could not parse raw response JSON")
    print()

conn.close()
