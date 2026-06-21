"""Tests for validate_verdict gate (Stream B — bug fix).

These tests lock in the 4 auto-detectable hard rules:
  1. separator/count/content consistency
  2. word count range (1-6 total) + per-chunk limits (1-3 for ;, 1-4 for |)
  3. headword-in-chunk (covers self-ref + leak)
  4. no-gloss bypass

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
        # This is fine — only exact match counts
        errs = validate_verdict('ball', 'basketball court', 'none', 1)
        assert errs == []


class TestWordCount:
    """Total 1-6 words; per-chunk limits."""

    def test_total_one_word_passes(self):
        # Rule A synonym-collapse: 1 word is allowed
        errs = validate_verdict('absurd', 'ridiculous', 'none', 1)
        assert errs == []

    def test_total_seven_words_fails(self):
        errs = validate_verdict('test', 'a b c d e f g', 'none', 1)
        assert any('word_count_out_of_range' in e for e in errs)

    def test_per_chunk_pipe_max_4(self):
        # '|': each side must be ≤4 words; 5 fails
        errs = validate_verdict('test', 'one two three four five | x', '|', 2)
        assert any('chunk_word_count[0]=5 > max=4' in e for e in errs)

    def test_per_chunk_pipe_max_4_passes_at_boundary(self):
        errs = validate_verdict('test', 'one two three four | five', '|', 2)
        # chunk[0] = 4 words OK (boundary); chunk[1] = 1 word OK
        assert not any('chunk_word_count' in e for e in errs)

    def test_per_chunk_semicolon_max_3(self):
        # ';': each side must be ≤3 words
        errs = validate_verdict('test', 'one two three four ; five', ';', 2)
        assert any('chunk_word_count[0]=4 > max=3' in e for e in errs)

    def test_per_chunk_pick1_max_6(self):
        # 'none': single chunk up to 6 words
        errs = validate_verdict('test', 'a b c d e f g', 'none', 1)
        assert any('word_count_out_of_range' in e for e in errs)


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
        errs = validate_verdict('test', ' '.join(['w'] * 100), 'none', 1, decision='no-gloss')
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
        # align|verb|C1: 'line up; align' — headword leak
        errs = validate_verdict('align', 'line up; align', ';', 2)
        assert any('headword_in_chunk[1]' in e for e in errs)

    def test_amid_chunk_too_long(self):
        # amid|preposition|C1: 'in the middle of; among' — chunk[0]=4 > max=3 for ;
        errs = validate_verdict('amid', 'in the middle of; among', ';', 2)
        assert any('chunk_word_count[0]=4 > max=3' in e for e in errs)

    def test_consultant_separator_mismatch(self):
        # consultant|noun|B2: 'subject expert; hospital specialist', '|' — declared | but actual ;
        errs = validate_verdict('consultant', 'subject expert; hospital specialist', '|', 2)
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
        assert any('headword_in_definition' in e for e in errs) or any('headword_in_phrase' in e for e in errs)

    def test_multi_word_related_derivative_passes(self):
        errs1 = validate_verdict('disabled', 'having disability', 'none', 1)
        assert errs1 == []

        errs2 = validate_verdict('differ', 'be different', 'none', 1)
        assert errs2 == []

    def test_idiom_phrase_prefix_passes(self):
        errs = validate_verdict('toss', 'toss: flip coin', 'none', 1)
        assert errs == []