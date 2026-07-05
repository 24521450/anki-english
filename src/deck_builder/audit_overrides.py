"""Audit override loading and lookup helpers."""
from __future__ import annotations

import json
from pathlib import Path


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
