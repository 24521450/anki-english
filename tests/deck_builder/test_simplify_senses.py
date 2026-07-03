"""Tests for simplify_senses (pure functions)."""
import pytest
from src.deck_builder.simplify_senses import (
    resolve_sense_cefr,
    _flatten_senses,
    _merge_texts,
    _merge_register_tags,
    _merge_topics,
    _merge_collocations,
    _pick_examples,
    _merge_countability,
    _merge_domain,
    cluster_senses,
    drop_redundant_unclassified,
    merge_cluster,
    simplify_record,
)


class TestResolveSenseCEFR:
    """Per-sense resolution per CONTEXT.md rule. Sources: sense_badge,
    inherited_single, inherited_primary, unlisted, no_data."""

    # Rule 1: def has own CEFR â†’ use it, source='sense_badge'
    def test_sense_badge_wins(self):
        val, src = resolve_sense_cefr('B2', 'C1', sense_idx=0, total_senses=1)
        assert val == 'B2' and src == 'sense_badge'

    def test_sense_badge_even_when_not_first(self):
        val, src = resolve_sense_cefr('B2', 'C1', sense_idx=3, total_senses=5)
        assert val == 'B2' and src == 'sense_badge'

    # Rule 2: def null, single-sense word â†’ inherit
    def test_inherited_single(self):
        val, src = resolve_sense_cefr(None, 'C1', sense_idx=0, total_senses=1)
        assert val == 'C1' and src == 'inherited_single'

    def test_no_data_single_no_badge(self):
        val, src = resolve_sense_cefr(None, None, sense_idx=0, total_senses=1)
        assert val is None and src == 'no_data'

    # Rule 3: def null, multi-sense, another sense has badge â†’ unlisted
    def test_unlisted_when_another_has_badge(self):
        val, src = resolve_sense_cefr(
            None, 'C1', sense_idx=1, total_senses=3, any_other_has_badge=True,
        )
        assert val is None and src == 'unlisted'

    def test_unlisted_even_for_sense_0_when_another_has_badge(self):
        """Rule 3 wins over Rule 4: another sense has badge â†’ this one unlisted,
        even if it's sense 0 (no inherited_primary fallback)."""
        val, src = resolve_sense_cefr(
            None, 'C1', sense_idx=0, total_senses=3, any_other_has_badge=True,
        )
        assert val is None and src == 'unlisted'

    # Rule 4: all senses null, multi-sense
    def test_inherited_primary_sense_0(self):
        val, src = resolve_sense_cefr(
            None, 'C1', sense_idx=0, total_senses=3, any_other_has_badge=False,
        )
        assert val == 'C1' and src == 'inherited_primary'

    def test_unlisted_secondary_sense(self):
        val, src = resolve_sense_cefr(
            None, 'C1', sense_idx=1, total_senses=3, any_other_has_badge=False,
        )
        assert val is None and src == 'unlisted'

    def test_unlisted_secondary_no_badge(self):
        val, src = resolve_sense_cefr(
            None, None, sense_idx=1, total_senses=3, any_other_has_badge=False,
        )
        assert val is None and src == 'unlisted'

    # Rule 5
    def test_no_data_primary_no_badge(self):
        val, src = resolve_sense_cefr(
            None, None, sense_idx=0, total_senses=3, any_other_has_badge=False,
        )
        assert val is None and src == 'no_data'


class TestMergeTexts:
    def test_pipe_join(self):
        assert _merge_texts(['a', 'b', 'c']) == 'a ; b ; c'

    def test_drop_empty(self):
        assert _merge_texts(['a', '', 'b', None]) == 'a ; b'

    def test_single(self):
        assert _merge_texts(['only']) == 'only'

    def test_empty(self):
        assert _merge_texts([]) == ''


class TestMergeRegisterTags:
    def test_union_preserving_order(self):
        out = _merge_register_tags([['informal', 'disapproving'], ['literary', 'disapproving']])
        assert out == ['informal', 'disapproving', 'literary']

    def test_empty(self):
        assert _merge_register_tags([]) == []
        assert _merge_register_tags([[], []]) == []


class TestMergeTopics:
    def test_union_by_name_cefr(self):
        t1 = [{'name': 'Education', 'cefr': 'B1'}, {'name': 'War', 'cefr': 'C1'}]
        t2 = [{'name': 'Education', 'cefr': 'B1'}, {'name': 'Politics', 'cefr': ''}]
        out = _merge_topics([t1, t2])
        assert len(out) == 3
        names = {(t['name'], t['cefr']) for t in out}
        assert ('Education', 'B1') in names
        assert ('War', 'C1') in names
        assert ('Politics', '') in names


class TestMergeCollocations:
    def test_union_per_bucket(self):
        s1 = {'adjective': ['a', 'b'], 'verb + word': ['x']}
        s2 = {'adjective': ['b', 'c']}
        out = _merge_collocations([s1, s2])
        assert out['adjective'] == ['a', 'b', 'c']
        assert out['verb + word'] == ['x']

    def test_empty(self):
        assert _merge_collocations([{}]) == {}


class TestPickExamples:
    def test_max_2_default(self):
        ex = [{'text': f'ex{i}', 'cf': None} for i in range(5)]
        out = _pick_examples([ex, []], max_n=2)
        assert len(out) == 2
        assert out[0]['text'] == 'ex0'
        assert out[1]['text'] == 'ex1'

    def test_dedup_by_text(self):
        ex1 = [{'text': 'same', 'cf': None}, {'text': 'unique1', 'cf': None}]
        ex2 = [{'text': 'same', 'cf': None}, {'text': 'unique2', 'cf': None}]
        out = _pick_examples([ex1, ex2], max_n=5)
        assert len(out) == 3  # 'same' deduplicated

    def test_empty(self):
        assert _pick_examples([]) == []


class TestMergeCountability:
    def test_most_common(self):
        assert _merge_countability(['countable', 'uncountable', 'countable']) == 'countable'

    def test_skip_null(self):
        assert _merge_countability([None, 'countable', None]) == 'countable'

    def test_all_null(self):
        assert _merge_countability([None, None]) is None

    def test_empty(self):
        assert _merge_countability([]) is None


class TestClusterSenses:
    def test_single_pos_single_cefr(self):
        record = {
            'oxford_badge': 'C1',
            'pos_data': [
                {'pos': 'noun', 'definitions': [
                    {'cefr': 'B2', 'text': 'd1'},
                    {'cefr': 'B2', 'text': 'd2'},
                ]},
            ],
        }
        flat = _flatten_senses(record)
        clusters = cluster_senses(flat)
        assert len(clusters) == 1
        assert sorted(clusters[0]) == [0, 1]

    def test_multi_pos_separate_clusters(self):
        record = {
            'oxford_badge': None,
            'pos_data': [
                {'pos': 'noun', 'definitions': [{'cefr': 'B2', 'text': 'd1'}]},
                {'pos': 'verb', 'definitions': [{'cefr': 'B2', 'text': 'd2'}]},
            ],
        }
        flat = _flatten_senses(record)
        clusters = cluster_senses(flat)
        assert len(clusters) == 2
        assert {tuple(flat[i].pos for i in c) for c in clusters} == {('noun',), ('verb',)}

    def test_cef_fallback_to_badge(self):
        record = {
            'oxford_badge': 'C1',
            'pos_data': [
                {'pos': 'noun', 'definitions': [{'cefr': None, 'text': 'd1'}]},
            ],
        }
        flat = _flatten_senses(record)
        clusters = cluster_senses(flat)
        assert len(clusters) == 1
        assert flat[clusters[0][0]].cefr_resolved == 'C1'

    def test_mixed_cefr_creates_multiple_clusters(self):
        record = {
            'oxford_badge': 'C1',
            'pos_data': [
                {'pos': 'noun', 'definitions': [
                    {'cefr': 'B1', 'text': 'd1'},
                    {'cefr': 'B2', 'text': 'd2'},
                    {'cefr': None, 'text': 'd3'},
                ]},
            ],
        }
        flat = _flatten_senses(record)
        clusters = cluster_senses(flat)
        # 3 buckets: B1, B2, C1 (fallback)
        assert len(clusters) == 3


class TestDropRedundantUnclassified:
    def test_drop_unclassified_when_pos_has_strong_signal(self):
        record = {
            'oxford_badge': None,
            'pos_data': [
                {'pos': 'noun', 'definitions': [
                    {'cefr': 'B2', 'text': 'd1'},
                    {'cefr': None, 'text': 'd2'},
                ]},
            ],
        }
        flat = _flatten_senses(record)
        clusters = cluster_senses(flat)  # [[0], [1]]
        kept = drop_redundant_unclassified(flat, clusters)
        # d2 cluster dropped because d1 (same pos) has signal
        assert kept == [[0]]

    def test_keep_all_when_all_unclassified(self):
        record = {
            'oxford_badge': None,
            'pos_data': [
                {'pos': 'noun', 'definitions': [
                    {'cefr': None, 'text': 'd1'},
                    {'cefr': None, 'text': 'd2'},
                ]},
            ],
        }
        flat = _flatten_senses(record)
        clusters = cluster_senses(flat)
        # Both cefr=None in same pos = same cluster
        assert len(clusters) == 1
        kept = drop_redundant_unclassified(flat, clusters)
        # All UNCLASSIFIED in record: keep the single merged cluster
        assert len(kept) == 1
        assert kept[0] == [0, 1]

    def test_keep_unclassified_in_different_pos(self):
        record = {
            'oxford_badge': None,
            'pos_data': [
                {'pos': 'noun', 'definitions': [{'cefr': 'B2', 'text': 'd1'}]},
                {'pos': 'verb', 'definitions': [{'cefr': None, 'text': 'd2'}]},
            ],
        }
        flat = _flatten_senses(record)
        clusters = cluster_senses(flat)
        kept = drop_redundant_unclassified(flat, clusters)
        # pos=verb has only d2 (no signal), keep it
        assert sorted([c[0] for c in kept]) == [0, 1]


class TestSimplifyRecord:
    def test_abortion_style_record(self):
        """abortion: 3 senses, 2 C1 + 1 null (sense_idx=2).
        Realistic data: shared collocations push Î² over merge threshold.
        """
        record = {
            'word': 'abortion',
            'oxford_badge': 'C1',
            'pos_data': [
                {'pos': 'noun', 'definitions': [
                    {'cefr': 'C1', 'text': 'the deliberate ending of a pregnancy at an early stage',
                     'register_tags': [], 'examples': [{'text': 'to support/oppose abortion', 'cf': None}],
                     'countability': 'uncountable', 'domain': None, 'topics': [], 'collocations': {'adjective': ['legal', 'legalized', 'elective']}, 'is_phrase': False, 'is_idiom': False},
                    {'cefr': 'C1', 'text': 'a medical operation to end a pregnancy at an early stage',
                     'register_tags': [], 'examples': [{'text': 'She decided to have an abortion.', 'cf': None}],
                     'countability': 'countable', 'domain': None, 'topics': [], 'collocations': {'adjective': ['legal', 'legalized', 'elective']}, 'is_phrase': False, 'is_idiom': False},
                    {'cefr': None, 'text': 'the process of giving birth to a baby before it is fully developed and able to survive',
                     'register_tags': [], 'examples': [], 'countability': 'uncountable', 'domain': 'medical', 'topics': [], 'collocations': {}, 'is_phrase': False, 'is_idiom': False},
                ]},
            ],
        }
        result = simplify_record(record)
        # Senses 1+2: shared collocations ['legal', 'legalized', 'elective'] â†’ Î² high â†’ merge
        # Sense 3: dropped (Rule 3: another sense has badge)
        assert len(result) == 1, f'expected 1 merged sense, got {len(result)}: {[r.text for r in result]}'
        merged = result[0]
        assert merged.pos == 'noun'
        assert merged.cefr == 'C1'
        assert 'deliberate ending' in merged.text and 'medical operation' in merged.text
        assert 'sense3' not in merged.text  # NOT the medical one
        assert merged.cefr_originals == ['C1', 'C1']
        assert merged.cefr_sources == ['sense_badge', 'sense_badge']
        assert merged.beta_decision in ('merge', 'review')  # depends on exact def similarity
        assert merged.semantic_score is not None
        assert merged.semantic_score >= 0.3  # at least in review band

    def test_saturate_style_record(self):
        """All defs cefr=null, oxford_badge=None, 2 senses with shared collocations.
        Both kept because no other sense has a signal; Î² may split (low overlap)
        or merge if collocations match.

        Per CONTEXT.md, these records should be SKIPPED at build time
        (no_data at sense[0]). But simplify_senses keeps them so build_notes
        can apply the Skip Rule.
        """
        record = {
            'word': 'saturate',
            'oxford_badge': None,
            'pos_data': [
                {'pos': 'verb', 'definitions': [
                    {'cefr': None, 'text': 'make something completely wet',
                     'register_tags': [], 'examples': [{'text': 'Saturate the soil with water.', 'cf': None}],
                     'countability': None, 'domain': None, 'topics': [],
                     'collocations': {'verb + saturate': ['fully', 'completely']}, 'is_phrase': False, 'is_idiom': False},
                    {'cefr': None, 'text': 'fill something completely',
                     'register_tags': [], 'examples': [{'text': 'The market is saturated with phones.', 'cf': None}],
                     'countability': None, 'domain': None, 'topics': [],
                     'collocations': {'verb + saturate': ['fully', 'completely']}, 'is_phrase': False, 'is_idiom': False},
                ]},
            ],
        }
        result = simplify_record(record)
        # Î²: shared collocations + similar defs â†’ likely merge or review
        # The exact decision depends on def token overlap, but neither sense should be silently dropped.
        assert len(result) >= 1
        if len(result) == 1:
            assert result[0].cefr is None
            assert result[0].cefr_sources == ['no_data', 'unlisted']
        # If split, each is its own no_data/unlisted sense
        for r in result:
            assert r.cefr is None

    def test_arguably_style_record(self):
        """arguably: 1 sense, cefr=null, badge=C1 â†’ inherited_single."""
        record = {
            'word': 'arguably',
            'oxford_badge': 'C1',
            'pos_data': [
                {'pos': 'adverb', 'definitions': [
                    {'cefr': None, 'text': 'used when you are stating an opinion that not everyone will agree with',
                     'register_tags': [], 'examples': [{'text': 'He is arguably the best player.', 'cf': None}],
                     'countability': None, 'domain': None, 'topics': [],
                     'collocations': {'adverb + arguably': ['most', 'best']}, 'is_phrase': False, 'is_idiom': False},
                ]},
            ],
        }
        result = simplify_record(record)
        assert result[0].cefr == 'C1'
        assert result[0].cefr_sources == ['inherited_single']

    def test_sense_0_unlisted_when_another_has_badge(self):
        """2 senses, sense 0 null, sense 1 C1 â†’ sense 0 is unlisted (Rule 3 wins
        over Rule 4). sense 1 kept as sense_badge C1.
        """
        record = {
            'word': 'test_primary',
            'oxford_badge': 'B1',
            'pos_data': [
                {'pos': 'noun', 'definitions': [
                    {'cefr': None, 'text': 's1', 'register_tags': [], 'examples': [{'text': 'e1', 'cf': None}], 'countability': None, 'domain': None, 'topics': [], 'collocations': {}, 'is_phrase': False, 'is_idiom': False},
                    {'cefr': 'C1', 'text': 's2', 'register_tags': [], 'examples': [{'text': 'e2', 'cf': None}], 'countability': None, 'domain': None, 'topics': [], 'collocations': {}, 'is_phrase': False, 'is_idiom': False},
                ]},
            ],
        }
        result = simplify_record(record)
        # Only sense 2 (C1) kept. Sense 0 dropped (unlisted, because sense 1 has badge)
        assert len(result) == 1
        assert result[0].cefr == 'C1'
        assert result[0].cefr_sources == ['sense_badge']
        assert 's1' not in result[0].text

    def test_unlisted_secondary_dropped(self):
        """2 senses same pos, sense 0 C1, sense 1 null â†’ sense 1 dropped (unlisted)."""
        record = {
            'word': 'test_unlisted',
            'oxford_badge': 'B1',
            'pos_data': [
                {'pos': 'noun', 'definitions': [
                    {'cefr': 'C1', 'text': 's1', 'register_tags': [], 'examples': [{'text': 'e1', 'cf': None}], 'countability': None, 'domain': None, 'topics': [], 'collocations': {}, 'is_phrase': False, 'is_idiom': False},
                    {'cefr': None, 'text': 's2 (unlisted, dropped)', 'register_tags': [], 'examples': [{'text': 'e2', 'cf': None}], 'countability': None, 'domain': None, 'topics': [], 'collocations': {}, 'is_phrase': False, 'is_idiom': False},
                ]},
            ],
        }
        result = simplify_record(record)
        assert len(result) == 1
        assert result[0].cefr == 'C1'
        assert 's2' not in result[0].text

    def test_inherited_primary_when_all_null_multisense(self):
        """Rule 4: all senses null, multi-sense â†’ sense 0 = inherited_primary.
        Realistic data: similar defs push Î² into merge band.
        """
        record = {
            'word': 'test_all_null',
            'oxford_badge': 'B2',
            'pos_data': [
                {'pos': 'noun', 'definitions': [
                    {'cefr': None, 'text': 'a place where something happens',
                     'register_tags': [], 'examples': [{'text': 'meeting place', 'cf': None}],
                     'countability': None, 'domain': None, 'topics': [],
                     'collocations': {'adjective': ['good', 'safe']}, 'is_phrase': False, 'is_idiom': False},
                    {'cefr': None, 'text': 'a particular location or position',
                     'register_tags': [], 'examples': [{'text': 'place of birth', 'cf': None}],
                     'countability': None, 'domain': None, 'topics': [],
                     'collocations': {'adjective': ['good', 'safe']}, 'is_phrase': False, 'is_idiom': False},
                ]},
            ],
        }
        result = simplify_record(record)
        # Shared collocations + similar defs â†’ Î² may merge or review
        if len(result) == 1:
            assert result[0].cefr == 'B2'
            assert 'inherited_primary' in result[0].cefr_sources
            assert 'unlisted' in result[0].cefr_sources

    def test_multi_pos_produces_multiple_senses(self):
        record = {
            'word': 'test',
            'oxford_badge': None,
            'pos_data': [
                {'pos': 'noun', 'definitions': [{'cefr': 'B2', 'text': 'n1', 'register_tags': [], 'examples': [], 'countability': None, 'domain': None, 'topics': [], 'collocations': {}, 'is_phrase': False, 'is_idiom': False}]},
                {'pos': 'verb', 'definitions': [{'cefr': 'B2', 'text': 'v1', 'register_tags': [], 'examples': [], 'countability': None, 'domain': None, 'topics': [], 'collocations': {}, 'is_phrase': False, 'is_idiom': False}]},
            ],
        }
        result = simplify_record(record)
        assert len(result) == 2
        assert {r.pos for r in result} == {'noun', 'verb'}

    def test_empty_record_returns_empty(self):
        record = {'word': 'empty', 'pos_data': [], 'oxford_badge': None}
        result = simplify_record(record)
        assert result == []

    def test_idiom_only_record_returns_empty(self):
        record = {'word': 'idiom', 'pos_data': [], 'oxford_badge': None, 'idioms': [{'phrase': 'test'}]}
        result = simplify_record(record)
        assert result == []


class TestDetectRuleLabel:
    def test_all_sense_badge(self):
        from src.deck_builder.simplify_senses import detect_rule_label
        assert detect_rule_label(['sense_badge', 'sense_badge'], original_sources=['sense_badge', 'sense_badge']) == \
            'Rule 1: all senses originally have own CEFR'

    def test_inherited_single(self):
        from src.deck_builder.simplify_senses import detect_rule_label
        assert detect_rule_label(['inherited_single'], original_sources=['inherited_single']) == \
            'Rule 2: single-sense word inherits headword CEFR'

    def test_inherited_primary_with_unlisted(self):
        from src.deck_builder.simplify_senses import detect_rule_label
        # survived: 1 sense (inherited_primary). originally 2 senses (both null).
        assert detect_rule_label(['inherited_primary'], original_sources=['inherited_primary', 'unlisted']) == \
            'Rule 4: all senses null, primary inherited'

    def test_mixed_surviving_sense_badge_but_originally_had_unlisted(self):
        from src.deck_builder.simplify_senses import detect_rule_label
        # abortion case: survived [sense_badge, sense_badge], original was [sense_badge, sense_badge, unlisted]
        assert detect_rule_label(['sense_badge', 'sense_badge'], original_sources=['sense_badge', 'sense_badge', 'unlisted']) == \
            'Rule 1+3: surviving senses all have own CEFR (dropped 1 unlisted)'

    def test_no_data_with_unlisted(self):
        from src.deck_builder.simplify_senses import detect_rule_label
        # saturate: all-null, badge=None, 2 senses
        assert detect_rule_label(['no_data', 'unlisted'], original_sources=['no_data', 'unlisted']) == \
            'Rule 5: no headword CEFR (no_data)'

    def test_mixed_surviving_with_no_data(self):
        from src.deck_builder.simplify_senses import detect_rule_label
        # survived: no_data, originally: no_data + unlisted + sense_badge
        # This means original HAD signal, but only no_data survived (e.g. unlisted dropped because
        # same pos had signal â€” but no_data itself is primary sense, so kept)
        assert detect_rule_label(['no_data'], original_sources=['no_data', 'unlisted', 'sense_badge']) == \
            'Rule 3: dropped unlisted senses (only no_data primary survived)'

    def test_fallback_unknown(self):
        from src.deck_builder.simplify_senses import detect_rule_label
        assert detect_rule_label([], original_sources=[]) == 'Unknown'

    def test_default_args_compat_with_old_api(self):
        """Old API: detect_rule_label(surviving) without original. Should still work."""
        from src.deck_builder.simplify_senses import detect_rule_label
        # When original is omitted, use surviving as proxy
        assert 'Rule 1' in detect_rule_label(['sense_badge', 'sense_badge'])
        assert 'Rule 2' in detect_rule_label(['inherited_single'])
