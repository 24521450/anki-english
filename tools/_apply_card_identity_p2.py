"""P2 Card Identity Dedup tool.

Safely deduplicates 5 exact (word, pos, cefr) duplicate keys in the audit master file.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ProjectPaths
paths = ProjectPaths(PROJECT_ROOT)
MASTER_AUDIT = paths.deck_audit_jsonl

LOSER_GUARDS = [
    # 1. labor
    {
        "word": "labor", "pos": "noun", "cefr": "C2",
        "def_before": "the period of time or the process of giving birth to a baby",
        "gloss_after": "process of giving birth",
        "gate_status": "skip_fallback", "source": "original_100pct",
        "rule_applied": "concrete_1sense", "fix_status": "rebuilt"
    },
    # 2. migrate
    {
        "word": "migrate", "pos": "verb", "cefr": "C1",
        "def_before": "to move from one town, country, etc. to go and live and/or work in another",
        "gloss_after": "move",
        "gate_status": "skip_fallback", "source": "original_100pct",
        "rule_applied": None, "fix_status": "p1_rewritten"
    },
    # 3. navigate
    {
        "word": "navigate", "pos": "verb", "cefr": "C1",
        "def_before": "to find your way around on the internet or on a particular website",
        "gloss_after": "find way",
        "gate_status": "skip_fallback", "source": "original_100pct",
        "rule_applied": None, "fix_status": "p1_rewritten"
    },
    # 4. sanctuary
    {
        "word": "sanctuary", "pos": "noun", "cefr": "C2",
        "def_before": "a holy building or the part of it that is considered the most holy",
        "gloss_after": "holy place",
        "gate_status": "skip_fallback", "source": "original_100pct",
        "rule_applied": None, "fix_status": "p1_rewritten"
    },
    # 5. diplomatic
    {
        "word": "diplomatic", "pos": "adjective", "cefr": "C1",
        "def_before": "connected with managing relations between countries (= diplomacy)|having or showing skill in dealing with people in difficult situations",
        "gloss_after": "political|tactful",
        "gate_status": "pass", "source": "rerun_v2_streamA",
        "rule_applied": "2sense_distinct", "fix_status": "rebuilt"
    }
]


def matches_guard(row: dict, guard: dict) -> bool:
    for k, v in guard.items():
        if row.get(k) != v:
            return False
    return True


def should_delete_row(row: dict) -> bool:
    """Returns True if the row matches one of the 5 targeted duplicate loser rows."""
    return any(matches_guard(row, guard) for guard in LOSER_GUARDS)


def process_rows(rows: list[dict]) -> list[dict]:
    """Filter out the 5 duplicate loser rows. Raises ValueError if exact count is not 5."""
    new_rows = []
    deleted_count = 0
    
    # We want to match exactly one of each guard to ensure all 5 unique guards matched
    matched_guards = [False] * len(LOSER_GUARDS)
    
    for r in rows:
        matched_any = False
        for idx, guard in enumerate(LOSER_GUARDS):
            if matches_guard(r, guard):
                if matched_guards[idx]:
                    # Already matched this specific guard; treat as duplicate keeper or general duplicate
                    # But actually we expect exactly one match per guard
                    pass
                else:
                    matched_guards[idx] = True
                    matched_any = True
                    deleted_count += 1
                    break
        if not matched_any:
            new_rows.append(r)

    if deleted_count != 5 or not all(matched_guards):
        raise ValueError(
            f"Did not find exactly 5 duplicate loser rows matching the specified guards. "
            f"Deleted count: {deleted_count}, Matched guards: {matched_guards}"
        )
        
    return new_rows


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def main() -> int:
    ap = argparse.ArgumentParser(description='Apply P2 card identity dedup.')
    ap.add_argument('--apply', action='store_true', help='Actually write changes.')
    args = ap.parse_args()

    print("=" * 72)
    print(f"P2 Card Identity Dedup (apply={args.apply})")
    print(f"Timestamp: {_ts()}")
    print("=" * 72)

    # 1. Load rows
    print(f"Loading {MASTER_AUDIT.name}...")
    rows = []
    with MASTER_AUDIT.open(encoding='utf-8') as fp:
        for line in fp:
            if line.strip():
                rows.append(json.loads(line))
    
    original_count = len(rows)
    print(f"Original row count: {original_count}")

    # 2. Process rows
    try:
        new_rows = process_rows(rows)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    new_count = len(new_rows)
    print(f"New row count: {new_count} (deleted {original_count - new_count} rows)")
    
    # Assert row count decreases by exactly 5
    assert original_count - new_count == 5, f"Unexpected deletion count: {original_count - new_count}"

    # 3. Write changes if --apply
    if args.apply:
        # Create backup
        bak = MASTER_AUDIT.with_suffix(MASTER_AUDIT.suffix + f'.bak_pre_card_identity_p2_{_ts()}')
        bak.write_bytes(MASTER_AUDIT.read_bytes())
        print(f"Created backup: {bak.name}")

        # Replace file contents
        tmp = MASTER_AUDIT.with_suffix(MASTER_AUDIT.suffix + '.tmp_p2')
        with tmp.open('w', encoding='utf-8', newline='') as fp:
            for r in new_rows:
                fp.write(json.dumps(r, ensure_ascii=False))
                fp.write('\n')
        tmp.replace(MASTER_AUDIT)
        print("Deduplicated audit rows written successfully.")
    else:
        print("Dry run completed. Run with --apply to write changes.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
