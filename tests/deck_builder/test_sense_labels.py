import pytest
from src.deck_builder.build_notes import BuiltCard
from src.deck_builder.simplify_senses import MergedSense
from src.deck_builder.sense_labels import (
    format_label_prefix,
    parse_existing_prefix,
    check_register_conflicts,
    apply_sense_labels,
    load_sense_label_overrides,
)


def _card(
    word: str = "slash",
    pos: str = "verb",
    cefr: str = "C1",
    definition: str = "cut violently (rạch/chém)|cut greatly (cắt giảm mạnh)",
    guid: str = "12345",
) -> BuiltCard:
    return BuiltCard(
        guid=guid,
        notetype="EAVM",
        deck="Oxford",
        word=word,
        pos=pos,
        ipa="...",
        definition=definition,
        example="...",
        collocations="...",
        wordfamily="...",
        uk_audio="...",
        us_audio="...",
        source1="Oxford",
        source2="Oxford",
        cefr=cefr,
        idioms="...",
        tags="...",
        synonyms="",
        antonyms="",
    )


def _sense(
    text: str,
    register_tags: list[str] | None = None,
    domain: str | None = None,
) -> MergedSense:
    return MergedSense(
        pos="verb",
        cefr="C1",
        text=text,
        register_tags=register_tags or [],
        topics=[],
        collocations={},
        examples=[],
        countability=None,
        domain=domain,
        is_phrase=False,
        is_idiom=False,
        source_pdd_idx=[0],
        source_def_idx=[0],
        cefr_originals=["C1"],
        cefr_sources=["oxford"],
    )


def test_format_label_prefix():
    assert format_label_prefix(["informal"], None) == "[informal]"
    assert format_label_prefix(["informal"], "law") == "[informal, law]"
    assert format_label_prefix([], "law") == "[law]"
    assert format_label_prefix([], None) == ""


def test_parse_existing_prefix():
    labels, rest = parse_existing_prefix("[informal] cut greatly (cắt giảm mạnh)")
    assert labels == ["informal"]
    assert rest == "cut greatly (cắt giảm mạnh)"

    labels, rest = parse_existing_prefix("cut violently (rạch/chém)")
    assert labels == []
    assert rest == "cut violently (rạch/chém)"


def test_check_register_conflicts():
    assert check_register_conflicts(["formal", "informal"]) is not None
    assert check_register_conflicts(["formal", "slang"]) is not None
    assert check_register_conflicts(["approving", "disapproving"]) is not None
    assert check_register_conflicts(["informal", "literary"]) is None


def test_apply_sense_labels_slash_one_to_one():
    card = _card(
        word="slash",
        pos="verb",
        cefr="C1",
        definition="cut violently (rạch/chém)|cut greatly (cắt giảm mạnh)",
        guid="slash_guid",
    )
    senses = [
        _sense("cut violently"),
        _sense("cut greatly", register_tags=["informal"]),
    ]
    cards, errors = apply_sense_labels([card], {"slash_guid": senses}, {})
    assert errors == []
    assert len(cards) == 1
    assert cards[0].definition == "cut violently (rạch/chém)|[informal]cut greatly (cắt giảm mạnh)"


def test_apply_sense_labels_idempotency():
    card = _card(
        word="slash",
        pos="verb",
        cefr="C1",
        definition="cut violently (rạch/chém)|[informal]cut greatly (cắt giảm mạnh)",
        guid="slash_guid",
    )
    senses = [
        _sense("cut violently"),
        _sense("cut greatly", register_tags=["informal"]),
    ]
    cards, errors = apply_sense_labels([card], {"slash_guid": senses}, {})
    assert errors == []
    assert cards[0].definition == "cut violently (rạch/chém)|[informal]cut greatly (cắt giảm mạnh)"


def test_apply_sense_labels_conflict_requires_override():
    card = _card(
        word="testword",
        pos="verb",
        cefr="C1",
        definition="single chunk definition (bản dịch)",
        guid="test_guid",
    )
    senses = [
        _sense("sense 1", register_tags=["formal", "informal"]),
    ]
    cards, errors = apply_sense_labels([card], {"test_guid": senses}, {})
    assert len(errors) == 1
    assert "Hard conflict detected" in errors[0]


def test_apply_sense_labels_with_manual_override():
    card = _card(
        word="slash",
        pos="verb",
        cefr="C1",
        definition="cut violently (rạch/chém)|cut greatly (cắt giảm mạnh)",
        guid="slash_guid",
    )
    overrides = {
        "slash_guid": [
            {
                "guid": "slash_guid",
                "word": "slash",
                "pos": "verb",
                "cefr": "C1",
                "definition_chunk": "cut greatly (cắt giảm mạnh)",
                "action": "apply",
                "labels": ["informal"],
            }
        ]
    }
    cards, errors = apply_sense_labels([card], {}, overrides)
    assert errors == []
    assert cards[0].definition == "cut violently (rạch/chém)|[informal]cut greatly (cắt giảm mạnh)"
