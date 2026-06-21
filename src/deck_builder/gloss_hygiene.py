"""Gloss hygiene helpers — shared P0 mechanical normalization.

Per user plan (2026-06-21, "P0 Gloss Hygiene Cleanup"):
  1. Unescape literal ``\\|`` → ``|`` (some manual edits wrote ``\\|`` thinking it
     was the way to escape the pipe in audit/JSONL, but JSONL stores ``|`` literally
     — the backslash is just noise).
  2. Normalize pipe spacing to compact: ``a | b`` / ``a |b`` / ``a| b`` → ``a|b``.
     Semicolon is left as-is (style not part of P0 scope).
  3. Infer ``separator``:
       - ``|`` if any pipe after un-escape
       - ``;`` if any semicolon
       - ``none`` otherwise
  4. Recompute ``gloss_word_count`` using the validator's rule:
       ``len(re.sub(r"[|;]", " ", gloss).split())``
     (mirror of ``src.deck_builder.gloss_llm.validate_verdict`` word-count formula).

This module is the single source of truth — both the apply tool
(``tools/_apply_gloss_hygiene.py``) and the merge tool
(``tools/_merge_expanded_glosses.py``) use these helpers, so future edits
can't drift again.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Literal backslash + pipe (the "escaped pipe" bug).
_ESCAPED_PIPE = "\\|"

# Match any pipe with optional surrounding whitespace:
#   ' | ', ' |', '| '
# Capture group 1 = leading whitespace, group 2 = trailing whitespace.
_PIPE_SPACING_RE = re.compile(r"( *)\|( *)")


@dataclass
class HygieneResult:
    """Result of normalizing one gloss string."""

    gloss: str
    separator: str  # '|' | ';' | 'none'
    gloss_word_count: int
    # Diagnostics — what changed (None if no change).
    unescaped_pipe: bool
    pipe_spacing_compacted: bool

    def changed(self) -> bool:
        return self.unescaped_pipe or self.pipe_spacing_compacted


def normalize_gloss(raw: str) -> HygieneResult:
    """Normalize one gloss string and return the canonical (gloss, separator, wc).

    Pure function — no I/O, no mutation of input.
    """
    if raw is None:
        raw = ""
    original = raw

    # Step 1: un-escape literal backslash-pipe → pipe.
    unescaped = _ESCAPED_PIPE in raw
    gloss = raw.replace(_ESCAPED_PIPE, "|")

    # Step 2: compact pipe spacing.
    spacing_changed = False
    if "|" in gloss:
        new_gloss = _PIPE_SPACING_RE.sub("|", gloss)
        if new_gloss != gloss:
            spacing_changed = True
        gloss = new_gloss

    # Step 3: infer separator (after un-escape, before any other mutation).
    if "|" in gloss:
        separator = "|"
    elif ";" in gloss:
        separator = ";"
    else:
        separator = "none"

    # Step 4: recompute word count using validator's rule.
    wc = len(re.sub(r"[|;]", " ", gloss).split())

    return HygieneResult(
        gloss=gloss,
        separator=separator,
        gloss_word_count=wc,
        unescaped_pipe=unescaped,
        pipe_spacing_compacted=spacing_changed,
    )


def compact_pipe_in_text(text: str) -> tuple[str, bool]:
    """Compact pipe spacing in free-form text (e.g. TXT def cells).

    Same rule as normalize_gloss step 2 (compact any `a | b` / `a |b` / `a| b` → `a|b`),
    plus un-escape literal ``\\|`` → ``|``. Semicolons are not touched.

    Returns (new_text, changed).
    """
    if not text:
        return text, False
    original = text
    text = text.replace(_ESCAPED_PIPE, "|")
    text = _PIPE_SPACING_RE.sub("|", text)
    return text, text != original
