"""Report-only audit for verbose or structurally compressed definitions."""
from __future__ import annotations

import copy
import json
import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from src.deck_builder.semantic_registry import validate_semantic_registry_rows
from src.deck_builder.canonical_io import (
    canonical_json_bytes,
    canonical_text_sha256,
    load_jsonl_document,
)


DEFINITION_AUDIT_SCHEMA_VERSION = 3
LONG_DEFINITION_LENGTH = 80
CONNECTOR_DEFINITION_LENGTH = 60
DEFAULT_MIN_TOKENS = 12
_AND_RE = re.compile(r"\band\b", re.IGNORECASE)
DEFINITION_REVIEW_DECISIONS = {
    "pending",
    "keep_explanatory",
    "rewrite_required",
    "split_required",
    "uncertain",
}
DEFINITION_REVIEW_APPROVALS = {"", "approved", "rejected"}
_GENERIC_REVIEW_TEXT = {
    "approved",
    "definition is fine",
    "good as is",
    "keep as is",
    "looks good",
    "loses detail",
    "loses meaning",
    "necessary detail",
    "needs context",
    "too vague",
}
_SUSPICIOUS_TOKEN_RE = re.compile(
    r"(?<!\w)(?:[0-9a-f]{8,}|(?=[a-z0-9_-]{8,}(?!\w))"
    r"(?=[a-z0-9_-]*[a-z])(?=[a-z0-9_-]*\d)[a-z0-9_-]+)(?!\w)",
    re.IGNORECASE,
)


def sha256_bytes(payload: bytes) -> str:
    return canonical_text_sha256(payload)


def load_jsonl_bytes(path: Path) -> tuple[bytes, list[dict]]:
    return load_jsonl_document(path)


def _json_digest(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _candidate_id(row: dict) -> str:
    return f"{row.get('guid') or ''}::{row.get('semantic_sense_id') or ''}"


def _candidate_fingerprint(row: dict) -> str:
    """Bind review to learner content and evidence, not report suggestions."""
    return _json_digest({
        "candidate_id": row.get("candidate_id"),
        "guid": row.get("guid"),
        "word": row.get("word"),
        "cefr": row.get("cefr"),
        "list": row.get("list"),
        "variant": row.get("variant"),
        "pos": row.get("pos"),
        "semantic_sense_id": row.get("semantic_sense_id"),
        "order": row.get("order"),
        "source_fingerprint": row.get("source_fingerprint"),
        "current": {
            key: (row.get("current") or {}).get(key)
            for key in ("definition_en", "definition_vi", "examples")
        },
        "triggers": row.get("triggers"),
        "evidence": row.get("evidence"),
    })


def _candidate_set_digest(candidates: list[dict]) -> str:
    return _json_digest([
        [row.get("candidate_id"), row.get("candidate_fingerprint")]
        for row in candidates
    ])


def _render_definition(senses: Iterable[dict]) -> str:
    return "|".join(
        f"{sense['definition_en']} ({sense['definition_vi']})"
        for sense in senses
    )


def _render_example(senses: Iterable[dict]) -> str:
    return "|".join(
        "<br><br>".join(sense.get("examples") or [])
        for sense in senses
    )


def _candidate_triggers(
    definition: str,
    *,
    min_tokens: int = DEFAULT_MIN_TOKENS,
) -> list[str]:
    triggers: list[str] = []
    length = len(definition)
    if len(definition.split()) >= min_tokens:
        triggers.append("token_threshold")
    if ";" in definition:
        triggers.append("semicolon")
    if length >= LONG_DEFINITION_LENGTH:
        triggers.append("long_definition")
    if length >= CONNECTOR_DEFINITION_LENGTH and _AND_RE.search(definition):
        triggers.append("and_connector")
    if length >= CONNECTOR_DEFINITION_LENGTH and "/" in definition:
        triggers.append("slash_connector")
    return triggers


def _source_sort_key(source: dict) -> tuple[int, int, str]:
    source_rank = 0 if source.get("source") == "Oxford" else 1
    number = str(source.get("sensenum_local") or "")
    sense_rank = int(number) if number.isdigit() else 10**6
    return source_rank, sense_rank, str(source.get("source_sense_id") or "")


def _relevant_evidence(audit_row: dict, semantic_sense: dict) -> tuple[list[dict], list[dict]]:
    relevant_ids = set(semantic_sense.get("source_sense_ids") or [])
    source_rows = [
        source
        for source in audit_row.get("source_senses") or []
        if source.get("source_sense_id") in relevant_ids
    ]
    source_rows.sort(key=_source_sort_key)
    evidence = [
        {
            "source_sense_id": source.get("source_sense_id") or "",
            "source": source.get("source") or "",
            "pos": source.get("pos") or "",
            "cefr_original": source.get("cefr_original"),
            "cefr_resolved": source.get("cefr_resolved") or "",
            "sensenum_local": source.get("sensenum_local"),
            "definition": source.get("definition") or "",
            "examples": list(source.get("examples") or []),
            "source_files": list(source.get("source_files") or []),
        }
        for source in source_rows
    ]
    coverage_by_id = {
        item.get("source_sense_id"): item
        for item in audit_row.get("source_coverage") or []
    }
    coverage = []
    for source in source_rows:
        source_id = source.get("source_sense_id") or ""
        item = coverage_by_id.get(source_id) or {}
        coverage.append({
            "source_sense_id": source_id,
            "disposition": item.get("disposition") or "",
            "target_semantic_sense_ids": list(
                item.get("target_semantic_sense_ids") or []
            ),
            "reason": item.get("reason") or "",
        })
    return evidence, coverage


def _distinct_oxford_senses(evidence: list[dict], cefr: str) -> list[dict]:
    rows = [
        source
        for source in evidence
        if source["source"] == "Oxford"
        and source["cefr_resolved"] == cefr
        and str(source.get("sensenum_local") or "").isdigit()
    ]
    distinct: dict[tuple[str, str], dict] = {}
    for source in rows:
        key = (str(source.get("pos") or ""), str(source["sensenum_local"]))
        distinct.setdefault(key, source)
    return sorted(distinct.values(), key=_source_sort_key)


def _split_parts(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _proposal_segment(
    index: int,
    definition_en: str,
    definition_vi: str,
    examples: list[str],
    source_sense_ids: list[str],
) -> dict:
    return {
        "proposal_segment_id": f"proposal_{index}",
        "definition_en": definition_en.strip(),
        "definition_vi": definition_vi.strip(),
        "examples": [example.strip() for example in examples if example.strip()],
        "source_sense_ids": source_sense_ids,
    }


def _matching_tokens(value: str) -> set[str]:
    stopwords = {
        "a", "an", "and", "as", "be", "is", "it", "of", "or", "sb",
        "something", "somebody", "sth", "that", "the", "this", "to",
    }
    return {
        token
        for token in re.findall(r"[a-z]+", value.casefold())
        if token not in stopwords
    }


def _source_part_score(source: dict, part: str) -> tuple[int, float]:
    source_text = str(source.get("definition") or "")
    overlap = len(_matching_tokens(source_text) & _matching_tokens(part))
    similarity = SequenceMatcher(
        None,
        source_text.casefold(),
        part.casefold(),
    ).ratio()
    return overlap, similarity


def _assign_sources_to_parts(sources: list[dict], parts: list[str]) -> list[list[dict]]:
    """Map Oxford senses to clauses without relying on POS-local sense numbers."""
    groups: list[list[dict]] = [[] for _ in parts]
    remaining = list(sources)

    # Give every clause its strongest distinct source before grouping related
    # source senses into the same displayed clause.
    for part_index, part in enumerate(parts):
        if not remaining:
            break
        best = max(
            range(len(remaining)),
            key=lambda index: (
                _source_part_score(remaining[index], part),
                -index,
            ),
        )
        groups[part_index].append(remaining.pop(best))

    for source in remaining:
        best_part = max(
            range(len(parts)),
            key=lambda index: (_source_part_score(source, parts[index]), -index),
        )
        groups[best_part].append(source)
    for group in groups:
        group.sort(key=_source_sort_key)
    return groups


def _normalise_example(value: str) -> str:
    return " ".join(value.casefold().split())


def _examples_for_source_groups(
    examples: list[str],
    source_groups: list[list[dict]],
) -> list[list[str]]:
    source_examples = [
        {
            _normalise_example(example)
            for source in group
            for example in source.get("examples") or []
        }
        for group in source_groups
    ]
    grouped: list[list[str]] = [[] for _ in source_groups]
    unmatched: list[str] = []
    for example in examples:
        normalised = _normalise_example(example)
        matches = [
            index for index, values in enumerate(source_examples)
            if normalised in values
        ]
        if len(matches) == 1:
            grouped[matches[0]].append(example)
        else:
            unmatched.append(example)
    for index, example in enumerate(unmatched):
        grouped[min(index, len(grouped) - 1)].append(example)
    return grouped


def _uphold_proposal(evidence: list[dict]) -> tuple[str, list[dict], str]:
    oxford = _distinct_oxford_senses(evidence, "C1")
    first_ids = [oxford[0]["source_sense_id"]] if oxford else []
    second_ids = [oxford[1]["source_sense_id"]] if len(oxford) > 1 else []
    segments = [
        _proposal_segment(
            1,
            "keep a law/principle",
            "duy trì luật/nguyên tắc",
            ["We have a duty to uphold the law."],
            first_ids,
        ),
        _proposal_segment(
            2,
            "confirm a decision",
            "xác nhận quyết định đúng",
            ["The court upheld the conviction."],
            second_ids,
        ),
    ]
    reason = (
        "Oxford C1 records maintaining a law or principle and confirming a "
        "previous legal decision as separate numbered senses, each supported "
        "by a different example."
    )
    return "split", segments, reason


def _draft_proposal(
    card: dict,
    sense: dict,
    evidence: list[dict],
) -> tuple[str, list[dict], str]:
    if card["word"] == "uphold" and card["cefr"] == "C1":
        return _uphold_proposal(evidence)

    definition_en = sense["definition_en"]
    definition_vi = sense["definition_vi"]
    examples = list(sense.get("examples") or [])
    oxford = _distinct_oxford_senses(evidence, card["cefr"])
    en_parts = _split_parts(definition_en)
    vi_parts = _split_parts(definition_vi)

    can_split = (
        len(oxford) >= 2
        and len(en_parts) >= 2
        and len(en_parts) == len(vi_parts)
        and len(en_parts) <= len(oxford)
    )
    if can_split:
        source_groups = _assign_sources_to_parts(oxford, en_parts)
        example_groups = _examples_for_source_groups(examples, source_groups)
        segments = []
        for index, (en_part, vi_part) in enumerate(zip(en_parts, vi_parts), 1):
            sources = source_groups[index - 1]
            segment_examples = example_groups[index - 1]
            if not segment_examples and sources and sources[0].get("examples"):
                segment_examples = [sources[0]["examples"][0]]
            segments.append(_proposal_segment(
                index,
                en_part,
                vi_part,
                segment_examples,
                [source["source_sense_id"] for source in sources],
            ))
        reason = (
            "The current semantic sense combines multiple same-CEFR Oxford "
            "numbered senses, and both English and Vietnamese definitions have "
            "matching clause boundaries suitable for separate examples."
        )
        return "split", segments, reason

    segment = _proposal_segment(
        1,
        definition_en,
        definition_vi,
        examples,
        list(sense.get("source_sense_ids") or []),
    )
    if len(oxford) >= 2:
        reason = (
            "Multiple Oxford senses map here, but the current bilingual text "
            "does not provide safe aligned clause boundaries. Keep one sense "
            "in this draft and require manual semantic review before splitting."
        )
        return "uncertain", [segment], reason
    reason = (
        "The connector or length is review-worthy, but the mapped Oxford "
        "evidence does not establish multiple independent same-CEFR senses."
    )
    return "keep_common", [segment], reason


def _render_proposal(segments: list[dict]) -> dict:
    return {
        "segments": segments,
        "definition": _render_definition(segments),
        "example": _render_example(segments),
    }


def _validate_input_parity(
    registry_rows: list[dict],
    notes_rows: list[dict],
    audit_rows: list[dict],
    card_registry_rows: list[dict],
    audit_sha256: str,
) -> list[str]:
    errors = validate_semantic_registry_rows(registry_rows, card_registry_rows)
    registry_by_guid = {row.get("guid"): row for row in registry_rows}
    notes_by_guid = {row.get("guid"): row for row in notes_rows}
    audit_by_guid = {row.get("guid"): row for row in audit_rows}
    if len(notes_by_guid) != len(notes_rows):
        errors.append("duplicate_build_note_guid")
    if len(audit_by_guid) != len(audit_rows):
        errors.append("duplicate_audit_guid")
    if set(registry_by_guid) != set(notes_by_guid):
        errors.append("semantic_registry_build_guid_mismatch")
    if set(registry_by_guid) != set(audit_by_guid):
        errors.append("semantic_registry_audit_guid_mismatch")
    registry_hashes = {row.get("audit_sha256") for row in registry_rows}
    if registry_hashes != {audit_sha256}:
        errors.append("semantic_registry_stale_audit_sha256")

    for guid in sorted(set(registry_by_guid) & set(notes_by_guid) & set(audit_by_guid)):
        registry = registry_by_guid[guid]
        note = notes_by_guid[guid]
        audit = audit_by_guid[guid]
        for field in ("word", "cefr", "pos"):
            if registry.get(field) != note.get(field):
                errors.append(f"build_identity_mismatch:{guid}:{field}")
            if registry.get(field) != audit.get(field):
                errors.append(f"audit_identity_mismatch:{guid}:{field}")
        if registry.get("source_fingerprint") != audit.get("source_fingerprint"):
            errors.append(f"source_fingerprint_mismatch:{guid}")
        rendered_definition = _render_definition(registry.get("senses") or [])
        if note.get("definition") != rendered_definition:
            errors.append(f"build_definition_mismatch:{guid}")
        definition_segments = (note.get("definition") or "").split("|")
        example_segments = (note.get("example") or "").split("|")
        if len(definition_segments) != len(example_segments):
            errors.append(f"build_definition_example_alignment:{guid}")
    return errors


def build_definition_audit(
    registry_rows: list[dict],
    notes_rows: list[dict],
    audit_rows: list[dict],
    card_registry_rows: list[dict],
    *,
    input_hashes: dict[str, str],
    min_tokens: int = DEFAULT_MIN_TOKENS,
) -> tuple[dict, list[dict]]:
    """Build deterministic report records without modifying canonical inputs."""
    if not isinstance(min_tokens, int) or isinstance(min_tokens, bool) or min_tokens < 1:
        raise ValueError("definition_audit_invalid_min_tokens")
    errors = _validate_input_parity(
        registry_rows,
        notes_rows,
        audit_rows,
        card_registry_rows,
        input_hashes["bilingual_semantic_audit"],
    )
    if errors:
        raise ValueError("Definition audit input validation failed:\n" + "\n".join(errors))

    notes_by_guid = {row["guid"]: row for row in notes_rows}
    audit_by_guid = {row["guid"]: row for row in audit_rows}
    candidates: list[dict] = []
    senses_scanned = 0
    for card in registry_rows:
        audit_row = audit_by_guid[card["guid"]]
        for sense in card.get("senses") or []:
            senses_scanned += 1
            triggers = _candidate_triggers(
                sense["definition_en"],
                min_tokens=min_tokens,
            )
            if not triggers:
                continue
            evidence, coverage = _relevant_evidence(audit_row, sense)
            recommendation, segments, reason = _draft_proposal(card, sense, evidence)
            proposal = _render_proposal(segments)
            candidate = {
                "record_type": "candidate",
                "schema_version": DEFINITION_AUDIT_SCHEMA_VERSION,
                "candidate_id": f"{card['guid']}::{sense['semantic_sense_id']}",
                "guid": card["guid"],
                "word": card["word"],
                "cefr": card["cefr"],
                "list": card["list"],
                "variant": card.get("variant") or "",
                "pos": card["pos"],
                "semantic_sense_id": sense["semantic_sense_id"],
                "order": sense["order"],
                "source_fingerprint": card["source_fingerprint"],
                "current": {
                    "definition_en": sense["definition_en"],
                    "definition_vi": sense["definition_vi"],
                    "examples": list(sense.get("examples") or []),
                    "rendered_definition": _render_definition([sense]),
                    "rendered_example": _render_example([sense]),
                    "build_definition": notes_by_guid[card["guid"]]["definition"],
                    "build_example": notes_by_guid[card["guid"]]["example"],
                    "definition_length": len(sense["definition_en"]),
                    "definition_token_count": len(sense["definition_en"].split()),
                },
                "triggers": triggers,
                "recommendation": recommendation,
                "proposal": proposal,
                "semantic_reason": reason,
                "evidence": {
                    "source_senses": evidence,
                    "source_coverage": coverage,
                    "audit_decision": next(
                        (
                            item.get("decision") or ""
                            for item in audit_row.get("semantic_senses") or []
                            if item.get("semantic_sense_id") == sense["semantic_sense_id"]
                        ),
                        "",
                    ),
                },
                "review": {
                    "status": "pending",
                    "approval": "",
                    "reviewer": "",
                    "reviewed_at": "",
                },
            }
            candidate["candidate_fingerprint"] = _candidate_fingerprint(candidate)
            candidates.append(candidate)

    candidates.sort(key=lambda row: (
        row["word"].casefold(),
        row["cefr"],
        row["list"],
        row["variant"],
        row["guid"],
        row["order"],
    ))
    summary = {
        "record_type": "summary",
        "schema_version": DEFINITION_AUDIT_SCHEMA_VERSION,
        "inputs": dict(sorted(input_hashes.items())),
        "thresholds": {
            "long_definition_length": LONG_DEFINITION_LENGTH,
            "connector_definition_length": CONNECTOR_DEFINITION_LENGTH,
            "minimum_definition_tokens": min_tokens,
            "connectors": [";", "and", "/"],
        },
        "cards_scanned": len(registry_rows),
        "senses_scanned": senses_scanned,
        "candidate_cards": len({row["guid"] for row in candidates}),
        "candidate_senses": len(candidates),
        "candidate_set_sha256": _candidate_set_digest(candidates),
        "recommendations": {
            value: sum(row["recommendation"] == value for row in candidates)
            for value in ("keep_common", "split", "uncertain")
        },
    }
    report_errors = validate_definition_audit(summary, candidates)
    if report_errors:
        raise ValueError("Definition audit report validation failed:\n" + "\n".join(report_errors))
    return summary, candidates


def apply_definition_review_overrides(
    summary: dict,
    candidates: list[dict],
    review_summary: dict,
    review_rows: list[dict],
    *,
    review_sha256: str,
) -> tuple[dict, list[dict]]:
    """Apply report-only human proposals while rejecting stale review files."""
    if review_summary.get("record_type") != "review_summary":
        raise ValueError("definition_review_missing_summary")
    if review_summary.get("schema_version") != DEFINITION_AUDIT_SCHEMA_VERSION:
        raise ValueError("definition_review_schema_version")
    if review_summary.get("inputs") != summary.get("inputs"):
        raise ValueError("definition_review_stale_inputs")

    reviewed = copy.deepcopy(candidates)
    by_identity = {
        (row["guid"], row["semantic_sense_id"]): row
        for row in reviewed
    }
    seen: set[tuple[str, str]] = set()
    for override in review_rows:
        identity = (
            str(override.get("guid") or ""),
            str(override.get("semantic_sense_id") or ""),
        )
        if identity in seen:
            raise ValueError(f"definition_review_duplicate:{identity}")
        seen.add(identity)
        row = by_identity.get(identity)
        if row is None:
            raise ValueError(f"definition_review_unknown_candidate:{identity}")
        if override.get("source_fingerprint") != row["source_fingerprint"]:
            raise ValueError(f"definition_review_stale_source:{identity}")
        recommendation = override.get("recommendation")
        if recommendation not in {"keep_common", "split"}:
            raise ValueError(f"definition_review_invalid_recommendation:{identity}")
        reason = str(override.get("semantic_reason") or "").strip()
        if not reason:
            raise ValueError(f"definition_review_missing_reason:{identity}")

        if override.get("use_current") is True:
            if recommendation != "keep_common":
                raise ValueError(f"definition_review_use_current_requires_keep:{identity}")
            segments = [_proposal_segment(
                1,
                row["current"]["definition_en"],
                row["current"]["definition_vi"],
                row["current"]["examples"],
                [
                    source["source_sense_id"]
                    for source in row["evidence"]["source_senses"]
                ],
            )]
        else:
            segments = copy.deepcopy(override.get("segments") or [])
            if recommendation == "split" and len(segments) < 2:
                raise ValueError(f"definition_review_split_requires_segments:{identity}")
        row["recommendation"] = recommendation
        row["proposal"] = _render_proposal(segments)
        row["semantic_reason"] = reason
        row["review"] = {
            "status": "proposed",
            "approval": "",
            "reviewer": str(override.get("reviewer") or "definition-audit"),
            "reviewed_at": str(override.get("reviewed_at") or ""),
        }

    result_summary = copy.deepcopy(summary)
    result_summary["recommendations"] = {
        value: sum(row["recommendation"] == value for row in reviewed)
        for value in ("keep_common", "split", "uncertain")
    }
    result_summary["review_overrides"] = {
        "count": len(review_rows),
        "sha256": review_sha256,
    }
    errors = validate_definition_audit(result_summary, reviewed)
    if errors:
        raise ValueError("Definition review validation failed:\n" + "\n".join(errors))
    return result_summary, reviewed


def validate_definition_audit(summary: dict, candidates: list[dict]) -> list[str]:
    errors: list[str] = []
    if summary.get("record_type") != "summary":
        errors.append("invalid_summary_record_type")
    if summary.get("schema_version") != DEFINITION_AUDIT_SCHEMA_VERSION:
        errors.append("invalid_summary_schema_version")
    seen: set[str] = set()
    for row in candidates:
        identity = (str(row.get("guid") or ""), str(row.get("semantic_sense_id") or ""))
        candidate_id = str(row.get("candidate_id") or "")
        if not all(identity) or not candidate_id or candidate_id in seen:
            errors.append(f"duplicate_or_empty_candidate:{identity}")
        seen.add(candidate_id)
        if row.get("record_type") != "candidate":
            errors.append(f"invalid_candidate_record_type:{identity}")
        if row.get("schema_version") != DEFINITION_AUDIT_SCHEMA_VERSION:
            errors.append(f"invalid_candidate_schema_version:{identity}")
        if candidate_id != _candidate_id(row):
            errors.append(f"candidate_id_mismatch:{identity}")
        if row.get("candidate_fingerprint") != _candidate_fingerprint(row):
            errors.append(f"candidate_fingerprint_mismatch:{identity}")
        if row.get("recommendation") not in {"keep_common", "split", "uncertain"}:
            errors.append(f"invalid_recommendation:{identity}")
        proposal = row.get("proposal") or {}
        segments = proposal.get("segments") or []
        if not segments:
            errors.append(f"missing_proposal_segments:{identity}")
            continue
        if row.get("recommendation") == "split" and len(segments) < 2:
            errors.append(f"split_requires_multiple_segments:{identity}")
        if row.get("recommendation") == "keep_common" and len(segments) != 1:
            errors.append(f"keep_common_requires_one_segment:{identity}")
        if not str(row.get("semantic_reason") or "").strip():
            errors.append(f"missing_semantic_reason:{identity}")
        if proposal.get("definition") != _render_definition(segments):
            errors.append(f"proposal_definition_render_mismatch:{identity}")
        if proposal.get("example") != _render_example(segments):
            errors.append(f"proposal_example_render_mismatch:{identity}")
        if len(proposal.get("definition", "").split("|")) != len(
            proposal.get("example", "").split("|")
        ):
            errors.append(f"proposal_alignment_mismatch:{identity}")
        evidence_ids = {
            item.get("source_sense_id")
            for item in (row.get("evidence") or {}).get("source_senses") or []
        }
        for segment in segments:
            if not segment.get("definition_en") or not segment.get("definition_vi"):
                errors.append(f"empty_proposal_definition:{identity}")
            unknown = set(segment.get("source_sense_ids") or []) - evidence_ids
            if unknown:
                errors.append(f"unknown_proposal_source_ids:{identity}:{sorted(unknown)}")
    if summary.get("candidate_senses") != len(candidates):
        errors.append("candidate_sense_count_mismatch")
    if summary.get("candidate_cards") != len({row.get("guid") for row in candidates}):
        errors.append("candidate_card_count_mismatch")
    expected_order = sorted(candidates, key=lambda row: (
        str(row.get("word") or "").casefold(),
        str(row.get("cefr") or ""),
        str(row.get("list") or ""),
        str(row.get("variant") or ""),
        str(row.get("guid") or ""),
        row.get("order"),
    ))
    if candidates != expected_order:
        errors.append("candidate_order_mismatch")
    if summary.get("candidate_set_sha256") != _candidate_set_digest(candidates):
        errors.append("candidate_set_sha256_mismatch")
    expected_recommendations = {
        value: sum(row.get("recommendation") == value for row in candidates)
        for value in ("keep_common", "split", "uncertain")
    }
    if summary.get("recommendations") != expected_recommendations:
        errors.append("recommendation_count_mismatch")
    return errors


def serialize_definition_audit(summary: dict, candidates: list[dict]) -> str:
    rows = [summary, *candidates]
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def scaffold_definition_review(
    summary: dict,
    candidates: list[dict],
    *,
    existing_review_rows: list[dict] | None = None,
) -> tuple[dict, list[dict]]:
    """Create the exact-coverage canonical Definition EN review ledger."""
    errors = validate_definition_audit(summary, candidates)
    if errors:
        raise ValueError("Invalid Definition audit:\n" + "\n".join(errors))
    review_summary = {
        "record_type": "review_summary",
        "schema_version": DEFINITION_AUDIT_SCHEMA_VERSION,
        "candidate_count": len(candidates),
        "candidate_set_sha256": summary["candidate_set_sha256"],
    }
    existing_by_id: dict[str, dict] = {}
    duplicate_ids: set[str] = set()
    for review in existing_review_rows or []:
        candidate_id = str(review.get("candidate_id") or "")
        if not candidate_id or candidate_id in existing_by_id:
            duplicate_ids.add(candidate_id)
            continue
        existing_by_id[candidate_id] = review

    rows: list[dict] = []
    for candidate in candidates:
        existing = existing_by_id.get(candidate["candidate_id"])
        if (
            candidate["candidate_id"] not in duplicate_ids
            and existing is not None
            and existing.get("record_type") == "review"
            and existing.get("schema_version") == DEFINITION_AUDIT_SCHEMA_VERSION
            and existing.get("candidate_fingerprint")
            == candidate["candidate_fingerprint"]
            and existing.get("guid") == candidate["guid"]
            and existing.get("semantic_sense_id")
            == candidate["semantic_sense_id"]
            and existing.get("expected_definition_en")
            == candidate["current"]["definition_en"]
        ):
            rows.append(copy.deepcopy(existing))
            continue
        rows.append({
            "record_type": "review",
            "schema_version": DEFINITION_AUDIT_SCHEMA_VERSION,
            "candidate_id": candidate["candidate_id"],
            "candidate_fingerprint": candidate["candidate_fingerprint"],
            "guid": candidate["guid"],
            "semantic_sense_id": candidate["semantic_sense_id"],
            "word": candidate["word"],
            "order": candidate["order"],
            "expected_definition_en": candidate["current"]["definition_en"],
            "decision": "pending",
            "shorter_en_considered": "",
            "preserved_distinction": "",
            "reason": "",
            "semantic_evidence": "",
            "reviewer": "",
            "reviewed_at": "",
            "approval": "",
        })
    return review_summary, rows


def _normalise_review_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _lexical_review_text(value: object) -> str:
    lexical = re.sub(
        r"[^\w\s]",
        " ",
        _normalise_review_text(value),
        flags=re.UNICODE,
    )
    return re.sub(r"\s+", " ", lexical).strip()


def _connector_count(value: object) -> int:
    text = str(value or "")
    return text.count(";") + text.count("/") + len(_AND_RE.findall(text))


def _is_conciser_definition(current: str, alternative: str) -> bool:
    current = current.strip()
    alternative = alternative.strip()
    if not current or not alternative:
        return False
    if _lexical_review_text(current) == _lexical_review_text(alternative):
        return False
    return (
        len(alternative) < len(current)
        or _connector_count(alternative) < _connector_count(current)
    )


def _is_specific_distinction(value: object) -> bool:
    normalized = _normalise_review_text(value)
    lexical = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    lexical = re.sub(r"\s+", " ", lexical).strip()
    if lexical in _GENERIC_REVIEW_TEXT:
        return False
    if re.fullmatch(
        r"(?:it|this|the shorter (?:wording|definition)) "
        r"(?:loses|omits) (?:detail|meaning|context|nuance)s?",
        lexical,
    ):
        return False
    return len(re.findall(r"\w+", lexical, flags=re.UNICODE)) >= 3


def _contains_exact_review_text(container: object, required: object) -> bool:
    needle = _normalise_review_text(required)
    return bool(needle and needle in _normalise_review_text(container))


def _definition_grounding_values(candidate: dict) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for value in (candidate.get("current") or {}).get("examples") or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)
    for source in (candidate.get("evidence") or {}).get("source_senses") or []:
        for value in [source.get("definition"), *(source.get("examples") or [])]:
            text = str(value or "").strip()
            if text and text not in seen:
                seen.add(text)
                values.append(text)
    return values


def _definition_review_residual(
    value: object,
    candidate: dict,
    review: dict,
    *,
    strip_review_values: bool = False,
) -> str:
    normalized = _normalise_review_text(value)
    dynamic = [
        candidate.get("candidate_id"),
        candidate.get("guid"),
        candidate.get("word"),
        candidate.get("semantic_sense_id"),
        candidate.get("source_fingerprint"),
        (candidate.get("current") or {}).get("definition_en"),
        *_definition_grounding_values(candidate),
    ]
    for source in (candidate.get("evidence") or {}).get("source_senses") or []:
        dynamic.append(source.get("source_sense_id"))
    if strip_review_values:
        dynamic.extend(
            [
                review.get("shorter_en_considered"),
                review.get("preserved_distinction"),
            ]
        )
    for item in sorted(
        {_normalise_review_text(item) for item in dynamic if str(item or "").strip()},
        key=len,
        reverse=True,
    ):
        if len(item) >= 2:
            normalized = normalized.replace(item, " ")
    for label in (
        "current en",
        "final en",
        "shorter en considered",
        "shorter en",
        "preserved distinction",
        "source definition",
        "learner example",
        "example",
    ):
        normalized = normalized.replace(label, " ")
    return _lexical_review_text(normalized)


def _has_suspicious_review_token(
    value: object,
    candidate: dict,
    review: dict,
    *,
    strip_review_values: bool = False,
) -> bool:
    return bool(
        _SUSPICIOUS_TOKEN_RE.search(
            _definition_review_residual(
                value,
                candidate,
                review,
                strip_review_values=strip_review_values,
            )
        )
    )


def validate_definition_review(
    summary: dict,
    candidates: list[dict],
    review_summary: dict,
    review_rows: list[dict],
) -> list[str]:
    """Validate exact coverage, immutable context, and row-specific evidence."""
    errors = validate_definition_audit(summary, candidates)
    if review_summary.get("record_type") != "review_summary":
        errors.append("definition_review_missing_summary")
    if review_summary.get("schema_version") != DEFINITION_AUDIT_SCHEMA_VERSION:
        errors.append("definition_review_invalid_schema_version")
    if review_summary.get("candidate_count") != len(candidates):
        errors.append("definition_review_candidate_count_mismatch")
    if review_summary.get("candidate_set_sha256") != summary.get(
        "candidate_set_sha256"
    ):
        errors.append("definition_review_stale_candidate_set")

    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    seen: set[str] = set()
    seen_reasons: set[str] = set()
    seen_evidence: set[str] = set()
    seen_distinctions: set[str] = set()
    for review in review_rows:
        candidate_id = str(review.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen:
            errors.append(f"definition_review_duplicate_or_empty:{candidate_id}")
            continue
        seen.add(candidate_id)
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None:
            errors.append(f"definition_review_extra_candidate:{candidate_id}")
            continue
        identity = f"{candidate['guid']}:{candidate['semantic_sense_id']}"
        if review.get("record_type") != "review":
            errors.append(f"definition_review_invalid_record_type:{identity}")
        if review.get("schema_version") != DEFINITION_AUDIT_SCHEMA_VERSION:
            errors.append(f"definition_review_invalid_row_schema_version:{identity}")
        if review.get("candidate_fingerprint") != candidate["candidate_fingerprint"]:
            errors.append(f"definition_review_stale_candidate:{identity}")
        if (
            review.get("guid") != candidate["guid"]
            or review.get("semantic_sense_id") != candidate["semantic_sense_id"]
        ):
            errors.append(f"definition_review_identity_mismatch:{identity}")
        if review.get("word") != candidate["word"] or review.get("order") != candidate[
            "order"
        ]:
            errors.append(f"definition_review_display_identity_mismatch:{identity}")
        expected = str(candidate["current"]["definition_en"])
        if review.get("expected_definition_en") != expected:
            errors.append(f"definition_review_stale_definition_en:{identity}")

        decision = review.get("decision")
        if decision not in DEFINITION_REVIEW_DECISIONS:
            errors.append(f"definition_review_invalid_decision:{identity}:{decision}")
            continue
        approval = review.get("approval", "")
        if approval not in DEFINITION_REVIEW_APPROVALS:
            errors.append(f"definition_review_invalid_approval:{identity}:{approval}")
        alternative = str(review.get("shorter_en_considered") or "").strip()
        distinction = str(review.get("preserved_distinction") or "").strip()
        evidence = str(review.get("semantic_evidence") or "").strip()
        reason = str(review.get("reason") or "").strip()
        reviewer = str(review.get("reviewer") or "").strip()
        reviewed_at = str(review.get("reviewed_at") or "").strip()

        if decision == "keep_explanatory":
            if not alternative:
                errors.append(f"definition_review_missing_shorter_en:{identity}")
            elif not _is_conciser_definition(expected, alternative):
                errors.append(f"definition_review_non_conciser_alternative:{identity}")
            if len(_lexical_review_text(alternative).replace(" ", "")) < 3:
                errors.append(
                    f"definition_review_non_substantive_alternative:{identity}"
                )
            if not distinction:
                errors.append(f"definition_review_missing_preserved_distinction:{identity}")
            elif not _is_specific_distinction(distinction):
                errors.append(f"definition_review_generic_preserved_distinction:{identity}")
            residual_distinction = _definition_review_residual(
                distinction,
                candidate,
                review,
            )
            if residual_distinction in seen_distinctions:
                errors.append(f"definition_review_duplicate_preserved_distinction:{identity}")
            if residual_distinction:
                seen_distinctions.add(residual_distinction)
            if _has_suspicious_review_token(distinction, candidate, review):
                errors.append(f"definition_review_suspicious_token:{identity}")
            normalized_reason = _normalise_review_text(reason)
            if (
                not reason
                or normalized_reason in _GENERIC_REVIEW_TEXT
                or len(re.findall(r"\w+", normalized_reason, flags=re.UNICODE)) < 4
            ):
                errors.append(f"definition_review_generic_reason:{identity}")
            residual_reason = _definition_review_residual(
                reason,
                candidate,
                review,
                strip_review_values=True,
            )
            if residual_reason in seen_reasons:
                errors.append(f"definition_review_duplicate_reason:{identity}")
            if residual_reason:
                seen_reasons.add(residual_reason)
            if _has_suspicious_review_token(
                reason,
                candidate,
                review,
                strip_review_values=True,
            ):
                errors.append(f"definition_review_suspicious_token:{identity}")
            if len(re.findall(r"\w", reviewer, flags=re.UNICODE)) < 3:
                errors.append(f"definition_review_invalid_reviewer:{identity}")
            try:
                date.fromisoformat(reviewed_at)
            except ValueError:
                errors.append(f"definition_review_invalid_reviewed_at:{identity}")
            if not evidence:
                errors.append(f"definition_review_missing_semantic_evidence:{identity}")
            else:
                normalized_evidence = _normalise_review_text(evidence)
                if normalized_evidence in _GENERIC_REVIEW_TEXT:
                    errors.append(
                        f"definition_review_generic_semantic_evidence:{identity}"
                    )
                residual_evidence = _definition_review_residual(
                    evidence,
                    candidate,
                    review,
                    strip_review_values=True,
                )
                if residual_evidence in seen_evidence:
                    errors.append(f"definition_review_duplicate_semantic_evidence:{identity}")
                if residual_evidence:
                    seen_evidence.add(residual_evidence)
                if _has_suspicious_review_token(
                    evidence,
                    candidate,
                    review,
                    strip_review_values=True,
                ):
                    errors.append(f"definition_review_suspicious_token:{identity}")
                for label, required in (
                    ("current_en", expected),
                    ("shorter_en", alternative),
                    ("distinction", distinction),
                ):
                    if required and _normalise_review_text(required) not in normalized_evidence:
                        errors.append(
                            f"definition_review_evidence_missing_{label}:{identity}"
                        )
                grounding = _definition_grounding_values(candidate)
                if not grounding or not any(
                    _contains_exact_review_text(evidence, value)
                    for value in grounding
                ):
                    errors.append(f"definition_review_missing_grounding:{identity}")
        elif any((alternative, distinction, evidence)):
            errors.append(f"definition_review_unexpected_keep_evidence:{identity}")

    for candidate_id in sorted(set(candidates_by_id) - seen):
        errors.append(f"definition_review_missing_candidate:{candidate_id}")
    return errors


def validate_definition_review_for_promotion(
    summary: dict,
    candidates: list[dict],
    review_summary: dict,
    review_rows: list[dict],
) -> list[str]:
    """Fail closed until every current candidate is an approved justified keep."""
    errors = validate_definition_review(
        summary,
        candidates,
        review_summary,
        review_rows,
    )
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    seen: set[str] = set()
    for review in review_rows:
        candidate_id = str(review.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen or candidate_id not in candidates_by_id:
            continue
        seen.add(candidate_id)
        candidate = candidates_by_id[candidate_id]
        identity = f"{candidate['guid']}:{candidate['semantic_sense_id']}"
        decision = review.get("decision")
        if decision != "keep_explanatory":
            errors.append(f"definition_promotion_open_decision:{identity}:{decision}")
        if review.get("approval") != "approved":
            errors.append(f"definition_promotion_not_approved:{identity}")
        for field in ("reason", "reviewer", "reviewed_at"):
            if not str(review.get(field) or "").strip():
                errors.append(f"definition_promotion_missing_{field}:{identity}")
    return errors


def serialize_definition_review(review_summary: dict, review_rows: list[dict]) -> str:
    """Serialize the canonical Definition EN review deterministically."""
    ordered_rows = sorted(
        review_rows,
        key=lambda row: str(row.get("candidate_id") or ""),
    )
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in [review_summary, *ordered_rows]
    )


def render_definition_audit_markdown(summary: dict, candidates: list[dict]) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# Definition Sense Audit",
        "",
        f"- Cards scanned: {summary['cards_scanned']}",
        f"- Senses scanned: {summary['senses_scanned']}",
        f"- Candidate cards: {summary['candidate_cards']}",
        f"- Candidate senses: {summary['candidate_senses']}",
        f"- Recommendations: {json.dumps(summary['recommendations'], sort_keys=True)}",
        "",
        "| Word | CEFR | POS | GUID | Sense | Chars | Tokens | Trigger | Proposal | Current definition | Proposed definition | Proposed example | Semantic reason | Source evidence |",
        "|---|---|---|---|---:|---:|---:|---|---|---|---|---|---|---|",
    ]
    for row in candidates:
        evidence = "; ".join(
            f"{source['source_sense_id']} "
            f"[{source['source']} {source['pos']}#{source['sensenum_local']}]: "
            f"{source['definition']}"
            for source in row["evidence"]["source_senses"]
        )
        lines.append(
            "| "
            + " | ".join([
                cell(row["word"]),
                cell(row["cefr"]),
                cell(row["pos"]),
                cell(row["guid"]),
                cell(row["order"]),
                cell(row["current"]["definition_length"]),
                cell(row["current"]["definition_token_count"]),
                cell(", ".join(row["triggers"])),
                cell(row["recommendation"]),
                cell(row["current"]["rendered_definition"]),
                cell(row["proposal"]["definition"]),
                cell(row["proposal"]["example"]),
                cell(row["semantic_reason"]),
                cell(evidence),
            ])
            + " |"
        )
    return "\n".join(lines) + "\n"
