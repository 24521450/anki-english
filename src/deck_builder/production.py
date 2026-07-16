"""Contracts shared by the Vietnamese-to-English production card.

The production card is a sibling card generated from the canonical EAVM note;
it does not introduce a second note identity.  Keeping the answer derivation
and eligibility predicate here gives the builder, validator, and package/live
import code one deterministic definition of which notes receive the card.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping


PRODUCTION_ANSWER_FIELD = "production_answer"

# Oxford occasionally appends a parenthetical display disambiguator to a
# headword (for example ``grave (serious)``).  Only a *trailing* parenthetical
# is considered; learning-pattern slots are deliberately left intact.
_TRAILING_DISPLAY_QUALIFIER = re.compile(
    r"^(?P<head>.+?)\s+\((?P<qualifier>[^()]+)\)\s*$"
)
_LEARNING_SLOT = re.compile(
    r"\b(?:sth|sb(?:['’]s)?|something|somebody|someone|somewhere|"
    r"one(?:['’]s)?|"
    r"oneself|yourself|yourselves|himself|herself|itself|ourselves|themselves)\b",
    re.IGNORECASE,
)


def strip_display_qualifier(word: str | None) -> str:
    """Return the canonical answer for a displayed headword.

    Display qualifiers are represented by one final parenthesized phrase.  A
    qualifier containing a learning-pattern slot (``sth``, ``sb``, etc.) is
    part of the answer and is therefore preserved.  No other punctuation,
    morphology, or phrase slot is rewritten.
    """

    value = str(word or "").strip()
    if not value:
        return ""
    match = _TRAILING_DISPLAY_QUALIFIER.match(value)
    if match is None:
        return value
    qualifier = match.group("qualifier").strip()
    if not qualifier or _LEARNING_SLOT.search(qualifier):
        return value
    return match.group("head").strip()


# Short aliases make the intent obvious to callers that deal with card rows.
derive_production_answer = strip_display_qualifier


def production_eligible(
    definition_vi: str | object,
    example: str | None = None,
    production_answer: str | None = None,
) -> bool:
    """Return whether a row has enough content for a Production card.

    The first argument may be a ``BuiltCard``-like object.  Supporting both a
    card and three scalar fields keeps this predicate usable from serializers,
    validators, and package code without importing the ``NamedTuple`` here.
    """

    if example is None and production_answer is None and not isinstance(definition_vi, str):
        card = definition_vi
        if isinstance(card, Mapping):
            definition_vi = card.get("definition_vi", card.get("DefinitionVI", ""))
            example = card.get("example", card.get("Example", ""))
            production_answer = card.get(
                "production_answer", card.get("ProductionAnswer", "")
            )
        else:
            definition_vi = getattr(card, "definition_vi", "")
            example = getattr(card, "example", "")
            production_answer = getattr(card, "production_answer", "")
    return all(
        str(value or "").strip()
        for value in (definition_vi, example, production_answer)
    )


# A descriptive alias used by some callers/tests.
is_production_eligible = production_eligible


def count_production_cards(cards: Iterable) -> int:
    """Count notes whose three canonical Production fields are populated."""

    return sum(1 for card in cards if production_eligible(card))


production_card_count = count_production_cards


def apply_production_answers(cards: Iterable) -> list:
    """Derive deterministic answers after all semantic/review transforms.

    ``_replace`` is intentionally used rather than mutating rows.  The
    helper accepts any iterable and preserves order, which is part of the
    build determinism contract.
    """

    return [
        card._replace(production_answer=derive_production_answer(card.word))
        for card in cards
    ]


# Compatibility/readability alias for pipeline code.
with_production_answers = apply_production_answers


__all__ = [
    "PRODUCTION_ANSWER_FIELD",
    "strip_display_qualifier",
    "derive_production_answer",
    "production_eligible",
    "is_production_eligible",
    "count_production_cards",
    "production_card_count",
    "apply_production_answers",
    "with_production_answers",
]
