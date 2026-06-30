"""Check if consist of/in are entries in oxford_merged.jsonl."""
import json

for ln in open(r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl", encoding="utf-8"):
    r = json.loads(ln)
    w = r["word"]
    if "consist" in w.lower():
        print(f"== {w!r} ==")
        print(f"  pos list: {r.get('pos')}")
        for pd in r.get("pos_data", []):
            defs = pd.get("definitions", [])
            for d in defs:
                t = d.get("text")
                print(f"  pos={pd.get('pos')!r} cefr={d.get('cefr')} text={t!r}")
        print()
