import sqlite3

conn = sqlite3.connect('data/bcllm.db')
conn.execute('PRAGMA foreign_keys = ON')
cur = conn.cursor()

# Reset run status to pending
cur.execute('UPDATE runs SET status = ? WHERE run_id = ?', ('pending', 'run_7daaeaa9'))

# Clear old responses and errors
cur.execute('DELETE FROM responses WHERE run_id = ?', ('run_7daaeaa9',))
cur.execute('DELETE FROM errors WHERE run_id = ?', ('run_7daaeaa9',))

conn.commit()

# Verify
cur.execute('SELECT run_id, status FROM runs WHERE run_id = ?', ('run_7daaeaa9',))
print(f'Run status: {cur.fetchone()}')

cur.execute('SELECT COUNT(*) FROM responses WHERE run_id = ?', ('run_7daaeaa9',))
print(f'Response count: {cur.fetchone()[0]}')

conn.close()
