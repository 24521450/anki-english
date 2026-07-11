from __future__ import annotations

from collections import Counter

from tools.archive.data_migrations._apply_exact_source_cefr_rescue import (
    APPROXIMATE_PAYLOAD,
    TARGETS,
    Target,
    build_manual_row,
    prepare_updates,
)


def test_target_manifest_is_complete_and_keeps_harbour_out():
    assert len(TARGETS) == 37
    assert Counter(target.cefr for target in TARGETS.values()) == {
        "B2": 3,
        "C1": 9,
        "C2": 25,
    }
    assert "m}g1cKg({G" not in TARGETS


def test_approximate_becomes_a_cambridge_adjective_payload():
    target = TARGETS["q-l2t)2u|/"]
    registry = {
        "word": "approximate",
        "cefr": "UNCLASSIFIED",
        "list": "AWL",
        "variant": "",
        "pos": "verb",
    }
    card = {
        "definition": "verb definition",
        "example": "verb example",
        "collocations": "verb collocation",
        "ipa": "ipa",
        "uk_audio": "[sound:cambridge_uk_approximate.mp3]",
        "us_audio": "[sound:cambridge_us_approximate.mp3]",
    }

    manual = build_manual_row(registry, card, target)

    assert target == Target("approximate", "B2", "adjective")
    assert manual["definition"] == APPROXIMATE_PAYLOAD["Definition"]
    assert manual["example"].count("<br><br>") == 1
    assert manual["source1"] == "Cambridge"
    assert manual["tags"] == "Source::Cambridge CEFR::B2 CEFR::cambridge AWL_Coxhead"


def test_prepare_updates_changes_criterion_identity_and_preserves_guid_key():
    guid = '"L-#l1@LS<>"'
    registry = [{
        "guid": guid,
        "word": "criterion",
        "cefr": "UNCLASSIFIED",
        "list": "AWL",
        "variant": "",
        "pos": "noun",
        "status": "active",
        "deck_override": None,
    }]
    overrides = [{
        "guid": guid,
        "word": "criterion",
        "input_pos": "noun",
        "cefr": "UNCLASSIFIED",
        "Definition": "standard",
        "Example": "example",
        "Collocations": "criterion for sth",
        "output_pos": None,
    }]
    built = [{
        "guid": guid,
        "word": "criterion",
        "definition": "standard",
        "example": "example",
        "collocations": "criterion for sth",
        "ipa": "ipa",
        "uk_audio": "uk",
        "us_audio": "us",
    }]

    registry_updates, override_updates, manual = prepare_updates(
        registry, overrides, built, {guid: TARGETS[guid]}
    )

    assert registry_updates[guid]["cefr"] == "B2"
    assert registry_updates[guid]["list"] == "Oxford_3000"
    assert override_updates[guid]["cefr"] == "B2"
    assert manual[0]["source1"] == "Oxford"
    assert manual[0]["tags"].endswith("Oxford_3000")
