from __future__ import annotations

import json

import pytest

from src.deck_builder.build_contracts import CARD_FIELDS, BuiltCard, serialize_jsonl, serialize_txt
from src.deck_builder.build_validation import (
    _parse_jsonl_cards,
    _parse_txt_cards,
    _validate_cards,
)
from src.deck_builder.card_identity import CardIdentity
from src.deck_builder.example_audio import plan_card_example_audio
from src.deck_builder.production import (
    apply_production_answers,
    count_production_cards,
    derive_production_answer,
    production_eligible,
)
from src.deck_builder.registry_build import RegistryTarget
from src.deck_builder.review_overrides import apply_review_overrides


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("grave (serious)", "grave"),
        ("counter (long flat surface)", "counter"),
        ("strip (remove clothes/a layer)", "strip"),
        ("derive from", "derive from"),
        ("devote sth to sth", "devote sth to sth"),
        ("refer to (sth)", "refer to (sth)"),
        ("keep to (oneself)", "keep to (oneself)"),
        ("  uphold  ", "uphold"),
        ("", ""),
    ],
)
def test_derive_production_answer_only_removes_display_qualifier(word, expected):
    assert derive_production_answer(word) == expected


@pytest.mark.parametrize(
    ("definition_vi", "example", "answer", "expected"),
    [
        ("nghiêm trọng", "A grave problem.", "grave", True),
        ("", "A grave problem.", "grave", False),
        ("nghiêm trọng", "", "grave", False),
        ("nghiêm trọng", "A grave problem.", "", False),
        ("  ", "A grave problem.", "grave", False),
    ],
)
def test_production_eligibility_requires_all_three_fields(
    definition_vi, example, answer, expected
):
    assert production_eligible(definition_vi, example, answer) is expected


def test_count_production_cards_accepts_build_rows_and_json_rows():
    eligible = _card(production_answer="grave")
    ineligible = _card(
        guid="idiom-only",
        definition="",
        definition_vi="",
        example="",
        idioms="phrase :: meaning :: example",
        production_answer="phrase",
    )

    assert count_production_cards([eligible, ineligible]) == 1
    assert count_production_cards([eligible.to_dict(), ineligible.to_dict()]) == 1


def _card(**overrides) -> BuiltCard:
    values = {
        "guid": "guid-grave",
        "notetype": "English Academic Vocabulary Model",
        "deck": "Deck",
        "word": "grave (serious)",
        "pos": "adjective",
        "ipa": "",
        "definition": "very serious (nghiêm trọng)",
        "example": "A grave problem.",
        "collocations": "",
        "wordfamily": "",
        "uk_audio": "",
        "us_audio": "",
        "source1": "Oxford",
        "source2": "Oxford",
        "cefr": "C1",
        "idioms": "",
        "tags": "Source::Oxford CEFR::C1 CEFR::oxford",
        "synonyms": "",
        "antonyms": "",
        "definition_vi": "nghiêm trọng",
        "cambridge_url": "https://dictionary.cambridge.org/dictionary/english/grave",
        "sense_pos": "adjective",
    }
    values.update(overrides)
    return BuiltCard(**values)


def test_production_answer_is_appended_without_reordering_existing_contract():
    assert CARD_FIELDS[-6:] == (
        "definition_vi",
        "cambridge_url",
        "oxford_pos_urls",
        "production_answer",
        "sense_pos",
        "idiom_meaning_vi",
    )

    card = apply_production_answers([_card()])[0]
    json_row = json.loads(serialize_jsonl([card]))
    txt_row = serialize_txt([card]).splitlines()[-1].split("\t")

    assert json_row["production_answer"] == "grave"
    assert json_row["sense_pos"] == "adjective"
    assert txt_row[-3:] == ["grave", "adjective", ""]
    assert len(txt_row) == len(CARD_FIELDS)
    assert production_eligible(card)


@pytest.mark.parametrize("removed_columns", [1, 2, 3])
def test_legacy_txt_is_readable_but_not_canonical_serialization(removed_columns):
    card = apply_production_answers([_card()])[0]
    canonical = serialize_txt([card])
    lines = canonical.splitlines()
    lines[-1] = "\t".join(lines[-1].split("\t")[:-removed_columns])
    legacy = "\n".join(lines) + "\n"

    parsed, issues = _parse_txt_cards(legacy, "legacy-fixture")

    assert not issues
    assert parsed == [card]
    assert serialize_txt(parsed) == canonical
    assert legacy != canonical


@pytest.mark.parametrize(
    "removed_fields",
    [
        ("idiom_meaning_vi",),
        ("sense_pos", "idiom_meaning_vi"),
        ("production_answer", "sense_pos", "idiom_meaning_vi"),
    ],
)
def test_legacy_jsonl_is_readable_but_not_canonical_serialization(removed_fields):
    card = apply_production_answers([_card()])[0]
    row = card.to_dict()
    for field in removed_fields:
        row.pop(field)
    legacy = json.dumps(row, ensure_ascii=False) + "\n"

    parsed, issues = _parse_jsonl_cards(legacy, "legacy-fixture")

    assert not issues
    assert parsed == [card]
    assert serialize_jsonl(parsed) == serialize_jsonl([card])
    assert legacy != serialize_jsonl([card])


def test_apply_production_answers_is_order_preserving_and_deterministic():
    cards = [
        _card(guid="first", word="derive from"),
        _card(guid="second", word="grave (serious)"),
    ]

    first = apply_production_answers(cards)
    second = apply_production_answers(cards)

    assert [card.guid for card in first] == ["first", "second"]
    assert [card.production_answer for card in first] == ["derive from", "grave"]
    assert serialize_jsonl(first) == serialize_jsonl(second)
    assert serialize_txt(first) == serialize_txt(second)


def test_review_override_preserves_appended_metadata_fields():
    card = _card(
        production_answer="grave",
        sense_pos="adjective",
        idiom_meaning_vi="bilingual_gloss :: nghĩa",
    )
    updated = apply_review_overrides(
        [card],
        {
            card.guid: {
                "guid": card.guid,
                "word": card.word,
                "cefr": card.cefr,
                "input_pos": card.pos,
                "output_pos": card.pos,
                "Definition": "reviewed definition (nghiêm trọng)",
            }
        },
    )[0]

    assert updated.production_answer == "grave"
    assert updated.sense_pos == "adjective"
    assert updated.idiom_meaning_vi == "bilingual_gloss :: nghĩa"


def _production_validation_codes(card: BuiltCard) -> set[str]:
    card, _ = plan_card_example_audio(card)
    identity = CardIdentity(card.word, card.cefr, "NO_LIST", "")
    target = RegistryTarget(
        row={
            "word": card.word,
            "cefr": card.cefr,
            "list": "NO_LIST",
            "variant": "",
            "pos": card.pos,
            "guid": card.guid,
            "status": "active",
            "deck_override": card.deck,
        },
        identity=identity,
    )
    return {
        issue.code
        for issue in _validate_cards([card], [target], {identity.as_key(): target})
    }


def test_build_validation_requires_recomputed_production_answer():
    assert "production_answer_missing" in _production_validation_codes(_card())
    assert "production_answer_mismatch" in _production_validation_codes(
        _card(production_answer="cemetery")
    )
    assert not {
        "production_answer_missing",
        "production_answer_mismatch",
    } & _production_validation_codes(_card(production_answer="grave"))
