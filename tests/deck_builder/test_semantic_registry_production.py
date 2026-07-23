import hashlib
import json
import re

from src.config import ProjectPaths
from src.deck_builder.synonym_annotator import strip_synonym_annotations


def _jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _definition(row):
    return "|".join(
        f"{sense['definition_en']} ({sense['definition_vi']})"
        for sense in row["senses"]
    )


def _example(row):
    return "|".join(
        "<br><br>".join(sense["examples"])
        for sense in row["senses"]
    )


def _relation_terms(card):
    terms = []
    for field in (card["synonyms"], card["antonyms"]):
        for part in re.split(r"\||<br\s*/?><br\s*/?>|,", field, flags=re.I):
            part = part.strip()
            if part and part not in terms:
                terms.append(part)
    return terms


def _semantic_example(value, relation_terms):
    return " ".join(strip_synonym_annotations(value, relation_terms).split())


def test_production_build_uses_the_complete_promoted_semantic_registry():
    paths = ProjectPaths()
    registry_rows = _jsonl(paths.semantic_registry)
    cards = _jsonl(paths.anki_notes_jsonl)
    registry_by_guid = {row["guid"]: row for row in registry_rows}
    cards_by_guid = {card["guid"]: card for card in cards}

    assert len(registry_by_guid) == len(cards_by_guid) == 2465
    assert set(registry_by_guid) == set(cards_by_guid)
    audit_sha256 = hashlib.sha256(paths.bilingual_semantic_audit.read_bytes()).hexdigest()
    assert {row["audit_sha256"] for row in registry_rows} == {audit_sha256}

    for guid, row in registry_by_guid.items():
        card = cards_by_guid[guid]
        assert card["definition"] == _definition(row), guid
        relation_terms = _relation_terms(card)
        assert _semantic_example(card["example"], relation_terms) == (
            _semantic_example(_example(row), relation_terms)
        ), guid


def test_production_inventory_matches_all_canonical_authorities():
    paths = ProjectPaths()
    card_registry = _jsonl(paths.card_registry)
    semantic_audit = _jsonl(paths.bilingual_semantic_audit)
    semantic_registry = _jsonl(paths.semantic_registry)
    collocation_registry = _jsonl(paths.collocation_registry)
    cards = _jsonl(paths.anki_notes_jsonl)
    vietnamese_review = _jsonl(paths.vietnamese_naturalness_review)
    pronunciation_locks = _jsonl(paths.pronunciation_selection_locks)
    headword_audio_manifest = _jsonl(paths.headword_audio_manifest)

    assert len(card_registry) == 2467
    assert sum(row["status"] == "active" for row in card_registry) == 2465
    assert sum(row["status"] == "retired" for row in card_registry) == 2
    assert len(semantic_audit) == 2465
    assert len(semantic_registry) == 2465
    assert len(collocation_registry) == 2465
    assert len(cards) == 2465
    assert sum(len(row["senses"]) for row in semantic_registry) == 3479

    vietnamese_summary = vietnamese_review[0]
    assert vietnamese_summary["record_type"] == "review_summary"
    assert vietnamese_summary["candidate_count"] == 3479
    assert len(vietnamese_review) == 3480
    assert sum(
        bool(card["definition_vi"])
        and bool(card["example"])
        and bool(card["production_answer"])
        for card in cards
    ) == 2463
    assert len(pronunciation_locks) == 277
    assert {row["schema_version"] for row in pronunciation_locks} == {2}
    assert sum(row["decision"] == "select" for row in pronunciation_locks) == 273
    assert sum(
        row["decision"] == "no_pronunciation" for row in pronunciation_locks
    ) == 4
    assert sum(
        row["reviewer"] == "pronunciation-authority-v2-migration-20260722"
        for row in pronunciation_locks
    ) == 218
    assert len(headword_audio_manifest) == 4890
    assert {row["schema_version"] for row in headword_audio_manifest} == {2}
    assert len({row["selection_fingerprint"] for row in headword_audio_manifest}) == 4890
    assert len({row["media_fingerprint"] for row in headword_audio_manifest}) == 4845
    assert len({row["filename"].casefold() for row in headword_audio_manifest}) == 4845


def test_takenote_reviewed_identity_splits_reach_production():
    paths = ProjectPaths()
    registry_by_guid = {row["guid"]: row for row in _jsonl(paths.card_registry)}
    cards_by_guid = {row["guid"]: row for row in _jsonl(paths.anki_notes_jsonl)}
    secondary_deck = (
        "English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses"
    )
    expected = {
        "$|_`hdAC|%": ("denial", "primary", False),
        "Jhp@WXA!ga": (
            "denial",
            "secondary_entitlement_psychological",
            True,
        ),
        "Y&tBh??_,}": ("alien", "primary", False),
        "q?0?C/TI0}": ("alien", "secondary_disapproving_space", True),
        "fM]>3mcy3=": ("sensitivity", "primary", False),
        "fXYJ-i~KFJ": ("sensitivity", "secondary_art_physical", True),
    }

    for guid, (word, variant, is_secondary) in expected.items():
        registry = registry_by_guid[guid]
        card = cards_by_guid[guid]
        assert registry["word"] == card["word"] == word
        assert registry["variant"] == variant
        assert (registry["deck_override"] == secondary_deck) is is_secondary
        assert (card["deck"] == secondary_deck) is is_secondary
        assert ("SecondarySense" in card["tags"].split()) is is_secondary


def test_takenote_semantic_and_idiom_repairs_reach_production():
    cards = {row["guid"]: row for row in _jsonl(ProjectPaths().anki_notes_jsonl)}

    assert cards["7~HN?EZ-{Z"]["definition_vi"] == "lạm dụng|ngược đãi|sỉ nhục"
    assert cards["b}M7Ln]zem"]["definition"] == (
        "fully developed physically or emotionally (trưởng thành; chín chắn)"
    )
    assert cards["b}M7Ln]zem"]["example"] == (
        "Jane is very mature (immature) for her age.<br><br>"
        "This particular breed of cattle matures early."
    )
    assert cards["x{!?8X[oY@"]["definition_vi"] == "quá khích/cực đoan"
    assert cards["x{!?8X[oY@"]["example"] == (
        "militant groups/leaders<br><br>Student militants were fighting with the police."
    )
    assert cards["z5x]Y~Fp;U"]["example"] == (
        "proposals to reform the social security system<br><br>"
        "There is disappointment at the slow pace of economic reform."
    )
    assert cards["LuhFTF6^1("]["definition_vi"] == (
        "dấu tích/dấu vết|một chút/lượng nhỏ"
    )
    assert cards["V>-bjI<%(k"]["definition_vi"] == "truy tìm; truy nguyên"
    assert cards["h8ke?|Zq:c"]["definition_vi"] == "luận văn / luận án"
    assert cards["z&94?C[j9g"]["idiom_meaning_vi"] == "vi_equivalent :: vắt kiệt"
    assert cards["odNq)Lg~YV"]["idiom_meaning_vi"] == (
        "bilingual_gloss :: hoàn toàn khỏe mạnh/nguyên vẹn"
    )


def test_takenote_collocation_provenance_repairs_reach_production():
    cards = {row["guid"]: row for row in _jsonl(ProjectPaths().anki_notes_jsonl)}

    incur = cards["ms38IO?OC2"]
    assert incur["collocations"] == (
        "incur someone's anger|incur someone's wrath|incur costs|"
        "incur expenses|loss incurred"
    )
    assert incur["collocation_sources"] == (
        "cambridge|cambridge|cambridge|cambridge|cambridge"
    )

    portion = cards["[ZF5/z3)vs"]
    assert portion["collocations"] == (
        "portion of|large portion|small portion|generous portions|"
        "portion control"
    )
    assert portion["collocation_sources"] == (
        "oxford+cambridge|cambridge|cambridge|cambridge|cambridge"
    )
