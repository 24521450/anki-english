"""Pytest version of design sync check.

Runs the same logic as tools/check_design_sync.py to ensure CI/pytest
catches any drift between design/index.html and design/EAVM/styling.txt.
"""
from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.check_design_sync import (
    INDEX_HTML,
    STYLING_TXT,
    extract_region2,
    normalize_css,
)

def test_design_is_in_sync():
    """Assert design/index.html (vùng 2 CSS) and design/EAVM/styling.txt are in sync."""
    assert INDEX_HTML.exists(), f"index.html not found at {INDEX_HTML}"
    assert STYLING_TXT.exists(), f"styling.txt not found at {STYLING_TXT}"

    html_content = INDEX_HTML.read_text(encoding="utf-8")
    region2_raw = extract_region2(html_content)
    styling_raw = STYLING_TXT.read_text(encoding="utf-8")

    region2_norm = normalize_css(region2_raw)
    styling_norm = normalize_css(styling_raw)

    assert region2_norm == styling_norm, (
        "Design drift detected between design/index.html (vùng 2) and design/EAVM/styling.txt! "
        "Run 'python -m tools.check_design_sync' to see the detailed diff."
    )
