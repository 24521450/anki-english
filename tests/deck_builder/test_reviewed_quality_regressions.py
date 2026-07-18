from __future__ import annotations

import json
import re
from collections import Counter

from src.config import ProjectPaths
from src.deck_builder.sense_labels import parse_existing_prefix
from src.deck_builder.synonym_annotator import strip_synonym_annotations


PATHS = ProjectPaths()
EXACT_SOURCE_STATUS = "exact_source_cefr_rescue_20260710"
SEMANTIC_GROUPING_STATUS = "semantic_overload_grouped_20260711"
SENSE_GROUPING_STATUS = "sense_grouping_review_20260711"
VIETNAMESE_PRECISION_STATUS = "vietnamese_gloss_precision_review_20260711"


def _load(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _canonical_rows():
    return {
        "audit": _load(PATHS.deck_audit_jsonl),
        "reviews": _load(PATHS.non_oxford_non_c2_overrides),
        "manuals": _load(PATHS.manual_cards),
        "registry": _load(PATHS.card_registry),
        "semantic_registry": _load(PATHS.semantic_registry),
        "collocation_registry": _load(PATHS.collocation_registry),
        "cards": _load(PATHS.anki_notes_jsonl),
    }


def _manual_key(row):
    return row["word"], row["cefr"], row["list"], row.get("variant") or ""


def _card_for_owner(owner: dict, cards: list[dict]) -> dict:
    if owner.get("guid"):
        return next(card for card in cards if card["guid"] == owner["guid"])

    owner_pos = {part.strip() for part in owner["pos"].split(",")}
    matches = [
        card
        for card in cards
        if card["word"] == owner["word"]
        and card["cefr"] == owner["cefr"]
        and owner_pos.issubset({part.strip() for part in card["pos"].split(",")})
    ]
    assert len(matches) == 1, owner["word"]
    return matches[0]


def _definition_without_labels(definition: str) -> str:
    return "|".join(parse_existing_prefix(chunk)[1] for chunk in definition.split("|"))


def _registry_definition(registry_row: dict) -> str:
    return "|".join(
        f"{sense['definition_en']} ({sense['definition_vi']})"
        for sense in registry_row["senses"]
    )


def _registry_examples(registry_row: dict) -> list[list[str]]:
    return [list(sense["examples"]) for sense in registry_row["senses"]]


def _relation_terms(card: dict) -> list[str]:
    terms = []
    for field in (card["synonyms"], card["antonyms"]):
        for part in re.split(r"\||<br\s*/?><br\s*/?>|,", field, flags=re.IGNORECASE):
            part = part.strip()
            if part and part not in terms:
                terms.append(part)
    return terms


def _split_example_sentences(value: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"<br\s*/?>\s*<br\s*/?>", value, flags=re.IGNORECASE)
        if part.strip()
    ]


def _assert_registry_payload(registry_row: dict, card: dict) -> None:
    """Assert production semantics against the promoted registry.

    Relation annotations are a presentation layer added after registry
    promotion.  Strip only those annotations while comparing each semantic
    sentence independently, preserving sense and example ordering/counts.
    """
    assert card["definition"] == _registry_definition(registry_row)
    relation_terms = _relation_terms(card)
    expected_senses = _registry_examples(registry_row)
    if not expected_senses:
        assert card["example"] == ""
        return
    actual_senses = [
        _split_example_sentences(chunk) for chunk in card["example"].split("|")
    ]
    assert len(actual_senses) == len(expected_senses)
    for actual, expected in zip(actual_senses, expected_senses):
        assert len(actual) == len(expected)
        for actual_sentence, expected_sentence in zip(actual, expected):
            assert strip_synonym_annotations(actual_sentence, relation_terms).strip() == (
                strip_synonym_annotations(expected_sentence, relation_terms).strip()
            )


def _assert_owner_payload(
    owner: dict,
    card: dict,
    semantic_registry_rows: list[dict],
    collocation_registry_rows: list[dict],
) -> None:
    # ADR 0024 makes the Collocation Registry the final owner, so the older
    # rescue/grouping ledgers no longer own their embedded collocation literal.
    collocation_row = next(
        row for row in collocation_registry_rows if row["guid"] == card["guid"]
    )
    items = sorted(collocation_row["items"], key=lambda item: item["order"])
    assert card["collocations"] == "|".join(item["text"] for item in items)
    assert card["collocation_sources"] == "|".join(
        item["source"] for item in items
    )
    registry_row = next(
        row for row in semantic_registry_rows if row["guid"] == card["guid"]
    )
    _assert_registry_payload(registry_row, card)


def test_exact_source_cefr_rescue_is_owned_by_canonical_inputs():
    rows = _canonical_rows()
    registry = {row["guid"]: row for row in rows["registry"]}
    cards = {row["guid"]: row for row in rows["cards"]}
    manuals = {_manual_key(row): row for row in rows["manuals"]}
    rescued = [
        row for row in rows["reviews"] if row.get("fix_status") == EXACT_SOURCE_STATUS
    ]

    assert len(rescued) == 37
    assert Counter(row["cefr"] for row in rescued) == {"B2": 3, "C1": 9, "C2": 25}
    for owner in rescued:
        reg = registry[owner["guid"]]
        manual = manuals[_manual_key(reg)]
        card = cards[owner["guid"]]
        assert manual["provenance"]["review_batch"] == EXACT_SOURCE_STATUS
        assert (card["word"], card["cefr"], card["pos"]) == (
            reg["word"], reg["cefr"], reg["pos"]
        )
        assert card["uk_audio"] and card["us_audio"]

    approximate = cards["q-l2t)2u|/"]
    approximate_manual = manuals[_manual_key(registry["q-l2t)2u|/"])]
    # The promoted Semantic Registry now owns the concise bilingual payload;
    # this card intentionally replaces the old mechanical “gần đúng/xấp xỉ”
    # pair with the reviewed lexical gloss “xấp xỉ”.
    assert approximate["definition"] == "not completely accurate but close (xấp xỉ)"
    assert approximate["example"] == approximate_manual["example"]
    assert approximate["source1"] == "Cambridge"
    assert "CEFR::cambridge" in approximate["tags"]
    assert cards["L-#l1@LS<>"]["deck"].endswith("Oxford 3000 Advanced")
    assert cards["m}g1cKg({G"]["cefr"] == "UNCLASSIFIED"


def test_semantic_overload_grouping_matches_canonical_owner_payloads():
    rows = _canonical_rows()
    owners = [
        row for row in rows["audit"] if row.get("fix_status") == SEMANTIC_GROUPING_STATUS
    ] + [
        row for row in rows["reviews"] if row.get("fix_status") == SEMANTIC_GROUPING_STATUS
    ]
    assert len(owners) == 10

    expected_relations = {
        "appreciation": ("||", "||"),
        "clash": ("conflict||", "||"),
        "critical": ("|crucial|", "||"),
        "gut": ("intestine, belly||", "||"),
        "harsh": ("||", "|soft|"),
        "humanity": ("||", "|inhumanity|"),
        "identification": ("||", "||"),
        "pop": ("||", "||"),
        "provision": ("||", "||"),
        "sterile": ("fruitless||", "||"),
    }
    for owner in owners:
        card = _card_for_owner(owner, rows["cards"])
        _assert_owner_payload(
            owner,
            card,
            rows["semantic_registry"],
            rows["collocation_registry"],
        )
        semantic_row = next(
            row for row in rows["semantic_registry"] if row["guid"] == card["guid"]
        )
        assert len(card["definition"].split("|")) == len(semantic_row["senses"])
        assert len(card["example"].split("|")) == len(semantic_row["senses"])
        expected_synonyms, expected_antonyms = expected_relations[card["word"]]
        assert {
            part.strip() for part in card["synonyms"].split("|") if part.strip()
        } == {
            part.strip() for part in expected_synonyms.split("|") if part.strip()
        }
        assert {
            part.strip() for part in card["antonyms"].split("|") if part.strip()
        } == {
            part.strip() for part in expected_antonyms.split("|") if part.strip()
        }


def test_sense_grouping_review_matches_canonical_owner_payloads():
    rows = _canonical_rows()
    owners = [
        row
        for row in rows["audit"]
        if row.get("fix_status") == SENSE_GROUPING_STATUS
        or row.get("sense_grouping_status") == SENSE_GROUPING_STATUS
    ] + [
        row
        for row in rows["reviews"]
        if row.get("fix_status") == SENSE_GROUPING_STATUS
        or row.get("sense_grouping_status") == SENSE_GROUPING_STATUS
    ]
    assert Counter("audit" if "gloss_after" in row else "review" for row in owners) == {
        "audit": 32,
        "review": 13,
    }
    for owner in owners:
        _assert_owner_payload(
            owner,
            _card_for_owner(owner, rows["cards"]),
            rows["semantic_registry"],
            rows["collocation_registry"],
        )

    registry = {_manual_key(row): row for row in rows["registry"]}
    cards = {row["guid"]: row for row in rows["cards"]}
    temporal_manuals = [
        row
        for row in rows["manuals"]
        if (row.get("provenance") or {}).get("review_batch") == SENSE_GROUPING_STATUS
    ]
    assert len(temporal_manuals) == 2
    for manual in temporal_manuals:
        reg = registry[_manual_key(manual)]
        card = cards[reg["guid"]]
        assert card["definition"] == manual["definition"]
        assert card["uk_audio"] and card["us_audio"]

    assert "blK!z$J^4}" not in cards
    assert "OZZPa?0t@2" not in cards
    assert "SenseVariant::general_formal" in cards["fxDIz0`1%."]["tags"]
    assert "SenseVariant::anatomy" in cards["t3mpAnat01"]["tags"]
    for guid in {"5h{~9ioTEb", "/xUiXso]~Q", "D0tq!F6I2+", "Hd?Kj:WO(B", "NQD8xUt1~7", "s>o7[6qaNE"}:
        assert guid in cards


def test_vietnamese_precision_review_matches_canonical_owner_payloads():
    rows = _canonical_rows()
    owners = [
        row
        for row in [*rows["audit"], *rows["reviews"]]
        if row.get("vietnamese_gloss_precision_status") == VIETNAMESE_PRECISION_STATUS
    ]
    assert Counter("audit" if "gloss_after" in row else "review" for row in owners) == {
        "audit": 8,
        "review": 4,
    }
    for owner in owners:
        card = _card_for_owner(owner, rows["cards"])
        _assert_owner_payload(
            owner,
            card,
            rows["semantic_registry"],
            rows["collocation_registry"],
        )
        for chunk in card["definition"].split("|"):
            translation = chunk.rsplit("(", 1)[-1].rstrip(")")
            assert translation.count("/") < 2, card["word"]

    remaining = [
        row
        for row in _load(PATHS.root / "data" / "review" / "quality_audit_decisions_20260711.jsonl")
        if row.get("issue_type") == "vietnamese_gloss_precision_review"
        and any(row.get("guid") == owner.get("guid") for owner in owners)
    ]
    assert remaining == []


def test_audit_review_20260713_matches_reviewed_card_payloads():
    rows = _canonical_rows()
    cards = {row["guid"]: row for row in rows["cards"]}
    registry = {row["guid"]: row for row in rows["registry"]}
    semantic_registry = {
        row["guid"]: row for row in rows["semantic_registry"]
    }

    assert (registry["d0+rK3^u+."]["word"], registry["d0+rK3^u+."]["pos"]) == (
        "devote sth to sth",
        "phrasal verb",
    )
    assert (cards["d0+rK3^u+."]["word"], cards["d0+rK3^u+."]["pos"]) == (
        "devote sth to sth",
        "phrasal verb",
    )
    _assert_registry_payload(semantic_registry["d0+rK3^u+."], cards["d0+rK3^u+."])

    advocate = cards["km/DeO(0eI"]
    assert advocate["pos"] == "noun, verb"
    _assert_registry_payload(semantic_registry["km/DeO(0eI"], advocate)

    deposit_b2 = cards["5[fv?8uF;~"]
    assert (deposit_b2["word"], deposit_b2["pos"], deposit_b2["cefr"]) == (
        "deposit",
        "noun",
        "B2",
    )
    _assert_registry_payload(semantic_registry["5[fv?8uF;~"], deposit_b2)

    deposit_c1 = cards["b6cD1Ck8TE"]
    assert deposit_c1["pos"] == "verb"
    _assert_registry_payload(semantic_registry["b6cD1Ck8TE"], deposit_c1)
    assert deposit_c1["synonyms"] == deposit_c1["antonyms"] == ""
    assert "idioms" not in deposit_c1["tags"].split()

    meantime = cards["N|.UFNN`SW"]
    assert meantime["pos"] == "noun"
    _assert_registry_payload(semantic_registry["N|.UFNN`SW"], meantime)
    assert meantime["collocations"] == ""
    assert [part.split(" :: ", 1)[0] for part in meantime["idioms"].split("$$")] == [
        "for the meantime",
        "in the meantime",
    ]
    assert "/meanwhile" not in meantime["idioms"]

    solo = cards["%nP=oVYMv%"]
    _assert_registry_payload(semantic_registry["%nP=oVYMv%"], solo)

    worship = cards[",qqw,<G4mQ"]
    _assert_registry_payload(semantic_registry[",qqw,<G4mQ"], worship)
    assert (worship["synonyms"], worship["antonyms"]) == ("|adoration", "|")

    yield_card = cards["@NbB`9?Tqc"]
    _assert_registry_payload(semantic_registry["@NbB`9?Tqc"], yield_card)

    _assert_registry_payload(semantic_registry["kCq5xM.G_7"], cards["kCq5xM.G_7"])

    audit_keys = {
        (row["word"], row["pos"], row["cefr"])
        for row in rows["audit"]
    }
    assert ("deposit", "noun", "C1") not in audit_keys
    assert ("meantime", "adverb", "C1") not in audit_keys
    assert len(rows["audit"]) == 2459
