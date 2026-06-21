"""Split audit_self_ref_keys.json (stale 134) into:
- audit_self_ref_narrow_117.json (gate-detected, exact match)
- audit_hidden_leaks_remaining_17.json (gate-misses, multi-word chunk)
"""
import json
from collections import Counter

# Load remaining hidden leaks (17 currently in audit)
with open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_hidden_self_ref_remaining.jsonl', encoding='utf-8') as f:
    remaining = [json.loads(l) for l in f]

# The narrow 117 = skip_fallback bucket from audit
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Narrow self-ref: words in skip_fallback, with their Oxford def
narrow_keys = []
narrow_set = set()
for r in records:
    if r['gate_status'] == 'skip_fallback':
        narrow_keys.append({
            'word': r['word'],
            'pos': r['pos'],
            'cefr': r['cefr'],
            'def_before': r['def_before'],
            'reason': 'gloss == headword (exact match, gate-detected)',
        })
        narrow_set.add((r['word'], r['pos'], r['cefr']))

print(f'Narrow self-ref (skip_fallback): {len(narrow_keys)}')

# Save
out_narrow = r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_self_ref_narrow_117.json'
with open(out_narrow, 'w', encoding='utf-8') as f:
    for k in narrow_keys:
        f.write(json.dumps(k, ensure_ascii=False) + '\n')
print(f'Saved {len(narrow_keys)} to {out_narrow}')

# Remaining hidden leaks (17)
print(f'\nRemaining hidden leaks: {len(remaining)}')
status_count = Counter(h['gate_status'] for h in remaining)
print(f'  by status: {dict(status_count)}')

# Save
out_hidden = r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_hidden_leaks_remaining_17.json'
with open(out_hidden, 'w', encoding='utf-8') as f:
    for h in remaining:
        f.write(json.dumps(h, ensure_ascii=False) + '\n')
print(f'Saved {len(remaining)} to {out_hidden}')

# Backup the stale 134 file
import shutil
import os
stale = r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_self_ref_keys.json'
if os.path.exists(stale):
    backup = stale + '.stale_134'
    shutil.move(stale, backup)
    print(f'\nMoved stale file to {backup}')
