import json
from pathlib import Path

from src.deck_builder.build_metadata import sync_idioms_feature_tag


ROOT = Path(__file__).resolve().parents[2]


def test_sync_idioms_feature_tag_removes_tag_without_payload():
    assert sync_idioms_feature_tag(
        "Source::Oxford idioms CEFR::C1 Oxford_5000", ""
    ) == "Source::Oxford CEFR::C1 Oxford_5000"


def test_sync_idioms_feature_tag_adds_one_tag_for_payload():
    payload = "back and forth :: repeatedly"
    assert sync_idioms_feature_tag("Source::Oxford CEFR::C1", payload) == (
        "Source::Oxford CEFR::C1 idioms"
    )
    assert sync_idioms_feature_tag("idioms Source::Oxford idioms", payload) == (
        "Source::Oxford idioms"
    )


def test_production_cards_derive_idioms_tag_from_payload():
    cards = [
        json.loads(line)
        for line in (ROOT / "data/build/anki_notes.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert len(cards) == 2461
    assert sum(bool(card["idioms"]) for card in cards) == 410
    assert sum("idioms" in card["tags"].split() for card in cards) == 410
    assert all(
        bool(card["idioms"]) == ("idioms" in card["tags"].split())
        for card in cards
    )
    assert all(
        len([entry for entry in card["idioms"].split("$$") if entry.strip()]) <= 2
        for card in cards
    )

    implicate = next(
        card
        for card in cards
        if card["word"] == "implicate" and card["cefr"] == "UNCLASSIFIED"
    )
    assert implicate["idioms"].split(" :: ", 1)[0] == "be implicated in something"
    assert "idioms" in implicate["tags"].split()
