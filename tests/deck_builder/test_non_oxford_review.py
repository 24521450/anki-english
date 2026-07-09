from __future__ import annotations

import json
import pytest
import subprocess
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.build_contracts import BuildNotesPaths, BuiltCard
from src.deck_builder.build_notes import build_notes
from src.deck_builder.review_overrides import apply_review_overrides, load_review_overrides

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REVIEW_PATH = ProjectPaths(PROJECT_ROOT).non_oxford_non_c2_overrides


def _load_jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _override_guids(path: Path) -> set[str]:
    """Return the set of GUIDs referenced by a relation-override JSONL file.

    The override JSONL's `guid` field uses the same `"..."` wrapper as
    Anki's TXT format (matches `c.guid`), so we just return the raw value
    after stripping outer whitespace.
    """
    guids: set[str] = set()
    for row in _load_jsonl_rows(path):
        g = row.get("guid", "").strip()
        if g:
            guids.add(g)
    return guids


def _build_paths(paths_reg: ProjectPaths, *, with_overrides: bool) -> BuildNotesPaths:
    return BuildNotesPaths(
        oxford_jsonl_path=paths_reg.oxford_jsonl,
        deck_audit_jsonl_path=paths_reg.deck_audit_jsonl,
        gamma_verdicts_path=paths_reg.gamma_verdicts,
        oxford_3000_md=paths_reg.oxford_3000_md,
        oxford_5000_md=paths_reg.oxford_5000_md,
        awl_md=paths_reg.awl_md,
        audio_dir=paths_reg.audio_dir,
        card_registry_path=paths_reg.card_registry,
        manual_cards_path=paths_reg.manual_cards,
        review_overrides_path=paths_reg.non_oxford_non_c2_overrides if with_overrides else None,
        synonym_example_overrides_path=paths_reg.synonym_example_overrides,
        antonym_example_overrides_path=paths_reg.antonym_example_overrides,
        sense_label_overrides_path=paths_reg.sense_label_overrides,
    )


def get_cards_without_overrides():
    """Build the baseline (no overrides of any kind).

    The only thing `get_cards_with_overrides` should do *differently* is
    apply the non-oxford-non-c2 review overrides (and synonym/antonym
    annotations). To measure that delta cleanly, we strip ALL overrides
    here so each build path is independent.
    """
    paths_reg = ProjectPaths(PROJECT_ROOT)
    paths = _build_paths(paths_reg, with_overrides=False)
    res = build_notes(paths)
    return res.built_cards


def get_cards_with_overrides():
    """Build with non-oxford AND synonym/antonym overrides applied."""
    paths_reg = ProjectPaths(PROJECT_ROOT)
    paths = _build_paths(paths_reg, with_overrides=True)
    res = build_notes(paths)
    return res.built_cards

def test_non_oxford_review_in_memory_metrics_and_scope():
    overrides = load_review_overrides(REVIEW_PATH)
    assert len(overrides) == 382

    paths_reg = ProjectPaths(PROJECT_ROOT)
    cards = get_cards_with_overrides()
    by_guid = {card.guid: card for card in cards}

    assert len(cards) == 2457
    assert set(overrides).issubset(by_guid)
    assert _override_guids(paths_reg.synonym_example_overrides).issubset(by_guid)
    assert _override_guids(paths_reg.antonym_example_overrides).issubset(by_guid)

def test_manual_override_specifics():
    cards = get_cards_with_overrides()

    # Verify harness
    harness_cards = [c for c in cards if c.word == "harness" and c.pos == "verb" and c.cefr == "UNCLASSIFIED"]
    assert len(harness_cards) == 1
    harness = harness_cards[0]
    assert harness.definition == "control and use power or resources (khai thác/tận dụng)"
    assert harness.example == "attempts to harness the sun’s rays as a source of energy"
    assert harness.collocations == "harness energy/power/resources|harness the sun/wind|harness sth to do sth"

    # Verify nursing
    nursing_cards = [c for c in cards if c.word == "nursing" and c.cefr == "B2"]
    assert len(nursing_cards) == 1
    nursing = nursing_cards[0]
    assert nursing.pos == "noun"
    assert nursing.definition == "care of sick people (nghề điều dưỡng/chăm sóc bệnh nhân)"
    assert nursing.example == "a career in nursing"
    assert nursing.collocations == "nursing care/profession/career|career in nursing"


def test_review_override_can_replace_ipa():
    card = BuiltCard(
        guid="extract-guid",
        notetype="English Academic Vocabulary Model",
        deck="Oxford",
        word="extract",
        pos="noun",
        ipa="/ɪkˈstrækt/",
        definition="short passage",
        example="an extract",
        collocations="extract from a book",
        wordfamily="",
        uk_audio="",
        us_audio="",
        source1="Oxford",
        source2="Oxford",
        cefr="B2",
        idioms="",
        tags="Source::Oxford CEFR::B2 Oxford_5000",
        synonyms="",
        antonyms="",
    )
    override = {
        "extract-guid": {
            "guid": "extract-guid",
            "word": "extract",
            "input_pos": "noun",
            "cefr": "B2",
            "IPA": "UK: /ˈekstrækt/ | US: /ˈekstrækt/",
        }
    }

    updated = apply_review_overrides([card], override)

    assert updated[0].ipa == "UK: /ˈekstrækt/ | US: /ˈekstrækt/"

def test_build_determinism():
    paths_reg = ProjectPaths(PROJECT_ROOT)
    paths = _build_paths(paths_reg, with_overrides=True)
    
    # First build
    cards1 = build_notes(paths).built_cards
    # Second build
    cards2 = build_notes(paths).built_cards

    assert len(cards1) == len(cards2)
    for c1, c2 in zip(cards1, cards2):
        assert c1.to_dict() == c2.to_dict()

@pytest.mark.external
def test_import_determinism():
    source_path = Path("c:/Users/admin/Downloads/non_oxford_non_c2_all_batches_381_cards.md")
    if not source_path.exists():
        pytest.skip("Source file not found in c:/Users/admin/Downloads/")

    # Dry-run execution 1
    cmd1 = ["python", "-m", "tools.import_non_oxford_review", "--source", str(source_path)]
    out1 = subprocess.check_output(cmd1, cwd=str(PROJECT_ROOT), text=True)
    assert "Dry-run verification passed successfully!" in out1

    # Dry-run execution 2
    cmd2 = ["python", "-m", "tools.import_non_oxford_review", "--source", str(source_path)]
    out2 = subprocess.check_output(cmd2, cwd=str(PROJECT_ROOT), text=True)
    assert "Dry-run verification passed successfully!" in out2

    assert out1 == out2


def test_collocations_no_semicolons():
    # Verify overrides jsonl
    overrides = load_review_overrides(REVIEW_PATH)
    for guid, r in overrides.items():
        collocations = r.get("Collocations") or ""
        assert ";" not in collocations, f"Semicolon found in Collocations for override GUID {guid!r}: {collocations!r}"

    # Verify built cards with overrides
    cards = get_cards_with_overrides()
    overridden_guids = set(overrides.keys())
    for c in cards:
        if c.guid in overridden_guids:
            assert ";" not in c.collocations, f"Semicolon found in built card Collocations for word {c.word!r}: {c.collocations!r}"
