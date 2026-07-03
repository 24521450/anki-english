"""Core label extraction module for Oxford dictionary HTML senses.

Provides canonical register and subject label taxonomies and extraction helpers.
"""
from __future__ import annotations

import re

# 12 Register Labels (from data/oxford_labels.json -> register_labels)
REGISTER_LABELS: frozenset[str] = frozenset({
    "approving",
    "disapproving",
    "figurative",
    "formal",
    "humorous",
    "informal",
    "ironic",
    "literary",
    "offensive",
    "slang",
    "specialist",
    "taboo",
})

# 23 Subject Labels (from data/oxford_labels.json -> subject_labels)
SUBJECT_LABELS: frozenset[str] = frozenset({
    "anatomy",
    "biochemistry",
    "biology",
    "business",
    "chemistry",
    "computing",
    "earth science",
    "ecology",
    "economics",
    "engineering",
    "finance",
    "geometry",
    "grammar",
    "law",
    "linguistics",
    "mathematics",
    "medical",
    "philosophy",
    "phonetics",
    "physics",
    "politics",
    "psychology",
    "statistics",
})

_LABEL_SPLIT_RE = re.compile(r"\s*,\s*")
_PAREN_STRIP_RE = re.compile(r"^\(|\)$")


def parse_label_compound(label_text: str) -> dict[str, list[str] | str | None]:
    """Parse a span.labels text value into structured register_tags and domain.

    Strategy:
      1. Strip outer parens
      2. Split on ',' (compound handling)
      3. For each part: strip whitespace, lowercase
      4. Classify:
         - if part ∈ REGISTER_LABELS -> add to register_tags (preserve order, dedup)
         - if part ∈ SUBJECT_LABELS -> set domain (first match wins, single value)
         - else -> drop (regional variants, grammar notes, usage restrictions)

    Returns:
        {"register_tags": list[str], "domain": str | None}
    """
    out: dict[str, list[str] | str | None] = {"register_tags": [], "domain": None}
    if not label_text:
        return out
    text = label_text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    if not text:
        return out

    parts = _LABEL_SPLIT_RE.split(text)
    reg_tags: list[str] = []
    dom: str | None = None

    for part in parts:
        p = part.strip().lower()
        if not p:
            continue
        if p in REGISTER_LABELS and p not in reg_tags:
            reg_tags.append(p)
        if p in SUBJECT_LABELS and dom is None:
            dom = p

    out["register_tags"] = reg_tags
    out["domain"] = dom
    return out


def extract_labels_for_sense(sense_el) -> dict[str, list[str] | str | None]:
    """Extract register_tags and domain from a li.sense element."""
    out: dict[str, list[str] | str | None] = {"register_tags": [], "domain": None}
    for lbl_el in sense_el.cssselect("span.labels"):
        # Skip labels inside collapsible note boxes (e.g. div.collapse, span.unbox)
        is_in_box = False
        for anc in lbl_el.iterancestors():
            if anc == sense_el:
                break
            cls = anc.get("class") or ""
            if "collapse" in cls or "unbox" in cls:
                is_in_box = True
                break
        if is_in_box:
            continue

        text = (lbl_el.text_content() or "").strip()
        if text:
            parsed = parse_label_compound(text)
            for r in parsed["register_tags"]:
                if r not in out["register_tags"]:
                    out["register_tags"].append(r)
            if out["domain"] is None and parsed["domain"]:
                out["domain"] = parsed["domain"]
    return out
