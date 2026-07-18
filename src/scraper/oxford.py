"""Oxford HTML parser → schema v2 record.

Locked to lxml + cssselect + text_content() per ADR-0001.

Schema v2: see `tests/fixtures/golden_oxford_v2.json` (5 records, generated 2026-06-10).
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit
from typing import Any, Optional

from lxml import html as lxml_html

from ._selectors import OXFORD
from src.scraper.oxford_labels import extract_labels_for_sense

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")

# Bug 2 fix (2026-06-13): Oxford Collocations Dictionary UI truncates long
# lists with these indicators. They are NOT real collocation items — they
# mean "more items available, click to expand". Filter them out before
# returning from `_extract_collocations()`.
COLLOC_ARTIFACTS = frozenset({"…", "..."})


def _normalize_text(s: Optional[str]) -> Optional[str]:
    """Collapse all whitespace runs to a single space, strip ends. None stays None."""
    if s is None:
        return None
    return _WHITESPACE_RE.sub(" ", s).strip()


def _text_of(el) -> str:
    """lxml text extraction via text_content(); collapse whitespace; never None."""
    if el is None:
        return ""
    return _normalize_text(el.text_content()) or ""


def _first(root, sel: str):
    """lxml has no select_one; return first match or None."""
    matches = root.cssselect(sel)
    return matches[0] if matches else None


def _dedup_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(p for p in items if p))


def _polymorphic_form(filename: str) -> str:
    """Classify an Oxford cache file by its polymorphic form (per CONTEXT.md term)."""
    base = filename.removesuffix(".html")
    if "_(" in base:
        head = base.split("_(")[0]
        if head.rsplit("_", 1)[-1].isdigit():
            return "indexed_pos"
        return "pos_suffix"
    return "main_page"


# -----------------------------------------------------------------------------
# Per-field extractors
# -----------------------------------------------------------------------------

def _extract_headword(root) -> Optional[str]:
    el = _first(root, OXFORD["headword"])
    return _normalize_text(el.text_content()) if el is not None else None


def _extract_homonym_index(root) -> Optional[int]:
    """Extract Oxford homonym index from h1.headword trailing digit.

    Oxford encodes homonyms as a trailing digit in the headword text
    (e.g. 'bass1' = bass the fish, 'bass2' = bass the music note).
    The digit is part of the page's headword span, NOT a separate
    span.homnum class. Examples: 'bass1', 'bass2', 'bow1', 'bow2'.

    Returns:
        1, 2, 3, ... for homonym pages; None for regular words.

    Notes:
        - The headword text is e.g. 'bass1' (no space between base + digit).
        - We strip the digit from the word field at the call site, and
          surface the index here as a separate field.
    """
    el = _first(root, OXFORD["headword"])
    if el is None:
        return None
    text = (el.text_content() or "").strip()
    m = re.search(r"(\d+)$", text)
    if m:
        return int(m.group(1))
    return None


def _extract_pos(root) -> list[str]:
    """POS labels — top-level only (skip related-entries' pos-g)."""
    raw = [_text_of(p) for p in root.cssselect(OXFORD["pos"])]
    # Strip empty <pos/> (related entries with no POS)
    return _dedup_preserve_order(p for p in raw if p)


def _extract_ipa_uk(root) -> Optional[str]:
    """UK IPA = first .phon inside .phons_br (British parent) at top level.

    Returns the FIRST .phon under .phons_br, which is the headword's UK IPA
    (not the comparative/superlative inflection forms, which appear as
    additional .phons_br blocks further down the page — e.g. 'abler', 'ablest'
    on the 'able' page).
    """
    el = _first(root, ".phons_br .phon")
    return _text_of(el) or None


def _extract_ipa_us(root) -> Optional[str]:
    """US IPA = first .phon inside .phons_n_am (North-American parent).

    Mirrors _extract_ipa_uk: returns the FIRST .phon under .phons_n_am (the
    headword's US IPA, not inflections).
    """
    el = _first(root, ".phons_n_am .phon")
    return _text_of(el) or None


def _extract_audio_paths(root) -> dict[str, Optional[str]]:
    """Audio MP3 URLs for UK and US accents (from .sound.audio_play_button data-src-mp3)."""
    out = {"uk": None, "us": None}
    buttons = root.cssselect(".sound.audio_play_button")
    for b in buttons:
        mp3 = b.get("data-src-mp3")
        if not mp3:
            continue
        # Geo-coded: BR -> uk, N_AM -> us (Oxford convention)
        if "uk_pron" in mp3 and out["uk"] is None:
            out["uk"] = mp3
        elif "us_pron" in mp3 and out["us"] is None:
            out["us"] = mp3
    return out


def _extract_oxford_lists(root) -> list[str]:
    """Oxford 3000/5000 list membership.

    Two signal sources, both consulted (union):
      1. **Page-top badge** — `<div class="symbols">` containing
         `<span class="ox3ksym_*">` (Oxford 3000) or `<span class="ox5ksym_*">`
         (Oxford 5000). This is the canonical signal on modern Oxford pages.
         Same selector used by `_extract_oxford_badge`.
      2. **Legacy sense attribute** — `<li class="sense" ox3000="y" ox5000="y">`.
         Older scrapes put the list flag on the sense; kept for backward compat.
    """
    lists: set[str] = set()
    # 1. Modern selector: page-top .ox3ksym_* / .ox5ksym_* spans (subclass of CEFR level).
    # Use substring match with trailing underscore to avoid matching e.g. "ox3ksymfoo".
    if root.cssselect('[class*="ox3ksym_"]'):
        lists.add("Oxford 3000")
    if root.cssselect('[class*="ox5ksym_"]'):
        lists.add("Oxford 5000")
    # 2. Legacy sense[ox3000/ox5000] attribute
    for sense in root.cssselect(OXFORD["sense"]):
        if sense.get("ox3000") == "y":
            lists.add("Oxford 3000")
        if sense.get("ox5000") == "y":
            lists.add("Oxford 5000")
    return sorted(lists)


def _extract_oxford_badge(root) -> Optional[str]:
    """Word-level CEFR badge from Oxford 3000/5000 top-of-page span.

    Layout: <span class="ox3ksym_c1"> (Oxford 3000) or <span class="ox5ksym_c1">
    (Oxford 5000). Class name embeds the CEFR level (a1/a2/b1/b2/c1/c2).

    Distinct from per-sense def.cefr: this is Oxford's tier endorsement for the
    whole word, not a per-sense classification.
    """
    import re as _re
    badge_re = _re.compile(r"ox[35]ksym_([abc][12])", _re.IGNORECASE)
    for el in root.cssselect(OXFORD["oxford_badge"]):
        cls = el.get("class", "")
        m = badge_re.search(cls)
        if m:
            return m.group(1).upper()
    return None


def _extract_opal(root) -> Optional[str]:
    """OPAL word list — look for OPAL_spoken / OPAL_written indicators.

    Implementation: look for symbols divs with class containing "OPAL".
    """
    # Check for ox3ksym (Oxford 3000/5000/OPAL symbol containers)
    # OPAL is rare; only present for words on the OPAL list.
    # We don't have a dedicated selector — set null and flag.
    return None


def _extract_awl(root) -> Optional[str]:
    """AWL (Academic Word List) membership. Oxford doesn't expose this directly;
    we need to cross-reference with vocab_list/AWL/AWL.json. Set null at parse time.
    """
    return None


def _extract_register_tags_top(root) -> list[str]:
    """Top-level register tags (word-level, near pos). Selector .reg was unverified."""
    raw = [_text_of(r) for r in root.cssselect(OXFORD["register_top"])]
    return _dedup_preserve_order(raw)


def _extract_see_also(root) -> list[str]:
    """SEE ALSO section — extract related word headwords.

    Oxford pattern: <span class='xrefs' hclass='xrefs'>
        <span class='prefix'>see also</span>
        <a class='Ref'><span class='xr-g'><span class="xh">word</span></span></a>
        <span class="sep">,</span>
        <a class='Ref'>...</a>
    </span>

    IMPORTANT: only look inside <span class='xrefs'> blocks (NOT <span class='xtoc'> which
    is the table-of-contents / jump links; NOT <span class='dictlink-g'> which is the
    "See [word] in the [Other Dictionary]" cross-dictionary link).

    The headword text is in the innermost <span class="xh">.
    """
    out: list[str] = []
    for xrefs in root.cssselect(".xrefs"):
        # Confirm this is a "see also" block, not "compare" or other
        prefix_el = _first(xrefs, ".prefix")
        if prefix_el is None or "see also" not in _text_of(prefix_el).lower():
            continue
        # Extract each linked headword from <span class="xh">
        for xh in xrefs.cssselect(".xh"):
            word = _text_of(xh)
            if word:
                out.append(word)
    return _dedup_preserve_order(out)


# Per-sense extractors ----------------------------------------------------

def _extract_synonyms(sense_el) -> list[str]:
    """Extract sense-level synonyms from span.xrefs[xt='syn' or xt='nsyn'] span.xh.

    Oxford uses two relation codes for synonyms:
      - xt="syn": standard synonym blocks
      - xt="nsyn": note/new synonym blocks (e.g. vicious -> brutal)

    Iterates relation blocks in DOM order, accepting both 'syn' and 'nsyn',
    extracts headwords from .xh spans, and deduplicates preserving first occurrence order.
    """
    out: list[str] = []
    for xrefs in sense_el.cssselect("span[xt='syn'], span[xt='nsyn']"):
        cls = xrefs.get("class") or ""
        hcls = xrefs.get("hclass") or ""
        if "xrefs" not in cls.split() and hcls != "xrefs":
            continue
        for xh in xrefs.cssselect("span"):
            x_cls = xh.get("class") or ""
            x_hcls = xh.get("hclass") or ""
            if "xh" in x_cls.split() or x_hcls == "xh":
                txt = (xh.text or "").strip()
                if txt:
                    out.append(txt)
    return _dedup_preserve_order(out)


def _extract_antonyms(sense_el) -> list[str]:
    """Extract sense-level antonyms from span.xrefs[xt='opp'] span.xh.

    Mirrors `_extract_synonyms` — same xh-class filter, same dedup, but reads
    `xt="opp"` blocks only. Oxford's opposite blocks look like:
        <span class="xrefs" hclass="xrefs" xt="opp">
            <span class="prefix">opposite</span>
            <a class="Ref"><span class="xr-g"><span class="xh">opaque</span></span></a>
        </span>

    Why `xt="opp"` is filtered separately: it's a different semantic relation
    (antonym, not synonym) and is rendered as a distinct UI prefix
    ("opposite" vs "synonym"). Mixing them in the same field would confuse
    learners ("is this a synonym or an antonym?"). See CONTEXT.md § Antonym
    for the data contract.

    Returns: list of headword strings, dedup'd, source-order preserved.
    Empty list when the sense has no opposite block.
    """
    out: list[str] = []
    for xrefs in sense_el.cssselect("span[xt='opp']"):
        cls = xrefs.get("class") or ""
        hcls = xrefs.get("hclass") or ""
        if "xrefs" not in cls.split() and hcls != "xrefs":
            continue
        for xh in xrefs.cssselect("span"):
            x_cls = xh.get("class") or ""
            x_hcls = xh.get("hclass") or ""
            if "xh" in x_cls.split() or x_hcls == "xh":
                txt = (xh.text or "").strip()
                if txt:
                    out.append(txt)
    return _dedup_preserve_order(out)


def _extract_sensenum(sense_el) -> Optional[str]:
    """sensenum attribute on <li class='sense'> — nullable for idioms."""
    return sense_el.get("sensenum")


def _extract_def_text(sense_el) -> Optional[str]:
    el = _first(sense_el, OXFORD["def"])
    return _text_of(el) or None


def _extract_cefr(sense_el) -> Optional[str]:
    """cefr attribute on li.sense (lowercase a1/b1/c2 etc.).

    Oxford uses 2 attribute names:
    - "cefr"   → sense 2, 3, ... of a pos block (most senses)
    - "fkcefr" → first sense of first pos block ("first-known CEFR")

    cefr is checked first; fkcefr is fallback. Both uppercased to match the
    rest of the schema (C1, B2, etc.). When both are present, cefr wins
    (avoids the rare case where they disagree).
    """
    v = sense_el.get("cefr") or sense_el.get("fkcefr")
    return v.upper() if v else None


def _extract_register_tags_def(sense_el) -> list[str]:
    """Per-sense register tags (.reg inside li.sense). Unverified — likely 0 hits."""
    raw = [_text_of(r) for r in sense_el.cssselect(OXFORD["register_def"])]
    return _dedup_preserve_order(raw)


def _extract_topics(sense_el) -> list[dict[str, str]]:
    """Per-sense topics: span.topic elements inside span.topic-g.

    Oxford DOM structure (per addictive_(adj).html):
        <span class="topic-g">
          <span class="prefix">Topics </span>
          <a class="Ref"><span class="topic">Social issues<span class="topic_cefr">c1</span></span></a>
          <span class="sep">,</span>
          <a class="Ref"><span class="topic">Health problems<span class="topic_cefr">c1</span></span></a>
        </span>

    Strategy: iterate span.topic elements directly (not topic-g text_content()).
    Each span.topic contains:
      - text node(s) for the name
      - optional <span class="topic_cefr"> sub-element for CEFR

    This correctly handles both 1-topic and N-topic senses. The old approach of
    calling text_content() on the whole topic-g collapsed "Social issuesc1, Health
    problemsc1" into a single string, causing the regex to misparse the first topic's
    name as "Social issuesc1" (CEFR leaked into the name).
    """
    topics = []
    for topic_g in sense_el.cssselect(OXFORD["topic_g"]):
        for topic_el in topic_g.cssselect("span.topic"):
            # Get CEFR from nested span.topic_cefr (may be absent)
            cefr_el = _first(topic_el, "span.topic_cefr")
            if cefr_el is not None:
                cefr_raw = (cefr_el.text_content() or "").strip()
                cefr = cefr_raw.upper() if cefr_raw else None
                # Name = topic text minus the cefr suffix
                # Use text_content() of the whole element, then strip the trailing cefr text
                full_text = _normalize_text(topic_el.text_content()) or ""
                if cefr_raw and full_text.lower().endswith(cefr_raw.lower()):
                    name = full_text[: -len(cefr_raw)].strip()
                else:
                    name = full_text
            else:
                cefr = None
                name = _normalize_text(topic_el.text_content()) or ""
            if name:
                topics.append({"name": name, "cefr": cefr})
    return topics


def _extract_grammar(sense_el) -> Optional[str]:
    """span.grammar — e.g. '[intransitive]', '[countable]'."""
    el = _first(sense_el, OXFORD["grammar"])
    return _text_of(el) or None


def _extract_examples_with_evidence(
    sense_el,
) -> tuple[list[dict[str, Optional[str]]], list[dict[str, Any]]]:
    """Extract examples and their example-linked collocation evidence.

    Oxford pattern: <li class='...'><span class='cf'>frame</span> <span class='x'>example</span></li>
    Section headers (e.g. '+ adv./prep.', '+ noun', '+ adj.') are also <span class='cf'>
    but do NOT have a <span class='x'> sibling — filter them out.

    Real cf filter: text must NOT start with '+' AND must have a <span class='x'> sibling.
    """
    examples: list[dict[str, Optional[str]]] = []
    evidence: list[dict[str, Any]] = []
    for container_index, li in enumerate(sense_el.cssselect(".examples li"), start=1):
        cf_el = _first(li, "span.cf")
        x_el = _first(li, "span.x")
        text = _text_of(x_el) or None
        if not text:
            continue
        # Section header: cf starts with '+' (e.g. '+ adv./prep.', '+ noun')
        # Real cf: no '+' prefix; if cf absent, that's fine
        if cf_el is not None:
            cf_text = _text_of(cf_el)
            if cf_text.startswith("+"):
                cf = None  # treat section header as no cf
            else:
                cf = cf_text or None
        else:
            cf = None
        examples.append({"text": text, "cf": cf})
        if cf:
            evidence.append({
                "text": cf,
                "source": "oxford",
                "origin": "oxford_example_cf",
                "evidence_kind": "example_linked",
                "example_index": len(examples),
                "example_text": text,
                "container_index": container_index,
                "item_index": None,
                "category": None,
                "truncated": False,
                "full_entry_url": None,
            })
    return examples, evidence


def _extract_examples(sense_el) -> list[dict[str, Optional[str]]]:
    """Compatibility wrapper returning the established examples field."""
    return _extract_examples_with_evidence(sense_el)[0]


def _extract_collocations_with_evidence(
    sense_el,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    """Extract Oxford Collocations Dictionary snippets and provenance.

    Layout: <div class='collapse'> > <span class='unbox' unbox='snippet'>
             > <span class='box_title'>Oxford Collocations Dictionary</span>
             > <span class='body'>
                <span class='unbox'>adverb</span>
                <ul>...adverbs...</ul>
                <span class='unbox'>phrases</span>
                <ul>...phrases...</ul>
    """
    out: dict[str, list[str]] = {}
    evidence: list[dict[str, Any]] = []
    container_index = 0
    # Find the "Oxford Collocations Dictionary" snippet within the sense
    for unbox in sense_el.cssselect(OXFORD["collocations"]):
        title = _text_of(_first(unbox, "span.box_title"))
        if "collocations dictionary" not in title.lower():
            continue
        full_entry = _first(unbox, "span.xref_to_full_entry a[href]")
        full_entry_url = full_entry.get("href") if full_entry is not None else None
        # Walk <span class='unbox'> categories, then <ul> with items
        for child in unbox.iter():
            tag = child.tag
            cls = child.get("class", "")
            if tag == "span" and "unbox" in cls.split() and child is not unbox:
                # This is a category label (e.g. "adverb", "phrases", "verb + stay")
                cat = _text_of(child).strip().lower()
                if not cat:
                    continue
                # Next sibling <ul>
                nxt = child.getnext()
                if nxt is not None and nxt.tag == "ul":
                    container_index += 1
                    raw_items = [_text_of(li) for li in nxt.cssselect("li")]
                    truncated = any(item in COLLOC_ARTIFACTS for item in raw_items)
                    # Bug 2 fix (2026-06-13): Oxford Collocations Dictionary UI
                    # truncates long lists with "…" (or ASCII "...") as a
                    # "more items available" indicator. The scraper previously
                    # included these as real collocation items. Filter them out
                    # before returning. Affects every category, not just "adverb".
                    items = [
                        item for item in raw_items
                        if item and item not in COLLOC_ARTIFACTS
                    ]
                    if items:
                        existing = out.setdefault(cat, [])
                        for item in items:
                            if item not in existing:
                                existing.append(item)
                        for item_index, item in enumerate(items, start=1):
                            evidence.append({
                                "text": item,
                                "source": "oxford",
                                "origin": "oxford_collocations_snippet",
                                "evidence_kind": "supporting",
                                "example_index": None,
                                "example_text": None,
                                "container_index": container_index,
                                "item_index": item_index,
                                "category": cat,
                                "truncated": truncated,
                                "full_entry_url": full_entry_url,
                            })
    return out, evidence


def _extract_collocations(sense_el) -> dict[str, list[str]]:
    """Compatibility wrapper returning the established collocations buckets."""
    return _extract_collocations_with_evidence(sense_el)[0]


def _is_idiom(sense_el) -> bool:
    """Walk parent chain: sense is inside <span class='idm-g'> ancestor.

    If the sense is part of an idiom block, sensenum is null AND ancestor has idm-g class.
    """
    p = sense_el.getparent()
    for _ in range(20):
        if p is None:
            return False
        if p.tag == "span" and "idm-g" in (p.get("class") or "").split():
            return True
        p = p.getparent()
    return False


def _extract_pos_sections(root) -> list[dict]:
    """Group senses by POS section.

    Phase 7a discovery: Oxford HTML structure puts the POS section in a different
    place than initially assumed:
        <div class='top-container'>
            <div class='top-g'>
                <span class='webtop'>
                    <h1 class='headword'>...</h1>
                    <span class='pos'>adjective</span>  ← POS label
                    ...
                </span>
            </div>
            <ol class='senses_multiple'>  ← main senses
                <li class='sense'>...</li>  × N
            </ol>
        </div>
        <span class='idm-g'>  ← idioms block
            <ol class='sense_single'>...</ol>
        </span>

    Algorithm:
    1. Find all top-level <ol class='senses_*' or 'sense_single'> whose PARENT is
       the entry div (NOT inside span.idm-g). These are main POS sections.
    2. For each such ol, find the POS label: walk up to the top-g div, find
       the span.pos within that top-g.
    3. If a file has 1 such main ol: 1 pos_data entry with all senses from it.
    4. If a file has 2+ such main ols (rare multi-POS single-file case):
       create 1 pos_data entry per main ol.
    5. Idiom senses (ol inside span.idm-g) are excluded from main POS sections.
    """
    # Find all main POS ols (parent is the entry div, not inside idm-g)
    main_ols: list = []
    for ol in root.cssselect("ol.senses_multiple, ol.sense_single"):
        p = ol.getparent()
        if p is None:
            continue
        cls = p.get("class") or ""
        # Main ols are direct children of the entry div (no idm-g ancestor)
        if "idm-g" in cls.split():
            continue
        main_ols.append(ol)

    if not main_ols:
        # Truly no main senses — return empty
        return []

    # For each main ol, find the POS label from the sibling span.pos
    sections: list[dict] = []
    for ol in main_ols:
        # Walk up to find the top-g / top-container, then find span.pos
        pos_label = _find_pos_for_ol(ol)
        if not pos_label:
            pos_label = "unknown"
        # Collect non-idiom senses from this ol
        section_senses = [
            s for s in ol.cssselect("li.sense, li[hclass='sense']")
            if not _is_idiom(s)
        ]
        sections.append({
            "pos": pos_label,
            "register_tags": [],
            "definitions": [_build_definition(n, s) for n, s in enumerate(section_senses, start=1)],
        })

    return sections


def _extract_canonical_url(root) -> str | None:
    """Return the page's official Oxford canonical URL, if trustworthy."""
    valid_urls: set[str] = set()
    for element in root.xpath("//link[contains(concat(' ', normalize-space(@rel), ' '), ' canonical ')]"):
        href = (element.get("href") or "").strip()
        if any(character.isspace() or character in "\"'<>" for character in href):
            continue
        try:
            parsed = urlsplit(href)
        except ValueError:
            continue
        if (
            parsed.scheme == "https"
            and parsed.hostname == "www.oxfordlearnersdictionaries.com"
            and parsed.path.startswith("/definition/english/")
            and parsed.path != "/definition/english/"
            and not parsed.query
            and not parsed.fragment
        ):
            valid_urls.add(href)
    return next(iter(valid_urls)) if len(valid_urls) == 1 else None


def _find_pos_for_ol(ol_el) -> str:
    """Find the POS label for a given main ol by walking up to find sibling span.pos.

    Oxford structure: <ol class='senses_multiple'> comes AFTER <div class='top-g'>
    which contains <span class='pos'>. The ol is inside <div class='top-container'>.
    The <div class='top-container'> contains both top-g (with pos) AND the ol.

    Strategy: find the closest preceding/ancestor span.pos in the same top-container
    or top-g div.
    """
    # Walk up to find top-container
    container = ol_el.getparent()  # typically top-container or similar
    if container is None:
        return ""

    # Look for span.pos within container (or close ancestors)
    for ancestor in [container, container.getparent()]:
        if ancestor is None:
            continue
        pos_el = ancestor.cssselect("span.pos")
        # Take the LAST one (or the first one that's not empty)
        for pe in pos_el:
            txt = (pe.text or "").strip()
            if txt:
                return txt

    # Fallback: look for the closest preceding sibling span.pos
    prev = ol_el.getprevious()
    while prev is not None:
        pos_el = prev.cssselect("span.pos") if prev.tag in ("div", "span") else []
        for pe in pos_el:
            txt = (pe.text or "").strip()
            if txt:
                return txt
        # Also check if prev itself is a span.pos
        if prev.tag == "span" and "pos" in (prev.get("class") or "").split():
            txt = (prev.text or "").strip()
            if txt:
                return txt
        prev = prev.getprevious()

    return ""


def _find_pos_for_idiom(idm_g, fallback_pos: str = "unknown") -> str:
    """Return the POS of the Oxford entry that owns an idiom block."""
    for ancestor in idm_g.iterancestors():
        if "entry" not in (ancestor.get("class") or "").split():
            continue
        for pos_el in ancestor.cssselect("div.top-container div.webtop span.pos"):
            text = _text_of(pos_el).strip()
            if text:
                return text
        break
    return fallback_pos


def _build_definition(n: int, sense_el) -> dict:
    """Build a single Definition dict from a li.sense element."""
    labels = extract_labels_for_sense(sense_el)
    examples, example_evidence = _extract_examples_with_evidence(sense_el)
    collocations, snippet_evidence = _extract_collocations_with_evidence(sense_el)
    return {
        "n": n,
        "sensenum_local": _extract_sensenum(sense_el),
        "text": _extract_def_text(sense_el),
        "register_tags": labels["register_tags"],
        "domain": labels["domain"],
        "cefr": _extract_cefr(sense_el),
        "topics": _extract_topics(sense_el),
        "collocations": collocations,
        "collocation_evidence": example_evidence + snippet_evidence,
        "examples": examples,
        "is_phrase": False,    # not detected in v1
        "is_idiom": _is_idiom(sense_el),
        "synonyms": _extract_synonyms(sense_el),
        "antonyms": _extract_antonyms(sense_el),
    }


# -----------------------------------------------------------------------------
# Main parser
# -----------------------------------------------------------------------------

def parse_oxford(html_bytes: bytes, source_files: Optional[list[str]] = None) -> dict[str, Any]:
    """Parse an Oxford HTML page into schema v2 record.

    Args:
        html_bytes: raw HTML bytes
        source_files: list of cache filenames (for traceability). Single file = [name].

    Returns:
        Schema v2 record. If the page is a non-word page (e.g. Oxford's labels taxonomy
        page at /about/english/labels), returns None — caller should skip.
    """
    root = lxml_html.fromstring(html_bytes)

    # Detect non-word pages (e.g. labels taxonomy, error pages).
    # Oxford's word pages have <h1 class="headword">. Other pages
    # (labels, about, etc.) don't.
    h1 = root.cssselect("h1.headword")
    if not h1:
        return None

    word = _extract_headword(root)
    homonym_index = _extract_homonym_index(root)
    # Strip trailing digit from word: 'bass1' -> 'bass'
    # The digit is preserved separately as homonym_index.
    if word and homonym_index is not None:
        word = re.sub(r"\d+$", "", word)
    pos = _extract_pos(root)
    uk_ipa = _extract_ipa_uk(root)
    us_ipa = _extract_ipa_us(root)
    audio = _extract_audio_paths(root)
    lists = _extract_oxford_lists(root)
    badge = _extract_oxford_badge(root)
    opal = _extract_opal(root)
    awl = _extract_awl(root)
    register_top = _extract_register_tags_top(root)
    see_also = _extract_see_also(root)

    # Phase 7a: scope sense extraction to actual POS section boundaries
    pos_data = _extract_pos_sections(root)
    canonical_url = _extract_canonical_url(root)
    for section in pos_data:
        section["source_url"] = canonical_url

    # Idiom extraction (phrase + def + examples)
    # Oxford's idiom block structure:
    #   <span class="idm-g" id="above_idmg_1" sk="aboveall">
    #     <span class="idm" cefr="c1">above all</span>
    #     <ol class="sense_single">
    #       <li class="sense" fkcefr="c1">
    #         <span class="def">most important of all; especially</span>
    #         <ul class="examples">
    #           <li><span class="x">Above all, keep in touch.</span></li>
    #         </ul>
    #       </li>
    #     </ol>
    #   </span>
    # CEFR resolution: span.idm @ cefr (idiom-level) → li.sense @ fkcefr (sense-level)
    # → span.idm @ cefr (idiom-level as final fallback) → null.
    idiom_owner_parts: list[str] = []
    for section in pos_data:
        owner_part = (section.get("pos") or "").strip()
        if owner_part and owner_part != "unknown" and owner_part not in idiom_owner_parts:
            idiom_owner_parts.append(owner_part)
    idiom_fallback_pos = ", ".join(idiom_owner_parts) or "unknown"
    idioms = []
    for idm_g in root.cssselect(OXFORD["idm_block"]):
        phrase_el = _first(idm_g, OXFORD["idm_phrase"])
        if phrase_el is None:
            continue
        phrase = _text_of(phrase_el)
        if not phrase:
            continue
        # CEFR: try @cefr on span.idm first, then @fkcefr on li.sense.
        # Uppercase to match the rest of the schema (C1, B2, etc.).
        cefr = phrase_el.get("cefr")
        sense_li = _first(idm_g, "li.sense")
        if not cefr and sense_li is not None:
            cefr = sense_li.get("fkcefr")
        if cefr:
            cefr = cefr.upper()
        # Def: first span.def inside the idiom's sense li (works for both
        # sense_single and senses_multiple ol classes).
        def_el = _first(idm_g, "li.sense span.def")
        def_text = _text_of(def_el) if def_el is not None else None
        # Examples: span.x inside ul.examples > li
        examples: list[str] = []
        if sense_li is not None:
            for x_el in sense_li.cssselect("ul.examples li span.x"):
                t = _text_of(x_el)
                if t:
                    examples.append(t)
        idioms.append({
            "phrase": phrase,
            "pos": _find_pos_for_idiom(idm_g, idiom_fallback_pos),
            "text": def_text,
            "examples": examples,
            "cefr": cefr,
        })

    # Verb forms table (only present for verbs)
    verb_forms = None
    vft = _first(root, OXFORD["verb_forms_table"])
    if vft is not None:
        forms: dict[str, str] = {}
        for tr in vft.cssselect("tr.verb_form"):
            form_name = tr.get("form")
            form_word_el = _first(tr, "td.verb_form")
            if form_name and form_word_el is not None:
                # Strip the "prefix" span
                word_text = _text_of(form_word_el)
                # Remove any leading prefix like "present simple I / you / we / they "
                word_text = re.sub(r"^.*?\)\s*", "", word_text).strip()
                forms[form_name] = word_text
        if forms:
            verb_forms = forms

    return {
        # $schema field removed in v3: placeholder URL (https://ielts-deck.local/...)
        # was non-resolvable, so no editor/tooling actually consumed it. The
        # data/schema/oxford_record.schema.json file is the real contract.
        "word": word,
        "homonym_index": homonym_index,
        "source": "oxford",
        "source_url": None,
        "source_files": source_files or [],
        "pos": pos,
        "register_tags": register_top,
        "oxford_lists": lists,
        "oxford_badge": badge,
        "opal": opal,
        "awl": awl,
        "uk_ipa": uk_ipa,
        "us_ipa": us_ipa,
        "audio": audio,
        "see_also": see_also,
        "pos_data": pos_data,
        "verb_forms": verb_forms,
        "idioms": idioms,
    }
