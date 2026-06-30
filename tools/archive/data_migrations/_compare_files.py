"""Stats report for oxford_merged.jsonl (the canonical Oxford builder input).

Replaces the pre-v3.1 two-file compare. After v3.1 there is only one Oxford
JSONL on disk; this tool summarizes its contents (record count, source-file
distribution, POS distribution, example record dump).
"""
import json
import os
from collections import Counter

MERGED = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

with open(MERGED, encoding="utf-8") as f:
    m = [json.loads(l) for l in f if l.strip()]

print("=== Record counts ===")
print(f"oxford_merged.jsonl:  {len(m)} records, 1 record per unique (word, homonym_index) pair")
print()

# Source-files-per-record distribution
files_per_record = Counter(len(r["source_files"]) for r in m)
print("=== Source-files per record ===")
for n_files in sorted(files_per_record.keys()):
    print(f"  {n_files} file(s):  {files_per_record[n_files]:4d} records ({100 * files_per_record[n_files] / len(m):.1f}%)")
print()

# POS distribution (top of pos array)
pos_counter = Counter()
for r in m:
    pos_list = r.get("pos") or []
    if pos_list:
        pos_counter[pos_list[0]] += 1
print("=== Top-level POS distribution (first pos in array) ===")
for pos, n in pos_counter.most_common():
    print(f"  {pos:20s}  {n:4d} records")
print()

# Examples
for sample_word in ["aggregate", "sick", "deprive", "transport"]:
    hits = [r for r in m if r["word"] == sample_word]
    if not hits:
        continue
    r = hits[0]
    n_defs = sum(len(pd["definitions"]) for pd in r["pos_data"])
    print(f'=== Example: "{sample_word}" ===')
    print(f"  homonym_index: {r.get('homonym_index')}")
    print(f"  source_files:  {r['source_files']}")
    print(f"  pos:           {r.get('pos')}")
    print(f"  pos_data:      {len(r['pos_data'])} entries, {n_defs} total definitions")
    print(f"  idioms:        {len(r.get('idioms', []))}")
    print(f"  _skip:         {r.get('_skip', False)}")
    print()

# Storage cost
merged_size = os.path.getsize(MERGED) / 1024 / 1024
print("=== File size ===")
print(f"oxford_merged.jsonl:  {merged_size:.1f} MB")
print()

print("=== Purpose ===")
print("oxford_merged.jsonl:  BUILDER INPUT — 1 record per unique (word, homonym_index) pair.")
print("                       This is what the Anki builder consumes.")
print("                       Multi-POS words (e.g. 'absent' as adj/verb/prep) have a single")
print("                       record with multiple POS sections; multi-source words (e.g.")
print("                       'transport' with verb + noun homonym pages) merge their")
print("                       source_files list into one record.")
print("                       Use this tool to spot-check record contents during development.")
