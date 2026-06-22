"""Tests for P1 gloss engine — covering POS label strip, morphological
variant replacement, headword replacement, heuristic shortening, and the
explicit FIXES map."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder.gloss_p1 import (  # noqa: E402
    strip_pos_labels,
    shorten_chunk,
    shorten_gloss,
    fix_one,
    is_valid,
)


def test_strip_pos_labels_simple():
    assert strip_pos_labels('noun: wrong or harmful use') == 'wrong or harmful use'
    assert strip_pos_labels('verb: use wrongly') == 'use wrongly'
    assert strip_pos_labels('noun/verb: sudden attack') == 'sudden attack'


def test_strip_pos_labels_with_pipe():
    assert strip_pos_labels('noun: a thing|verb: to do something') == 'a thing|to do something'


def test_strip_pos_labels_no_match():
    assert strip_pos_labels('just a gloss') == 'just a gloss'
    assert strip_pos_labels('Agile: iterative method') == 'Agile: iterative method'


def test_shorten_chunk_under_limit():
    assert shorten_chunk('hello world', 4) == 'hello world'


def test_shorten_chunk_drops_stopwords():
    # "the" "a" "of" are stopwords; keep "big" "red" "house"
    assert shorten_chunk('the big red house', 4) == 'big red house'


def test_shorten_chunk_truncates():
    assert shorten_chunk('one two three four five', 3) == 'one two three'


def test_shorten_chunk_drops_parens():
    # "sudden surge (of something bad)" → "sudden surge"
    out = shorten_chunk('sudden surge (of something bad)', 4)
    assert out == 'sudden surge'


def test_shorten_gloss_pipe():
    out = shorten_gloss('move to a new place seasonally or permanently|transfer data/systems')
    # side 0: 8 → ≤4; side 1: 2
    assert is_valid('migrate', out)


def test_fix_one_pos_label():
    # abuse: noun: ... | verb: ...
    out = fix_one('abuse', 'noun, verb', 'C1',
                  'noun: wrong or harmful use; cruel treatment|verb: use wrongly|treat cruelly',
                  'the use of something in a way that is wrong or harmful')
    assert out is not None
    assert is_valid('abuse', out)


def test_fix_one_morphological_variant():
    out = fix_one('intent', 'noun', 'C1', 'intention', 'what you intend to do')
    assert out is not None
    assert is_valid('intent', out)
    # Should not contain 'intent' or 'intention'
    assert 'intent' not in out.lower().split()


def test_fix_one_headword_in_chunk():
    out = fix_one('hip', 'noun', 'B2', 'hip joint|side of the body at the waist',
                  'the area at either side of the body')
    assert out is not None
    assert is_valid('hip', out)
    # Should not contain 'hip'
    assert 'hip' not in out.lower().split()


def test_fix_one_explicit_override():
    out = fix_one('cult', 'adjective, noun', 'C1',
                  'noun: devoted following or extreme religious group|adj: having a cult following',
                  'very popular with a particular group of people')
    assert out == 'devoted following'
    assert is_valid('cult', out)


def test_fix_one_alert_avoids_dangling_to():
    out = fix_one('alert', 'adjective, noun, verb', 'C1',
                  'adj: watchful and quick to notice|noun: warning of danger|verb: warn of danger',
                  'able to think quickly; quick to notice things|a warning of danger')
    assert out == 'watchful|warning'
    assert is_valid('alert', out)


def test_fix_one_blast_keeps_clean_chunks():
    out = fix_one('blast', 'noun, verb', 'C1',
                  'noun: explosion or rush of air|verb: blow up|criticize harshly',
                  'an explosion or a powerful movement of air caused by an explosion|to violently destroy')
    assert out == 'explosion|blow up'
    assert is_valid('blast', out)


def test_fix_one_all_categories_pump():
    # pump: original has headword_in_definition + chunk_word_count
    out = fix_one('pump', 'noun, verb', 'C1',
                  'a device that forces liquid or gas through a pipe|to move liquid or gas using a pump',
                  'a machine that is used to force liquid')
    assert out is not None
    assert is_valid('pump', out)


def test_fix_one_aggressive_shortening():
    # glide through heuristic shortening
    out = fix_one('migrate', 'verb', 'C1',
                  'move to a new place seasonally or permanently|transfer data/systems',
                  'to move from one town, country, etc.')
    assert out is not None
    assert is_valid('migrate', out)


def test_is_valid_handles_self_ref():
    # Self-ref is a violation per validator
    assert not is_valid('pump', 'pump')


def test_is_valid_handles_long():
    # P5D (2026-06-22) removed word-count limits from `validate_verdict`.
    # Long glosses now PASS as long as structure + headword are clean.
    assert is_valid('test', 'one two three four five six seven')


def test_negations_preserved_in_shorten():
    # 'not' should not be dropped by shortening chunk
    out = shorten_chunk('not likely to change', 3)
    assert 'not' in out.split()
    assert out == 'not likely to'

    # If shortening would drop the negation, it must return the original chunk
    out2 = shorten_chunk('state governed by elected representatives, not a monarch', 3)
    assert out2 == 'state governed by elected representatives, not a monarch'


def test_is_valid_forbids_duplicate_chunks():
    assert not is_valid('adapt', 'change|change')
    assert not is_valid('test', 'adjust behavior|adjust behavior')
    assert is_valid('adapt', 'adjust behavior|modify for new use')


def test_is_valid_forbids_vague_chunks():
    # Single-word vague chunks are forbidden
    assert not is_valid('anchor', 'heavy')
    assert not is_valid('anchor', 'heavy|TV/radio')
    assert not is_valid('establishment', 'place')
    
    # Multi-word chunks containing vague words are allowed
    assert is_valid('anchor', 'heavy weight')
    assert is_valid('establishment', 'public institution')


def test_to_not_dropped_as_stopword():
    # 'to' should not be dropped, preserving infinitives and semantic phrases
    out = shorten_chunk('right to enter', 3)
    assert 'to' in out.split()
    assert out == 'right to enter'
