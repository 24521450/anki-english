"""Find cards where def_before == gloss_after (audit fallback bug).

The audit's def_before falls back to current txt def when the card is not
in gloss_jobs.jsonl. After apply, current txt def IS the gloss. So for
any card not in gloss_jobs, def_before = gloss_after = same gloss text.
This is the bug pattern.

Find all such cards and report.
"""
import json
from collections import Counter

records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Find cards where def_before == gloss_after (or where def_before contains the gloss)
suspicious = []
for r in records:
    db = r.get('def_before', '')
    gl = r.get('gloss_after')
    if gl and db and db.strip() == gl.strip():
        suspicious.append({
            'word': r['word'],
            'pos': r['pos'],
            'cefr': r['cefr'],
            'def_before': db,
            'gloss_after': gl,
            'gate_status': r['gate_status'],
        })
    # Also: def_before starts with the gloss word (broader check)
    elif gl and db and gl.strip().split()[0] in db and len(db.split()) <= 2:
        suspicious.append({
            'word': r['word'],
            'pos': r['pos'],
            'cefr': r['cefr'],
            'def_before': db,
            'gloss_after': gl,
            'gate_status': r['gate_status'],
            'note': 'def_before might be gloss word in single chunk',
        })

print(f'Suspicious cards (def_before == gloss_after or similar): {len(suspicious)}')
for s in suspicious[:10]:
    print(f"\n  {s['word']}|{s['pos']}|{s['cefr']} ({s['gate_status']})")
    print(f"    def_before: {s['def_before'][:80]!r}")
    print(f"    gloss_after: {s['gloss_after']!r}")
    if 'note' in s:
        print(f"    note: {s['note']}")
