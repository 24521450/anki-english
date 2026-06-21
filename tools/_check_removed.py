"""Check which 49 cards were removed by build_notes."""
import json
import os

# Old txt (backup)
old = set()
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt.bak_pre_rebuild_20260618', encoding='utf-8') as f:
    for l in f:
        if l.startswith('#') or not l.strip():
            continue
        p = l.split('\t')
        if len(p) >= 15:
            old.add((p[3], p[4], p[14]))

# New txt
new = set()
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    for l in f:
        if l.startswith('#') or not l.strip():
            continue
        p = l.split('\t')
        if len(p) >= 15:
            new.add((p[3], p[4], p[14]))

removed = old - new
print(f'Removed: {len(removed)} cards')

# Load oxford_merged to check if these are _skip=True
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl', encoding='utf-8')]
skip_keys = set()
for r in oxford:
    if r.get('_skip'):
        for pd in r.get('pos_data') or []:
            skip_keys.add((r.get('word'), pd.get('pos')))

# Show removed cards
removed_with_skip = 0
for w, p, c in sorted(removed)[:20]:
    is_skip = (w, p) in skip_keys
    if is_skip:
        removed_with_skip += 1
    print(f'  {w}|{p}|{c}: _skip={is_skip}')

# Total
print(f'\nOf {len(removed)} removed, {removed_with_skip} have _skip=True in oxford_merged')
