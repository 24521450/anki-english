"""Show all 17 cards with def_before for verification."""
import json

records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]
leaks = [r for r in records if r['gate_status'] == 'known_leak_unfixed']
leaks.sort(key=lambda r: r['word'])

for r in leaks:
    print(f"\n=== {r['word']} ({r['pos']}, {r['cefr']}) ===")
    print(f"  def_before: {r['def_before']}")
    print(f"  gloss (current): {r['gloss_after']!r}")
    print(f"  separator: {r.get('separator')}")
    print(f"  source: {r.get('source')}")
