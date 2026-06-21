"""Validate every updated audit gloss against src.deck_builder.gloss_llm.validate_verdict.

Per task spec: Validate every new gloss with src.deck_builder.gloss_llm.validate_verdict.
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
AUDIT = ROOT / "data" / "audit_full_deck_v2.jsonl"

# Make sure src/ is on path
sys.path.insert(0, str(ROOT))
from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

# Same targets as the edit script
TARGETS = {
    ("deposit", "noun", "C2"): ("candidate election payment", "none"),
    ("deposit", "noun", "B2"): ("down payment; security", ";"),
    ("fit", "noun", "C1"): ("sudden attack", "none"),
    ("sanctuary", "noun", "C1"): ("wildlife refuge", "none"),
    ("sake", "noun", "C1"): ("Japanese rice wine", "none"),
    ("manual", "noun", "C2"): ("stick-shift car", "none"),
    ("pitch", "noun", "B2"): ("sports field", "none"),
    ("concrete", "adjective, noun", "B2"): ("cement-based building material", "none"),
}


def main():
    rows = [json.loads(l) for l in AUDIT.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_key: dict[tuple, list[dict]] = {}
    for r in rows:
        k = (r.get("word"), r.get("pos"), r.get("cefr"))
        by_key.setdefault(k, []).append(r)

    all_ok = True
    print("=" * 80)
    print(f"Validating {len(TARGETS)} target keys (manual C2 has 2 rows):")
    print("=" * 80)
    for key, (expected_gloss, expected_sep) in TARGETS.items():
        matching = by_key.get(key, [])
        if not matching:
            print(f"  [MISS] {key}: no row found in audit")
            all_ok = False
            continue
        for i, row in enumerate(matching):
            word = row["word"]
            gloss = row["gloss_after"]
            sep = row["separator"]
            wc = row["gloss_word_count"]
            chunks = len([c for c in gloss.replace("|", ";").split(";") if c.strip()])
            # Mirror validator's count calculation
            import re
            raw_chunks = re.split(r"\s*[|;]\s*", gloss.strip())
            chunks = len([c for c in raw_chunks if c.strip()])

            violations = validate_verdict(word, gloss, sep, chunks)
            status = "OK" if not violations else "FAIL"
            if violations:
                all_ok = False

            suffix = f" (dup #{i+1}/{len(matching)})" if len(matching) > 1 else ""
            print(f"  [{status}] {key}{suffix}")
            print(f"    gloss='{gloss}' | sep={sep!r} | declared_wc={wc} | actual_chunks={chunks}")
            if violations:
                for v in violations:
                    print(f"    - {v}")

    print("=" * 80)
    print(f"OVERALL: {'PASS' if all_ok else 'FAIL'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()