"""Rebuild audit_full_deck.jsonl with proper def_before from jobs file."""
import json
import re
import hashlib
from collections import Counter, defaultdict

# Read all_verdicts
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    all_verdicts = json.load(f)['verdicts']

# Read rerun verdicts
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_verdicts.json', encoding='utf-8') as f:
    rerun = json.load(f)
if isinstance(rerun, dict) and 'verdicts' in rerun:
    rerun = rerun['verdicts']
rerun_hashes = {x['hash'] for x in rerun}

# Read original jobs (has source def_before)
jobs_by_key = {}
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs.jsonl', encoding='utf-8') as f:
    for l in f:
        j = json.loads(l)
        key = (j['word'], j['pos'], j['cefr'])
        jobs_by_key[key] = j

# Read streamD jobs (the 46 cards we just added)
streamD_jobs = {}
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_streamD.jsonl', encoding='utf-8') as f:
    for l in f:
        j = json.loads(l)
        key = (j['word'], j['pos'], j['cefr'])
        streamD_jobs[key] = j

# Identify which verdicts are streamD (by source field in batch files)
# Read all 4 batch files to identify streamD verdicts
streamD_verdict_keys = set()
for batch in ['D1', 'D2', 'D3', 'D4']:
    with open(rf'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_batch_{batch}.json', encoding='utf-8') as f:
        for v in json.load(f):
            streamD_verdict_keys.add((v['word'], v['pos'], v['cefr']))

# Build verdict lookup
verdict_by_key = {}
for v in all_verdicts:
    key = (v['word'], v['pos'], v['cefr'])
    h = v.get('hash', '')
    if key in streamD_verdict_keys:
        source = 'streamD_legacy_20260618'
    elif h in rerun_hashes:
        source = 'rerun_v2_streamA'
    else:
        source = 'original_100pct'
    verdict_by_key[key] = {**v, 'source': source}

# Read txt
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')

# Parse txt cards
cards = []
skipped_deleted = 0
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) < 15:
        continue
    word = p[3].strip()
    pos = p[4].strip()
    cefr = p[14].strip() or 'UNCLASSIFIED'
    defn = p[6] if len(p) > 6 else ''
    # Skip cards with 'delete' tag (last field, col 15) — Anki will remove
    tags = p[15] if len(p) > 15 else ''
    if 'delete' in tags.split():
        skipped_deleted += 1
        continue
    cards.append({
        'word': word,
        'pos': pos,
        'cefr': cefr,
        'definition_in_txt': defn,
    })
if skipped_deleted:
    print(f'Skipped {skipped_deleted} cards tagged with "delete"')

# Build audit records
audit_records = []
status_count = Counter()
for c in cards:
    key = (c['word'], c['pos'], c['cefr'])
    v = verdict_by_key.get(key)

    # def_before: prefer jobs file (has source def)
    job = jobs_by_key.get(key) or streamD_jobs.get(key)
    def_before = job.get('def', c['definition_in_txt']) if job else c['definition_in_txt']

    if v is None:
        audit_records.append({
            'word': c['word'],
            'pos': c['pos'],
            'cefr': c['cefr'],
            'def_before': def_before,
            'gloss_after': None,
            'separator': None,
            'rule_applied': None,
            'gloss_word_count': None,
            'gate_status': 'not_yet_run',
            'source': None,
        })
        status_count['not_yet_run'] += 1
        continue

    gloss = v.get('gloss', '')
    source = v.get('source', 'original_100pct')

    if '|' in gloss:
        sep = '|'
    elif ';' in gloss:
        sep = ';'
    else:
        sep = 'none'

    rule_applied = v.get('rule_applied', '') or None
    chunks = [c2.strip() for c2 in gloss.replace('|', ';').split(';') if c2.strip()]
    word_count = sum(len(c2.split()) for c2 in chunks)

    is_applied = (c['definition_in_txt'].strip() == gloss.strip())

    # Gate status — check for hidden self-ref leaks (headword in multi-word chunk)
    def has_hidden_leak(word, gloss):
        if not word or not gloss:
            return False
        word_lower = word.lower().strip()
        gloss_lower = gloss.lower()
        chunks = [c.strip() for c in gloss_lower.replace('|', ';').split(';') if c.strip()]
        if any(c == word_lower for c in chunks):
            return False  # exact match is in skip_fallback
        for c in chunks:
            words = c.split()
            if len(words) > 1 and word_lower in words:
                return True
        return False

    if not is_applied:
        gate_status = 'skip_fallback'
    elif has_hidden_leak(c['word'], gloss):
        # Hidden self-ref leak: headword in multi-word chunk, gate misses this
        # Do NOT mark as 'pass' even if structurally valid (silent corruption pattern)
        gate_status = 'known_leak_unfixed'
    elif source == 'original_100pct':
        # Check if this verdict was manually re-audited (has non-empty reasoning)
        if v.get('reasoning', '').strip():
            gate_status = 'pass'  # M3-fixed, treat as audited
        else:
            gate_status = 'unverified_rule_a'
    else:
        gate_status = 'pass'

    audit_records.append({
        'word': c['word'],
        'pos': c['pos'],
        'cefr': c['cefr'],
        'def_before': def_before,
        'gloss_after': gloss if is_applied else None,
        'separator': sep if is_applied else None,
        'rule_applied': rule_applied if is_applied else None,
        'gloss_word_count': word_count if is_applied else None,
        'gate_status': gate_status,
        'source': source,
    })
    status_count[gate_status] += 1

print(f'=== STATUS COUNTS (audit_full_deck.jsonl) ===')
total = 0
for s in ['skip_fallback', 'unverified_rule_a', 'not_yet_run', 'pass']:
    n = status_count.get(s, 0)
    print(f'  {s:20s}: {n}')
    total += n
print(f'  {"TOTAL":20s}: {total}')

# Sort
sort_priority = {'skip_fallback': 0, 'unverified_rule_a': 1, 'not_yet_run': 2, 'pass': 3}
audit_records.sort(key=lambda r: (sort_priority.get(r['gate_status'], 99), r['word'], r['pos'], r['cefr']))

# Write
out_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl'
with open(out_path, 'w', encoding='utf-8') as f:
    for r in audit_records:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print(f'\nWrote {len(audit_records)} records to {out_path}')

# Detailed samples
print('\n=== SAMPLE skip_fallback (first 5) ===')
for r in [r for r in audit_records if r['gate_status'] == 'skip_fallback'][:5]:
    print(f"  {r['word']}|{r['pos']}|{r['cefr']}")
    print(f"    def_before: {r['def_before'][:80]}")
    print(f"    gloss_after: {r['gloss_after']}")

print('\n=== SAMPLE unverified_rule_a (first 3) ===')
for r in [r for r in audit_records if r['gate_status'] == 'unverified_rule_a'][:3]:
    print(f"  {r['word']}|{r['pos']}|{r['cefr']}")
    print(f"    def_before: {r['def_before'][:80]}")
    print(f"    gloss_after: {r['gloss_after']}")

print('\n=== SAMPLE pass (first 3 streamD) ===')
streamD = [r for r in audit_records if r['source'] == 'streamD_legacy_20260618'][:3]
for r in streamD:
    print(f"  {r['word']}|{r['pos']}|{r['cefr']}")
    print(f"    def_before: {r['def_before'][:80]}")
    print(f"    gloss_after: {r['gloss_after']}")

print('\n=== Source breakdown for pass records ===')
src_count = Counter(r['source'] for r in audit_records if r['gate_status'] == 'pass')
for s, n in src_count.most_common():
    print(f'  {s}: {n}')
