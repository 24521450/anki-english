"""Fix 56 cards' def_before in audit by populating from oxford_merged.jsonl.

For each suspicious card (def_before == gloss_after or similar), look up the
canonical source def in oxford_merged.jsonl and update the audit record.

Approach: directly update the audit file with corrected def_before values.
This is a one-time fix; the audit is rebuilt by build_audit.py from txt +
jobs files, so a re-run would lose the fix. Need to either:
  (a) Add the def to gloss_jobs.jsonl so re-runs are correct
  (b) Just fix the audit file directly

Going with (a) — add to gloss_jobs.jsonl, then re-run build_audit.
"""
import json
from collections import Counter, defaultdict

PROJECT_ROOT = r'C:\Users\admin\Downloads\ankideck'
JOBS_PATH = f'{PROJECT_ROOT}/data/simplify_diff/gloss_jobs.jsonl'

# Load audit
records = [json.loads(l) for l in open(f'{PROJECT_ROOT}/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Load oxford_merged.jsonl
oxford = []
with open(f'{PROJECT_ROOT}/data/oxford_merged.jsonl', encoding='utf-8') as f:
    for l in f:
        oxford.append(json.loads(l))

# Index oxford by (word, pos, cefr) → list of defs at that CEFR
oxford_by_key = defaultdict(list)
for r in oxford:
    if r.get('_skip'):
        continue
    word = r.get('word', '').lower()
    for pd in r.get('pos_data') or []:
        pos = pd.get('pos', '')
        for d in pd.get('definitions') or []:
            cefr = d.get('cefr')
            text = d.get('text', '')
            if cefr and text:
                oxford_by_key[(word, pos, cefr)].append(text)

# Find suspicious records (def_before == gloss_after or very similar)
suspicious = []
for r in records:
    db = r.get('def_before', '') or ''
    gl = r.get('gloss_after')
    if gl is None:
        continue
    if db.strip() == gl.strip():
        suspicious.append(r)
    # Also: def_before is a SHORT (≤3 word) string and contains gloss
    elif len(db.split()) <= 2 and gl.strip() in db:
        suspicious.append(r)

print(f'Suspicious: {len(suspicious)}')

# Check how many can be found in oxford_merged
found = 0
not_found = []
for r in suspicious:
    key = (r['word'].lower(), r['pos'], r['cefr'])
    if key in oxford_by_key:
        found += 1
    else:
        not_found.append(r)

print(f'Found in oxford_merged: {found}/{len(suspicious)}')
print(f'NOT found: {len(not_found)}')
for r in not_found[:5]:
    print(f"  {r['word']}|{r['pos']}|{r['cefr']}")
