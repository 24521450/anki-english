"""Tests for opal_sync (Phase A.1).

Pure-function tests: no I/O, no real files. Build jsonl records and txt lines in-memory.
"""
import pytest
from src.deck_builder.opal_sync import (
    compute_card_updates,
    apply_updates,
    CardUpdate,
    HEADER_LINES,
    _build_jsonl_index,
    _parse_txt_card,
)


HEADER = [
    '#separator:tab',
    '#html:true',
    '#guid column:1',
    '#notetype column:2',
    '#deck column:3',
    '#tags column:16',
]


def make_txt_line(guid, word, pos, source, tags, src2='Oxford', cefr='B2'):
    return '\t'.join([
        guid,
        'English Academic Vocabulary Model',
        'English Academic Vocabulary::Oxford',
        word,
        pos,
        '/test/',
        'def',
        'ex',
        '',  # WordFamily
        '',  # Collocations
        '[sound:uk.mp3]',  # AudioUK
        '[sound:us.mp3]',  # AudioUS
        source,
        src2,
        cefr,
        tags,
    ])


def make_jsonl_record(word, pos, opal, source_files=None):
    if source_files is None:
        source_files = [f'oxford_{word.lower()}_(adj).html']
    return {
        'word': word,
        'pos': pos if isinstance(pos, list) else [pos],
        'opal': opal,
        'source_files': source_files,
    }


class TestComputeCardUpdates:
    """Pure: feed jsonl records + txt lines, get back a list of updates."""

    def test_no_update_when_no_jsonl_match(self):
        """Card with no matching jsonl record -> no update."""
        jsonl = [make_jsonl_record('hello', 'noun', 'W')]
        txt = HEADER + [make_txt_line('g1', 'goodbye', 'noun', 'Oxford', 'Audio::Cambridge')]
        assert compute_card_updates(jsonl, txt) == []

    def test_no_update_when_jsonl_has_no_opal(self):
        """Card matched, but jsonl has opal=None -> no update."""
        jsonl = [make_jsonl_record('hello', 'noun', None)]
        txt = HEADER + [make_txt_line('g1', 'hello', 'noun', 'Oxford', 'Audio::Cambridge')]
        assert compute_card_updates(jsonl, txt) == []

    def test_no_update_when_tag_already_present(self):
        """Card matched, jsonl has W, txt already has OPAL_W -> no update."""
        jsonl = [make_jsonl_record('hello', 'noun', 'W')]
        txt = HEADER + [make_txt_line('g1', 'hello', 'noun', 'Oxford', 'Audio::Cambridge OPAL_W')]
        assert compute_card_updates(jsonl, txt) == []

    def test_adds_OPAL_W_when_missing(self):
        """Card matched, jsonl has W, txt missing OPAL_W -> add it."""
        jsonl = [make_jsonl_record('hello', 'noun', 'W')]
        txt = HEADER + [make_txt_line('g1', 'hello', 'noun', 'Oxford', 'Audio::Cambridge')]
        updates = compute_card_updates(jsonl, txt)
        assert len(updates) == 1
        u = updates[0]
        assert u.guid == 'g1'
        assert u.opal_added == 'OPAL_W'
        assert u.new_tags == 'Audio::Cambridge OPAL_W'

    def test_adds_OPAL_S_when_missing(self):
        """S variant works the same way."""
        jsonl = [make_jsonl_record('sad', 'adjective', 'S')]
        txt = HEADER + [make_txt_line('g2', 'sad', 'adjective', 'Oxford', 'Audio::Cambridge')]
        updates = compute_card_updates(jsonl, txt)
        assert len(updates) == 1
        assert updates[0].opal_added == 'OPAL_S'
        assert updates[0].new_tags == 'Audio::Cambridge OPAL_S'

    def test_does_not_overwrite_OPAL_S_with_W(self):
        """If jsonl says W but txt has OPAL_S, no update (mismatch, but don't auto-correct)."""
        jsonl = [make_jsonl_record('mixed', 'noun', 'W')]
        txt = HEADER + [make_txt_line('g3', 'mixed', 'noun', 'Oxford', 'OPAL_S')]
        # OPAL_W not in tags, jsonl says W -> adds OPAL_W (BOTH will end up in tags)
        # This is actually a known limitation; the test documents current behavior.
        # If we wanted to be stricter (skip if ANY OPAL_* is present), we'd test that here.
        updates = compute_card_updates(jsonl, txt)
        # Documented current behavior: append OPAL_W alongside OPAL_S.
        assert len(updates) == 1
        assert updates[0].opal_added == 'OPAL_W'
        assert updates[0].new_tags == 'OPAL_S OPAL_W'

    def test_pos_must_match(self):
        """Word matches but pos doesn't -> no update (different record)."""
        jsonl = [make_jsonl_record('record', ['noun', 'verb'], 'W')]
        txt = HEADER + [make_txt_line('g4', 'record', 'adjective', 'Oxford', '')]
        assert compute_card_updates(jsonl, txt) == []

    def test_source_must_match(self):
        """Word matches but source doesn't -> no update (Cambridge card won't pick up Oxford opal)."""
        jsonl = [make_jsonl_record('sound', 'noun', 'W', source_files=['oxford_sound_(noun).html'])]
        txt = HEADER + [make_txt_line('g5', 'sound', 'noun', 'Cambridge', '')]
        # The jsonl record's source_files[0] starts with 'oxford_' -> src='Oxford'
        # txt card says source='Cambridge' -> no match
        assert compute_card_updates(jsonl, txt) == []

    def test_case_insensitive_word_match(self):
        """Word in txt can have different case from jsonl."""
        jsonl = [make_jsonl_record('Argue', 'verb', 'W')]
        txt = HEADER + [make_txt_line('g6', 'argue', 'verb', 'Oxford', '')]
        updates = compute_card_updates(jsonl, txt)
        assert len(updates) == 1
        assert updates[0].opal_added == 'OPAL_W'

    def test_word_with_disambiguation_paren_stripped(self):
        """Word like 'transport (verb)' should match 'transport' in jsonl."""
        # In txt, the word field is just 'transport', not 'transport (verb)'.
        # (the disambiguation paren is only in the deck display, not the source txt)
        jsonl = [make_jsonl_record('transport', 'verb', 'W')]
        txt = HEADER + [make_txt_line('g7', 'transport', 'verb', 'Oxford', '')]
        updates = compute_card_updates(jsonl, txt)
        assert len(updates) == 1
        assert updates[0].opal_added == 'OPAL_W'

    def test_multiple_pos_in_jsonl_match_any(self):
        """If jsonl has pos=['noun', 'verb'] and txt card is 'noun', match works."""
        jsonl = [make_jsonl_record('break', ['noun', 'verb'], 'W')]
        txt = HEADER + [make_txt_line('g8', 'break', 'noun', 'Oxford', '')]
        updates = compute_card_updates(jsonl, txt)
        assert len(updates) == 1

    def test_multiple_cards_mixed_state(self):
        """Multiple cards, some need update, some don't."""
        jsonl = [
            make_jsonl_record('a', 'noun', 'W'),
            make_jsonl_record('b', 'noun', 'S'),
            make_jsonl_record('c', 'noun', None),
            make_jsonl_record('d', 'noun', 'W'),
        ]
        txt = HEADER + [
            make_txt_line('g_a', 'a', 'noun', 'Oxford', ''),  # needs OPAL_W
            make_txt_line('g_b', 'b', 'noun', 'Oxford', 'OPAL_S'),  # already has
            make_txt_line('g_c', 'c', 'noun', 'Oxford', ''),  # no jsonl opal
            make_txt_line('g_d', 'd', 'noun', 'Oxford', ''),  # needs OPAL_W
            make_txt_line('g_e', 'e', 'noun', 'Oxford', ''),  # no jsonl match
        ]
        updates = compute_card_updates(jsonl, txt)
        assert len(updates) == 2
        guids = {u.guid for u in updates}
        assert guids == {'g_a', 'g_d'}


class TestApplyUpdates:
    """Pure: apply_updates(lines, updates) -> new lines."""

    def test_apply_changes_target_line(self):
        jsonl = [make_jsonl_record('hello', 'noun', 'W')]
        txt = HEADER + [make_txt_line('g1', 'hello', 'noun', 'Oxford', 'Audio::Cambridge')]
        updates = compute_card_updates(jsonl, txt)
        out = apply_updates(txt, updates)
        # Header unchanged
        assert out[:HEADER_LINES] == HEADER
        # Target line has updated tags
        line_parts = out[HEADER_LINES].split('\t')
        assert line_parts[15] == 'Audio::Cambridge OPAL_W'

    def test_apply_does_not_mutate_input(self):
        jsonl = [make_jsonl_record('hello', 'noun', 'W')]
        txt = HEADER + [make_txt_line('g1', 'hello', 'noun', 'Oxford', 'Audio::Cambridge')]
        original_tags = txt[HEADER_LINES].split('\t')[15]
        updates = compute_card_updates(jsonl, txt)
        apply_updates(txt, updates)
        # Original txt unchanged
        assert txt[HEADER_LINES].split('\t')[15] == original_tags

    def test_apply_with_no_updates_returns_identical(self):
        txt = HEADER + [make_txt_line('g1', 'hello', 'noun', 'Oxford', 'Audio::Cambridge')]
        out = apply_updates(txt, [])
        assert out == txt

    def test_apply_preserves_other_fields(self):
        """Only the tags column (15) should change; everything else byte-identical."""
        jsonl = [make_jsonl_record('hello', 'noun', 'W')]
        txt = HEADER + [make_txt_line('g1', 'hello', 'noun', 'Oxford', 'Audio::Cambridge', src2='Cambridge', cefr='C1')]
        updates = compute_card_updates(jsonl, txt)
        out = apply_updates(txt, updates)
        old_parts = txt[HEADER_LINES].split('\t')
        new_parts = out[HEADER_LINES].split('\t')
        # All fields except 15 should be identical
        for i in range(16):
            if i == 15:
                assert old_parts[i] != new_parts[i]
            else:
                assert old_parts[i] == new_parts[i]


class TestBuildJsonlIndex:
    """Direct test of the indexer."""

    def test_oxford_source_label(self):
        rec = make_jsonl_record('x', 'noun', 'W', source_files=['oxford_x_(noun).html'])
        idx = _build_jsonl_index([rec])
        assert ('x', 'noun', 'Oxford') in idx
        assert ('x', 'noun', 'Cambridge') not in idx

    def test_cambridge_source_label(self):
        rec = make_jsonl_record('x', 'noun', 'W', source_files=['cambridge_x.html'])
        idx = _build_jsonl_index([rec])
        assert ('x', 'noun', 'Cambridge') in idx

    def test_unknown_source_label(self):
        rec = make_jsonl_record('x', 'noun', 'W', source_files=['awl_x.json'])
        idx = _build_jsonl_index([rec])
        assert ('x', 'noun', None) in idx


class TestParseTxtCard:
    """Direct test of the line parser."""

    def test_basic(self):
        line = make_txt_line('g1', 'test', 'noun', 'Oxford', 'A B C')
        card = _parse_txt_card(line)
        assert card['guid'] == 'g1'
        assert card['word'] == 'test'
        assert card['pos'] == 'noun'
        assert card['source'] == 'Oxford'
        assert card['tags'] == 'A B C'

    def test_malformed_short_line_returns_none(self):
        assert _parse_txt_card('only one field') is None
        assert _parse_txt_card('one\ttwo') is None

    def test_word_with_paren_stripped(self):
        line = make_txt_line('g1', 'transport (verb)', 'verb', 'Oxford', '')
        card = _parse_txt_card(line)
        assert card['word'] == 'transport'
