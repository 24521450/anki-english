#!/usr/bin/env python3
"""Check the canonical Card CSS Region against production styling.txt."""
from __future__ import annotations

import difflib
import sys
from pathlib import Path

from src.design_css import (
    END_MARKER,
    START_MARKER,
    design_css_in_sync,
    extract_card_css as extract_region2,
    normalize_css,
    remove_preview_only_rules,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = PROJECT_ROOT / "design" / "index.html"
STYLING_TXT = PROJECT_ROOT / "design" / "EAVM" / "styling.txt"


def main() -> int:
    if not INDEX_HTML.exists():
        print(f"Error: index.html not found at {INDEX_HTML}", file=sys.stderr)
        return 1
    if not STYLING_TXT.exists():
        print(f"Error: styling.txt not found at {STYLING_TXT}", file=sys.stderr)
        return 1

    try:
        region2_raw = extract_region2(INDEX_HTML.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    styling_raw = STYLING_TXT.read_text(encoding="utf-8")
    region2_norm = normalize_css(region2_raw)
    styling_norm = normalize_css(styling_raw)
    if design_css_in_sync(INDEX_HTML, STYLING_TXT):
        print("[OK] design/index.html (vùng 2) and design/EAVM/styling.txt are in sync.")
        return 0

    print("Error: Design drift detected between index.html and styling.txt!", file=sys.stderr)
    print("Diff (index.html vs styling.txt):", file=sys.stderr)
    for line in difflib.unified_diff(
        region2_norm.splitlines(),
        styling_norm.splitlines(),
        fromfile="index.html (vùng 2)",
        tofile="styling.txt",
        lineterm="",
    ):
        print(line, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
