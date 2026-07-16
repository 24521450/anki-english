from __future__ import annotations

import json

import pytest

from src.deck_builder.build_issues import BuildValidationError
from src.deck_builder.manual_cards import (
    serialize_manual_cards_rows,
    validate_manual_cards_or_raise,
    validate_manual_cards_rows,
)


def _manual_row(word: str = "yield", definition: str = "output") -> dict:
    return {
        "word": word,
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": "",
        "definition": definition,
        "example": "Higher-rate deposit accounts yield good returns.",
        "collocations": "high/low crop yield",
        "wordfamily": "",
        "ipa": "/jiːld/",
        "uk_audio": "[sound:cambridge_uk_yield.mp3]",
        "us_audio": "[sound:cambridge_us_yield.mp3]",
        "source1": "Oxford",
        "source2": "Oxford",
        "idioms": "",
        "provenance": {"source": "manual_card_fills", "ledger_pos": "noun"},
    }


def test_serialize_manual_cards_rows_uses_canonical_jsonl():
    rows = [_manual_row()]
    text = serialize_manual_cards_rows(rows)
    assert [json.loads(line) for line in text.splitlines()] == rows


def test_validate_manual_cards_rows_rejects_bad_provenance():
    row = _manual_row("x")
    row["provenance"] = {"source": "other", "ledger_pos": ""}
    issues = validate_manual_cards_rows([row])
    assert any(issue.code == "invalid_provenance_source" for issue in issues)
    assert any(issue.code == "invalid_ledger_pos" for issue in issues)


def test_validate_manual_cards_or_raise_rejects_duplicates():
    with pytest.raises(BuildValidationError):
        validate_manual_cards_or_raise([_manual_row("x", "one"), _manual_row("x", "two")])


def test_validate_manual_cards_rows_rejects_multiple_examples_per_idiom():
    row = _manual_row()
    row["idioms"] = "phrase :: meaning :: First.|Second."

    issues = validate_manual_cards_rows([row])

    assert any(issue.code == "idiom_example_limit_exceeded" for issue in issues)


def test_validate_manual_cards_rows_rejects_duplicate_examples_between_idioms():
    row = _manual_row()
    row["idioms"] = (
        "first :: meaning :: Shared   sentence.$$"
        "second :: meaning :: shared sentence."
    )

    issues = validate_manual_cards_rows([row])

    assert any(issue.code == "idiom_example_duplicate" for issue in issues)
