"""Cambridge HTML parser → schema v2 record.

Locked to lxml + cssselect + text_content() per ADR-0001.

Schema v2: see `tests/fixtures/golden_cambridge_v2.json` (5 records, generated 2026-06-10).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from lxml import html as lxml_html

from ._selectors import CAMBRIDGE

# -----------------------------------------------------------------------------
# Helpers (mirror of oxford.py)
# -----------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return _WHITESPACE_RE.sub(" ", s).strip()


def _text_of(el) -> str:
    if el is None:
        return ""
    return _normalize_text(el.text_content()) or ""


def _first(root, sel: str):
    matches = root.cssselect(sel)
    return matches[0] if matches else None


def _dedup_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(p for p in items if p))


# -----------------------------------------------------------------------------
# Per-field extractors
# -----------------------------------------------------------------------------

def _extract_headword(root) -> Optional[str]:
    el = _first(root, CAMBRIDGE["headword"])
    return _text_of(el) or None


def _extract_pos(root) -> list[str]:
    raw = [_text_of(p) for p in root.cssselect(CAMBRIDGE["pos"])]
    return _dedup_preserve_order(raw)


def _extract_ipa(root) -> Optional[str]:
    el = _first(root, CAMBRIDGE["ipa"])
    return _text_of(el) or None


def _extract_ipa_uk(root) -> Optional[str]:
    """UK IPA = first .dipa inside an ancestor with class 'uk' (region marker).

    Cambridge wraps each pronunciation block in <span class="uk dpron-i"> for
    UK and <span class="us dpron-i"> for US. The IPA text is inside
    <span class="ipa dipa">. We pick the FIRST .dipa whose ancestor carries the
    'uk' class — i.e. the headword's UK IPA, not later variants (e.g. suffixes).
    """
    for dipa in root.cssselect(".dipa"):
        p = dipa.getparent()
        for _ in range(20):
            if p is None:
                break
            cls = (p.get("class") or "").split()
            if "uk" in cls:
                return _text_of(dipa) or None
            p = p.getparent()
    return None


def _extract_ipa_us(root) -> Optional[str]:
    """US IPA = first .dipa inside an ancestor with class 'us' (region marker).

    Mirrors _extract_ipa_uk for the US accent. Returns the headword's US IPA
    (first match) to keep parity with Oxford's behavior.
    """
    for dipa in root.cssselect(".dipa"):
        p = dipa.getparent()
        for _ in range(20):
            if p is None:
                break
            cls = (p.get("class") or "").split()
            if "us" in cls:
                return _text_of(dipa) or None
            p = p.getparent()
    return None


def _extract_audio_paths(root) -> dict[str, Optional[str]]:
    """Cambridge audio: <audio><source src="/media/english/{uk,us}_pron/...">.

    The <audio> tag has class="hdn" (hidden), and inside is <source type="audio/mpeg"
    src="..."> with the actual URL. We pick UK and US based on path component.
    """
    out = {"uk": None, "us": None}
    # UK = source with uk_pron in src; US = source with us_pron in src
    uk = _first(root, CAMBRIDGE["audio_uk"])
    us = _first(root, CAMBRIDGE["audio_us"])
    if uk is not None:
        out["uk"] = uk.get("src")
    if us is not None:
        out["us"] = us.get("src")
    return out


def _extract_oxford_lists(root) -> list[str]:
    """Cambridge does not tag Oxford 3000/5000. Empty."""
    return []


def _extract_awl(root) -> Optional[str]:
    """Cambridge does not tag AWL. Empty."""
    return None


def _extract_register_top(root) -> list[str]:
    """Cambridge .usage is per-sense. Top-level: look for .reg or .labels near .headword."""
    # No top-level register in Cambridge pages — set empty.
    return []


def _extract_see_also(root) -> list[str]:
    """See also via .xref cross-reference blocks.

    Cambridge pages have multiple .xref blocks (synonyms, opposites, related_word,
    see_also, compare, grammar, idioms, phrasal_verbs, etc.). Only the semantic
    cross-reference blocks should be included in see_also — not grammar/idiom/
    phrasal-verb pattern blocks.

    Within each included block, extract <span class="x-h dx-h"> elements which
    wrap real headword anchors. Skip register labels (.x-lab, .region, .usage)
    and the section header (<strong class="xref-title">).
    """
    # xref types to EXCLUDE — these are not see-also, they are grammar/idiom patterns
    EXCLUDE_TYPES = {"grammar", "idiom", "idioms", "phrasal_verb", "phrasal_verbs"}

    seen = []
    for xref in root.cssselect(CAMBRIDGE["xref"]):
        cls = (xref.get("class") or "").split()
        # class list is like: ['xref', 'synonyms', 'hax', 'dxref-w', 'lmt-25']
        # Index 1 is the type
        xref_type = cls[1] if len(cls) > 1 else ""
        if xref_type in EXCLUDE_TYPES:
            continue
        # Extract real headwords from <span class="x-h dx-h">
        for hw in xref.cssselect(".x-h.dx-h"):
            w = _text_of(hw).strip()
            if w and w.isalpha() and len(w) <= 25:
                seen.append(w)
    return _dedup_preserve_order(seen)


# Per-sense extractors ----------------------------------------------------

def _extract_def_text(sense_el) -> Optional[str]:
    el = _first(sense_el, CAMBRIDGE["def"])
    return _text_of(el) or None


def _extract_cefr(sense_el) -> Optional[str]:
    """Cambridge cefr from .epp-xref (uppercase A1/B2/C1 etc.)."""
    el = _first(sense_el, CAMBRIDGE["cefr"])
    return _text_of(el).upper() or None


def _extract_register_def(sense_el) -> list[str]:
    """Per-sense register: .usage inside .dsense_b."""
    raw = [_text_of(r) for r in sense_el.cssselect(CAMBRIDGE["register"])]
    return _dedup_preserve_order(raw)


def _extract_grammar(sense_el) -> Optional[str]:
    el = _first(sense_el, CAMBRIDGE["grammar"])
    return _text_of(el) or None


def _extract_examples(sense_el) -> list[dict[str, Optional[str]]]:
    """Cambridge .dexamp — extract only the <span class="eg deg"> (example sentence).

    A .dexamp block often contains BOTH a collocation phrase (<span class="lu dlu">)
    AND an example sentence (<span class="eg deg">). Bare collocations (only
    .lu, no .eg) are NOT examples — they belong in the collocations dict.

    Returns one entry per .dexamp that has an .eg child, with text from .eg only.
    cf is always None for Cambridge.
    """
    out = []
    for ex in sense_el.cssselect(CAMBRIDGE["examples"]):
        # Only consider .dexamp that has an .eg child
        eg = _first(ex, ".eg.deg")
        if eg is None:
            continue
        text = _text_of(eg)
        if text:
            out.append({"text": text, "cf": None})
    return out


def _extract_topics(sense_el) -> list[dict[str, str]]:
    """Cambridge does not expose structured topic tags (per CONTEXT.md)."""
    return []


def _extract_collocations(sense_el) -> dict[str, list[str]]:
    """Cambridge collocations from two sources:

    1. <span class="lu dlu"> inside <span class="dexamp"> — collocation phrases
       attached to example sentences (e.g. "flagrant violation" before the sentence
       "The takeover constitutes a flagrant violation of...").
    2. <span class="cl"> — grammar frame patterns (e.g. "traffic/probation/safety
       violation", "violation of"). These are sometimes called "phrase patterns"
       in Cambridge, but are stored alongside regular collocations.

    Both sources are merged into a single "collocations" bucket (flat list).
    Schema mirrors Oxford's `definitions[].collocations` shape but with one bucket
    instead of category-keyed buckets.
    """
    collocs: list[str] = []
    seen: set[str] = set()

    # 1. <span class="lu dlu"> from <span class="dexamp">
    for ex in sense_el.cssselect(".dexamp"):
        for lu in ex.cssselect(".lu.dlu"):
            t = _text_of(lu).strip()
            if t and t not in seen:
                seen.add(t)
                collocs.append(t)

    # 2. <span class="cl"> (grammar frame patterns)
    for cl in sense_el.cssselect(".cl"):
        t = _text_of(cl).strip()
        if t and t not in seen:
            seen.add(t)
            collocs.append(t)

    return {"collocations": collocs}


def _is_idiom(sense_el) -> bool:
    """Cambridge idiom detection: walk parent chain for .idiom-body or .phrase-di-body."""
    p = sense_el.getparent()
    for _ in range(20):
        if p is None:
            return False
        cls = (p.get("class") or "").split()
        if "idiom-body" in cls or "phrase-di-body" in cls:
            return True
        p = p.getparent()
    return False


# -----------------------------------------------------------------------------
# Main parser
# -----------------------------------------------------------------------------

def parse_cambridge(html_bytes: bytes, source_files: Optional[list[str]] = None) -> dict[str, Any]:
    """Parse a Cambridge HTML page into schema v2 record."""
    root = lxml_html.fromstring(html_bytes)

    word = _extract_headword(root)
    pos = _extract_pos(root)
    ipa = _extract_ipa(root)
    uk_ipa = _extract_ipa_uk(root)
    us_ipa = _extract_ipa_us(root)
    audio = _extract_audio_paths(root)
    lists = _extract_oxford_lists(root)
    awl = _extract_awl(root)
    register_top = _extract_register_top(root)
    see_also = _extract_see_also(root)

    pos_data: list[dict] = []
    for pos_label in pos:
        definitions: list[dict] = []
        for n, sense_el in enumerate(root.cssselect(CAMBRIDGE["sense"]), start=1):
            # Cambridge does not expose sensenum attribute
            definitions.append({
                "n": n,
                "sensenum_local": None,  # Cambridge doesn't have this attribute
                "text": _extract_def_text(sense_el),
                "register_tags": _extract_register_def(sense_el),
                "cefr": _extract_cefr(sense_el),
                "topics": _extract_topics(sense_el),
                "collocations": _extract_collocations(sense_el),
                "examples": _extract_examples(sense_el),
                "is_phrase": False,
                "is_idiom": _is_idiom(sense_el),
            })
        pos_data.append({
            "pos": pos_label,
            "register_tags": [],
            "definitions": definitions,
        })

    # Cambridge has no idiom-phrase block separate from senses
    idioms: list[dict] = []

    return {
        # $schema field removed in v3: placeholder URL (https://ielts-deck.local/...)
        # was non-resolvable, so no editor/tooling actually consumed it. The
        # data/schema/cambridge_record.schema.json file is the real contract.
        "word": word,
        "homonym_index": None,  # Cambridge does not model homonyms in v2
        "source": "cambridge",
        "source_url": None,
        "source_files": source_files or [],
        "pos": pos,
        "register_tags": register_top,
        "oxford_lists": lists,
        "opal": None,  # Cambridge does not have OPAL
        "awl": awl,
        "uk_ipa": uk_ipa,
        "us_ipa": us_ipa,
        "audio": audio,
        "see_also": see_also,
        "pos_data": pos_data,
        "verb_forms": None,  # Cambridge has no verb_forms section
        "idioms": idioms,
    }
