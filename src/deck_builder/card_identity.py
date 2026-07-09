"""Shared identity helpers for deck build and registry work."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


LIST_PRIORITY: Final[tuple[str, ...]] = ("Oxford_5000", "Oxford_3000", "AWL_Coxhead")
CANONICAL_LIST_PRIORITY: Final[tuple[str, ...]] = ("Oxford_5000", "Oxford_3000", "AWL")

# Registry canonicalization keeps AWL as the stored list name while the
# existing deck tags continue to use the legacy AWL_Coxhead token.
LIST_ALIASES: Final[dict[str, str]] = {
    "AWL_Coxhead": "AWL",
    "AWL": "AWL",
}

# Reviewed identity exceptions are the only cards allowed to carry a non-empty
# registry variant. They cover true homonyms and explicitly reviewed POS splits.
# The value is the exact variant label written into the registry row.
REVIEWED_IDENTITY_VARIANTS: Final[dict[tuple[str, str, str], frozenset[str]]] = {
    ("converse", "UNCLASSIFIED", "AWL"): frozenset({"verb", "adjective, noun"}),
    ("trail", "C1", "Oxford_5000"): frozenset({"noun", "verb"}),
    ("bow", "C1", "Oxford_5000"): frozenset({"noun, verb", "noun"}),
    ("hint", "C1", "Oxford_5000"): frozenset({"noun", "verb"}),
    ("rally", "C1", "Oxford_5000"): frozenset({"noun", "verb"}),
}

# Compatibility for archived migrations that predate reviewed POS variants.
REVIEWED_HOMONYM_VARIANTS = REVIEWED_IDENTITY_VARIANTS


@dataclass(frozen=True, slots=True)
class CardIdentity:
    """Canonical registry identity."""

    word: str
    cefr: str
    list: str
    variant: str = ""

    def as_key(self) -> tuple[str, str, str, str]:
        return (self.word, self.cefr, self.list, self.variant)


CardRegistryKey = tuple[str, str, str, str]


def normalize_word(word: str | None) -> str:
    return (word or "").strip()


def normalize_cefr(cefr: str | None) -> str:
    return (cefr or "").strip().upper() or "UNCLASSIFIED"


def normalize_variant(variant: str | None) -> str:
    return (variant or "").strip()


def normalize_list_name(list_name: str | None, *, canonical: bool = False) -> str:
    raw = (list_name or "").strip()
    if not canonical:
        return raw
    return LIST_ALIASES.get(raw, raw)


def primary_list_from_tags(tags: str | None, *, canonical: bool = False) -> str:
    """Resolve the primary corpus/list bucket from a tags string."""
    tokens = {token for token in (tags or "").split() if token}
    priority = CANONICAL_LIST_PRIORITY if canonical else LIST_PRIORITY

    for token in priority:
        if token in tokens:
            return normalize_list_name(token, canonical=canonical)

    if "AWL_Coxhead" in tokens or "AWL" in tokens:
        return "AWL" if canonical else "AWL_Coxhead"
    return "NO_LIST"


def reviewed_identity_variant(
    word: str | None,
    cefr: str | None,
    list_name: str | None,
    pos: str | None,
) -> str:
    """Return the reviewed identity variant, or '' if none applies."""
    word_key = normalize_word(word).lower()
    cefr_key = normalize_cefr(cefr)
    list_key = normalize_list_name(list_name, canonical=True)
    pos_key = normalize_variant(pos).lower()

    allowed = REVIEWED_IDENTITY_VARIANTS.get((word_key, cefr_key, list_key))
    if allowed and pos_key in allowed:
        return pos_key
    return ""


def reviewed_homonym_variant(
    word: str | None,
    cefr: str | None,
    list_name: str | None,
    pos: str | None,
) -> str:
    """Compatibility alias for the former homonym-only contract."""
    return reviewed_identity_variant(word, cefr, list_name, pos)
