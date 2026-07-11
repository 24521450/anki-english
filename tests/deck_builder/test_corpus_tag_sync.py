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
    get_vocab_membership,
    route_deck,
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
        project_root = Path(__file__).resolve().parents[2]
        path = project_root / 'vocab_list' / 'Oxford' / 'Oxford_3000.md'
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
        project_root = Path(__file__).resolve().parents[2]
        path = project_root / 'vocab_list' / 'Oxford' / 'Oxford_5000.md'
        if not path.exists():
            pytest.skip("vocab_list not available")
        result = _parse_vocab_list(path)
        # arm (verb) C1 in 5000
        assert ('arm', 'verb', 'C1') in result

    def test_normalizes_phrasal_verb_abbreviation(self, tmp_path):
        path = tmp_path / "awl.md"
        path.write_text(
            "| **derive** | phrasal v., v. | B2 | 1 |  |\n",
            encoding="utf-8",
        )
        result = _parse_vocab_list(path)
        assert ('derive', 'phrasal verb', 'B2') in result
        assert ('derive', 'verb', 'B2') in result


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
class TestNewRoutingAndTagContracts:
    def test_meantime_and_phrasal_cards_get_tag_from_non_first_pos(self):
        v3000 = set()
        v5000 = {
            ('adhere', 'verb', 'C1'),
            ('meantime', 'noun', 'C1'),
            ('deposit', 'verb', 'C1'),
            ('deprive', 'verb', 'C1'),
            ('derive', 'verb', 'B2'),
            ('devote', 'verb', 'B2'),
        }

        # meantime: pos = "adverb, noun" (noun is second)
        in_3000, in_5000 = get_vocab_membership('meantime', 'adverb, noun', 'C1', v3000, v5000)
        assert in_5000 is True

        # deposit: pos = "noun, verb" (verb is second)
        in_3000, in_5000 = get_vocab_membership('deposit', 'noun, verb', 'C1', v3000, v5000)
        assert in_5000 is True

        # deprive: pos = "phrasal verb, verb" (verb is second)
        in_3000, in_5000 = get_vocab_membership('deprive', 'phrasal verb, verb', 'C1', v3000, v5000)
        assert in_5000 is True

        # derive: pos = "phrasal verb, verb" (verb is second)
        in_3000, in_5000 = get_vocab_membership('derive', 'phrasal verb, verb', 'B2', v3000, v5000)
        assert in_5000 is True

        in_3000, in_5000 = get_vocab_membership('derive from', 'phrasal verb, verb', 'B2', v3000, v5000)
        assert in_5000 is True

        in_3000, in_5000 = get_vocab_membership('deprive of', 'phrasal verb', 'C1', v3000, v5000)
        assert in_5000 is True

        in_3000, in_5000 = get_vocab_membership('adhere to', 'phrasal verb', 'C1', v3000, v5000)
        assert in_5000 is True

        # devote: pos = "phrasal verb, verb" (verb is second)
        in_3000, in_5000 = get_vocab_membership('devote', 'phrasal verb, verb', 'B2', v3000, v5000)
        assert in_5000 is True

    def test_mainland_manual_fill_branch_gets_tag(self):
        v3000 = set()
        v5000 = {('mainland', 'noun', 'C1')}
        in_3000, in_5000 = get_vocab_membership('mainland', 'noun', 'C1', v3000, v5000)
        assert in_5000 is True

    def test_nursing_exception_tagged_and_routed(self):
        v3000 = set()
        v5000 = set()  # nursing is adj. in 5000.md, not noun
        in_3000, in_5000 = get_vocab_membership('nursing', 'noun', 'B2', v3000, v5000)
        assert in_5000 is True
        deck = route_deck('English Academic Vocabulary::Oxford', in_3000, in_5000, 'nursing', 'noun', 'B2')
        assert deck == 'English Academic Vocabulary::Oxford::Oxford 5000'

    def test_tags_column_17_and_19_parsing(self):
        # col 17 line (17th item is tags)
        line17 = "\t".join(["g1", "model", "deck", "word", "pos", "ipa", "def", "ex", "coll", "wf", "uk", "us", "src1", "src2", "C1", "idioms", "Tag17", "Syn18", "Ant19"])
        card17 = _parse_txt_card(line17, tags_col=17)
        assert card17["tags"] == "Tag17"

        # col 19 line (19th item is tags)
        line19 = "\t".join(["g1", "model", "deck", "word", "pos", "ipa", "def", "ex", "coll", "wf", "uk", "us", "src1", "src2", "C1", "idioms", "Syn17", "Ant18", "Tag19"])
        card19 = _parse_txt_card(line19, tags_col=19)
        assert card19["tags"] == "Tag19"

    def test_basic_advanced_5000_routing_and_priority(self):
        # Oxford 5000 priority wins
        deck = route_deck("English Academic Vocabulary::Oxford", is_in_3000=True, is_in_5000=True, word="test", pos_str="noun", cefr="B2")
        assert deck == "English Academic Vocabulary::Oxford::Oxford 5000"
        deck = route_deck("English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses", is_in_3000=False, is_in_5000=True, word="test", pos_str="noun", cefr="B2")
        assert deck == "English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses"

        # Oxford 3000 + B2 -> Advanced
        deck = route_deck("English Academic Vocabulary::Oxford", is_in_3000=True, is_in_5000=False, word="test", pos_str="noun", cefr="B2")
        assert deck == "English Academic Vocabulary::Oxford::Oxford 3000 Advanced"

        # Oxford 3000 + A2/B1 -> Basic
        deck = route_deck("English Academic Vocabulary::Oxford", is_in_3000=True, is_in_5000=False, word="test", pos_str="noun", cefr="B1")
        assert deck == "English Academic Vocabulary::Oxford::Oxford 3000 Basic"
        deck = route_deck("English Academic Vocabulary::Oxford", is_in_3000=True, is_in_5000=False, word="test", pos_str="noun", cefr="A2")
        assert deck == "English Academic Vocabulary::Oxford::Oxford 3000 Basic"

        # AWL Coxhead routing
        deck = route_deck("English Academic Vocabulary::TED YT", is_in_3000=False, is_in_5000=False, word="criterion", pos_str="noun", cefr="UNCLASSIFIED", is_in_awl_coxhead=True)
        assert deck == "English Academic Vocabulary::AWL 50 Academic Words"

        # Not in either list -> keep current deck (unless in AWL deck -> move to Oxford)
        deck = route_deck("English Academic Vocabulary::TED YT", is_in_3000=False, is_in_5000=False, word="test", pos_str="noun", cefr="C1")
        assert deck == "English Academic Vocabulary::TED YT"

        deck = route_deck("English Academic Vocabulary::AWL 50 Academic Words", is_in_3000=False, is_in_5000=False, word="rover", pos_str="noun", cefr="C2")
        assert deck == "English Academic Vocabulary::Oxford"

    def test_awl_coxhead_membership_rules_and_routing(self):
        from src.config import ProjectPaths
        from src.deck_builder.build_validation import _parse_txt_cards
        from src.deck_builder.corpus_tag_sync import apply_corpus_routing_and_tags

        proj = ProjectPaths()
        v3 = _parse_vocab_list(proj.oxford_3000_md)
        v5 = _parse_vocab_list(proj.oxford_5000_md)
        v_awl = _parse_vocab_list(proj.awl_md)
        cards, issues = _parse_txt_cards(proj.anki_notes_txt.read_text(encoding="utf-8"), proj.anki_notes_txt)
        assert not issues

        from collections import namedtuple
        CardMock = namedtuple('CardMock', ['word', 'pos', 'cefr', 'tags', 'deck'])
        cards = [CardMock(c.word, c.pos, c.cefr, c.tags, c.deck) for c in cards]

        updated = apply_corpus_routing_and_tags(cards, v3, v5, v_awl)

        by_word = {}
        for c in updated:
            w_clean = c.word.split(' (')[0].strip().lower()
            by_word.setdefault(w_clean, []).append(c)

        # 1. criterion is Oxford 3000 B2; labor remains AWL_Coxhead.
        assert any('Oxford_3000' in c.tags for c in by_word['criterion'])
        assert all('AWL_Coxhead' not in c.tags for c in by_word['criterion'])
        assert all(
            c.deck == 'English Academic Vocabulary::Oxford::Oxford 3000 Advanced'
            for c in by_word['criterion']
        )
        assert any('AWL_Coxhead' in c.tags for c in by_word['labor'])
        for c in by_word['labor']:
            assert c.deck == 'English Academic Vocabulary::AWL 50 Academic Words'

        # 2. trigger|verb|C2 gets NO AWL_Coxhead tag because headword trigger belongs to Oxford 5000
        for c in by_word['trigger']:
            assert 'AWL_Coxhead' not in c.tags

        # 3. rover gets NO list tag and moves to Oxford deck
        for c in by_word['rover']:
            tags_set = set(c.tags.split())
            assert not (tags_set & {'Oxford_3000', 'Oxford_5000', 'AWL_Coxhead'})
            assert c.deck == 'English Academic Vocabulary::Oxford'

        # 4. Every Oxford card has NO AWL_Coxhead
        for c in updated:
            tags_set = set(c.tags.split())
            if 'Oxford_3000' in tags_set or 'Oxford_5000' in tags_set:
                assert 'AWL_Coxhead' not in tags_set

    def test_behalf_oxford_idiom_c1(self):
        from src.config import ProjectPaths
        from src.deck_builder.awl_integrity import AwlIntegrityPaths, _load_oxford_facts
        proj = ProjectPaths()
        paths = AwlIntegrityPaths(awl_md=proj.awl_md, oxford_jsonl=proj.oxford_jsonl, cambridge_fallbacks_json=proj.awl_cambridge_fallbacks)
        facts = _load_oxford_facts(paths.oxford_jsonl)
        behalf_facts = facts.get('behalf')
        assert behalf_facts is not None
        assert 'noun' in behalf_facts.assigned
        assert 'C1' in behalf_facts.assigned['noun']

    def test_export_content_drift_rejection(self):
        from tools.check_corpus_tags import validate_export_consistency

        db_cards = [
            {
                'guid': 'g1',
                'notetype': 'model',
                'word': 'test',
                'pos': 'noun',
                'ipa': '/t/',
                'definition': 'canonical def',
                'example': 'ex',
                'collocations': '',
                'wordfamily': '',
                'uk_audio': '',
                'us_audio': '',
                'source1': 'Oxford',
                'source2': 'Oxford',
                'cefr': 'B2',
                'idioms': '',
                'synonyms': '',
                'antonyms': '',
                'tags': 'Oxford_3000',
            }
        ]

        # Case 1: Identical cards -> 0 errors
        exp_cards_clean = [dict(db_cards[0])]
        errors = validate_export_consistency(db_cards, exp_cards_clean, expected_count=1)
        assert errors == []

        # Case 2: Definition drift -> returns error
        exp_cards_drift = [dict(db_cards[0], definition='DRIFTED DEFINITION')]
        errors_drift = validate_export_consistency(db_cards, exp_cards_drift, expected_count=1)
        assert len(errors_drift) == 1
        assert "Field mismatch for card 'test'" in errors_drift[0]
        assert "DRIFTED DEFINITION" in errors_drift[0]
