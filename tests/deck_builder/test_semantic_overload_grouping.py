from __future__ import annotations

import json

from src.config import ProjectPaths
from tools.archive.data_migrations._apply_semantic_overload_grouping import (
    FIX_STATUS,
    GROUPINGS,
)
from tools.archive.data_migrations._apply_vietnamese_gloss_precision_review import (
    REPAIRS as VIETNAMESE_GLOSS_REPAIRS,
)


PATHS = ProjectPaths()


def _load(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_grouped_cards_have_three_aligned_cells_and_relations():
    cards = {row["guid"]: row for row in _load(PATHS.anki_notes_jsonl)}
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

    for grouping in GROUPINGS:
        card = cards[grouping.guid]
        downstream = next(
            (repair for repair in VIETNAMESE_GLOSS_REPAIRS if repair.guid == grouping.guid),
            None,
        )
        expected_definition = downstream.new_definition if downstream else grouping.definition
        assert card["definition"] == expected_definition
        assert len(card["definition"].split("|")) == 3
        assert len(card["example"].split("|")) == 3
        assert len(card["synonyms"].split("|")) == 3
        assert len(card["antonyms"].split("|")) == 3
        assert "<br><br>" in card["example"]
        assert (card["synonyms"], card["antonyms"]) == expected_relations[grouping.word]


def test_disconnect_and_exclusive_remain_reviewed_four_sense_keeps():
    cards = {row["guid"]: row for row in _load(PATHS.anki_notes_jsonl)}
    expected = {
        "B7[0+R><3N": (
            "separate equipment from a supply (ngắt khỏi nguồn)|"
            "stop an official service (cắt dịch vụ)|"
            "break phone contact (mất/ngắt liên lạc)|"
            "end an internet connection (ngắt mạng)"
        ),
        "ka@NZF]8Qa": (
            "only for one person/group (độc quyền/riêng)|"
            "closed to outsiders (khép kín)|"
            "expensive and high-class (cao cấp)|"
            "not including others (chỉ riêng/không gồm gì khác)"
        ),
    }
    for guid, definition in expected.items():
        assert cards[guid]["definition"] == definition
        assert len(cards[guid]["definition"].split("|")) == 4


def test_grouping_fix_status_and_sterile_skip_override_are_canonical():
    audit = {
        (row["word"], row["pos"], row["cefr"]): row
        for row in _load(PATHS.deck_audit_jsonl)
    }
    reviews = {
        row["guid"]: row for row in _load(PATHS.non_oxford_non_c2_overrides)
    }
    overrides = _load(PATHS.synonym_example_overrides)

    for grouping in GROUPINGS:
        owner = (
            audit[grouping.identity]
            if grouping.owner == "audit"
            else reviews[grouping.guid]
        )
        assert owner["fix_status"] == FIX_STATUS

    sterile_skips = [
        row for row in overrides
        if row.get("guid") == '"j>(#&<;AW0"'
        and row.get("original_example") == "sterile soil"
        and row.get("action") == "skip"
    ]
    assert len(sterile_skips) == 1
