from __future__ import annotations

import json
import pytest
import subprocess
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.build_notes import build_notes, BuildNotesPaths, BuiltCard
from src.deck_builder.review_overrides import load_review_overrides

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


def get_cards_without_overrides():
    """Build the baseline (no overrides of any kind).

    The only thing `get_cards_with_overrides` should do *differently* is
    apply the non-oxford-non-c2 review overrides (and synonym/antonym
    annotations). To measure that delta cleanly, we strip ALL overrides
    here so each build path is independent.
    """
    paths_reg = ProjectPaths(PROJECT_ROOT)
    paths = BuildNotesPaths(
        oxford_jsonl_path=paths_reg.oxford_jsonl,
        oxford_3000_md=paths_reg.oxford_3000_md,
        oxford_5000_md=paths_reg.oxford_5000_md,
        awl_md=paths_reg.awl_md,
        notes_txt_path=paths_reg.anki_notes_txt,
        gamma_verdicts_path=paths_reg.gamma_verdicts,
        deck_audit_jsonl_path=paths_reg.deck_audit_jsonl,
        manual_card_fills_path=paths_reg.manual_card_fills,
        audio_dir=paths_reg.audio_dir,
        review_overrides_path=None,
    )
    res = build_notes(paths)
    return res.built_cards


def get_cards_with_overrides():
    """Build with non-oxford AND synonym/antonym overrides applied."""
    paths_reg = ProjectPaths(PROJECT_ROOT)
    paths = BuildNotesPaths(
        oxford_jsonl_path=paths_reg.oxford_jsonl,
        oxford_3000_md=paths_reg.oxford_3000_md,
        oxford_5000_md=paths_reg.oxford_5000_md,
        awl_md=paths_reg.awl_md,
        notes_txt_path=paths_reg.anki_notes_txt,
        gamma_verdicts_path=paths_reg.gamma_verdicts,
        deck_audit_jsonl_path=paths_reg.deck_audit_jsonl,
        manual_card_fills_path=paths_reg.manual_card_fills,
        audio_dir=paths_reg.audio_dir,
        review_overrides_path=paths_reg.non_oxford_non_c2_overrides,
        synonym_example_overrides_path=paths_reg.synonym_example_overrides,
        antonym_example_overrides_path=paths_reg.antonym_example_overrides,
    )
    res = build_notes(paths)
    return res.built_cards

def test_non_oxford_review_in_memory_metrics_and_scope():
    overrides = load_review_overrides(REVIEW_PATH)
    assert len(overrides) == 381

    paths_reg = ProjectPaths(PROJECT_ROOT)
    syn_guids = _override_guids(paths_reg.synonym_example_overrides)
    ant_guids = _override_guids(paths_reg.antonym_example_overrides)
    relation_override_guids = syn_guids | ant_guids

    baseline_cards = get_cards_without_overrides()
    overridden_cards = get_cards_with_overrides()

    assert len(baseline_cards) == 2452
    assert len(overridden_cards) == 2452

    baseline_by_guid = {c.guid: c for c in baseline_cards}
    overridden_by_guid = {c.guid: c for c in overridden_cards}

    # Count actual field changes
    def_changed = 0
    coll_changed = 0
    ex_changed = 0
    pos_changed = 0

    for guid, base in baseline_by_guid.items():
        assert guid in overridden_by_guid
        overridden = overridden_by_guid[guid]

        if guid in overrides:
            # Verify non-overridden fields are completely preserved
            for field in ("guid", "notetype", "deck", "word", "ipa", "uk_audio", "us_audio", "source1", "source2", "cefr", "idioms", "tags"):
                assert getattr(base, field) == getattr(overridden, field), f"Field {field} changed for word {base.word}"

            if base.definition != overridden.definition:
                def_changed += 1
            if base.collocations != overridden.collocations:
                coll_changed += 1
            if base.example != overridden.example:
                ex_changed += 1
            if base.pos != overridden.pos:
                pos_changed += 1
                # Only nursing can have a POS change
                assert base.word == "nursing"
                assert base.pos == "noun, adjective"
                assert overridden.pos == "noun"
            else:
                if base.word == "nursing":
                    assert overridden.pos == "noun"
        else:
            # Cards outside the non-oxford scope. The synonym/antonym
            # override may legitimately change `example`/`synonyms`/`antonyms`
            # for cards it annotates. Definition/collocation/etc. must
            # still be completely identical.
            relation_overridden = guid in relation_override_guids
            immutable_fields = (
                "guid", "notetype", "deck", "word", "pos", "ipa",
                "definition", "collocations", "wordfamily",
                "uk_audio", "us_audio", "source1", "source2", "cefr",
                "idioms", "tags",
            )
            if relation_overridden:
                # example/synonyms/antonyms may differ
                relation_fields = ("example", "synonyms", "antonyms")
            else:
                # nothing should differ at all
                relation_fields = immutable_fields
                immutable_fields = (  # type: ignore[assignment]
                    "guid", "notetype", "deck", "word", "pos", "ipa",
                    "definition", "example", "collocations", "wordfamily",
                    "uk_audio", "us_audio", "source1", "source2", "cefr",
                    "idioms", "tags", "synonyms", "antonyms",
                )

            for field in immutable_fields:
                assert getattr(base, field) == getattr(overridden, field), (
                    f"Card outside scope {base.word} ({guid}) field {field!r} "
                    f"was modified! base={getattr(base, field)!r} "
                    f"overridden={getattr(overridden, field)!r}"
                )

    # Verification of exact modification counts
    assert def_changed == 381
    # 380 because mainland's collocation was already identical to the review override value
    assert coll_changed == 380
    assert ex_changed == 52  # 51 from MD + 1 from harness manual override
    assert pos_changed in (0, 1)

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

def test_build_determinism():
    paths_reg = ProjectPaths(PROJECT_ROOT)
    paths = BuildNotesPaths(
        oxford_jsonl_path=paths_reg.oxford_jsonl,
        oxford_3000_md=paths_reg.oxford_3000_md,
        oxford_5000_md=paths_reg.oxford_5000_md,
        awl_md=paths_reg.awl_md,
        notes_txt_path=paths_reg.anki_notes_txt,
        gamma_verdicts_path=paths_reg.gamma_verdicts,
        deck_audit_jsonl_path=paths_reg.deck_audit_jsonl,
        manual_card_fills_path=paths_reg.manual_card_fills,
        audio_dir=paths_reg.audio_dir,
        review_overrides_path=paths_reg.non_oxford_non_c2_overrides,
        synonym_example_overrides_path=paths_reg.synonym_example_overrides,
        antonym_example_overrides_path=paths_reg.antonym_example_overrides,
    )
    
    # First build
    cards1 = build_notes(paths).built_cards
    # Second build
    cards2 = build_notes(paths).built_cards

    assert len(cards1) == len(cards2)
    for c1, c2 in zip(cards1, cards2):
        assert c1.to_dict() == c2.to_dict()

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
