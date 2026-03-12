import sqlite3
conn = sqlite3.connect('./data/benchmark.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

for table in tables:
    if not table[0].startswith('sqlite_'):
        cursor.execute(f'PRAGMA table_info({table[0]})')
        columns = [col[1] for col in cursor.fetchall()]
        print(f"\n{table[0]}: {columns}")
conn.close()
