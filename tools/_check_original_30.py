"""Find all original 30 hidden leaks, check which are now still leaking."""
import json

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

# Original 30 from earlier audit
original_30_words = [
    'bat', 'blade', 'closure', 'deployment', 'firework', 'gender', 'hook', 'jet',
    'meantime', 'pace', 'punk', 'radar', 'reporting', 'slam', 'stall', 'tackle',
    'adoption', 'balloon', 'bass', 'behalf', 'boom', 'canvas', 'cutting', 'horn',
    'monthly', 'rip', 'slot', 'snap', 'stark', 'thumb',
]

# For each original 30, look up its (word, pos, cefr) in audit and check if still leaking
for w in original_30_words:
    found = False
    for r in records:
        if r['word'] == w:
            found = True
            gloss = r.get('gloss_after')
            leak = has_hidden_leak(w, gloss)
            status = r['gate_status']
            print(f"  {w:15s} | {r['pos']:10s} | {r['cefr']:13s} | status={status:20s} | leak={'YES' if leak else 'no ':3s} | gloss={gloss!r}")
            break
    if not found:
        print(f"  {w:15s} | NOT IN AUDIT")
