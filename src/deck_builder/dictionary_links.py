"""Resolve trusted dictionary links for built cards."""
from __future__ import annotations

from urllib.parse import quote, urlsplit

from src.deck_builder.simplify_senses import _flatten_senses
from src.deck_builder.source_sense_identity import source_sense_id


CAMBRIDGE_BASE = "https://dictionary.cambridge.org/dictionary/english/"
OXFORD_HOST = "www.oxfordlearnersdictionaries.com"
OXFORD_PATH_PREFIX = "/definition/english/"


def _has_unsafe_url_characters(value: str) -> bool:
    return any(character.isspace() or character in "\"'<>" for character in value)


def cambridge_url(source_lemma: str) -> str:
    slug = quote("-".join(source_lemma.strip().casefold().split()), safe="-")
    return CAMBRIDGE_BASE + slug if slug else ""


def is_official_cambridge_url(value: str) -> bool:
    if not value or _has_unsafe_url_characters(value):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname == "dictionary.cambridge.org"
        and parsed.path.startswith("/dictionary/english/")
        and parsed.path != "/dictionary/english/"
        and not parsed.query
        and not parsed.fragment
    )


def is_official_oxford_url(value: str) -> bool:
    if not value or _has_unsafe_url_characters(value):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname == OXFORD_HOST
        and parsed.path.startswith(OXFORD_PATH_PREFIX)
        and parsed.path != OXFORD_PATH_PREFIX
        and not parsed.query
        and not parsed.fragment
    )


class OxfordLinkIndex:
    def __init__(self, records_by_word: dict[str, list[dict]]) -> None:
        self._by_source_id: dict[str, tuple[str, str]] = {}
        self._by_word_pos: dict[tuple[str, str], set[str]] = {}
        for word, records in records_by_word.items():
            for record in records:
                for pd in record.get("pos_data") or []:
                    url = pd.get("source_url") or ""
                    pos = (pd.get("pos") or "").strip()
                    if pos and is_official_oxford_url(url):
                        self._by_word_pos.setdefault((word, pos), set()).add(url)
                for flat in _flatten_senses(record):
                    pd = record["pos_data"][flat.pd_idx]
                    url = pd.get("source_url") or ""
                    if is_official_oxford_url(url):
                        self._by_source_id[source_sense_id(record, flat)] = (flat.pos, url)

    def aligned_urls(
        self,
        source_lemma: str,
        pos_parts: list[str],
        semantic_source_ids: set[str],
    ) -> str:
        cells: list[str] = []
        for pos in pos_parts:
            evidence_urls = {
                url
                for source_id in semantic_source_ids
                for evidence_pos, url in [self._by_source_id.get(source_id, ("", ""))]
                if evidence_pos == pos and url
            }
            if len(evidence_urls) == 1:
                cells.append(next(iter(evidence_urls)))
                continue
            if evidence_urls:
                cells.append("")
                continue
            fallback = self._by_word_pos.get((source_lemma, pos), set())
            cells.append(next(iter(fallback)) if len(fallback) == 1 else "")
        return "|".join(cells)
