#!/usr/bin/env python
"""Direct database verification for Block 6e"""

import sqlite3
import json

DB_PATH = 'benchmark.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all responses
cursor.execute('''
    SELECT response_id, response_tokens, input_tokens, review_status, selected_answer, parse_confidence
    FROM responses
    ORDER BY response_id
''')

rows = cursor.fetchall()

print('=== Responses Table Verification ===\n')
print(f'| Response ID | Input Tokens | Response Tokens | Review Status | Answer | Confidence |')
print(f'|-------------|--------------|-----------------|---------------|--------|------------|')

for row in rows:
    resp_id = row['response_id'][:40] if row['response_id'] else 'N/A'
    input_tok = row['input_tokens'] if row['input_tokens'] is not None else 'NULL'
    resp_tok = row['response_tokens'] if row['response_tokens'] is not None else 'NULL'
    review = row['review_status'] if row['review_status'] else 'NULL'
    answer = row['selected_answer'] if row['selected_answer'] else 'NULL'
    conf = row['parse_confidence'] if row['parse_confidence'] else 'NULL'
    print(f'| {resp_id} | {input_tok} | {resp_tok} | {review} | {answer} | {conf} |')

# Check raw_response for first entry
cursor.execute('SELECT raw_response FROM responses LIMIT 1')
row = cursor.fetchone()
if row and row[0]:
    raw = json.loads(row[0])
    print(f'\n=== Raw Response Structure ===')
    print(f'Chunk count: {len(raw)}')
    print(f'First chunk has debug: {"debug" in raw[0]}')
    if 'debug' in raw[0]:
        debug = raw[0]['debug']
        print(f'Debug keys: {list(debug.keys())}')
        if 'echo_upstream_body' in debug:
            body = debug['echo_upstream_body']
            print(f'echo_upstream_body.model: {body.get("model", "N/A")}')
            print(f'echo_upstream_body.messages count: {len(body.get("messages", []))}')
else:
    print('\nNo raw_response found')

# Verify needs_review column does NOT exist
cursor.execute('PRAGMA table_info(responses)')
cols = [col[1] for col in cursor.fetchall()]
needs_review_exists = 'needs_review' in cols

print(f'\n=== Schema Verification ===')
print(f'needs_review column exists: {needs_review_exists}')
print(f'response_tokens column exists: {"response_tokens" in cols}')
print(f'review_status column exists: {"review_status" in cols}')

conn.close()

print('\n=== FINAL STATUS ===')
if not needs_review_exists and 'response_tokens' in cols and 'review_status' in cols:
    print('✅ PASS - All schema fixes verified')
else:
    print('❌ FAIL - Schema issues remain')
