"""Tests for build layer merge (Phase 7b).

Per Phase 7b grill decisions, merge strategy is pinned:
- word, source, source_url: take first non-null
- source_files: union preserving first-appearance order
- pos: union, sorted by canonical order
- pos_data: concatenate, dedupe by (pos, sensenum_local, text)
- oxford_lists: union
- oxford_badge: first non-null
- audio.uk, audio.us: first non-null
- see_also: union, dedup
- register_tags: union
- verb_forms: first non-null
- idioms: concatenate, dedupe by phrase
"""
from __future__ import annotations

import sys

from pathlib import Path
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, PROJECT_ROOT)

import pytest  # noqa: E402

from src.scraper.merge import merge_word_records  # noqa: E402


def _rec(word, pos, pos_data=None, audio=None, badge=None, homonym_index=None, **kwargs):
    """Build a minimal record for testing."""
    return {
        "word": word,
        "homonym_index": homonym_index,
        "source": "oxford",
        "source_url": None,
        "source_files": [f"oxford_{word}_({pos}).html"],
        "pos": [pos],
        "register_tags": [],
        "oxford_lists": [],
        "oxford_badge": badge,
        "opal": None,
        "awl": None,
        "audio": audio or {"uk": None, "us": None},
        "see_also": [],
        "pos_data": pos_data or [],
        "verb_forms": None,
        "idioms": [],
        **kwargs,
    }


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_single_record_passthrough():
    """1 record → unchanged (just deep copy)."""
    rec = _rec("sick", "adjective", pos_data=[
        {"pos": "adjective", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "ill", "register_tags": [], "cefr": "A1", "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    merged = merge_word_records([rec])
    assert merged is not rec  # new dict object
    assert merged["word"] == "sick"
    assert len(merged["pos_data"]) == 1
    assert merged["pos_data"][0]["definitions"][0]["text"] == "ill"


def test_aggregate_3_records_merge():
    """3 records (adj + verb + noun) → 1 record with 3 pos_data entries."""
    adj = _rec("aggregate", "adjective", pos_data=[
        {"pos": "adjective", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "made up of", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    verb = _rec("aggregate", "verb", pos_data=[
        {"pos": "verb", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "to combine", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    noun = _rec("aggregate", "noun", pos_data=[
        {"pos": "noun", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "a total number", "register_tags": [], "cefr": "C2", "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
            {"n": 2, "sensenum_local": "2", "text": "sand", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ], idioms=[
        {"phrase": "in (the) aggregate", "pos": None, "text": None, "register_tags": [], "cefr": None},
    ])

    merged = merge_word_records([adj, verb, noun])

    assert merged["word"] == "aggregate"
    assert len(merged["pos_data"]) == 3
    pos_list = [pd["pos"] for pd in merged["pos_data"]]
    assert pos_list == ["adjective", "noun", "verb"]  # canonical: adj before noun before verb (Phase 7b spec)
    assert merged["source_files"] == [
        "oxford_aggregate_(adjective).html",
        "oxford_aggregate_(verb).html",
        "oxford_aggregate_(noun).html",
    ]
    # Nouns should have 2 defs
    noun_pd = next(pd for pd in merged["pos_data"] if pd["pos"] == "noun")
    assert len(noun_pd["definitions"]) == 2
    # Idiom preserved
    assert len(merged["idioms"]) == 1


def test_audio_first_non_null():
    """audio.uk from file 1, audio.us from file 2 → both present in merged."""
    r1 = _rec("off", "noun", audio={"uk": "https://uk_pron/off_1.mp3", "us": None})
    r2 = _rec("off", "verb", audio={"uk": None, "us": "https://us_pron/off_2.mp3"})

    merged = merge_word_records([r1, r2])

    assert merged["audio"]["uk"] == "https://uk_pron/off_1.mp3"
    assert merged["audio"]["us"] == "https://us_pron/off_2.mp3"


def test_idioms_dedup_by_phrase():
    """Same idiom phrase in 2 files → 1 entry in merged."""
    r1 = _rec("like", "verb", idioms=[
        {"phrase": "be like", "pos": None, "text": None, "register_tags": [], "cefr": None},
    ])
    r2 = _rec("like", "noun", idioms=[
        {"phrase": "be like", "pos": None, "text": None, "register_tags": [], "cefr": None},
        {"phrase": "more like it", "pos": None, "text": None, "register_tags": [], "cefr": None},
    ])

    merged = merge_word_records([r1, r2])

    phrases = [i["phrase"] for i in merged["idioms"]]
    assert "be like" in phrases
    assert "more like it" in phrases
    assert phrases.count("be like") == 1  # deduped


def test_up_noun_edge_preserved():
    """up_(noun) has pos_data=[] but idioms=3 → preserved as-is."""
    r1 = _rec("up", "noun", pos_data=[], idioms=[
        {"phrase": "ups and downs", "pos": None, "text": None, "register_tags": [], "cefr": None},
        {"phrase": "what's up", "pos": None, "text": None, "register_tags": [], "cefr": None},
        {"phrase": "be up to", "pos": None, "text": None, "register_tags": [], "cefr": None},
    ])

    merged = merge_word_records([r1])
    assert len(merged["pos_data"]) == 0
    assert len(merged["idioms"]) == 3


def test_oxford_badge_first_non_null():
    """oxford_badge: first non-null wins (per Q6: badge is display metadata)."""
    r1 = _rec("acid", "adjective", badge="C1")
    r2 = _rec("acid", "noun", badge="B2")

    merged = merge_word_records([r1, r2])
    assert merged["oxford_badge"] == "C1"  # first record's badge


def test_verb_forms_first_non_null():
    """verb_forms: only 1 file has it; first non-null wins."""
    r1 = _rec("go", "verb", verb_forms=None)
    r2 = _rec("go", "noun", verb_forms={"root": "went", "past": "went", "pastpart": "gone", "thirdps": "goes", "prespart": "going"})

    merged = merge_word_records([r1, r2])
    assert merged["verb_forms"] == {"root": "went", "past": "went", "pastpart": "gone", "thirdps": "goes", "prespart": "going"}


def test_pos_data_dedup_across_records():
    """If 2 records have identical def (pos, sensenum_local, text), keep 1."""
    r1 = _rec("test", "noun", pos_data=[
        {"pos": "noun", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "duplicate", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    r2 = _rec("test", "verb", pos_data=[
        {"pos": "noun", "register_tags": [], "definitions": [  # same pos, same text
            {"n": 1, "sensenum_local": "1", "text": "duplicate", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])

    merged = merge_word_records([r1, r2])
    # Even though both records have same pos, dedupe by (pos, sensenum, text) → 1 def
    all_defs = [d for pd in merged["pos_data"] for d in pd["definitions"]]
    assert len(all_defs) == 1


def test_empty_records_raises():
    """0 records should raise (not silently produce empty dict)."""
    with pytest.raises(ValueError):
        merge_word_records([])


# -----------------------------------------------------------------------------
# _skip flag (build-layer redirect detection)
# -----------------------------------------------------------------------------

def test_skip_flag_set_when_both_empty():
    """When pos_data=[] AND idioms=[], record gets _skip=True with reason.

    This is the phrasal-verb-redirect case (e.g. 'deprive' page that just
    links to 'deprive of' without any definitions of its own).
    """
    rec = _rec("deprive", "verb", pos_data=[], idioms=[])
    merged = merge_word_records([rec])
    assert merged["_skip"] is True
    assert "phrasal-verb-redirect" in merged["_skip_reason"]


def test_skip_flag_false_when_pos_data_present():
    """When pos_data is non-empty, _skip=False (no reason)."""
    rec = _rec("sick", "adjective", pos_data=[
        {"pos": "adjective", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "ill", "register_tags": [], "cefr": "A1", "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    merged = merge_word_records([rec])
    assert merged["_skip"] is False
    assert "_skip_reason" not in merged


def test_skip_flag_false_when_only_idioms():
    """When pos_data=[] but idioms>0, _skip=False (idiom-only is valid)."""
    rec = _rec("accordance", "noun", pos_data=[], idioms=[
        {"phrase": "in accordance with", "pos": None, "text": None, "register_tags": [], "cefr": None},
    ])
    merged = merge_word_records([rec])
    assert merged["_skip"] is False
    assert len(merged["idioms"]) == 1


def test_skip_flag_set_when_merged_yields_empty():
    """When 2 records merge to empty pos_data + empty idioms, _skip=True.

    This shouldn't happen in practice (records with content wouldn't merge
    to empty), but the flag logic must handle the edge case correctly.
    """
    r1 = _rec("foo", "verb", pos_data=[], idioms=[])
    r2 = _rec("foo", "noun", pos_data=[], idioms=[])
    merged = merge_word_records([r1, r2])
    assert merged["_skip"] is True


# -----------------------------------------------------------------------------
# Homonym handling (Phase 7b+ fix)
# -----------------------------------------------------------------------------
# bass1 = the fish / low-frequency voice (homonym_index=1)
# bass2 = the music note (homonym_index=2)
# These are distinct words with different etymologies; merge step must
# group by (word, homonym_index), not just by word.

def test_homonym_distinct_bass1_bass2_separate():
    """bass1 and bass2 are passed in separately to merge_word_records.

    The merge function itself doesn't group — the runner does. So this test
    verifies that each call returns a record with its own homonym_index,
    and that they're treated as independent when grouped by (word, h).
    """
    bass1 = _rec("bass", "noun", homonym_index=1, pos_data=[
        {"pos": "noun", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "the lowest male singing voice", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    bass2 = _rec("bass", "noun", homonym_index=2, pos_data=[
        {"pos": "noun", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "a type of fish", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])

    m1 = merge_word_records([bass1])
    m2 = merge_word_records([bass2])
    assert m1["homonym_index"] == 1
    assert m2["homonym_index"] == 2
    # Word field has the digit stripped (the parser strips it before merge)
    # but in this test we manually pass "bass" (digit already stripped).
    assert m1["word"] == "bass"
    assert m2["word"] == "bass"


def test_homonym_same_index_merges():
    """Two records with same (word, homonym_index) merge into 1."""
    r1 = _rec("bass", "noun", homonym_index=1, pos_data=[
        {"pos": "noun", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "fish def", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    r2 = _rec("bass", "verb", homonym_index=1, pos_data=[
        {"pos": "verb", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "verb def", "register_tags": [], "cefr": None, "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    merged = merge_word_records([r1, r2])
    assert merged["homonym_index"] == 1
    assert len(merged["pos_data"]) == 2


def test_homonym_null_index_works():
    """Regular non-homonym word (homonym_index=None) merges normally."""
    sick = _rec("sick", "adjective", pos_data=[
        {"pos": "adjective", "register_tags": [], "definitions": [
            {"n": 1, "sensenum_local": "1", "text": "ill", "register_tags": [], "cefr": "A1", "topics": [], "collocations": {}, "examples": [], "is_phrase": False, "is_idiom": False},
        ]},
    ])
    merged = merge_word_records([sick])
    assert merged["homonym_index"] is None


def test_homonym_index_first_non_null():
    """When merging records, homonym_index comes from first non-null."""
    r1 = _rec("bow", "noun", homonym_index=None, pos_data=[])
    r2 = _rec("bow", "noun", homonym_index=2, pos_data=[])
    merged = merge_word_records([r1, r2])
    assert merged["homonym_index"] == 2


# -----------------------------------------------------------------------------
# Proper-noun-or-cultural-entry skip rule (Issue C)
# -----------------------------------------------------------------------------
from src.scraper.merge import fold_phrasal_verb_records, _apply_skip_flags  # noqa: E402


def _def(cefr=None, text="x"):
    return {
        "n": 1, "sensenum_local": "1", "text": text, "register_tags": [],
        "cefr": cefr, "topics": [], "collocations": {}, "examples": [],
        "is_phrase": False, "is_idiom": False,
    }


def test_proper_noun_skip_all_conditions_met():
    """All 4 conditions met → _skip=true with proper-noun reason."""
    rec = {
        "word": "Buck Rogers", "homonym_index": None, "source": "oxford",
        "source_url": None, "source_files": ["oxford_buck-rogers.html"],
        "pos": ["unknown"],
        "register_tags": [], "oxford_lists": [],
        "oxford_badge": None, "opal": None, "awl": None,
        "audio": {"uk": None, "us": None}, "see_also": [],
        "pos_data": [{"pos": "unknown", "register_tags": [], "definitions": [_def()]}],
        "verb_forms": None, "idioms": [],
    }
    _apply_skip_flags(rec)
    assert rec["_skip"] is True
    assert "proper-noun" in rec["_skip_reason"]


def test_proper_noun_skip_kept_when_has_badge():
    """Has oxford_badge → kept (B1 person names exist in OALD 3000)."""
    rec = {
        "word": "Test", "homonym_index": None, "source": "oxford",
        "source_url": None, "source_files": ["oxford_test.html"],
        "pos": ["unknown"],
        "register_tags": [], "oxford_lists": [],
        "oxford_badge": "B2",  # ← has curriculum signal
        "opal": None, "awl": None,
        "audio": {"uk": None, "us": None}, "see_also": [],
        "pos_data": [{"pos": "unknown", "register_tags": [], "definitions": [_def()]}],
        "verb_forms": None, "idioms": [],
    }
    _apply_skip_flags(rec)
    assert rec["_skip"] is False


def test_proper_noun_skip_kept_when_in_oxford_list():
    """In Oxford 3000 → kept."""
    rec = {
        "word": "Test", "homonym_index": None, "source": "oxford",
        "source_url": None, "source_files": ["oxford_test.html"],
        "pos": ["unknown"],
        "register_tags": [], "oxford_lists": ["Oxford 3000"],  # ← signal
        "oxford_badge": None, "opal": None, "awl": None,
        "audio": {"uk": None, "us": None}, "see_also": [],
        "pos_data": [{"pos": "unknown", "register_tags": [], "definitions": [_def()]}],
        "verb_forms": None, "idioms": [],
    }
    _apply_skip_flags(rec)
    assert rec["_skip"] is False


def test_proper_noun_skip_kept_when_has_def_cefr():
    """At least 1 def has cefr → kept."""
    rec = {
        "word": "Habitat", "homonym_index": None, "source": "oxford",
        "source_url": None, "source_files": ["oxford_habitat.html"],
        "pos": ["unknown"],
        "register_tags": [], "oxford_lists": [],
        "oxford_badge": None, "opal": None, "awl": None,
        "audio": {"uk": None, "us": None}, "see_also": [],
        "pos_data": [
            {"pos": "unknown", "register_tags": [], "definitions": [_def()]},
            {"pos": "noun", "register_tags": [], "definitions": [_def(cefr="B1", text="natural environment")]},  # ← has CEFR
        ],
        "verb_forms": None, "idioms": [],
    }
    _apply_skip_flags(rec)
    assert rec["_skip"] is False


def test_proper_noun_skip_kept_when_mixed_pos():
    """pos_data has both 'unknown' and a real POS → kept (not all pos=unknown)."""
    rec = {
        "word": "Test", "homonym_index": None, "source": "oxford",
        "source_url": None, "source_files": ["oxford_test.html"],
        "pos": ["unknown", "noun"],
        "register_tags": [], "oxford_lists": [],
        "oxford_badge": None, "opal": None, "awl": None,
        "audio": {"uk": None, "us": None}, "see_also": [],
        "pos_data": [
            {"pos": "unknown", "register_tags": [], "definitions": [_def()]},
            {"pos": "noun", "register_tags": [], "definitions": [_def()]},  # ← has real POS
        ],
        "verb_forms": None, "idioms": [],
    }
    _apply_skip_flags(rec)
    assert rec["_skip"] is False


def test_proper_noun_skip_does_not_fire_on_idiom_only():
    """Idiom-only record (pos_data=[], idioms>0) should NOT trigger proper-noun rule
    (the phrasal-verb-redirect rule has priority, but here idioms are present
    so neither rule fires → not skipped)."""
    rec = {
        "word": "accordance", "homonym_index": None, "source": "oxford",
        "source_url": None, "source_files": ["oxford_accordance.html"],
        "pos": ["noun"],
        "register_tags": [], "oxford_lists": [],
        "oxford_badge": None, "opal": None, "awl": None,
        "audio": {"uk": None, "us": None}, "see_also": [],
        "pos_data": [],  # ← empty
        "verb_forms": None,
        "idioms": [{"phrase": "in accordance with", "pos": None, "text": None, "register_tags": [], "cefr": "B2"}],
    }
    _apply_skip_flags(rec)
    assert rec["_skip"] is False  # idioms present, no rule fires


# -----------------------------------------------------------------------------
# Phrasal Verb Folding (Issue A, option β)
# -----------------------------------------------------------------------------

def _pv_rec(word, base_pos_data, source_file):
    """Build a phrasal-verb record."""
    return {
        "word": word, "homonym_index": None, "source": "oxford",
        "source_url": None, "source_files": [source_file],
        "pos": ["phrasal verb"],
        "register_tags": [], "oxford_lists": [],
        "oxford_badge": None, "opal": None, "awl": None,
        "audio": {"uk": None, "us": None}, "see_also": [],
        "pos_data": [{"pos": "phrasal verb", "register_tags": [], "definitions": base_pos_data}],
        "verb_forms": None, "idioms": [],
    }


def _main_rec(word, source_file, pos_data, badge=None):
    """Build a main-word record (the phrasal-verb-redirect stub normally)."""
    return {
        "word": word, "homonym_index": None, "source": "oxford",
        "source_url": None, "source_files": [source_file],
        "pos": ["verb"],
        "register_tags": [], "oxford_lists": [],
        "oxford_badge": badge, "opal": None, "awl": None,
        "audio": {"uk": None, "us": None}, "see_also": [],
        "pos_data": pos_data,
        "verb_forms": None, "idioms": [],
    }


def test_fold_phrasal_verb_basic():
    """Phrasal-verb record folds into main-word; main gets 'phrasal verb' pos_data."""
    main = _main_rec("deprive", "oxford_deprive.html", pos_data=[])  # stub
    pv = _pv_rec("deprive of", [_def(text="to prevent somebody from having")],
                 "oxford_deprive-of_(phrasal_verb).html")

    out = fold_phrasal_verb_records([main, pv])

    # Find the main record (it's a copy now, not the same object)
    main_out = [r for r in out if r["word"] == "deprive"][0]
    pv_out = [r for r in out if r["word"] == "deprive of"][0]

    # Main gets the phrasal-verb's pos_data
    assert len(main_out["pos_data"]) == 1
    assert main_out["pos_data"][0]["pos"] == "phrasal verb"
    assert main_out["pos_data"][0]["definitions"][0]["text"] == "to prevent somebody from having"
    # pos top-level includes "phrasal verb"
    assert "phrasal verb" in main_out["pos"]
    # source_files unions in
    assert "oxford_deprive-of_(phrasal_verb).html" in main_out["source_files"]
    assert "oxford_deprive.html" in main_out["source_files"]

    # PV record is flagged for skip
    assert pv_out["_skip"] is True
    assert pv_out["_skip_reason"] == "folded-into-main-word: deprive"


def test_fold_phrasal_verb_preserves_existing_main_pos_data():
    """Main word with its own pos_data (e.g. deprive has 1 verb def elsewhere)
    keeps its pos_data and APPENDS the folded phrasal-verb entry."""
    main = _main_rec("deprive", "oxford_deprive.html", pos_data=[
        {"pos": "verb", "register_tags": [], "definitions": [_def(text="main verb def")]},
    ])
    pv = _pv_rec("deprive of", [_def(text="phrasal def")], "oxford_deprive-of_(phrasal_verb).html")

    out = fold_phrasal_verb_records([main, pv])
    main_out = [r for r in out if r["word"] == "deprive"][0]

    assert len(main_out["pos_data"]) == 2
    pos_list = [pd["pos"] for pd in main_out["pos_data"]]
    assert "verb" in pos_list
    assert "phrasal verb" in pos_list


def test_fold_phrasal_verb_no_main_record_leaves_pv_alone():
    """If no main-word record exists, the phrasal-verb record is left untouched
    (not flagged _skip=true). Defensive: this shouldn't happen in practice."""
    pv = _pv_rec("orphan of", [_def(text="some def")], "oxford_orphan-of_(phrasal_verb).html")

    out = fold_phrasal_verb_records([pv])
    pv_out = out[0]
    assert pv_out.get("_skip") is not True
    assert "_skip_reason" not in pv_out or not pv_out["_skip_reason"].startswith("folded-into-main-word")


def test_fold_phrasal_verb_does_not_affect_non_phrasal_records():
    """Records that aren't phrasal verbs (e.g. sick, sickly) pass through unchanged."""
    sick = _main_rec("sick", "oxford_sick.html", pos_data=[
        {"pos": "adjective", "register_tags": [], "definitions": [_def(cefr="A1", text="ill")]},
    ])
    out = fold_phrasal_verb_records([sick])
    assert len(out) == 1
    assert out[0]["word"] == "sick"
    assert out[0].get("_skip") is not True
    # The pos array is unchanged
    assert out[0]["pos"] == ["verb"]


def test_fold_phrasal_verb_idempotent():
    """Running fold twice produces the same result (no double-folding)."""
    main = _main_rec("deprive", "oxford_deprive.html", pos_data=[])
    pv = _pv_rec("deprive of", [_def(text="phrasal def")], "oxford_deprive-of_(phrasal_verb).html")

    out1 = fold_phrasal_verb_records([main, pv])
    out2 = fold_phrasal_verb_records(out1)

    # Same final state — no extra pos_data entries
    main1 = [r for r in out1 if r["word"] == "deprive"][0]
    main2 = [r for r in out2 if r["word"] == "deprive"][0]
    assert len(main1["pos_data"]) == len(main2["pos_data"]) == 1


def test_fold_phrasal_verb_handles_3_particle():
    """Phrasal verb with 3-word particle (e.g. 'look forward to') folds correctly.
    Base word is the FIRST whitespace-separated token."""
    pv = _pv_rec("look forward to", [_def(text="to anticipate")], "oxford_look-forward-to_(phrasal_verb).html")
    main = _main_rec("look", "oxford_look.html", pos_data=[])

    out = fold_phrasal_verb_records([main, pv])
    main_out = [r for r in out if r["word"] == "look"][0]
    assert len(main_out["pos_data"]) == 1
    assert main_out["pos_data"][0]["pos"] == "phrasal verb"
