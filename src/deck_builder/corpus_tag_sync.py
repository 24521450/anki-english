"""Sync corpus tags (Oxford_3000 / Oxford_5000) on .txt deck.

Source of truth: vocab_list/Oxford/{Oxford_3000,Oxford_5000}.md
The vocab_list is keyed on (word, POS, CEFR) — which is the right granularity
for our cards.
"""
from __future__ import annotations
from pathlib import Path
import re
from typing import NamedTuple

HEADER_LINES = 6
OXFORD_3000 = "Oxford 3000"
OXFORD_5000 = "Oxford 5000"
AWL_COXHEAD = "AWL Coxhead"

TOKEN_3000 = "Oxford_3000"
TOKEN_5000 = "Oxford_5000"
TOKEN_AWL = "AWL_Coxhead"
LEGACY_TOKEN_AWL = "AWL"
CORPUS_TOKENS = {TOKEN_3000, TOKEN_5000, TOKEN_AWL, LEGACY_TOKEN_AWL}

HEADWORD_ALIASES = {
    "criteria": "criterion",
    "labour": "labor",
    "maximise": "maximize",
    "minimise": "minimize",
    "utilise": "utilize",
}

DECK_OXFORD_5000 = "English Academic Vocabulary::Oxford::Oxford 5000"
DECK_OXFORD_3000_ADVANCED = (
    "English Academic Vocabulary::Oxford::Oxford 3000 Advanced"
)
DECK_OXFORD_3000_BASIC = "English Academic Vocabulary::Oxford::Oxford 3000 Basic"
DECK_AWL = "English Academic Vocabulary::AWL 50 Academic Words"
DECK_OXFORD = "English Academic Vocabulary::Oxford"


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
    'phrasal v': 'phrasal verb', 'phrasal verb': 'phrasal verb',
    'indefinite article': 'indefinite article', 'definite article': 'definite article',
    'number': 'number',
}


def parse_header(path: Path) -> int:
    """Read the first few lines of a file to find the `#tags column:` value.
    Defaults to 17 if not found.
    """
    if not path.exists():
        return 17
    for line in path.read_text(encoding='utf-8').splitlines()[:10]:
        if line.startswith('#tags column:'):
            try:
                return int(line.split(':')[1].strip())
            except ValueError:
                pass
    return 17


def _parse_vocab_list(path: Path) -> set[tuple[str, str, str]]:
    """Parse vocab_list/Oxford/*.md or AWL.md. Returns (word_lower, pos, cefr) tuples."""
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


def _parse_txt_card(line: str, tags_col: int = 16) -> dict | None:
    parts = line.rstrip('\r\n').split("\t")
    if len(parts) < 16:
        return None
    # Pad to 19 columns
    if len(parts) < 19:
        parts = parts + [''] * (19 - len(parts))

    # Extract tags depending on tags_col index
    if tags_col == 19:
        tags = parts[18]
    elif tags_col == 17:
        tags = parts[16]
    else:
        tags = parts[tags_col - 1]

    return {
        "guid": parts[0],
        "word": parts[3].split(" (")[0].strip().lower(),
        "pos_str": parts[4],
        "pos_list": _parse_deck_pos(parts[4]),
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


def get_vocab_membership(
    word: str,
    pos_str: str,
    cefr: str,
    vocab_3000: set[tuple[str, str, str]],
    vocab_5000: set[tuple[str, str, str]],
) -> tuple[bool, bool]:
    """Determine list membership by (word, any POS, CEFR), including exceptions."""
    word_clean = word.split(' (')[0].strip().lower()
    cefr_upper = cefr.strip().upper()
    pos_parts = [p.strip().lower() for p in pos_str.split(',') if p.strip()]

    is_in_3000 = False
    is_in_5000 = False

    for pos_part in pos_parts:
        if (word_clean, pos_part, cefr_upper) in vocab_3000:
            is_in_3000 = True
        if (word_clean, pos_part, cefr_upper) in vocab_5000:
            is_in_5000 = True

    # Sole explicit exception: nursing|noun|B2 (vocab list has adj., card has noun)
    if word_clean == 'nursing' and cefr_upper == 'B2' and 'noun' in pos_parts:
        is_in_5000 = True

    return is_in_3000, is_in_5000


def route_deck(
    current_deck: str,
    is_in_3000: bool,
    is_in_5000: bool,
    word: str,
    pos_str: str,
    cefr: str,
    is_in_awl_coxhead: bool = False,
) -> str:
    """Apply deck routing logic:

    1. Oxford_5000 or nursing exception -> nested Oxford 5000 deck.
    2. Oxford_3000 + B2 -> nested Oxford 3000 Advanced deck.
    3. Oxford_3000 + A1/A2/B1 -> nested Oxford 3000 Basic deck.
    4. AWL_Coxhead -> AWL 50 Academic Words deck.
    5. Not in any list -> keep current deck (if AWL deck, move to Oxford).
    """
    word_clean = word.split(' (')[0].strip().lower()
    cefr_upper = cefr.strip().upper()
    pos_parts = [p.strip().lower() for p in pos_str.split(',') if p.strip()]

    # nursing exception for Oxford_5000 routing
    is_nursing_exception = (word_clean == 'nursing' and cefr_upper == 'B2' and 'noun' in pos_parts)

    if is_in_5000 or is_nursing_exception:
        return DECK_OXFORD_5000
    elif is_in_3000:
        if cefr_upper == 'B2':
            return DECK_OXFORD_3000_ADVANCED
        elif cefr_upper in ('A1', 'A2', 'B1'):
            return DECK_OXFORD_3000_BASIC
    elif is_in_awl_coxhead:
        return DECK_AWL

    if current_deck == DECK_AWL:
        return DECK_OXFORD

    return current_deck


def apply_corpus_routing_and_tags(
    cards: list,
    vocab_3000: set[tuple[str, str, str]],
    vocab_5000: set[tuple[str, str, str]],
    vocab_awl: set[tuple[str, str, str]] | None = None,
) -> list:
    """Post-process built cards to update tags and route decks.

    Rules:
    1. Oxford tags assigned first per (word, any POS, CEFR).
    2. Oxford headwords identified (any headword with Oxford_3000 or Oxford_5000).
    3. AWL_Coxhead assigned ONLY to Coxhead headwords that have NO Oxford tag across all cards of the headword.
    4. Each card gets AT MOST ONE list tag (Oxford_5000 > Oxford_3000 > AWL_Coxhead > NO_LIST).
    5. Remove legacy AWL tag if present.
    6. Card with AWL_Coxhead routes to English Academic Vocabulary::AWL 50 Academic Words.
    7. Card without list tag in wrong deck (e.g. rover) routes to English Academic Vocabulary::Oxford.
    """
    awl_headwords = set()
    if vocab_awl:
        for w, _, _ in vocab_awl:
            awl_headwords.add(HEADWORD_ALIASES.get(w, w))
    awl_headwords.update({"criterion", "labor", "maximize", "minimize", "utilize"})

    # Pass 1: Identify all headwords that possess an Oxford tag
    oxford_headwords = set()
    for c in cards:
        w_clean = c.word.split(" (")[0].strip().lower()
        hw = HEADWORD_ALIASES.get(w_clean, w_clean)
        is_in_3000, is_in_5000 = get_vocab_membership(c.word, c.pos, c.cefr, vocab_3000, vocab_5000)
        tags_set = set(c.tags.split())
        if is_in_3000 or is_in_5000 or "Oxford_3000" in tags_set or "Oxford_5000" in tags_set:
            oxford_headwords.add(hw)

    # Pass 2: Assign tags and route decks
    updated_cards = []
    for c in cards:
        w_clean = c.word.split(" (")[0].strip().lower()
        hw = HEADWORD_ALIASES.get(w_clean, w_clean)
        is_in_3000, is_in_5000 = get_vocab_membership(c.word, c.pos, c.cefr, vocab_3000, vocab_5000)

        assigned_tag = None
        if is_in_5000:
            assigned_tag = TOKEN_5000
        elif is_in_3000:
            assigned_tag = TOKEN_3000
        elif hw in awl_headwords and hw not in oxford_headwords:
            assigned_tag = TOKEN_AWL

        tags_list = [t for t in c.tags.split() if t not in CORPUS_TOKENS]
        if assigned_tag:
            tags_list.append(assigned_tag)
        new_tags = " ".join(tags_list)

        # Route deck
        new_deck = route_deck(
            c.deck, is_in_3000, is_in_5000, c.word, c.pos, c.cefr,
            is_in_awl_coxhead=(assigned_tag == TOKEN_AWL)
        )

        c_new = c._replace(tags=new_tags, deck=new_deck)
        updated_cards.append(c_new)

    return updated_cards


def compute_tag_updates(
    txt_lines: list[str],
    vocab_3000: set[tuple[str, str, str]],
    vocab_5000: set[tuple[str, str, str]],
) -> list[TagUpdate]:
    """Compute corpus-tag deltas. Pure function."""
    tags_col = 17
    for line in txt_lines[:HEADER_LINES]:
        if line.startswith('#tags column:'):
            try:
                tags_col = int(line.split(':')[1].strip())
            except ValueError:
                pass

    updates = []
    for line in txt_lines[HEADER_LINES:]:
        card = _parse_txt_card(line, tags_col)
        if not card:
            continue
        parts = line.split("\t")
        cefr = parts[14] if len(parts) > 14 else None
        if cefr is None:
            continue

        tag_set = set(card["tags"].split())
        has_corpus = bool(tag_set & CORPUS_TOKENS)
        in_any_vocab = (
            any(w == card['word'] for (w, _, _) in vocab_3000)
            or any(w == card['word'] for (w, _, _) in vocab_5000)
        )
        if not has_corpus and not in_any_vocab:
            continue

        # Decide what tags SHOULD be present (per vocab_list at this card's CEFR)
        # Note: here we also use get_vocab_membership to align with new logic
        is_in_3000, is_in_5000 = get_vocab_membership(card["word"], card["pos_str"], cefr, vocab_3000, vocab_5000)
        new_tokens: set[str] = set()
        if is_in_3000:
            new_tokens.add(TOKEN_3000)
        if is_in_5000:
            new_tokens.add(TOKEN_5000)

        old_tokens = tag_set & CORPUS_TOKENS
        if old_tokens == new_tokens:
            continue

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
    tags_col = 17
    for line in txt_lines[:HEADER_LINES]:
        if line.startswith('#tags column:'):
            try:
                tags_col = int(line.split(':')[1].strip())
            except ValueError:
                pass

    guid_to_update = {u.guid: u for u in updates}
    out = list(txt_lines)
    for i, line in enumerate(out[HEADER_LINES:], start=HEADER_LINES):
        parts = line.split("\t")
        if len(parts) < 16:
            continue
        guid = parts[0]
        if guid in guid_to_update:
            # Pad if needed
            if len(parts) < tags_col:
                parts = parts + [''] * (tags_col - len(parts))
            parts[tags_col - 1] = guid_to_update[guid].new_tags
            out[i] = "\t".join(parts)
    return out
