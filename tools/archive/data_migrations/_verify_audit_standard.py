"""Verify audit_full_deck.jsonl against the user's original spec.

Spec (from earlier in session):
- JSONL, 1 record per line
- 9 fields: word, pos, cefr, def_before, gloss_after, separator,
  rule_applied, gloss_word_count, gate_status, source
- gate_status in {pass, skip_fallback, unverified_rule_a, not_yet_run}
- def_before = full Oxford def (post β+γ)
- gloss_after = applied gloss in txt, or null if gate-skip
- separator in {none, |, ;} or null
- Sort by (gate_status priority, word) — skip_fallback first
"""
import json
from collections import Counter

records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]
print(f'Total records: {len(records)}')

# Check schema
required_fields = ['word', 'pos', 'cefr', 'def_before', 'gloss_after', 'separator', 'rule_applied', 'gloss_word_count', 'gate_status', 'source']
for f in required_fields:
    present = all(f in r for r in records)
    print(f'  field {f}: {"OK" if present else "MISSING"} ({sum(1 for r in records if f in r)}/{len(records)})')

# Check field types
print('\n=== Field type sample (first 3) ===')
for r in records[:3]:
    for f in required_fields:
        v = r.get(f)
        t = type(v).__name__
        if isinstance(v, str) and len(v) > 60:
            v = v[:60] + '...'
        print(f'  {f}: ({t}) {v!r}')
    print()

# gate_status distribution
sc = Counter(r['gate_status'] for r in records)
print(f'\n=== gate_status distribution ===')
for s, n in sc.most_common():
    print(f'  {s}: {n}')

# Spec gate_status set
spec_set = {'pass', 'skip_fallback', 'unverified_rule_a', 'not_yet_run'}
extra = set(sc.keys()) - spec_set
missing = spec_set - set(sc.keys())
print(f'\nExtra gate_status (NOT in original spec): {extra}')
print(f'Missing gate_status (in spec but not present): {missing}')

# def_before: should be Oxford def (not gloss). Check first 5
print('\n=== def_before sample (first 5) ===')
for r in records[:5]:
    print(f"  {r['word']:15s} | {r['pos']:10s} | def_before={r['def_before'][:60]!r}")

# Check: def_before is from jobs file (post β+γ) — verify by comparing to a known record
import json as j
jobs = [j.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_jobs.jsonl', encoding='utf-8')]
job_dict = {(j['word'], j['pos'], j['cefr']): j['def'] for j in jobs}
sample_match = 0
sample_total = 0
for r in records[:50]:
    key = (r['word'], r['pos'], r['cefr'])
    if key in job_dict:
        sample_total += 1
        if r['def_before'] == job_dict[key]:
            sample_match += 1
print(f'\n=== def_before vs jobs file match (first 50) ===')
print(f'  matched: {sample_match}/{sample_total}')

# gloss_after: should be the def currently in txt
# Read txt
with open(r'C:\Users\admin\Downloads\ankideck/English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')
txt_defs = {}
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) < 15:
        continue
    txt_defs[(p[3].strip(), p[4].strip(), p[14].strip() or 'UNCLASSIFIED')] = p[6] if len(p) > 6 else ''

# Compare gloss_after to txt def
print('\n=== gloss_after vs txt def match (sample) ===')
match_count = 0
mismatch_count = 0
null_count = 0
for r in records:
    key = (r['word'], r['pos'], r['cefr'])
    txt_def = txt_defs.get(key)
    gloss = r.get('gloss_after')
    if gloss is None:
        null_count += 1
    elif txt_def is not None and gloss.strip() == txt_def.strip():
        match_count += 1
    else:
        mismatch_count += 1
print(f'  match: {match_count}')
print(f'  mismatch: {mismatch_count}')
print(f'  null: {null_count}')

# separator validity
print('\n=== separator validity ===')
valid_sep = {None, 'none', '|', ';'}
invalid_sep = set(r.get('separator') for r in records) - valid_sep
print(f'  unique separators: {set(r.get("separator") for r in records)}')
print(f'  invalid: {invalid_sep}')

# Sort order check
# Spec: "sort by gate_status first (skip_fallback, unverified_rule_a, not_yet_run, pass)"
# Then alphabetical by word
# But known_leak_unfixed is added — should it be before pass or where?
# Spec implies only 4 buckets, doesn't account for known_leak_unfixed
print('\n=== Sort order check ===')
prev_status = None
prev_word = None
sort_ok = True
priority = {'skip_fallback': 0, 'unverified_rule_a': 1, 'not_yet_run': 2, 'pass': 3, 'known_leak_unfixed': 4}
for r in records:
    cur_pri = priority.get(r['gate_status'], 99)
    if prev_status is not None:
        if cur_pri < priority.get(prev_status, 99):
            sort_ok = False
            break
        if cur_pri == priority.get(prev_status, 99) and r['word'] < prev_word:
            sort_ok = False
            break
    prev_status = r['gate_status']
    prev_word = r['word']
print(f'  sort OK: {sort_ok}')

# Final check: total = 2,528
print(f'\n=== Total check ===')
print(f'  records: {len(records)} (expected 2,528)')
print(f'  sum by status: {sum(sc.values())}')
