"""Audio filename resolution for deck-builder output."""
from __future__ import annotations

import re
from pathlib import Path

from src.scraper.cambridge_audio import resolve_audio_pos


def audio_dir_filenames(audio_dir: Path) -> set[str]:
    if not audio_dir.exists():
        return set()
    return {path.name for path in audio_dir.glob("*.mp3")}


def resolve_audio_filename(
    word: str,
    pos_or_accent: str,
    accent_or_available: str | set[str],
    available: set[str] = None,
) -> str:
    if available is None:
        # Called with 3 arguments: (word, accent, available)
        pos = ""
        accent = pos_or_accent
        avail = accent_or_available
    else:
        # Called with 4 arguments: (word, pos, accent, available)
        pos = pos_or_accent
        accent = accent_or_available
        avail = available

    word_clean = re.sub(r"\s*\(.*?\)\s*", "", word).strip().lower()
    candidates = []
    by_lower = {name.lower(): name for name in avail}
    allow_case_insensitive_audio = word == word.lower()

    def first_available(names: list[str]) -> str:
        for name in names:
            if name in avail:
                return f"[sound:{name}]"
            if allow_case_insensitive_audio:
                actual = by_lower.get(name.lower())
                if actual is not None:
                    return f"[sound:{actual}]"
        return ""

    if pos:
        resolved_pos = resolve_audio_pos(word, pos)
        pos_slug = "_".join(
            part.strip().lower()
            for part in resolved_pos.replace(",", " ").replace("/", " ").split()
            if part.strip()
        )
        if word_clean == "sake" and pos_slug == "noun":
            candidates.append(f"cambridge_{accent}_sake_noun_2.mp3")
        candidates.append(f"cambridge_{accent}_{word_clean}_{pos_slug}.mp3")

    candidates.extend([
        f"cambridge_{accent}_{word}.mp3",
        f"cambridge_{accent}_{word.replace(' ', '_')}.mp3",
        f"cambridge_{accent}_{word.replace('-', '')}.mp3",
    ])

    found = first_available(candidates)
    if found:
        return found

    if allow_case_insensitive_audio:
        raw_word_variants = (
            word_clean,
            word_clean.replace(" ", "_"),
            word_clean.replace("-", ""),
            word.replace(" ", "_").lower(),
        )
    else:
        raw_word_variants = (
            word,
            word.replace(" ", "_"),
            word.replace("-", ""),
        )

    word_variants = []
    for candidate in raw_word_variants:
        if candidate and candidate not in word_variants:
            word_variants.append(candidate)
    if allow_case_insensitive_audio and word_clean.endswith("e") and len(word_clean) > 2:
        ing_stem = word_clean[:-1]
        if ing_stem and ing_stem not in word_variants:
            word_variants.append(ing_stem)

    prefix_rank = {"cambridge": 0, "oxford": 1}
    exact_candidates = [
        f"{prefix}_{accent}_{variant}.mp3"
        for variant in word_variants
        for prefix in ("cambridge", "oxford")
    ]
    found = first_available(exact_candidates)
    if found:
        return found

    if not allow_case_insensitive_audio:
        return ""

    fuzzy_matches: list[tuple[int, int, str]] = []
    for name in avail:
        name_lower = name.lower()
        for variant in word_variants:
            for prefix, rank in prefix_rank.items():
                stem = f"{prefix}_{accent}_{variant}"
                if name_lower.startswith(stem) and name_lower.endswith(".mp3"):
                    fuzzy_matches.append((rank, len(name), name))
    if fuzzy_matches:
        fuzzy_matches.sort()
        return f"[sound:{fuzzy_matches[0][2]}]"
    return ""
