"""Promotion, validation, and build application for the Semantic Registry."""
from __future__ import annotations

import json
import re

from src.deck_builder.build_contracts import BuiltCard
from src.deck_builder.semantic_audit import validate_audit_rows


SEMANTIC_REGISTRY_SCHEMA_VERSION = 1

_ROW_FIELDS = {
    "schema_version", "guid", "word", "cefr", "list", "variant", "pos",
    "audit_sha256", "source_fingerprint", "senses",
}
_SENSE_FIELDS = {
    "semantic_sense_id", "order", "definition_en", "definition_vi", "examples",
    "source_sense_ids", "cambridge_match", "translation_provenance",
}
_IDENTITY_FIELDS = ("word", "cefr", "list", "variant", "pos")
_PROMOTED_CAMBRIDGE_MATCHES = {"exact", "partial", "missing", "conflict"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _invalid_text(
    value: object, *, required: bool = False, allow_pipe: bool = False
) -> bool:
    if not isinstance(value, str) or (required and not value):
        return True
    separators = "\t\r\n" if allow_pipe else "|\t\r\n"
    return any(char in value for char in separators) or bool(_BR_RE.search(value))


def _validate_structure(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_guids: set[str] = set()
    seen_semantic_ids: set[str] = set()
    audit_hashes: set[str] = set()

    for row in rows:
        if not isinstance(row, dict):
            errors.append("invalid_row_type")
            continue
        guid = row.get("guid") or ""
        if set(row) != _ROW_FIELDS:
            errors.append(f"invalid_row_fields:{guid}")
        if not guid or guid in seen_guids:
            errors.append(f"duplicate_or_empty_guid:{guid}")
        seen_guids.add(guid)
        if row.get("schema_version") != SEMANTIC_REGISTRY_SCHEMA_VERSION:
            errors.append(f"invalid_schema_version:{guid}")

        for field in ("guid", *_IDENTITY_FIELDS):
            if _invalid_text(
                row.get(field),
                required=field in {"guid", "word", "cefr", "pos"},
                allow_pipe=field == "guid",
            ):
                errors.append(f"invalid_scalar:{guid}:{field}")

        audit_sha = row.get("audit_sha256")
        if not isinstance(audit_sha, str) or not _SHA256_RE.fullmatch(audit_sha):
            errors.append(f"invalid_audit_sha256:{guid}")
        else:
            audit_hashes.add(audit_sha)
        source_fingerprint = row.get("source_fingerprint")
        if not isinstance(source_fingerprint, str) or not _SHA256_RE.fullmatch(source_fingerprint):
            errors.append(f"invalid_source_fingerprint:{guid}")

        senses = row.get("senses")
        if not isinstance(senses, list):
            errors.append(f"invalid_senses:{guid}")
            continue
        orders = [sense.get("order") for sense in senses if isinstance(sense, dict)]
        if len(orders) != len(senses) or orders != list(range(1, len(senses) + 1)):
            errors.append(f"invalid_sense_order:{guid}")

        local_ids: set[str] = set()
        for sense in senses:
            if not isinstance(sense, dict):
                continue
            semantic_id = sense.get("semantic_sense_id") or ""
            if set(sense) != _SENSE_FIELDS:
                errors.append(f"invalid_sense_fields:{guid}:{semantic_id}")
            if _invalid_text(semantic_id, required=True) or semantic_id in local_ids:
                errors.append(f"duplicate_or_empty_semantic_sense_id:{guid}:{semantic_id}")
            local_ids.add(semantic_id)
            if semantic_id in seen_semantic_ids:
                errors.append(f"duplicate_semantic_sense_id:{semantic_id}")
            seen_semantic_ids.add(semantic_id)

            for field in ("definition_en", "definition_vi", "translation_provenance"):
                if _invalid_text(sense.get(field), required=True):
                    errors.append(f"invalid_scalar:{guid}:{semantic_id}:{field}")
            if sense.get("cambridge_match") not in _PROMOTED_CAMBRIDGE_MATCHES:
                errors.append(f"invalid_cambridge_match:{guid}:{semantic_id}")

            examples = sense.get("examples")
            if not isinstance(examples, list):
                errors.append(f"invalid_examples:{guid}:{semantic_id}")
            elif any(_invalid_text(example, required=True) for example in examples):
                errors.append(f"invalid_example:{guid}:{semantic_id}")

            source_ids = sense.get("source_sense_ids")
            if not isinstance(source_ids, list):
                errors.append(f"invalid_source_sense_ids:{guid}:{semantic_id}")
            elif (
                len(source_ids) != len(set(source_ids))
                or any(_invalid_text(source_id, required=True) for source_id in source_ids)
            ):
                errors.append(f"invalid_source_sense_ids:{guid}:{semantic_id}")

    if len(audit_hashes) > 1:
        errors.append("multiple_audit_sha256")
    return errors


def validate_semantic_registry_rows(
    rows: list[dict], card_registry_rows: list[dict]
) -> list[str]:
    """Validate registry structure and exact active Card Identity coverage."""
    errors = _validate_structure(rows)
    active_by_guid: dict[str, dict] = {}
    for registry_row in card_registry_rows:
        if not isinstance(registry_row, dict):
            errors.append("invalid_card_registry_row_type")
            continue
        if registry_row.get("status") != "active":
            continue
        guid = registry_row.get("guid") or ""
        if not guid or guid in active_by_guid:
            errors.append(f"duplicate_or_empty_active_guid:{guid}")
        active_by_guid[guid] = registry_row

    rows_by_guid = {
        row.get("guid") or "": row
        for row in rows
        if isinstance(row, dict)
    }
    for guid in sorted(set(active_by_guid) - set(rows_by_guid)):
        errors.append(f"missing_active_guid:{guid}")
    for guid in sorted(set(rows_by_guid) - set(active_by_guid)):
        errors.append(f"unknown_registry_guid:{guid}")
    for guid in sorted(set(active_by_guid) & set(rows_by_guid)):
        expected = active_by_guid[guid]
        actual = rows_by_guid[guid]
        for field in _IDENTITY_FIELDS:
            if (actual.get(field) or "") != (expected.get(field) or ""):
                errors.append(f"identity_mismatch:{guid}:{field}")
    return errors


def promote_audit_rows(
    audit_rows: list[dict], card_registry_rows: list[dict], *, audit_sha256: str
) -> list[dict]:
    """Promote a complete approved audit to the deterministic build payload."""
    audit_errors = validate_audit_rows(
        audit_rows, card_registry_rows, require_complete=True
    )
    if audit_errors:
        raise ValueError(
            "Semantic audit is not promotion-ready:\n" + "\n".join(audit_errors)
        )

    promoted: list[dict] = []
    for card in audit_rows:
        senses: list[dict] = []
        for sense in card.get("semantic_senses") or []:
            decision = sense.get("decision")
            if decision == "pass":
                content = sense.get("current") or {}
            elif decision == "repair_proposed" and sense.get("approval") == "approved":
                content = sense.get("proposed") or {}
            else:
                raise ValueError(
                    f"Unsupported promoted decision:{card.get('guid')}:{sense.get('semantic_sense_id')}:{decision}"
                )
            cambridge = sense.get("cambridge") or {}
            senses.append({
                "semantic_sense_id": sense.get("semantic_sense_id") or "",
                "order": sense.get("order"),
                "definition_en": content.get("definition_en") or "",
                "definition_vi": content.get("definition_vi") or "",
                "examples": list(content.get("examples") or []),
                "source_sense_ids": list(sense.get("source_sense_ids") or []),
                "cambridge_match": cambridge.get("match") or "",
                "translation_provenance": cambridge.get("translation_provenance") or "",
            })
        promoted.append({
            "schema_version": SEMANTIC_REGISTRY_SCHEMA_VERSION,
            "guid": card.get("guid") or "",
            "word": card.get("word") or "",
            "cefr": card.get("cefr") or "",
            "list": card.get("list") or "",
            "variant": card.get("variant") or "",
            "pos": card.get("pos") or "",
            "audit_sha256": audit_sha256,
            "source_fingerprint": card.get("source_fingerprint") or "",
            "senses": senses,
        })

    registry_errors = validate_semantic_registry_rows(promoted, card_registry_rows)
    if registry_errors:
        raise ValueError(
            "Promoted Semantic Registry is invalid:\n" + "\n".join(registry_errors)
        )
    return promoted


def serialize_semantic_registry(rows: list[dict]) -> str:
    """Serialize registry rows as compact deterministic UTF-8 JSONL text."""
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def apply_semantic_registry(cards: list[BuiltCard], rows: list[dict]) -> list[BuiltCard]:
    """Replace the bilingual Definition payload and Example fields."""
    structural_errors = _validate_structure(rows)
    if structural_errors:
        raise ValueError("Invalid Semantic Registry:\n" + "\n".join(structural_errors))

    rows_by_guid = {row["guid"]: row for row in rows}
    cards_by_guid: dict[str, BuiltCard] = {}
    for card in cards:
        if not card.guid or card.guid in cards_by_guid:
            raise ValueError(f"Duplicate or empty built-card GUID:{card.guid}")
        cards_by_guid[card.guid] = card
    if set(cards_by_guid) != set(rows_by_guid):
        missing = sorted(set(cards_by_guid) - set(rows_by_guid))
        extra = sorted(set(rows_by_guid) - set(cards_by_guid))
        raise ValueError(f"Semantic Registry/card GUID mismatch:missing={missing}:extra={extra}")

    updated: list[BuiltCard] = []
    for card in cards:
        row = rows_by_guid[card.guid]
        for field in ("word", "cefr", "pos"):
            if getattr(card, field) != row[field]:
                raise ValueError(f"Semantic Registry/card identity mismatch:{card.guid}:{field}")
        definitions = [
            f"{sense['definition_en']} ({sense['definition_vi']})"
            for sense in row["senses"]
        ]
        definitions_vi = [sense["definition_vi"] for sense in row["senses"]]
        examples = ["<br><br>".join(sense["examples"]) for sense in row["senses"]]
        updated.append(card._replace(
            definition="|".join(definitions),
            definition_vi="|".join(definitions_vi),
            example="|".join(examples),
        ))
    return updated
