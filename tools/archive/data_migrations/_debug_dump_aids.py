"""Dump the AIDS record fully to find '' location."""
import json

with open(r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl") as f:
    for line in f:
        rec = json.loads(line)
        if rec.get("word") != "AIDS":
            continue
        print(json.dumps(rec, indent=2, ensure_ascii=False)[:3000])
        break
