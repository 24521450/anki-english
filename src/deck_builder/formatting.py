"""Formatting helpers for deck-builder fields."""
from __future__ import annotations

from src.deck_builder.build_contracts import (
    COLL_SEPARATOR,
    EX_SEP,
    MAX_IDIOM_EXAMPLES_PER_IDIOM,
    MAX_IDIOMS_PER_CARD,
)
from src.scraper._common import flatten_collocations


def format_examples(examples: list, max_n: int = 1) -> str:
    parts = []
    for ex in (examples or [])[:max_n]:
        text = (ex.get("text") or "").strip()
        if text:
            parts.append(text)
    return EX_SEP.join(parts)


def format_collocations(colls: dict) -> str:
    flat = flatten_collocations(colls or {})
    seen: set[str] = set()
    out: list[str] = []
    for value in flat:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return COLL_SEPARATOR.join(out)


def normalize_idiom_example_key(value: str) -> str:
    """Normalize only for card-local duplicate comparison."""
    return " ".join((value or "").split()).casefold()


def parse_serialized_idiom_examples(value: str) -> list[list[str]]:
    """Return non-empty example cells for each serialized idiom entry."""
    groups: list[list[str]] = []
    for entry in value.split("$$") if value else []:
        if not entry.strip():
            continue
        parts = entry.split("::", 2)
        raw_examples = parts[2] if len(parts) == 3 else ""
        groups.append([
            example.strip()
            for example in raw_examples.split("|")
            if example.strip()
        ])
    return groups


def format_idioms(idioms: list) -> str:
    if not idioms:
        return ""
    selected = list(idioms)
    if len(selected) > MAX_IDIOMS_PER_CARD:
        selected = sorted(
            enumerate(selected),
            key=lambda item: (not bool(item[1].get("cefr")), item[0]),
        )
        selected = [idiom for _, idiom in selected[:MAX_IDIOMS_PER_CARD]]
    parts: list[str] = []
    seen_example_keys: set[str] = set()
    for idiom in selected:
        phrase = (idiom.get("phrase") or "").strip()
        text = (idiom.get("text") or "").strip()
        selected_examples: list[str] = []
        for example in idiom.get("examples") or []:
            display_text = (example or "").strip()
            key = normalize_idiom_example_key(display_text)
            if not key or key in seen_example_keys:
                continue
            selected_examples.append(display_text)
            seen_example_keys.add(key)
            if len(selected_examples) == MAX_IDIOM_EXAMPLES_PER_IDIOM:
                break
        ex_str = "|".join(selected_examples)
        inner = " :: ".join(part for part in [phrase, text, ex_str] if part)
        if inner:
            parts.append(inner)
    return "$$".join(parts)


def format_wordfamily(verb_forms: dict) -> str:
    if not verb_forms:
        return ""
    pos_map = {
        "root": "n",
        "thirdps": "v",
        "past": "v",
        "pastpart": "v",
        "prespart": "v",
        "neg": "v",
        "short": "v",
        "rareshortform": "v",
    }
    parts: list[str] = []
    for form_key, word_val in verb_forms.items():
        if word_val:
            pos_short = pos_map.get(form_key, "n")
            parts.append(f"{word_val} ({pos_short})")
    return "\\n".join(parts)


def format_ipa(ipa: str | None) -> str:
    return (ipa or "").strip()


def normalize_ipa(value) -> str:
    if not value:
        return ""
    return str(value).strip().strip("/").strip()


def format_ipa_field(uk_ipa, us_ipa) -> str:
    uk = normalize_ipa(uk_ipa)
    us = normalize_ipa(us_ipa)
    if uk and us:
        if uk == us:
            return f"/{uk}/"
        return f"UK: /{uk}/ | US: /{us}/"
    if uk:
        return f"/{uk}/"
    if us:
        return f"/{us}/"
    return ""


def format_audio(audio: dict | None) -> tuple[str, str]:
    audio_data = audio or {}
    return audio_data.get("uk") or "", audio_data.get("us") or ""
