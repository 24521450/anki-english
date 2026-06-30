"""Fix 56 cards' def_before in audit by populating gloss_jobs.jsonl with proper Oxford defs.

For each suspicious card:
  1. Try to find def in oxford_merged.jsonl (canonical Oxford source)
  2. If not found, use streamD jobs (for streamD-generated cards)
  3. If not found, leave as-is

Then re-run build_audit to verify.
"""
import json
import shutil
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
JOBS_PATH = PROJECT_ROOT / 'data/simplify_diff' / 'gloss_jobs.jsonl'
BACKUP = JOBS_PATH.with_suffix('.jsonl.bak_pre_def_before_fix_20260618')

# Load audit
records = [json.loads(l) for l in open(PROJECT_ROOT / 'data/simplify_diff' / 'audit_full_deck.jsonl', encoding='utf-8')]

# Load oxford
oxford = []
with open(PROJECT_ROOT / 'data/oxford_merged.jsonl', encoding='utf-8') as f:
    for l in f:
        oxford.append(json.loads(l))

# Index oxford by (word_lower, pos)
oxford_by_pos = defaultdict(list)
for r in oxford:
    if r.get('_skip'):
        continue
    word = r.get('word', '').lower()
    for pd in r.get('pos_data') or []:
        pos = pd.get('pos', '')
        for d in pd.get('definitions') or []:
            text = d.get('text', '')
            if text:
                oxford_by_pos[(word, pos)].append(d)

# Load streamD jobs
streamd_jobs = {}
with open(PROJECT_ROOT / 'data/simplify_diff' / 'gloss_jobs_streamD.jsonl', encoding='utf-8') as f:
    for l in f:
        j = json.loads(l)
        key = (j['word'], j['pos'], j['cefr'])
        streamd_jobs[key] = j.get('definition', '')

# Load existing jobs
existing_jobs = []
existing_keys = set()
with open(JOBS_PATH, encoding='utf-8') as f:
    for l in f:
        j = json.loads(l)
        existing_jobs.append(j)
        existing_keys.add((j['word'], j['pos'], j['cefr'], j['def']))

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

print(f'Suspicious: {len(suspicious)}')

# Build new jobs
new_jobs = []
for r in suspicious:
    word = r['word']
    pos = r['pos']
    cefr = r['cefr']
    source_def = None
    source = None

    # Try streamD first (for streamD-generated cards)
    key = (word, pos, cefr)
    if key in streamd_jobs and streamd_jobs[key]:
        source_def = streamd_jobs[key]
        source = 'streamD'

    # Try oxford (canonical source)
    if not source_def:
        key_pos = (word.lower(), pos)
        if key_pos in oxford_by_pos:
            for d in oxford_by_pos[key_pos]:
                if d.get('cefr') == cefr and d.get('text'):
                    source_def = d['text']
                    source = 'oxford'
                    break
            else:
                # No exact CEFR match — use first def
                if oxford_by_pos[key_pos]:
                    source_def = oxford_by_pos[key_pos][0].get('text', '')
                    source = 'oxford (CEFR mismatch)'

    if source_def and (word, pos, cefr, source_def) not in existing_keys:
        new_jobs.append({
            'word': word,
            'pos': pos,
            'cefr': cefr,
            'def': source_def,
            '_source': source,
        })

print(f'New jobs to add: {len(new_jobs)}')
for j in new_jobs[:10]:
    src = j.get('_source', '')
    defn = j['def'][:80]
    print(f"  [{src}] {j['word']}|{j['pos']}|{j['cefr']}: {defn!r}")

# Backup + write
shutil.copy(JOBS_PATH, BACKUP)
print(f'\nBackup: {BACKUP}')

# Write new jobs (without _source field — that's metadata)
with open(JOBS_PATH, 'a', encoding='utf-8') as f:
    for j in new_jobs:
        clean = {k: v for k, v in j.items() if k != '_source'}
        f.write(json.dumps(clean, ensure_ascii=False) + '\n')

print(f'Appended {len(new_jobs)} new jobs to {JOBS_PATH}')
print(f'\nNew total: {len(existing_jobs) + len(new_jobs)}')
