#!/usr/bin/env python3
"""Check sync between design/index.html (vùng 2 CSS) and design/EAVM/styling.txt.

Drift check rules:
- Extracts Region 2 from design/index.html (between the boundary markers).
- Reads design/EAVM/styling.txt.
- Skips rules marked with /* @preview-only */ on both sides.
- Removes all other comments.
- Compares normalized CSS properties.
- Exits 0 if in sync, 1 if drift detected.
"""
from __future__ import annotations
import difflib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = PROJECT_ROOT / "design" / "index.html"
STYLING_TXT = PROJECT_ROOT / "design" / "EAVM" / "styling.txt"

START_MARKER = "/* ANKI CARD STYLES — must match EAVM/styling.txt exactly */"
END_MARKER = "/* END ANKI CARD STYLES */"

def remove_preview_only_rules(css: str) -> str:
    """Scan CSS line-by-line and discard blocks preceded by /* @preview-only."""
    lines = css.splitlines()
    output_lines = []
    skip_next_rule = False
    brace_depth = 0
    
    for line in lines:
        stripped = line.strip()
        
        # Detect preview-only comment
        if stripped.startswith("/*") and "@preview-only" in stripped:
            skip_next_rule = True
            continue
            
        opening_braces = line.count("{")
        closing_braces = line.count("}")
        
        if skip_next_rule:
            brace_depth += opening_braces - closing_braces
            if brace_depth <= 0 and "}" in line:
                skip_next_rule = False
                brace_depth = 0
            continue
            
        output_lines.append(line)
        
    return "\n".join(output_lines)

def normalize_css(css: str) -> str:
    """Remove preview-only rules, comments, and normalize whitespaces."""
    # 1. Remove preview-only rules
    css_no_preview = remove_preview_only_rules(css)
    # 2. Strip comments
    css_no_comments = re.sub(r'/\*.*?\*/', '', css_no_preview, flags=re.DOTALL)
    # 3. Clean up whitespaces & empty lines
    lines = []
    for line in css_no_comments.splitlines():
        line = line.strip()
        if line:
            line = re.sub(r'\s+', ' ', line)
            lines.append(line)
    return "\n".join(lines)

def extract_region2(html_content: str) -> str:
    """Extract CSS from index.html between boundary comments."""
    if START_MARKER not in html_content:
        raise ValueError(f"Start marker not found in index.html: {START_MARKER}")
    if END_MARKER not in html_content:
        raise ValueError(f"End marker not found in index.html: {END_MARKER}")
        
    parts = html_content.split(START_MARKER, 1)
    sub_parts = parts[1].split(END_MARKER, 1)
    return sub_parts[0]

def main() -> int:
    if not INDEX_HTML.exists():
        print(f"Error: index.html not found at {INDEX_HTML}", file=sys.stderr)
        return 1
    if not STYLING_TXT.exists():
        print(f"Error: styling.txt not found at {STYLING_TXT}", file=sys.stderr)
        return 1

    html_content = INDEX_HTML.read_text(encoding="utf-8")
    try:
        region2_raw = extract_region2(html_content)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    styling_raw = STYLING_TXT.read_text(encoding="utf-8")

    region2_norm = normalize_css(region2_raw)
    styling_norm = normalize_css(styling_raw)

    if region2_norm == styling_norm:
        print("[OK] design/index.html (vùng 2) and design/EAVM/styling.txt are in sync.")
        return 0

    print("Error: Design drift detected between index.html and styling.txt!", file=sys.stderr)
    print("Diff (index.html vs styling.txt):", file=sys.stderr)
    
    diff = difflib.unified_diff(
        region2_norm.splitlines(),
        styling_norm.splitlines(),
        fromfile="index.html (vùng 2)",
        tofile="styling.txt",
        lineterm=""
    )
    for line in diff:
        print(line, file=sys.stderr)
        
    return 1

if __name__ == "__main__":
    sys.exit(main())
