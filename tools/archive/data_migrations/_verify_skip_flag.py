"""Verify _skip flag distribution after merge."""
import json

PATH = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

with open(PATH, encoding="utf-8") as f:
    records = [json.loads(l) for l in f]

skipped = [r for r in records if r.get("_skip") is True]
not_skipped = [r for r in records if r.get("_skip") is not True]
print(f"Total: {len(records)}")
print(f"  _skip=True:   {len(skipped)}")
print(f"  _skip=False:  {len(not_skipped)}")
print(f"  no _skip key: {len(records) - len(skipped) - len(not_skipped)}")
print()

print("Skipped records:")
for r in skipped:
    print(f"  {r['word']:15s} reason: {r.get('_skip_reason', '(none)')}")
print()

# Spot check: sick should have _skip=False
sick = [r for r in records if r["word"] == "sick"][0]
print(f"sick _skip: {sick.get('_skip')}")
print(f"sick _skip_reason: {sick.get('_skip_reason', '(absent)')}")
print()

# Spot check: aggregate should have _skip=False
agg = [r for r in records if r["word"] == "aggregate"][0]
print(f"aggregate _skip: {agg.get('_skip')}")
print(f"aggregate pos_data count: {len(agg['pos_data'])}")
print()

# Spot check: like should have _skip=False
lk = [r for r in records if r["word"] == "like"][0]
print(f"like _skip: {lk.get('_skip')}")
print(f"like pos_data count: {len(lk['pos_data'])}")

# Spot check: idiom-only words (accordance, Nod) should have _skip=False (idioms present)
for w in ["accordance", "Nod", "rid"]:
    r = [r for r in records if r["word"] == w]
    if r:
        r = r[0]
        print(f"{w:15s} _skip={r.get('_skip')}, idioms={len(r.get('idioms', []))}, pos_data={len(r.get('pos_data', []))}")
