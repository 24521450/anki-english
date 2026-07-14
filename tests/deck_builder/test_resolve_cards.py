"""Tests for deck builder: build Anki Notes from Oxford/Cambridge records.

Per CONTEXT.md § Card Identity: a card is uniquely identified by
(Word, CEFRLevel). One record may produce multiple Notes (one per CEFR
level its senses carry), or zero Notes (if the record is skipped).

Per CONTEXT.md § Sense Sorting (replaces the legacy Sense Cap, removed
2026-06-21): every CEFR-matching sense is retained on the card. Senses
are ordered by `sensenum_local` ascending (Oxford's frequency proxy),
ties broken by example count descending. No per-card def limit.

CEFR resolution waterfall (decided Phase 7c grill):
    def.cefr (per sense)  →  if None, fall back to oxford_badge (word-level)
                          →  if still None, use UNCLASSIFIED.
"""
from __future__ import annotations

import sys

from pathlib import Path
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, PROJECT_ROOT)


# =============================================================================
# Test helpers
# =============================================================================

def _record(word: str = "sick", pos_data=None, pos=("adjective",), badge="A1",
            audio=None, idioms=None, oxford_lists=None, verb_forms=None,
            homonym_index=None, _skip: bool = False, _skip_reason: str = None,
            see_also=None, uk_ipa=None, us_ipa=None) -> dict:
    """Build a minimal Oxford record for testing."""
    return {
        "word": word,
        "homonym_index": homonym_index,
        "source": "oxford",
        "source_url": None,
        "source_files": [f"oxford_{word}.html"],
        "pos": list(pos),
        "register_tags": [],
        "oxford_lists": list(oxford_lists) if oxford_lists else [],
        "oxford_badge": badge,
        "opal": None,
        "awl": None,
        "uk_ipa": uk_ipa,
        "us_ipa": us_ipa,
        "audio": audio or {"uk": None, "us": None},
        "see_also": list(see_also) if see_also else [],
        "pos_data": pos_data or [],
        "verb_forms": verb_forms,
        "idioms": idioms or [],
        "_skip": _skip,
        "_skip_reason": _skip_reason,
    }


def _def(text: str, cefr=None, examples=None, sensenum_local="1",
         register_tags=None, topics=None, collocations=None) -> dict:
    """Build a minimal Definition dict for testing."""
    return {
        "n": 1,
        "sensenum_local": sensenum_local,
        "text": text,
        "register_tags": list(register_tags) if register_tags else [],
        "cefr": cefr,
        "topics": list(topics) if topics else [],
        "collocations": dict(collocations) if collocations else {},
        "examples": list(examples) if examples else [],
        "is_phrase": False,
        "is_idiom": False,
    }


def _pos_data(pos: str, defs: list) -> dict:
    return {"pos": pos, "register_tags": [], "definitions": defs}


# =============================================================================
# Cycle 1 — Tracer bullet: _skip record produces no Notes
# =============================================================================

def test_resolve_cards_skipped_record_produces_no_notes():
    """A record with _skip=true produces 0 Notes (builder ignores it)."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="Buck Rogers",
        pos_data=[_pos_data("unknown", [_def("biography stub", cefr=None)])],
        badge=None,
        oxford_lists=[],
        _skip=True,
        _skip_reason="proper-noun-or-cultural-entry: no CEFR/oxford-list membership",
    )

    notes = resolve_cards(rec)

    assert notes == []


# =============================================================================
# Cycle 2 — Single sense, single CEFR: 1 Note
# =============================================================================

def test_resolve_cards_single_sense_single_cefr_produces_one_note():
    """A record with 1 sense, 1 explicit def.cefr → 1 Note (the card)."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="sick",
        badge="A1",
        pos_data=[_pos_data("adjective", [
            _def("ill; not healthy", cefr="A1", sensenum_local="1"),
        ])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    note = notes[0]
    assert note["Word"] == "sick"
    assert note["CEFRLevel"] == "A1"
    assert note["PartOfSpeech"] == "adjective"


# =============================================================================
# Cycle 3 — Multi-CEFR split: 1 record → N Notes (one per CEFR)
# =============================================================================

def test_resolve_cards_multi_cefr_splits_into_one_note_per_cefr():
    """Record with 3 senses at 3 different CEFRs → 3 Notes."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="aggregate",
        badge=None,
        pos_data=[
            _pos_data("adjective", [_def("made up of several amounts",
                                       cefr="C1", sensenum_local="1")]),
            _pos_data("verb", [_def("to combine into a group",
                                    cefr="B2", sensenum_local="1")]),
            _pos_data("noun", [_def("a total number",
                                    cefr="C2", sensenum_local="1")]),
        ],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 3
    cefrs = {n["CEFRLevel"] for n in notes}
    assert cefrs == {"C1", "B2", "C2"}


# =============================================================================
# Cycle 4 — Sense Sorting: no per-card cap, all senses retained in sensenum order
# =============================================================================

def test_resolve_cards_sense_sorting_retains_all_defs():
    """A single (word, CEFR) card with > 3 defs keeps ALL of them, ordered by
    sensenum_local (ascending). Per CONTEXT.md § Sense Sorting, the legacy
    3-definition cap was removed on 2026-06-21; every CEFR-matching sense is
    now retained.
    """
    from src.deck_builder import resolve_cards

    rec = _record(
        word="run",
        badge="B1",
        pos_data=[_pos_data("verb", [
            _def(f"verb def {i}", cefr="B1", sensenum_local=str(i))
            for i in range(1, 6)  # 5 defs
        ])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    # Behavior: all 5 defs retained in sensenum_local order (1..5).
    # The field encoding (pipe-join) is an implementation detail; we verify the
    # behavior by counting pipe-delimited entries.
    note = notes[0]
    defs = [d for d in note["Definition"].split("|") if d]
    assert len(defs) == 5, f"expected all 5 defs retained (Sense Sorting), got {len(defs)}"
    # Verify ordering matches sensenum_local ascending.
    assert defs == [f"verb def {i}" for i in range(1, 6)]


def test_resolve_cards_sense_sorting_default_cap_none_returns_all():
    """`_apply_sense_sorting` with cap=None (default) returns every sense —
    no slicing, just sorting by sensenum_local.
    """
    from src.deck_builder import _apply_sense_sorting, _sense_sorting_key

    pairs = [(f"pos{i}", {"sensenum_local": str(i), "examples": []}) for i in range(1, 8)]
    out = _apply_sense_sorting(pairs)
    assert len(out) == 7
    # Order: sensenum_local asc → 1..7
    assert [p[0] for p in out] == [f"pos{i}" for i in range(1, 8)]


def test_resolve_cards_sense_sorting_with_explicit_cap_truncates():
    """`_apply_sense_sorting(pairs, cap=N)` retains the legacy Sense Cap
    behavior: top N by sensenum_local, ties broken by example count desc.
    Kept as opt-in for future study-profile variants.
    """
    from src.deck_builder import _apply_sense_sorting

    pairs = [(f"pos{i}", {"sensenum_local": str(i), "examples": []}) for i in range(1, 8)]
    out = _apply_sense_sorting(pairs, cap=3)
    assert len(out) == 3
    assert [p[0] for p in out] == ["pos1", "pos2", "pos3"]


def test_resolve_cards_sense_sorting_tie_breaks_by_example_count():
    """When two defs share the same sensenum_local (rare but possible for
    idioms with sensenum_local=None), the one with more examples sorts first.
    """
    from src.deck_builder import _apply_sense_sorting

    pairs = [
        ("p1", {"sensenum_local": None, "examples": [{"text": "a"}, {"text": "b"}]}),
        ("p2", {"sensenum_local": None, "examples": [{"text": "a"}]}),
    ]
    out = _apply_sense_sorting(pairs)
    # p1 has 2 examples (negated → -2 sorts before -1) → first
    assert [p[0] for p in out] == ["p1", "p2"]


def test_resolve_cards_sense_sorting_empty_input_returns_empty():
    """`_apply_sense_sorting([])` returns []. Defensive: build stage must not
    crash on a (word, CEFR) bucket with no senses (already filtered upstream,
    but the helper should still be safe to call).
    """
    from src.deck_builder import _apply_sense_sorting

    assert _apply_sense_sorting([]) == []
    assert _apply_sense_sorting([], cap=3) == []


def test_resolve_cards_sense_sorting_key_exposed_for_testing():
    """`_sense_sorting_key` is the same key previously named `_sense_cap_key`
    — the sort is the legacy ordering, just without the truncation step.
    """
    from src.deck_builder import _sense_sorting_key

    item = ("verb", {"sensenum_local": "2", "examples": [{"text": "a"}]})
    sl_rank, neg_ex = _sense_sorting_key(item)
    assert sl_rank == 2
    assert neg_ex == -1


# =============================================================================
# Cycle 5 — CEFR waterfall: def.cefr None + oxford_badge set → badge wins
# =============================================================================

def test_resolve_cards_cefr_inherits_from_oxford_badge():
    """A sense with def.cefr=None inherits the word's oxford_badge (per grill decision)."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="DVD",
        badge="A1",
        pos_data=[_pos_data("noun", [
            _def("a digital video disc", cefr=None, sensenum_local="1"),
        ])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["CEFRLevel"] == "A1"


def test_resolve_cards_no_cefr_no_badge_yields_unclassified():
    """A sense with no def.cefr and no word badge → UNCLASSIFIED card."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="obscureword",
        badge=None,
        pos_data=[_pos_data("noun", [
            _def("a word with no CEFR", cefr=None, sensenum_local="1"),
        ])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["CEFRLevel"] == "UNCLASSIFIED"


# =============================================================================
# Cycle 6 — Field population: Word, CEFRLevel, PartOfSpeech
# =============================================================================

def test_resolve_cards_part_of_speech_is_comma_joined_for_multi_pos():
    """A card spanning multiple POS labels → PartOfSpeech is comma-joined
    (so the front_template JS can render multiple chips).

    Note: this test uses 3 POS labels. Each POS contributes exactly 1 sense,
    so the card spans 3 senses total — well within the unlimited Sense
    Sorting model (no cap).
    """
    from src.deck_builder import resolve_cards

    rec = _record(
        word="round",
        badge="B2",
        pos_data=[
            _pos_data("adjective", [_def("circular", cefr="B2", sensenum_local="1")]),
            _pos_data("noun", [_def("a single stage", cefr="B2", sensenum_local="1")]),
            _pos_data("verb", [_def("to make round", cefr="B2", sensenum_local="1")]),
        ],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    pos_field = notes[0]["PartOfSpeech"]
    for p in ["adjective", "noun", "verb"]:
        assert p in pos_field
    # Comma-joined (not space-joined, not pipe-joined)
    assert "," in pos_field


# =============================================================================
# Cycle 7 — Definition + Example pipe-splitting
# =============================================================================

def test_resolve_cards_definition_and_example_fields_are_pipe_split():
    """Each def's text goes into Definition field (|), first example into Example (|)."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="sick",
        badge="A1",
        pos_data=[_pos_data("adjective", [
            _def("ill", cefr="A1", sensenum_local="1",
                 examples=[{"text": "I feel sick.", "cf": None}]),
            _def("fed up", cefr="A1", sensenum_local="2",
                 examples=[{"text": "I'm sick of waiting.", "cf": None}]),
        ])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    note = notes[0]
    defs = [d for d in note["Definition"].split("|") if d]
    assert len(defs) == 2
    assert "ill" in defs[0]
    assert "fed up" in defs[1]
    examples = [e for e in note["Example"].split("|") if e]
    assert len(examples) == 2


# =============================================================================
# Cycle 8 — Audio field population
# =============================================================================

def test_resolve_cards_populates_audio_fields_from_record():
    """Note fields AudioUK / AudioUS come from the record's audio dict."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="sick",
        badge="A1",
        pos_data=[_pos_data("adjective", [_def("ill", cefr="A1", sensenum_local="1")])],
        audio={"uk": "https://audio.example.com/sick_uk.mp3",
               "us": "https://audio.example.com/sick_us.mp3"},
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    note = notes[0]
    assert note["AudioUK"] == "https://audio.example.com/sick_uk.mp3"
    assert note["AudioUS"] == "https://audio.example.com/sick_us.mp3"


# =============================================================================
# Cycle 9 — Collocations + WordFamily fields: BOTH empty per user (2026-06-20)
# =============================================================================

def test_resolve_cards_collocations_field_is_empty():
    """Per user decision (2026-06-20), the Collocations field is empty.

    Even when the source record has collocations extracted, the Anki note
    receives '' for Collocations. Field stays in ANKI_FIELDS so the template
    reference doesn't break, but content is intentionally cleared.
    """
    from src.deck_builder import resolve_cards

    rec = _record(
        word="sick",
        badge="A1",
        pos_data=[_pos_data("adjective", [
            _def("ill", cefr="A1", sensenum_local="1",
                 collocations={"adjective": ["terribly"], "verb + sick": ["feel"]}),
        ])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["Collocations"] == ""


def test_resolve_cards_wordfamily_field_is_empty_even_with_verb_forms():
    """Per user decision (2026-06-20), WordFamily field is empty.

    Even when the record has verb_forms (e.g. for a regular verb), the Anki
    note's WordFamily is '' — we no longer surface verb forms in cards.
    """
    from src.deck_builder import resolve_cards

    rec = _record(
        word="linger",
        pos=("verb",),
        badge="C1",
        verb_forms={"root": "linger", "past": "lingered", "pastpart": "lingered"},
        pos_data=[_pos_data("verb", [_def("to continue to exist", cefr="C1",
                                          sensenum_local="1")])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["WordFamily"] == ""


# =============================================================================
# Cycle 10 — Tags field (corpus badges)
# =============================================================================

def test_resolve_cards_corpus_badge_translates_to_tags():
    """Oxford 3000/5000 list membership → space-separated tag tokens in Tags field."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="sick",
        badge="A1",
        oxford_lists=["Oxford 3000", "Oxford 5000"],
        pos_data=[_pos_data("adjective", [_def("ill", cefr="A1", sensenum_local="1")])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    tags = notes[0]["Tags"]
    assert "Oxford_3000" in tags
    assert "Oxford_5000" in tags


# =============================================================================
# Cycle 11 — Idiom-only records (e.g. accordance, Nod) produce 1 card
# =============================================================================

def test_resolve_cards_idiom_only_record_produces_one_card():
    """A record with pos_data=[] but idioms>0 (e.g. 'accordance', 'Nod')
    produces 1 card. The card has the word's oxford_badge as CEFR (or
    UNCLASSIFIED if no badge). Idioms render in the back template's Idiom Box.

    Per CONTEXT.md § Skip Rule: idiom-only records are NOT skipped.
    Per CONTEXT.md § Idiom Box: idioms are rendered separately from senses.
    """
    from src.deck_builder import resolve_cards

    rec = _record(
        word="accordance",
        pos=("noun",),
        badge="C1",
        pos_data=[],  # no main-word defs
        idioms=[
            {"phrase": "in accordance with", "pos": None, "text": None,
             "register_tags": [], "cefr": None},
        ],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    note = notes[0]
    assert note["Word"] == "accordance"
    assert note["CEFRLevel"] == "C1"
    # No definitions, so Definition field is empty
    assert note["Definition"] == ""


def test_resolve_cards_idiom_only_no_badge_yields_unclassified():
    """Idiom-only record with no oxford_badge → 1 card with UNCLASSIFIED CEFR."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="Nod",
        pos=("noun", "verb"),
        badge=None,
        pos_data=[],
        idioms=[
            {"phrase": "a Nod to something", "pos": None, "text": None,
             "register_tags": [], "cefr": None},
        ],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["CEFRLevel"] == "UNCLASSIFIED"


# =============================================================================
# Cycle 12 — IPA formatting (UK/US, identical/different/missing) per 2026-06-20
# =============================================================================

def test_resolve_cards_ipa_both_different_uses_uk_us_pipe_format():
    """When UK and US IPAs differ, format as 'UK: /uk/ | US: /us/'."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="schedule",
        badge="B1",
        uk_ipa="/ˈʃedjuːl/",
        us_ipa="/ˈskedʒuːl/",
        pos_data=[_pos_data("noun", [_def("a plan", cefr="B1", sensenum_local="1")])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["IPA"] == "UK: /ˈʃedjuːl/ | US: /ˈskedʒuːl/"


def test_resolve_cards_ipa_both_identical_uses_single_form():
    """When UK and US IPAs match, emit a single /ipa/ (no UK:/US: prefix)."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="able",
        badge="A2",
        uk_ipa="/ˈeɪbl/",
        us_ipa="/ˈeɪbl/",
        pos_data=[_pos_data("adjective", [_def("capable", cefr="A2",
                                               sensenum_local="1")])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["IPA"] == "/ˈeɪbl/"


def test_resolve_cards_ipa_uk_only_uses_single_form():
    """When only UK IPA is present, emit /uk/."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="alpha",
        badge="A1",
        uk_ipa="/ˈælfə/",
        us_ipa=None,
        pos_data=[_pos_data("noun", [_def("first letter", cefr="A1",
                                           sensenum_local="1")])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["IPA"] == "/ˈælfə/"


def test_resolve_cards_ipa_us_only_uses_single_form():
    """When only US IPA is present, emit /us/."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="alpha",
        badge="A1",
        uk_ipa=None,
        us_ipa="/ˈælfə/",
        pos_data=[_pos_data("noun", [_def("first letter", cefr="A1",
                                           sensenum_local="1")])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["IPA"] == "/ˈælfə/"


def test_resolve_cards_ipa_neither_yields_empty_string():
    """When neither UK nor US IPA is present, the IPA field is ''."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="orphan",
        badge=None,
        uk_ipa=None,
        us_ipa=None,
        pos_data=[_pos_data("noun", [_def("a child", cefr=None, sensenum_local="1")])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["IPA"] == ""


def test_resolve_cards_ipa_handles_already_wrapped_and_unwrapped_inputs():
    """The formatter re-strips slashes before comparing/wrapping. Inputs may
    be bare (e.g. 'eɪbl'), wrapped ('/eɪbl/'), or have stray whitespace —
    all produce a clean '/eɪbl/' output."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="able",
        badge="A2",
        uk_ipa="  /ˈeɪbl/  ",  # whitespace + slashes
        us_ipa="ˈeɪbl",          # bare, no slashes
        pos_data=[_pos_data("adjective", [_def("capable", cefr="A2",
                                               sensenum_local="1")])],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    assert notes[0]["IPA"] == "/ˈeɪbl/"


# =============================================================================
# Cycle 13 — Idiom selection: max two, with conditional CEFR priority
# =============================================================================

def test_resolve_cards_idiom_field_prioritizes_cefr_then_fills_from_null_cefr():
    from src.deck_builder import resolve_cards

    rec = _record(
        word="above",
        pos=("adverb", "preposition"),
        badge=None,
        pos_data=[],
        idioms=[
            {"phrase": "above all", "text": "most importantly",
             "examples": ["Above all, keep in touch."], "cefr": "C1"},
            {"phrase": "above board", "text": "honest and open",
             "examples": ["The deal was above board."], "cefr": None},
            {"phrase": "above the law", "text": "not subject to the law",
             "examples": [], "cefr": None},
        ],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    idioms_field = notes[0]["Idioms"]
    assert "above all" in idioms_field
    assert "above board" in idioms_field
    assert "above the law" not in idioms_field


def test_resolve_cards_idiom_field_keeps_all_when_all_have_cefr():
    """Sanity: when every idiom has a CEFR, all of them are kept."""
    from src.deck_builder import resolve_cards

    rec = _record(
        word="set",
        pos=("verb",),
        badge="A2",
        pos_data=[],
        idioms=[
            {"phrase": "set in", "text": "to begin and seem likely to continue",
             "examples": ["Winter has set in early this year."], "cefr": "B2"},
            {"phrase": "set off", "text": "to start a journey",
             "examples": ["We set off at dawn."], "cefr": "A2"},
        ],
    )

    notes = resolve_cards(rec)

    assert len(notes) == 1
    idioms_field = notes[0]["Idioms"]
    assert "set in" in idioms_field
    assert "set off" in idioms_field
