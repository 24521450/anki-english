"""Find all original 30 hidden leaks - check ALL matching (word, pos, cefr) combos."""
import json
from collections import Counter

records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

def has_hidden_leak(word, gloss):
    if not word or not gloss:
        return False
    word_lower = word.lower().strip()
    gloss_lower = gloss.lower()
    chunks = [c.strip() for c in gloss_lower.replace('|', ';').split(';') if c.strip()]
    if any(c == word_lower for c in chunks):
        return False
    for c in chunks:
        words = c.split()
        if len(words) > 1 and word_lower in words:
            return True
    return False

# Find all hidden leaks (current state)
hidden_now = []
for r in records:
    word = r['word']
    gloss = r.get('gloss_after')
    if has_hidden_leak(word, gloss):
        hidden_now.append({
            'word': word, 'pos': r['pos'], 'cefr': r['cefr'],
            'gloss': gloss,
            'gate_status': r['gate_status'],
        })

print(f'Total hidden leaks CURRENTLY: {len(hidden_now)}')
status_count = Counter(h['gate_status'] for h in hidden_now)
print(f'  by status: {dict(status_count)}')

# Save full list
out_path = r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/audit_hidden_self_ref_remaining.jsonl'
with open(out_path, 'w', encoding='utf-8') as f:
    for h in hidden_now:
        f.write(json.dumps(h, ensure_ascii=False) + '\n')
print(f'\nSaved to {out_path}')

# Print all 17
print('\n=== All 17 remaining hidden leaks ===')
for h in hidden_now:
    print(f"  {h['gate_status']:20s} {h['word']:30s} | {h['pos']:10s} | {h['cefr']:13s} | gloss={h['gloss']!r}")
