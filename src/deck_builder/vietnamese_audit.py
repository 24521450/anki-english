"""Deterministic naturalness audit for promoted Vietnamese sense glosses.

This module deliberately separates candidate selection from linguistic review.
Length and style signals only place a promoted sense in the review queue; they
never decide whether its Vietnamese should be rewritten.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping

from src.deck_builder.semantic_audit import CHECK_FIELDS, validate_audit_rows


VIETNAMESE_AUDIT_SCHEMA_VERSION = 3
DEFAULT_MIN_TOKENS = 8
AUDIT_SCOPES = ("long", "all")
REVIEW_DECISIONS = (
    "pending",
    "keep_natural",
    "keep_explanatory",
    "rewrite",
    "uncertain",
)
REVIEW_APPROVALS = ("", "approved", "rejected")
INPUT_NAMES = (
    "bilingual_semantic_audit",
    "card_registry",
    "semantic_registry",
)

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_CLAUSE_MARKER_RE = re.compile(
    r"(?:^|[\s,;])(người|vật|việc|điều|nơi|khi|mà|để|nhằm|"
    r"có thể|được dùng|dùng để)(?:\s|$)",
    re.IGNORECASE,
)


def _json_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rows_digest(rows: Iterable[dict]) -> str:
    return _json_digest(list(rows))


def input_content_hashes(
    registry_rows: list[dict],
    audit_rows: list[dict],
    card_registry_rows: list[dict],
) -> dict[str, str]:
    """Return deterministic content hashes when raw file hashes are unavailable."""
    return {
        "bilingual_semantic_audit": _rows_digest(audit_rows),
        "card_registry": _rows_digest(card_registry_rows),
        "semantic_registry": _rows_digest(registry_rows),
    }


def _normalise_input_hashes(
    registry_rows: list[dict],
    audit_rows: list[dict],
    card_registry_rows: list[dict],
    input_hashes: Mapping[str, str] | None,
) -> dict[str, str]:
    if input_hashes is None:
        return input_content_hashes(registry_rows, audit_rows, card_registry_rows)
    normalised = {str(key): str(value) for key, value in input_hashes.items()}
    if set(normalised) != set(INPUT_NAMES):
        raise ValueError("vietnamese_audit_invalid_input_hash_set")
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in normalised.values()):
        raise ValueError("vietnamese_audit_invalid_input_hash")
    return dict(sorted(normalised.items()))


def vietnamese_token_count(value: str) -> int:
    """Count learner-visible tokens using the audit's whitespace contract."""
    return len(str(value or "").split())


def _invalid_vietnamese(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    return any(separator in value for separator in "|\t\r\n") or bool(
        _BR_RE.search(value)
    )


def _lexical_text(value: object) -> str:
    """Return text with case, spacing, and punctuation differences removed."""
    return re.sub(r"[\W_]+", "", str(value or ""), flags=re.UNICODE).casefold()


def _unique_by_guid(rows: list[dict], *, label: str) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for row in rows:
        guid = str(row.get("guid") or "")
        if not guid or guid in indexed:
            raise ValueError(f"vietnamese_audit_duplicate_or_empty_{label}_guid:{guid}")
        indexed[guid] = row
    return indexed


def _sense_by_id(card: dict, field: str) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for sense in card.get(field) or []:
        semantic_id = str(sense.get("semantic_sense_id") or "")
        if not semantic_id or semantic_id in indexed:
            raise ValueError(
                "vietnamese_audit_duplicate_or_empty_semantic_sense_id:"
                f"{card.get('guid')}:{semantic_id}"
            )
        indexed[semantic_id] = sense
    return indexed


def _effective_audit_payload(guid: str, sense: dict) -> dict:
    decision = sense.get("decision")
    if decision == "pass":
        return sense.get("current") or {}
    if decision == "repair_proposed" and sense.get("approval") == "approved":
        return sense.get("proposed") or {}
    raise ValueError(
        "vietnamese_audit_unpromotable_audit_sense:"
        f"{guid}:{sense.get('semantic_sense_id')}:{decision}"
    )


def _validate_promoted_sense_parity(
    guid: str,
    registry_sense: dict,
    audit_sense: dict,
) -> None:
    semantic_id = str(registry_sense.get("semantic_sense_id") or "")
    effective = _effective_audit_payload(guid, audit_sense)
    comparisons = {
        "definition_en": (
            registry_sense.get("definition_en") or "",
            effective.get("definition_en") or "",
        ),
        "definition_vi": (
            registry_sense.get("definition_vi") or "",
            effective.get("definition_vi") or "",
        ),
        "examples": (
            list(registry_sense.get("examples") or []),
            list(effective.get("examples") or []),
        ),
        "source_sense_ids": (
            list(registry_sense.get("source_sense_ids") or []),
            list(audit_sense.get("source_sense_ids") or []),
        ),
        "order": (registry_sense.get("order"), audit_sense.get("order")),
    }
    for field, (promoted, expected) in comparisons.items():
        if promoted != expected:
            raise ValueError(
                f"vietnamese_audit_promoted_sense_mismatch:{guid}:"
                f"{semantic_id}:{field}"
            )


def _heuristic_flags(
    definition_vi: str,
    audit_current_vi: str,
    *,
    min_tokens: int,
) -> list[str]:
    flags = ["token_threshold"]
    if len(definition_vi) >= 50:
        flags.append("long_char_count")
    if _CLAUSE_MARKER_RE.search(definition_vi):
        flags.append("explanatory_clause")
    if definition_vi.count(",") >= 2 or ";" in definition_vi:
        flags.append("connector_heavy")
    if (
        audit_current_vi
        and definition_vi != audit_current_vi
        and vietnamese_token_count(definition_vi)
        > vietnamese_token_count(audit_current_vi)
    ):
        flags.append("expanded_from_audit_current")
    # The threshold itself is recorded in the summary. Keep the per-row flag
    # stable when a caller selects a threshold other than the default.
    if min_tokens != DEFAULT_MIN_TOKENS:
        flags.append(f"threshold_{min_tokens}")
    return flags


def _candidate_fingerprint(candidate: dict) -> str:
    payload = {key: value for key, value in candidate.items() if key != "candidate_fingerprint"}
    return _json_digest(payload)


def _context_fingerprint(candidate: Mapping[str, object]) -> str:
    return _json_digest(
        {
            key: candidate.get(key)
            for key in (
                "candidate_id",
                "guid",
                "semantic_sense_id",
                "order",
                "word",
                "cefr",
                "list",
                "variant",
                "pos",
                "source_fingerprint",
                "definition_en",
                "examples",
                "source_sense_ids",
            )
        }
    )


def _candidate_set_digest(candidates: list[dict]) -> str:
    return _json_digest(
        [
            {
                "candidate_id": row["candidate_id"],
                "candidate_fingerprint": row["candidate_fingerprint"],
            }
            for row in candidates
        ]
    )


def _review_final_vi(review: Mapping[str, object]) -> str:
    if review.get("decision") == "rewrite":
        return str(review.get("proposed_vi") or "")
    if review.get("decision") in {"keep_natural", "keep_explanatory"}:
        return str(review.get("expected_definition_vi") or "")
    return ""


def _review_is_reusable(review: dict, candidate: dict) -> bool:
    decision = review.get("decision")
    if (
        review.get("record_type") != "review"
        or review.get("schema_version") != VIETNAMESE_AUDIT_SCHEMA_VERSION
        or review.get("approval") != "approved"
        or decision not in {"keep_natural", "keep_explanatory", "rewrite"}
        or review.get("context_fingerprint") != candidate["context_fingerprint"]
        or _review_final_vi(review) != candidate["definition_vi"]
        or review.get("guid") != candidate["guid"]
        or review.get("semantic_sense_id") != candidate["semantic_sense_id"]
        or review.get("word") != candidate["word"]
        or review.get("order") != candidate["order"]
        or any(
            not str(review.get(field) or "").strip()
            for field in ("reason", "reviewer", "reviewed_at")
        )
    ):
        return False
    proposed_vi = review.get("proposed_vi", "")
    shorter_vi = review.get("shorter_vi_considered", "")
    distinction = str(review.get("preserved_distinction") or "").strip()
    expected_vi = str(review.get("expected_definition_vi") or "")
    if decision == "rewrite":
        return (
            not _invalid_vietnamese(proposed_vi)
            and proposed_vi != expected_vi
            and _lexical_text(proposed_vi) != _lexical_text(expected_vi)
            and not shorter_vi
            and not distinction
        )
    if proposed_vi:
        return False
    if decision == "keep_explanatory":
        return (
            not _invalid_vietnamese(shorter_vi)
            and vietnamese_token_count(shorter_vi)
            < vietnamese_token_count(expected_vi)
            and bool(distinction)
        )
    return not shorter_vi and not distinction


def build_vietnamese_audit(
    registry_rows: list[dict],
    audit_rows: list[dict],
    card_registry_rows: list[dict],
    *,
    min_tokens: int = DEFAULT_MIN_TOKENS,
    scope: str = "long",
    input_hashes: Mapping[str, str] | None = None,
) -> tuple[dict, list[dict]]:
    """Build the report-only queue from the promoted Semantic Registry."""
    if not isinstance(min_tokens, int) or isinstance(min_tokens, bool) or min_tokens < 1:
        raise ValueError("vietnamese_audit_invalid_min_tokens")
    if scope not in AUDIT_SCOPES:
        raise ValueError(f"vietnamese_audit_invalid_scope:{scope}")

    inputs = _normalise_input_hashes(
        registry_rows,
        audit_rows,
        card_registry_rows,
        input_hashes,
    )
    registry_by_guid = _unique_by_guid(registry_rows, label="semantic_registry")
    audit_by_guid = _unique_by_guid(audit_rows, label="semantic_audit")
    active_card_rows = [
        row for row in card_registry_rows if row.get("status") == "active"
    ]
    cards_by_guid = _unique_by_guid(active_card_rows, label="active_card_registry")

    candidates: list[dict] = []
    senses_scanned = 0
    identity_fields = ("word", "cefr", "list", "variant", "pos")
    for guid, card in registry_by_guid.items():
        audit_card = audit_by_guid.get(guid)
        identity = cards_by_guid.get(guid)
        if audit_card is None:
            raise ValueError(f"vietnamese_audit_missing_semantic_audit_card:{guid}")
        if identity is None:
            raise ValueError(f"vietnamese_audit_missing_active_card:{guid}")
        for field in identity_fields:
            if str(card.get(field) or "") != str(identity.get(field) or ""):
                raise ValueError(f"vietnamese_audit_identity_mismatch:{guid}:{field}")
        if str(card.get("source_fingerprint") or "") != str(
            audit_card.get("source_fingerprint") or ""
        ):
            raise ValueError(f"vietnamese_audit_source_fingerprint_mismatch:{guid}")

        audit_senses = _sense_by_id(audit_card, "semantic_senses")
        for sense in card.get("senses") or []:
            senses_scanned += 1
            semantic_id = str(sense.get("semantic_sense_id") or "")
            audit_sense = audit_senses.get(semantic_id)
            if audit_sense is None:
                raise ValueError(
                    f"vietnamese_audit_missing_audit_sense:{guid}:{semantic_id}"
                )
            _validate_promoted_sense_parity(guid, sense, audit_sense)
            definition_vi = str(sense.get("definition_vi") or "")
            token_count = vietnamese_token_count(definition_vi)
            if scope == "long" and token_count < min_tokens:
                continue
            current_vi = str(
                (audit_sense.get("current") or {}).get("definition_vi") or ""
            )
            proposed_vi = str(
                (audit_sense.get("proposed") or {}).get("definition_vi") or ""
            )
            cambridge = audit_sense.get("cambridge") or {}
            candidate = {
                "record_type": "candidate",
                "schema_version": VIETNAMESE_AUDIT_SCHEMA_VERSION,
                "candidate_id": f"{guid}::{semantic_id}",
                "guid": guid,
                "semantic_sense_id": semantic_id,
                "order": sense.get("order"),
                "word": str(card.get("word") or ""),
                "cefr": str(card.get("cefr") or ""),
                "list": str(card.get("list") or ""),
                "variant": str(card.get("variant") or ""),
                "pos": str(card.get("pos") or ""),
                "source_fingerprint": str(card.get("source_fingerprint") or ""),
                "definition_en": str(sense.get("definition_en") or ""),
                "definition_vi": definition_vi,
                "examples": list(sense.get("examples") or []),
                "source_sense_ids": list(sense.get("source_sense_ids") or []),
                "vi_token_count": token_count,
                "vi_char_count": len(definition_vi),
                "heuristic_flags": _heuristic_flags(
                    definition_vi,
                    current_vi,
                    min_tokens=min_tokens,
                ),
                "audit_decision": str(audit_sense.get("decision") or ""),
                "audit_current_vi": current_vi,
                "audit_proposed_vi": proposed_vi,
                "cambridge_url": str(cambridge.get("url") or ""),
                "cambridge_match": str(cambridge.get("match") or ""),
                "cambridge_summary": str(cambridge.get("summary") or ""),
                "translation_provenance": str(
                    cambridge.get("translation_provenance")
                    or sense.get("translation_provenance")
                    or ""
                ),
            }
            candidate["context_fingerprint"] = _context_fingerprint(candidate)
            candidate["candidate_fingerprint"] = _candidate_fingerprint(candidate)
            candidates.append(candidate)

    candidates.sort(
        key=lambda row: (
            row["word"].casefold(),
            row["cefr"],
            row["list"],
            row["variant"],
            row["guid"],
            row["order"],
            row["semantic_sense_id"],
        )
    )
    summary = {
        "record_type": "summary",
        "schema_version": VIETNAMESE_AUDIT_SCHEMA_VERSION,
        "inputs": inputs,
        "scope": scope,
        "selection": (
            "all_promoted_definition_vi"
            if scope == "all"
            else "promoted_definition_vi_whitespace_tokens_gte_min_tokens"
        ),
        "min_tokens": min_tokens,
        "cards_scanned": len(registry_rows),
        "senses_scanned": senses_scanned,
        "candidate_cards": len({row["guid"] for row in candidates}),
        "candidate_senses": len(candidates),
        "candidate_set_sha256": _candidate_set_digest(candidates),
    }
    errors = validate_vietnamese_audit(summary, candidates)
    if errors:
        raise ValueError(
            "Vietnamese audit report validation failed:\n" + "\n".join(errors)
        )
    return summary, candidates


def validate_vietnamese_audit(summary: dict, candidates: list[dict]) -> list[str]:
    """Validate report structure, metrics, ordering, and fingerprints."""
    errors: list[str] = []
    if summary.get("record_type") != "summary":
        errors.append("invalid_summary_record_type")
    if summary.get("schema_version") != VIETNAMESE_AUDIT_SCHEMA_VERSION:
        errors.append("invalid_summary_schema_version")
    min_tokens = summary.get("min_tokens")
    if not isinstance(min_tokens, int) or isinstance(min_tokens, bool) or min_tokens < 1:
        errors.append("invalid_summary_min_tokens")
        min_tokens = DEFAULT_MIN_TOKENS
    scope = summary.get("scope")
    if scope not in AUDIT_SCOPES:
        errors.append("invalid_summary_scope")
        scope = "long"
    if set(summary.get("inputs") or {}) != set(INPUT_NAMES):
        errors.append("invalid_summary_inputs")

    seen: set[str] = set()
    for row in candidates:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen:
            errors.append(f"duplicate_or_empty_candidate:{candidate_id}")
        seen.add(candidate_id)
        if row.get("record_type") != "candidate":
            errors.append(f"invalid_candidate_record_type:{candidate_id}")
        if row.get("schema_version") != VIETNAMESE_AUDIT_SCHEMA_VERSION:
            errors.append(f"invalid_candidate_schema_version:{candidate_id}")
        definition_vi = str(row.get("definition_vi") or "")
        if _invalid_vietnamese(definition_vi):
            errors.append(f"invalid_candidate_definition_vi:{candidate_id}")
        token_count = vietnamese_token_count(definition_vi)
        if row.get("vi_token_count") != token_count:
            errors.append(f"token_count_mismatch:{candidate_id}")
        if scope == "long" and token_count < min_tokens:
            errors.append(f"candidate_below_threshold:{candidate_id}")
        if row.get("vi_char_count") != len(definition_vi):
            errors.append(f"char_count_mismatch:{candidate_id}")
        if row.get("candidate_fingerprint") != _candidate_fingerprint(row):
            errors.append(f"candidate_fingerprint_mismatch:{candidate_id}")
        if row.get("context_fingerprint") != _context_fingerprint(row):
            errors.append(f"context_fingerprint_mismatch:{candidate_id}")

    expected_order = sorted(
        candidates,
        key=lambda row: (
            str(row.get("word") or "").casefold(),
            str(row.get("cefr") or ""),
            str(row.get("list") or ""),
            str(row.get("variant") or ""),
            str(row.get("guid") or ""),
            row.get("order"),
            str(row.get("semantic_sense_id") or ""),
        ),
    )
    if candidates != expected_order:
        errors.append("candidate_order_mismatch")
    if summary.get("candidate_senses") != len(candidates):
        errors.append("candidate_sense_count_mismatch")
    if summary.get("candidate_cards") != len(
        {row.get("guid") for row in candidates}
    ):
        errors.append("candidate_card_count_mismatch")
    if summary.get("candidate_set_sha256") != _candidate_set_digest(candidates):
        errors.append("candidate_set_sha256_mismatch")
    return errors


def scaffold_vietnamese_review(
    summary: dict,
    candidates: list[dict],
    *,
    existing_review_rows: list[dict] | None = None,
) -> tuple[dict, list[dict]]:
    """Create an exact-coverage, fingerprint-protected review ledger."""
    errors = validate_vietnamese_audit(summary, candidates)
    if errors:
        raise ValueError("Invalid Vietnamese audit:\n" + "\n".join(errors))
    review_summary = {
        "record_type": "review_summary",
        "schema_version": VIETNAMESE_AUDIT_SCHEMA_VERSION,
        "inputs": copy.deepcopy(summary["inputs"]),
        "scope": summary["scope"],
        "min_tokens": summary["min_tokens"],
        "candidate_count": len(candidates),
        "candidate_set_sha256": summary["candidate_set_sha256"],
    }
    existing_by_id: dict[str, dict] = {}
    duplicate_ids: set[str] = set()
    for row in existing_review_rows or []:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in existing_by_id:
            duplicate_ids.add(candidate_id)
            continue
        existing_by_id[candidate_id] = row

    review_rows: list[dict] = []
    for candidate in candidates:
        existing = existing_by_id.get(candidate["candidate_id"])
        if (
            candidate["candidate_id"] not in duplicate_ids
            and existing is not None
            and _review_is_reusable(existing, candidate)
        ):
            review_rows.append(copy.deepcopy(existing))
            continue
        review_rows.append(
            {
                "record_type": "review",
                "schema_version": VIETNAMESE_AUDIT_SCHEMA_VERSION,
                "candidate_id": candidate["candidate_id"],
                "candidate_fingerprint": candidate["candidate_fingerprint"],
                "context_fingerprint": candidate["context_fingerprint"],
                "guid": candidate["guid"],
                "semantic_sense_id": candidate["semantic_sense_id"],
                "word": candidate["word"],
                "order": candidate["order"],
                "expected_definition_vi": candidate["definition_vi"],
                "decision": "pending",
                "proposed_vi": "",
                "shorter_vi_considered": "",
                "preserved_distinction": "",
                "reason": "",
                "reviewer": "",
                "reviewed_at": "",
                "approval": "",
            }
        )
    return review_summary, review_rows


def validate_vietnamese_review(
    summary: dict,
    candidates: list[dict],
    review_summary: dict,
    review_rows: list[dict],
    *,
    require_complete: bool = False,
) -> list[str]:
    """Validate exact candidate coverage and all immutable review evidence."""
    errors = validate_vietnamese_audit(summary, candidates)
    min_tokens = summary.get("min_tokens", DEFAULT_MIN_TOKENS)
    if review_summary.get("record_type") != "review_summary":
        errors.append("review_missing_summary")
    if review_summary.get("schema_version") != VIETNAMESE_AUDIT_SCHEMA_VERSION:
        errors.append("review_invalid_schema_version")
    if review_summary.get("inputs") != summary.get("inputs"):
        errors.append("review_stale_inputs")
    if review_summary.get("scope") != summary.get("scope"):
        errors.append("review_stale_scope")
    if review_summary.get("min_tokens") != summary.get("min_tokens"):
        errors.append("review_stale_threshold")
    if review_summary.get("candidate_set_sha256") != summary.get(
        "candidate_set_sha256"
    ):
        errors.append("review_stale_candidate_set")
    if review_summary.get("candidate_count") != len(candidates):
        errors.append("review_candidate_count_mismatch")

    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    seen: set[str] = set()
    for review in review_rows:
        candidate_id = str(review.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen:
            errors.append(f"review_duplicate_or_empty_candidate:{candidate_id}")
            continue
        seen.add(candidate_id)
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None:
            errors.append(f"review_extra_candidate:{candidate_id}")
            continue
        identity = f"{candidate['guid']}:{candidate['semantic_sense_id']}"
        if review.get("record_type") != "review":
            errors.append(f"review_invalid_record_type:{identity}")
        if review.get("schema_version") != VIETNAMESE_AUDIT_SCHEMA_VERSION:
            errors.append(f"review_invalid_row_schema_version:{identity}")
        context_matches = (
            review.get("context_fingerprint") == candidate["context_fingerprint"]
        )
        reusable_snapshot = (
            review.get("approval") == "approved"
            and context_matches
            and _review_final_vi(review) == candidate["definition_vi"]
        )
        if (
            review.get("candidate_fingerprint") != candidate["candidate_fingerprint"]
            and not reusable_snapshot
        ):
            errors.append(f"review_stale_fingerprint:{identity}")
        if not context_matches:
            errors.append(f"review_stale_context:{identity}")
        if review.get("guid") != candidate["guid"] or review.get(
            "semantic_sense_id"
        ) != candidate["semantic_sense_id"]:
            errors.append(f"review_identity_mismatch:{identity}")
        if review.get("word") != candidate["word"] or review.get("order") != candidate[
            "order"
        ]:
            errors.append(f"review_display_identity_mismatch:{identity}")
        if (
            review.get("expected_definition_vi") != candidate["definition_vi"]
            and not reusable_snapshot
        ):
            errors.append(f"review_stale_definition_vi:{identity}")

        decision = review.get("decision")
        if decision not in REVIEW_DECISIONS:
            errors.append(f"review_invalid_decision:{identity}:{decision}")
            continue
        approval = review.get("approval", "")
        if approval not in REVIEW_APPROVALS:
            errors.append(f"review_invalid_approval:{identity}:{approval}")
        proposed_vi = review.get("proposed_vi", "")
        shorter_vi_considered = review.get("shorter_vi_considered", "")
        preserved_distinction = str(
            review.get("preserved_distinction") or ""
        ).strip()
        expected_vi = str(review.get("expected_definition_vi") or "")
        expected_token_count = vietnamese_token_count(expected_vi)
        if decision == "rewrite":
            if _invalid_vietnamese(proposed_vi):
                errors.append(f"review_invalid_proposed_vi:{identity}")
            elif proposed_vi == expected_vi:
                errors.append(f"review_rewrite_without_change:{identity}")
            elif _lexical_text(proposed_vi) == _lexical_text(expected_vi):
                errors.append(
                    f"review_rewrite_without_substantive_change:{identity}"
                )
            if (
                expected_token_count >= min_tokens
                and not _invalid_vietnamese(proposed_vi)
                and vietnamese_token_count(proposed_vi) >= expected_token_count
            ):
                errors.append(f"review_rewrite_without_compression:{identity}")
            if shorter_vi_considered:
                errors.append(f"review_unexpected_shorter_vi_considered:{identity}")
            if preserved_distinction:
                errors.append(f"review_unexpected_preserved_distinction:{identity}")
        elif proposed_vi:
            errors.append(f"review_unexpected_proposed_vi:{identity}")

        if decision == "keep_explanatory":
            if _invalid_vietnamese(shorter_vi_considered):
                errors.append(f"review_missing_shorter_vi_considered:{identity}")
            elif vietnamese_token_count(shorter_vi_considered) >= expected_token_count:
                errors.append(f"review_non_shorter_vi_considered:{identity}")
            if not preserved_distinction:
                errors.append(f"review_missing_preserved_distinction:{identity}")
        elif decision == "keep_natural" and expected_token_count >= min_tokens:
            errors.append(
                f"review_long_gloss_requires_explanatory_evidence:{identity}"
            )
        elif decision != "rewrite":
            if shorter_vi_considered:
                errors.append(f"review_unexpected_shorter_vi_considered:{identity}")
            if preserved_distinction:
                errors.append(f"review_unexpected_preserved_distinction:{identity}")

        if require_complete:
            if decision in {"pending", "uncertain"}:
                errors.append(f"review_open_decision:{identity}")
            if approval != "approved":
                errors.append(f"review_not_approved:{identity}")
            for field in ("reason", "reviewer", "reviewed_at"):
                if not str(review.get(field) or "").strip():
                    errors.append(f"review_missing_{field}:{identity}")

    missing = sorted(set(candidates_by_id) - seen)
    for candidate_id in missing:
        errors.append(f"review_missing_candidate:{candidate_id}")
    return errors


def validate_vietnamese_review_for_promotion(
    audit_rows: list[dict],
    review_summary: dict,
    review_rows: list[dict],
) -> list[str]:
    """Validate an all-sense review against effective bilingual audit payloads."""
    errors: list[str] = []
    if review_summary.get("record_type") != "review_summary":
        errors.append("promotion_review_missing_summary")
    if review_summary.get("schema_version") != VIETNAMESE_AUDIT_SCHEMA_VERSION:
        errors.append("promotion_review_invalid_schema_version")
    if review_summary.get("scope") != "all":
        errors.append("promotion_review_scope_must_be_all")
    min_tokens = review_summary.get("min_tokens", DEFAULT_MIN_TOKENS)
    if (
        not isinstance(min_tokens, int)
        or isinstance(min_tokens, bool)
        or min_tokens < 1
    ):
        errors.append("promotion_review_invalid_min_tokens")
        min_tokens = DEFAULT_MIN_TOKENS

    effective_by_id: dict[str, dict] = {}
    seen_guids: set[str] = set()
    for card in sorted(audit_rows, key=lambda row: str(row.get("guid") or "")):
        guid = str(card.get("guid") or "")
        if not guid or guid in seen_guids:
            errors.append(f"promotion_duplicate_or_empty_guid:{guid}")
            continue
        seen_guids.add(guid)
        seen_senses: set[str] = set()
        for sense in card.get("semantic_senses") or []:
            semantic_id = str(sense.get("semantic_sense_id") or "")
            candidate_id = f"{guid}::{semantic_id}"
            if not semantic_id or semantic_id in seen_senses:
                errors.append(
                    f"promotion_duplicate_or_empty_semantic_sense_id:{candidate_id}"
                )
                continue
            seen_senses.add(semantic_id)
            try:
                effective = _effective_audit_payload(guid, sense)
            except ValueError as exc:
                errors.append(f"promotion_{exc}")
                continue
            candidate = {
                "candidate_id": candidate_id,
                "guid": guid,
                "semantic_sense_id": semantic_id,
                "order": sense.get("order"),
                "word": str(card.get("word") or ""),
                "cefr": str(card.get("cefr") or ""),
                "list": str(card.get("list") or ""),
                "variant": str(card.get("variant") or ""),
                "pos": str(card.get("pos") or ""),
                "source_fingerprint": str(card.get("source_fingerprint") or ""),
                "definition_en": str(effective.get("definition_en") or ""),
                "definition_vi": str(effective.get("definition_vi") or ""),
                "examples": list(effective.get("examples") or []),
                "source_sense_ids": list(sense.get("source_sense_ids") or []),
            }
            candidate["context_fingerprint"] = _context_fingerprint(candidate)
            effective_by_id[candidate_id] = candidate

    if review_summary.get("candidate_count") != len(effective_by_id):
        errors.append("promotion_review_candidate_count_mismatch")

    reviews_by_id: dict[str, dict] = {}
    for review in review_rows:
        candidate_id = str(review.get("candidate_id") or "")
        if not candidate_id or candidate_id in reviews_by_id:
            errors.append(f"promotion_review_duplicate_or_empty_candidate:{candidate_id}")
            continue
        reviews_by_id[candidate_id] = review

    for candidate_id in sorted(set(reviews_by_id) - set(effective_by_id)):
        errors.append(f"promotion_review_extra_candidate:{candidate_id}")
    for candidate_id in sorted(effective_by_id):
        candidate = effective_by_id[candidate_id]
        review = reviews_by_id.get(candidate_id)
        if review is None:
            errors.append(f"promotion_review_missing_candidate:{candidate_id}")
            continue
        identity = f"{candidate['guid']}:{candidate['semantic_sense_id']}"
        if review.get("record_type") != "review":
            errors.append(f"promotion_review_invalid_record_type:{identity}")
        if review.get("schema_version") != VIETNAMESE_AUDIT_SCHEMA_VERSION:
            errors.append(f"promotion_review_invalid_row_schema_version:{identity}")
        if review.get("context_fingerprint") != candidate["context_fingerprint"]:
            errors.append(f"promotion_review_stale_context:{identity}")
        if (
            review.get("guid") != candidate["guid"]
            or review.get("semantic_sense_id") != candidate["semantic_sense_id"]
            or review.get("word") != candidate["word"]
            or review.get("order") != candidate["order"]
        ):
            errors.append(f"promotion_review_identity_mismatch:{identity}")

        decision = review.get("decision")
        if decision not in {"keep_natural", "keep_explanatory", "rewrite"}:
            errors.append(f"promotion_review_open_or_invalid_decision:{identity}")
        if review.get("approval") != "approved":
            errors.append(f"promotion_review_not_approved:{identity}")
        for field in ("reason", "reviewer", "reviewed_at"):
            if not str(review.get(field) or "").strip():
                errors.append(f"promotion_review_missing_{field}:{identity}")

        expected_vi = str(review.get("expected_definition_vi") or "")
        proposed_vi = review.get("proposed_vi", "")
        shorter_vi = review.get("shorter_vi_considered", "")
        distinction = str(review.get("preserved_distinction") or "").strip()
        if decision == "rewrite":
            if _invalid_vietnamese(proposed_vi):
                errors.append(f"promotion_review_invalid_proposed_vi:{identity}")
            elif proposed_vi == expected_vi:
                errors.append(f"promotion_review_rewrite_without_change:{identity}")
            elif _lexical_text(proposed_vi) == _lexical_text(expected_vi):
                errors.append(
                    f"promotion_review_rewrite_without_substantive_change:{identity}"
                )
            if (
                vietnamese_token_count(expected_vi) >= min_tokens
                and not _invalid_vietnamese(proposed_vi)
                and vietnamese_token_count(proposed_vi)
                >= vietnamese_token_count(expected_vi)
            ):
                errors.append(
                    f"promotion_review_rewrite_without_compression:{identity}"
                )
            if shorter_vi or distinction:
                errors.append(f"promotion_review_unexpected_rewrite_evidence:{identity}")
        elif decision == "keep_explanatory":
            if _invalid_vietnamese(shorter_vi):
                errors.append(
                    f"promotion_review_missing_shorter_vi_considered:{identity}"
                )
            elif vietnamese_token_count(shorter_vi) >= vietnamese_token_count(
                expected_vi
            ):
                errors.append(
                    f"promotion_review_non_shorter_vi_considered:{identity}"
                )
            if not distinction:
                errors.append(
                    f"promotion_review_missing_preserved_distinction:{identity}"
                )
            if proposed_vi:
                errors.append(f"promotion_review_unexpected_proposed_vi:{identity}")
        elif decision == "keep_natural":
            if vietnamese_token_count(candidate["definition_vi"]) >= min_tokens:
                errors.append(
                    "promotion_review_long_gloss_requires_explanatory_evidence:"
                    f"{identity}"
                )
            if proposed_vi or shorter_vi or distinction:
                errors.append(f"promotion_review_unexpected_keep_evidence:{identity}")

        final_vi = _review_final_vi(review)
        if _invalid_vietnamese(final_vi) or final_vi != candidate["definition_vi"]:
            errors.append(f"promotion_review_final_vi_mismatch:{identity}")

    return sorted(errors)


def apply_vietnamese_review(
    registry_rows: list[dict],
    audit_rows: list[dict],
    card_registry_rows: list[dict],
    review_summary: dict,
    review_rows: list[dict],
    *,
    input_hashes: Mapping[str, str] | None = None,
    require_complete: bool = True,
) -> list[dict]:
    """Apply approved rewrites to a deep copy of the semantic review ledger."""
    min_tokens = review_summary.get("min_tokens")
    scope = review_summary.get("scope", "long")
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_registry_rows,
        min_tokens=min_tokens,
        scope=scope,
        input_hashes=input_hashes,
    )
    review_errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        review_rows,
        require_complete=require_complete,
    )
    if review_errors:
        raise ValueError(
            "Vietnamese naturalness review is invalid:\n"
            + "\n".join(review_errors)
        )

    updated = copy.deepcopy(audit_rows)
    audit_by_guid = {card["guid"]: card for card in updated}
    registry_by_guid = {card["guid"]: card for card in registry_rows}
    reviews_by_id = {row["candidate_id"]: row for row in review_rows}

    for candidate in candidates:
        review = reviews_by_id[candidate["candidate_id"]]
        if review.get("decision") != "rewrite":
            continue
        if review.get("proposed_vi") == candidate["definition_vi"]:
            continue
        guid = candidate["guid"]
        semantic_id = candidate["semantic_sense_id"]
        audit_card = audit_by_guid[guid]
        audit_sense = _sense_by_id(audit_card, "semantic_senses")[semantic_id]
        registry_sense = _sense_by_id(registry_by_guid[guid], "senses")[semantic_id]

        if audit_sense.get("decision") == "repair_proposed":
            existing_proposed = audit_sense.get("proposed") or {}
            definition_en = existing_proposed.get("definition_en")
            examples = copy.deepcopy(existing_proposed.get("examples"))
        else:
            definition_en = registry_sense.get("definition_en")
            examples = copy.deepcopy(registry_sense.get("examples") or [])
        audit_sense["proposed"] = {
            "definition_en": definition_en,
            "definition_vi": review["proposed_vi"],
            "examples": examples,
        }
        checks = dict(audit_sense.get("checks") or {})
        if set(checks) != set(CHECK_FIELDS):
            raise ValueError(f"vietnamese_review_invalid_check_set:{guid}:{semantic_id}")
        checks["vietnamese_semantics"] = "repair"
        checks["simplicity"] = "repair"
        audit_sense["checks"] = checks
        audit_sense["decision"] = "repair_proposed"
        audit_sense["confidence"] = audit_sense.get("confidence") or "high"
        audit_sense["review_reason"] = review["reason"]
        audit_sense["reviewer"] = review["reviewer"]
        audit_sense["reviewed_at"] = review["reviewed_at"]
        audit_sense["approval"] = "approved"

        if not any(
            item.get("disposition") == "pending"
            for item in audit_card.get("source_coverage") or []
        ):
            audit_card.setdefault("coverage", {})["status"] = "repair_proposed"

    audit_errors = validate_audit_rows(
        updated,
        card_registry_rows,
        require_complete=require_complete,
    )
    if audit_errors:
        raise ValueError(
            "Vietnamese review produced an invalid semantic ledger:\n"
            + "\n".join(audit_errors)
        )
    return updated


def serialize_vietnamese_audit(summary: dict, candidates: list[dict]) -> str:
    """Serialize one summary row followed by deterministic candidate rows."""
    return _serialize_rows([summary, *candidates])


def serialize_vietnamese_review(review_summary: dict, review_rows: list[dict]) -> str:
    """Serialize the canonical review scaffold or completed review."""
    return _serialize_rows([review_summary, *review_rows])


def _serialize_rows(rows: list[dict]) -> str:
    return "".join(
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    )


def render_vietnamese_audit_markdown(
    summary: dict,
    candidates: list[dict],
) -> str:
    """Render a compact reviewer-facing report without changing its evidence."""
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# Vietnamese Gloss Naturalness Audit",
        "",
        f"- Cards scanned: {summary['cards_scanned']}",
        f"- Senses scanned: {summary['senses_scanned']}",
        f"- Candidate senses: {summary['candidate_senses']}",
        (
            "- Selection: all promoted senses"
            if summary.get("scope") == "all"
            else f"- Selection: at least {summary['min_tokens']} whitespace tokens"
        ),
        "",
        "| Word | CEFR | POS | Sense | Tokens | Flags | Promoted VI | Audit current VI | Audit proposed VI | English | Cambridge evidence |",
        "|---|---|---|---:|---:|---|---|---|---|---|---|",
    ]
    for row in candidates:
        cambridge = "; ".join(
            part
            for part in (
                row["cambridge_url"],
                row["cambridge_summary"],
                row["translation_provenance"],
            )
            if part
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    cell(row["word"]),
                    cell(row["cefr"]),
                    cell(row["pos"]),
                    cell(row["order"]),
                    cell(row["vi_token_count"]),
                    cell(", ".join(row["heuristic_flags"])),
                    cell(row["definition_vi"]),
                    cell(row["audit_current_vi"]),
                    cell(row["audit_proposed_vi"]),
                    cell(row["definition_en"]),
                    cell(cambridge),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
