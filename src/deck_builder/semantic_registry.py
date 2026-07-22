"""Promotion, validation, and build application for the Semantic Registry."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping

from src.deck_builder.build_contracts import (
    IDIOM_DISPLAY_MODES,
    MAX_IDIOM_EXAMPLES_PER_IDIOM,
    MAX_IDIOMS_PER_CARD,
    BuiltCard,
)
from src.deck_builder.example_policy import main_example_pos_shortfall
from src.deck_builder.sense_pos import derive_sense_pos_cell
from src.deck_builder.semantic_audit import validate_audit_rows
from src.deck_builder.canonical_io import canonical_text_bytes, canonical_text_sha256
from src.deck_builder.text_integrity import has_suspected_lossy_unicode


SEMANTIC_REGISTRY_SCHEMA_VERSION = 4

_ROW_FIELDS = {
    "schema_version", "guid", "word", "cefr", "list", "variant", "pos",
    "audit_sha256", "source_fingerprint", "senses",
    "idiom_audit_sha256", "vietnamese_review_sha256",
    "semantic_policy_sha256", "definition_review_sha256",
    "sense_merge_review_sha256", "idioms",
}
_SENSE_FIELDS = {
    "semantic_sense_id", "order", "definition_en", "definition_vi", "examples",
    "source_sense_ids", "cambridge_match", "translation_provenance",
}
_IDIOM_FIELDS = {
    "idiom_id", "order", "source_fingerprint", "phrase_en", "display_mode",
    "explanation_en", "explanation_vi", "examples", "translation_provenance",
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
    idiom_audit_hashes: set[str] = set()
    vietnamese_review_hashes: set[str] = set()
    semantic_policy_hashes: set[str] = set()
    definition_review_hashes: set[str] = set()
    sense_merge_review_hashes: set[str] = set()

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

        idiom_audit_sha = row.get("idiom_audit_sha256")
        if (
            not isinstance(idiom_audit_sha, str)
            or not _SHA256_RE.fullmatch(idiom_audit_sha)
        ):
            errors.append(f"invalid_idiom_audit_sha256:{guid}")
        else:
            idiom_audit_hashes.add(idiom_audit_sha)

        vietnamese_review_sha = row.get("vietnamese_review_sha256")
        if (
            not isinstance(vietnamese_review_sha, str)
            or not _SHA256_RE.fullmatch(vietnamese_review_sha)
        ):
            errors.append(f"invalid_vietnamese_review_sha256:{guid}")
        else:
            vietnamese_review_hashes.add(vietnamese_review_sha)

        for field, hashes in (
            ("semantic_policy_sha256", semantic_policy_hashes),
            ("definition_review_sha256", definition_review_hashes),
            ("sense_merge_review_sha256", sense_merge_review_hashes),
        ):
            value = row.get(field)
            if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
                errors.append(f"invalid_{field}:{guid}")
            else:
                hashes.add(value)

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
            if has_suspected_lossy_unicode(sense.get("definition_vi")):
                errors.append(
                    f"suspected_lossy_unicode:{guid}:{semantic_id}:definition_vi"
                )
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

        if senses:
            shortfall = main_example_pos_shortfall(
                row.get("pos"),
                (
                    example
                    for sense in senses
                    if isinstance(sense, dict)
                    for example in (sense.get("examples") or [])
                ),
            )
            if shortfall is not None:
                actual, required = shortfall
                errors.append(f"main_example_pos_shortfall:{guid}:{actual}<{required}")

        idioms = row.get("idioms")
        if not isinstance(idioms, list):
            errors.append(f"invalid_idioms:{guid}")
            continue
        if len(idioms) > MAX_IDIOMS_PER_CARD:
            errors.append(f"idiom_limit_exceeded:{guid}")
        idiom_orders = [
            idiom.get("order") for idiom in idioms if isinstance(idiom, dict)
        ]
        if (
            len(idiom_orders) != len(idioms)
            or idiom_orders != list(range(1, len(idioms) + 1))
        ):
            errors.append(f"invalid_idiom_order:{guid}")

        local_idiom_ids: set[str] = set()
        for idiom in idioms:
            if not isinstance(idiom, dict):
                continue
            idiom_id = idiom.get("idiom_id") or ""
            if set(idiom) != _IDIOM_FIELDS:
                errors.append(f"invalid_idiom_fields:{guid}:{idiom_id}")
            if (
                _invalid_text(idiom_id, required=True)
                or "::" in idiom_id
                or "$$" in idiom_id
                or idiom_id in local_idiom_ids
            ):
                errors.append(f"duplicate_or_invalid_idiom_id:{guid}:{idiom_id}")
            local_idiom_ids.add(idiom_id)

            idiom_fingerprint = idiom.get("source_fingerprint")
            if (
                not isinstance(idiom_fingerprint, str)
                or not _SHA256_RE.fullmatch(idiom_fingerprint)
            ):
                errors.append(f"invalid_idiom_source_fingerprint:{guid}:{idiom_id}")
            if idiom.get("display_mode") not in IDIOM_DISPLAY_MODES:
                errors.append(f"invalid_idiom_display_mode:{guid}:{idiom_id}")
            for field in (
                "phrase_en", "explanation_en", "explanation_vi",
                "translation_provenance",
            ):
                value = idiom.get(field)
                if (
                    _invalid_text(
                        value,
                        required=True,
                        allow_pipe=field == "phrase_en",
                    )
                    or (isinstance(value, str) and ("::" in value or "$$" in value))
                ):
                    errors.append(f"invalid_idiom_scalar:{guid}:{idiom_id}:{field}")
            if has_suspected_lossy_unicode(idiom.get("explanation_vi")):
                errors.append(
                    f"suspected_lossy_unicode:{guid}:{idiom_id}:explanation_vi"
                )

            idiom_examples = idiom.get("examples")
            if not isinstance(idiom_examples, list):
                errors.append(f"invalid_idiom_examples:{guid}:{idiom_id}")
            elif (
                len(idiom_examples) > MAX_IDIOM_EXAMPLES_PER_IDIOM
                or any(_invalid_text(example, required=True) for example in idiom_examples)
            ):
                errors.append(f"invalid_idiom_examples:{guid}:{idiom_id}")

    if len(audit_hashes) > 1:
        errors.append("multiple_audit_sha256")
    if len(idiom_audit_hashes) > 1:
        errors.append("multiple_idiom_audit_sha256")
    if len(vietnamese_review_hashes) > 1:
        errors.append("multiple_vietnamese_review_sha256")
    if len(semantic_policy_hashes) > 1:
        errors.append("multiple_semantic_policy_sha256")
    if len(definition_review_hashes) > 1:
        errors.append("multiple_definition_review_sha256")
    if len(sense_merge_review_hashes) > 1:
        errors.append("multiple_sense_merge_review_sha256")
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


def _render_promoted_audit_rows(
    audit_rows: list[dict],
    card_registry_rows: list[dict],
    *,
    audit_sha256: str,
    idiom_audit_sha256: str | None = None,
    vietnamese_review_sha256: str | None = None,
    semantic_policy_sha256: str | None = None,
    definition_review_sha256: str | None = None,
    sense_merge_review_sha256: str | None = None,
    idiom_audit_rows: list[dict] | None = None,
    idioms_by_guid: Mapping[str, list[dict]] | None = None,
) -> list[dict]:
    """Promote a complete approved audit to the deterministic build payload."""
    audit_errors = validate_audit_rows(
        audit_rows, card_registry_rows, require_complete=True
    )
    if audit_errors:
        raise ValueError(
            "Semantic audit is not promotion-ready:\n" + "\n".join(audit_errors)
        )
    if not isinstance(idiom_audit_sha256, str) or not _SHA256_RE.fullmatch(
        idiom_audit_sha256
    ):
        raise ValueError("Invalid idiom audit SHA-256")
    if (
        not isinstance(vietnamese_review_sha256, str)
        or not _SHA256_RE.fullmatch(vietnamese_review_sha256)
    ):
        raise ValueError("Invalid Vietnamese review SHA-256")
    for label, value in (
        ("semantic policy", semantic_policy_sha256),
        ("Definition review", definition_review_sha256),
        ("Sense Merge review", sense_merge_review_sha256),
    ):
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise ValueError(f"Invalid {label} SHA-256")
    if idiom_audit_rows is not None and idioms_by_guid is not None:
        raise ValueError("Pass idiom_audit_rows or idioms_by_guid, not both")
    if idiom_audit_rows is not None:
        # Keep the registry independent from the review/XLSX implementation;
        # the import is needed only by the promotion command.
        from src.deck_builder.idiom_audit import promoted_idioms_by_guid

        idioms_by_guid = promoted_idioms_by_guid(idiom_audit_rows)
    if idioms_by_guid is None:
        raise ValueError("Complete promoted idiom payload is required")
    if not isinstance(idioms_by_guid, Mapping):
        raise ValueError("Promoted idiom payload must be keyed by card GUID")

    promoted_guids = {
        str(card.get("guid") or "") for card in audit_rows if isinstance(card, dict)
    }
    unknown_idiom_guids = sorted(set(idioms_by_guid) - promoted_guids)
    if unknown_idiom_guids:
        raise ValueError(
            f"Promoted idioms contain unknown card GUIDs:{unknown_idiom_guids}"
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
            "idiom_audit_sha256": idiom_audit_sha256,
            "vietnamese_review_sha256": vietnamese_review_sha256,
            "semantic_policy_sha256": semantic_policy_sha256,
            "definition_review_sha256": definition_review_sha256,
            "sense_merge_review_sha256": sense_merge_review_sha256,
            "idioms": [
                {
                    **dict(idiom),
                    "examples": list(idiom.get("examples") or []),
                }
                for idiom in idioms_by_guid.get(card.get("guid") or "", [])
            ],
        })

    registry_errors = validate_semantic_registry_rows(promoted, card_registry_rows)
    if registry_errors:
        raise ValueError(
            "Promoted Semantic Registry is invalid:\n" + "\n".join(registry_errors)
        )
    return promoted


def _document_rows(payload: bytes, expected_rows: list[dict], *, label: str) -> None:
    try:
        parsed = [
            json.loads(line)
            for line in canonical_text_bytes(payload).decode("utf-8").splitlines()
            if line.strip()
        ]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid {label} JSONL payload") from exc
    if parsed != expected_rows:
        raise ValueError(f"{label} bytes do not match supplied rows")


def _definition_gate_notes(registry_rows: list[dict]) -> list[dict]:
    """Project promoted senses into the fields inspected by Definition Audit."""

    return [
        {
            "guid": row["guid"],
            "word": row["word"],
            "cefr": row["cefr"],
            "pos": row["pos"],
            "definition": "|".join(
                f"{sense['definition_en']} ({sense['definition_vi']})"
                for sense in row.get("senses") or []
            ),
            "example": "|".join(
                "<br><br>".join(sense.get("examples") or [])
                for sense in row.get("senses") or []
            ),
        }
        for row in registry_rows
    ]


def build_promotion_gate_candidates(
    audit_rows: list[dict],
    card_registry_rows: list[dict],
    idiom_audit_rows: list[dict],
    deck_audit_rows: list[dict],
    non_oxford_non_c2_override_rows: list[dict],
    *,
    audit_sha256: str,
    idiom_audit_sha256: str,
    vietnamese_review_sha256: str,
    semantic_policy_sha256: str,
    deck_audit_sha256: str,
    non_oxford_non_c2_override_sha256: str,
) -> tuple[dict, list[dict], dict, list[dict]]:
    """Derive both promotion queues from the would-be promoted payload."""

    from src.deck_builder.canonical_io import canonical_jsonl_bytes
    from src.deck_builder.definition_audit import build_definition_audit
    from src.deck_builder.sense_merge_audit import build_sense_merge_audit

    placeholder_sha256 = "0" * 64
    provisional = _render_promoted_audit_rows(
        audit_rows,
        card_registry_rows,
        audit_sha256=audit_sha256,
        idiom_audit_sha256=idiom_audit_sha256,
        vietnamese_review_sha256=vietnamese_review_sha256,
        semantic_policy_sha256=semantic_policy_sha256,
        definition_review_sha256=placeholder_sha256,
        sense_merge_review_sha256=placeholder_sha256,
        idiom_audit_rows=idiom_audit_rows,
    )
    provisional_bytes = canonical_jsonl_bytes(provisional)
    note_rows = _definition_gate_notes(provisional)
    note_bytes = canonical_jsonl_bytes(note_rows)
    card_registry_bytes = canonical_jsonl_bytes(card_registry_rows)
    definition_summary, definition_candidates = build_definition_audit(
        provisional,
        note_rows,
        audit_rows,
        card_registry_rows,
        input_hashes={
            "bilingual_semantic_audit": audit_sha256,
            "build_notes": canonical_text_sha256(note_bytes),
            "card_registry": canonical_text_sha256(card_registry_bytes),
            "semantic_registry": canonical_text_sha256(provisional_bytes),
        },
    )
    sense_merge_summary, sense_merge_candidates = build_sense_merge_audit(
        provisional,
        audit_rows,
        deck_audit_rows,
        non_oxford_non_c2_override_rows,
        input_hashes={
            "semantic_registry": canonical_text_sha256(provisional_bytes),
            "bilingual_semantic_audit": audit_sha256,
            "card_registry": canonical_text_sha256(card_registry_bytes),
            "deck_audit": deck_audit_sha256,
            "non_oxford_non_c2_overrides": (
                non_oxford_non_c2_override_sha256
            ),
        },
    )
    return (
        definition_summary,
        definition_candidates,
        sense_merge_summary,
        sense_merge_candidates,
    )


def promote_reviewed_semantics(
    audit_rows: list[dict],
    card_registry_rows: list[dict],
    idiom_audit_rows: list[dict],
    vietnamese_review_summary: dict,
    vietnamese_review_rows: list[dict],
    *,
    policy_rows: list[dict],
    definition_review_summary: dict,
    definition_review_rows: list[dict],
    sense_merge_review_summary: dict,
    sense_merge_review_rows: list[dict],
    deck_audit_rows: list[dict],
    non_oxford_non_c2_override_rows: list[dict],
    audit_bytes: bytes,
    idiom_audit_bytes: bytes,
    vietnamese_review_bytes: bytes,
    policy_bytes: bytes,
    definition_review_bytes: bytes,
    sense_merge_review_bytes: bytes,
    deck_audit_bytes: bytes,
    non_oxford_non_c2_override_bytes: bytes,
    require_user_exact_vi_locks: bool = True,
) -> list[dict]:
    """Validate every semantic authority, derive provenance, and promote."""
    from src.deck_builder.definition_audit import (
        validate_definition_review_for_promotion,
    )
    from src.deck_builder.idiom_audit import validate_audit_rows as validate_idioms
    from src.deck_builder.semantic_policy import (
        validate_audit_policy,
        validate_required_user_exact_vi_locks,
        validate_registry_policy,
        validate_vietnamese_user_lock_evidence,
    )
    from src.deck_builder.sense_merge_audit import (
        validate_sense_merge_review_for_promotion,
    )
    from src.deck_builder.vietnamese_audit import (
        validate_vietnamese_review_for_promotion,
    )

    _document_rows(audit_bytes, audit_rows, label="bilingual semantic audit")
    _document_rows(idiom_audit_bytes, idiom_audit_rows, label="idiom audit")
    _document_rows(
        vietnamese_review_bytes,
        [vietnamese_review_summary, *vietnamese_review_rows],
        label="Vietnamese review",
    )
    _document_rows(policy_bytes, policy_rows, label="semantic policy")
    _document_rows(
        definition_review_bytes,
        [definition_review_summary, *definition_review_rows],
        label="Definition review",
    )
    _document_rows(
        sense_merge_review_bytes,
        [sense_merge_review_summary, *sense_merge_review_rows],
        label="Sense Merge review",
    )
    _document_rows(deck_audit_bytes, deck_audit_rows, label="deck audit")
    _document_rows(
        non_oxford_non_c2_override_bytes,
        non_oxford_non_c2_override_rows,
        label="non-Oxford/non-C2 overrides",
    )

    audit_errors = validate_audit_rows(
        audit_rows, card_registry_rows, require_complete=True
    )
    if audit_errors:
        raise ValueError(
            "Semantic audit is not promotion-ready:\n" + "\n".join(audit_errors)
        )
    idiom_errors = validate_idioms(
        idiom_audit_rows, card_registry_rows, require_complete=True
    )
    if idiom_errors:
        raise ValueError(
            "Idiom audit is not promotion-ready:\n" + "\n".join(idiom_errors)
        )
    vietnamese_errors = validate_vietnamese_review_for_promotion(
        audit_rows,
        vietnamese_review_summary,
        vietnamese_review_rows,
    )
    vietnamese_errors.extend(
        validate_vietnamese_user_lock_evidence(
            vietnamese_review_rows,
            policy_rows,
        )
    )
    if vietnamese_errors:
        raise ValueError(
            "Vietnamese review is not promotion-ready:\n"
            + "\n".join(vietnamese_errors)
        )

    policy_errors = validate_audit_policy(audit_rows, policy_rows)
    if require_user_exact_vi_locks:
        policy_errors.extend(validate_required_user_exact_vi_locks(policy_rows))
    if policy_errors:
        raise ValueError(
            "Semantic policy is not promotion-ready:\n"
            + "\n".join(policy_errors)
        )

    audit_sha256 = canonical_text_sha256(audit_bytes)
    idiom_audit_sha256 = canonical_text_sha256(idiom_audit_bytes)
    vietnamese_review_sha256 = canonical_text_sha256(vietnamese_review_bytes)
    semantic_policy_sha256 = canonical_text_sha256(policy_bytes)
    # Build queues from the payload that would be promoted, not from the
    # previous downstream registry. This prevents a provenance cycle.
    (
        definition_summary,
        definition_candidates,
        sense_merge_summary,
        sense_merge_candidates,
    ) = build_promotion_gate_candidates(
        audit_rows,
        card_registry_rows,
        idiom_audit_rows,
        deck_audit_rows,
        non_oxford_non_c2_override_rows,
        audit_sha256=audit_sha256,
        idiom_audit_sha256=idiom_audit_sha256,
        vietnamese_review_sha256=vietnamese_review_sha256,
        semantic_policy_sha256=semantic_policy_sha256,
        deck_audit_sha256=canonical_text_sha256(deck_audit_bytes),
        non_oxford_non_c2_override_sha256=canonical_text_sha256(
            non_oxford_non_c2_override_bytes
        ),
    )
    definition_errors = validate_definition_review_for_promotion(
        definition_summary,
        definition_candidates,
        definition_review_summary,
        definition_review_rows,
    )
    if definition_errors:
        raise ValueError(
            "Definition review is not promotion-ready:\n"
            + "\n".join(definition_errors)
        )

    sense_merge_errors = validate_sense_merge_review_for_promotion(
        sense_merge_summary,
        sense_merge_candidates,
        sense_merge_review_summary,
        sense_merge_review_rows,
    )
    if sense_merge_errors:
        raise ValueError(
            "Sense Merge review is not promotion-ready:\n"
            + "\n".join(sense_merge_errors)
        )

    promoted = _render_promoted_audit_rows(
        audit_rows,
        card_registry_rows,
        audit_sha256=audit_sha256,
        idiom_audit_sha256=idiom_audit_sha256,
        vietnamese_review_sha256=vietnamese_review_sha256,
        semantic_policy_sha256=semantic_policy_sha256,
        definition_review_sha256=canonical_text_sha256(definition_review_bytes),
        sense_merge_review_sha256=canonical_text_sha256(sense_merge_review_bytes),
        idiom_audit_rows=idiom_audit_rows,
    )
    promoted_policy_errors = validate_registry_policy(promoted, policy_rows)
    if promoted_policy_errors:
        raise ValueError(
            "Promoted registry violates semantic policy:\n"
            + "\n".join(promoted_policy_errors)
        )
    return promoted


def serialize_semantic_registry(rows: list[dict]) -> str:
    """Serialize registry rows as compact deterministic UTF-8 JSONL text."""
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def render_registry_idiom_fields(idioms: list[dict]) -> tuple[str, str]:
    """Render v2 idiom payload into the two append-only EAVM fields."""
    legacy_entries: list[str] = []
    vietnamese_entries: list[str] = []
    for idiom in idioms:
        parts = [idiom["phrase_en"], idiom["explanation_en"]]
        examples = list(idiom.get("examples") or [])
        if examples:
            parts.append("|".join(examples))
        legacy_entries.append(" :: ".join(parts))
        vietnamese_entries.append(
            f"{idiom['display_mode']} :: {idiom['explanation_vi']}"
        )
    return "$$".join(legacy_entries), "$$".join(vietnamese_entries)


def apply_semantic_registry(
    cards: list[BuiltCard],
    rows: list[dict],
    source_pos_by_id: Mapping[str, tuple[str, ...]] | None = None,
) -> list[BuiltCard]:
    """Replace final semantic and idiom payloads after exact source checks."""
    from src.deck_builder.idiom_audit import (
        idiom_source_fingerprint,
        parse_serialized_idioms,
    )

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
    source_pos_index = source_pos_by_id or {}
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
        sense_pos = [
            derive_sense_pos_cell(
                card.pos,
                sense.get("source_sense_ids") or [],
                source_pos_index,
            )
            for sense in row["senses"]
        ]
        selected_idioms = parse_serialized_idioms(card.idioms)
        promoted_idioms = row["idioms"]
        if len(selected_idioms) != len(promoted_idioms):
            raise ValueError(
                f"Semantic Registry/card idiom count mismatch:{card.guid}:"
                f"{len(selected_idioms)}!={len(promoted_idioms)}"
            )
        for order, (selected, promoted_idiom) in enumerate(
            zip(selected_idioms, promoted_idioms), 1
        ):
            if selected["phrase_en"] != promoted_idiom["phrase_en"]:
                raise ValueError(
                    f"Semantic Registry/card idiom phrase mismatch:{card.guid}:{order}"
                )
            if selected["examples"] != promoted_idiom["examples"]:
                raise ValueError(
                    f"Semantic Registry/card idiom examples mismatch:{card.guid}:{order}"
                )
            selected_fingerprint = idiom_source_fingerprint(
                selected["phrase_en"],
                selected["source_explanation_en"],
                selected["examples"],
            )
            if selected_fingerprint != promoted_idiom["source_fingerprint"]:
                raise ValueError(
                    f"Semantic Registry/card idiom source fingerprint mismatch:"
                    f"{card.guid}:{order}"
                )
            if (
                promoted_idiom["display_mode"] == "vi_equivalent"
                and promoted_idiom["explanation_en"]
                != selected["source_explanation_en"]
            ):
                raise ValueError(
                    f"Semantic Registry/card idiom fallback mismatch:{card.guid}:{order}"
                )
        idioms, idiom_meaning_vi = render_registry_idiom_fields(promoted_idioms)
        updated.append(card._replace(
            definition="|".join(definitions),
            definition_vi="|".join(definitions_vi),
            example="|".join(examples),
            sense_pos="|".join(sense_pos),
            idioms=idioms,
            idiom_meaning_vi=idiom_meaning_vi,
        ))
    return updated
