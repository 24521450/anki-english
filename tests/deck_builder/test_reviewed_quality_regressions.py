from __future__ import annotations

import json
from collections import Counter

from src.config import ProjectPaths
from src.deck_builder.sense_labels import parse_existing_prefix


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
    if len(matches) > 1:
        matches = [
            card
            for card in matches
            if _definition_without_labels(card["definition"])
            == _definition_without_labels(owner["gloss_after"])
        ]
    assert len(matches) == 1, owner["word"]
    return matches[0]


def _definition_without_labels(definition: str) -> str:
    return "|".join(parse_existing_prefix(chunk)[1] for chunk in definition.split("|"))


def _assert_owner_payload(owner: dict, card: dict) -> None:
    if owner.get("guid"):
        owner_definition = owner["Definition"]
        owner_example = owner["Example"]
        assert card["collocations"] == owner["Collocations"]
    else:
        owner_definition = owner["gloss_after"]
        owner_example = owner["example_after"]
        assert card["collocations"] == owner["collocations_after"]
    assert _definition_without_labels(card["definition"]) == _definition_without_labels(
        owner_definition
    )
    assert len(card["example"].split("|")) == len(owner_example.split("|"))
    if "<br><br>" in owner_example:
        assert "<br><br>" in card["example"]


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
    assert approximate["definition"] == approximate_manual["definition"]
    assert approximate["example"] == approximate_manual["example"]
    assert approximate["source1"] == "Cambridge"
    assert "CEFR::cambridge" in approximate["tags"]
    assert cards['"L-#l1@LS<>"']["deck"].endswith("Oxford 3000 Advanced")
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
        _assert_owner_payload(owner, card)
        assert len(card["definition"].split("|")) == 3
        assert len(card["example"].split("|")) == 3
        assert (card["synonyms"], card["antonyms"]) == expected_relations[card["word"]]


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
        "review": 14,
    }
    for owner in owners:
        _assert_owner_payload(owner, _card_for_owner(owner, rows["cards"]))

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
        _assert_owner_payload(owner, card)
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

    assert (registry["d0+rK3^u+."]["word"], registry["d0+rK3^u+."]["pos"]) == (
        "devote sth to sth",
        "phrasal verb",
    )
    assert (cards["d0+rK3^u+."]["word"], cards["d0+rK3^u+."]["pos"]) == (
        "devote sth to sth",
        "phrasal verb",
    )

    advocate = cards["km/DeO(0eI"]
    assert advocate["pos"] == "noun, verb"
    assert advocate["example"] == (
        "an advocate for hospital workers<br><br>"
        "The group does not advocate the use of violence."
    )

    deposit_b2 = cards["5[fv?8uF;~"]
    assert (deposit_b2["word"], deposit_b2["pos"], deposit_b2["cefr"]) == (
        "deposit",
        "noun",
        "B2",
    )
    assert deposit_b2["definition"] == (
        "first part of payment (tiền đặt cọc)|"
        "refundable security money (tiền cọc bảo đảm)"
    )

    deposit_c1 = cards["b6cD1Ck8TE"]
    assert deposit_c1["pos"] == "verb"
    assert deposit_c1["definition"] == (
        "put money into a bank account (gửi tiền vào tài khoản)|"
        "pay money in advance or as refundable security (đặt cọc)"
    )
    assert deposit_c1["synonyms"] == deposit_c1["antonyms"] == ""
    assert "idioms" not in deposit_c1["tags"].split()

    meantime = cards["N|.UFNN`SW"]
    assert meantime["pos"] == "noun"
    assert (meantime["definition"], meantime["example"], meantime["collocations"]) == (
        "",
        "",
        "",
    )
    assert [part.split(" :: ", 1)[0] for part in meantime["idioms"].split("$$")] == [
        "for the meantime",
        "in the meantime",
    ]
    assert "/meanwhile" not in meantime["idioms"]

    solo = cards["%nP=oVYMv%"]
    assert solo["definition"] == "done by one person alone|a piece or performance for one person"
    assert solo["example"] == "his first solo flight|She played a piano solo."

    worship = cards[",qqw,<G4mQ"]
    assert worship["definition"] == (
        "showing respect to God (thờ phụng)|strong love/respect (sùng bái)"
    )
    assert (worship["synonyms"], worship["antonyms"]) == ("|adoration", "|")

    yield_card = cards["@NbB`9?Tqc"]
    assert yield_card["example"] == (
        "This will give a yield of 10% on your investment.<br><br>"
        "Higher-rate deposit accounts yield good returns.|"
        "After a long siege, the town was forced to yield (give way)."
    )

    assert cards["kCq5xM.G_7"]["definition"] == (
        "believing people act selfishly (hoài nghi)|"
        "not believing good will happen (bi quan)"
    )

    audit_keys = {
        (row["word"], row["pos"], row["cefr"])
        for row in rows["audit"]
    }
    assert ("deposit", "noun", "C1") not in audit_keys
    assert ("meantime", "adverb", "C1") not in audit_keys
    assert len(rows["audit"]) == 2459
