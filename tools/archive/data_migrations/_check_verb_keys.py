"""Find all distinct verb_form keys in Oxford data."""
import json
from collections import Counter

key_counter = Counter()
with open(r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        vf = r.get("verb_forms")
        if vf:
            for k in vf.keys():
                key_counter[k] += 1
print("All verb_forms keys (count):")
for k, c in key_counter.most_common():
    print(f"  {k}: {c}")
