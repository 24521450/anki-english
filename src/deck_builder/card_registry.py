"""Registry bootstrap and validation helpers for deck identities."""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from src.deck_builder.build_issues import BuildIssue, BuildValidationError
from src.deck_builder.card_identity import (
    CardIdentity,
    is_reviewed_identity_variant_allowed,
    is_reviewed_semantic_identity_variant,
    normalize_cefr,
    normalize_list_name,
    normalize_variant,
    normalize_word,
    primary_list_from_tags,
    reviewed_identity_variant,
)


REGISTRY_FIELDS: tuple[str, ...] = (
    "word",
    "cefr",
    "list",
    "variant",
    "pos",
    "guid",
    "status",
    "deck_override",
)

ALLOWED_STATUSES = {"active", "retired"}

# genanki.util.BASE91_TABLE.  Card Registry GUIDs are stored as the decoded
# Anki value, never as their CSV/TSV representation.
ANKI_GUID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "!#$%&()*+,-./:;<=>?@[]^_`{|}~"
)


def normalize_bootstrap_guid(value: object) -> object:
    """Normalize the one historical TXT-quoting defect at import time.

    Anki's tab export may wrap a GUID containing ``#`` in ASCII double quotes.
    The old bootstrap parser copied those CSV quotes into the GUID.  Only that
    exact outer double-quote pair is unwrapped; apostrophes are not wrappers
    and are not valid Anki base91 characters.
    """
    if not isinstance(value, str):
        return value
    guid = value.strip()
    if len(guid) >= 2 and guid.startswith('"') and guid.endswith('"'):
        guid = guid[1:-1]
    return guid


def guid_validation_error(value: object) -> tuple[str, str] | None:
    """Return a stable validation code/message for a stored GUID."""
    if not isinstance(value, str):
        return "invalid_guid", "GUID must be a string"
    if not value:
        return "invalid_guid", "GUID must not be empty"
    if value != value.strip():
        return "noncanonical_guid", "GUID must not contain outer whitespace"
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return "noncanonical_guid", "GUID must store the decoded value without TXT quotes"
    invalid_chars = sorted(set(value) - ANKI_GUID_CHARS)
    if invalid_chars:
        return "invalid_guid", f"GUID contains invalid Anki base91 characters {invalid_chars!r}"
    return None


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


def _canonical_registry_row(note: dict) -> dict:
    word = normalize_word(note.get("word"))
    cefr = normalize_cefr(note.get("cefr"))
    pos = (note.get("pos") or "").strip()
    guid = normalize_bootstrap_guid(note.get("guid"))
    list_name = primary_list_from_tags(note.get("tags"), canonical=True)
    variant = reviewed_identity_variant(word, cefr, list_name, pos)
    deck_override = None if list_name != "NO_LIST" else (note.get("deck") or "").strip() or None
    return OrderedDict([
        ("word", word),
        ("cefr", cefr),
        ("list", list_name),
        ("variant", variant),
        ("pos", pos),
        ("guid", guid),
        ("status", "active"),
        ("deck_override", deck_override),
    ])


def bootstrap_registry_rows(notes_jsonl_path: Path) -> list[dict]:
    rows = load_jsonl(notes_jsonl_path)
    return [_canonical_registry_row(row) for row in rows]


def serialize_registry_rows(rows: Iterable[dict]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )


def _row_identity(row: dict) -> CardIdentity:
    return CardIdentity(
        word=normalize_word(row.get("word")),
        cefr=normalize_cefr(row.get("cefr")),
        list=normalize_list_name(row.get("list"), canonical=True),
        variant=normalize_variant(row.get("variant")),
    )


def validate_registry_rows(rows: list[dict]) -> list[BuildIssue]:
    issues: list[BuildIssue] = []
    seen_keys: dict[tuple[str, str, str, str], int] = {}
    seen_guids: dict[str, int] = {}

    for idx, row in enumerate(rows, 1):
        identity = _row_identity(row)

        for field in REGISTRY_FIELDS:
            if field not in row:
                issues.append(BuildIssue(
                    severity="error",
                    code="missing_field",
                    message=f"row {idx} missing required field {field!r}",
                    identity=identity,
                ))

        if identity.word != row.get("word", ""):
            issues.append(BuildIssue(
                severity="error",
                code="noncanonical_word",
                message=f"row {idx} word should be stored stripped and raw",
                identity=identity,
            ))

        if identity.cefr != row.get("cefr", ""):
            issues.append(BuildIssue(
                severity="error",
                code="noncanonical_cefr",
                message=f"row {idx} cefr must be uppercased",
                identity=identity,
            ))

        if identity.list != row.get("list", ""):
            issues.append(BuildIssue(
                severity="error",
                code="noncanonical_list",
                message=f"row {idx} list must use canonical registry list names",
                identity=identity,
            ))

        if identity.variant != row.get("variant", ""):
            issues.append(BuildIssue(
                severity="error",
                code="noncanonical_variant",
                message=f"row {idx} variant must be stripped",
                identity=identity,
            ))

        if row.get("status") not in ALLOWED_STATUSES:
            issues.append(BuildIssue(
                severity="error",
                code="invalid_status",
                message=f"row {idx} has invalid status {row.get('status')!r}",
                identity=identity,
            ))

        deck_override = row.get("deck_override")
        if identity.list == "NO_LIST":
            if not deck_override:
                issues.append(BuildIssue(
                    severity="error",
                    code="missing_deck_override",
                    message=f"row {idx} with NO_LIST requires deck_override",
                    identity=identity,
                ))
        elif deck_override not in (None, "") and not is_reviewed_semantic_identity_variant(
            row.get("word"),
            row.get("cefr"),
            row.get("list"),
            row.get("pos"),
            row.get("variant"),
        ):
            issues.append(BuildIssue(
                severity="error",
                code="unexpected_deck_override",
                message=f"row {idx} with list {identity.list!r} must not set deck_override",
                identity=identity,
            ))

        if not is_reviewed_identity_variant_allowed(
            row.get("word"),
            row.get("cefr"),
            row.get("list"),
            row.get("pos"),
            row.get("variant"),
        ):
            issues.append(BuildIssue(
                severity="error",
                code="unauthorized_variant",
                message=(
                    f"row {idx} variant {identity.variant!r} is not allowed for "
                    f"{identity.word!r}/{identity.cefr!r}/{identity.list!r}"
                ),
                identity=identity,
            ))

        key = identity.as_key()
        if key in seen_keys:
            issues.append(BuildIssue(
                severity="error",
                code="duplicate_key",
                message=f"duplicate registry key at rows {seen_keys[key]} and {idx}",
                identity=identity,
            ))
        else:
            seen_keys[key] = idx

        raw_guid = row.get("guid")
        guid_error = guid_validation_error(raw_guid)
        if guid_error is not None:
            code, message = guid_error
            issues.append(BuildIssue(
                severity="error",
                code=code,
                message=f"row {idx}: {message}",
                identity=identity,
            ))
            continue

        assert isinstance(raw_guid, str)
        guid = raw_guid
        if guid in seen_guids:
            issues.append(BuildIssue(
                severity="error",
                code="duplicate_guid",
                message=f"duplicate GUID at rows {seen_guids[guid]} and {idx}",
                identity=identity,
            ))
        elif guid:
            seen_guids[guid] = idx

    return issues


def validate_registry_or_raise(rows: list[dict]) -> None:
    issues = validate_registry_rows(rows)
    if issues:
        raise BuildValidationError(issues)


def bootstrap_registry_text(notes_jsonl_path: Path) -> str:
    rows = bootstrap_registry_rows(notes_jsonl_path)
    validate_registry_or_raise(rows)
    return serialize_registry_rows(rows)
