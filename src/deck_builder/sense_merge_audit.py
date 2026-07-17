"""Report-only audit for potentially redundant semantic senses."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date
from typing import Iterable


SCHEMA_VERSION = 1
AUDIT_KIND = "semantic_sense_merge_audit"
REVIEW_KIND = "semantic_sense_merge_review"
HISTORICAL_GROUPING_STATUS = "sense_grouping_review_20260711"
REVIEW_DECISIONS = {
    "merge_candidate",
    "keep_separate",
    "keep_separate_reword",
    "uncertain",
}
CONFIDENCE_VALUES = {"high", "medium", "low"}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _normalized_vi(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _vi_overlap_groups(senses: list[dict]) -> tuple[list[list[str]], list[dict]]:
    """Return connected sense groups whose VI strings have prefix containment."""
    adjacency: dict[str, set[str]] = {
        sense["semantic_sense_id"]: set() for sense in senses
    }
    pairs: list[dict] = []
    for index, left in enumerate(senses):
        left_vi = _normalized_vi(left.get("definition_vi"))
        for right in senses[index + 1 :]:
            right_vi = _normalized_vi(right.get("definition_vi"))
            overlaps = bool(
                left_vi
                and right_vi
                and (
                    (len(left_vi) >= 4 and right_vi.startswith(left_vi))
                    or (len(right_vi) >= 4 and left_vi.startswith(right_vi))
                )
            )
            if not overlaps:
                continue
            left_id = left["semantic_sense_id"]
            right_id = right["semantic_sense_id"]
            adjacency[left_id].add(right_id)
            adjacency[right_id].add(left_id)
            pairs.append({
                "left_semantic_sense_id": left_id,
                "right_semantic_sense_id": right_id,
                "left_vi": left.get("definition_vi") or "",
                "right_vi": right.get("definition_vi") or "",
            })

    groups: list[list[str]] = []
    seen: set[str] = set()
    order = {
        sense["semantic_sense_id"]: int(sense.get("order") or 0)
        for sense in senses
    }
    for semantic_id in adjacency:
        if semantic_id in seen or not adjacency[semantic_id]:
            continue
        stack = [semantic_id]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        seen.update(component)
        groups.append(sorted(component, key=lambda value: (order[value], value)))
    groups.sort(key=lambda group: (order[group[0]], group))
    return groups, pairs


def _legacy_chunk_count(value: object) -> int:
    text = str(value or "")
    return len(text.split("|")) if text else 0


def _historical_evidence(
    semantic_rows: list[dict],
    deck_audit_rows: list[dict],
    override_rows: list[dict],
) -> dict[str, list[dict]]:
    evidence: dict[str, list[dict]] = {}
    by_identity: dict[tuple[str, str], list[dict]] = {}
    by_guid = {row.get("guid"): row for row in semantic_rows}
    for row in semantic_rows:
        by_identity.setdefault((row.get("word") or "", row.get("cefr") or ""), []).append(row)

    for owner in deck_audit_rows:
        if owner.get("fix_status") != HISTORICAL_GROUPING_STATUS:
            continue
        legacy_count = _legacy_chunk_count(owner.get("gloss_after"))
        for semantic in by_identity.get((owner.get("word") or "", owner.get("cefr") or ""), []):
            if len(semantic.get("senses") or []) <= legacy_count:
                continue
            evidence.setdefault(semantic["guid"], []).append({
                "owner": "deck_audit",
                "legacy_sense_count": legacy_count,
                "legacy_definition": owner.get("gloss_after") or "",
            })

    for owner in override_rows:
        if not (
            owner.get("fix_status") == HISTORICAL_GROUPING_STATUS
            or owner.get("sense_grouping_status") == HISTORICAL_GROUPING_STATUS
        ):
            continue
        semantic = by_guid.get(owner.get("guid"))
        legacy_count = _legacy_chunk_count(owner.get("Definition"))
        if not semantic or len(semantic.get("senses") or []) <= legacy_count:
            continue
        evidence.setdefault(semantic["guid"], []).append({
            "owner": "non_oxford_non_c2_overrides",
            "legacy_sense_count": legacy_count,
            "legacy_definition": owner.get("Definition") or "",
        })
    return evidence


def _source_evidence(audit_row: dict) -> dict[str, dict]:
    return {
        source["source_sense_id"]: {
            key: source.get(key)
            for key in (
                "source_sense_id",
                "source",
                "pos",
                "cefr_original",
                "cefr_resolved",
                "sensenum_local",
                "definition",
                "examples",
                "register_tags",
                "domain",
            )
        }
        for source in audit_row.get("source_senses") or []
    }


def _candidate(
    semantic: dict,
    audit_row: dict,
    overlap_groups: list[list[str]],
    overlap_pairs: list[dict],
    historical: list[dict],
) -> dict:
    source_by_id = _source_evidence(audit_row)
    senses = []
    for sense in sorted(semantic.get("senses") or [], key=lambda row: row.get("order") or 0):
        source_ids = list(sense.get("source_sense_ids") or [])
        missing_source_ids = [
            source_id for source_id in source_ids if source_id not in source_by_id
        ]
        if missing_source_ids:
            raise ValueError(
                "sense_merge_missing_source_evidence:"
                f"{semantic['guid']}:{','.join(missing_source_ids)}"
            )
        senses.append({
            "semantic_sense_id": sense["semantic_sense_id"],
            "order": sense.get("order"),
            "definition_en": sense.get("definition_en") or "",
            "definition_vi": sense.get("definition_vi") or "",
            "examples": list(sense.get("examples") or []),
            "source_sense_ids": source_ids,
            "source_evidence": [source_by_id[source_id] for source_id in source_ids],
        })
    triggers = []
    if overlap_groups:
        triggers.append("vi_prefix_overlap")
    if historical:
        triggers.append("historical_grouping_reexpanded")
    immutable = {
        "guid": semantic["guid"],
        "word": semantic.get("word") or "",
        "cefr": semantic.get("cefr") or "",
        "list": semantic.get("list") or "",
        "variant": semantic.get("variant") or "",
        "pos": semantic.get("pos") or "",
        "triggers": triggers,
        "vi_overlap_groups": overlap_groups,
        "vi_overlap_pairs": overlap_pairs,
        "historical_evidence": historical,
        "senses": senses,
        "source_coverage": audit_row.get("source_coverage") or [],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "semantic_sense_merge_candidate",
        "candidate_id": semantic["guid"],
        "candidate_fingerprint": sha256_bytes(_canonical_bytes(immutable)),
        **immutable,
    }


def build_sense_merge_audit(
    semantic_rows: list[dict],
    audit_rows: list[dict],
    deck_audit_rows: list[dict],
    override_rows: list[dict],
    *,
    input_hashes: dict[str, str],
) -> tuple[dict, list[dict]]:
    """Build the focused deterministic candidate queue without reviewing it."""
    audit_by_guid = {row.get("guid"): row for row in audit_rows}
    historical = _historical_evidence(semantic_rows, deck_audit_rows, override_rows)
    candidates = []
    for semantic in semantic_rows:
        senses = semantic.get("senses") or []
        if len(senses) < 2:
            continue
        overlap_groups, overlap_pairs = _vi_overlap_groups(senses)
        historical_rows = historical.get(semantic.get("guid"), [])
        if not overlap_groups and not historical_rows:
            continue
        audit_row = audit_by_guid.get(semantic.get("guid"))
        if audit_row is None:
            raise ValueError(f"sense_merge_missing_audit_row:{semantic.get('guid')}")
        candidates.append(_candidate(
            semantic,
            audit_row,
            overlap_groups,
            overlap_pairs,
            historical_rows,
        ))
    candidates.sort(key=lambda row: (
        row["word"].lower(), row["cefr"], row["list"], row["variant"], row["guid"]
    ))
    trigger_counts = Counter(
        trigger for candidate in candidates for trigger in candidate["triggers"]
    )
    candidate_set_sha256 = sha256_bytes(_canonical_bytes([
        [row["candidate_id"], row["candidate_fingerprint"]] for row in candidates
    ]))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "kind": AUDIT_KIND,
        "cards_scanned": len(semantic_rows),
        "senses_scanned": sum(len(row.get("senses") or []) for row in semantic_rows),
        "candidate_cards": len(candidates),
        "trigger_counts": dict(sorted(trigger_counts.items())),
        "candidate_set_sha256": candidate_set_sha256,
        "input_hashes": dict(sorted(input_hashes.items())),
    }
    return summary, candidates


def scaffold_sense_merge_review(summary: dict, candidates: list[dict]) -> tuple[dict, list[dict]]:
    review_summary = {
        "schema_version": SCHEMA_VERSION,
        "kind": REVIEW_KIND,
        "candidate_set_sha256": summary["candidate_set_sha256"],
        "candidate_cards": len(candidates),
        "input_hashes": dict(sorted(summary.get("input_hashes", {}).items())),
    }
    rows = [{
        "candidate_id": candidate["candidate_id"],
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "word": candidate["word"],
        "decision": "",
        "confidence": "",
        "reason": "",
        "merge_groups": [],
        "vi_rewrites": [],
    } for candidate in candidates]
    return review_summary, rows


def _ordered_examples(senses: list[dict]) -> list[str]:
    examples: list[str] = []
    seen: set[str] = set()
    for sense in sorted(senses, key=lambda row: row.get("order") or 0):
        for example in sense.get("examples") or []:
            key = re.sub(r"\s+", " ", example).strip().lower()
            if key and key not in seen:
                seen.add(key)
                examples.append(example)
    return examples


def _merge_preview(candidate: dict, group: dict) -> dict:
    by_id = {sense["semantic_sense_id"]: sense for sense in candidate["senses"]}
    ids = list(group["semantic_sense_ids"])
    grouped = [by_id[semantic_id] for semantic_id in ids]
    retained = min(grouped, key=lambda row: (row.get("order") or 0, row["semantic_sense_id"]))
    retained_id = retained["semantic_sense_id"]
    removed_ids = [semantic_id for semantic_id in ids if semantic_id != retained_id]
    remaps = []
    group_ids = set(ids)
    for coverage in candidate.get("source_coverage") or []:
        old_targets = list(coverage.get("target_semantic_sense_ids") or [])
        if not group_ids.intersection(old_targets):
            continue
        new_targets = []
        for target in old_targets:
            replacement = retained_id if target in group_ids else target
            if replacement not in new_targets:
                new_targets.append(replacement)
        if new_targets == old_targets:
            continue
        remaps.append({
            "source_sense_id": coverage.get("source_sense_id") or "",
            "old_target_semantic_sense_ids": old_targets,
            "new_target_semantic_sense_ids": new_targets,
        })
    return {
        "retained_semantic_sense_id": retained_id,
        "removed_semantic_sense_ids": removed_ids,
        "definition_en": group["definition_en"],
        "definition_vi": group["definition_vi"],
        "examples": _ordered_examples(grouped),
        "source_coverage_remaps": remaps,
    }


def apply_sense_merge_reviews(
    summary: dict,
    candidates: list[dict],
    review_summary: dict,
    review_rows: list[dict],
) -> tuple[dict, list[dict]]:
    """Validate complete fingerprint-bound reviews and attach report previews."""
    if review_summary.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("sense_merge_review_invalid_schema_version")
    if review_summary.get("kind") != REVIEW_KIND:
        raise ValueError("sense_merge_review_invalid_kind")
    if review_summary.get("candidate_set_sha256") != summary.get("candidate_set_sha256"):
        raise ValueError("sense_merge_review_stale_candidate_set")
    if review_summary.get("candidate_cards") != len(candidates):
        raise ValueError("sense_merge_review_candidate_count_mismatch")
    if review_summary.get("input_hashes") != summary.get("input_hashes"):
        raise ValueError("sense_merge_review_stale_inputs")
    expected = {row["candidate_id"]: row for row in candidates}
    supplied: dict[str, dict] = {}
    for review in review_rows:
        candidate_id = review.get("candidate_id") or ""
        if not candidate_id or candidate_id in supplied:
            raise ValueError(f"sense_merge_review_duplicate_or_empty:{candidate_id}")
        candidate = expected.get(candidate_id)
        if candidate is None:
            raise ValueError(f"sense_merge_review_unknown_candidate:{candidate_id}")
        if review.get("candidate_fingerprint") != candidate["candidate_fingerprint"]:
            raise ValueError(f"sense_merge_review_stale_candidate:{candidate_id}")
        if review.get("word") != candidate["word"]:
            raise ValueError(f"sense_merge_review_word_mismatch:{candidate_id}")
        decision = review.get("decision") or ""
        if decision not in REVIEW_DECISIONS:
            raise ValueError(f"sense_merge_review_invalid_decision:{candidate_id}:{decision}")
        if review.get("confidence") not in CONFIDENCE_VALUES:
            raise ValueError(f"sense_merge_review_invalid_confidence:{candidate_id}")
        if not str(review.get("reason") or "").strip():
            raise ValueError(f"sense_merge_review_missing_reason:{candidate_id}")
        by_id = {sense["semantic_sense_id"]: sense for sense in candidate["senses"]}
        groups = list(review.get("merge_groups") or [])
        rewrites = list(review.get("vi_rewrites") or [])
        if decision == "merge_candidate" and not groups:
            raise ValueError(f"sense_merge_review_missing_merge_group:{candidate_id}")
        if decision != "merge_candidate" and groups:
            raise ValueError(f"sense_merge_review_unexpected_merge_group:{candidate_id}")
        if decision == "keep_separate_reword" and not rewrites:
            raise ValueError(f"sense_merge_review_missing_vi_rewrite:{candidate_id}")
        if decision != "keep_separate_reword" and rewrites:
            raise ValueError(f"sense_merge_review_unexpected_vi_rewrite:{candidate_id}")
        used_ids: set[str] = set()
        previews = []
        for group in groups:
            ids = list(group.get("semantic_sense_ids") or [])
            if len(ids) < 2 or len(ids) != len(set(ids)) or set(ids) - set(by_id):
                raise ValueError(f"sense_merge_review_invalid_group:{candidate_id}")
            if used_ids.intersection(ids):
                raise ValueError(f"sense_merge_review_overlapping_groups:{candidate_id}")
            if not group.get("definition_en") or not group.get("definition_vi"):
                raise ValueError(f"sense_merge_review_empty_proposal:{candidate_id}")
            used_ids.update(ids)
            previews.append(_merge_preview(candidate, group))
        rewrite_ids: set[str] = set()
        for rewrite in rewrites:
            semantic_id = rewrite.get("semantic_sense_id") or ""
            if semantic_id not in by_id or semantic_id in rewrite_ids or not rewrite.get("definition_vi"):
                raise ValueError(f"sense_merge_review_invalid_vi_rewrite:{candidate_id}")
            rewrite_ids.add(semantic_id)
        removed_count = sum(
            len(preview["removed_semantic_sense_ids"])
            for preview in previews
        )
        supplied[candidate_id] = {
            **review,
            "merge_previews": previews,
            "projected_sense_count": len(by_id) - removed_count,
        }
    missing = set(expected) - set(supplied)
    if missing:
        raise ValueError(f"sense_merge_review_missing_candidates:{','.join(sorted(missing))}")

    reviewed = [{**candidate, "review": supplied[candidate["candidate_id"]]} for candidate in candidates]
    decision_counts = Counter(row["review"]["decision"] for row in reviewed)
    projected_removed_senses = sum(
        len(preview["removed_semantic_sense_ids"])
        for row in reviewed
        for preview in row["review"].get("merge_previews") or []
    )
    reviewed_summary = {
        **summary,
        "reviewed": True,
        "decision_counts": dict(sorted(decision_counts.items())),
        "projected_removed_senses": projected_removed_senses,
        "projected_senses_after_approval": (
            summary["senses_scanned"] - projected_removed_senses
        ),
    }
    return reviewed_summary, reviewed


def build_sense_merge_review_bundle(
    reviewed_candidates: list[dict],
    *,
    reviewer: str,
    reviewed_at: str,
) -> list[dict]:
    """Convert approved merge review outcomes into canonical audit mutations."""
    if not reviewer.strip():
        raise ValueError("sense_merge_bundle_missing_reviewer")
    try:
        date.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise ValueError("sense_merge_bundle_invalid_reviewed_at") from exc

    bundle: list[dict] = []
    for candidate in reviewed_candidates:
        review = candidate.get("review") or {}
        decision = review.get("decision") or ""
        sense_updates: list[dict] = []
        remove_ids: list[str] = []
        coverage_updates: list[dict] = []

        if decision == "merge_candidate":
            previews = list(review.get("merge_previews") or [])
            replacements: dict[str, str] = {}
            for preview in previews:
                retained_id = preview["retained_semantic_sense_id"]
                removed = list(preview["removed_semantic_sense_ids"])
                remove_ids.extend(removed)
                replacements.update({semantic_id: retained_id for semantic_id in removed})
                sense_updates.append({
                    "semantic_sense_id": retained_id,
                    "checks": {
                        "english_semantics": "repair",
                        "vietnamese_semantics": "repair",
                        "simplicity": "pass",
                        "example_pos_alignment": "pass",
                    },
                    "decision": "repair_proposed",
                    "proposed": {
                        "definition_en": preview["definition_en"],
                        "definition_vi": preview["definition_vi"],
                        "examples": list(preview["examples"]),
                    },
                    "confidence": review["confidence"],
                    "review_reason": f"Approved semantic sense merge: {review['reason']}",
                    "reviewer": reviewer,
                    "reviewed_at": reviewed_at,
                    "approval": "approved",
                })
            for coverage in candidate.get("source_coverage") or []:
                old_targets = list(coverage.get("target_semantic_sense_ids") or [])
                new_targets: list[str] = []
                for target in old_targets:
                    replacement = replacements.get(target, target)
                    if replacement not in new_targets:
                        new_targets.append(replacement)
                if new_targets == old_targets:
                    continue
                retained_targets = sorted({
                    replacements[target]
                    for target in old_targets
                    if target in replacements
                })
                coverage_updates.append({
                    "source_sense_id": coverage.get("source_sense_id") or "",
                    "disposition": coverage.get("disposition") or "mapped",
                    "target_semantic_sense_ids": new_targets,
                    "reason": (
                        "Remapped after approved semantic merge into "
                        + ", ".join(retained_targets)
                        + "."
                    ),
                })
        elif decision == "keep_separate_reword":
            by_id = {
                sense["semantic_sense_id"]: sense
                for sense in candidate.get("senses") or []
            }
            for rewrite in review.get("vi_rewrites") or []:
                semantic_id = rewrite["semantic_sense_id"]
                original = by_id[semantic_id]
                sense_updates.append({
                    "semantic_sense_id": semantic_id,
                    "checks": {
                        "english_semantics": "pass",
                        "vietnamese_semantics": "repair",
                        "simplicity": "pass",
                        "example_pos_alignment": "pass",
                    },
                    "decision": "repair_proposed",
                    "proposed": {
                        "definition_en": original["definition_en"],
                        "definition_vi": rewrite["definition_vi"],
                        "examples": list(original["examples"]),
                    },
                    "confidence": review["confidence"],
                    "review_reason": (
                        "Approved Vietnamese distinction rewrite: " + review["reason"]
                    ),
                    "reviewer": reviewer,
                    "reviewed_at": reviewed_at,
                    "approval": "approved",
                })
        elif decision not in {"keep_separate", "uncertain"}:
            raise ValueError(
                f"sense_merge_bundle_invalid_decision:{candidate.get('candidate_id')}:{decision}"
            )

        if sense_updates or remove_ids or coverage_updates:
            bundle.append({
                "guid": candidate["guid"],
                "remove_senses": remove_ids,
                "source_coverage": coverage_updates,
                "senses": sense_updates,
            })
    return bundle


def serialize_sense_merge_audit(summary: dict, candidates: list[dict]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in [summary, *candidates]
    )


def serialize_sense_merge_review(summary: dict, rows: list[dict]) -> str:
    return serialize_sense_merge_audit(summary, rows)


def render_sense_merge_markdown(summary: dict, candidates: list[dict]) -> str:
    def code(value: object) -> str:
        text = str(value)
        longest_run = max((len(run) for run in re.findall(r"`+", text)), default=0)
        marker = "`" * (longest_run + 1)
        padding = " " if text.startswith("`") or text.endswith("`") else ""
        return f"{marker}{padding}{text}{padding}{marker}"

    lines = [
        "# Semantic Sense Merge Audit",
        "",
        "> Report-only: no canonical semantic or Anki data was modified.",
        "",
        f"- Cards scanned: **{summary['cards_scanned']}**",
        f"- Senses scanned: **{summary['senses_scanned']}**",
        f"- Candidate cards: **{summary['candidate_cards']}**",
        f"- Candidate set SHA-256: `{summary['candidate_set_sha256']}`",
    ]
    if summary.get("reviewed"):
        lines.extend([
            f"- Decisions: `{json.dumps(summary['decision_counts'], sort_keys=True)}`",
            f"- Projected removed senses if approved: **{summary['projected_removed_senses']}**",
            f"- Projected total senses after approval: **{summary['projected_senses_after_approval']}**",
        ])
    for candidate in candidates:
        lines.extend([
            "",
            f"## {candidate['word']} — {candidate['cefr']} / {candidate['list']}",
            "",
            f"- GUID: {code(candidate['guid'])}",
            f"- Triggers: `{', '.join(candidate['triggers'])}`",
            f"- Fingerprint: `{candidate['candidate_fingerprint']}`",
            "",
            "| Order | Semantic ID | EN | VI | Examples |",
            "|---:|---|---|---|---|",
        ])
        for sense in candidate["senses"]:
            cells = [
                sense["order"],
                sense["semantic_sense_id"],
                sense["definition_en"],
                sense["definition_vi"],
                "<br>".join(sense["examples"]),
            ]
            lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in cells) + " |")
        source_rows = {}
        for sense in candidate["senses"]:
            for source in sense.get("source_evidence") or []:
                source_rows[source["source_sense_id"]] = source
        if source_rows:
            lines.extend(["", "Source evidence:"])
            for source_id, source in sorted(source_rows.items()):
                coordinate = " ".join(
                    str(value)
                    for value in (
                        source.get("source") or "",
                        source.get("pos") or "",
                        f"#{source.get('sensenum_local')}" if source.get("sensenum_local") else "",
                    )
                    if value
                )
                definition = str(source.get("definition") or "").replace("\n", " ")
                lines.append(f"- `{source_id}` [{coordinate}]: {definition}")
        review = candidate.get("review")
        if not review:
            lines.extend(["", "- Decision: `pending`"])
            continue
        lines.extend([
            "",
            f"- Decision: `{review['decision']}` (`{review['confidence']}`)",
            f"- Reason: {review['reason']}",
            f"- Projected sense count: `{review['projected_sense_count']}`",
        ])
        for preview in review.get("merge_previews") or []:
            lines.extend([
                f"- Merge `{', '.join([preview['retained_semantic_sense_id'], *preview['removed_semantic_sense_ids']])}`:",
                f"  - EN: {preview['definition_en']}",
                f"  - VI: {preview['definition_vi']}",
                f"  - Retain: `{preview['retained_semantic_sense_id']}`",
                f"  - Remove after remap: `{', '.join(preview['removed_semantic_sense_ids'])}`",
                f"  - Examples: {' / '.join(preview['examples'])}",
                f"  - Source remaps: `{len(preview['source_coverage_remaps'])}`",
            ])
        for rewrite in review.get("vi_rewrites") or []:
            lines.append(f"- Reword `{rewrite['semantic_sense_id']}` VI → {rewrite['definition_vi']}")
    return "\n".join(lines) + "\n"


def load_jsonl_records(payload: bytes) -> list[dict]:
    return [
        json.loads(line)
        for line in payload.decode("utf-8").splitlines()
        if line.strip()
    ]


def audit_input_hashes(named_payloads: Iterable[tuple[str, bytes]]) -> dict[str, str]:
    return {name: sha256_bytes(payload) for name, payload in named_payloads}
