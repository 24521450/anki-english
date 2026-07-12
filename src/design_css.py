"""Derive production Anki CSS from the canonical design source."""
from __future__ import annotations

import re
from pathlib import Path


START_MARKER = "/* ANKI CARD STYLES — must match EAVM/styling.txt exactly */"
END_MARKER = "/* END ANKI CARD STYLES */"


def remove_preview_only_rules(css: str) -> str:
    """Discard each CSS rule immediately preceded by ``@preview-only``."""
    output: list[str] = []
    skipping = False
    brace_depth = 0

    for line in css.splitlines():
        stripped = line.strip()
        if not skipping and stripped.startswith("/*") and "@preview-only" in stripped:
            skipping = True
            brace_depth = 0
            continue

        if skipping:
            brace_depth += line.count("{") - line.count("}")
            if "}" in line and brace_depth <= 0:
                skipping = False
                brace_depth = 0
            continue

        output.append(line)

    return "\n".join(output)


def derive_production_css(css: str) -> str:
    """Return CSS safe to bake into the EAVM Note Type."""
    derived = remove_preview_only_rules(css).strip()
    return derived + "\n" if derived else ""


def load_production_css(path: Path) -> str:
    return derive_production_css(path.read_text(encoding="utf-8"))


def normalize_css(css: str) -> str:
    """Normalize derived CSS for source-of-truth comparisons."""
    production = derive_production_css(css)
    without_comments = re.sub(r"/\*.*?\*/", "", production, flags=re.DOTALL)
    lines = []
    for line in without_comments.splitlines():
        normalized = re.sub(r"\s+", " ", line.strip())
        if normalized:
            lines.append(normalized)
    return "\n".join(lines)


def extract_card_css(html_content: str) -> str:
    """Extract the canonical Card CSS Region from ``design/index.html``."""
    if START_MARKER not in html_content:
        raise ValueError(f"Start marker not found in index.html: {START_MARKER}")
    if END_MARKER not in html_content:
        raise ValueError(f"End marker not found in index.html: {END_MARKER}")
    return html_content.split(START_MARKER, 1)[1].split(END_MARKER, 1)[0]


def design_css_in_sync(index_path: Path, styling_path: Path) -> bool:
    region = extract_card_css(index_path.read_text(encoding="utf-8"))
    styling = styling_path.read_text(encoding="utf-8")
    return normalize_css(region) == normalize_css(styling)
