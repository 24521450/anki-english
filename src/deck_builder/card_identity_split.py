"""Fingerprint-bound transaction for reviewed semantic Card Identity splits."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from src.deck_builder.canonical_io import canonical_json_bytes, canonical_jsonl_bytes
from src.deck_builder.card_identity import is_reviewed_identity_variant_allowed
from src.deck_builder.card_registry import (
    guid_validation_error,
    validate_registry_or_raise,
)
from src.deck_builder.production import derive_production_answer
from src.deck_builder.semantic_audit import (
    build_audit_rows,
    semantic_sense_id,
    validate_audit_rows,
)


SCHEMA_VERSION = 2
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_CHECK_FIELDS = {
    "english_semantics",
    "vietnamese_semantics",
    "simplicity",
    "example_pos_alignment",
}
_REVIEW_FIELDS = {"reviewer", "reviewed_at", "approval", "reason"}
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "source_guid",
    "expected_registry_row_sha256",
    "expected_audit_row_sha256",
    "expected_built_card_sha256",
    "expected_source_fingerprint",
    "primary",
    "secondary",
    "source_ownership",
    "review",
}
_V2_TOP_LEVEL_FIELDS = _TOP_LEVEL_FIELDS | {
    "operation",
    "expected_target_source_fingerprint",
}
_PRIMARY_FIELDS = {"variant", "senses", "collocations", "idioms"}
_SECONDARY_FIELDS = {
    "guid",
    "variant",
    "deck_override",
    "senses",
    "collocations",
    "idioms",
}
_V2_SECONDARY_FIELDS = _SECONDARY_FIELDS | {
    "word",
    "pos",
    "cefr",
    "list",
    "source_word",
}
_SOURCE_OWNERSHIP_FIELDS = {"source_sense_id", "primary", "secondary"}
_SOURCE_SIDE_FIELDS = {
    "disposition",
    "target_semantic_sense_ids",
    "reason",
}
_EFFECTIVE_FIELDS = {"definition_en", "definition_vi", "examples"}
_CAMBRIDGE_FIELDS = {
    "url",
    "match",
    "summary",
    "translation_provenance",
    "accessed_at",
}


class CardIdentitySplitError(ValueError):
    """A split bundle or its bound canonical input is invalid."""


@dataclass(frozen=True, slots=True)
class PreparedCardIdentitySplit:
    registry_rows: list[dict]
    audit_rows: list[dict]
    projection_rows: list[dict]
    already_applied: bool
    registry_input_sha256: str
    audit_input_sha256: str


_TRANSACTION_SCHEMA_VERSION = 1
_TRANSACTION_PREFIX = ".card_identity_split.txn-"
_TRANSACTION_STATES = {
    "prepared",
    "registry_replaced",
    "audit_replaced",
    "projection_replaced",
    "committed",
}
_TRANSACTION_TARGET_KEYS = ("registry", "audit", "projection")


def row_sha256(row: dict) -> str:
    """Return the stable hash used to bind one immutable input row."""
    return hashlib.sha256(canonical_json_bytes(row)).hexdigest()


def serialize_rows(rows: Iterable[dict]) -> bytes:
    return canonical_jsonl_bytes(rows)


def _document_sha256(rows: Iterable[dict]) -> str:
    return hashlib.sha256(serialize_rows(rows)).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CardIdentitySplitError(f"invalid_jsonl:{path}:{exc}") from exc


def _require_fields(value: object, fields: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise CardIdentitySplitError(
            f"invalid_{label}_fields:expected={sorted(fields)} actual={actual}"
        )
    return value


def _validate_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise CardIdentitySplitError(f"invalid_{label}")
    return value


def _guid(row: dict) -> str:
    return str(row.get("guid") or row.get("GUID") or "")


def _index_unique(rows: Sequence[dict], *, label: str) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for row in rows:
        guid = _guid(row)
        if not guid or guid in indexed:
            raise CardIdentitySplitError(f"duplicate_or_empty_{label}_guid:{guid}")
        indexed[guid] = row
    return indexed


def _effective_content(sense: dict) -> dict:
    decision = sense.get("decision")
    if decision == "pass":
        content = sense.get("current") or {}
    elif decision == "repair_proposed" and sense.get("approval") == "approved":
        content = sense.get("proposed") or {}
    else:
        raise CardIdentitySplitError(
            "unpromotable_semantic_sense:"
            f"{sense.get('semantic_sense_id')}:{decision}"
        )
    return {
        "definition_en": str(content.get("definition_en") or ""),
        "definition_vi": str(content.get("definition_vi") or ""),
        "examples": list(content.get("examples") or []),
    }


def _validate_effective(value: object, label: str) -> dict:
    effective = _require_fields(value, _EFFECTIVE_FIELDS, label)
    if not isinstance(effective["definition_en"], str) or not effective["definition_en"]:
        raise CardIdentitySplitError(f"empty_{label}_definition_en")
    if not isinstance(effective["definition_vi"], str):
        raise CardIdentitySplitError(f"invalid_{label}_definition_vi")
    examples = effective["examples"]
    if not isinstance(examples, list) or any(
        not isinstance(example, str) or not example for example in examples
    ):
        raise CardIdentitySplitError(f"invalid_{label}_examples")
    return copy.deepcopy(effective)


def _validate_seed_list(value: object, *, delimiter: str, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item or delimiter in item for item in value
    ):
        raise CardIdentitySplitError(f"invalid_{label}")
    return list(value)


def _validate_review(review: object) -> dict:
    review = _require_fields(review, _REVIEW_FIELDS, "review")
    if review.get("approval") != "approved":
        raise CardIdentitySplitError("split_review_not_approved")
    for field in ("reviewer", "reviewed_at", "reason"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            raise CardIdentitySplitError(f"missing_review_{field}")
    return review


def _validate_bundle_shape(review_row: object) -> dict:
    if not isinstance(review_row, dict):
        raise CardIdentitySplitError("invalid_split_review_fields")
    schema_version = review_row.get("schema_version")
    fields = _V2_TOP_LEVEL_FIELDS if schema_version == 2 else _TOP_LEVEL_FIELDS
    row = _require_fields(review_row, fields, "split_review")
    if schema_version not in {1, SCHEMA_VERSION}:
        raise CardIdentitySplitError("invalid_split_review_schema_version")
    if schema_version == 2 and row.get("operation") != "extract_secondary_headword":
        raise CardIdentitySplitError("invalid_split_review_operation")
    if not isinstance(row.get("source_guid"), str) or not row["source_guid"]:
        raise CardIdentitySplitError("invalid_source_guid")
    for field in (
        "expected_registry_row_sha256",
        "expected_audit_row_sha256",
        "expected_built_card_sha256",
        "expected_source_fingerprint",
    ):
        _validate_hash(row.get(field), field)
    primary = _require_fields(row.get("primary"), _PRIMARY_FIELDS, "primary")
    secondary_fields = _V2_SECONDARY_FIELDS if schema_version == 2 else _SECONDARY_FIELDS
    secondary = _require_fields(row.get("secondary"), secondary_fields, "secondary")
    if schema_version == 1 and primary.get("variant") != "primary":
        raise CardIdentitySplitError("primary_variant_must_be_primary")
    if schema_version == 2 and primary.get("variant") != "":
        raise CardIdentitySplitError("extracted_primary_variant_must_remain_empty")
    if (
        not isinstance(secondary.get("variant"), str)
        or not secondary["variant"].startswith("secondary_")
    ):
        raise CardIdentitySplitError("invalid_secondary_variant")
    guid_error = guid_validation_error(secondary.get("guid"))
    if guid_error is not None:
        raise CardIdentitySplitError(f"invalid_secondary_guid:{guid_error[1]}")
    if not isinstance(secondary.get("deck_override"), str) or not secondary["deck_override"]:
        raise CardIdentitySplitError("missing_secondary_deck_override")
    if schema_version == 2:
        _validate_hash(
            row.get("expected_target_source_fingerprint"),
            "expected_target_source_fingerprint",
        )
        for field in ("word", "pos", "cefr", "list", "source_word"):
            if not isinstance(secondary.get(field), str) or not secondary[field].strip():
                raise CardIdentitySplitError(f"invalid_secondary_{field}")
        if secondary["word"].casefold() == secondary["source_word"].casefold():
            raise CardIdentitySplitError("secondary_source_word_must_differ_from_display_word")
    for label, side in (("primary", primary), ("secondary", secondary)):
        if not isinstance(side.get("senses"), list) or not side["senses"]:
            raise CardIdentitySplitError(
                f"invalid semantic sense partition:empty_{label}_senses"
            )
        _validate_seed_list(
            side.get("collocations"), delimiter="|", label=f"{label}_collocations"
        )
        _validate_seed_list(
            side.get("idioms"), delimiter="$$", label=f"{label}_idioms"
        )
    if not isinstance(row.get("source_ownership"), list):
        raise CardIdentitySplitError("invalid_source_ownership")
    _validate_review(row.get("review"))
    return row


def _validate_audit_identity(audit_rows: Sequence[dict], registry_rows: Sequence[dict]) -> None:
    registry = {
        str(row.get("guid") or ""): row
        for row in registry_rows
        if row.get("status") == "active"
    }
    for row in audit_rows:
        guid = str(row.get("guid") or "")
        expected = registry.get(guid)
        if expected is None:
            continue
        for field in ("word", "cefr", "list", "variant", "pos"):
            if str(row.get(field) or "") != str(expected.get(field) or ""):
                raise CardIdentitySplitError(f"audit_identity_mismatch:{guid}:{field}")


def _validate_global_semantic_ids(audit_rows: Sequence[dict]) -> None:
    owners: dict[str, str] = {}
    for row in audit_rows:
        guid = str(row.get("guid") or "")
        for sense in row.get("semantic_senses") or []:
            semantic_id = str(sense.get("semantic_sense_id") or "")
            previous = owners.setdefault(semantic_id, guid)
            if not semantic_id or previous != guid:
                raise CardIdentitySplitError(
                    f"duplicate_global_semantic_sense_id:{semantic_id}:{previous}:{guid}"
                )


def _validate_documents(
    registry_rows: list[dict],
    audit_rows: list[dict],
    projection_rows: list[dict],
    *,
    allow_unsplit_guids: set[str] | None = None,
) -> None:
    registry_for_validation = copy.deepcopy(registry_rows)
    audit_for_validation = copy.deepcopy(audit_rows)
    allowed = allow_unsplit_guids or set()
    if allowed:
        for row in registry_for_validation:
            if _guid(row) in allowed and row.get("variant") == "":
                row["variant"] = "primary"
        for row in audit_for_validation:
            if _guid(row) in allowed and row.get("variant") == "":
                row["variant"] = "primary"
    try:
        validate_registry_or_raise(registry_for_validation)
    except Exception as exc:
        raise CardIdentitySplitError(f"invalid_card_registry:{exc}") from exc
    audit_errors = validate_audit_rows(
        audit_for_validation, registry_for_validation, require_complete=True
    )
    if audit_errors:
        raise CardIdentitySplitError(
            "invalid_bilingual_semantic_audit:\n" + "\n".join(audit_errors[:100])
        )
    _validate_audit_identity(audit_for_validation, registry_for_validation)
    _validate_global_semantic_ids(audit_for_validation)
    active = {
        str(row.get("guid") or "")
        for row in registry_rows
        if row.get("status") == "active"
    }
    projection = _index_unique(projection_rows, label="projection")
    if set(projection) != active:
        missing = sorted(active - set(projection))
        extra = sorted(set(projection) - active)
        raise CardIdentitySplitError(
            f"projection_guid_coverage_mismatch:missing={missing[:5]} extra={extra[:5]}"
        )


def _fresh_source_context(
    card: dict,
    registry: dict,
    oxford_records: list[dict],
    cambridge_records: list[dict],
) -> dict:
    fresh = build_audit_rows(
        [card], [registry], oxford_records, cambridge_records
    )
    if len(fresh) != 1:
        raise CardIdentitySplitError(f"source_context_missing:{registry.get('guid')}")
    return fresh[0]


def _fresh_target_source_context(
    card: dict,
    registry: dict,
    source_word: str,
    oxford_records: list[dict],
) -> dict:
    exact_records = [
        record
        for record in oxford_records
        if str(record.get("word") or "").strip().casefold()
        == source_word.strip().casefold()
    ]
    if not exact_records:
        raise CardIdentitySplitError(f"target_oxford_page_missing:{source_word}")
    source_registry = {**registry, "word": source_word}
    source_card = {
        **card,
        "guid": registry["guid"],
        "word": source_word,
        "pos": registry["pos"],
        "cefr": registry["cefr"],
    }
    return _fresh_source_context(source_card, source_registry, exact_records, [])


def _group_fields(
    group: object,
    *,
    primary: bool,
    label: str,
    allow_target_sources: bool = False,
) -> dict:
    required = {"from_semantic_sense_ids", "effective"}
    optional = {"review_reason"}
    if allow_target_sources and not primary:
        optional |= {"source_sense_ids", "cambridge"}
    if primary:
        required.add("retain_semantic_sense_id")
    if not isinstance(group, dict) or not required.issubset(group) or set(group) - required - optional:
        raise CardIdentitySplitError(f"invalid_{label}_sense_group_fields")
    source_ids = group.get("from_semantic_sense_ids")
    if not isinstance(source_ids, list) or any(
        not isinstance(value, str) or not value for value in source_ids
    ) or len(source_ids) != len(set(source_ids)):
        raise CardIdentitySplitError(f"invalid_{label}_sense_origins")
    if not source_ids and not (allow_target_sources and not primary):
        raise CardIdentitySplitError(f"invalid_{label}_sense_origins")
    if not source_ids:
        target_source_ids = group.get("source_sense_ids")
        if not isinstance(target_source_ids, list) or not target_source_ids or any(
            not isinstance(value, str) or not value for value in target_source_ids
        ) or len(target_source_ids) != len(set(target_source_ids)):
            raise CardIdentitySplitError(f"invalid_{label}_target_source_sense_ids")
        cambridge = _require_fields(group.get("cambridge"), _CAMBRIDGE_FIELDS, f"{label}_cambridge")
        if cambridge.get("match") == "pending" or not cambridge.get("translation_provenance"):
            raise CardIdentitySplitError(f"incomplete_{label}_cambridge_review")
    _validate_effective(group.get("effective"), f"{label}_effective")
    if primary and group.get("retain_semantic_sense_id") not in source_ids:
        raise CardIdentitySplitError(f"invalid_{label}_retained_semantic_sense_id")
    return group


def _build_final_senses(
    old_senses: Sequence[dict],
    primary_plan: dict,
    secondary_plan: dict,
    secondary_guid: str,
    review: dict,
    *,
    allow_target_sources: bool = False,
) -> tuple[list[dict], list[dict], dict[str, tuple[str, str]]]:
    old_by_id = {
        str(sense.get("semantic_sense_id") or ""): sense
        for sense in old_senses
    }
    if len(old_by_id) != len(old_senses) or "" in old_by_id:
        raise CardIdentitySplitError("invalid_old_semantic_sense_ids")
    seen_origins: set[str] = set()
    origin_map: dict[str, tuple[str, str]] = {}

    def build_side(plan: dict, *, owner: str) -> list[dict]:
        output: list[dict] = []
        primary = owner == "primary"
        for order, raw_group in enumerate(plan["senses"], 1):
            group = _group_fields(
                raw_group,
                primary=primary,
                label=f"{owner}_{order}",
                allow_target_sources=allow_target_sources,
            )
            origins = list(group["from_semantic_sense_ids"])
            unknown = set(origins) - set(old_by_id)
            duplicate = set(origins) & seen_origins
            if unknown or duplicate:
                raise CardIdentitySplitError(
                    "invalid semantic sense partition:"
                    f"unknown={sorted(unknown)} duplicate={sorted(duplicate)}"
                )
            seen_origins.update(origins)
            effective = _validate_effective(
                group["effective"], f"{owner}_{order}_effective"
            )
            final_id = (
                str(group["retain_semantic_sense_id"])
                if primary
                else semantic_sense_id(
                    secondary_guid, order, effective["definition_en"]
                )
            )
            if origins:
                retained = group["retain_semantic_sense_id"] if primary else origins[0]
                sense = copy.deepcopy(old_by_id[retained])
                old_effective = _effective_content(sense)
            else:
                sense = {
                    "semantic_sense_id": final_id,
                    "order": order,
                    "source_sense_ids": [],
                    "current": {"definition_en": "", "definition_vi": "", "examples": []},
                    "checks": {field: "repair" for field in _CHECK_FIELDS},
                    "decision": "repair_proposed",
                    "proposed": copy.deepcopy(effective),
                    "cambridge": copy.deepcopy(group["cambridge"]),
                    "confidence": "high",
                    "review_reason": "",
                    "reviewer": review["reviewer"],
                    "reviewed_at": review["reviewed_at"],
                    "approval": "approved",
                }
                old_effective = {"definition_en": "", "definition_vi": "", "examples": []}
            changed = not origins or len(origins) > 1 or effective != old_effective
            if changed:
                reason = str(group.get("review_reason") or "").strip()
                if not reason:
                    raise CardIdentitySplitError(
                        f"missing_{owner}_{order}_sense_review_reason"
                    )
                sense.update({
                    "checks": {field: "repair" for field in _CHECK_FIELDS},
                    "decision": "repair_proposed",
                    "proposed": effective,
                    "confidence": "high",
                    "review_reason": reason,
                    "reviewer": review["reviewer"],
                    "reviewed_at": review["reviewed_at"],
                    "approval": "approved",
                })
            sense["order"] = order
            sense["semantic_sense_id"] = final_id
            sense["source_sense_ids"] = []
            output.append(sense)
            for origin in origins:
                origin_map[origin] = (owner, final_id)
            if not origins:
                origin_map[final_id] = (owner, final_id)
        return output

    primary = build_side(primary_plan, owner="primary")
    secondary = build_side(secondary_plan, owner="secondary")
    if seen_origins != set(old_by_id):
        raise CardIdentitySplitError(
            "invalid semantic sense partition:"
            f"missing={sorted(set(old_by_id) - seen_origins)}"
        )
    return primary, secondary, origin_map


def _build_source_coverage(
    plan_rows: object,
    fresh: dict,
    origin_map: dict[str, tuple[str, str]],
    *,
    allow_extra_plan_sources: bool = False,
) -> tuple[list[dict], list[dict]]:
    if not isinstance(plan_rows, list):
        raise CardIdentitySplitError("invalid_source_ownership")
    by_source: dict[str, dict] = {}
    for raw in plan_rows:
        item = _require_fields(
            raw, _SOURCE_OWNERSHIP_FIELDS, "source_ownership_item"
        )
        source_id = item.get("source_sense_id")
        if not isinstance(source_id, str) or not source_id or source_id in by_source:
            raise CardIdentitySplitError(f"duplicate_source_ownership:{source_id}")
        if all(
            isinstance(item.get(side_name), dict)
            and item[side_name].get("disposition") == "mapped"
            for side_name in ("primary", "secondary")
        ):
            raise CardIdentitySplitError(
                f"source must map to exactly one sibling or be excluded from both:{source_id}"
            )
        mapped_sides = 0
        for side_name in ("primary", "secondary"):
            side = _require_fields(
                item.get(side_name), _SOURCE_SIDE_FIELDS, f"{side_name}_source"
            )
            disposition = side.get("disposition")
            targets = side.get("target_semantic_sense_ids")
            reason = side.get("reason")
            if disposition not in {"mapped", "excluded"}:
                raise CardIdentitySplitError(
                    f"invalid_source_disposition:{source_id}:{side_name}"
                )
            if not isinstance(targets, list) or any(
                not isinstance(target, str) or not target for target in targets
            ) or len(targets) != len(set(targets)):
                raise CardIdentitySplitError(
                    f"invalid_source_targets:{source_id}:{side_name}"
                )
            if not isinstance(reason, str) or not reason.strip():
                raise CardIdentitySplitError(
                    f"missing_source_reason:{source_id}:{side_name}"
                )
            if disposition == "mapped":
                mapped_sides += 1
                if not targets:
                    raise CardIdentitySplitError(
                        f"mapped_source_without_target:{source_id}:{side_name}"
                    )
                for target in targets:
                    owner = origin_map.get(target)
                    if owner is None or owner[0] != side_name:
                        raise CardIdentitySplitError(
                            f"source_target_wrong_owner:{source_id}:{target}:{side_name}"
                        )
            elif targets:
                raise CardIdentitySplitError(
                    f"excluded_source_has_target:{source_id}:{side_name}"
                )
        if mapped_sides > 1:
            raise CardIdentitySplitError(
                f"source must map to exactly one sibling or be excluded from both:{source_id}"
            )
        by_source[source_id] = item

    candidate_ids = list(
        fresh.get("coverage", {}).get("candidate_source_sense_ids") or []
    )
    if (not allow_extra_plan_sources and set(by_source) != set(candidate_ids)) or not set(candidate_ids).issubset(by_source) or len(candidate_ids) != len(set(candidate_ids)):
        raise CardIdentitySplitError(
            "invalid source ownership partition:"
            f"missing={sorted(set(candidate_ids) - set(by_source))} "
            f"extra={sorted(set(by_source) - set(candidate_ids))}"
        )

    output = {"primary": [], "secondary": []}
    for source_id in candidate_ids:
        item = by_source[source_id]
        for side_name in ("primary", "secondary"):
            spec = item[side_name]
            targets = [
                origin_map[target][1]
                for target in spec["target_semantic_sense_ids"]
            ]
            output[side_name].append({
                "source_sense_id": source_id,
                "disposition": spec["disposition"],
                "target_semantic_sense_ids": list(dict.fromkeys(targets)),
                "reason": spec["reason"],
            })
    return output["primary"], output["secondary"]


def _attach_source_ids(senses: list[dict], coverage: Sequence[dict]) -> None:
    by_semantic = {
        str(sense.get("semantic_sense_id") or ""): sense for sense in senses
    }
    for item in coverage:
        if item.get("disposition") != "mapped":
            continue
        for semantic_id in item.get("target_semantic_sense_ids") or []:
            by_semantic[semantic_id]["source_sense_ids"].append(
                item["source_sense_id"]
            )
    for sense in senses:
        sense["source_sense_ids"] = sorted(set(sense["source_sense_ids"]))


def _coverage_status(senses: Sequence[dict]) -> str:
    decisions = {sense.get("decision") for sense in senses}
    if "uncertain" in decisions:
        return "uncertain"
    if "pending" in decisions:
        return "pending"
    if "repair_proposed" in decisions:
        return "repair_proposed"
    return "pass"


def _render_semantic_fields(senses: Sequence[dict]) -> tuple[str, str, str]:
    content = [_effective_content(sense) for sense in senses]
    definition = "|".join(
        f"{item['definition_en']} ({item['definition_vi']})"
        if item["definition_vi"]
        else item["definition_en"]
        for item in content
    )
    definition_vi = "|".join(item["definition_vi"] for item in content)
    example = "|".join("<br><br>".join(item["examples"]) for item in content)
    return definition, definition_vi, example


def _build_audit_card(
    registry: dict,
    fresh: dict,
    senses: list[dict],
    coverage: list[dict],
    idioms: Sequence[str],
) -> dict:
    definition, _, example = _render_semantic_fields(senses)
    row = {
        "schema_version": fresh["schema_version"],
        "guid": registry["guid"],
        "word": registry["word"],
        "cefr": registry["cefr"],
        "list": registry["list"],
        "variant": registry["variant"],
        "pos": registry["pos"],
        "current": {
            "definition": definition,
            "example": example,
            "idioms": "$$".join(idioms),
        },
        "source_fingerprint": fresh["source_fingerprint"],
        "source_senses": copy.deepcopy(fresh["source_senses"]),
        "coverage": copy.deepcopy(fresh["coverage"]),
        "source_coverage": coverage,
        "semantic_senses": senses,
    }
    row["coverage"]["status"] = _coverage_status(senses)
    row["coverage"]["reason"] = ""
    return row


def _set_note_field(note: dict, modern: str, legacy: str, value: str) -> None:
    if modern in note or legacy not in note:
        note[modern] = value
    else:
        note[legacy] = value


def _projection_card(
    old_card: dict,
    registry: dict,
    audit: dict,
    collocations: Sequence[str],
    idioms: Sequence[str],
) -> dict:
    card = copy.deepcopy(old_card)
    if "guid" in card or "GUID" not in card:
        card["guid"] = registry["guid"]
    else:
        card["GUID"] = registry["guid"]
    _set_note_field(card, "word", "Word", registry["word"])
    _set_note_field(card, "pos", "POS", registry["pos"])
    _set_note_field(card, "cefr", "CEFRLevel", registry["cefr"])
    _set_note_field(
        card,
        "production_answer",
        "ProductionAnswer",
        derive_production_answer(registry["word"]),
    )
    definition, definition_vi, example = _render_semantic_fields(
        audit["semantic_senses"]
    )
    _set_note_field(card, "definition", "Definition", definition)
    _set_note_field(card, "definition_vi", "DefinitionVI", definition_vi)
    _set_note_field(card, "example", "Example", example)
    _set_note_field(card, "collocations", "Collocations", "|".join(collocations))
    _set_note_field(card, "collocation_sources", "CollocationSources", "")
    _set_note_field(card, "idioms", "Idioms", "$$".join(idioms))
    if registry.get("deck_override"):
        _set_note_field(card, "deck", "Deck", registry["deck_override"])
    return card


def _registry_split_rows(old: dict, primary_plan: dict, secondary_plan: dict) -> tuple[dict, dict]:
    primary = copy.deepcopy(old)
    primary["variant"] = primary_plan["variant"]
    secondary = copy.deepcopy(old)
    secondary.update({
        "variant": secondary_plan["variant"],
        "guid": secondary_plan["guid"],
        "deck_override": secondary_plan["deck_override"],
    })
    for field in ("word", "pos", "cefr", "list"):
        if field in secondary_plan:
            secondary[field] = secondary_plan[field]
    for row in (primary, secondary):
        if not is_reviewed_identity_variant_allowed(
            row.get("word"),
            row.get("cefr"),
            row.get("list"),
            row.get("pos"),
            row.get("variant"),
        ):
            raise CardIdentitySplitError(
                f"unauthorized_reviewed_variant:{row.get('word')}:{row.get('variant')}"
            )
    return primary, secondary


def _replace_with_pair(rows: list[dict], guid: str, first: dict, second: dict) -> None:
    positions = [index for index, row in enumerate(rows) if _guid(row) == guid]
    if len(positions) != 1:
        raise CardIdentitySplitError(f"missing_or_duplicate_split_guid:{guid}")
    index = positions[0]
    rows[index:index + 1] = [first, second]


def _require_adjacent(
    rows: Sequence[dict], primary_guid: str, secondary_guid: str, label: str
) -> None:
    positions = {_guid(row): index for index, row in enumerate(rows)}
    if positions.get(secondary_guid) != positions.get(primary_guid, -2) + 1:
        raise CardIdentitySplitError(
            f"non_adjacent_primary_secondary:{label}:{primary_guid}:{secondary_guid}"
        )


def _side_source_coverage(
    fresh: dict,
    plan: dict,
    origin_map: dict[str, tuple[str, str]],
    *,
    allow_extra_plan_sources: bool = False,
) -> tuple[list[dict], list[dict]]:
    return _build_source_coverage(
        plan["source_ownership"],
        fresh,
        origin_map,
        allow_extra_plan_sources=allow_extra_plan_sources,
    )


def _validate_target_sense_sources(
    secondary_plan: dict,
    secondary_senses: Sequence[dict],
    secondary_coverage: Sequence[dict],
) -> None:
    mapped_by_semantic: dict[str, set[str]] = {}
    for item in secondary_coverage:
        if item.get("disposition") != "mapped":
            continue
        for semantic_id in item.get("target_semantic_sense_ids") or []:
            mapped_by_semantic.setdefault(str(semantic_id), set()).add(
                str(item.get("source_sense_id") or "")
            )
    for group, sense in zip(secondary_plan["senses"], secondary_senses):
        if group.get("from_semantic_sense_ids"):
            continue
        declared = set(group.get("source_sense_ids") or [])
        actual = mapped_by_semantic.get(str(sense.get("semantic_sense_id") or ""), set())
        if declared != actual:
            raise CardIdentitySplitError(
                "target_sense_source_mapping_mismatch:"
                f"{sense.get('semantic_sense_id')}:"
                f"declared={sorted(declared)} mapped={sorted(actual)}"
            )


def _verify_applied_split(
    primary_registry: dict,
    secondary_registry: dict | None,
    primary_audit: dict | None,
    secondary_audit: dict | None,
    primary_card: dict | None,
    secondary_card: dict | None,
    fresh: dict,
    target_fresh: dict | None,
    plan: dict,
) -> None:
    if None in (
        secondary_registry,
        primary_audit,
        secondary_audit,
        primary_card,
        secondary_card,
    ):
        raise CardIdentitySplitError(f"partial_applied_split:{plan['source_guid']}")
    assert secondary_registry is not None
    assert primary_audit is not None and secondary_audit is not None
    assert primary_card is not None and secondary_card is not None
    expected_primary, expected_secondary = _registry_split_rows(
        {**primary_registry, "variant": ""}, plan["primary"], plan["secondary"]
    )
    if primary_registry != expected_primary or secondary_registry != expected_secondary:
        raise CardIdentitySplitError(f"applied_registry_mismatch:{plan['source_guid']}")

    origin_map: dict[str, tuple[str, str]] = {}
    for owner, side, audit in (
        ("primary", plan["primary"], primary_audit),
        ("secondary", plan["secondary"], secondary_audit),
    ):
        senses = audit.get("semantic_senses") or []
        if len(senses) != len(side["senses"]):
            raise CardIdentitySplitError(f"applied_sense_count_mismatch:{owner}")
        for order, (sense, raw_group) in enumerate(zip(senses, side["senses"]), 1):
            group = _group_fields(
                raw_group,
                primary=owner == "primary",
                label=f"{owner}_{order}",
                allow_target_sources=plan["schema_version"] == 2,
            )
            effective = _validate_effective(
                group["effective"], f"{owner}_{order}_effective"
            )
            if _effective_content(sense) != effective or sense.get("order") != order:
                raise CardIdentitySplitError(f"applied_sense_content_mismatch:{owner}:{order}")
            expected_id = (
                group["retain_semantic_sense_id"]
                if owner == "primary"
                else semantic_sense_id(
                    secondary_registry["guid"], order, effective["definition_en"]
                )
            )
            if sense.get("semantic_sense_id") != expected_id:
                raise CardIdentitySplitError(f"applied_semantic_id_mismatch:{owner}:{order}")
            for origin in group["from_semantic_sense_ids"]:
                if origin in origin_map:
                    raise CardIdentitySplitError(f"duplicate_applied_sense_origin:{origin}")
                origin_map[origin] = (owner, expected_id)
            if not group["from_semantic_sense_ids"]:
                origin_map[expected_id] = (owner, expected_id)

    is_v2 = plan["schema_version"] == 2
    if is_v2:
        assert target_fresh is not None
        primary_coverage, _ = _side_source_coverage(
            fresh, plan, origin_map, allow_extra_plan_sources=True
        )
        _, secondary_coverage = _side_source_coverage(
            target_fresh, plan, origin_map, allow_extra_plan_sources=True
        )
        _validate_target_sense_sources(
            plan["secondary"], secondary_audit["semantic_senses"], secondary_coverage
        )
    else:
        primary_coverage, secondary_coverage = _side_source_coverage(
            fresh, plan, origin_map
        )
    for owner, registry, audit, coverage, side_fresh in (
        ("primary", primary_registry, primary_audit, primary_coverage, fresh),
        (
            "secondary",
            secondary_registry,
            secondary_audit,
            secondary_coverage,
            target_fresh if is_v2 else fresh,
        ),
    ):
        if any(
            str(audit.get(field) or "") != str(registry.get(field) or "")
            for field in ("guid", "word", "cefr", "list", "variant", "pos")
        ):
            raise CardIdentitySplitError(f"applied_audit_identity_mismatch:{owner}")
        if (
            audit.get("source_fingerprint") != side_fresh.get("source_fingerprint")
            or audit.get("source_senses") != side_fresh.get("source_senses")
            or audit.get("source_coverage") != coverage
        ):
            raise CardIdentitySplitError(f"applied_source_context_mismatch:{owner}")

    expected_primary_card = _projection_card(
        primary_card,
        primary_registry,
        primary_audit,
        plan["primary"]["collocations"],
        plan["primary"]["idioms"],
    )
    expected_secondary_card = _projection_card(
        primary_card,
        secondary_registry,
        secondary_audit,
        plan["secondary"]["collocations"],
        plan["secondary"]["idioms"],
    )
    if primary_card != expected_primary_card or secondary_card != expected_secondary_card:
        raise CardIdentitySplitError(f"applied_projection_mismatch:{plan['source_guid']}")


def prepare_card_identity_splits(
    registry_rows: list[dict],
    audit_rows: list[dict],
    built_cards: list[dict],
    oxford_records: list[dict],
    cambridge_records: list[dict],
    review_rows: list[dict],
) -> PreparedCardIdentitySplit:
    """Validate and stage reviewed splits without mutating supplied rows."""
    if not review_rows:
        raise CardIdentitySplitError("empty_split_review_bundle")
    plans = [_validate_bundle_shape(row) for row in review_rows]
    registry_input_sha256 = _document_sha256(registry_rows)
    audit_input_sha256 = _document_sha256(audit_rows)
    registry_rows = copy.deepcopy(registry_rows)
    audit_rows = copy.deepcopy(audit_rows)
    built_cards = copy.deepcopy(built_cards)
    _validate_documents(
        registry_rows,
        audit_rows,
        built_cards,
        allow_unsplit_guids={
            plan["source_guid"]
            for plan in plans
            if plan["schema_version"] == 1
        },
    )

    seen_source_guids: set[str] = set()
    seen_secondary_guids: set[str] = set()
    all_applied = True
    for plan in plans:
        source_guid = plan["source_guid"]
        secondary_guid = plan["secondary"]["guid"]
        if source_guid in seen_source_guids:
            raise CardIdentitySplitError(f"duplicate_split_source_guid:{source_guid}")
        if secondary_guid in seen_secondary_guids or secondary_guid == source_guid:
            raise CardIdentitySplitError(f"duplicate_split_secondary_guid:{secondary_guid}")
        seen_source_guids.add(source_guid)
        seen_secondary_guids.add(secondary_guid)

        registry_by_guid = _index_unique(registry_rows, label="registry")
        audit_by_guid = _index_unique(audit_rows, label="audit")
        cards_by_guid = _index_unique(built_cards, label="built_card")
        old_registry = registry_by_guid.get(source_guid)
        old_audit = audit_by_guid.get(source_guid)
        old_card = cards_by_guid.get(source_guid)
        if old_registry is None or old_audit is None or old_card is None:
            raise CardIdentitySplitError(f"unknown_split_source_guid:{source_guid}")

        fresh = _fresh_source_context(
            old_card, old_registry, oxford_records, cambridge_records
        )
        if fresh["source_fingerprint"] != plan["expected_source_fingerprint"]:
            raise CardIdentitySplitError(f"stale_source_context:{source_guid}")

        is_v2 = plan["schema_version"] == 2
        prospective_secondary = copy.deepcopy(old_registry)
        prospective_secondary.update(plan["secondary"])
        target_fresh = (
            _fresh_target_source_context(
                old_card,
                prospective_secondary,
                plan["secondary"]["source_word"],
                oxford_records,
            )
            if is_v2
            else None
        )
        if is_v2 and target_fresh["source_fingerprint"] != plan["expected_target_source_fingerprint"]:
            raise CardIdentitySplitError(f"stale_target_source_context:{source_guid}")

        applied_variant = plan["primary"]["variant"]
        if old_registry.get("variant") == applied_variant and secondary_guid in registry_by_guid:
            _verify_applied_split(
                old_registry,
                registry_by_guid.get(secondary_guid),
                old_audit,
                audit_by_guid.get(secondary_guid),
                old_card,
                cards_by_guid.get(secondary_guid),
                fresh,
                target_fresh,
                plan,
            )
            continue

        all_applied = False
        if old_registry.get("variant") != "":
            raise CardIdentitySplitError(
                f"split_source_is_not_unsplit:{source_guid}:{old_registry.get('variant')}"
            )
        if secondary_guid in registry_by_guid or secondary_guid in audit_by_guid or secondary_guid in cards_by_guid:
            raise CardIdentitySplitError(f"secondary_guid_already_exists:{secondary_guid}")
        for field, row in (
            ("registry", old_registry),
            ("audit", old_audit),
            ("built_card", old_card),
        ):
            expected = plan[f"expected_{field}_row_sha256"] if field != "built_card" else plan["expected_built_card_sha256"]
            if row_sha256(row) != expected:
                raise CardIdentitySplitError(f"stale_{field}_row:{source_guid}")

        primary_registry, secondary_registry = _registry_split_rows(
            old_registry, plan["primary"], plan["secondary"]
        )
        primary_senses, secondary_senses, origin_map = _build_final_senses(
            old_audit.get("semantic_senses") or [],
            plan["primary"],
            plan["secondary"],
            secondary_guid,
            plan["review"],
            allow_target_sources=is_v2,
        )
        if is_v2:
            assert target_fresh is not None
            planned_source_ids = {
                str(item.get("source_sense_id") or "")
                for item in plan["source_ownership"]
            }
            expected_source_ids = set(
                fresh.get("coverage", {}).get("candidate_source_sense_ids") or []
            ) | set(
                target_fresh.get("coverage", {}).get("candidate_source_sense_ids") or []
            )
            if planned_source_ids != expected_source_ids:
                raise CardIdentitySplitError(
                    "invalid source ownership partition:"
                    f"missing={sorted(expected_source_ids - planned_source_ids)} "
                    f"extra={sorted(planned_source_ids - expected_source_ids)}"
                )
            primary_coverage, _ = _side_source_coverage(
                fresh, plan, origin_map, allow_extra_plan_sources=True
            )
            _, secondary_coverage = _side_source_coverage(
                target_fresh, plan, origin_map, allow_extra_plan_sources=True
            )
            _validate_target_sense_sources(
                plan["secondary"], secondary_senses, secondary_coverage
            )
        else:
            primary_coverage, secondary_coverage = _side_source_coverage(
                fresh, plan, origin_map
            )
        _attach_source_ids(primary_senses, primary_coverage)
        _attach_source_ids(secondary_senses, secondary_coverage)
        primary_audit = _build_audit_card(
            primary_registry,
            fresh,
            primary_senses,
            primary_coverage,
            plan["primary"]["idioms"],
        )
        secondary_audit = _build_audit_card(
            secondary_registry,
            target_fresh if is_v2 else fresh,
            secondary_senses,
            secondary_coverage,
            plan["secondary"]["idioms"],
        )
        primary_card = _projection_card(
            old_card,
            primary_registry,
            primary_audit,
            plan["primary"]["collocations"],
            plan["primary"]["idioms"],
        )
        secondary_card = _projection_card(
            old_card,
            secondary_registry,
            secondary_audit,
            plan["secondary"]["collocations"],
            plan["secondary"]["idioms"],
        )
        _replace_with_pair(
            registry_rows, source_guid, primary_registry, secondary_registry
        )
        _replace_with_pair(audit_rows, source_guid, primary_audit, secondary_audit)
        _replace_with_pair(built_cards, source_guid, primary_card, secondary_card)

    _validate_documents(registry_rows, audit_rows, built_cards)
    for plan in plans:
        source_guid = str(plan.get("source_guid") or "")
        secondary_guid = str((plan.get("secondary") or {}).get("guid") or "")
        _require_adjacent(registry_rows, source_guid, secondary_guid, "registry")
        _require_adjacent(audit_rows, source_guid, secondary_guid, "audit")
        _require_adjacent(built_cards, source_guid, secondary_guid, "projection")
    return PreparedCardIdentitySplit(
        registry_rows=registry_rows,
        audit_rows=audit_rows,
        projection_rows=built_cards,
        already_applied=all_applied,
        registry_input_sha256=registry_input_sha256,
        audit_input_sha256=audit_input_sha256,
    )


def _write_fsynced(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_journal(path: Path, journal: dict) -> None:
    """Atomically persist a recovery journal before crossing a publish step."""
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    payload = (
        json.dumps(journal, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    try:
        _write_fsynced(temporary, payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _transaction_targets(
    registry_path: Path,
    audit_path: Path,
    projection_path: Path,
) -> dict[str, Path]:
    targets = {
        "registry": registry_path.resolve(),
        "audit": audit_path.resolve(),
        "projection": projection_path.resolve(),
    }
    if len(set(targets.values())) != len(_TRANSACTION_TARGET_KEYS):
        raise CardIdentitySplitError("duplicate_split_publish_targets")
    return targets


def _copy_fsynced(source: Path, target: Path) -> None:
    _write_fsynced(target, source.read_bytes())


def _backup_targets(txn_dir: Path, targets: dict[str, Path]) -> dict[str, dict]:
    backup_dir = txn_dir / "old"
    backup_dir.mkdir(parents=True, exist_ok=True)
    old: dict[str, dict] = {}
    for key, target in targets.items():
        if target.exists():
            if target.is_symlink():
                raise CardIdentitySplitError(f"target_is_symlink:{target}")
            if not target.is_file():
                raise CardIdentitySplitError(f"target_is_not_file:{target}")
            backup = backup_dir / key
            _copy_fsynced(target, backup)
            old[key] = {
                "exists": True,
                "sha256": _sha256_file(target),
                "backup": str(backup),
            }
        else:
            old[key] = {"exists": False, "sha256": None, "backup": None}
    return old


def _target_hash(path: Path) -> str | None:
    if path.is_symlink():
        raise CardIdentitySplitError(f"target_is_symlink:{path}")
    return _sha256_file(path) if path.exists() else None


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _validate_transaction_journal(
    txn_dir: Path,
    journal: dict,
    expected_targets: dict[str, Path] | None = None,
) -> tuple[dict[str, Path], dict, dict]:
    if journal.get("schema_version") != _TRANSACTION_SCHEMA_VERSION:
        raise CardIdentitySplitError(
            f"invalid_split_transaction_schema:{txn_dir}"
        )
    state = journal.get("state")
    if state not in _TRANSACTION_STATES:
        raise CardIdentitySplitError(
            f"unknown_split_transaction_state:{txn_dir}:{state}"
        )
    raw_targets = journal.get("targets")
    if not isinstance(raw_targets, dict) or set(raw_targets) != set(_TRANSACTION_TARGET_KEYS):
        raise CardIdentitySplitError(f"invalid_split_transaction_targets:{txn_dir}")
    targets = {
        key: Path(str(raw_targets[key])).resolve()
        for key in _TRANSACTION_TARGET_KEYS
    }
    if expected_targets is not None and targets != expected_targets:
        raise CardIdentitySplitError(f"split_transaction_target_mismatch:{txn_dir}")
    if len(set(targets.values())) != len(_TRANSACTION_TARGET_KEYS):
        raise CardIdentitySplitError(f"duplicate_split_transaction_targets:{txn_dir}")
    old = journal.get("old")
    staged = journal.get("staged")
    if not isinstance(old, dict) or not isinstance(staged, dict):
        raise CardIdentitySplitError(f"invalid_split_transaction_backups:{txn_dir}")
    for key in _TRANSACTION_TARGET_KEYS:
        old_info = old.get(key)
        staged_info = staged.get(key)
        if not isinstance(old_info, dict) or not isinstance(staged_info, dict):
            raise CardIdentitySplitError(f"invalid_split_transaction_entry:{txn_dir}:{key}")
        if old_info.get("exists"):
            if not isinstance(old_info.get("backup"), str):
                raise CardIdentitySplitError(f"missing_split_transaction_backup:{txn_dir}:{key}")
            if not _path_is_within(Path(old_info["backup"]), txn_dir):
                raise CardIdentitySplitError(
                    f"split_transaction_backup_outside_txn:{txn_dir}:{key}"
                )
            if not _SHA256_RE.fullmatch(str(old_info.get("sha256") or "")):
                raise CardIdentitySplitError(f"invalid_split_transaction_old_hash:{txn_dir}:{key}")
        elif old_info.get("sha256") is not None or old_info.get("backup") is not None:
            raise CardIdentitySplitError(f"invalid_split_transaction_missing_old:{txn_dir}:{key}")
        if not isinstance(staged_info.get("path"), str):
            raise CardIdentitySplitError(
                f"missing_split_transaction_staged_path:{txn_dir}:{key}"
            )
        if not _path_is_within(Path(staged_info["path"]), txn_dir):
            raise CardIdentitySplitError(
                f"split_transaction_staged_outside_txn:{txn_dir}:{key}"
            )
        if not _SHA256_RE.fullmatch(str(staged_info.get("sha256") or "")):
            raise CardIdentitySplitError(f"invalid_split_transaction_new_hash:{txn_dir}:{key}")
    return targets, old, staged


def _cleanup_transaction(txn_dir: Path) -> None:
    if txn_dir.exists():
        shutil.rmtree(txn_dir)


def _restore_transaction(
    txn_dir: Path,
    journal: dict,
    targets: dict[str, Path],
    old: dict,
    staged: dict,
) -> None:
    # Refuse to overwrite an unrelated post-crash edit.  A target may only be
    # the pre-transaction bytes, the staged bytes, or absent as recorded.
    for key, target in targets.items():
        current = _target_hash(target)
        old_hash = old[key].get("sha256")
        new_hash = staged[key].get("sha256")
        allowed = {old_hash, new_hash}
        if not old[key].get("exists"):
            allowed.add(None)
        if current not in allowed:
            raise CardIdentitySplitError(
                f"split_transaction_target_conflict:{txn_dir}:{key}"
            )

    for key, target in targets.items():
        old_info = old[key]
        if old_info.get("exists"):
            backup = Path(str(old_info["backup"]))
            if not backup.is_file() or _sha256_file(backup) != old_info["sha256"]:
                raise CardIdentitySplitError(
                    f"split_transaction_backup_corrupt:{txn_dir}:{key}"
                )
            # Copy, rather than move, so recovery is idempotent if interrupted.
            _copy_fsynced(backup, target)
            if _sha256_file(target) != old_info["sha256"]:
                raise CardIdentitySplitError(
                    f"split_transaction_restore_failed:{txn_dir}:{key}"
                )
        elif target.exists():
            target.unlink()


def _recover_transaction_dir(
    txn_dir: Path,
    *,
    expected_targets: dict[str, Path] | None = None,
) -> None:
    journal_path = txn_dir / "journal.json"
    if not journal_path.is_file():
        raise CardIdentitySplitError(f"missing_split_transaction_journal:{txn_dir}")
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CardIdentitySplitError(
            f"invalid_split_transaction_journal:{txn_dir}:{exc}"
        ) from exc
    targets, old, staged = _validate_transaction_journal(
        txn_dir, journal, expected_targets
    )
    if journal["state"] == "committed":
        mismatches = [
            key
            for key, target in targets.items()
            if _target_hash(target) != staged[key]["sha256"]
        ]
        if mismatches:
            raise CardIdentitySplitError(
                f"committed_split_transaction_hash_mismatch:{txn_dir}:{','.join(mismatches)}"
            )
    else:
        _restore_transaction(txn_dir, journal, targets, old, staged)
    _cleanup_transaction(txn_dir)


def recover_card_identity_split_transactions(
    registry_path: Path,
    audit_path: Path | None = None,
    projection_path: Path | None = None,
    *,
    acquire_lock: bool = True,
) -> None:
    """Recover interrupted Card Identity publishes left by a hard crash.

    Incomplete journals are restored from their durable backups.  A committed
    journal is retained only when every target still has the staged hash; this
    makes recovery fail closed on an unrelated external edit.
    """
    def recover() -> None:
        root = registry_path.resolve().parent
        expected = None
        if audit_path is not None and projection_path is not None:
            expected = _transaction_targets(
                registry_path, audit_path, projection_path
            )
        for txn_dir in sorted(root.glob(f"{_TRANSACTION_PREFIX}*")):
            if txn_dir.is_dir():
                # A crash while preparing backups/staged bytes happens before
                # the journal is durable and before any canonical target is
                # replaced.  Such an orphan is safe to discard; a
                # present-but-invalid journal still fails closed below because
                # it may describe a partial publish.
                if not (txn_dir / "journal.json").exists():
                    _cleanup_transaction(txn_dir)
                    continue
                _recover_transaction_dir(txn_dir, expected_targets=expected)

    if acquire_lock:
        lock_path = registry_path.resolve().parent / ".card_identity_split.lock"
        with _transaction_lock(lock_path):
            recover()
    else:
        recover()


@contextmanager
def _transaction_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        # A hard crash can leave the lock behind.  Reclaim it only when the
        # recorded owner is demonstrably gone; a live owner still fails closed.
        stale = False
        try:
            owner = int(path.read_text(encoding="ascii").strip())
            if owner <= 0:
                stale = True
            else:
                try:
                    os.kill(owner, 0)
                except ProcessLookupError:
                    stale = True
                except PermissionError:
                    stale = False
                except OSError:
                    stale = True
        except (OSError, ValueError, UnicodeDecodeError):
            stale = True
        if stale:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        else:
            raise CardIdentitySplitError(f"split_transaction_lock_exists:{path}") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        if path.exists():
            path.unlink()


def _parse_staged(path: Path, expected: list[dict]) -> None:
    actual = load_jsonl(path)
    if actual != expected or path.read_bytes() != serialize_rows(expected):
        raise CardIdentitySplitError(f"staged_validation_failed:{path}")


def publish_card_identity_split(
    prepared: PreparedCardIdentitySplit,
    registry_path: Path,
    audit_path: Path,
    projection_path: Path,
    *,
    fault_at: str | None = None,
) -> None:
    """Publish all three JSONL documents as an all-or-restore transaction.

    The replacement sequence cannot be made a single filesystem operation for
    three independent files.  A durable journal and old-value backups make the
    sequence recoverable, though: an ordinary exception is recovered
    immediately, while a later invocation can recover a journal left by a
    process/power crash before checking the prepared input fingerprints.
    """
    targets = _transaction_targets(registry_path, audit_path, projection_path)
    rows_by_key = {
        "registry": prepared.registry_rows,
        "audit": prepared.audit_rows,
        "projection": prepared.projection_rows,
    }
    payloads = {
        key: serialize_rows(rows) for key, rows in rows_by_key.items()
    }
    # The Card Registry is the transaction's identity authority.  Anchor the
    # lock beside it so concurrent callers cannot bypass one another merely by
    # choosing different scratch projection paths.
    lock_path = registry_path.resolve().parent / ".card_identity_split.lock"
    with _transaction_lock(lock_path):
        # A previous process may have died after one or more replacements.  Do
        # this before the optimistic input-hash check so recovery restores the
        # exact pre-transaction documents before we decide whether this plan is
        # still current.
        recover_card_identity_split_transactions(
            registry_path, audit_path, projection_path, acquire_lock=False
        )
        if prepared.already_applied:
            # Even an idempotent reapplication must finish recovery for a
            # journal left after the commit marker was durable but before
            # cleanup.  Verify the exact reviewed bytes afterwards: an
            # incomplete journal may have restored the old state, in which
            # case silently returning would claim success for a state that
            # still needs to be applied.
            if any(
                not targets[key].is_file()
                or load_jsonl(targets[key]) != rows_by_key[key]
                for key in _TRANSACTION_TARGET_KEYS
            ):
                raise CardIdentitySplitError(
                    "already_applied_state_changed_during_recovery"
                )
            return
        for path, expected in (
            (targets["registry"], prepared.registry_input_sha256),
            (targets["audit"], prepared.audit_input_sha256),
        ):
            if not path.is_file() or _document_sha256(load_jsonl(path)) != expected:
                raise CardIdentitySplitError(f"stale_document_before_publish:{path}")

        txn_dir = (
            targets["registry"].parent
            / f"{_TRANSACTION_PREFIX}{uuid.uuid4().hex}"
        )
        journal_path = txn_dir / "journal.json"
        created_txn = False
        try:
            txn_dir.mkdir(parents=True, exist_ok=False)
            created_txn = True
            old = _backup_targets(txn_dir, targets)
            staged: dict[str, dict] = {}
            staged_dir = txn_dir / "new"
            staged_dir.mkdir(parents=True, exist_ok=True)
            for key in _TRANSACTION_TARGET_KEYS:
                temporary = staged_dir / key
                _write_fsynced(temporary, payloads[key])
                # Parse before exposing any new bytes at a canonical path.
                _parse_staged(temporary, rows_by_key[key])
                staged[key] = {
                    "path": str(temporary),
                    "sha256": _sha256_file(temporary),
                }
            journal = {
                "schema_version": _TRANSACTION_SCHEMA_VERSION,
                "state": "prepared",
                "targets": {key: str(path) for key, path in targets.items()},
                "old": old,
                "staged": staged,
            }
            _write_journal(journal_path, journal)

            fault_names = (
                "after_registry_replace",
                "after_audit_replace",
                "after_projection_replace",
            )
            state_after_replace = {
                "registry": "registry_replaced",
                "audit": "audit_replaced",
                "projection": "projection_replaced",
            }
            for index, key in enumerate(_TRANSACTION_TARGET_KEYS):
                os.replace(Path(staged[key]["path"]), targets[key])
                if fault_at == fault_names[index]:
                    raise RuntimeError(f"injected fault at {fault_at}")
                journal["state"] = state_after_replace[key]
                _write_journal(journal_path, journal)

            # Confirm every visible target before recording the commit.  If a
            # process dies before this journal state reaches disk, recovery
            # intentionally restores the old set rather than guessing that a
            # late replacement completed.
            for key, target in targets.items():
                if _target_hash(target) != journal["staged"][key]["sha256"]:
                    raise CardIdentitySplitError(
                        f"split_transaction_target_hash_mismatch:{target}"
                    )
            journal["state"] = "committed"
            _write_journal(journal_path, journal)
            _cleanup_transaction(txn_dir)
        except Exception:
            if journal_path.is_file():
                # Reuse the same conflict-checked recovery path used after a
                # hard crash; this also leaves one implementation of rollback
                # semantics to test and maintain.
                _recover_transaction_dir(txn_dir, expected_targets=targets)
            elif created_txn and txn_dir.exists():
                # No canonical file is replaced before the journal is durable.
                # An interrupted backup/staging setup is therefore safe to
                # discard, and must not poison the next publish attempt.
                _cleanup_transaction(txn_dir)
            raise
