"""Display pilot jobs in human-readable format."""
import json
from pathlib import Path

JOBS = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\pilot_v2_jobs.jsonl')

jobs = [json.loads(l) for l in JOBS.read_text(encoding='utf-8').splitlines() if l.strip()]

# Group by category
by_cat = {}
for j in jobs:
    by_cat.setdefault(j['category'], []).append(j)

for cat in sorted(by_cat):
    print(f'\n=== {cat} ({len(by_cat[cat])}) ===')
    for j in by_cat[cat]:
        w = j['word']; p = j['pos']; c = j['cefr']
        sc = j['sense_count']
        es = j['expected_separator']
        eg = j['expected_gloss_count']
        n = j['notes']
        d = j['def']
        print(f'  [{w}/{p}/{c}] senses={sc} exp_sep={es} n={eg} | {n}')
        print(f'    def: {d[:200]}')
