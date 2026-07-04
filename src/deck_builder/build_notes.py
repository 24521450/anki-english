"""Public facade for the canonical registry-driven Anki notes builder."""
from __future__ import annotations

from src.deck_builder.build_contracts import (
    BuildNotesPaths,
    BuildNotesResult,
    BuiltCard,
)
from src.deck_builder.registry_build import build_notes_from_registry

__all__ = ["BuildNotesPaths", "BuildNotesResult", "BuiltCard", "build_notes"]


def build_notes(paths: BuildNotesPaths) -> BuildNotesResult:
    return build_notes_from_registry(paths)
