from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.config import ProjectPaths


def test_project_paths_default_root_is_repository_root():
    paths = ProjectPaths()
    assert paths.root == Path(__file__).resolve().parents[1]


def test_project_paths_resolve_canonical_artifacts(tmp_path):
    paths = ProjectPaths(tmp_path)

    assert paths.oxford_jsonl == tmp_path / "data" / "sources" / "oxford.jsonl"
    assert paths.cambridge_jsonl == tmp_path / "data" / "sources" / "cambridge.jsonl"
    assert paths.deck_audit_jsonl == tmp_path / "data" / "curated" / "deck_audit.jsonl"
    assert paths.card_registry == tmp_path / "data" / "curated" / "card_registry.jsonl"
    assert paths.bilingual_semantic_audit == tmp_path / "data" / "review" / "bilingual_semantic_audit.jsonl"
    assert paths.vietnamese_naturalness_review == tmp_path / "data" / "review" / "vietnamese_naturalness_review.jsonl"
    assert paths.bilingual_idiom_audit == tmp_path / "data" / "review" / "bilingual_idiom_audit.jsonl"
    assert paths.collocation_audit == tmp_path / "data" / "review" / "collocation_audit.jsonl"
    assert paths.collocation_audit_jsonl == paths.collocation_audit
    assert paths.semantic_registry == tmp_path / "data" / "curated" / "semantic_registry.jsonl"
    assert paths.collocation_registry == tmp_path / "data" / "curated" / "collocation_registry.jsonl"
    assert paths.collocation_registry_jsonl == paths.collocation_registry
    assert paths.gamma_verdicts == tmp_path / "data" / "review" / "gamma_verdicts.json"
    assert paths.manual_card_fills == tmp_path / "data" / "review" / "manual_card_fills.json"
    assert paths.manual_cards == tmp_path / "data" / "review" / "manual_cards.jsonl"
    assert paths.anki_notes_jsonl == tmp_path / "data" / "build" / "anki_notes.jsonl"
    assert paths.anki_notes_txt == tmp_path / "data" / "build" / "anki_notes.txt"
    assert paths.build_staging_dir == tmp_path / "data" / "build" / ".staging"


def test_project_paths_is_immutable(tmp_path):
    paths = ProjectPaths(tmp_path)

    with pytest.raises(FrozenInstanceError):
        paths.root = tmp_path.parent
