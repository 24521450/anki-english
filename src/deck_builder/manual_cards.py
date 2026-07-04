"""Canonical manual card payload helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.deck_builder.build_issues import BuildIssue, BuildValidationError
from src.deck_builder.card_identity import (
    CardIdentity,
    normalize_cefr,
    normalize_list_name,
    normalize_variant,
    normalize_word,
)

MANUAL_CARD_FIELDS: tuple[str, ...] = (
    "word",
    "cefr",
    "list",
    "variant",
    "definition",
    "example",
    "collocations",
    "wordfamily",
    "ipa",
    "uk_audio",
    "us_audio",
    "source1",
    "source2",
    "idioms",
    "provenance",
)

REQUIRED_CONTENT_FIELDS: tuple[str, ...] = (
    "definition",
    "example",
    "collocations",
    "wordfamily",
    "ipa",
    "uk_audio",
    "us_audio",
    "source1",
    "source2",
    "idioms",
)

ALLOWED_PROVENANCE_SOURCES: tuple[str, ...] = (
    "manual_card_fills",
    "build_contract_source_gap",
)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def serialize_manual_cards_rows(rows: Iterable[dict]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )


def validate_manual_cards_rows(rows: list[dict]) -> list[BuildIssue]:
    issues: list[BuildIssue] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for idx, row in enumerate(rows, 1):
        identity = CardIdentity(
            word=normalize_word(row.get("word")),
            cefr=normalize_cefr(row.get("cefr")),
            list=normalize_list_name(row.get("list"), canonical=True),
            variant=normalize_variant(row.get("variant")),
        )
        for field in MANUAL_CARD_FIELDS:
            if field not in row:
                issues.append(BuildIssue(
                    severity="error",
                    code="missing_field",
                    message=f"row {idx} missing required field {field!r}",
                    identity=identity,
                ))

        for field in REQUIRED_CONTENT_FIELDS:
            if not isinstance(row.get(field), str):
                issues.append(BuildIssue(
                    severity="error",
                    code="invalid_content",
                    message=f"row {idx} field {field!r} must be a string",
                    identity=identity,
                ))

        provenance = row.get("provenance")
        if not isinstance(provenance, dict):
            issues.append(BuildIssue(
                severity="error",
                code="missing_provenance",
                message=f"row {idx} provenance must be an object",
                identity=identity,
            ))
        else:
            if provenance.get("source") not in ALLOWED_PROVENANCE_SOURCES:
                issues.append(BuildIssue(
                    severity="error",
                    code="invalid_provenance_source",
                    message=(
                        f"row {idx} provenance.source must be one of "
                        f"{ALLOWED_PROVENANCE_SOURCES!r}"
                    ),
                    identity=identity,
                ))
            if not isinstance(provenance.get("ledger_pos"), str) or not provenance.get("ledger_pos").strip():
                issues.append(BuildIssue(
                    severity="error",
                    code="invalid_ledger_pos",
                    message=f"row {idx} provenance.ledger_pos must be a non-empty string",
                    identity=identity,
                ))

        key = identity.as_key()
        if key in seen_keys:
            issues.append(BuildIssue(
                severity="error",
                code="duplicate_manual_key",
                message=f"duplicate manual card identity {key}",
                identity=identity,
            ))
        else:
            seen_keys.add(key)

    return issues


def validate_manual_cards_or_raise(rows: list[dict]) -> None:
    issues = validate_manual_cards_rows(rows)
    if issues:
        raise BuildValidationError(issues)
