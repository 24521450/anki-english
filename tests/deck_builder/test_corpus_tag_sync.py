"""Tests for corpus_tag_sync (v2: vocab_list source of truth)."""
import pytest
from pathlib import Path
from src.deck_builder.corpus_tag_sync import (
    compute_tag_updates,
    apply_updates,
    HEADER_LINES,
    TOKEN_3000,
    TOKEN_5000,
    _parse_vocab_list,
    _parse_deck_pos,
    _parse_txt_card,
    _card_should_have_corpus_tag,
    OXFORD_3000,
    OXFORD_5000,
)

HEADER = [
    '#separator:tab',
    '#html:true',
    '#guid column:1',
    '#notetype column:2',
    '#deck column:3',
    '#tags column:16',
]


def make_txt_line(guid, word, pos, source, tags, cefr='B2'):
    return '\t'.join([
        guid, 'English Academic Vocabulary Model', 'English Academic Vocabulary::Oxford',
        word, pos, '/test/', 'def', 'ex', '', '',
        '[sound:uk.mp3]', '[sound:us.mp3]',
        source, 'Oxford', cefr, tags,
    ])


# Real vocab_list subsets for tests
VOCAB_3000 = {
    ('hello', 'noun', 'A1'),
    ('arm', 'noun', 'A1'),
    ('arm', 'verb', 'B1'),
    ('say', 'verb', 'A1'),
    ('about', 'preposition', 'A1'),
    ('about', 'adverb', 'A1'),
}
VOCAB_5000 = {
    ('arm', 'verb', 'C1'),
    ('about', 'adverb', 'B1'),
    ('say', 'noun', 'B1'),
    ('testword', 'noun', 'B2'),
    ('striking', 'adjective', 'C1'),
}


class TestParseVocabList:
    """Verify the vocab_list parser handles real file format."""

    def test_parses_3000_real(self):
        path = Path(r'C:\Users\admin\Downloads\ankideck\vocab_list\Oxford\Oxford_3000.md')
        if not path.exists():
            pytest.skip("vocab_list not available")
        result = _parse_vocab_list(path)
        # arm (noun) A1 should be in there
        assert ('arm', 'noun', 'A1') in result
        # POS normalized: 'n.' -> 'noun'
        assert ('ability', 'noun', 'A2') in result
        # Multi-POS: 'about' should appear twice
        assert ('about', 'preposition', 'A1') in result
        assert ('about', 'adverb', 'A1') in result

    def test_parses_5000_real(self):
        path = Path(r'C:\Users\admin\Downloads\ankideck\vocab_list\Oxford\Oxford_5000.md')
        if not path.exists():
            pytest.skip("vocab_list not available")
        result = _parse_vocab_list(path)
        # arm (verb) C1 in 5000
        assert ('arm', 'verb', 'C1') in result


class TestCardShouldHaveCorpusTag:
    """Pure: card dict + vocab_set + cefr -> bool."""

    def test_exact_match_3000(self):
        card = {'word': 'arm', 'pos_list': ['noun']}
        assert _card_should_have_corpus_tag(card, VOCAB_3000, 'A1')

    def test_cefr_mismatch_3000(self):
        """arm (noun) is in 3000 at A1 only. At C1 it's NOT in 3000."""
        card = {'word': 'arm', 'pos_list': ['noun']}
        assert not _card_should_have_corpus_tag(card, VOCAB_3000, 'C1')

    def test_arm_verb_only_5000_at_C1(self):
        """The user's case: arm (verb) C1 is on 5000 only, not 3000."""
        card = {'word': 'arm', 'pos_list': ['verb']}
        assert not _card_should_have_corpus_tag(card, VOCAB_3000, 'C1')
        assert _card_should_have_corpus_tag(card, VOCAB_5000, 'C1')

    def test_arm_verb_in_3000_at_B1(self):
        """arm (verb) is on 3000 at B1 (not C1)."""
        card = {'word': 'arm', 'pos_list': ['verb']}
        assert _card_should_have_corpus_tag(card, VOCAB_3000, 'B1')

    def test_multi_pos_card_match_any(self):
        """Multi-POS card: if any pos matches vocab at this CEFR, True."""
        card = {'word': 'about', 'pos_list': ['preposition', 'adverb']}
        # both preposition and adverb are in 3000 at A1
        assert _card_should_have_corpus_tag(card, VOCAB_3000, 'A1')
        # adverb is in 5000 at B1
        assert _card_should_have_corpus_tag(card, VOCAB_5000, 'B1')


class TestComputeTagUpdates:
    """Pure: feed txt + vocab, get TagUpdate list."""

    def test_arm_verb_C1_should_only_have_5000(self):
        """User's exact case: arm (verb) C1 -> only Oxford_5000."""
        txt = HEADER + [
            make_txt_line('g1', 'arm', 'verb', 'Oxford', f'Audio::Cambridge {TOKEN_3000} {TOKEN_5000}', cefr='C1'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert len(updates) == 1
        # 3000 should be removed
        assert TOKEN_3000 in updates[0].removed
        # 5000 should stay (no remove, no add)
        assert updates[0].added == []
        assert updates[0].removed == [TOKEN_3000]

    def test_arm_noun_A1_should_have_3000_only(self):
        """arm (noun) A1 -> only Oxford_3000."""
        txt = HEADER + [
            make_txt_line('g1', 'arm', 'noun', 'Oxford', f'Audio::Cambridge {TOKEN_5000}', cefr='A1'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert len(updates) == 1
        assert TOKEN_5000 in updates[0].removed
        assert TOKEN_3000 in updates[0].added

    def test_no_change_when_correct(self):
        """arm (noun) A1 with 3000 already tagged -> no change."""
        txt = HEADER + [
            make_txt_line('g1', 'arm', 'noun', 'Oxford', f'Audio::Cambridge {TOKEN_3000}', cefr='A1'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert updates == []

    def test_skips_card_without_corpus_tag(self):
        """Card with no corpus tag is left alone."""
        txt = HEADER + [
            make_txt_line('g1', 'random', 'noun', 'Oxford', 'Audio::Cambridge CEFR::B2', cefr='B2'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert updates == []

    def test_multi_pos_card_with_one_pos_in_vocab(self):
        """Card with 2 POS, only 1 in vocab at this CEFR -> card still tagged."""
        # about (preposition, adverb) at A1 — both in 3000
        txt = HEADER + [
            make_txt_line('g1', 'about', 'preposition, adverb', 'Oxford', f'Audio::Cambridge {TOKEN_3000}', cefr='A1'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert updates == []  # already correct

    def test_about_5000_at_B1_only(self):
        """about (preposition, adverb) at B1: 5000 has adverb at B1, 3000 has both at A1 only.
        So 5000 should be present, 3000 should NOT (because B1 != A1).
        """
        txt = HEADER + [
            make_txt_line('g1', 'about', 'preposition, adverb', 'Oxford', f'Audio::Cambridge {TOKEN_3000}', cefr='B1'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert len(updates) == 1
        assert TOKEN_3000 in updates[0].removed
        assert TOKEN_5000 in updates[0].added

    def test_word_not_in_vocab_at_all(self):
        """Card tagged 5000 but word not in 5000 at card's CEFR -> 5000 removed."""
        txt = HEADER + [
            make_txt_line('g1', 'testword', 'noun', 'Oxford', f'Audio::Cambridge {TOKEN_5000}', cefr='A1'),
        ]
        # testword is in VOCAB_5000 at B2, not A1
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert len(updates) == 1
        assert TOKEN_5000 in updates[0].removed

    def test_unclassified_cefr(self):
        """CEFR=UNCLASSIFIED: vocab_list has no UNCLASSIFIED entry -> both tags removed."""
        txt = HEADER + [
            make_txt_line('g1', 'arm', 'noun', 'Oxford', f'Audio::Cambridge {TOKEN_3000} {TOKEN_5000}', cefr='UNCLASSIFIED'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        # Both should be removed (UNCLASSIFIED is not in vocab)
        assert len(updates) == 1
        assert TOKEN_3000 in updates[0].removed
        assert TOKEN_5000 in updates[0].removed

    def test_striking_added_when_vocab_has_it(self):
        """User adds 'striking adj. C1' to vocab_5000. Card with no corpus tag
        but matching word in vocab should get 5000 tag added."""
        txt = HEADER + [
            make_txt_line('g1', 'striking', 'adjective', 'Oxford', 'Audio::Cambridge CEFR::C1', cefr='C1'),
        ]
        # striking is in VOCAB_5000 at C1
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert len(updates) == 1
        assert TOKEN_5000 in updates[0].added
        assert updates[0].removed == []

    def test_no_add_when_word_not_in_any_vocab(self):
        """Word not in any vocab list -> no tag added even if scanned."""
        txt = HEADER + [
            make_txt_line('g1', 'notanyword', 'noun', 'Oxford', 'Audio::Cambridge CEFR::C1', cefr='C1'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        assert updates == []


class TestApplyUpdates:
    def test_apply_changes_only_tag_column(self):
        txt = HEADER + [
            make_txt_line('g1', 'arm', 'verb', 'Oxford', f'Audio::Cambridge {TOKEN_3000} {TOKEN_5000}', cefr='C1'),
        ]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        out = apply_updates(txt, updates)
        # Other fields unchanged
        for i in range(15):
            assert out[HEADER_LINES].split('\t')[i] == txt[HEADER_LINES].split('\t')[i]
        # Tag column changed
        new_tags = out[HEADER_LINES].split('\t')[15].split()
        assert TOKEN_3000 not in new_tags
        assert TOKEN_5000 in new_tags

    def test_apply_does_not_mutate_input(self):
        txt = HEADER + [
            make_txt_line('g1', 'arm', 'verb', 'Oxford', f'Audio::Cambridge {TOKEN_3000} {TOKEN_5000}', cefr='C1'),
        ]
        original_tags = txt[HEADER_LINES].split('\t')[15]
        updates = compute_tag_updates(txt, VOCAB_3000, VOCAB_5000)
        apply_updates(txt, updates)
        assert txt[HEADER_LINES].split('\t')[15] == original_tags

    def test_apply_no_updates_returns_identical(self):
        txt = HEADER + [make_txt_line('g1', 'arm', 'noun', 'Oxford', 'Audio::Cambridge', cefr='A1')]
        out = apply_updates(txt, [])
        assert out == txt
