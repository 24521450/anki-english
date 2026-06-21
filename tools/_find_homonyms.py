"""Find all records with trailing digit (homonym candidates)."""
import json
import re

PATH = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

with open(PATH, encoding="utf-8") as f:
    records = [json.loads(l) for l in f]

# Find all records with trailing digit
homonym_re = re.compile(r"^(.+?)(\d+)$")
homonyms = {}
for r in records:
    m = homonym_re.match(r["word"] or "")
    if m:
        base = m.group(1)
        idx = int(m.group(2))
        homonyms.setdefault(base, []).append((idx, r["word"], r["pos"]))

print(f"Total homonym base words: {len(homonyms)}")
print(f"Total homonym records: {sum(len(v) for v in homonyms.values())}")
print()

# Sort by base
for base in sorted(homonyms.keys()):
    entries = homonyms[base]
    entries.sort()
    print(f"  {base}: {len(entries)} homonyms")
    for idx, word, pos in entries:
        print(f"    {word:15s} (idx={idx}) pos={pos}")
