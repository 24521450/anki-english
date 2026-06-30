"""Find group 2: records with pos_data=[] AND idioms=[] (truly empty)."""
import json

PATH = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

with open(PATH, encoding="utf-8") as f:
    records = [json.loads(l) for l in f]

# Group 1: pos_data=[] but idioms>0 (idiom-only, valid)
group1 = []
# Group 2: pos_data=[] AND idioms=[] (truly empty, parser miss)
group2 = []

for r in records:
    n_pd = len(r.get("pos_data", []))
    n_id = len(r.get("idioms", []))
    if n_pd == 0 and n_id > 0:
        group1.append(r)
    elif n_pd == 0 and n_id == 0:
        group2.append(r)

print(f"Total records: {len(records)}")
print()
print(f"=== Group 1: idiom-only (pos_data=[], idioms>0) ===")
print(f"  Count: {len(group1)}")
for r in group1[:30]:
    print(f"    {r['word']:25s} idioms={len(r['idioms'])}")
if len(group1) > 30:
    print(f"    ... and {len(group1) - 30} more")
print()

print(f"=== Group 2: TRULY EMPTY (pos_data=[], idioms=[]) ===")
print(f"  Count: {len(group2)}")
for r in group2:
    files = r.get("source_files", [])
    files_str = ", ".join(files[:3]) if files else "(no files)"
    print(f"    {r['word']:25s} pos={r['pos']} badge={r.get('oxford_badge')} files={files_str}")
print()

# Also: pos_data=[] but no idioms, but might have other content (audio, verb_forms, etc.)
print("=== Group 2 details (all fields) ===")
for r in group2:
    print(f"  {r['word']}:")
    for k, v in r.items():
        if k in ("$schema", "word", "source", "source_url", "register_tags", "oxford_lists",
                 "opal", "awl", "see_also", "is_phrase", "is_idiom"):
            continue
        if k == "audio":
            print(f"    audio: uk={v.get('uk') is not None}, us={v.get('us') is not None}")
        elif k == "pos_data":
            print(f"    pos_data: [] (empty)")
        elif k == "idioms":
            print(f"    idioms: [] (empty)")
        elif k == "verb_forms":
            print(f"    verb_forms: {v}")
        else:
            print(f"    {k}: {v}")
    print()
