import sqlite3
import json

conn = sqlite3.connect('data/benchmark.db')
cur = conn.cursor()

# Check recent responses
cur.execute('''
    SELECT response_id, model_id, raw_response_json
    FROM responses 
    ORDER BY response_id DESC 
    LIMIT 1
''')

row = cur.fetchone()

if row and row[2]:
    print(f"Response ID: {row[0]}, Model: {row[1]}")
    print("=" * 100)
    try:
        raw = json.loads(row[2])
        print(json.dumps(raw, indent=2))
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        print(row[2][:1000])
else:
    print("No data found")

conn.close()
