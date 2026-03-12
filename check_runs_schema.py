import sqlite3
conn = sqlite3.connect('./data/benchmark.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(runs)')
print([col[1] for col in cursor.fetchall()])
conn.close()
