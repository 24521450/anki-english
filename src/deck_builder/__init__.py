"""Deck builder — turn merged records into Anki Notes.

Public interface (deep module, per skill guidance):
    resolve_cards(record) -> list[Note]
        One record in, zero or more Anki Notes out. Implements Card Identity
        (Word, CEFR) and Sense Sorting (all CEFR-matching defs retained, no
        per-card cap) per CONTEXT.md.

Each Note is a dict with the Anki field names that
`design/EAVM/{front,back}_template.txt` expect:
    Word, CEFRLevel, PartOfSpeech, Definition, Example,
    IPA, AudioUK, AudioUS, Tags, Collocations, WordFamily

CEFR resolution waterfall (Phase 7c grill decision):
    def.cefr (per sense)  →  if None, fall back to oxford_badge (word-level)
                          →  if still None, use "UNCLASSIFIED".

Per CONTEXT.md § Skip Rule: records with _skip=true produce 0 Notes.
Per CONTEXT.md § Idiom Box: idiom-only records produce 1 card; idioms
render in the back template's Idiom Box.
"""
from __future__ import annotations

from src.deck_builder.formatting import (
    format_idioms as _shared_format_idioms,
    format_ipa_field as _shared_format_ipa_field,
    normalize_ipa as _shared_normalize_ipa,
)
from src.deck_builder.build_metadata import sync_idioms_feature_tag


# Anki note field names (per design/EAVM/{front,back}_template.txt)
ANKI_FIELDS = (
    "Word", "CEFRLevel", "PartOfSpeech", "Definition", "Example",
    "IPA", "AudioUK", "AudioUS", "Tags", "Collocations", "WordFamily",
    "Idioms",
)


def _format_idioms_field(idioms: list) -> str:
    """Serialize idioms list to the deck format the back template parses.

    Per grill session decision (2026-06-19):
        phrase :: text :: ex1 | ex2 $$ phrase2 :: text2 :: ex1
    Delimiters:
        $$  separates idioms (top-level)
        ::  separates phrase / text / examples within an idiom
        |   separates examples within an idiom (mirrors other list fields)
    Empty / missing fields are dropped from each entry.
    Empty input → ''.

    Filter: only idioms with a CEFR level assigned (A1..C2 / UNCLASSIFIED).
    Idioms with cefr=None are dropped per user decision (2026-06-20).
    """
    return _shared_format_idioms(idioms)


def _normalize_ipa_value(s) -> str:
    """Strip a raw IPA string: whitespace + surrounding slashes.

    Inputs may be None, '', '/x/', or 'x' (Oxford sometimes has stray whitespace
    around the slashes). Returns the bare IPA without slashes, or ''.
    """
    return _shared_normalize_ipa(s)


def _format_ipa_field(uk_ipa, us_ipa) -> str:
    """Format the IPA field per user decision (2026-06-20).

    - If both UK and US are present and DIFFERENT → "UK: /uk/ | US: /us/"
    - If both are present and IDENTICAL → "/uk/" (single)
    - If only one is present → "/that/"
    - If neither → ""

    Inputs are normalized (slashes + whitespace stripped) before comparison and
    re-wrapped in slashes on output. The "/" separator between UK: and US: is
    literal (not a template pipe).
    """
    return _shared_format_ipa_field(uk_ipa, us_ipa)


def _empty_note() -> dict:
    """An empty Anki Note with all fields set to ''."""
    return {f: "" for f in ANKI_FIELDS}


def _sense_cefr(def_dict: dict, fallback_badge: str | None) -> str:
    """CEFR waterfall: def.cefr → oxford_badge → UNCLASSIFIED."""
    return def_dict.get("cefr") or fallback_badge or "UNCLASSIFIED"


def _sense_sorting_key(item: tuple[str, dict]) -> tuple:
    """Sort key for Sense Sorting: sensenum_local asc, then example count desc.

    `sensenum_local` may be None (idiom defs); treat as last. Examples count
    is negated to get descending order with Python's stable sort.

    Per CONTEXT.md § Sense Sorting: ordering matters for stable presentation,
    not for filtering. The sort is by Oxford's own frequency proxy
    (sensenum_local asc), with example count as tie-breaker.
    """
    _, d = item
    sl = d.get("sensenum_local")
    sl_rank = int(sl) if sl and str(sl).isdigit() else 10 ** 6
    ex_count = -len(d.get("examples") or [])
    return (sl_rank, ex_count)


def _apply_sense_sorting(pairs: list[tuple[str, dict]], cap: int | None = None) -> list[tuple[str, dict]]:
    """Sort senses by sensenum_local (Oxford's frequency proxy), ties by examples.

    Per CONTEXT.md § Sense Sorting (replaces the legacy Sense Cap): all
    CEFR-matching senses are retained. Senses are logically ordered by
    `sensenum_local` ascending so the most common senses render first; ties
    broken by example count descending.

    `cap` is retained as an optional parameter for future flexibility (e.g.
    study-profile variants that DO want a per-card limit). When `cap` is None
    (the default) no limit is applied — every sense is kept.
    """
    sorted_pairs = sorted(pairs, key=_sense_sorting_key)
    if cap is None:
        return sorted_pairs
    return sorted_pairs[:cap]


def _pos_set(pairs: list[tuple[str, dict]]) -> list[str]:
    """Unique POS labels in first-appearance order."""
    out: list[str] = []
    for p, _ in pairs:
        if p and p not in out:
            out.append(p)
    return out


def _populate_note_fields(
    note: dict, record: dict, capped: list[tuple[str, dict]]
) -> None:
    """Fill in Note fields from record + sorted (post-Sense-Sorting) defs.

    Mutates `note` in place. Field encoding matches what the Anki templates
    expect (see design/EAVM/{front,back}_template.txt):
        - Definition, Example: pipe-joined
        - Tags: space-joined tag tokens
        - Others: scalar
    """
    # Definition + Example fields (pipe-joined; per template JS split)
    def_texts = [(d.get("text") or "") for _, d in capped]
    note["Definition"] = "|".join(def_texts)
    example_texts: list[str] = []
    for _, d in capped:
        examples = d.get("examples") or []
        example_texts.append((examples[0].get("text") or "") if examples else "")
    note["Example"] = "|".join(example_texts)

    # Audio fields (UK/US URLs from record.audio)
    audio = record.get("audio") or {}
    note["AudioUK"] = audio.get("uk") or ""
    note["AudioUS"] = audio.get("us") or ""

    # IPA: formatted from record.uk_ipa / record.us_ipa
    # Both come from the parser already wrapped in slashes; _format_ipa_field
    # normalizes (re-strips) and decides the single-vs-double form.
    note["IPA"] = _format_ipa_field(record.get("uk_ipa"), record.get("us_ipa"))

    # Collocations: empty per user decision (2026-06-20). Field stays in the
    # ANKI_FIELDS tuple (template references it) but we always write ''.
    note["Collocations"] = ""

    # Tags: corpus badges (Oxford 3000/5000) → space-separated tag tokens
    tag_tokens: list[str] = []
    for lst in record.get("oxford_lists") or []:
        if lst == "Oxford 3000":
            tag_tokens.append("Oxford_3000")
        elif lst == "Oxford 5000":
            tag_tokens.append("Oxford_5000")
    note["Tags"] = " ".join(tag_tokens)

    # WordFamily: empty per user decision (2026-06-20). Even though verb_forms
    # is in the record, the field is no longer populated.
    note["WordFamily"] = ""

    # Idioms: phrase :: text :: ex1 | ex2 $$ phrase2 :: text2 :: ex1
    # Empties drop from the inner triple; empties across the whole list → ''.
    # Per user (2026-06-20): only idioms with a CEFR level survive.
    note["Idioms"] = _format_idioms_field(record.get("idioms") or [])
    note["Tags"] = sync_idioms_feature_tag(note["Tags"], note["Idioms"])


def _resolve_idiom_only_card(record: dict) -> dict:
    """Build a single card for an idiom-only record (no pos_data, has idioms)."""
    note = _empty_note()
    note["Word"] = record.get("word") or ""
    note["CEFRLevel"] = record.get("oxford_badge") or "UNCLASSIFIED"
    note["PartOfSpeech"] = ",".join(record.get("pos") or [])
    # No senses to populate, but audio + IPA + idioms still apply
    audio = record.get("audio") or {}
    note["AudioUK"] = audio.get("uk") or ""
    note["AudioUS"] = audio.get("us") or ""
    note["IPA"] = _format_ipa_field(record.get("uk_ipa"), record.get("us_ipa"))
    note["Idioms"] = _format_idioms_field(record.get("idioms") or [])
    note["Tags"] = sync_idioms_feature_tag(note["Tags"], note["Idioms"])
    return note


def _resolve_main_cards(record: dict, all_pairs: list[tuple[str, dict]]) -> list[dict]:
    """Build the per-CEFR cards for a record that has at least 1 sense."""
    badge = record.get("oxford_badge")
    word = record.get("word") or ""

    # Group defs by resolved CEFR (per waterfall)
    by_cefr: dict[str, list[tuple[str, dict]]] = {}
    for pos, d in all_pairs:
        c = _sense_cefr(d, badge)
        by_cefr.setdefault(c, []).append((pos, d))

    notes: list[dict] = []
    for cefr, pairs in by_cefr.items():
        sorted_pairs = _apply_sense_sorting(pairs)
        note = _empty_note()
        note["Word"] = word
        note["CEFRLevel"] = cefr
        note["PartOfSpeech"] = ",".join(_pos_set(sorted_pairs))
        _populate_note_fields(note, record, sorted_pairs)
        notes.append(note)
    return notes


def resolve_cards(record: dict) -> list[dict]:
    """Turn a merged record into 0+ Anki Notes, one per (word, CEFR) card.

    Card Identity (CONTEXT.md § Card Identity): (Word, CEFRLevel) is unique.
    Sense Sorting (CONTEXT.md § Sense Sorting): all CEFR-matching senses are
    retained and ordered by sensenum_local asc, example count desc.

    Skip Rule (CONTEXT.md § Skip Rule): _skip=true records produce 0 Notes.

    Idiom-only records (pos_data=[], idioms>0) produce 1 card with the
    word's oxford_badge as CEFR (or UNCLASSIFIED). Per CONTEXT.md § Idiom
    Box, the back template renders the idioms separately from senses.

    Returns: list of Notes. Each Note is a dict mapping Anki field names
    (Word, CEFRLevel, ...) to string values.
    """
    # Skip rule: builder ignores records flagged for skip
    if record.get("_skip"):
        return []

    # Flatten all (pos, def) pairs from all pos_data entries
    all_pairs: list[tuple[str, dict]] = []
    for pd in record.get("pos_data", []):
        pos = pd.get("pos", "")
        for d in pd.get("definitions", []):
            all_pairs.append((pos, d))

    if not all_pairs:
        if record.get("idioms"):
            return [_resolve_idiom_only_card(record)]
        return []

    return _resolve_main_cards(record, all_pairs)
