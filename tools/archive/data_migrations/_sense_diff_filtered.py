"""Compare audit vs oxford senses filtered by CEFR match.

Logic:
1. For each audit (word, pos, cefr):
   - Find word in oxford (any POS)
   - Check CEFR match: any sense's cefr == audit's cefr OR word's oxford_badge == audit's cefr
   - If NO match -> filter out (audit cefr not from oxford)
   - If match -> count oxford senses with that cefr (any POS) and audit senses
2. Report stats + list of "audit missing senses" cases
"""
import json
import re
from collections import defaultdict, Counter

OX = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"
AUDIT = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl"


def split_audit_pos(p):
    return [x.strip() for x in p.split(",")]


def count_audit_senses(def_before):
    if not def_before or not def_before.strip():
        return 0
    parts = re.split(r"[|;]", def_before)
    return len([p for p in parts if p.strip()])


# Load oxford: word_lower -> {badge, pos_data: [{pos, defs: [{cefr, text, is_null}]}]}
ox_by_word = {}
with open(OX, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        if r.get("_skip"):
            continue
        w = r["word"].lower()
        entry = {
            "word": r["word"],
            "badge": r.get("oxford_badge"),
            "pos_data": [],
        }
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

# Load audit
audit_records = []
with open(AUDIT, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        w = r["word"].lower()
        if " " in w:
            continue
        audit_records.append({
            "word": w,
            "pos": r["pos"],
            "cefr": r.get("cefr"),
            "def_before": r.get("def_before"),
            "senses": count_audit_senses(r.get("def_before")),
        })

# Process each audit record
def oxford_has_cefr_match(word_lower, target_cefr):
    """Return (matched: bool, badge_match: bool, senses_with_cefr: int)"""
    o = ox_by_word.get(word_lower)
    if o is None:
        return False, False, 0
    badge_match = (o["badge"] == target_cefr) if target_cefr else False
    senses_with_cefr = 0
    sense_match = False
    for pd in o["pos_data"]:
        for d in pd["defs"]:
            if d["cefr"] == target_cefr and not d["is_null"]:
                senses_with_cefr += 1
                sense_match = True
    return (sense_match or badge_match), badge_match, senses_with_cefr


matched_cases = []     # word has oxford match for the audit's cefr
unmatched_cases = []   # word has NO oxford match for the audit's cefr (filtered out)

for a in audit_records:
    matched, badge_match, ox_senses = oxford_has_cefr_match(a["word"], a["cefr"])
    rec = {
        **a,
        "matched": matched,
        "badge_match": badge_match,
        "ox_senses": ox_senses,
    }
    if matched:
        matched_cases.append(rec)
    else:
        unmatched_cases.append(rec)

# Among matched: identify audit_missing (audit_senses < ox_senses)
audit_missing = [c for c in matched_cases if c["senses"] < c["ox_senses"]]
audit_extra = [c for c in matched_cases if c["senses"] > c["ox_senses"]]
audit_exact = [c for c in matched_cases if c["senses"] == c["ox_senses"]]

# Sort by missing count desc
audit_missing.sort(key=lambda c: (c["ox_senses"] - c["senses"]), reverse=True)

print("=" * 80)
print("FILTER + SO SÁNH SENSE COUNT")
print("=" * 80)
print(f"Filter: oxford có sense hoặc badge với cefr = audit's cefr (bất kể POS)")
print()
print(f"Tổng audit records (đã skip multi-word): {len(audit_records)}")
print(f"  - MATCH (oxford có CEFR này cho word):     {len(matched_cases)}")
print(f"    - exact (audit == oxford):                {len(audit_exact)}")
print(f"    - audit THIẾU sense (oxford > audit):     {len(audit_missing)}")
print(f"    - audit nhiều hơn oxford:                 {len(audit_extra)}")
print(f"  - KHÔNG MATCH (audit cefr không có ở oxford): {len(unmatched_cases)}")
print()

# Show unmatched distribution by CEFR (for context)
print("=" * 80)
print("AUDIT RECORDS BỊ FILTER RA (audit cefr không có ở oxford)")
print("=" * 80)
unmatched_cefr = Counter(c["cefr"] for c in unmatched_cases)
print(f"Phân bố theo CEFR:")
for cefr, n in unmatched_cefr.most_common():
    print(f"  {str(cefr):<15} {n}")
print()

print("=" * 80)
print(f"AUDIT THIẾU SENSE ({len(audit_missing)} cases) — TOP 50 THIẾU NHIỀU NHẤT")
print("=" * 80)
print(f"{'word':<18} {'pos':<14} {'audit-cefr':<11} {'ox':<4} {'au':<4} diff  | ox-badge | audit-def")
print("-" * 130)
for c in audit_missing[:50]:
    o = ox_by_word.get(c["word"])
    badge = o["badge"] if o else None
    badge_str = str(badge) if badge else "-"
    defb = (c["def_before"] or "")[:55]
    print(f"{c['word']:<18} {c['pos']:<14} {str(c['cefr']):<11} "
          f"{c['ox_senses']:<4} {c['senses']:<4} -{c['ox_senses']-c['senses']:<3} "
          f"| {badge_str:<8} | {defb!r}")

if len(audit_missing) > 50:
    print(f"\n... và {len(audit_missing)-50} cases nữa. In tiếp không?")

# Also count how many of missing are "real concern" (diff >= 2) vs "minor" (diff == 1)
big_missing = [c for c in audit_missing if c["ox_senses"] - c["senses"] >= 2]
print()
print("=" * 80)
print("THỐNG KÊ MỨC ĐỘ THIẾU")
print("=" * 80)
diff_dist = Counter(c["ox_senses"] - c["senses"] for c in audit_missing)
for d, n in sorted(diff_dist.items()):
    print(f"  thiếu {d} sense: {n} cases")
print(f"  Tổng cases thiếu >= 2 senses: {len(big_missing)}")
