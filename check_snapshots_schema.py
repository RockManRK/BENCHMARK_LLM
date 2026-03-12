import sqlite3

conn = sqlite3.connect('data/benchmark.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(question_snapshots)')
cols = cur.fetchall()

print('Colunas da tabela question_snapshots:')
for c in cols:
    print(f'  {c[1]} ({c[2]})')

conn.close()
