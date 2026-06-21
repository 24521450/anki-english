"""Find 17 hidden self-ref cases — pass gate (exact match) but headword leaks
into multi-word chunks (e.g. 'adoption' -> 'child adoption' — adoption is part
of multi-word chunk, gate doesn't catch this)."""
import json
from collections import Counter

# Load audit records
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Load verdicts for full content
with open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8') as f:
    all_v = json.load(f)['verdicts']

verdict_by_key = {}
for v in all_v:
    verdict_by_key[(v['word'], v['pos'], v['cefr'])] = v

# Broader headword-leak detector: headword as part of multi-word chunk
def has_hidden_leak(word, gloss):
    word_lower = word.lower().strip()
    if not word_lower or not gloss:
        return False
    gloss_lower = gloss.lower()
    chunks = [c.strip() for c in gloss_lower.replace('|', ';').split(';') if c.strip()]
    for c in chunks:
        words = c.split()
        if len(words) > 1 and word_lower in words:
            return True
    return False

# The 117 self-ref are gate-detected (exact match).
# The 17 broader are headword-in-multi-word-chunk (gate misses).
# Find all hidden leaks (gate passes = no exact match, but multi-word leak exists)

hidden_leaks = []  # headword-in-multi-word-chunk (gate passes)
for r in records:
    if r['gate_status'] in ('pass', 'unverified_rule_a'):
        word = r['word']
        gloss = r['gloss_after']
        if gloss and has_hidden_leak(word, gloss):
            # Make sure it's not exact match (otherwise it's in 117)
            chunks = [c.strip() for c in gloss.lower().replace('|', ';').split(';') if c.strip()]
            if not any(c == word.lower() for c in chunks):
                hidden_leaks.append({
                    'word': word,
                    'pos': r['pos'],
                    'cefr': r['cefr'],
                    'gloss': gloss,
                    'gate_status': r['gate_status'],
                    'source': r.get('source'),
                    'reason': f'headword "{word}" appears as part of multi-word chunk (gate does not catch this)',
                })

print(f'Hidden leaks (pass gate but headword in multi-word chunk): {len(hidden_leaks)}')
print()
for h in hidden_leaks:
    print(f"  {h['gate_status']:20s} {h['word']:30s} | {h['pos']:10s} | {h['cefr']:13s} | gloss={h['gloss']!r} | source={h.get('source')}")

# Save
out_path = r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_hidden_self_ref.jsonl'
with open(out_path, 'w', encoding='utf-8') as f:
    for h in hidden_leaks:
        f.write(json.dumps(h, ensure_ascii=False) + '\n')
print(f'\nSaved {len(hidden_leaks)} hidden leaks to {out_path}')

# Stat by status
status_count = Counter(h['gate_status'] for h in hidden_leaks)
print(f'\nBy gate_status: {dict(status_count)}')
