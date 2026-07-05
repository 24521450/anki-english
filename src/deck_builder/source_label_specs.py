"""Source label provenance lookup for rendered cards."""
from __future__ import annotations

from src.deck_builder.build_contracts import BuiltCard
from src.deck_builder.word_lookup import get_word_candidates


def build_source_label_specs_index(
    by_word: dict[str, list[dict]],
) -> dict[tuple[str, str], list[dict]]:
    """Index raw Oxford definition provenance independently of CEFR filtering."""
    index: dict[tuple[str, str], list[dict]] = {}
    for word, records in by_word.items():
        for record in records:
            for pos_data in record.get("pos_data") or []:
                pos = (pos_data.get("pos") or "").strip().lower()
                if not pos:
                    continue
                for definition in pos_data.get("definitions") or []:
                    source_definition = (definition.get("text") or "").strip()
                    if not source_definition:
                        continue
                    index.setdefault((word, pos), []).append({
                        "source_definition": source_definition,
                        "register_tags": list(definition.get("register_tags") or []),
                        "domain": definition.get("domain"),
                        "examples": [
                            (example.get("text") or "").strip()
                            for example in (definition.get("examples") or [])
                            if (example.get("text") or "").strip()
                        ],
                        "synonyms": list(definition.get("synonyms") or []),
                        "antonyms": list(definition.get("antonyms") or []),
                    })
    return index


def get_source_label_specs_for_card(
    card: BuiltCard,
    source_label_specs_index: dict[tuple[str, str], list[dict]],
) -> list[dict]:
    word_clean = card.word.split(" (")[0].strip().lower()
    positions = [part.strip().lower() for part in card.pos.split(",") if part.strip()]
    for candidate in get_word_candidates(word_clean):
        specs: list[dict] = []
        for pos in positions:
            specs.extend(source_label_specs_index.get((candidate, pos), []))
        if specs:
            return specs
    return []
