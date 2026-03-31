import sqlite3

conn = sqlite3.connect('data/bcllm.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check run status
cur.execute('SELECT run_id, status, duration FROM runs WHERE run_id = ?', ('run_7daaeaa9',))
run = cur.fetchone()
print(f'Run: {run["run_id"]} | Status: {run["status"]} | Duration: {run["duration"]}ms')

# Check responses
cur.execute('''
    SELECT response_id, question_id, model_id, status, selected_answer, 
           input_tokens, output_tokens, latency_ms, parse_confidence, needs_review
    FROM responses 
    WHERE run_id = ?
''', ('run_7daaeaa9',))

print(f'\nResponses ({cur.rowcount}):')
for row in cur.fetchall():
    print(f'  {row["question_id"]}: answer={row["selected_answer"]} | tokens=in:{row["input_tokens"]}/out:{row["output_tokens"]} | latency={row["latency_ms"]}ms | confidence={row["parse_confidence"]} | needs_review={row["needs_review"]}')

# Summary
cur.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
        SUM(CASE WHEN needs_review = 1 THEN 1 ELSE 0 END) as needs_review
    FROM responses 
    WHERE run_id = ?
''', ('run_7daaeaa9',))
summary = cur.fetchone()
print(f'\nSummary:')
print(f'  Total: {summary["total"]}')
print(f'  Success: {summary["success"]}')
print(f'  Needs Review: {summary["needs_review"]}')

conn.close()
