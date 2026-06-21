"""Verify audit + TXT changes match expected mappings, and no old bad chunks remain.

Layer-by-layer check:
  L1: Audit row exists with exact (gloss_after, separator, gloss_word_count)
  L2: TXT row has matching def cell
  L3: Targeted negative check - old bad chunks NOT present in any matching key
  L4: Side-effect scan - no other rows accidentally touched
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
AUDIT = ROOT / "data" / "audit_full_deck_v2.jsonl"
TXT = ROOT / "English Academic Vocabulary.txt"

# Expected mapping per task
EXPECTED_AUDIT = {
    ("deposit", "noun", "C2"): {"gloss": "candidate election payment", "sep": "none", "wc": 3},
    ("deposit", "noun", "B2"): {"gloss": "down payment; security", "sep": ";", "wc": 3},
    ("fit", "noun", "C1"): {"gloss": "sudden attack", "sep": "none", "wc": 2},
    ("sanctuary", "noun", "C1"): {"gloss": "wildlife refuge", "sep": "none", "wc": 2},
    ("sake", "noun", "C1"): {"gloss": "Japanese rice wine", "sep": "none", "wc": 3},
    ("manual", "noun", "C2"): {"gloss": "stick-shift car", "sep": "none", "wc": 2},  # 2 rows
    ("pitch", "noun", "B2"): {"gloss": "sports field", "sep": "none", "wc": 2},
    ("concrete", "adjective, noun", "B2"): {"gloss": "cement-based building material", "sep": "none", "wc": 3},
}

EXPECTED_TXT = {
    ("concrete", "adjective, noun", "B2"): "cement-based building material",
    ("deposit", "noun", "B2"): "down payment; security",
    ("fit", "noun", "C1"): "sudden attack",
    ("manual", "noun", "C2"): "stick-shift car",
    ("pitch", "noun", "B2"): "sports field",
    ("sake", "noun", "C1"): "Japanese rice wine",
    ("sanctuary", "noun", "C1"): "wildlife refuge",
}

# Old bad chunks that should NOT appear in any updated row
# (regex substring pattern that would indicate drift)
BAD_CHUNKS = {
    ("deposit", "noun", "C2"): ["bank", "sediment", "naturally underground", "layer of a substance"],
    ("deposit", "noun", "B2"): ["money paid into a bank", "sediment"],
    ("fit", "noun", "C1"): ["sizing", "suitability"],
    ("sanctuary", "noun", "C1"): ["holy place", "safety or protection"],
    ("sake", "noun", "C1"): ["for the sake of", "for the purpose"],
    ("manual", "noun", "C2"): ["instruction book"],
    ("pitch", "noun", "B2"): ["level of a sound", "persuasive speech", "sound"],
    ("concrete", "adjective, noun", "B2"): ["specific and definite", "cement, sand and stone"],
}


def main():
    ok = True
    print("=" * 80)
    print("L1: AUDIT row exactness check")
    print("=" * 80)
    rows = [json.loads(l) for l in AUDIT.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_key: dict[tuple, list[dict]] = {}
    for r in rows:
        k = (r.get("word"), r.get("pos"), r.get("cefr"))
        by_key.setdefault(k, []).append(r)

    for key, exp in EXPECTED_AUDIT.items():
        matching = by_key.get(key, [])
        if not matching:
            print(f"  [FAIL] {key}: NO ROW")
            ok = False
            continue
        for i, row in enumerate(matching):
            ga = row.get("gloss_after")
            sep = row.get("separator")
            wc = row.get("gloss_word_count")
            gs = row.get("gate_status")
            sub = f" (dup #{i+1}/{len(matching)})" if len(matching) > 1 else ""
            checks = []
            if ga != exp["gloss"]:
                checks.append(f"gloss={ga!r} != {exp['gloss']!r}")
            if sep != exp["sep"]:
                checks.append(f"sep={sep!r} != {exp['sep']!r}")
            if wc != exp["wc"]:
                checks.append(f"wc={wc} != {exp['wc']}")
            if gs != "pass":
                checks.append(f"gate_status={gs!r} != 'pass'")
            if checks:
                print(f"  [FAIL] {key}{sub}: " + "; ".join(checks))
                ok = False
            else:
                print(f"  [OK]   {key}{sub}: gloss={ga!r} sep={sep!r} wc={wc} gate={gs!r}")

    print()
    print("=" * 80)
    print("L2: TXT def cell match check")
    print("=" * 80)
    txt_text = TXT.read_text(encoding="utf-8")
    for ln in txt_text.splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 17:
            continue
        word, pos, defn = parts[3], parts[4], parts[6]
        cefr = parts[14]
        key = (word, pos, cefr)
        if key in EXPECTED_TXT:
            exp_def = EXPECTED_TXT[key]
            if defn == exp_def:
                print(f"  [OK]   {key}: def='{defn}'")
            else:
                print(f"  [FAIL] {key}: def={defn!r} != {exp_def!r}")
                ok = False
    # Also report any expected TXT keys that were NOT found
    found_keys = set()
    for ln in txt_text.splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 17:
            continue
        key = (parts[3], parts[4], parts[14])
        found_keys.add(key)
    for key in EXPECTED_TXT:
        if key not in found_keys:
            print(f"  [FAIL] {key}: no TXT row found (cannot sync)")
            ok = False

    print()
    print("=" * 80)
    print("L3: BAD-CHUNK ABSENCE check")
    print("=" * 80)
    for key, bad_substrings in BAD_CHUNKS.items():
        matching = by_key.get(key, [])
        for i, row in enumerate(matching):
            ga = (row.get("gloss_after") or "").lower()
            hits = [b for b in bad_substrings if b.lower() in ga]
            sub = f" (dup #{i+1}/{len(matching)})" if len(matching) > 1 else ""
            if hits:
                print(f"  [FAIL] {key}{sub}: bad chunks still present: {hits}")
                ok = False
            else:
                print(f"  [OK]   {key}{sub}: no bad chunks in '{row.get('gloss_after')}'")

    # Also scan TXT rows for the same bad chunks
    print()
    print("--- TXT bad-chunk scan ---")
    txt_keys_in_scope = set(EXPECTED_TXT.keys())
    for ln in txt_text.splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 17:
            continue
        word, pos, defn, cefr = parts[3], parts[4], parts[6], parts[14]
        key = (word, pos, cefr)
        if key in txt_keys_in_scope:
            bad_substrings = BAD_CHUNKS.get(key, [])
            lower_def = defn.lower()
            hits = [b for b in bad_substrings if b.lower() in lower_def]
            if hits:
                print(f"  [FAIL] TXT {key}: bad chunks still present: {hits}")
                ok = False

    print()
    print("=" * 80)
    print("L4: SIDE-EFFECT SCAN - count of rows changed should match expectation")
    print("=" * 80)
    # Quick sanity: 9 audit rows (manual C2 is duplicated)
    expected_audit_changes = sum(1 for k, ms in [(k, by_key.get(k, [])) for k in EXPECTED_AUDIT] for _ in ms)
    print(f"  Expected audit rows touched: {expected_audit_changes}")
    # Actual: count rows whose gloss_after matches one of the new expected glosses
    new_glosses = {exp["gloss"] for exp in EXPECTED_AUDIT.values()}
    actual_changes = sum(1 for r in rows if r.get("gloss_after") in new_glosses)
    print(f"  Actual audit rows with new glosses: {actual_changes}")
    if actual_changes != expected_audit_changes:
        print(f"  [FAIL] unexpected change count: {actual_changes} != {expected_audit_changes}")
        ok = False
    else:
        print(f"  [OK]   counts match")

    print()
    print("=" * 80)
    print(f"OVERALL: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()