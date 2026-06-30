import json
from pathlib import Path

AUDIT_DIR = Path(r"C:\Users\admin\Downloads\ankideck\data\simplify_diff")

with (AUDIT_DIR / "full_audit_cases.json").open(encoding="utf-8") as f:
    full = json.load(f)

# Save full 134 cases with complete def_before to a reviewable file
cases = full["layer_c_cases"]["under_represented_multi_sense"]
print(f"Total: {len(cases)}")

# Categorize by source
from collections import Counter
by_source = Counter(c["source"] for c in cases)
print(f"By source: {dict(by_source)}")

# Get 134 cases with FULL def_before
with (AUDIT_DIR / "audit_full_deck.jsonl").open(encoding="utf-8") as f:
    audit = {tuple((c["word"], c["pos"], c["cefr"])): c for c in (json.loads(l) for l in f)}

# Save full review file
review_path = AUDIT_DIR / "full_audit_review_134.jsonl"
with review_path.open("w", encoding="utf-8") as f:
    for c in cases:
        key = (c["word"], c["pos"], c["cefr"])
        full_rec = audit.get(key, c)
        # Use full def_before from audit (which has jobs file def, not truncated)
        f.write(json.dumps({
            "word": c["word"],
            "pos": c["pos"],
            "cefr": c["cefr"],
            "def_before_full": full_rec.get("def_before", c["def_before"]),
            "gloss_after": c["gloss_after"],
            "def_chunks": c["_def_chunks"],
            "rule_applied": c["rule_applied"],
            "gate_status": c["gate_status"],
            "source": c["source"],
        }, ensure_ascii=False) + "\n")
print(f"Saved full review to: {review_path}")

# Show all 134 with full def (truncated to 300 chars for readability)
print("\n" + "=" * 80)
print("ALL 134 UNDER-REPRESENTED MULTI-SENSE CASES")
print("(3+ def chunks → 1 gloss chunk, NOT tagged rule_b_pick1)")
print("=" * 80)
for i, c in enumerate(cases, 1):
    key = (c["word"], c["pos"], c["cefr"])
    full_rec = audit.get(key, c)
    def_full = full_rec.get("def_before", c["def_before"])
    print(f"\n{i:3d}. {c['word']}|{c['pos']}|{c['cefr']}  (def_chunks={c['_def_chunks']}, src={c['source']})")
    print(f"     def_before: {def_full}")
    print(f"     gloss:      {c['gloss_after']}")
