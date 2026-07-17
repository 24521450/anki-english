"""Derive pipe-aligned per-sense POS metadata from source provenance."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.deck_builder.build_contracts import POS_NORM
from src.deck_builder.simplify_senses import _flatten_senses
from src.deck_builder.source_sense_identity import source_sense_id


def normalize_pos_parts(value: object) -> tuple[str, ...]:
    """Return canonical, de-duplicated POS parts in display order."""
    parts: list[str] = []
    for raw_part in str(value or "").split(","):
        raw = raw_part.strip().casefold()
        if not raw:
            continue
        normalized = POS_NORM.get(raw, raw)
        if normalized not in parts:
            parts.append(normalized)
    return tuple(parts)


def build_source_sense_pos_index(
    records: Iterable[dict],
) -> dict[str, tuple[str, ...]]:
    """Index stable Oxford/Cambridge source-sense IDs to canonical POS parts."""
    index: dict[str, tuple[str, ...]] = {}
    for record in records:
        for flat_sense in _flatten_senses(record):
            sense_id = source_sense_id(record, flat_sense)
            pos_parts = normalize_pos_parts(flat_sense.pos)
            previous = index.setdefault(sense_id, pos_parts)
            if previous != pos_parts:
                raise ValueError(
                    f"Conflicting POS metadata for source sense {sense_id!r}: "
                    f"{previous!r} != {pos_parts!r}"
                )
    return index


def derive_sense_pos_cell(
    card_pos: object,
    source_sense_ids: Iterable[object],
    source_pos_by_id: Mapping[str, tuple[str, ...]],
) -> str:
    """Derive one canonical SensePOS cell, falling back to card-level POS."""
    card_parts = normalize_pos_parts(card_pos)
    evidence_parts = {
        part
        for source_id in source_sense_ids
        for part in source_pos_by_id.get(str(source_id or ""), ())
    }
    aligned = tuple(part for part in card_parts if part in evidence_parts)
    return ", ".join(aligned or card_parts)


def fallback_sense_pos(card_pos: object, definition_vi: object) -> str:
    """Build a readable legacy fallback with one card-POS cell per VI sense."""
    definition_vi_text = str(definition_vi or "")
    if not definition_vi_text:
        return ""
    cell = ", ".join(normalize_pos_parts(card_pos))
    return "|".join(cell for _ in definition_vi_text.split("|"))


def valid_sense_pos_cell(card_pos: object, sense_pos: object) -> bool:
    """Return whether a cell is a canonical ordered subset of card-level POS."""
    card_parts = normalize_pos_parts(card_pos)
    cell_text = str(sense_pos or "")
    cell_parts = normalize_pos_parts(cell_text)
    if not card_parts or not cell_parts:
        return False
    expected = tuple(part for part in card_parts if part in set(cell_parts))
    return (
        cell_parts == expected
        and cell_text == ", ".join(cell_parts)
    )


__all__ = [
    "build_source_sense_pos_index",
    "derive_sense_pos_cell",
    "fallback_sense_pos",
    "normalize_pos_parts",
    "valid_sense_pos_cell",
]
