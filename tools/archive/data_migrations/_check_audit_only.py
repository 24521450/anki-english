"""Inspect audit-only entries (in audit but not in oxford)."""
import json
from collections import Counter

AUDIT = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl"
OX = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

audit = {}
with open(AUDIT, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        audit[(r["word"].lower(), r["pos"])] = r

ox = {}
with open(OX, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        for pd in r.get("pos_data", []):
            ox[(r["word"].lower(), pd["pos"])] = r["word"]

extra = [k for k in audit if k not in ox]
print(f"audit-only (word,pos) count: {len(extra)}")
print()
# Group by source field
src_counter = Counter(audit[k]["source"] for k in extra)
print("Source distribution:")
for s, c in src_counter.most_common():
    print(f"  {s:<35} {c}")
print()
print("Sample 30:")
for k in sorted(extra)[:30]:
    a = audit[k]
    defb = a.get("def_before") or ""
    print(f"  {k[0]:<18} pos={k[1]:<14} cefr={str(a.get('cefr')):<6} src={a['source']:<25} def={defb[:60]!r}")
