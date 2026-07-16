from __future__ import annotations

from src.deck_builder.formatting import format_idioms


def _idiom(
    phrase: str,
    cefr: str | None,
    examples: list[str] | None = None,
) -> dict:
    return {
        "phrase": phrase,
        "text": f"meaning of {phrase}",
        "examples": examples if examples is not None else [f"Example for {phrase}."],
        "cefr": cefr,
    }


def _phrases(value: str) -> list[str]:
    return [entry.split(" :: ", 1)[0] for entry in value.split("$$") if entry]


def _examples(value: str) -> list[str]:
    out: list[str] = []
    for entry in value.split("$$") if value else []:
        parts = entry.split(" :: ", 2)
        out.append(parts[2] if len(parts) == 3 else "")
    return out


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


def test_format_idioms_keeps_first_nonempty_example_only():
    value = format_idioms([
        _idiom("first", "C1", ["", "  First usable.  ", "Second usable."]),
    ])

    assert _examples(value) == ["First usable."]


def test_format_idioms_skips_card_local_duplicate_and_uses_next_oxford_example():
    idioms = [
        _idiom("first", "C1", ["Shared   sentence."]),
        _idiom("second", "C1", [" shared sentence. ", "Fallback sentence."]),
    ]

    value = format_idioms(idioms)

    assert _examples(value) == ["Shared   sentence.", "Fallback sentence."]
    assert idioms[1]["examples"] == [" shared sentence. ", "Fallback sentence."]


def test_format_idioms_keeps_punctuation_distinct_examples():
    value = format_idioms([
        _idiom("first", "C1", ["A statement."]),
        _idiom("second", "C1", ["A statement!"]),
    ])

    assert _examples(value) == ["A statement.", "A statement!"]


def test_format_idioms_keeps_idiom_without_example_when_all_candidates_duplicate():
    value = format_idioms([
        _idiom("first", "C1", ["Shared sentence."]),
        _idiom("second", "C1", [" shared  sentence. ", ""]),
    ])

    assert _phrases(value) == ["first", "second"]
    assert _examples(value) == ["Shared sentence.", ""]
