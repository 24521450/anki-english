import json
from pathlib import Path

AUDIT_DIR = Path(r"C:\Users\admin\Downloads\ankideck\data\simplify_diff")

with (AUDIT_DIR / "full_audit_cases.json").open(encoding="utf-8") as f:
    full = json.load(f)

# Layer D: headword leaks
print("=" * 70)
print("LAYER D: HEADWORD-IN-GLOSS (all cases)")
print("=" * 70)
leaks = full["layer_d_cases"]["headword_in_gloss"]
print(f"Total: {len(leaks)}")
for c in leaks:
    w = c["word"]; p = c["pos"]; ce = c["cefr"]
    print(f"\n  {w}|{p}|{ce} (rule={c['rule_applied']}, gate={c['gate_status']}, src={c['source']})")
    print(f"    def_before: {c['def_before'][:200]}")
    print(f"    gloss:      {c['gloss_after']}")
    print(f"    leak chunk: {c['_leak_chunk']!r}")

print("\n" + "=" * 70)
print("LAYER C: GENERIC SINGLE GLOSSES")
print("=" * 70)
gen = full["layer_c_cases"]["generic_single_gloss"]
print(f"Total: {len(gen)}")
for c in gen:
    w = c["word"]; p = c["pos"]; ce = c["cefr"]
    print(f"\n  {w}|{p}|{ce} (rule={c['rule_applied']}, gate={c['gate_status']})")
    print(f"    def_before: {c['def_before'][:200]}")
    print(f"    gloss:      {c['gloss_after']}")

print("\n" + "=" * 70)
print("LAYER C: def == gloss (no simplification)")
print("=" * 70)
defeq = full["layer_c_cases"]["def_equals_gloss"]
print(f"Total: {len(defeq)}")
for c in defeq[:25]:
    w = c["word"]; p = c["pos"]; ce = c["cefr"]
    print(f"  {w}|{p}|{ce}: def==gloss={c['gloss_after']!r} (rule={c['rule_applied']}, src={c['source']})")

print("\n" + "=" * 70)
print("LAYER C: ABSTRACT defs (state/act/quality of) - sample 30")
print("=" * 70)
abstract = full["layer_c_cases"]["abstract_def"]
print(f"Total: {len(abstract)}")
print("\nSample 30 cases:")
for c in abstract[:30]:
    w = c["word"]; p = c["pos"]; ce = c["cefr"]
    print(f"\n  {w}|{p}|{ce} (rule={c['rule_applied']}, gate={c['gate_status']}, src={c['source']})")
    print(f"    def_before: {c['def_before'][:180]}")
    print(f"    gloss:      {c['gloss_after']}")
