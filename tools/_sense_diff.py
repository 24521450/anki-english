"""Đếm senses mỗi bên, so sánh trực tiếp."""
import json
import re
from collections import defaultdict

OX = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"
AUDIT = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl"


def split_pos(p):
    return [x.strip() for x in p.split(",")]


def count_audit_senses(def_before):
    """Đếm senses trong audit def_before.
    Tách theo | (Oxford separator) hoặc ; (English semicolon)."""
    if not def_before or not def_before.strip():
        return 0
    # Oxford dùng | ; một số legacy dùng ;
    parts = re.split(r"[|;]", def_before)
    parts = [p.strip() for p in parts if p.strip()]
    return len(parts)


# Load oxford: (word_lower, pos) -> {senses_count, senses_non_null}
ox = {}
with open(OX, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        if r.get("_skip"):
            continue
        for pd in r.get("pos_data", []):
            p = pd.get("pos")
            if not p:
                continue
            defs = pd.get("definitions", [])
            non_null = [d for d in defs if d.get("text") and d["text"].strip()]
            ox[(r["word"].lower(), p)] = {
                "word": r["word"],
                "pos": p,
                "total_senses": len(defs),
                "non_null_senses": len(non_null),
            }

# Load audit
audit = {}
with open(AUDIT, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        w = r["word"].lower()
        if " " in w:
            continue
        for p in split_pos(r["pos"]):
            audit.setdefault((w, p), []).append({
                "cefr": r.get("cefr"),
                "def_before": r.get("def_before"),
                "senses": count_audit_senses(r.get("def_before")),
            })

# So sánh
print("=" * 80)
print("SO SÁNH SENSE COUNT: oxford non-null vs audit")
print("=" * 80)
print(f"{'word':<18} {'pos':<14} {'oxford':<8} {'audit':<7} diff  audit-def")
print("-" * 110)

missing_sense = []  # audit thiếu so với oxford
exact = []
audit_more = []  # audit có nhiều hơn oxford (cũng đáng chú ý)
audit_empty = []  # audit rỗng

for k in sorted(audit):
    a_recs = audit[k]
    o = ox.get(k)
    audit_senses = a_recs[0]["senses"]
    audit_def = (a_recs[0]["def_before"] or "")[:60]

    if o is None:
        audit_only_key = True
        ox_count = 0
    else:
        audit_only_key = False
        ox_count = o["non_null_senses"]

    diff = ox_count - audit_senses

    if audit_only_key:
        # In oxford thì không có
        print(f"{k[0]:<18} {k[1]:<14} {'(no ox)':<8} {audit_senses:<7} "
              f"{'(in audit only)':<22} {audit_def!r}")
    elif audit_senses == 0:
        audit_empty.append((k, ox_count, audit_def))
    elif diff > 0:
        missing_sense.append((k, ox_count, audit_senses, diff, audit_def))
    elif diff < 0:
        audit_more.append((k, ox_count, audit_senses, -diff, audit_def))
    else:
        exact.append(k)

print()
print("=" * 80)
print(f"THỐNG KÊ")
print("=" * 80)
print(f"Tổng (word,pos) unique trong audit:       {len(audit)}")
print(f"  - match exact (audit == oxford):         {len(exact)}")
print(f"  - AUDIT THIẾU sense (oxford > audit):    {len(missing_sense)}")
print(f"  - audit nhiều hơn oxford:                {len(audit_more)}")
print(f"  - audit def rỗng:                        {len(audit_empty)}")
print(f"  - không có trong oxford:                  {len([k for k in audit if k not in ox])}")
print()

print("=" * 80)
print(f"CHỈ CÁC CASE AUDIT THIẾU SENSE SO VỚI OXFORD ({len(missing_sense)})")
print("=" * 80)
print(f"{'word':<18} {'pos':<14} {'oxford':<8} {'audit':<7} diff  audit-def")
print("-" * 110)
for k, ox_c, a_c, d, defb in sorted(missing_sense):
    print(f"{k[0]:<18} {k[1]:<14} {ox_c:<8} {a_c:<7} -{d:<3} {defb!r}")
