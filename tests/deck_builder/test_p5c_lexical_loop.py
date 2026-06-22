"""P5C Lexical Loop Guard — detector tests.

Locks in the 5 plan cases:

  - `additionally -> in addition` flagged as `word_family_loop`
  - `additionally -> also` passes
  - `permanent -> not temporary` flagged as `antonym_loop`
  - `permanent -> long-lasting` passes
  - `mediate -> arbitrate` flagged as `hard_synonym_drift`

The detector (`tools/_detect_lexical_loops.py`) is read-only; these
tests assert the `detect_loops` function's verdict on each known case.
The detector is imported at test collection time so NLTK's Porter
stemmer is initialized once.
"""
from __future__ import annotations

import pytest

from tools._detect_lexical_loops import (
    BASIC_STOPWORDS,
    detect_loops,
)


class TestPlanCases:
    """Plan § Verification — 5 lock-in cases."""

    def test_additionally_in_addition_is_word_family_loop(self):
        """`additionally -> in addition` flagged as `word_family_loop`.

        Both share the `addit-*` stem (Porter stemmer).
        """
        assert detect_loops('additionally', 'in addition') == ['word_family_loop']

    def test_additionally_also_passes(self):
        """`additionally -> also` passes — `also` is a basic-English
        stopword and does not share headword stem."""
        assert detect_loops('additionally', 'also') == []

    def test_permanent_not_temporary_is_antonym_loop(self):
        """`permanent -> not temporary` flagged as `antonym_loop`."""
        assert detect_loops('permanent', 'not temporary') == ['antonym_loop']

    def test_permanent_long_lasting_passes(self):
        """`permanent -> long-lasting` passes — hyphenated compound is
        treated as 1 word, and `long-lasting` is built from basic
        stopwords (`long`, `lasting`)."""
        assert detect_loops('permanent', 'long-lasting') == []

    def test_mediate_arbitrate_is_hard_synonym_drift(self):
        """`mediate -> arbitrate` flagged as `hard_synonym_drift` —
        1-chunk, 1-word gloss, no shared stem, not a basic word."""
        assert detect_loops('mediate', 'arbitrate') == ['hard_synonym_drift']


class TestLoopTypeBoundaries:
    """Edge cases for each loop type."""

    def test_hyphenated_compound_treated_as_one_word(self):
        """`well-known` should be treated as 1 word for hard_synonym_drift
        purposes (not flagged as a hard synonym by word-count)."""
        # `well-known` has no shared stem with `unknown` headword.
        assert detect_loops('unknown', 'well-known') == []

    def test_basic_stopword_never_hard_synonym(self):
        """Basic stopwords never trigger `hard_synonym_drift`."""
        for w in ('also', 'too', 'more', 'long', 'short'):
            assert detect_loops('synonym', w) == [], f'{w!r} flagged as hard_synonym_drift'

    def test_multi_chunk_no_loop(self):
        """Multi-chunk glosses (with `|`) are not hard_synonym_drift."""
        # headword 'unrelated' -> multi-chunk gloss 'abc|def' has no
        # shared stem and isn't a single word.
        assert detect_loops('unrelated', 'abc|def') == []

    def test_word_family_loop_via_compound(self):
        """Compound gloss sharing headword stem is a `word_family_loop`."""
        # `long` -> `long-lasting` shares the `long` stem.
        assert 'word_family_loop' in detect_loops('long', 'long-lasting')

    def test_antonym_loop_with_un_prefix(self):
        """`un-` prefix on a real word triggers antonym_loop."""
        assert detect_loops('fair', 'unfair') == ['antonym_loop']

    def test_antonym_loop_false_positive_check(self):
        """`notable` (starting with `not `) would false-positive; check
        that `notable` alone (no space after `not`) doesn't trigger."""
        # No space after `not`, so it shouldn't be detected as antonym_loop.
        # Also `notable` shares no stem with `good`.
        assert 'antonym_loop' not in detect_loops('good', 'notable')


class TestDetectorMetadata:
    """Sanity on the detector's exposed metadata."""

    def test_basic_stopwords_is_nonempty(self):
        assert len(BASIC_STOPWORDS) > 100, 'basic stoplist suspiciously small'

    def test_basic_stopwords_contains_also(self):
        """`also` must be in the stoplist for the `additionally -> also`
        case to pass."""
        assert 'also' in BASIC_STOPWORDS

    def test_basic_stopwords_does_not_contain_arbitrate(self):
        """`arbitrate` must NOT be in the stoplist for the
        `mediate -> arbitrate` case to flag."""
        assert 'arbitrate' not in BASIC_STOPWORDS
