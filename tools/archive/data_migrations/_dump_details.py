"""Dump details for: 17 missing-def skipped, 37 audit-only."""
import json
from collections import Counter

OX = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"
AUDIT = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl"


def expand_pos(p):
    return [x.strip() for x in p.split(",")]


# Load oxford: (word_lower, pos) -> {word, defs, pos_data}
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
            defs = []
            for d in pd.get("definitions", []):
                txt = d.get("text")
                is_null = txt is None or (isinstance(txt, str) and txt.strip() == "")
                defs.append({"n": d.get("n"), "text": txt, "is_null": is_null,
                             "cefr": d.get("cefr")})
            ox[(r["word"].lower(), p)] = {
                "word": r["word"],
                "pos": p,
                "defs": defs,
                "oxford_badge": r.get("oxford_badge"),
            }

# Load audit: (word_lower, pos) -> rec
audit = {}
with open(AUDIT, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        w = r["word"].lower()
        if " " in w:
            continue
        for p in expand_pos(r["pos"]):
            audit.setdefault((w, p), r)

ox_missing = {k: v for k, v in ox.items() if any(d["is_null"] for d in v["defs"])}
missing_not_in_audit = {k: v for k, v in ox_missing.items() if k not in audit}
audit_only = {k: v for k, v in audit.items() if k not in ox}


print("=" * 76)
print(f"17 MISSING-DEF PAIRS (Oxford) CORRECTLY SKIPPED BY BUILD")
print("=" * 76)
print()
print(f"{'word':<14} {'pos':<14} {'good':<5} {'null':<5} {'badge':<6} cefr-distribution | first-good-def")
print("-" * 120)
for k in sorted(missing_not_in_audit):
    v = missing_not_in_audit[k]
    good = [d for d in v["defs"] if not d["is_null"]]
    null = [d for d in v["defs"] if d["is_null"]]
    cefrs = [d["cefr"] for d in v["defs"] if d["cefr"]]
    cefr_dist = Counter(cefrs)
    cefr_str = ",".join(f"{c}×{n}" for c, n in sorted(cefr_dist.items()))
    sample = good[0]["text"][:60] if good else "(NONE)"
    print(f"{v['word']:<14} {v['pos']:<14} {len(good):<5} {len(null):<5} "
          f"{str(v['oxford_badge']):<6} {cefr_str:<25} | {sample!r}")

print()
print("=" * 76)
print(f"37 AUDIT-ONLY PAIRS (in audit, NOT in oxford)")
print("=" * 76)
print()
# Try to find base word in oxford for inflected forms
def find_base(word):
    """Strip common inflections to find base word in oxford."""
    bases = []
    for suffix, strip in [("ies", "y"), ("ied", "y"), ("ying", "y"),
                          ("ed", ""), ("ing", ""), ("ly", ""),
                          ("s", ""), ("es", ""), ("er", ""), ("est", "")]:
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            base = word[: -len(suffix)] + strip
            bases.append(base)
    return bases


print(f"{'word':<18} {'pos':<14} {'cefr':<6} {'src':<28} | base-word-in-oxford? | first-def")
print("-" * 150)
for k in sorted(audit_only):
    a = audit[k]
    w_raw = a["word"]
    bases = find_base(w_raw.lower())
    base_in_ox = None
    for b in bases:
        if any(k_b[0] == b for k_b in ox):
            base_in_ox = b
            break
    if " " in w_raw.lower():
        category = "MULTI-WORD"
    elif base_in_ox:
        category = f"inflected -> {base_in_ox}"
    elif w_raw.lower() in ("solo", "downtown", "behalf"):
        category = "scrape-fail"
    else:
        category = "?"
    defb = (a.get("def_before") or "")[:60]
    print(f"{w_raw:<18} {a['pos']:<14} {str(a.get('cefr')):<6} "
          f"{a.get('source', ''):<28} | {category:<25} | {defb!r}")
