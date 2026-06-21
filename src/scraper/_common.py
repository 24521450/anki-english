"""Shared utilities for scraper modules.

Functions here are source-agnostic — used by both Oxford and Cambridge parsers
and any downstream stage that needs a common view of bucketed data.
"""
from __future__ import annotations


def flatten_collocations(d: dict[str, list[str]]) -> list[str]:
    """Flatten a bucketed collocations dict into a single list.

    Schema accepts two shapes:
      - Oxford: {"adverb": [...], "phrases": [...], "verb + head": [...]}
        (multiple category keys)
      - Cambridge: {"collocations": [...]} (single flat bucket)

    Both shapes flatten to a list[str] preserving insertion order.
    """
    out: list[str] = []
    for vals in d.values():
        out.extend(vals)
    return out
