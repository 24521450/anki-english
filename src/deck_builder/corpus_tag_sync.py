"""Sync corpus tags (Oxford_3000 / Oxford_5000) on .txt deck.

Source of truth: vocab_list/Oxford/{Oxford_3000,Oxford_5000}.md
The vocab_list is keyed on (word, POS, CEFR) — which is the right granularity
for our cards. The jsonl `oxford_lists` field is coarser (per-word, no CEFR
discrimination), so we use vocab_list directly.

For each card with Oxford_3000 / Oxford_5000 tag:
  1. Look up vocab_3000 for (word, ANY_POS_IN_CARD, card.cefr)
     - "ANY_POS_IN_CARD" means: any POS value in the card's pos list appears
       in the vocab entry at this CEFR
  2. If found -> card SHOULD have Oxford_3000 tag
     Else -> card should NOT have Oxford_3000 tag
  3. Same for Oxford_5000

A card's pos is comma-separated like "adjective, noun". For the lookup we
need at least ONE of the card's POS values to match a vocab entry at the
card's CEFR.
"""
from __future__ import annotations
from pathlib import Path
import re
from typing import NamedTuple

HEADER_LINES = 6
OXFORD_3000 = "Oxford 3000"
OXFORD_5000 = "Oxford 5000"
TOKEN_3000 = "Oxford_3000"
TOKEN_5000 = "Oxford_5000"
CORPUS_TOKENS = {TOKEN_3000, TOKEN_5000}


class TagUpdate(NamedTuple):
    guid: str
    word: str
    pos: str
    source: str
    old_tags: str
    new_tags: str
    added: list[str]
    removed: list[str]


# POS normalization: vocab_list uses 'n.', 'v.', 'adj.' -> jsonl uses 'noun', 'verb', 'adjective'
POS_NORM = {
    'n': 'noun', 'v': 'verb', 'adj': 'adjective', 'adv': 'adverb',
    'prep': 'preposition', 'pron': 'pronoun', 'det': 'determiner',
    'conj': 'conjunction', 'num': 'number', 'modal': 'modal',
    'predet': 'predeterminer', 'aux': 'auxiliary', 'exclam': 'exclamation',
    'abbr': 'abbreviation', 'exclamation': 'exclamation',
    'indefinite article': 'indefinite article', 'definite article': 'definite article',
    'number': 'number',
}


def _parse_vocab_list(path: Path) -> set[tuple[str, str, str]]:
    """Parse vocab_list/Oxford/*.md. Returns (word_lower, pos, cefr) tuples."""
    out = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.startswith('| **'):
            continue
        m = re.match(r'\| \*\*([^*]+)\*\* \| ([^|]+) \| ([^|]+) \|', line)
        if not m:
            continue
        word = m.group(1).strip()
        word_clean = word.split(' (')[0].strip().lower()
        pos_str = m.group(2).strip()
        cefr = m.group(3).strip().upper()
        # Special case: 'a, an' is a single entry with 'indefinite article' POS
        if word_clean == 'a, an' or word_clean == 'a':
            pos_list = ['indefinite article']
        else:
            raw_parts = []
            for p in re.split(r',|/', pos_str):
                p = p.strip()
                if p:
                    raw_parts.append(p)
            pos_list = []
            for p in raw_parts:
                p_clean = p.rstrip('.')
                pos_list.append(POS_NORM.get(p_clean, p_clean))
        for p in pos_list:
            out.add((word_clean, p, cefr))
    return out


def _parse_deck_pos(pos_str: str) -> list[str]:
    """'adjective, noun' -> ['adjective', 'noun']."""
    return [p.strip() for p in pos_str.split(",") if p.strip()]


def _parse_txt_card(line: str) -> dict | None:
    parts = line.split("\t")
    if len(parts) < 16:
        return None
    guid, _nt, _deck, word, pos, *_rest, tags = parts
    return {
        "guid": guid,
        "word": word.split(" (")[0].strip().lower(),
        "pos_str": pos,
        "pos_list": _parse_deck_pos(pos),
        "source": parts[12],
        "tags": tags,
    }


def _card_should_have_corpus_tag(
    card: dict, vocab_set: set[tuple[str, str, str]], cefr: str
) -> bool:
    """Return True if vocab_list says card's (word, any_pos, cefr) is in this list."""
    for w, p, c in vocab_set:
        if w == card['word'] and c == cefr and p in card['pos_list']:
            return True
    return False


def compute_tag_updates(
    txt_lines: list[str],
    vocab_3000: set[tuple[str, str, str]],
    vocab_5000: set[tuple[str, str, str]],
) -> list[TagUpdate]:
    """Compute corpus-tag deltas. Pure function.

    For EVERY card (not just those with corpus tags), decide per vocab_list
    whether Oxford_3000 / Oxford_5000 should be present. Add or remove as
    needed to converge to vocab_list as the source of truth.

    Why scan all cards (not just ones with corpus tags)? Because vocab_list
    edits (e.g. user adds 'striking adj. C1' to 5000.md) should propagate to
    cards that currently lack the tag.
    """
    updates = []
    for line in txt_lines[HEADER_LINES:]:
        card = _parse_txt_card(line)
        if not card:
            continue
        parts = line.split("\t")
        cefr = parts[14] if len(parts) > 14 else None
        if cefr is None:
            continue
        # Skip cards that have NO corpus signal in either direction
        # (we don't want to add corpus tags to cards that were never in any list)
        # Heuristic: only update if either (a) card already has a corpus tag,
        # or (b) vocab_list has the card at ANY CEFR (in either list).
        tag_set = set(card["tags"].split())
        has_corpus = bool(tag_set & CORPUS_TOKENS)
        in_any_vocab = (
            any(w == card['word'] for (w, _, _) in vocab_3000)
            or any(w == card['word'] for (w, _, _) in vocab_5000)
        )
        if not has_corpus and not in_any_vocab:
            continue
        # Decide what tags SHOULD be present (per vocab_list at this card's CEFR)
        new_tokens: set[str] = set()
        if _card_should_have_corpus_tag(card, vocab_3000, cefr):
            new_tokens.add(TOKEN_3000)
        if _card_should_have_corpus_tag(card, vocab_5000, cefr):
            new_tokens.add(TOKEN_5000)
        # Diff
        old_tokens = tag_set & CORPUS_TOKENS
        if old_tokens == new_tokens:
            continue
        # Build new tag string
        kept_tags = [t for t in card["tags"].split() if t not in CORPUS_TOKENS]
        new_tag_list = kept_tags + sorted(new_tokens)
        new_tags_str = " ".join(new_tag_list)
        updates.append(TagUpdate(
            guid=card["guid"],
            word=card["word"],
            pos=card["pos_str"],
            source=card["source"],
            old_tags=card["tags"],
            new_tags=new_tags_str,
            added=sorted(new_tokens - old_tokens),
            removed=sorted(old_tokens - new_tokens),
        ))
    return updates


def apply_updates(txt_lines: list[str], updates: list[TagUpdate]) -> list[str]:
    """Apply updates to txt_lines. Pure: does not mutate input."""
    guid_to_update = {u.guid: u for u in updates}
    out = list(txt_lines)
    for i, line in enumerate(out[HEADER_LINES:], start=HEADER_LINES):
        parts = line.split("\t")
        if len(parts) < 16:
            continue
        guid = parts[0]
        if guid in guid_to_update:
            parts[15] = guid_to_update[guid].new_tags
            out[i] = "\t".join(parts)
    return out
