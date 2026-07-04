from __future__ import annotations

import pytest
from src.scraper.cambridge_audio import (
    normalize_word,
    normalize_pos,
    resolve_audio_pos,
    select_entry,
    get_audio_filename,
)
from src.deck_builder.build_support import resolve_audio_filename

def test_normalization():
    # Parenthetical removal
    assert normalize_word("strip (remove clothes/a layer)") == "strip"
    assert normalize_word("sake ") == "sake"
    assert normalize_word("Counter") == "counter"
    
    # POS normalization
    assert normalize_pos("noun") == "noun"
    assert normalize_pos("noun, verb") == "noun_verb"
    assert normalize_pos("verb/noun") == "verb_noun"
    assert normalize_pos("Adjective") == "adjective"
    assert resolve_audio_pos("converse", "adjective, noun, verb") == "verb"
    assert resolve_audio_pos("deposit", "noun, verb") == "noun, verb"

def test_select_entry_override_locks():
    entries = [
        {"headword": "counter", "pos": ["noun"], "uk_audio": "uk0", "us_audio": "us0"},
        {"headword": "counter", "pos": ["verb"], "uk_audio": "uk1", "us_audio": "us1"},
        {"headword": "counter", "pos": ["adjective"], "uk_audio": "uk2", "us_audio": "us2"},
    ]
    # counter|noun is entry 0
    res = select_entry("counter", "noun", entries)
    assert res == entries[0]
    
    entries_designate = [
        {"headword": "designate", "pos": ["verb"], "uk_audio": "uk0", "us_audio": "us0"},
        {"headword": "designate", "pos": ["adjective"], "uk_audio": "uk1", "us_audio": "us1"},
    ]
    # designate|adjective is entry 1
    res = select_entry("designate", "adjective", entries_designate)
    assert res == entries_designate[1]

    entries_mainland = [
        {"headword": "mainland", "pos": ["adjective"], "uk_audio": "uk0", "us_audio": "us0"},
        {"headword": "the mainland", "pos": ["noun"], "uk_audio": "uk1", "us_audio": "us1"},
    ]
    # mainland|noun is entry 1
    res = select_entry("mainland", "noun", entries_mainland)
    assert res == entries_mainland[1]

    entries_sake = [
        {"headword": "sake", "pos": ["noun"], "uk_audio": "uk0", "us_audio": "us0"},
        {"headword": "sake", "pos": ["noun"], "uk_audio": "uk1", "us_audio": "us1"},
        {"headword": "sake", "pos": ["noun"], "uk_audio": "uk2", "us_audio": "us2"},
    ]
    # sake|noun (Japanese) is entry 1
    res = select_entry("sake", "noun", entries_sake)
    assert res == entries_sake[1]

def test_select_entry_standard_prioritization():
    entries = [
        {"headword": "dynamic", "pos": ["adjective"], "uk_audio": None, "us_audio": "us0"},
        {"headword": "dynamic", "pos": ["noun"], "uk_audio": "uk1", "us_audio": "us1"},
        {"headword": "dynamic", "pos": ["adjective"], "uk_audio": "uk2", "us_audio": "us2"},
    ]
    # dynamic|adjective should choose Entry 2 because it has both UK/US audio
    res = select_entry("dynamic", "adjective", entries)
    assert res == entries[2]

def test_get_audio_filename():
    assert get_audio_filename("extract", "noun", "uk") == "cambridge_uk_extract_noun.mp3"
    assert get_audio_filename("deposit", "noun, verb", "us") == "cambridge_us_deposit_noun_verb.mp3"
    assert get_audio_filename("strip (remove clothes/a layer)", "verb", "uk") == "cambridge_uk_strip_verb.mp3"
    # sake index 2 override
    assert get_audio_filename("sake", "noun", "uk") == "cambridge_uk_sake_noun_2.mp3"

def test_builder_resolver_fallback():
    available = {
        "cambridge_uk_acid_noun.mp3",
        "cambridge_uk_alien.mp3",
    }
    # POS-specific exists
    assert resolve_audio_filename("acid", "noun", "uk", available) == "[sound:cambridge_uk_acid_noun.mp3]"
    # POS-specific does not exist, falls back to legacy (preserving word case)
    assert resolve_audio_filename("alien", "noun", "uk", available) == "[sound:cambridge_uk_alien.mp3]"
    assert resolve_audio_filename("Alien", "noun", "uk", available) == ""  # case sensitive check
    # Neither exists
    assert resolve_audio_filename("craft", "noun", "uk", available) == ""


def test_builder_resolver_prefers_oxford_over_tts_and_ignores_tts():
    available = {
        "tts_uk_craft.mp3",
        "oxford_uk_craft.mp3",
        "cambridge_uk_other.mp3",
    }

    assert resolve_audio_filename("craft", "noun", "uk", available) == "[sound:oxford_uk_craft.mp3]"
    assert resolve_audio_filename("other", "noun", "uk", {"tts_uk_other.mp3"}) == ""


def test_builder_resolver_uses_verb_audio_for_converse_card():
    available = {
        "cambridge_uk_converse.mp3",
        "cambridge_uk_converse_verb.mp3",
    }

    assert resolve_audio_filename(
        "converse", "adjective, noun, verb", "uk", available
    ) == "[sound:cambridge_uk_converse_verb.mp3]"
