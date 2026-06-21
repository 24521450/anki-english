import json
from pathlib import Path
from collections import Counter

AUDIT_DIR = Path(r"C:\Users\admin\Downloads\ankideck\data\simplify_diff")

# Load
with (AUDIT_DIR / "gloss_all_verdicts.json").open(encoding="utf-8") as f:
    verdicts = json.load(f)["verdicts"]

with (AUDIT_DIR / "full_audit_cases.json").open(encoding="utf-8") as f:
    full = json.load(f)

# 1. Check verdicts completeness
with_rule = sum(1 for v in verdicts if v.get("rule_applied", "").strip())
without_rule = sum(1 for v in verdicts if not v.get("rule_applied", "").strip())
print(f"Total verdicts: {len(verdicts)}")
print(f"  with rule_applied: {with_rule}")
print(f"  without rule_applied (empty/null): {without_rule}")
print(f"  ratio: {without_rule/len(verdicts)*100:.1f}%")

# Sample 10 with rule_applied
print("\nSample 8 with rule_applied:")
shown = 0
for v in verdicts:
    if v.get("rule_applied", "").strip():
        w = v["word"]; p = v["pos"]; c = v["cefr"]
        rule = v["rule_applied"]
        gloss = v["gloss"]
        print(f"  {w}|{p}|{c}: rule={rule!r}, gloss={gloss!r}")
        shown += 1
        if shown >= 8:
            break

# Sample 8 without rule_applied
print("\nSample 8 WITHOUT rule_applied (showing gate detection issue):")
shown = 0
for v in verdicts:
    if not v.get("rule_applied", "").strip():
        w = v["word"]; p = v["pos"]; c = v["cefr"]
        gloss = v["gloss"]
        reason = v.get("reasoning", "")[:60]
        print(f"  {w}|{p}|{c}: gloss={gloss!r}")
        shown += 1
        if shown >= 8:
            break

print("\n" + "=" * 70)
print("134 UNDER-REPRESENTED MULTI-SENSE CASES (def has 3+ chunks, gloss has 1, NOT rule_b_pick1)")
print("=" * 70)
cases = full["layer_c_cases"]["under_represented_multi_sense"]
print(f"Total: {len(cases)}")
print("\nBreakdown by gate_status and source:")
gate_source = Counter()
for c in cases:
    gate_source[(c["gate_status"], c["source"])] += 1
for k, n in gate_source.most_common():
    print(f"  {k}: {n}")

print("\nSample 20 cases for manual review:")
for c in cases[:20]:
    w = c["word"]; p = c["pos"]; ce = c["cefr"]
    print(f"\n  {w}|{p}|{ce}  (def_chunks={c['_def_chunks']}, rule_applied={c['rule_applied']!r}, gate={c['gate_status']})")
    print(f"    def_before: {c['def_before'][:200]}")
    print(f"    gloss:      {c['gloss_after']}")
