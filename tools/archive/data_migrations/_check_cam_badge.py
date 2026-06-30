"""Check if Cambridge data has oxford_badge set."""
import json

CAMBRIDGE = r"C:\Users\admin\Downloads\ankideck\data\cambridge_full.jsonl"

n_total = 0
n_with_badge = 0
with open(CAMBRIDGE, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        n_total += 1
        if r.get("oxford_badge") is not None:
            n_with_badge += 1
            if n_with_badge <= 3:
                print(f"{r['word']}: badge={r['oxford_badge']}")
print(f"Total: {n_total}, with oxford_badge: {n_with_badge}")
