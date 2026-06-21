"""Relaxed oxford search: try (word, pos) without CEFR restriction."""
import json
from collections import defaultdict

PROJECT_ROOT = r'C:\Users\admin\Downloads\ankideck'
records = [json.loads(l) for l in open(f'{PROJECT_ROOT}/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

oxford = []
with open(f'{PROJECT_ROOT}/data/oxford_merged.jsonl', encoding='utf-8') as f:
    for l in f:
        oxford.append(json.loads(l))

oxford_by_pos = defaultdict(list)
for r in oxford:
    if r.get('_skip'):
        continue
    word = r.get('word', '').lower()
    for pd in r.get('pos_data') or []:
        pos = pd.get('pos', '')
        for d in pd.get('definitions') or []:
            cefr = d.get('cefr')
            text = d.get('text', '')
            if text:
                oxford_by_pos[(word, pos)].append((cefr, text))

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

found_match = 0
found_no_cefr_match = 0
not_found = []

existing_jobs = set()
with open(f'{PROJECT_ROOT}/data/simplify_diff/gloss_jobs.jsonl', encoding='utf-8') as f:
    for l in f:
        j = json.loads(l)
        existing_jobs.add((j['word'], j['pos'], j['cefr'], j['def']))

new_jobs_to_add = []

for r in suspicious:
    word = r['word'].lower()
    pos = r['pos']
    cefr = r['cefr']
    key = (word, pos)
    if key in oxford_by_pos:
        for d_cefr, d_text in oxford_by_pos[key]:
            if d_cefr == cefr:
                found_match += 1
                if (word, pos, cefr, d_text) not in existing_jobs:
                    new_jobs_to_add.append({
                        'word': word, 'pos': pos, 'cefr': cefr, 'def': d_text,
                    })
                break
        else:
            if oxford_by_pos[key]:
                d_cefr, d_text = oxford_by_pos[key][0]
                found_no_cefr_match += 1
                if (word, pos, cefr, d_text) not in existing_jobs:
                    new_jobs_to_add.append({
                        'word': word, 'pos': pos, 'cefr': cefr, 'def': d_text,
                    })
            else:
                not_found.append(r)
    else:
        not_found.append(r)

print(f'Found exact CEFR match: {found_match}/{len(suspicious)}')
print(f'Found but wrong CEFR: {found_no_cefr_match}')
print(f'NOT found: {len(not_found)}')

print(f'\nNew jobs to add: {len(new_jobs_to_add)}')
for j in new_jobs_to_add[:10]:
    print(f"  {j['word']}|{j['pos']}|{j['cefr']}: {j['def'][:80]!r}")

out_path = f'{PROJECT_ROOT}/data/simplify_diff/gloss_jobs_def_before_fix_20260618.jsonl'
with open(out_path, 'w', encoding='utf-8') as f:
    for j in new_jobs_to_add:
        f.write(json.dumps(j, ensure_ascii=False) + '\n')
print(f'\nSaved {len(new_jobs_to_add)} new jobs to {out_path}')

print(f'\nNOT found examples:')
for r in not_found[:10]:
    print(f"  {r['word']}|{r['pos']}|{r['cefr']}")
