"""Inspect known_leak_unfixed cards — headword in multi-word chunk."""
import json

records = [json.loads(l) for l in open(
    r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl', encoding='utf-8')]
leaks = [r for r in records if r['gate_status'] == 'known_leak_unfixed']
print(f'Total known_leak_unfixed: {len(leaks)}\n')

for r in leaks:
    word = r['word']
    gloss = r['gloss_after'] or ''
    # Show which chunk contains headword
    chunks = [c.strip() for c in gloss.replace('|', ';').split(';') if c.strip()]
    bad_chunks = [c for c in chunks if word.lower() in c.lower().split() and c.lower() != word.lower()]
    print(f"  {word} | {r['pos']} | {r['cefr']}")
    print(f"    gloss     : {gloss}")
    print(f"    bad_chunks: {bad_chunks}")
    print(f"    def_before: {r['def_before'][:90]}")
    print(f"    source    : {r['source']}")
    print()
