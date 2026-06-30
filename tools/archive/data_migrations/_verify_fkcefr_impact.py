"""Verify fkcefr fix impact: count cards that had fkcefr vs cefr in HTML,
and check oxford_merged for those."""
import json
import os
from collections import Counter

PROJECT_ROOT = r'C:\Users\admin\Downloads\ankideck'

# Load oxford_merged
oxford = []
with open(f'{PROJECT_ROOT}/data/oxford_merged.jsonl', encoding='utf-8') as f:
    for l in f:
        oxford.append(json.loads(l))

skip = sum(1 for r in oxford if r.get('_skip'))
print(f'Total records: {len(oxford)}, _skip: {skip}')

# Sample a few words that should have fkcefr (test cases)
test_words = ['audition', 'aggregate', 'absorb', 'abolish', 'abstract']
for w in test_words:
    matches = [r for r in oxford if r.get('word', '').lower() == w]
    for m in matches:
        skip = m.get('_skip', False)
        badge = m.get('oxford_badge')
        print(f"  {w}: _skip={skip}, oxford_badge={badge!r}")
