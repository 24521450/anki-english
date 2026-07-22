from src.deck_builder.build_metadata import sync_semantic_identity_tag


SECONDARY_DECK = (
    "English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses"
)


def _denial_row(*, variant: str, deck_override: str | None) -> dict:
    return {
        "word": "denial",
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": variant,
        "pos": "noun",
        "deck_override": deck_override,
    }


def test_secondary_sense_tag_is_derived_from_registry_deck():
    assert sync_semantic_identity_tag(
        "Source::Oxford SenseVariant::stale",
        _denial_row(
            variant="secondary_entitlement_psychological",
            deck_override=SECONDARY_DECK,
        ),
    ) == "Source::Oxford SecondarySense"


def test_primary_semantic_variant_has_no_routing_tag():
    assert sync_semantic_identity_tag(
        "Source::Oxford SecondarySense",
        _denial_row(variant="primary", deck_override=None),
    ) == "Source::Oxford"


def test_non_secondary_reviewed_variant_uses_namespaced_tag():
    row = {
        "word": "temporal",
        "cefr": "UNCLASSIFIED",
        "list": "NO_LIST",
        "variant": "anatomy",
        "pos": "adjective",
        "deck_override": "English Academic Vocabulary::TED YT",
    }
    assert sync_semantic_identity_tag("Source::Oxford", row) == (
        "Source::Oxford SenseVariant::anatomy"
    )
