from __future__ import annotations

from src.deck_builder.formatting import format_idioms


def _idiom(phrase: str, cefr: str | None) -> dict:
    return {
        "phrase": phrase,
        "text": f"meaning of {phrase}",
        "examples": [f"Example for {phrase}."],
        "cefr": cefr,
    }


def _phrases(value: str) -> list[str]:
    return [entry.split(" :: ", 1)[0] for entry in value.split("$$") if entry]


def test_format_idioms_keeps_up_to_two_entries_in_oxford_order_including_null_cefr():
    value = format_idioms([
        _idiom("first ungraded", None),
        _idiom("second graded", "C1"),
    ])

    assert _phrases(value) == ["first ungraded", "second graded"]


def test_format_idioms_prioritizes_cefr_then_oxford_order_when_more_than_two():
    value = format_idioms([
        _idiom("first ungraded", None),
        _idiom("first graded", "C1"),
        _idiom("second ungraded", None),
        _idiom("second graded", "B2"),
        _idiom("third graded", "C2"),
    ])

    assert _phrases(value) == ["first graded", "second graded"]


def test_format_idioms_fills_remaining_slot_from_first_ungraded_idiom():
    value = format_idioms([
        _idiom("first ungraded", None),
        _idiom("only graded", "C1"),
        _idiom("second ungraded", None),
    ])

    assert _phrases(value) == ["only graded", "first ungraded"]


def test_format_idioms_uses_first_two_oxford_entries_when_none_have_cefr():
    value = format_idioms([
        _idiom("first", None),
        _idiom("second", None),
        _idiom("third", None),
    ])

    assert _phrases(value) == ["first", "second"]
