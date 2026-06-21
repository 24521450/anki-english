"""Re-run hidden leak detection, find 18 remaining, reclassify the ones in 'pass'
to a new bucket 'known_leak_unfixed' so 'pass' bucket doesn't claim verified."""
import json
from collections import Counter

# Find remaining hidden leaks (after the 12 fixed)
with open(r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8') as f:
    all_v = json.load(f)['verdicts']

# Load current audit
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Find hidden leaks (headword in multi-word chunk, not exact match)
def has_hidden_leak(word, gloss):
    if not word or not gloss:
        return False
    word_lower = word.lower().strip()
    gloss_lower = gloss.lower()
    chunks = [c.strip() for c in gloss_lower.replace('|', ';').split(';') if c.strip()]
    if any(c == word_lower for c in chunks):
        return False  # exact match is in narrow self-ref, not hidden
    for c in chunks:
        words = c.split()
        if len(words) > 1 and word_lower in words:
            return True
    return False

# Get fixed cards (have reasoning that starts with fix marker)
# Markers: "RULE A fix:", "HIDDEN SELF-REF fix:", "GLOSS TOO STRONG fix:" (etc.)
fixed_keys = set()
for v in all_v:
    r = v.get('reasoning', '').strip()
    if r.startswith(('RULE A fix:', 'HIDDEN SELF-REF fix:', 'GLOSS TOO STRONG fix:')):
        fixed_keys.add((v['word'], v['pos'], v['cefr']))

# Find all hidden leaks, distinguish fixed vs remaining
all_hidden = []
for r in records:
    word = r['word']
    gloss = r.get('gloss_after')
    if not has_hidden_leak(word, gloss):
        continue
    key = (word, r['pos'], r['cefr'])
    is_fixed = key in fixed_keys
    all_hidden.append({
        'word': word, 'pos': r['pos'], 'cefr': r['cefr'],
        'gloss': gloss,
        'gate_status': r['gate_status'],
        'source': r.get('source'),
        'is_fixed': is_fixed,
    })

remaining = [h for h in all_hidden if not h['is_fixed']]
print(f'Total hidden leaks: {len(all_hidden)}')
print(f'Fixed: {sum(1 for h in all_hidden if h["is_fixed"])}')
print(f'Remaining: {len(remaining)}')

# Count by gate_status
status_count = Counter(h['gate_status'] for h in remaining)
print(f'\nRemaining by gate_status: {dict(status_count)}')

# Specifically: how many in pass?
remaining_in_pass = [h for h in remaining if h['gate_status'] == 'pass']
remaining_in_unverified = [h for h in remaining if h['gate_status'] == 'unverified_rule_a']
print(f'  in pass: {len(remaining_in_pass)}')
print(f'  in unverified_rule_a: {len(remaining_in_unverified)}')

print('\n=== 11 remaining in pass (silently corrupt) ===')
for h in remaining_in_pass:
    print(f"  {h['word']:35s} | {h['pos']:10s} | {h['cefr']:13s} | gloss={h['gloss']!r} | source={h.get('source')}")
