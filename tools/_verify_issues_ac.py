"""Verify Issue A: 4 main words + 4 PV records after fold."""
import json

with open(r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl", encoding="utf-8") as f:
    rs = [json.loads(l) for l in f]

from collections import Counter
by_reason = Counter()
for r in rs:
    if r.get("_skip"):
        by_reason[r.get("_skip_reason", "(none)")] += 1
print("ALL skip reasons:")
for reason, n in sorted(by_reason.items(), key=lambda x: -x[1]):
    print(f"  {n:3d} | {reason}")
print(f"Total skips: {sum(by_reason.values())}")
print()

print("Issue A — 4 main words:")
for w in ["deprive", "derive", "devote", "rely"]:
    matches = [r for r in rs if r["word"] == w]
    for r in matches:
        h = r.get("homonym_index")
        skip = r.get("_skip")
        reason = r.get("_skip_reason")
        print(f"  {w:10s} (h={h}): _skip={skip}, reason={reason}, pos={r['pos']}, pos_data_count={len(r['pos_data'])}, idioms={len(r['idioms'])}")
print()

print("Issue A — 4 phrasal-verb records:")
for w in ["deprive of", "derive from", "devote to", "rely on"]:
    matches = [r for r in rs if r["word"] == w]
    for r in matches:
        skip = r.get("_skip")
        reason = r.get("_skip_reason")
        print(f"  {w:12s}: _skip={skip}, reason={reason}, pos_data_count={len(r['pos_data'])}")
print()

# Sample 10 proper-noun-or-cultural-entry skips
print("Issue C — 10 samples of proper-noun-or-cultural-entry:")
pn = [r for r in rs if r.get("_skip_reason") == "proper-noun-or-cultural-entry: no CEFR/oxford-list membership"]
for r in pn[:10]:
    print(f"  {r['word']:25s} pos={r['pos']} badge={r.get('oxford_badge')} oxford_lists={r.get('oxford_lists')}")
print(f"Total proper-noun skips: {len(pn)}")
