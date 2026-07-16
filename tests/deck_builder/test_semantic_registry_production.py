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

    assert len(registry_by_guid) == len(cards_by_guid) == 2461
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
