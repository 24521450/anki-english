import json
from collections import Counter

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    merged = json.load(f)['verdicts']

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_verdicts.json', encoding='utf-8') as f:
    rerun = json.load(f)
# rerun may be a list or {verdicts: [...]} — handle both
if isinstance(rerun, dict) and 'verdicts' in rerun:
    rerun = rerun['verdicts']
print('merged total:', len(merged))
print('rerun total:', len(rerun))

# Identify rerun hashes
rerun_hashes = {x.get('hash') for x in rerun}
print('rerun_hashes count:', len(rerun_hashes))

# Kept = merged minus rerun hashes
kept = [x for x in merged if x.get('hash') not in rerun_hashes]
print('kept (merged - rerun):', len(kept))
print('check 2477 - 889 =', 2477 - 889)

# Self-ref detection (headword as a chunk in gloss)
def is_self_ref(x):
    word = (x.get('word') or '').lower().strip()
    if not word:
        return False
    gloss = (x.get('gloss') or '').lower()
    if not gloss or gloss == 'no-gloss':
        return False
    chunks = [c.strip().strip('"') for c in gloss.replace('|', ';').split(';')]
    chunks = [c for c in chunks if c]
    return any(c == word for c in chunks)

# Headword leak: word as standalone chunk OR as part of multi-word chunk
def has_headword_leak(x):
    word = (x.get('word') or '').lower().strip()
    if not word:
        return False
    gloss = (x.get('gloss') or '').lower()
    chunks = [c.strip() for c in gloss.replace('|', ';').split(';') if c.strip()]
    for c in chunks:
        if c == word:
            return True
        words = c.split()
        if len(words) > 1 and word in words:
            return True
    return False

print('--- KEPT verdicts audit ---')
print('self_ref (gloss == word):', sum(1 for x in kept if is_self_ref(x)))
print('headword-leak (broader):', sum(1 for x in kept if has_headword_leak(x)))
print('clean (no headword in any chunk):', sum(1 for x in kept if not has_headword_leak(x)))

# Word count check on clean
def chunk_count(x):
    gloss = (x.get('gloss') or '').strip()
    if not gloss or gloss.lower() == 'no-gloss':
        return 0
    chunks = [c.strip() for c in gloss.replace('|', ';').split(';') if c.strip()]
    return len(chunks)

def total_word_count(x):
    gloss = (x.get('gloss') or '').strip()
    if not gloss or gloss.lower() == 'no-gloss':
        return 0
    return len(gloss.split())

clean = [x for x in kept if not has_headword_leak(x)]
cc = Counter(chunk_count(x) for x in clean)
print('clean chunk-count dist:', dict(cc))

wc = Counter(total_word_count(x) for x in clean)
print('clean total-word-count dist (>8 means too long):', dict(wc))

# Save self-ref keys for reference
self_ref_keys = [
    {'word': x.get('word'), 'pos': x.get('pos'), 'cefr': x.get('cefr'),
     'gloss': x.get('gloss'), 'rule_applied': x.get('rule_applied')}
    for x in kept if has_headword_leak(x)
]
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_self_ref_keys.json', 'w', encoding='utf-8') as f:
    json.dump(self_ref_keys, f, indent=2, ensure_ascii=False)
print(f'wrote {len(self_ref_keys)} self-ref keys to audit_self_ref_keys.json')
