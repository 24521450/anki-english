import json
import re
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
    assert len(cards) == 2465
    # Only cards with a POS-owned idiom receive the payload/tag. The previous
    # count included idioms leaked across homonym/POS entry boundaries.
    assert sum(bool(card["idioms"]) for card in cards) == 369
    assert sum("idioms" in card["tags"].split() for card in cards) == 369
    assert all(
        bool(card["idioms"]) == ("idioms" in card["tags"].split())
        for card in cards
    )
    assert all(
        len([entry for entry in card["idioms"].split("$$") if entry.strip()]) <= 2
        for card in cards
    )
    for card in cards:
        seen_examples: set[str] = set()
        for entry in card["idioms"].split("$$") if card["idioms"] else []:
            parts = entry.split("::", 2)
            examples = [
                example.strip()
                for example in (parts[2] if len(parts) == 3 else "").split("|")
                if example.strip()
            ]
            assert len(examples) <= 1
            for example in examples:
                key = re.sub(r"\s+", " ", example).strip().casefold()
                assert key not in seen_examples
                seen_examples.add(key)

    implicate = next(
        card
        for card in cards
        if card["word"] == "implicate" and card["cefr"] == "UNCLASSIFIED"
    )
    assert implicate["idioms"].split(" :: ", 1)[0] == "be implicated in something"
    assert "idioms" in implicate["tags"].split()

    blink = next(card for card in cards if card["word"] == "blink of an eye")
    assert blink["idioms"] == ""
    assert "idioms" not in blink["tags"].split()


def test_curated_manual_idioms_keep_the_first_example():
    cards = [
        json.loads(line)
        for line in (ROOT / "data/build/anki_notes.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    by_word = {card["word"]: card for card in cards}

    expected = {
        "meantime": "My first novel was rejected by six publishers. In the meantime I had written a play.",
        "accordance": "in accordance with legal requirements",
    }
    for word, example in expected.items():
        assert example in by_word[word]["idioms"]
        assert "|" not in by_word[word]["idioms"].split("::", 2)[-1]


def test_blink_of_an_eye_manual_card_has_no_unrelated_idiom_box():
    cards = [
        json.loads(line)
        for line in (ROOT / "data/review/manual_cards.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    blink = next(card for card in cards if card["word"] == "blink of an eye")
    assert blink["idioms"] == ""
    assert "idioms" not in blink["tags"].split()
