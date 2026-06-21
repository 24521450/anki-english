"""Phase 2 — Upsert 30 glosses from filled.json into audit_full_deck_v2.jsonl.

Per plan:
- Key = (word.lower(), pos.lower(), cefr.upper())
- If key already in audit -> UPDATE gloss_after (filled is source of truth)
- If key not in audit -> APPEND new record
- Idempotent for identical values (writes back same value, file may change line endings)

NOTE: Backup audit_full_deck_v2.jsonl BEFORE running.
"""
import json
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
AUDIT_PATH = ROOT / "data" / "audit_full_deck_v2.jsonl"
FILLED_PATH = ROOT / "data" / "missing_oxford_5000_cards_filled.json"


def _key(r):
    return (
        (r.get("word") or "").strip().lower(),
        (r.get("pos") or "").strip().lower(),
        (r.get("cefr") or "").strip().upper(),
    )


def main():
    # Load audit
    audit = []
    with AUDIT_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                audit.append(json.loads(line))
    print(f"Audit records loaded: {len(audit)}")

    # Index audit by key
    audit_idx = {_key(r): i for i, r in enumerate(audit)}

    # Load filled
    filled = json.load(FILLED_PATH.open(encoding="utf-8"))
    print(f"Filled records: {len(filled)}")

    # Categorize
    n_updated = 0
    n_appended = 0
    n_unchanged = 0
    updates = []  # for dry-run summary
    appends = []

    for r in filled:
        key = _key(r)
        new_ga = (r.get("gloss_after") or "").strip()
        if not new_ga:
            print(f"  SKIP (empty gloss_after): {key}")
            continue
        if key in audit_idx:
            i = audit_idx[key]
            old_ga = (audit[i].get("gloss_after") or "").strip()
            if old_ga == new_ga:
                n_unchanged += 1
                continue
            # Update: replace gloss_after + bump fix_status (audit already has it from filled.json metadata)
            # Preserve other fields — only overwrite gloss_after (and fix_status if present in filled)
            audit[i]["gloss_after"] = new_ga
            if "fix_status" in r:
                audit[i]["fix_status"] = r["fix_status"]
            if "rule_applied" in r:
                audit[i]["rule_applied"] = r["rule_applied"]
            if "source" in r:
                audit[i]["source"] = r["source"]
            updates.append((key, old_ga, new_ga))
            n_updated += 1
        else:
            # Append new record
            audit.append(r)
            appends.append((key, new_ga))
            n_appended += 1

    print()
    print(f"Updated:   {n_updated}")
    print(f"Appended:  {n_appended}")
    print(f"Unchanged: {n_unchanged}")
    print()
    if updates:
        print("=== UPDATES ===")
        for key, old, new in updates:
            print(f"  {key}")
            print(f"    old: {old!r}")
            print(f"    new: {new!r}")
    if appends:
        print("=== APPENDS ===")
        for key, new in appends:
            print(f"  {key} -> {new!r}")

    # Write back
    with AUDIT_PATH.open("w", encoding="utf-8") as f:
        for r in audit:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print()
    print(f"Wrote {len(audit)} records to {AUDIT_PATH.name}")


if __name__ == "__main__":
    main()
