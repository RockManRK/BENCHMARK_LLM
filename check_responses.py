import sqlite3, json

conn = sqlite3.Connection('data/bcllm.db')
cursor = conn.cursor()

# Check all responses from our test run
cursor.execute("""
    SELECT response_id, run_id, raw_response, response_text, finish_reason, parse_confidence, selected_answer, needs_review
    FROM responses 
    WHERE run_id = 'run_63517728'
    ORDER BY response_id
""")
rows = cursor.fetchall()

print(f'Total responses in run_63517728: {len(rows)}')
print()

for i, row in enumerate(rows):
    print(f'=== Response {i+1}/{len(rows)} ===')
    print(f'Response ID: {row[0]}')
    print(f'raw_response IS NOT NULL: {row[2] is not None}')
    print(f'response_text: {row[3][:100] if row[3] else "NULL"}...')
    print(f'finish_reason: {row[4]}')
    print(f'parse_confidence: {row[5]}')
    print(f'selected_answer: {row[6]}')
    print(f'needs_review: {row[7]}')
    
    if row[2]:
        raw = json.loads(row[2])
        print(f'raw_response type: {type(raw).__name__}')
        print(f'Chunk count: {len(raw) if isinstance(raw, list) else 1}')
        
        if isinstance(raw, list) and len(raw) > 0:
            print(f'\nFirst chunk:')
            print(f'  Keys: {list(raw[0].keys())}')
            if 'choices' in raw[0]:
                print(f'  Choices: {raw[0]["choices"]}')
            
            print(f'\nLast chunk:')
            print(f'  Keys: {list(raw[-1].keys())}')
            if 'choices' in raw[-1] and len(raw[-1]['choices']) > 0:
                print(f'  Delta: {raw[-1]["choices"][0].get("delta")}')
                print(f'  finish_reason: {raw[-1]["choices"][0].get("finish_reason")}')
    print()
