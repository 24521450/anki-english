"""Apply semantic gloss drift fix to audit_full_deck_v2.jsonl.

Per task spec (2026-06-21):
- 9 audit rows get new gloss_after, separator, gloss_word_count
- gate_status=pass preserved
- non-essential provenance fields preserved unless directly inconsistent
- ordering of fields in JSON preserved
"""
import json
import re
import shutil
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
AUDIT = ROOT / "data" / "audit_full_deck_v2.jsonl"

# (key tuple) -> (new_gloss, new_separator, new_rule_applied_or_None_to_keep)
# rule_applied set to None means "leave existing value alone"
TARGETS = {
    ("deposit", "noun", "C2"): ("candidate election payment", "none", None),
    ("deposit", "noun", "B2"): ("down payment; security", ";", None),
    ("fit", "noun", "C1"): ("sudden attack", "none", None),
    ("sanctuary", "noun", "C1"): ("wildlife refuge", "none", None),
    ("sake", "noun", "C1"): ("Japanese rice wine", "none", None),
    ("manual", "noun", "C2"): ("stick-shift car", "none", None),  # both duplicates
    ("pitch", "noun", "B2"): ("sports field", "none", None),
    ("concrete", "adjective, noun", "B2"): ("cement-based building material", "none", None),
}

def compute_word_count(gloss: str) -> int:
    """Mirror src/deck_builder/gloss_llm.validate_verdict word count rule."""
    return len(re.sub(r"[|;]", " ", gloss).split())


def main():
    text = AUDIT.read_text(encoding="utf-8")
    lines = text.splitlines()
    updated = 0
    new_lines = []
    audit_keys_seen: dict[tuple, int] = {}

    for ln in lines:
        if not ln.strip():
            new_lines.append(ln)
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            new_lines.append(ln)
            continue

        key = (row.get("word"), row.get("pos"), row.get("cefr"))
        # Track how many times each key appears to handle the manual C2 dup case
        dup_index = audit_keys_seen.get(key, 0)
        audit_keys_seen[key] = dup_index + 1

        if key in TARGETS:
            new_gloss, new_sep, _ = TARGETS[key]
            row["gloss_after"] = new_gloss
            row["separator"] = new_sep
            row["gloss_word_count"] = compute_word_count(new_gloss)
            # gate_status stays as-is (already 'pass')
            updated += 1

        new_lines.append(json.dumps(row, ensure_ascii=False))

    # Write back atomically: write to tmp then rename
    tmp = AUDIT.with_suffix(".jsonl.tmp_glossdrift")
    tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    tmp.replace(AUDIT)
    print(f"Updated {updated} audit rows in {AUDIT.name}")
    print(f"Total target rows: {sum(1 for k in TARGETS)}")


if __name__ == "__main__":
    main()