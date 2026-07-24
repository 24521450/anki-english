from __future__ import annotations

from src.deck_builder.card_identity import (
    LIST_PRIORITY,
    is_reviewed_identity_variant_allowed,
    primary_list_from_tags,
    reviewed_identity_variant,
)


def test_primary_list_from_tags_keeps_legacy_awl_token_by_default():
    assert LIST_PRIORITY == ("Oxford_5000", "Oxford_3000", "AWL_Coxhead")
    assert primary_list_from_tags("Source::Oxford AWL_Coxhead") == "AWL_Coxhead"


def test_primary_list_from_tags_can_canonicalize_awl():
    assert primary_list_from_tags("Source::Oxford AWL_Coxhead", canonical=True) == "AWL"
    assert primary_list_from_tags("Source::Oxford AWL", canonical=True) == "AWL"


def test_reviewed_identity_variants_cover_approved_pos_splits():
    assert reviewed_identity_variant("converse", "UNCLASSIFIED", "AWL", "verb") == "verb"
    assert reviewed_identity_variant("converse", "UNCLASSIFIED", "AWL", "adjective, noun") == "adjective, noun"
    assert reviewed_identity_variant("trail", "C1", "Oxford_5000", "noun") == "noun"
    assert reviewed_identity_variant("trail", "C1", "Oxford_5000", "verb") == "verb"
    assert reviewed_identity_variant("bow", "C1", "Oxford_5000", "noun, verb") == "noun, verb"
    assert reviewed_identity_variant("bow", "C1", "Oxford_5000", "noun") == "noun"
    assert reviewed_identity_variant("hint", "C1", "Oxford_5000", "noun") == "noun"
    assert reviewed_identity_variant("hint", "C1", "Oxford_5000", "verb") == "verb"
    assert reviewed_identity_variant("rally", "C1", "Oxford_5000", "noun") == "noun"
    assert reviewed_identity_variant("rally", "C1", "Oxford_5000", "verb") == "verb"
    assert is_reviewed_identity_variant_allowed(
        "proposition", "C1", "Oxford_5000", "noun", "primary"
    )
    assert is_reviewed_identity_variant_allowed(
        "proposition", "C1", "Oxford_5000", "noun", "secondary_law_formal"
    )
    assert not is_reviewed_identity_variant_allowed(
        "proposition", "C1", "Oxford_5000", "noun", "other"
    )
    assert reviewed_identity_variant("torture", "C1", "Oxford_5000", "noun") == ""
    assert reviewed_identity_variant("torture", "C1", "Oxford_5000", "verb") == ""


def test_temporal_reviewed_semantic_variants_are_allowed():
    assert is_reviewed_identity_variant_allowed(
        "temporal", "UNCLASSIFIED", "NO_LIST", "adjective", "general_formal"
    )
    assert is_reviewed_identity_variant_allowed(
        "temporal", "UNCLASSIFIED", "NO_LIST", "adjective", "anatomy"
    )
    assert not is_reviewed_identity_variant_allowed(
        "temporal", "UNCLASSIFIED", "NO_LIST", "adjective", ""
    )
    assert reviewed_identity_variant("firm", "B2", "Oxford_5000", "adjective") == ""


def test_contend_with_reviewed_secondary_variant_is_exactly_allowlisted():
    assert is_reviewed_identity_variant_allowed(
        "contend with sb/sth",
        "C1",
        "Oxford_5000",
        "phrasal verb",
        "secondary_phrasal_contend_with",
    )
    assert not is_reviewed_identity_variant_allowed(
        "contend with sb/sth", "C1", "Oxford_5000", "phrasal verb", ""
    )


def test_takenote_reviewed_semantic_variants_are_exactly_allowlisted():
    reviewed = (
        ("allowance", "noun", "secondary_child_allowance"),
        ("provision", "noun", "secondary_legal_condition"),
        ("worthy", "adjective", "secondary_typical_of"),
    )
    for word, pos, secondary in reviewed:
        assert is_reviewed_identity_variant_allowed(
            word, "C1", "Oxford_5000", pos, "primary"
        )
        assert is_reviewed_identity_variant_allowed(
            word, "C1", "Oxford_5000", pos, secondary
        )
        assert not is_reviewed_identity_variant_allowed(
            word, "C1", "Oxford_5000", pos, "secondary_other"
        )
