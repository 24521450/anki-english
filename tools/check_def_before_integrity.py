"""Integrity check adapter for def_before rows in deck_audit.jsonl."""
from __future__ import annotations

import json
import sys
from src.config import ProjectPaths
from src.deck_builder.def_before_integrity import (
    DefBeforeIntegrityPaths,
    check_def_before_integrity
)

EXPECTED_AUDIT_ROWS = 2459

def main() -> int:
    paths = ProjectPaths()
    diag_paths = DefBeforeIntegrityPaths(
        deck_audit_jsonl=paths.deck_audit_jsonl,
        oxford_jsonl=paths.oxford_jsonl,
        manual_card_fills=paths.manual_card_fills,
        anki_notes_txt=paths.anki_notes_txt,
        oxford_5000_md=paths.oxford_5000_md,
    )

    try:
        report = check_def_before_integrity(diag_paths)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Print results
    print("=== Integrity Check Classification Stats ===")
    for k, v in report.stats.items():
        print(f"  {k:22s}: {v}")

    # Verify total sum of all stats is exactly EXPECTED_AUDIT_ROWS
    total_classified = sum(report.stats.values())
    print(f"  Total Rows Read:       {report.total_rows_read}")
    print(f"  Total Rows Classified: {total_classified}")

    count_mismatch = (
        total_classified != report.total_rows_read
        or report.total_rows_read != EXPECTED_AUDIT_ROWS
    )
    if report.has_errors() or count_mismatch:
        if report.orphan_rows:
            print(f"\nError: Found {len(report.orphan_rows)} orphan rows in deck_audit.jsonl:", file=sys.stderr)
            for line_no, r in report.orphan_rows[:10]:
                print(f"  Line {line_no}: {r['word']} | {r['pos']} | {r['cefr']}", file=sys.stderr)
        if report.unmatched_rows:
            print(f"\nError: Found {len(report.unmatched_rows)} unmatched rows in deck_audit.jsonl:", file=sys.stderr)
            for line_no, r in report.unmatched_rows[:10]:
                print(f"  Line {line_no}: {r['word']} | {r['pos']} | {r['cefr']} | def: {r['def_before']}", file=sys.stderr)
        if report.ambiguous_rows:
            print(f"\nError: Found {len(report.ambiguous_rows)} ambiguous rows in deck_audit.jsonl:", file=sys.stderr)
            for line_no, r in report.ambiguous_rows[:10]:
                print(f"  Line {line_no}: {r['word']} | {r['pos']} | {r['cefr']}", file=sys.stderr)
        if count_mismatch:
            print(
                f"\nError: expected {EXPECTED_AUDIT_ROWS} audit rows and complete "
                f"classification, read={report.total_rows_read}, "
                f"classified={total_classified}",
                file=sys.stderr,
            )
        print("\nIntegrity check FAILED.", file=sys.stderr)
        return 1

    print("\nIntegrity check PASSED.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
