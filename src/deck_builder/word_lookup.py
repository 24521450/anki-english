"""Word and sense lookup helpers for registry-driven builds."""
from __future__ import annotations

import re

from src.deck_builder.build_contracts import BuiltCard
from src.deck_builder.corpus_tag_sync import LEARNING_PATTERN_ALIASES


SOURCE_HEADWORD_ALIASES = {
    "contend with sb/sth": "contend with",
}


def get_word_candidates(word: str) -> list[str]:
    display_word = re.sub(r"\s*\(.*?\)\s*", "", word.lower()).strip()
    word_clean = SOURCE_HEADWORD_ALIASES.get(
        display_word,
        LEARNING_PATTERN_ALIASES.get(display_word, display_word),
    )
    cands = [word_clean]
    suffixes = [
        ("ies", "y"), ("ied", "y"), ("ying", "y"),
        ("ed", ""), ("ing", ""), ("ly", ""),
        ("es", ""), ("s", ""), ("er", ""), ("est", ""),
        ("al", ""),
    ]
    for suf, repl in suffixes:
        if word_clean.endswith(suf) and len(word_clean) > len(suf) + 2:
            base = word_clean[:-len(suf)]
            cands.append(base + repl)
            if len(base) > 1 and base[-1] == base[-2] and base[-1] in "bdfglmnprstz":
                cands.append(base[:-1] + repl)
            if suf in ("ed", "ing"):
                cands.append(base + "e")
    if word_clean.endswith("or") and len(word_clean) > 3:
        cands.append(word_clean[:-2] + "our")
    if word_clean.endswith("our") and len(word_clean) > 4:
        cands.append(word_clean[:-3] + "or")
    if "wellbeing" in word_clean:
        cands.append("well-being")
    if "byproduct" in word_clean:
        cands.append("by-product")
    if "shortsighted" in word_clean:
        cands.append("short-sighted")
    irregular = {
        "criteria": "criterion",
        "vertebrae": "vertebra",
        "ligaments": "ligament",
    }
    if word_clean in irregular:
        cands.append(irregular[word_clean])
    seen = set()
    deduped = []
    for candidate in cands:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def resolve_primary_record(
    matched_records: list[dict],
    contributing_records: list[dict],
) -> dict:
    if not matched_records:
        raise ValueError("matched_records cannot be empty")

    unique_contributors: list[dict] = []
    seen_ids: set[int] = set()
    for record in contributing_records:
        record_id = id(record)
        if record_id not in seen_ids:
            seen_ids.add(record_id)
            unique_contributors.append(record)

    if len(unique_contributors) == 1:
        return unique_contributors[0]
    return matched_records[0]


def find_idioms_for_word(word_clean: str, idioms_db: dict) -> list[tuple[dict, dict]]:
    if word_clean in idioms_db:
        return idioms_db[word_clean]
    for phrase_clean, records in idioms_db.items():
        if word_clean in phrase_clean or phrase_clean in word_clean:
            return records
    return []


def get_senses_for_card(card: BuiltCard, senses_index: dict) -> list:
    word_clean = card.word.split(" (")[0].strip().lower()
    cands = get_word_candidates(word_clean)
    pos_parts = [part.strip().lower() for part in card.pos.split(",") if part.strip()]
    card_cefr = card.cefr.strip().upper() if card.cefr else "UNCLASSIFIED"

    senses = []
    for cand in cands:
        for pos in pos_parts:
            key = (cand, pos, card_cefr)
            if key in senses_index:
                senses.extend(senses_index[key])
        if senses:
            break

    if not senses:
        for cand in cands:
            for (word, pos, _), sense_list in senses_index.items():
                if word == cand and pos in pos_parts:
                    senses.extend(sense_list)
            if senses:
                break
    return senses
