"""Verify homonym records after rebuild."""
import json
from collections import Counter

PATH = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

with open(PATH, encoding="utf-8") as f:
    records = [json.loads(l) for l in f]

print(f"Total records: {len(records)}")
print()

# Distribution of homonym_index
h_idx_dist = Counter()
for r in records:
    h_idx_dist[r.get("homonym_index")] += 1
print("homonym_index distribution:")
for k, v in sorted(h_idx_dist.items(), key=lambda x: (x[0] is None, x[0] or 0)):
    print(f"  {k!s:6s} {v:4d}")
print()

# Find all homonym records
homonyms = [r for r in records if r.get("homonym_index") is not None]
print(f"Homonym records: {len(homonyms)}")
print()

# Group by base word
from collections import defaultdict
by_base = defaultdict(list)
for r in homonyms:
    by_base[r["word"]].append(r)

print(f"Unique homonym base words: {len(by_base)}")
print()

# Show details for bass
for w in ["bass", "bow", "content", "minute", "sake", "pension"]:
    if w in by_base:
        print(f"=== {w} ===")
        for r in sorted(by_base[w], key=lambda r: r["homonym_index"]):
            print(f"  h={r['homonym_index']}: pos={r['pos']}, "
                  f"pos_data={len(r['pos_data'])} entries, "
                  f"defs={sum(len(pd['definitions']) for pd in r['pos_data'])}, "
                  f"idioms={len(r['idioms'])}")
            # Show first def text
            for pd in r["pos_data"]:
                for d in pd["definitions"][:1]:
                    print(f"    [{pd['pos']}] {d['text'][:80]}")
        print()

# Verify no digit in word field
print("=== Verify no digits in word field ===")
bad = [r for r in records if r.get("word") and any(c.isdigit() for c in r["word"])]
print(f"Records with digit in word: {len(bad)} (must be 0)")
if bad:
    for r in bad[:5]:
        print(f"  {r['word']} (h={r.get('homonym_index')})")
