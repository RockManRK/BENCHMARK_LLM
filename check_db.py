import sqlite3

conn = sqlite3.connect('data/benchmark.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

errs = c.execute('SELECT * FROM errors').fetchall()
print("Errors found:", len(errs))
for e in errs:
    print(dict(e))
    
run = c.execute("SELECT run_id, status FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
print("Latest run status:", dict(run) if run else None)
    
conn.close()
