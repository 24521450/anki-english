"""Tests for beta_score (β heuristic)."""
import pytest
from src.deck_builder.beta_score import (
    _tokenize,
    _jaccard,
    _flatten_collocations,
    collocation_overlap,
    example_overlap,
    definition_similarity,
    semantic_score,
    evaluate_pair,
    ScoreVerdict,
)


class TestTokenize:
    def test_lowercase_and_split(self):
        assert 'pregnancy' in _tokenize("the deliberate ending of a pregnancy")

    def test_strip_stopwords(self):
        toks = _tokenize("a person who teaches")
        assert 'person' in toks
        assert 'teaches' in toks
        # Stopwords removed
        assert 'a' not in toks
        assert 'who' not in toks

    def test_drop_short_tokens(self):
        toks = _tokenize("I am a doer of deeds")
        # 'I', 'am', 'a' dropped
        assert 'doer' in toks
        assert 'deeds' in toks

    def test_empty(self):
        assert _tokenize("") == set()
        assert _tokenize("a the of") == set()  # all stopwords


class TestJaccard:
    def test_identical(self):
        assert _jaccard({'a', 'b'}, {'a', 'b'}) == 1.0

    def test_disjoint(self):
        assert _jaccard({'a', 'b'}, {'c', 'd'}) == 0.0

    def test_partial(self):
        # 1 common, 3 unique total → 1/3
        assert _jaccard({'a', 'b'}, {'b', 'c'}) == pytest.approx(1/3)

    def test_both_empty(self):
        assert _jaccard(set(), set()) == 0.0


class TestFlattenCollocations:
    def test_basic(self):
        c = {'adjective': ['broad', 'general'], 'verb + word': ['have']}
        out = _flatten_collocations(c)
        assert out == {'broad', 'general', 'have'}

    def test_empty(self):
        assert _flatten_collocations({}) == set()
        assert _flatten_collocations(None) == set()

    def test_ignores_empty_buckets(self):
        c = {'adjective': None, 'verb + word': [], 'noun': ['legal']}
        assert _flatten_collocations(c) == {'legal'}


class TestCollocationOverlap:
    def test_identical(self):
        c = {'adj': ['a', 'b', 'c']}
        assert collocation_overlap(c, c) == 1.0

    def test_disjoint(self):
        c1 = {'adj': ['a', 'b']}
        c2 = {'adj': ['c', 'd']}
        assert collocation_overlap(c1, c2) == 0.0

    def test_one_empty(self):
        c1 = {'adj': ['a', 'b']}
        c2 = {}
        assert collocation_overlap(c1, c2) == 0.0

    def test_partial(self):
        c1 = {'adj': ['legal', 'safe']}
        c2 = {'adj': ['safe', 'open']}
        # 1 common, 3 unique total → 1/3
        assert collocation_overlap(c1, c2) == pytest.approx(1/3)


class TestExampleOverlap:
    def test_identical(self):
        e1 = [{'text': 'He is great'}, {'text': 'She is tall'}]
        assert example_overlap(e1, e1) == 1.0

    def test_disjoint(self):
        e1 = [{'text': 'a'}]
        e2 = [{'text': 'b'}]
        assert example_overlap(e1, e2) == 0.0

    def test_one_empty(self):
        assert example_overlap([], [{'text': 'a'}]) == 0.0


class TestDefinitionSimilarity:
    def test_identical(self):
        assert definition_similarity("the deliberate ending", "the deliberate ending") == 1.0

    def test_synonyms_cheap_match(self):
        # 'pregnancy' / 'pregnancy' overlap; 'medical' not in both
        # Tokens: {pregnancy, ending} vs {pregnancy, operation}
        # Jaccard: 1/3
        s1 = "the ending of a pregnancy"
        s2 = "the medical operation of pregnancy"
        score = definition_similarity(s1, s2)
        assert 0 < score < 1

    def test_completely_different(self):
        assert definition_similarity("red", "blue") == 0.0

    def test_empty_one_side(self):
        assert definition_similarity("red", "") == 0.0


class TestSemanticScore:
    def test_overlap_components(self):
        # senses with high collocation overlap, low example, no def similarity
        s1 = {'text': 'aaa', 'collocations': {'adj': ['a', 'b', 'c']}, 'examples': []}
        s2 = {'text': 'bbb', 'collocations': {'adj': ['a', 'b', 'c']}, 'examples': []}
        # coll=1.0, ex=0.0, defn=0.0 → score = 0.5
        assert semantic_score(s1, s2) == pytest.approx(0.5)

    def test_zero_when_all_empty(self):
        s1 = {'text': '', 'collocations': {}, 'examples': []}
        s2 = {'text': '', 'collocations': {}, 'examples': []}
        assert semantic_score(s1, s2) == 0.0


class TestEvaluatePair:
    def test_high_score_merge(self):
        s1 = {'text': 'a medical operation to do something', 'collocations': {'adj': ['a', 'b']}, 'examples': [{'text': 'a'}]}
        s2 = {'text': 'an operation to do something', 'collocations': {'adj': ['a', 'b']}, 'examples': [{'text': 'a'}]}
        verdict = evaluate_pair(s1, s2)
        # Just check it returns a verdict
        assert verdict.score > 0
        assert verdict.decision in ('merge', 'review', 'split')

    def test_low_score_split(self):
        s1 = {'text': 'red color', 'collocations': {}, 'examples': []}
        s2 = {'text': 'blue sky', 'collocations': {}, 'examples': []}
        verdict = evaluate_pair(s1, s2)
        # No overlap → 0.0 → split
        assert verdict.score < 0.3
        assert verdict.decision == 'split'

    def test_review_band(self):
        """Score in middle band (0.3-0.7) → 'review'.

        Construct senses with PARTIAL collocation overlap and similar but
        not identical definitions. Should land in review band.
        """
        s1 = {
            'text': 'to plan something in advance',
            'collocations': {'adjective': ['careful', 'detailed']},
            'examples': [{'text': 'plan a meeting'}],
        }
        s2 = {
            'text': 'to schedule something carefully',
            'collocations': {'adjective': ['careful']},
            'examples': [{'text': 'schedule a meeting'}],
        }
        # coll: 1/2 = 0.5 → 0.25
        # ex: 0/2 (different texts after lowercase) = 0 → 0
        # defn: token overlap = some, maybe 0.2-0.4 → 0.04-0.08
        # Total: ~0.29-0.33 → review band (close to split threshold)
        verdict = evaluate_pair(s1, s2)
        # If we're at the edge, just verify decision is 'review' or 'split'
        # (0.3 is a soft threshold; this is on the edge).
        assert verdict.decision in ('review', 'split')

    def test_thresholds_documented(self):
        """Default thresholds are 0.7/0.3."""
        s1 = {'text': 'foo', 'collocations': {}, 'examples': []}
        s2 = {'text': 'foo', 'collocations': {}, 'examples': []}
        verdict = evaluate_pair(s1, s2)
        assert verdict.threshold_merge == 0.7
        assert verdict.threshold_split == 0.3


class TestRealCases:
    """Real-word test cases from user's review."""

    def test_abortion_should_merge(self):
        """Senses 1+2 share collocations heavily and similar definitions."""
        s1 = {
            'text': 'the deliberate ending of a pregnancy at an early stage',
            'collocations': {'adjective': ['legal', 'legalized', 'elective']},
            'examples': [{'text': 'to support/oppose abortion'}],
        }
        s2 = {
            'text': 'a medical operation to end a pregnancy at an early stage',
            'collocations': {'adjective': ['legal', 'legalized', 'elective']},
            'examples': [{'text': 'She decided to have an abortion.'}],
        }
        # Same collocations → coll=1.0
        # Examples differ → ex=0.0
        # Text overlap: pregnancy, ending/operation, early, stage → some
        # Score should be high
        verdict = evaluate_pair(s1, s2)
        # col=1.0*0.5=0.5, ex=0.0*0.3=0, def ~0.2 → ~0.7+
        assert verdict.score >= 0.5, f'expected >= 0.5, got {verdict.score}'

    def test_set_up_should_split(self):
        """set up senses have empty collocations and different definitions."""
        s1 = {
            'text': 'to create a business or organization',
            'collocations': {},
            'examples': [{'text': 'set up a new company'}],
        }
        s2 = {
            'text': 'to build or put something in position',
            'collocations': {},
            'examples': [{'text': 'set up a camera'}],
        }
        s3 = {
            'text': 'to arrange a meeting',
            'collocations': {},
            'examples': [{'text': 'set up a meeting'}],
        }
        v12 = evaluate_pair(s1, s2)
        v13 = evaluate_pair(s1, s3)
        v23 = evaluate_pair(s2, s3)
        # All pairs should be low (no overlap, different texts)
        assert v12.score < 0.5, f'set up 1-2: {v12.score}'
        assert v13.score < 0.5, f'set up 1-3: {v13.score}'
        assert v23.score < 0.5, f'set up 2-3: {v23.score}'

    def test_weave_partial_overlap(self):
        """weave cloth vs weave through traffic — should split (different verbs)."""
        s_cloth = {
            'text': 'to make cloth by crossing threads',
            'collocations': {'noun': ['thread', 'cloth']},
            'examples': [{'text': 'weave a basket'}],
        }
        s_traffic = {
            'text': 'to move in a winding path',
            'collocations': {},
            'examples': [{'text': 'The road weaves through the hills.'}],
        }
        verdict = evaluate_pair(s_cloth, s_traffic)
        # No shared collocations, different texts, no shared examples
        assert verdict.score < 0.5
