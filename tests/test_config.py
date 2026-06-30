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
    assert paths.gamma_verdicts == tmp_path / "data" / "review" / "gamma_verdicts.json"
    assert paths.manual_card_fills == tmp_path / "data" / "review" / "manual_card_fills.json"
    assert paths.anki_notes_jsonl == tmp_path / "data" / "build" / "anki_notes.jsonl"
    assert paths.anki_notes_txt == tmp_path / "data" / "build" / "anki_notes.txt"


def test_project_paths_is_immutable(tmp_path):
    paths = ProjectPaths(tmp_path)

    with pytest.raises(FrozenInstanceError):
        paths.root = tmp_path.parent
