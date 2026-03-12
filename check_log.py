import json

with open('logs/benchmark.log', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find lines with usage
usage_lines = [l for l in lines if 'usage' in l.lower()][-10:]
print("Recent usage log entries:")
for line in usage_lines:
    print(line.strip())
