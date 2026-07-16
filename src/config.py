"""Canonical filesystem paths for the repository."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    """Resolve canonical project artifacts from an optional repository root."""

    root: Path | str | None = None

    def __post_init__(self) -> None:
        root = self.root
        if root is None:
            root = Path(__file__).resolve().parent.parent
        object.__setattr__(self, "root", Path(root).resolve())

    @property
    def oxford_jsonl(self) -> Path:
        return self.root / "data" / "sources" / "oxford.jsonl"

    @property
    def cambridge_jsonl(self) -> Path:
        return self.root / "data" / "sources" / "cambridge.jsonl"

    @property
    def deck_audit_jsonl(self) -> Path:
        return self.root / "data" / "curated" / "deck_audit.jsonl"

    @property
    def card_registry(self) -> Path:
        return self.root / "data" / "curated" / "card_registry.jsonl"

    @property
    def bilingual_semantic_audit(self) -> Path:
        return self.root / "data" / "review" / "bilingual_semantic_audit.jsonl"

    @property
    def semantic_registry(self) -> Path:
        return self.root / "data" / "curated" / "semantic_registry.jsonl"

    @property
    def gamma_verdicts(self) -> Path:
        return self.root / "data" / "review" / "gamma_verdicts.json"

    @property
    def manual_card_fills(self) -> Path:
        return self.root / "data" / "review" / "manual_card_fills.json"

    @property
    def manual_cards(self) -> Path:
        return self.root / "data" / "review" / "manual_cards.jsonl"

    @property
    def non_oxford_non_c2_overrides(self) -> Path:
        return self.root / "data" / "review" / "non_oxford_non_c2_overrides.jsonl"

    @property
    def synonym_example_overrides(self) -> Path:
        return self.root / "data" / "review" / "synonym_example_overrides.jsonl"

    @property
    def antonym_example_overrides(self) -> Path:
        return self.root / "data" / "review" / "antonym_example_overrides.jsonl"

    @property
    def antonym_loop_decisions(self) -> Path:
        return self.root / "data" / "review" / "antonym_loop_decisions.jsonl"

    @property
    def sense_label_overrides(self) -> Path:
        return self.root / "data" / "review" / "sense_label_overrides.jsonl"

    @property
    def anki_notes_jsonl(self) -> Path:
        return self.root / "data" / "build" / "anki_notes.jsonl"

    @property
    def anki_notes_txt(self) -> Path:
        return self.root / "data" / "build" / "anki_notes.txt"

    @property
    def build_staging_dir(self) -> Path:
        return self.root / "data" / "build" / ".staging"

    @property
    def oxford_3000_md(self) -> Path:
        return self.root / "vocab_list" / "Oxford" / "Oxford_3000.md"

    @property
    def oxford_5000_md(self) -> Path:
        return self.root / "vocab_list" / "Oxford" / "Oxford_5000.md"

    @property
    def awl_md(self) -> Path:
        return self.root / "vocab_list" / "AWL" / "AWL.md"

    @property
    def cambridge_cache_dir(self) -> Path:
        return self.root / "data" / ".cache_html" / "cambridge"

    @property
    def awl_cambridge_fallbacks(self) -> Path:
        return self.root / "vocab_list" / "AWL" / "cambridge_fallbacks.json"

    @property
    def audio_dir(self) -> Path:
        return self.root / "audio"
