"""Public API: compute_card_updates(jsonl_records, txt_lines) -> list[CardUpdate].

A CardUpdate is a (guid, old_tags, new_tags) tuple OR None for "no change".

Behavior:
  - For each .txt card, look up matching jsonl record by (word_lower, pos, source).
  - If jsonl record has opal in (W, S) AND .txt Tags (col 15) doesn't have OPAL_<W|S>:
      -> return CardUpdate(guid, old_tags, old_tags + f' OPAL_<W|S>')
  - Otherwise: return None (no change).

The function is pure: takes inputs, returns list. No I/O, no side effects.
"""
from __future__ import annotations
from typing import Iterable, NamedTuple


class CardUpdate(NamedTuple):
    guid: str
    word: str
    pos: str
    source: str
    old_tags: str
    new_tags: str
    opal_added: str  # "OPAL_W" or "OPAL_S"


HEADER_LINES = 6  # 6 #separator/html/guid/notetype/deck/tags lines


def _build_jsonl_index(jsonl_records: list[dict]) -> dict[tuple, dict]:
    """Index jsonl records by (word_lower, pos, source).

    pos in jsonl is a list. We index by (word, each_pos_in_list, source).
    source: 'Oxford' if first source_file starts with 'oxford_', else 'Cambridge', else None.
    """
    index = {}
    for r in jsonl_records:
        word_l = r.get('word', '').lower()
        pos_list = r.get('pos', [])
        if isinstance(pos_list, str):
            pos_list = [pos_list]
        sf = r.get('source_files', [])
        if sf and sf[0].startswith('oxford_'):
            src = 'Oxford'
        elif sf and sf[0].startswith('cambridge_'):
            src = 'Cambridge'
        else:
            src = None
        for p in pos_list:
            key = (word_l, p, src)
            if key not in index:
                index[key] = r
    return index


def _parse_txt_card(line: str) -> dict | None:
    """Parse one .txt data line. Return dict or None if malformed."""
    parts = line.split('\t')
    if len(parts) < 16:
        return None
    guid, _nt, _deck, word, pos, _ipa, _def, _ex, _wf, _col, _uk, _us, src1, src2, _cefr, tags = parts
    return {
        'guid': guid,
        'word': word.split(' (')[0].strip().lower(),
        'pos': pos,
        'source': src1,
        'tags': tags,
    }


def compute_card_updates(
    jsonl_records: list[dict],
    txt_lines: list[str],
) -> list[CardUpdate]:
    """Compute the tag-delta list. Pure function.

    Returns a list of CardUpdate for cards that need a new OPAL_* tag added.
    Cards that are already up-to-date or unmatchable are omitted.
    """
    jsonl_index = _build_jsonl_index(jsonl_records)
    updates = []
    for line in txt_lines[HEADER_LINES:]:
        card = _parse_txt_card(line)
        if not card:
            continue
        rec = jsonl_index.get((card['word'], card['pos'], card['source']))
        if not rec:
            continue
        jsonl_opal = rec.get('opal')
        if jsonl_opal not in ('W', 'S'):
            continue
        expected_tag = f'OPAL_{jsonl_opal}'
        if expected_tag in card['tags'].split():
            continue
        updates.append(CardUpdate(
            guid=card['guid'],
            word=card['word'],
            pos=card['pos'],
            source=card['source'],
            old_tags=card['tags'],
            new_tags=card['tags'] + f' {expected_tag}',
            opal_added=expected_tag,
        ))
    return updates


def apply_updates(txt_lines: list[str], updates: list[CardUpdate]) -> list[str]:
    """Apply updates to txt_lines, returning a new list. Pure: does not mutate input."""
    guid_to_update = {u.guid: u for u in updates}
    out = list(txt_lines)
    for i, line in enumerate(out[HEADER_LINES:], start=HEADER_LINES):
        parts = line.split('\t')
        if len(parts) < 16:
            continue
        guid = parts[0]
        if guid in guid_to_update:
            parts[15] = guid_to_update[guid].new_tags
            out[i] = '\t'.join(parts)
    return out
