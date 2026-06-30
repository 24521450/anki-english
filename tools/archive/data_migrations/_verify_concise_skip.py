"""Verify the concise_def_skip update against the backup."""
import json
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
audit = ROOT / "data" / "audit_full_deck_v2.jsonl"
backup = ROOT / "data" / "audit_full_deck_v2.jsonl.bak_concise_skip_20260621_090016"

cur = [json.loads(l) for l in audit.read_text(encoding="utf-8").splitlines() if l.strip()]
old = [json.loads(l) for l in backup.read_text(encoding="utf-8").splitlines() if l.strip()]

cur_by = {(r["word"], r["pos"], r["cefr"]): r for r in cur}
old_by = {(r["word"], r["pos"], r["cefr"]): r for r in old}

print(f"current: {len(cur)} records; backup: {len(old)} records")

test_words = ["formerly", "well-being", "spouse", "sibling", "firm", "wellbeing"]
print("\nTest cases (before -> after):")
for w in test_words:
    matches = [r for r in cur if r["word"] == w]
    for r in matches:
        old_r = old_by.get((r["word"], r["pos"], r["cefr"]))
        old_gloss = old_r["gloss_after"] if old_r else "?"
        old_rule = old_r["rule_applied"] if old_r else "?"
        print(
            f"  {r['word']:14} {r['cefr']:12} "
            f"rule: {old_rule!r:>22} -> {r['rule_applied']!r:<22} "
            f"gloss: {old_gloss!r:>40} -> {r['gloss_after']!r}"
        )

skip_count = sum(1 for r in cur if r.get("rule_applied") == "concise_def_skip")
print(f"\nTotal concise_def_skip entries in current file: {skip_count}")
