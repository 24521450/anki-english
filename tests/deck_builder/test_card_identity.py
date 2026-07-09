from __future__ import annotations

from src.deck_builder.card_identity import (
    LIST_PRIORITY,
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
    assert reviewed_identity_variant("torture", "C1", "Oxford_5000", "noun") == ""
    assert reviewed_identity_variant("torture", "C1", "Oxford_5000", "verb") == ""
    assert reviewed_identity_variant("firm", "B2", "Oxford_5000", "adjective") == ""
