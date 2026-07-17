from __future__ import annotations

from src.deck_builder.sense_pos import (
    build_source_sense_pos_index,
    derive_sense_pos_cell,
    fallback_sense_pos,
    valid_sense_pos_cell,
)
from src.deck_builder.simplify_senses import _flatten_senses
from src.deck_builder.source_sense_identity import source_sense_id


def _record(source: str, pos: str, text: str) -> dict:
    return {
        "word": "yield",
        "source": source,
        "source_files": [f"{source}_yield.html"],
        "homonym_index": None,
        "oxford_badge": "B2",
        "pos_data": [{
            "pos": pos,
            "definitions": [{
                "text": text,
                "cefr": "B2",
                "sensenum_local": 1,
                "examples": [],
            }],
        }],
    }


def _sense_id(record: dict) -> str:
    return source_sense_id(record, _flatten_senses(record)[0])


def test_source_index_supports_oxford_and_cambridge_ids():
    oxford = _record("oxford", "noun", "an amount produced")
    cambridge = _record("cambridge", "verb", "to produce a result")

    index = build_source_sense_pos_index([oxford, cambridge])

    assert index == {
        _sense_id(oxford): ("noun",),
        _sense_id(cambridge): ("verb",),
    }
    assert _sense_id(oxford).startswith("ox_")
    assert _sense_id(cambridge).startswith("cam_")


def test_sense_cell_filters_and_orders_evidence_by_card_pos():
    index = {
        "ox-noun": ("noun",),
        "cam-verb": ("verb",),
        "ox-adjective": ("adjective",),
    }

    assert derive_sense_pos_cell(
        "noun, verb", ["cam-verb"], index
    ) == "verb"
    assert derive_sense_pos_cell(
        "noun, verb", ["cam-verb", "ox-noun"], index
    ) == "noun, verb"
    assert derive_sense_pos_cell(
        "noun, verb", ["ox-adjective", "unknown"], index
    ) == "noun, verb"


def test_legacy_fallback_repeats_card_pos_for_every_vi_sense():
    assert fallback_sense_pos("noun, verb", "nghĩa một|nghĩa hai") == (
        "noun, verb|noun, verb"
    )
    assert fallback_sense_pos("noun", "") == ""


def test_sense_pos_cell_must_be_a_canonical_ordered_card_subset():
    assert valid_sense_pos_cell("noun, verb", "noun")
    assert valid_sense_pos_cell("noun, verb", "noun, verb")
    assert not valid_sense_pos_cell("noun, verb", "verb, noun")
    assert not valid_sense_pos_cell("noun, verb", "adjective")
    assert not valid_sense_pos_cell("noun, verb", "")
