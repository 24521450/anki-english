"""Dump full lists."""
import json
import re
from collections import Counter

OX = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"
AUDIT = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl"
OUT_MISSING = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\sense_missing_222.csv"
OUT_UNMATCHED = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\sense_unmatched_232.csv"


def count_audit_senses(def_before):
    if not def_before or not def_before.strip():
        return 0
    return len([p for p in re.split(r"[|;]", def_before) if p.strip()])


ox_by_word = {}
with open(OX, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        if r.get("_skip"):
            continue
        w = r["word"].lower()
        entry = {"word": r["word"], "badge": r.get("oxford_badge"), "pos_data": []}
        for pd in r.get("pos_data", []):
            p = pd.get("pos")
            if not p:
                continue
            defs = []
            for d in pd.get("definitions", []):
                txt = d.get("text")
                is_null = txt is None or (isinstance(txt, str) and txt.strip() == "")
                defs.append({"cefr": d.get("cefr"), "is_null": is_null, "text": txt})
            entry["pos_data"].append({"pos": p, "defs": defs})
        ox_by_word[w] = entry

audit_records = []
with open(AUDIT, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        w = r["word"].lower()
        if " " in w:
            continue
        audit_records.append({
            "word": w, "pos": r["pos"], "cefr": r.get("cefr"),
            "def_before": r.get("def_before"),
            "senses": count_audit_senses(r.get("def_before")),
        })


def ox_match(word_lower, target_cefr):
    o = ox_by_word.get(word_lower)
    if o is None:
        return None, 0
    badge_match = (o["badge"] == target_cefr) if target_cefr else False
    senses_with_cefr = 0
    sense_match = False
    for pd in o["pos_data"]:
        for d in pd["defs"]:
            if d["cefr"] == target_cefr and not d["is_null"]:
                senses_with_cefr += 1
                sense_match = True
    matched = sense_match or badge_match
    return matched, senses_with_cefr


missing_rows = []
unmatched_rows = []
for a in audit_records:
    o = ox_by_word.get(a["word"])
    badge = o["badge"] if o else ""
    matched, ox_s = ox_match(a["word"], a["cefr"])
    if matched is None:
        unmatched_rows.append({**a, "ox_badge": "", "ox_senses": 0,
                               "reason": "word not in oxford"})
    elif matched and a["senses"] < ox_s:
        missing_rows.append({
            "word": a["word"], "pos": a["pos"], "audit_cefr": a["cefr"],
            "ox_senses": ox_s, "audit_senses": a["senses"],
            "diff": ox_s - a["senses"], "ox_badge": badge,
            "audit_def": a["def_before"] or "",
        })
    elif not matched:
        unmatched_rows.append({**a, "ox_badge": badge, "ox_senses": 0,
                               "reason": f"oxford has no sense/badge with cefr={a['cefr']}"})

# Sort by diff desc, then word
missing_rows.sort(key=lambda r: (-r["diff"], r["word"]))
unmatched_rows.sort(key=lambda r: (str(r["cefr"]), r["word"]))

# Write CSVs
with open(OUT_MISSING, "w", encoding="utf-8", newline="") as f:
    f.write("word,pos,audit_cefr,oxford_senses,audit_senses,missing,oxford_badge,audit_def\n")
    for r in missing_rows:
        defb = (r["audit_def"] or "").replace('"', '""')
        f.write(f'{r["word"]},{r["pos"]},{r["audit_cefr"]},{r["ox_senses"]},{r["audit_senses"]},'
                f'{r["diff"]},{r["ox_badge"]},"{defb[:200]}"\n')

with open(OUT_UNMATCHED, "w", encoding="utf-8", newline="") as f:
    f.write("word,pos,audit_cefr,oxford_badge,reason,audit_def\n")
    for r in unmatched_rows:
        defb = (r["def_before"] or "").replace('"', '""')
        f.write(f'{r["word"]},{r["pos"]},{r["cefr"]},{r["ox_badge"]},{r["reason"]},"{defb[:200]}"\n')

print(f"Wrote {len(missing_rows)} missing cases -> {OUT_MISSING}")
print(f"Wrote {len(unmatched_rows)} unmatched cases -> {OUT_UNMATCHED}")
print()
print(f"Missing diff distribution: {Counter(r['diff'] for r in missing_rows)}")
print(f"Unmatched cefr distribution: {Counter(r['cefr'] for r in unmatched_rows)}")
