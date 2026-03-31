import sqlite3

conn = sqlite3.connect('data/bcllm.db')
cur = conn.cursor()

# Check responses table schema
cur.execute('PRAGMA table_info(responses)')
print('Responses schema columns:')
for row in cur.fetchall():
    print(f'  {row[1]}')

# Check response count
cur.execute('SELECT COUNT(*) FROM responses WHERE run_id = ?', ('run_7daaeaa9',))
print(f'\nResponse count: {cur.fetchone()[0]}')

# Check response status
cur.execute('SELECT status, COUNT(*) FROM responses GROUP BY status')
print(f'Response status: {cur.fetchall()}')

# Check if responses were written
cur.execute('SELECT response_id, model_id, status, selected_answer FROM responses LIMIT 3')
print(f'\nSample responses:')
for row in cur.fetchall():
    print(f'  {row}')

conn.close()
