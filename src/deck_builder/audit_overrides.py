"""Audit override loading and lookup helpers."""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.deck_builder.simplify_senses import _flatten_senses


def _pos_parts(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def _normalize_example(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().casefold()


def find_cross_cefr_override_examples(
    audit_rows: list[dict],
    records_by_word: dict[str, list[dict]],
    *,
    active_non_manual_cards: set[tuple[str, str, str]],
) -> list[dict]:
    """Find curated examples copied from a source sense assigned elsewhere.

    This is deliberately evidence-based: an override segment is rejected only
    when it exactly matches a raw Oxford example, every matching source sense
    is assigned to a CEFR other than the target card, and the card is built
    from source data rather than an explicit manual payload.
    """
    active_by_word_cefr: dict[tuple[str, str], list[set[str]]] = {}
    for word, pos, cefr in active_non_manual_cards:
        key = (word.strip().lower(), cefr.strip().upper())
        active_by_word_cefr.setdefault(key, []).append(_pos_parts(pos))

    issues: list[dict] = []
    for row in audit_rows:
        word = (row.get("word") or "").strip().lower()
        cefr = (row.get("cefr") or "").strip().upper()
        row_pos = _pos_parts(row.get("pos") or "")
        active_pos_sets = active_by_word_cefr.get((word, cefr), [])
        if not any(row_pos & active_pos for active_pos in active_pos_sets):
            continue

        example_matches: dict[str, list[dict]] = {}
        for record in records_by_word.get(word, []):
            flat = _flatten_senses(record)
            for flat_sense in flat:
                if flat_sense.pos.strip().lower() not in row_pos:
                    continue
                definition = record["pos_data"][flat_sense.pd_idx]["definitions"][flat_sense.def_idx]
                assigned_cefr = flat_sense.cefr_resolved or "UNCLASSIFIED"
                for example in definition.get("examples") or []:
                    text = example.get("text") if isinstance(example, dict) else str(example)
                    normalized = _normalize_example(text)
                    if not normalized:
                        continue
                    example_matches.setdefault(normalized, []).append({
                        "assigned_cefr": assigned_cefr,
                        "sense_cefr": definition.get("cefr"),
                        "cefr_source": flat_sense.cefr_source,
                        "sense_number": definition.get("sensenum_local"),
                        "source_example": text,
                    })

        for segment in (row.get("example_after") or "").split("|"):
            normalized = _normalize_example(segment)
            matches = example_matches.get(normalized, [])
            if not matches or any(match["assigned_cefr"] == cefr for match in matches):
                continue
            match = matches[0]
            issues.append({
                "word": word,
                "pos": (row.get("pos") or "").strip().lower(),
                "cefr": cefr,
                "example": segment.strip(),
                **match,
            })

    return issues


def lookup_gloss(
    audit_glosses: dict[tuple[str, str, str], str],
    word: str,
    pos_str: str,
    cefr: str,
    resolved_word: str,
    resolved_pos_parts: list[str],
    new_cefr: str,
) -> str | None:
    word_lower = (word or "").strip().lower()
    word_base = word_lower.split(" (")[0].strip()
    has_disambiguator = word_base != word_lower
    pos_lower = pos_str.strip().lower()

    full_key = (word_lower, pos_lower, cefr)
    if full_key in audit_glosses:
        return audit_glosses[full_key]

    if has_disambiguator:
        sibling_present = any(
            key[0].startswith(word_base + " (") and (key[1], key[2]) == (pos_lower, cefr)
            for key in audit_glosses
        )
        if sibling_present:
            if cefr != new_cefr:
                sibling_cefr_present = any(
                    key[0].startswith(word_base + " (")
                    and (key[1], key[2]) == (pos_lower, new_cefr)
                    for key in audit_glosses
                )
                if sibling_cefr_present:
                    return None
            return None

    base_candidate_keys = [
        (word_base, ", ".join(resolved_pos_parts) if resolved_pos_parts else pos_lower, new_cefr),
        (word_base, pos_lower, new_cefr),
        (word_base, ", ".join(resolved_pos_parts) if resolved_pos_parts else pos_lower, cefr),
        (word_base, pos_lower, cefr),
    ]
    for gloss_key in base_candidate_keys:
        if gloss_key in audit_glosses:
            return audit_glosses[gloss_key]

    orig_pos_parts = [part.strip().lower() for part in pos_str.split(",") if part.strip()]
    res_pos_parts = [part.strip().lower() for part in resolved_pos_parts]

    all_parts = []
    seen_parts = set()
    for part in orig_pos_parts + res_pos_parts:
        if part not in seen_parts:
            all_parts.append(part)
            seen_parts.add(part)

    matched_glosses = []
    seen_glosses = set()
    for part in all_parts:
        pos_lookup_keys = [
            (word_lower, part, cefr),
            (word_base, part, new_cefr),
            (word_lower, part, new_cefr),
            (word_base, part, cefr),
        ]
        for gloss_key in pos_lookup_keys:
            if gloss_key in audit_glosses:
                gloss = audit_glosses[gloss_key]
                if gloss not in seen_glosses:
                    matched_glosses.append(gloss)
                    seen_glosses.add(gloss)
                break

    if matched_glosses:
        return " | ".join(matched_glosses)
    return None


def load_audit_overrides(
    path: Path,
) -> tuple[
    dict[tuple[str, str, str], str],
    dict[tuple[str, str, str], str],
    dict[tuple[str, str, str], str],
]:
    """Load build-stage overrides from the audit ledger."""
    audit_glosses: dict[tuple[str, str, str], str] = {}
    audit_examples: dict[tuple[str, str, str], str] = {}
    audit_collocations: dict[tuple[str, str, str], str] = {}

    if not path.exists():
        return audit_glosses, audit_examples, audit_collocations

    with path.open(encoding="utf-8") as audit_file:
        for line in audit_file:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (
                row.get("word", "").strip().lower(),
                row.get("pos", "").strip().lower(),
                row.get("cefr", "").strip().upper(),
            )
            gloss = (row.get("gloss_after") or "").strip()
            example = (row.get("example_after") or "").strip()
            collocations = (row.get("collocations_after") or "").strip()
            if gloss:
                audit_glosses[key] = gloss
            if example:
                audit_examples[key] = example
            if collocations:
                audit_collocations[key] = collocations

    return audit_glosses, audit_examples, audit_collocations
