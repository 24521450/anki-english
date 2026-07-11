from __future__ import annotations

import json
from collections import Counter

from src.config import ProjectPaths
from tools.archive.data_migrations._apply_exact_source_cefr_rescue import (
    APPROXIMATE_PAYLOAD,
    FIX_STATUS,
    TARGETS,
)


PATHS = ProjectPaths()


def _load(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_exact_source_rescue_canonical_owners_match():
    registry = {row["guid"]: row for row in _load(PATHS.card_registry)}
    overrides = {row["guid"]: row for row in _load(PATHS.non_oxford_non_c2_overrides)}
    manuals = {
        (row["word"], row["cefr"], row["list"], row.get("variant") or ""): row
        for row in _load(PATHS.manual_cards)
    }

    assert Counter(target.cefr for target in TARGETS.values()) == {
        "B2": 3,
        "C1": 9,
        "C2": 25,
    }
    for guid, target in TARGETS.items():
        reg = registry[guid]
        list_name = target.list_name or reg["list"]
        manual = manuals[(target.word, target.cefr, list_name, reg.get("variant") or "")]
        override = overrides[guid]
        assert reg["word"] == target.word
        assert reg["cefr"] == target.cefr
        assert reg["pos"] == target.pos
        assert override["cefr"] == target.cefr
        assert override["fix_status"] == FIX_STATUS
        assert manual["provenance"]["review_batch"] == FIX_STATUS
        assert manual["provenance"]["cefr_source"] == target.cefr_source


def test_exact_source_rescue_built_output_and_special_cases():
    cards = {row["guid"]: row for row in _load(PATHS.anki_notes_jsonl)}

    for guid, target in TARGETS.items():
        card = cards[guid]
        assert card["word"] == target.word
        assert card["cefr"] == target.cefr
        assert card["pos"] == target.pos
        assert card["uk_audio"] and card["us_audio"]

    approximate = cards["q-l2t)2u|/"]
    assert approximate["definition"] == APPROXIMATE_PAYLOAD["Definition"]
    assert approximate["example"] == APPROXIMATE_PAYLOAD["Example"]
    assert approximate["source1"] == "Cambridge"
    assert "CEFR::cambridge" in approximate["tags"]

    criterion = cards['"L-#l1@LS<>"']
    assert criterion["deck"] == (
        "English Academic Vocabulary::Oxford::Oxford 3000 Advanced"
    )
    assert criterion["tags"] == (
        "Source::Oxford CEFR::B2 CEFR::oxford Oxford_3000"
    )

    harbour = cards["m}g1cKg({G"]
    assert harbour["word"] == "harbour"
    assert harbour["pos"] == "verb"
    assert harbour["cefr"] == "UNCLASSIFIED"
