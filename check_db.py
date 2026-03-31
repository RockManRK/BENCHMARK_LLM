import sqlite3

conn = sqlite3.connect('data/bcllm.db')
cur = conn.cursor()

# Check table schema
cur.execute('PRAGMA table_info(runs)')
print('Runs schema:')
for row in cur.fetchall():
    print(f'  {row}')

# Check current run status
cur.execute('SELECT run_id, status FROM runs WHERE run_id = ?', ('run_7daaeaa9',))
print(f'\nRun status before: {cur.fetchone()}')

# Update run status to pending
cur.execute('UPDATE runs SET status = ? WHERE run_id = ?', ('pending', 'run_7daaeaa9'))
print(f'Rows updated: {cur.rowcount}')

conn.commit()

# Verify
cur.execute('SELECT run_id, status FROM runs WHERE run_id = ?', ('run_7daaeaa9',))
print(f'Run status after: {cur.fetchone()}')

conn.close()
