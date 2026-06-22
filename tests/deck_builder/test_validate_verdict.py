"""Tests for validate_verdict gate (Stream B — bug fix).

These tests lock in the auto-detectable hard rules AFTER the 2026-06-22
P5D pass that REMOVED word-count limits:

  1. separator/count/content consistency (incl. empty chunk detection)
  2. headword-in-chunk (covers self-ref + leak + morphological_variant)
  3. no-gloss bypass

REMOVED in P5D:
  - Total word count 1-6 limit
  - Per-chunk word limits (`pick1` ≤6, `|` ≤4, `;` ≤3)

Human-filled glosses are now trusted over arbitrary numeric length caps.
See ADR 0005 addendum and `tools/_diag_p5d_validate_check.py` (the
pre-flight check that confirmed exactly 8 v2 repairs were blocked
purely by the word-count limit).

Rule A (synonym detection) is NOT auto-detectable; verified by M3 + human.
"""
import pytest

from src.deck_builder.gloss_llm import validate_verdict


class TestSelfReferential:
    """Headword as chunk = self-ref for pick1, leak for multi-chunk."""

    def test_pick1_self_ref_fails(self):
        errs = validate_verdict('basket', 'basket', 'none', 1)
        assert any('headword_in_chunk' in e for e in errs)

    def test_pick1_lowercase_headword_in_uppercase_gloss_fails(self):
        errs = validate_verdict('Basket', 'BASKET', 'none', 1)
        assert any('headword_in_chunk' in e for e in errs)

    def test_pick2_headword_leak_fails(self):
        errs = validate_verdict('accelerate', 'speed up; accelerate', ';', 2)
        assert any('headword_in_chunk[1]' in e for e in errs)

    def test_pick2_no_headword_passes(self):
        errs = validate_verdict('orient', 'direct | adjust', '|', 2)
        assert errs == []

    def test_pick1_word_in_gloss_but_not_whole_word_passes(self):
        # "basket" contains "basket" but "basketball" is not "basket"
        # This is fine -- only exact match counts
        errs = validate_verdict('ball', 'basketball court', 'none', 1)
        assert errs == []


class TestWordCountLimitsRemoved:
    """P5D: word-count limits removed. Long glosses pass if structure +
    headword checks are clean."""

    def test_long_single_chunk_passes(self):
        """A 7-word gloss used to fail with `word_count_out_of_range`.
        Now passes if separator/count/headword are valid."""
        errs = validate_verdict('test', 'a b c d e f g', 'none', 1)
        assert errs == []

    def test_long_pipe_chunks_pass(self):
        """Each side 5 words (was >4 limit for |). Now passes."""
        errs = validate_verdict(
            'test', 'one two three four five | six seven eight nine ten', '|', 2
        )
        assert errs == []

    def test_long_semicolon_chunks_pass(self):
        """Each side 4 words (was >3 limit for ;). Now passes."""
        errs = validate_verdict(
            'test', 'one two three four ; five six seven eight', ';', 2
        )
        assert errs == []

    def test_p5d_seed_additionally_passes(self):
        """The P5D seed fix `additionally -> also` already had a 1-word
        gloss, but verify the new validator still passes it."""
        errs = validate_verdict('additionally', 'also', 'none', 1)
        assert errs == []

    def test_p5d_identification_long_phrase_passes(self):
        """`identification` -> long multi-chunk gloss (12 words total).
        Pre-P5D: failed word_count_out_of_range. Post-P5D: passes."""
        gloss = (
            'proving who or what|recognizing importance|'
            'ID document|strong sympathy|close linking'
        )
        errs = validate_verdict('identification', gloss, '|', 5)
        assert errs == []

    def test_p5d_rental_three_chunks_passes(self):
        """`rental` -> 3-chunk gloss (7 words total).
        Pre-P5D: failed word_count_out_of_range. Post-P5D: passes."""
        errs = validate_verdict('rental', 'use fee|hiring deal|thing for hire', '|', 3)
        assert errs == []

    def test_p5d_pop_five_chunks_passes(self):
        """`pop` -> 5-chunk gloss (9 words total).
        Pre-P5D: failed word_count_out_of_range. Post-P5D: passes."""
        gloss = (
            'short sound|burst|go quickly|put quickly|appear suddenly'
        )
        errs = validate_verdict('pop', gloss, '|', 5)
        assert errs == []

    def test_p5d_compromise_three_chunks_passes(self):
        """`compromise` -> 3-chunk gloss (8 words total).
        Pre-P5D: failed word_count_out_of_range. Post-P5D: passes."""
        gloss = 'agreement by concession|lower standards|put at risk'
        errs = validate_verdict('compromise', gloss, '|', 3)
        assert errs == []

    def test_p5d_whip_four_chunks_passes(self):
        """`whip` -> 4-chunk gloss (9 words total).
        Pre-P5D: failed word_count_out_of_range. Post-P5D: passes."""
        gloss = 'hit with cord|move suddenly|pull suddenly|mix fast'
        errs = validate_verdict('whip', gloss, '|', 4)
        assert errs == []

    def test_p5d_punk_phrase_passes(self):
        """`punk` -> 2-word gloss."""
        errs = validate_verdict('punk', 'rock subculture member', 'none', 1)
        assert errs == []


class TestSeparatorCountConsistency:
    """Declared separator/count must match actual gloss content."""

    def test_separator_pipe_but_content_uses_semicolon(self):
        errs = validate_verdict('test', 'one ; two', '|', 2)
        assert any('separator_mismatch' in e for e in errs)
        assert any('declared=\'|\'' in e for e in errs)
        assert any('actual=\';\'' in e for e in errs)

    def test_count_mismatch_actual_2_declared_1(self):
        errs = validate_verdict('test', 'one|two', '|', 1)
        assert any('count_mismatch' in e for e in errs)

    def test_count_mismatch_actual_1_declared_2(self):
        # Actual structure = pick1, declared = pick2. count_mismatch fires,
        # but separator is consistent (both 'none'). separator_mismatch NOT fired.
        errs = validate_verdict('test', 'one', 'none', 2)
        assert any('count_mismatch' in e for e in errs)
        assert not any('separator_mismatch' in e for e in errs)

    def test_consistent_pass(self):
        errs = validate_verdict('test', 'one|two|three', '|', 3)
        assert errs == []

    def test_empty_chunk_after_pipe_fails(self):
        """`x |` -> separator with empty side. Empty chunk must fail."""
        errs = validate_verdict('test', 'x |', '|', 1)
        assert any('empty_chunk' in e for e in errs)

    def test_empty_chunk_between_semicolons_fails(self):
        """`x ; ; y` -> empty middle chunk. Must fail."""
        errs = validate_verdict('test', 'x ; ; y', ';', 2)
        assert any('empty_chunk' in e for e in errs)


class TestNoGlossBypass:
    """decision='no-gloss' should skip all checks."""

    def test_no_gloss_empty_gloss_passes(self):
        errs = validate_verdict('test', '', 'none', 0, decision='no-gloss')
        assert errs == []

    def test_no_gloss_with_self_ref_still_passes(self):
        # Even self-ref gloss is allowed in no-gloss mode
        errs = validate_verdict('basket', 'basket', 'none', 1, decision='no-gloss')
        assert errs == []

    def test_no_gloss_with_huge_word_count_passes(self):
        # Even 100-word "gloss" is allowed in no-gloss mode
        errs = validate_verdict(
            'test', ' '.join(['w'] * 100), 'none', 1, decision='no-gloss'
        )
        assert errs == []


class TestRealisticCases:
    """Real cases from the audit (M3 verdicts)."""

    def test_conviction_passes(self):
        # The regression test fixture from earlier work
        errs = validate_verdict('conviction', 'guilty verdict | firm belief', '|', 2)
        assert errs == []

    def test_basket_self_ref_fails(self):
        errs = validate_verdict('basket', 'basket', 'none', 1)
        assert errs != []

    def test_align_self_ref_leak(self):
        # align|verb|C1: 'line up; align' -- headword leak
        errs = validate_verdict('align', 'line up; align', ';', 2)
        assert any('headword_in_chunk[1]' in e for e in errs)

    def test_consultant_separator_mismatch(self):
        # consultant|noun|B2: 'subject expert; hospital specialist', '|' -- declared | but actual ;
        errs = validate_verdict(
            'consultant', 'subject expert; hospital specialist', '|', 2
        )
        assert any('separator_mismatch' in e for e in errs)


class TestMorphologicalSelfReferential:
    """Validate that morphological variants of headword are rejected in single-word glosses
    and exact headwords are rejected in phrases (except idiom templates)."""

    def test_single_word_variant_fails(self):
        errs1 = validate_verdict('configure', 'configuration', 'none', 1)
        assert any('morphological_variant' in e for e in errs1)

        errs2 = validate_verdict('demonstrate', 'demonstration', 'none', 1)
        assert any('morphological_variant' in e for e in errs2)

    def test_multi_word_exact_headword_in_phrase_fails(self):
        errs = validate_verdict('solo', 'solo performance', 'none', 1)
        assert any(
            'headword_in_definition' in e or 'headword_in_phrase' in e
            for e in errs
        )

    def test_multi_word_related_derivative_passes(self):
        errs1 = validate_verdict('disabled', 'having disability', 'none', 1)
        assert errs1 == []

        errs2 = validate_verdict('differ', 'be different', 'none', 1)
        assert errs2 == []

    def test_idiom_phrase_prefix_passes(self):
        errs = validate_verdict('toss', 'toss: flip coin', 'none', 1)
        assert errs == []
