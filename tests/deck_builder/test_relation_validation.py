from __future__ import annotations

from src.deck_builder.relation_validation import validate_lexical_relation_metadata


def _codes(example: str, synonyms: str = "", antonyms: str = "") -> set[str]:
    return {
        issue.code
        for issue in validate_lexical_relation_metadata(example, synonyms, antonyms)
    }


def test_union_metadata_may_be_rendered_by_separate_subset_parentheticals():
    issues = validate_lexical_relation_metadata(
        "Food passes through the gut (intestine).<br><br>"
        "He had a bit of a gut (belly) on him.",
        "intestine, belly",
        "",
    )

    assert issues == ()


def test_nonempty_metadata_must_be_pipe_aligned_with_example():
    assert "relation_metadata_alignment" in _codes(
        "First example (plain).|Second example.",
        "plain",
    )


def test_every_metadata_term_must_have_a_renderable_parenthetical():
    assert "relation_metadata_unrepresented" in _codes(
        "The result was clear.",
        "plain",
    )


def test_cross_channel_overlap_and_ambiguous_parenthetical_are_rejected():
    codes = _codes(
        "The result was clear (plain).",
        "plain",
        "plain",
    )

    assert "relation_channel_overlap" in codes
    assert "relation_channel_ambiguous" in codes


def test_mixed_parenthetical_intersecting_metadata_is_rejected():
    assert "relation_annotation_unrenderable" in _codes(
        "The result was clear (plain, unrelated).",
        "plain",
    )


def test_unrelated_natural_parenthetical_is_ignored():
    issues = validate_lexical_relation_metadata(
        "Use the rule (= if applicable) when the meaning is relevant (pertinent).",
        "pertinent",
        "",
    )

    assert issues == ()
