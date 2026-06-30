"""Spot check Phase 7b merged output."""
import json

OUT = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

with open(OUT, "r", encoding="utf-8") as f:
    records = {json.loads(line)["word"]: json.loads(line) for line in f}

for w in ["aggregate", "like", "sick", "up"]:
    r = records.get(w)
    if r is None:
        print(f"*** {w} NOT FOUND ***")
        continue
    pos_list = [pd["pos"] for pd in r.get("pos_data", [])]
    n_defs = sum(len(pd["definitions"]) for pd in r.get("pos_data", []))
    n_idioms = len(r.get("idioms", []))
    print(
        f"{w:12s}: pos={r['pos']}, "
        f"pos_data={pos_list}, defs={n_defs}, "
        f"idioms={n_idioms}, files={len(r['source_files'])}"
    )
    if w == "aggregate":
        print(f"             source_files = {r['source_files']}")
        for pd in r["pos_data"]:
            defs = [d["text"][:30] for d in pd["definitions"]]
            print(f"             {pd['pos']}: {defs}")
        if r.get("idioms"):
            for i in r["idioms"]:
                print(f"             idiom: {i.get('phrase')}")
