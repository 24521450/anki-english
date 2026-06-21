"""Compare oxford_merged vs audit_full_deck with proper key handling.

Key strategy:
- audit pos can be combined: "noun, verb" → expand to individual POS
- audit words can be multi-word (e.g. "blink of an eye") — skip those (not in oxford scope)
- audit plurals (e.g. "byproducts") — note but don't fault
- oxford pos is always single
"""
import json
from collections import defaultdict, Counter

OX = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"
AUDIT = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl"


def expand_audit_pos(pos_str):
    """'noun, verb' -> ['noun', 'verb']; 'noun' -> ['noun']"""
    return [p.strip() for p in pos_str.split(",")]


# Load oxford: (word_lower, pos) -> {word, defs: [(n, text, is_null)]}
ox = {}
ox_skip = 0
with open(OX, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        if r.get("_skip"):
            ox_skip += 1
            continue
        for pd in r.get("pos_data", []):
            p = pd.get("pos")
            if not p:
                continue
            defs = []
            for d in pd.get("definitions", []):
                txt = d.get("text")
                is_null = txt is None or (isinstance(txt, str) and txt.strip() == "")
                defs.append((d.get("n"), txt, is_null))
            ox[(r["word"].lower(), p)] = {"word": r["word"], "pos": p, "defs": defs}

# Load audit: (word_lower, pos) -> first record
audit = {}
audit_multiword = 0
audit_combined_pos = 0
with open(AUDIT, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        w = r["word"].lower()
        if " " in w:
            audit_multiword += 1
            continue
        for p in expand_audit_pos(r["pos"]):
            if "," in r["pos"]:
                audit_combined_pos += 1
            audit.setdefault((w, p), r)

# Diff
ox_missing_def = {k: v for k, v in ox.items() if any(d[2] for d in v["defs"])}
missing_def_in_audit = {k: v for k, v in ox_missing_def.items() if k in audit}
missing_def_not_in_audit = {k: v for k, v in ox_missing_def.items() if k not in audit}
ox_not_in_audit = {k: v for k, v in ox.items() if k not in audit}
audit_not_in_ox = {k: v for k, v in audit.items() if k not in ox}
both_clean = {k: v for k, v in ox.items() if k in audit and not any(d[2] for d in v["defs"])}

print("=" * 72)
print("LOAD SUMMARY")
print("=" * 72)
print(f"Oxford:     {len(ox)} (word,pos) pairs  ({ox_skip} skipped words)")
print(f"Audit:      {len(audit)} (word,pos) after expanding combined-pos & skipping multi-word")
print(f"  audit multi-word entries skipped: {audit_multiword}")
print(f"  audit records that had combined POS: {audit_combined_pos}")
print()
print("=" * 72)
print("DIFF SUMMARY")
print("=" * 72)
print(f"  (word,pos) in BOTH files:              {len(both_clean)}")
print(f"  (word,pos) in oxford but NOT in audit: {len(ox_not_in_audit)}  <- dropped at build")
print(f"  (word,pos) in audit but NOT in oxford: {len(audit_not_in_ox)}  <- audit has no oxford source")
print()
print("=" * 72)
print("MISSING-DEF ANALYSIS (text=null or empty in oxford_merged)")
print("=" * 72)
print(f"  (word,pos) with >=1 null def in oxford:          {len(ox_missing_def)}")
print(f"  ... of those, IN audit (cards with null def):     {len(missing_def_in_audit)}")
print(f"  ... of those, NOT in audit (correctly skipped):    {len(missing_def_not_in_audit)}")
print()

if missing_def_in_audit:
    print("=" * 72)
    print(f"BUG LIST: (word,pos) with null def that appears in audit ({len(missing_def_in_audit)})")
    print("=" * 72)
    for k, v in sorted(missing_def_in_audit.items()):
        a = audit[k]
        null_defs = [d for d in v["defs"] if d[2]]
        good_defs = [d for d in v["defs"] if not d[2]]
        print(f"\n  {v['word']}  pos={v['pos']}  cefr={a.get('cefr')}")
        print(f"    oxford: {len(v['defs'])} defs total, {len(null_defs)} null, {len(good_defs)} non-null")
        print(f"    audit def_before: {a.get('def_before')!r}")
        print(f"    audit gloss_after: {a.get('gloss_after')!r}")
        if good_defs:
            print(f"    surviving oxford defs:")
            for n, txt, _ in good_defs:
                print(f"      [{n}] {txt}")

print()
print("=" * 72)
print(f"OXFORD-NOT-IN-AUDIT ({len(ox_not_in_audit)} pairs - dropped at build)")
print("=" * 72)
# breakdown by reason
cefr_in_ox = 0
no_cefr_in_ox = 0
for k, v in ox_not_in_audit.items():
    defs_with_cefr = [d for d in v["defs"] if not d[2]]
    if any(d[2] is None for d in v["defs"]):
        no_cefr_in_ox += 1
    else:
        cefr_in_ox += 1
print(f"  have at least one CEFR-tagged def: ~{cefr_in_ox}")
print(f"  have at least one null def: {no_cefr_in_ox}")
print(f"  Top 20 samples:")
for k in sorted(ox_not_in_audit)[:20]:
    v = ox_not_in_audit[k]
    cefrs = []
    for d in v["defs"]:
        # we need to fetch cefr from the original record, not the simplified defs tuple
        pass
    print(f"    {v['word']:<20} pos={v['pos']:<14} defs={len(v['defs'])}")

print()
print("=" * 72)
print(f"AUDIT-NOT-IN-OXFORD ({len(audit_not_in_ox)} pairs - audit has no oxford source)")
print("=" * 72)
src_counter = Counter(audit[k].get("source") for k in audit_not_in_ox)
print("  Source distribution:")
for s, c in src_counter.most_common():
    print(f"    {s:<35} {c}")
print(f"  Top 30 samples:")
for k in sorted(audit_not_in_ox)[:30]:
    a = audit[k]
    print(f"    {k[0]:<20} pos={k[1]:<14} cefr={str(a.get('cefr')):<6} def={(a.get('def_before') or '')[:60]!r}")

# Re-check missing-def-not-in-audit list
print()
print("=" * 72)
print(f"MISSING-DEF NOT IN AUDIT (correctly skipped, {len(missing_def_not_in_audit)})")
print("=" * 72)
for k, v in sorted(missing_def_not_in_audit.items()):
    null_defs = [d for d in v["defs"] if d[2]]
    good_defs = [d for d in v["defs"] if not d[2]]
    print(f"  {v['word']:<20} pos={v['pos']:<14} null={len(null_defs)} good={len(good_defs)}")
