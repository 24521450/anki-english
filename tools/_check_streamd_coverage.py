"""Check if 53 missing cards are in streamD jobs file."""
import json

PROJECT_ROOT = r'C:\Users\admin\Downloads\ankideck'
records = [json.loads(l) for l in open(f'{PROJECT_ROOT}/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Load streamD jobs
streamd_jobs = {}
with open(f'{PROJECT_ROOT}/data/simplify_diff/gloss_jobs_streamD.jsonl', encoding='utf-8') as f:
    for l in f:
        j = json.loads(l)
        key = (j['word'], j['pos'], j['cefr'])
        streamd_jobs[key] = j.get('definition', '')

print(f'streamD jobs total: {len(streamd_jobs)}')

# Find suspicious
suspicious = []
for r in records:
    db = r.get('def_before', '') or ''
    gl = r.get('gloss_after')
    if gl is None:
        continue
    if db.strip() == gl.strip():
        suspicious.append(r)
    elif len(db.split()) <= 2 and gl.strip() in db:
        suspicious.append(r)

# Check streamD coverage
in_streamd = 0
not_in_streamd = []
for r in suspicious:
    key = (r['word'], r['pos'], r['cefr'])
    if key in streamd_jobs:
        in_streamd += 1
    else:
        not_in_streamd.append(r)

print(f'In streamD: {in_streamd}/{len(suspicious)}')
print(f'NOT in streamD: {len(not_in_streamd)}')
for r in not_in_streamd[:10]:
    print(f"  {r['word']}|{r['pos']}|{r['cefr']}")
