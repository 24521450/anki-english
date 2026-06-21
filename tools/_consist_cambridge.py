"""Check Cambridge jsonl for consist."""
import json
for ln in open(r"C:\Users\admin\Downloads\ankideck\data\cambridge_full.jsonl", encoding="utf-8"):
    r = json.loads(ln)
    w = r.get("word")
    if w and w.lower() == "consist":
        print(json.dumps(r, ensure_ascii=False, indent=2)[:2000])
        break
else:
    print("consist NOT in cambridge_full.jsonl")
