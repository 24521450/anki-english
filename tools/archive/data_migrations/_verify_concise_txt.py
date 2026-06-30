"""Final precise check: verify all 37 concise_def_skip words made it into the rebuilt txt.

Anki txt column layout (0-indexed):
  0: GUID, 1: notetype, 2: deck, 3: word, 4: POS, 5: IPA, 6: DEF,
  7: examples, 8-9: idioms, 10: audio UK, 11: audio US, 12: src1,
  13: src2, 14: CEFR, 15: notes, 16: tags
"""
import json
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
txt = (ROOT / "English Academic Vocabulary.txt").read_text(encoding="utf-8")
audit = [json.loads(l) for l in (ROOT / "data" / "audit_full_deck_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

WORD_IDX = 3
DEF_IDX = 6
CEFR_IDX = 14

# Index cards by (word, cefr)
cards = {}
for line in txt.splitlines():
    if line.startswith("#") or "\t" not in line:
        continue
    fields = line.split("\t")
    if len(fields) <= CEFR_IDX:
        continue
    key = (fields[WORD_IDX], fields[CEFR_IDX])
    cards.setdefault(key, []).append(fields)

skip_records = [r for r in audit if r.get("rule_applied") == "concise_def_skip"]
print(f"Total concise_def_skip audit records: {len(skip_records)}")

ok = bad = missing = 0
mismatches = []
for r in skip_records:
    key = (r["word"], r["cefr"])
    matches = cards.get(key, [])
    if not matches:
        missing += 1
        print(f"  MISSING: {r['word']} {r['cefr']}  expected def={r['def_before']!r}")
        continue
    expected = r["def_before"]
    matched = False
    for fields in matches:
        if fields[DEF_IDX] == expected:
            matched = True
            ok += 1
            break
    if not matched:
        bad += 1
        actual = matches[0][DEF_IDX]
        mismatches.append((r["word"], r["cefr"], expected, actual))

print(f"\nResults: ok={ok}  bad={bad}  missing={missing}")
if mismatches:
    print("Mismatches:")
    for w, c, exp, act in mismatches:
        print(f"  {w} {c}: expected={exp!r}  actual={act!r}")
