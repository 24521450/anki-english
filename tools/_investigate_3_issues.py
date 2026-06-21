"""Investigate 3 data integrity questions raised in grill session."""
import json
from collections import Counter

OX_MERGED = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

with open(OX_MERGED, encoding="utf-8") as f:
    records = [json.loads(l) for l in f]

# ===========================================================================
# 1. sick: pos array (top) vs pos_data array (nested) length mismatch
# ===========================================================================
print("=" * 70)
print("1. sick — pos (top) vs pos_data (nested) length mismatch")
print("=" * 70)
sick = [r for r in records if r["word"] == "sick"][0]
print(f"  pos (top-level): {sick['pos']}")
print(f"  pos_data entries: {len(sick['pos_data'])}")
print(f"  pos_data pos list: {[pd['pos'] for pd in sick['pos_data']]}")
print()
print("  This is intentional (per Phase 7a investigation):")
print("  - 'pos' top-level = all POS labels visible on the page,")
print("    including from <span class='arl*'> navigation links")
print("  - 'pos_data' = actual POS sections with definitions (1 per real POS)")
print()
print("  Implication for Anki builder: pos array can be a SUPERSET")
print("  of pos_data.pos. Don't iterate 'pos' for cards; iterate pos_data.")
print()

# Find all records where len(pos) > len(pos_data)
mismatches = []
for r in records:
    top_pos_set = set(r["pos"])
    pos_data_set = {pd["pos"] for pd in r["pos_data"]}
    extra_in_top = top_pos_set - pos_data_set
    if extra_in_top:
        mismatches.append((r["word"], r["pos"], [pd["pos"] for pd in r["pos_data"]], extra_in_top))

print(f"  Records where pos (top) is SUPERSET of pos_data.pos: {len(mismatches)} / {len(records)}")
print()
print("  Distribution of extra-POS-in-top (which POS labels appear in top but not pos_data?):")
extra_pos_dist = Counter()
for _, _, _, extra in mismatches:
    for p in extra:
        extra_pos_dist[p] += 1
for p, n in extra_pos_dist.most_common():
    print(f"    {p}: {n} records")
print()

# Sample 5 of these mismatches
print("  Sample 5 mismatches:")
for word, top, nested, extra in mismatches[:5]:
    print(f"    {word:15s} top={top}, nested={[p for p in nested]}, extra-in-top={list(extra)}")
print()

# ===========================================================================
# 2. run: 52 defs, pos_data=2 (noun + verb)
# ===========================================================================
print("=" * 70)
print("2. run — 52 defs, pos_data=2")
print("=" * 70)
run = [r for r in records if r["word"] == "run"][0]
print(f"  pos: {run['pos']}")
print(f"  pos_data entries: {len(run['pos_data'])}")
for pd in run["pos_data"]:
    print(f"    [{pd['pos']}] {len(pd['definitions'])} defs")
    # Show first 3 def texts
    for i, d in enumerate(pd["definitions"][:3], 1):
        text_preview = d["text"][:60] + ("..." if len(d["text"]) > 60 else "")
        print(f"      {i}. {text_preview}")
    if len(pd["definitions"]) > 3:
        print(f"      ... and {len(pd['definitions']) - 3} more")
print()

# Top 10 most-defs records
def def_count(r):
    return sum(len(pd["definitions"]) for pd in r["pos_data"])

top_def_records = sorted(records, key=def_count, reverse=True)[:15]
print("  Top 15 records by total def count:")
for r in top_def_records:
    n_pos = len(r["pos_data"])
    n_defs = def_count(r)
    pos_list = [pd["pos"] for pd in r["pos_data"]]
    print(f"    {r['word']:15s} {n_defs:3d} defs across {n_pos} POS: {pos_list}")
print()

# ===========================================================================
# 3. POS = 'unknown' or empty: 43 records
# ===========================================================================
print("=" * 70)
print("3. POS extraction failures (43 records)")
print("=" * 70)
no_pos = [r for r in records if not r["pos"] or r["pos"] == ["unknown"] or "unknown" in r["pos"]]
print(f"  Records with no/empty/'unknown' top-level pos: {len(no_pos)}")
print()

if no_pos:
    # Are these also empty in pos_data?
    print("  Sub-breakdown:")
    empty_pos_no_pd = 0
    pos_has_pd = 0
    for r in no_pos:
        if not r["pos_data"]:
            empty_pos_no_pd += 1
        else:
            pos_has_pd += 1
    print(f"    pos empty AND pos_data empty:    {empty_pos_no_pd}")
    print(f"    pos empty/missing but pos_data has data: {pos_has_pd}")
    print()

    # Show 10 of them
    print("  Sample 10 records with no/empty pos:")
    for r in no_pos[:10]:
        pos_data_count = len(r["pos_data"])
        word_preview = r["word"][:20] if r["word"] else "(null)"
        # First pos_data pos
        first_pd_pos = r["pos_data"][0]["pos"] if r["pos_data"] else "(none)"
        print(f"    word={word_preview:20s} pos={r['pos']!s:20s} pos_data_count={pos_data_count} first_pd_pos={first_pd_pos}")
    print()

    # What do the actual page URLs look like? Check source_files
    print("  Source file pattern (first 10):")
    for r in no_pos[:10]:
        if r["source_files"]:
            print(f"    {r['source_files'][0]}")
