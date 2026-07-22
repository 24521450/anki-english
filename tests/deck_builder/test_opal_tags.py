from __future__ import annotations

import pytest

from src.deck_builder.build_contracts import BuiltCard
from src.deck_builder.opal_tags import apply_opal_tags, build_opal_index


def _record(word: str, pos: list[str], opal: dict[str, list[str]] | None) -> dict:
    return {
        "word": word,
        "pos": pos,
        "pos_data": [{"pos": item} for item in pos],
        "opal": opal,
    }


def _card(
    word: str,
    pos: str,
    *,
    source1: str = "Oxford",
    tags: str = "Source::Oxford CEFR::C1 Oxford_5000",
) -> BuiltCard:
    return BuiltCard(
        guid=f"guid-{word}-{pos}",
        notetype="English Academic Vocabulary Model",
        deck="English Academic Vocabulary::Oxford",
        word=word,
        pos=pos,
        ipa="",
        definition="definition",
        example="example",
        collocations="",
        wordfamily="",
        uk_audio="",
        us_audio="",
        source1=source1,
        source2="Oxford",
        cefr="C1",
        idioms="",
        tags=tags,
        synonyms="",
        antonyms="",
    )


def test_apply_opal_tags_is_pos_scoped_and_uses_canonical_order():
    records = [
        _record("accordingly", ["adverb"], {"adverb": ["W"]}),
        _record("adapt", ["verb"], {"verb": ["W", "S"]}),
        _record("trace", ["noun", "verb"], {"noun": ["S"]}),
        _record("reference", ["noun", "verb"], {"noun": ["W", "S"]}),
        _record("total", ["adjective", "noun", "verb"], {
            "adjective": ["W", "S"],
            "noun": ["W", "S"],
        }),
        _record("derive", ["verb", "phrasal verb"], {"verb": ["W", "S"]}),
    ]
    cards = [
        _card("accordingly", "adverb"),
        _card("adapt", "verb", tags="OPAL_S Source::Oxford OPAL_W CEFR::B2"),
        _card("trace", "noun"),
        _card("trace", "verb", tags="Source::Oxford OPAL_W CEFR::B2"),
        _card("reference", "verb"),
        _card("total", "verb"),
        _card("derive from", "phrasal verb"),
    ]

    updated = apply_opal_tags(cards, build_opal_index(records))

    assert updated[0].tags == "Source::Oxford CEFR::C1 Oxford_5000 OPAL_W"
    assert updated[1].tags == "Source::Oxford CEFR::B2 OPAL_W OPAL_S"
    assert updated[2].tags.endswith("OPAL_S")
    assert "OPAL_" not in updated[3].tags
    assert "OPAL_" not in updated[4].tags
    assert "OPAL_" not in updated[5].tags
    assert updated[6].tags.endswith("OPAL_W OPAL_S")


def test_apply_opal_tags_strips_stale_tags_from_non_oxford_cards():
    card = _card(
        "accordingly",
        "adverb",
        source1="Cambridge",
        tags="Source::Cambridge OPAL_W OPAL_S CEFR::C1",
    )
    index = build_opal_index([
        _record("accordingly", ["adverb"], {"adverb": ["W"]}),
    ])

    updated = apply_opal_tags([card], index)

    assert updated[0].tags == "Source::Cambridge CEFR::C1"


def test_opal_lookup_fails_closed_when_same_word_pos_candidates_disagree():
    index = build_opal_index([
        _record("content", ["noun"], {"noun": ["W"]}),
        _record("content", ["noun"], None),
    ])

    with pytest.raises(ValueError, match=r"ambiguous OPAL membership.*content.*noun"):
        apply_opal_tags([_card("content", "noun")], index)


def test_unreferenced_opal_ambiguity_does_not_block_other_cards():
    index = build_opal_index([
        _record("content", ["noun"], {"noun": ["W"]}),
        _record("content", ["noun"], None),
        _record("accordingly", ["adverb"], {"adverb": ["W"]}),
    ])

    updated = apply_opal_tags([_card("accordingly", "adverb")], index)

    assert updated[0].tags.endswith("OPAL_W")


def test_opal_index_ignores_related_entry_pos_noise():
    index = build_opal_index([{
        "word": "reference",
        "pos": ["noun", "verb"],
        "pos_data": [{"pos": "noun"}],
        "opal": {"noun": ["W", "S"]},
    }])

    assert index[("reference", "noun")] == frozenset({("W", "S")})
    assert ("reference", "verb") not in index


@pytest.mark.parametrize("opal", [{}, {"verb": []}, {"verb": ["S", "W"]}])
def test_opal_index_rejects_noncanonical_source_metadata(opal):
    with pytest.raises(ValueError, match="invalid OPAL"):
        build_opal_index([_record("adapt", ["verb"], opal)])
