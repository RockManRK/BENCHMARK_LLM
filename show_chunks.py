import sqlite3, json

conn = sqlite3.Connection('data/bcllm.db')
cursor = conn.cursor()

# Get a sample response with full raw_response
cursor.execute('''
    SELECT raw_response FROM responses 
    WHERE run_id = 'run_63517728' AND response_text IS NOT NULL AND response_text != ''
    LIMIT 1
''')
row = cursor.fetchone()

if row and row[0]:
    chunks = json.loads(row[0])
    print(f'Total chunks: {len(chunks)}')
    print(f'\nAll chunks:')
    for i, chunk in enumerate(chunks):
        choice = chunk.get('choices', [{}])[0] if chunk.get('choices') else {}
        delta = choice.get('delta', {})
        finish = choice.get('finish_reason')
        content = delta.get('content', '')
        print(f'  Chunk {i+1}: content="{content}" finish={finish}')
