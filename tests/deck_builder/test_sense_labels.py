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
    label_specs: list[dict] | None = None,
) -> MergedSense:
    if label_specs is None:
        label_specs = [
            {
                "source_definition": part.strip(),
                "register_tags": list(register_tags or []),
                "domain": domain,
            }
            for part in text.split(" ; ")
            if part.strip()
        ]
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
        label_specs=label_specs,
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
    senses = [
        _sense("cut violently"),
        _sense("cut greatly", register_tags=["informal", "formal"]),
    ]
    overrides = {
        "slash_guid": [
            {
                "guid": "slash_guid",
                "word": "slash",
                "pos": "verb",
                "cefr": "C1",
                "source_definition": "cut greatly",
                "definition_chunk": "cut greatly (cắt giảm mạnh)",
                "action": "apply",
                "labels": ["informal"],
            }
        ]
    }
    cards, errors = apply_sense_labels([card], {"slash_guid": senses}, overrides)
    assert errors == []
    assert cards[0].definition == "cut violently (rạch/chém)|[informal]cut greatly (cắt giảm mạnh)"


def test_override_invented_label_not_in_source_sense_raises_error():
    card = _card(
        word="slash",
        pos="verb",
        cefr="C1",
        definition="cut violently (rạch/chém)|cut greatly (cắt giảm mạnh)",
        guid="slash_guid",
    )
    senses = [
        _sense("cut violently"),
        _sense("cut greatly", register_tags=["formal"]),  # source sense only has 'formal'
    ]
    overrides = {
        "slash_guid": [
            {
                "guid": "slash_guid",
                "word": "slash",
                "pos": "verb",
                "cefr": "C1",
                "source_definition": "cut greatly",
                "definition_chunk": "cut greatly (cắt giảm mạnh)",
                "action": "apply",
                "labels": ["informal"],  # 'informal' is canonical but NOT owned by source sense
            }
        ]
    }
    cards, errors = apply_sense_labels([card], {"slash_guid": senses}, overrides)
    assert len(errors) == 1
    assert "label is not present on source definition" in errors[0]


def test_override_cannot_use_label_owned_by_other_source_definition():
    card = _card(definition="definition A|definition B", guid="merged_guid")
    sense = _sense(
        "definition A ; definition B",
        register_tags=["formal", "literary"],
        label_specs=[
            {"source_definition": "definition A", "register_tags": ["formal"], "domain": None},
            {"source_definition": "definition B", "register_tags": ["literary"], "domain": None},
        ],
    )
    overrides = {
        "merged_guid": [{
            "guid": "merged_guid",
            "word": "slash",
            "pos": "verb",
            "cefr": "C1",
            "source_definition": "definition A",
            "definition_chunk": "definition A",
            "action": "apply",
            "labels": ["literary"],
        }]
    }

    _, errors = apply_sense_labels([card], {"merged_guid": [sense]}, overrides)

    assert len(errors) == 1
    assert "label is not present on source definition" in errors[0]


def test_override_accepts_label_owned_by_exact_source_definition():
    card = _card(definition="definition A|definition B", guid="merged_guid")
    sense = _sense(
        "definition A ; definition B",
        register_tags=["formal", "literary"],
        label_specs=[
            {"source_definition": "definition A", "register_tags": ["formal"], "domain": None},
            {"source_definition": "definition B", "register_tags": ["literary"], "domain": None},
        ],
    )
    overrides = {
        "merged_guid": [{
            "guid": "merged_guid",
            "word": "slash",
            "pos": "verb",
            "cefr": "C1",
            "source_definition": "definition B",
            "definition_chunk": "definition B",
            "action": "apply",
            "labels": ["literary"],
        }]
    }

    cards, errors = apply_sense_labels([card], {"merged_guid": [sense]}, overrides)

    assert errors == []
    assert cards[0].definition == "definition A|[literary]definition B"


def test_override_legacy_sense_without_label_specs_uses_fallback():
    card = _card(definition="cut greatly", guid="legacy_guid")
    sense = _sense("cut greatly", register_tags=["informal"])._replace(label_specs=None)
    overrides = {
        "legacy_guid": [{
            "guid": "legacy_guid",
            "word": "slash",
            "pos": "verb",
            "cefr": "C1",
            "source_definition": "cut greatly",
            "definition_chunk": "cut greatly",
            "action": "apply",
            "labels": ["informal"],
        }]
    }

    cards, errors = apply_sense_labels([card], {"legacy_guid": [sense]}, overrides)

    assert errors == []
    assert cards[0].definition == "[informal]cut greatly"


def test_override_rejects_ambiguous_duplicate_source_definition_labels():
    card = _card(definition="same definition", guid="ambiguous_guid")
    sense = _sense(
        "same definition",
        register_tags=["formal", "literary"],
        label_specs=[
            {"source_definition": "same definition", "register_tags": ["formal"], "domain": None},
            {"source_definition": "same definition", "register_tags": ["literary"], "domain": None},
        ],
    )
    overrides = {
        "ambiguous_guid": [{
            "guid": "ambiguous_guid",
            "word": "slash",
            "pos": "verb",
            "cefr": "C1",
            "source_definition": "same definition",
            "definition_chunk": "same definition",
            "action": "apply",
            "labels": ["formal"],
        }]
    }

    _, errors = apply_sense_labels([card], {"ambiguous_guid": [sense]}, overrides)

    assert len(errors) == 1
    assert "Ambiguous source definition" in errors[0]


def test_skip_checks_labels_on_exact_source_definition():
    card = _card(definition="definition A|definition B", guid="merged_guid")
    sense = _sense(
        "definition A ; definition B",
        register_tags=["informal"],
        label_specs=[
            {"source_definition": "definition A", "register_tags": [], "domain": None},
            {"source_definition": "definition B", "register_tags": ["informal"], "domain": None},
        ],
    )
    overrides = {
        "merged_guid": [{
            "guid": "merged_guid",
            "word": "slash",
            "pos": "verb",
            "cefr": "C1",
            "source_definition": "definition A",
            "definition_chunk": "definition A",
            "action": "skip",
            "reason": "test exact source ownership",
        }]
    }

    _, errors = apply_sense_labels([card], {"merged_guid": [sense]}, overrides)

    assert len(errors) == 1
    assert "source definition has no labels to skip" in errors[0]


def test_override_source_definition_mismatch_raises_error():
    card = _card(
        word="slash",
        pos="verb",
        cefr="C1",
        definition="cut violently (rạch/chém)",
        guid="slash_guid",
    )
    senses = [_sense("cut violently")]
    overrides = {
        "slash_guid": [
            {
                "guid": "slash_guid",
                "word": "slash",
                "pos": "verb",
                "cefr": "C1",
                "source_definition": "completely wrong definition",
                "definition_chunk": "cut violently (rạch/chém)",
                "action": "apply",
                "labels": ["informal"],
            }
        ]
    }
    cards, errors = apply_sense_labels([card], {"slash_guid": senses}, overrides)
    assert len(errors) == 1
    assert "Source definition mismatch" in errors[0]


def test_override_substring_source_definition_fails_exact_match():
    """Substring matching is forbidden; source_definition must exact-match a source def."""
    card = _card(
        word="slash",
        pos="verb",
        cefr="C1",
        definition="cut violently (rạch/chém)",
        guid="slash_guid",
    )
    senses = [_sense("cut violently", register_tags=["informal"])]
    overrides = {
        "slash_guid": [
            {
                "guid": "slash_guid",
                "word": "slash",
                "pos": "verb",
                "cefr": "C1",
                "source_definition": "cut",  # substring of "cut violently", NOT exact
                "definition_chunk": "cut violently (rạch/chém)",
                "action": "apply",
                "labels": ["informal"],
            }
        ]
    }
    cards, errors = apply_sense_labels([card], {"slash_guid": senses}, overrides)
    assert len(errors) == 1
    assert "does not exact-match" in errors[0]


def test_override_unnecessary_skip_raises_error():
    card = _card(
        word="slash",
        pos="verb",
        cefr="C1",
        definition="cut violently (rạch/chém)",
        guid="slash_guid",
    )
    senses = [_sense("cut violently", register_tags=[])]  # no labels
    overrides = {
        "slash_guid": [
            {
                "guid": "slash_guid",
                "word": "slash",
                "pos": "verb",
                "cefr": "C1",
                "source_definition": "cut violently",
                "definition_chunk": "cut violently (rạch/chém)",
                "action": "skip",
                "reason": "testing unnecessary skip",
            }
        ]
    }
    cards, errors = apply_sense_labels([card], {"slash_guid": senses}, overrides)
    assert len(errors) == 1
    assert "Unnecessary 'skip' override" in errors[0]
