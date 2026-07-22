"""Derive POS-scoped Oxford OPAL tags from canonical source records."""
from __future__ import annotations

from collections.abc import Iterable

from src.deck_builder.corpus_tag_sync import corpus_lookup_identity


OPAL_MARKERS = ("W", "S")
OPAL_TAGS = frozenset(f"OPAL_{marker}" for marker in OPAL_MARKERS)

OpalMembership = tuple[str, ...]
OpalIndex = dict[tuple[str, str], frozenset[OpalMembership]]


def _normalize_membership(value: object, *, word: str, pos: str) -> OpalMembership:
    membership = tuple(value) if isinstance(value, list) else None
    if membership not in (("W",), ("S",), ("W", "S")):
        raise ValueError(
            f"invalid OPAL membership for {word!r}/{pos!r}: {value!r}"
        )
    return membership


def build_opal_index(records: Iterable[dict]) -> OpalIndex:
    """Index every Oxford record's OPAL candidate, including empty values."""
    candidates: dict[tuple[str, str], set[OpalMembership]] = {}
    for record in records:
        word = (record.get("word") or "").strip().casefold()
        if not word:
            continue

        raw_opal = record.get("opal")
        if raw_opal is None:
            opal_by_pos: dict[str, OpalMembership] = {}
        elif isinstance(raw_opal, dict) and raw_opal:
            opal_by_pos = {}
            for raw_pos, value in raw_opal.items():
                pos = str(raw_pos).strip().casefold()
                if not pos:
                    raise ValueError(f"invalid empty OPAL POS for {word!r}")
                if pos in opal_by_pos:
                    raise ValueError(f"duplicate OPAL POS for {word!r}: {pos!r}")
                opal_by_pos[pos] = _normalize_membership(value, word=word, pos=pos)
        else:
            raise ValueError(f"invalid OPAL mapping for {word!r}: {raw_opal!r}")

        positions: set[str] = set(opal_by_pos)
        positions.update(
            str(pos_data.get("pos")).strip().casefold()
            for pos_data in (record.get("pos_data") or [])
            if pos_data.get("pos") and str(pos_data.get("pos")).strip()
        )

        for pos in positions:
            membership = opal_by_pos.get(pos, ())
            candidates.setdefault((word, pos), set()).add(membership)

    return {key: frozenset(values) for key, values in candidates.items()}


def apply_opal_tags(cards: Iterable, index: OpalIndex) -> list:
    """Replace stale OPAL tags using each card's final Oxford word/POS identity."""
    updated = []
    for card in cards:
        tags = [token for token in card.tags.split() if token not in OPAL_TAGS]
        memberships: set[str] = set()

        if card.source1 == "Oxford":
            word, positions = corpus_lookup_identity(card.word, card.pos)
            for pos in positions:
                candidates = index.get((word, pos))
                if not candidates:
                    continue
                if len(candidates) != 1:
                    rendered = [list(value) for value in sorted(candidates)]
                    raise ValueError(
                        f"ambiguous OPAL membership for {word!r}/{pos!r}: "
                        f"{rendered!r}"
                    )
                memberships.update(next(iter(candidates)))

        tags.extend(
            f"OPAL_{marker}" for marker in OPAL_MARKERS if marker in memberships
        )
        updated.append(card._replace(tags=" ".join(tags)))

    return updated
