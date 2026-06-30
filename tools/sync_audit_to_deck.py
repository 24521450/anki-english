"""
tools/sync_audit_to_deck.py
===========================
Syncs anki_notes.txt with deck_audit.jsonl.

Task A: Insert 11 new cards (CEFR discrepancies found in audit but missing in deck).
Task B: Update 521 definition mismatches (overwrite col 6 with gloss_after).

Usage:
    python -m tools.sync_audit_to_deck [--dry-run]
"""

import json
import re
import shutil
import string
import random
import sys
from datetime import datetime
from pathlib import Path

from src.config import ProjectPaths

paths = ProjectPaths()
ROOT = paths.root
AUDIT_FILE = paths.deck_audit_jsonl
DECK_FILE = paths.anki_notes_txt
BACKUP_SUFFIX = f".bak_pre_audit_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

DRY_RUN = "--dry-run" in sys.argv

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ANKI_GUID_CHARS = string.ascii_letters + string.digits

def new_guid(length: int = 10) -> str:
    """Generate a random Anki-compatible GUID."""
    return "".join(random.choices(ANKI_GUID_CHARS, k=length))

def update_cefr_tag(tags: str, old_cefr: str, new_cefr: str) -> str:
    """Replace CEFR::OLD with CEFR::NEW in a space-separated tag string."""
    tag_list = tags.strip().split()
    old_tag = f"CEFR::{old_cefr}"
    new_tag = f"CEFR::{new_cefr}"
    # Replace old CEFR level tag
    result = [new_tag if t == old_tag else t for t in tag_list]
    # Also add new_tag if old wasn't found (safety)
    if old_tag not in tag_list and new_tag not in result:
        result.append(new_tag)
    return " ".join(result)


# ---------------------------------------------------------------------------
# Step 1: Load audit → dict keyed by (word_lower, pos_lower, cefr_upper)
# When duplicates exist, prefer gate_status='pass' > 'unverified_rule_a' > 'skip_fallback'
# ---------------------------------------------------------------------------

GATE_PRIORITY = {"pass": 0, "unverified_rule_a": 1, "skip_fallback": 2}

def load_audit(path: Path) -> dict:
    audit = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            key = (
                r["word"].strip().lower(),
                r["pos"].strip().lower(),
                r["cefr"].strip().upper(),
            )
            existing = audit.get(key)
            if existing is None:
                audit[key] = r
            else:
                # Keep higher priority record
                prio_new = GATE_PRIORITY.get(r.get("gate_status", ""), 99)
                prio_old = GATE_PRIORITY.get(existing.get("gate_status", ""), 99)
                if prio_new < prio_old:
                    audit[key] = r
    return audit


# ---------------------------------------------------------------------------
# Step 2: Load deck file → raw lines, build index
# ---------------------------------------------------------------------------

def load_deck(path: Path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    return lines


def build_deck_index(lines: list) -> dict:
    """Returns {(word_lower, pos_lower, cefr_upper): line_index}"""
    index = {}
    for i, line in enumerate(lines):
        if line.startswith("#") or not line.strip():
            continue
        p = line.split("\t")
        if len(p) < 16:
            continue
        key = (
            p[3].strip().lower(),
            p[4].strip().lower(),
            p[14].strip().upper(),
        )
        index[key] = i
    return index


# ---------------------------------------------------------------------------
# Step 3: Task B — update definitions
# ---------------------------------------------------------------------------

def task_b_update_definitions(lines: list, index: dict, audit: dict):
    updated = 0
    skipped_null = 0
    skipped_same = 0

    for key, rec in audit.items():
        gloss_after = rec.get("gloss_after")
        if not gloss_after or not gloss_after.strip():
            skipped_null += 1
            continue

        line_idx = index.get(key)
        if line_idx is None:
            # Will be handled by Task A (new card)
            continue

        parts = lines[line_idx].rstrip("\n").split("\t")
        if len(parts) < 16:
            continue

        current_def = parts[6].strip()
        new_def = gloss_after.strip()

        if current_def == new_def:
            skipped_same += 1
            continue

        parts[6] = new_def
        lines[line_idx] = "\t".join(parts) + "\n"
        updated += 1

    return updated, skipped_null, skipped_same


# ---------------------------------------------------------------------------
# Step 4: Task A — insert missing cards
# ---------------------------------------------------------------------------

# Canonical ordered list of cards to insert
# Format: (word, pos, new_cefr, gloss_after_override_or_None)
# gloss_after_override: if None → use audit record's gloss_after
# Special case: labor C2 has 2 audit records; we pick 'pass' via load_audit priority
CARDS_TO_INSERT = [
    ("labor",    "noun", "C2", None),
    ("craft",    "noun", "C2", None),
    ("deposit",  "noun", "C2", None),
    ("deposit",  "noun", "C1", None),
    ("fit",      "noun", "B2", None),
    ("migrate",  "verb", "B2", None),
    ("navigate", "verb", "B2", None),
    ("sanctuary","noun", "C1", None),
    ("total",    "verb", "C2", None),
    ("pop",      "verb", "C2", None),
    ("trigger",  "verb", "C2", None),
]


def find_sibling_line_idx(lines: list, word_lower: str, pos_lower: str,
                          exclude_cefr: str) -> int | None:
    """Find a sibling card line index (same word+pos, any CEFR except the one we're adding)."""
    for i, line in enumerate(lines):
        if line.startswith("#") or not line.strip():
            continue
        p = line.split("\t")
        if len(p) < 16:
            continue
        if (p[3].strip().lower() == word_lower
                and p[4].strip().lower() == pos_lower
                and p[14].strip().upper() != exclude_cefr):
            return i
    return None


def task_a_insert_cards(lines: list, audit: dict):
    inserted = 0
    errors = []

    # Process in reverse order so that insertion indices stay valid when we
    # insert after each sibling (we rebuild index each time to be safe)
    for word, pos, new_cefr, gloss_override in CARDS_TO_INSERT:
        key = (word.lower(), pos.lower(), new_cefr.upper())

        # Get gloss_after
        rec = audit.get(key)
        if gloss_override:
            definition = gloss_override
        elif rec and rec.get("gloss_after"):
            definition = rec["gloss_after"].strip()
        else:
            errors.append(f"  SKIP {word} {pos} {new_cefr}: no gloss_after in audit")
            continue

        # Find sibling in current lines
        sibling_idx = find_sibling_line_idx(lines, word.lower(), pos.lower(), new_cefr.upper())
        if sibling_idx is None:
            errors.append(f"  SKIP {word} {pos} {new_cefr}: no sibling found in deck")
            continue

        sibling_parts = lines[sibling_idx].rstrip("\n").split("\t")
        if len(sibling_parts) < 16:
            errors.append(f"  SKIP {word} {pos} {new_cefr}: sibling malformed")
            continue

        old_cefr = sibling_parts[14].strip().upper()

        # Build new card (clone sibling, override specific fields)
        new_parts = sibling_parts[:]
        new_parts[0]  = new_guid()          # col 0: new GUID
        new_parts[6]  = definition           # col 6: definition
        new_parts[7]  = ""                   # col 7: example — leave blank
        new_parts[14] = new_cefr             # col 14: new CEFR
        new_parts[15] = update_cefr_tag(     # col 15: tags
            sibling_parts[15], old_cefr, new_cefr
        )

        new_line = "\t".join(new_parts) + "\n"

        # Insert AFTER sibling
        lines.insert(sibling_idx + 1, new_line)
        inserted += 1
        print(f"  INSERT {word} {pos} {new_cefr}: \"{definition}\"")

    for e in errors:
        print(e)

    return inserted, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("sync_audit_to_deck.py")
    print(f"DRY RUN: {DRY_RUN}")
    print("=" * 60)

    # Backup
    if not DRY_RUN:
        backup_path = DECK_FILE.parent / (DECK_FILE.name + BACKUP_SUFFIX)
        shutil.copy2(DECK_FILE, backup_path)
        print(f"\nBackup created: {backup_path.name}")

    # Load
    print("\n[1/4] Loading audit...")
    audit = load_audit(AUDIT_FILE)
    print(f"      Audit records loaded: {len(audit)}")

    print("[2/4] Loading deck...")
    lines = load_deck(DECK_FILE)
    print(f"      Deck lines loaded: {len(lines)}")

    # Task B
    print("\n[3/4] Task B — updating definitions...")
    index = build_deck_index(lines)
    updated, skipped_null, skipped_same = task_b_update_definitions(lines, index, audit)
    print(f"      Updated:      {updated}")
    print(f"      Skipped (same def): {skipped_same}")
    print(f"      Skipped (null gloss): {skipped_null}")

    # Task A
    print("\n[4/4] Task A — inserting missing cards...")
    inserted, errors = task_a_insert_cards(lines, audit)
    print(f"      Inserted: {inserted}")
    if errors:
        print(f"      Errors/Skips: {len(errors)}")

    # Write
    if not DRY_RUN:
        with open(DECK_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"\nDeck written: {DECK_FILE}")
    else:
        print("\n[DRY RUN] No file written.")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Definitions updated (Task B): {updated}")
    print(f"  Cards inserted    (Task A): {inserted}")
    print(f"  Errors/Skips:               {len(errors)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
