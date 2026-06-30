"""Check consist across backup files."""
import json, os

files = [
    r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl",
    r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl.bak_pre_fkcefr_fix_20260618",
    r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl.bak_pre_hallucination_fix_20260616_203314",
    r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl.bak_pre_def_fixes_v2_20260615_186S",
    r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl.bak_pre_bug2_20260613_110052",
]
for f in files:
    name = os.path.basename(f)
    if not os.path.exists(f):
        print(f"{name}: NOT FOUND")
        continue
    found = False
    with open(f, encoding="utf-8") as fh:
        for ln in fh:
            r = json.loads(ln)
            if r["word"] == "consist":
                for pd in r.get("pos_data", []):
                    for d in pd.get("definitions", []):
                        t = d.get("text")
                        pos = pd.get("pos")
                        cefr = d.get("cefr")
                        snippet = (t or "")[:80]
                        print(f"{name:<70} pos={pos} cefr={cefr} text={snippet!r}")
                        found = True
    if not found:
        print(f"{name}: no consist entry")
