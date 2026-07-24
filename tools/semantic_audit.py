"""Build, review, validate, and exchange the bilingual semantic audit."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.canonical_io import canonical_jsonl_bytes
from src.deck_builder.definition_audit import (
    DEFAULT_MIN_TOKENS as DEFAULT_DEFINITION_MIN_TOKENS,
    apply_definition_review_overrides,
    build_definition_audit,
    load_jsonl_bytes as load_definition_jsonl_bytes,
    render_definition_audit_markdown,
    scaffold_definition_review,
    select_definition_audit_scope,
    serialize_definition_audit,
    serialize_definition_review,
    sha256_bytes as definition_sha256_bytes,
    validate_definition_review,
    validate_definition_review_for_promotion,
)
from src.deck_builder.idiom_audit import (
    audit_summary as idiom_audit_summary,
    validate_audit_rows as validate_idiom_audit_rows,
)
from src.deck_builder.semantic_audit import (
    audit_summary,
    apply_review_bundle,
    build_audit_rows,
    export_workbook,
    import_workbook,
    load_jsonl,
    serialize_jsonl,
    validate_audit_rows,
)
from src.deck_builder.semantic_audit_manifests import (
    build_artifacts,
    sha256_bytes,
    utc_now,
    validate_artifacts,
)
from src.deck_builder.semantic_registry import (
    build_promotion_gate_candidates,
    promote_reviewed_semantics,
    serialize_semantic_registry,
    validate_semantic_registry_rows,
)
from src.deck_builder.semantic_policy import (
    validate_audit_policy,
    validate_policy_rows,
    validate_vietnamese_user_lock_evidence,
)
from src.deck_builder.sense_merge_audit import (
    apply_sense_merge_reviews,
    audit_input_hashes as sense_merge_input_hashes,
    build_sense_merge_audit,
    build_sense_merge_review_bundle,
    load_jsonl_records as load_sense_merge_jsonl_records,
    render_sense_merge_markdown,
    scaffold_sense_merge_review,
    serialize_sense_merge_audit,
    serialize_sense_merge_review,
    validate_sense_merge_review_for_promotion,
)
from src.deck_builder.vietnamese_audit import (
    DEFAULT_MIN_TOKENS as DEFAULT_VIETNAMESE_MIN_TOKENS,
    apply_vietnamese_review,
    build_vietnamese_audit,
    render_vietnamese_audit_markdown,
    scaffold_vietnamese_review,
    serialize_vietnamese_audit,
    serialize_vietnamese_review,
    validate_vietnamese_review,
    validate_vietnamese_review_for_promotion,
)


paths = ProjectPaths()
DEFAULT_AUDIT = paths.bilingual_semantic_audit
DEFAULT_IDIOM_AUDIT = paths.bilingual_idiom_audit
DEFAULT_XLSX = paths.root / "scratch" / "bilingual_semantic_audit.xlsx"
DEFAULT_MANIFEST_DIR = paths.root / "scratch" / "parallel" / "manifests"
DEFAULT_DEFINITION_AUDIT = paths.root / "scratch" / "definition_sense_audit.jsonl"
DEFAULT_DEFINITION_AUDIT_MARKDOWN = paths.root / "scratch" / "definition_sense_audit.md"
DEFAULT_VIETNAMESE_AUDIT = paths.root / "scratch" / "vietnamese_naturalness_audit.jsonl"
DEFAULT_VIETNAMESE_AUDIT_MARKDOWN = paths.root / "scratch" / "vietnamese_naturalness_audit.md"
DEFAULT_VIETNAMESE_REVIEW = paths.vietnamese_naturalness_review
DEFAULT_SEMANTIC_POLICY = paths.semantic_policy_locks
DEFAULT_DEFINITION_REVIEW = paths.definition_concision_review
DEFAULT_DEFINITION_REVIEW_MANIFEST_DIR = (
    paths.root / "scratch" / "definition_review_manifests"
)
DEFAULT_VIETNAMESE_REVIEW_MANIFEST_DIR = (
    paths.root / "scratch" / "vietnamese_review_manifests"
)
DEFAULT_CANONICAL_SENSE_MERGE_REVIEW = paths.semantic_sense_merge_review
DEFAULT_SENSE_MERGE_AUDIT = paths.root / "scratch" / "semantic_sense_merge_audit.jsonl"
DEFAULT_SENSE_MERGE_AUDIT_MARKDOWN = paths.root / "scratch" / "semantic_sense_merge_audit.md"
DEFAULT_SENSE_MERGE_REVIEW = paths.root / "scratch" / "semantic_sense_merge_review.jsonl"
PARALLEL_LOCK = paths.root / "scratch" / "parallel" / ".canonical_ledger.lock"
MAX_REVIEW_MANIFEST_ROWS = 100
DEFINITION_REVIEW_EDITABLE_FIELDS = frozenset({
    "decision",
    "shorter_en_considered",
    "preserved_distinction",
    "reason",
    "semantic_evidence",
    "reviewer",
    "reviewed_at",
    "approval",
})
VIETNAMESE_REVIEW_EDITABLE_FIELDS = frozenset({
    "decision",
    "suggested_vi",
    "proposed_vi",
    "shorter_vi_considered",
    "preserved_distinction",
    "reason",
    "reason_code",
    "semantic_evidence",
    "lock_id",
    "reviewer",
    "reviewed_at",
    "approval",
})


def _write_atomic(path: Path, text: str) -> None:
    if PARALLEL_LOCK.exists():
        raise RuntimeError(f"canonical ledger write blocked by parallel snapshot lock: {PARALLEL_LOCK}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


@contextmanager
def _parallel_snapshot_lock():
    PARALLEL_LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(PARALLEL_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"parallel snapshot lock already exists: {PARALLEL_LOCK}") from exc
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "ledger": str(DEFAULT_AUDIT)}).encode("utf-8"))
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        try:
            PARALLEL_LOCK.unlink()
        except FileNotFoundError:
            pass


def _load_audit_bytes(path: Path) -> tuple[bytes, list[dict]]:
    payload = path.read_bytes()
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    return payload, rows


def _write_manifest_outputs(output_dir: Path, outputs: dict[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        target = output_dir / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, target)


def _review_records(path: Path, *, label: str) -> tuple[dict, list[dict]]:
    records = load_jsonl(path)
    if not records:
        raise ValueError(f"{label}_empty")
    summary = records[0]
    if not isinstance(summary, dict) or any(
        not isinstance(row, dict) for row in records[1:]
    ):
        raise ValueError(f"{label}_invalid_record_type")
    if summary.get("record_type") != "review_summary":
        raise ValueError(f"{label}_missing_summary")
    return summary, records[1:]


def _merge_review_patch(
    canonical_summary: dict,
    canonical_rows: list[dict],
    patch_summary: dict,
    patch_rows: list[dict],
    *,
    label: str,
    editable_fields: frozenset[str],
) -> list[dict]:
    """Merge a small review patch without allowing context fields to drift."""
    if patch_summary != canonical_summary:
        raise ValueError(f"{label}_patch_summary_mismatch")

    canonical_by_id: dict[str, dict] = {}
    for row in canonical_rows:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in canonical_by_id:
            raise ValueError(f"{label}_canonical_duplicate_or_empty:{candidate_id}")
        canonical_by_id[candidate_id] = row

    patch_ids: set[str] = set()
    merged_by_id = copy.deepcopy(canonical_by_id)
    for patch in patch_rows:
        candidate_id = str(patch.get("candidate_id") or "")
        if not candidate_id or candidate_id in patch_ids:
            raise ValueError(f"{label}_patch_duplicate_or_empty:{candidate_id}")
        patch_ids.add(candidate_id)
        existing = canonical_by_id.get(candidate_id)
        if existing is None:
            raise ValueError(f"{label}_patch_unknown_candidate:{candidate_id}")
        immutable_fields = (set(existing) | set(patch)) - editable_fields
        changed = sorted(
            field
            for field in immutable_fields
            if patch.get(field) != existing.get(field)
        )
        if changed:
            raise ValueError(
                f"{label}_patch_immutable_change:{candidate_id}:{','.join(changed)}"
            )
        merged = copy.deepcopy(existing)
        for field in editable_fields:
            if field in patch:
                merged[field] = copy.deepcopy(patch[field])
        merged_by_id[candidate_id] = merged

    return [merged_by_id[candidate_id] for candidate_id in sorted(merged_by_id)]


def _validate_review_patch_size(patch_rows: list[dict], *, label: str) -> None:
    if not 1 <= len(patch_rows) <= MAX_REVIEW_MANIFEST_ROWS:
        raise ValueError(
            f"{label}_patch_rows_must_be_1_to_{MAX_REVIEW_MANIFEST_ROWS}"
        )


def _review_manifest_payloads(
    summary: dict,
    review_rows: list[dict],
    *,
    max_rows: int,
    resolved,
) -> tuple[dict[str, bytes], int]:
    if (
        not isinstance(max_rows, int)
        or isinstance(max_rows, bool)
        or not 1 <= max_rows <= MAX_REVIEW_MANIFEST_ROWS
    ):
        raise ValueError(
            f"review_manifest_max_rows_must_be_1_to_{MAX_REVIEW_MANIFEST_ROWS}"
        )
    unresolved = sorted(
        (copy.deepcopy(row) for row in review_rows if not resolved(row)),
        key=lambda row: (
            str(row.get("word") or "").casefold(),
            str(row.get("guid") or ""),
            str(row.get("candidate_id") or ""),
        ),
    )
    groups: list[list[dict]] = []
    for row in unresolved:
        guid = str(row.get("guid") or "")
        if groups and str(groups[-1][0].get("guid") or "") == guid:
            groups[-1].append(row)
        else:
            groups.append([row])

    chunks: list[list[dict]] = []
    current: list[dict] = []
    for group in groups:
        if len(group) > max_rows:
            if current:
                chunks.append(current)
                current = []
            chunks.extend(
                group[offset:offset + max_rows]
                for offset in range(0, len(group), max_rows)
            )
            continue
        if current and len(current) + len(group) > max_rows:
            chunks.append(current)
            current = []
        current.extend(group)
    if current:
        chunks.append(current)

    outputs: dict[str, bytes] = {}
    for index, chunk in enumerate(chunks, start=1):
        name = f"manifest_{index:03d}.jsonl"
        outputs[name] = canonical_jsonl_bytes([summary, *chunk])
    return outputs, len(unresolved)


def _write_review_manifest_outputs(
    output_dir: Path,
    outputs: dict[str, bytes],
    *,
    replace: bool,
) -> None:
    existing = sorted(output_dir.glob("manifest_*.jsonl")) if output_dir.exists() else []
    if existing and not replace:
        raise ValueError(f"review manifest output exists: {output_dir}; use --replace")
    _write_manifest_outputs(output_dir, outputs)
    expected = set(outputs)
    for path in existing:
        if path.name not in expected:
            path.unlink()


def _write_report_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _reject_canonical_report_output(path: Path) -> None:
    target = path.resolve()
    forbidden = (
        (paths.root / "data" / "review").resolve(),
        (paths.root / "data" / "curated").resolve(),
    )
    if any(target == root or target.is_relative_to(root) for root in forbidden):
        raise ValueError(
            f"report-only output must stay outside canonical data directories: {target}"
        )


def _semantic_rows_from_complete_audit(audit_rows: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for card in audit_rows:
        senses: list[dict] = []
        for sense in card.get("semantic_senses") or []:
            if sense.get("decision") == "pass":
                content = sense.get("current") or {}
            elif (
                sense.get("decision") == "repair_proposed"
                and sense.get("approval") == "approved"
            ):
                content = sense.get("proposed") or {}
            else:
                raise ValueError(
                    "vietnamese_audit_incomplete_semantic_sense:"
                    f"{card.get('guid')}:{sense.get('semantic_sense_id')}"
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
                "translation_provenance": (
                    cambridge.get("translation_provenance") or ""
                ),
            })
        rows.append({
            **{
                field: card.get(field) or ""
                for field in ("guid", "word", "cefr", "list", "variant", "pos")
            },
            "source_fingerprint": card.get("source_fingerprint") or "",
            "senses": senses,
        })
    return rows


def _load_vietnamese_audit_inputs(
    *,
    semantic_registry: Path,
    audit: Path,
    card_registry: Path,
) -> tuple[list[dict], list[dict], list[dict], dict[str, str], bytes]:
    semantic_bytes, semantic_rows = _load_audit_bytes(semantic_registry)
    audit_bytes, audit_rows = _load_audit_bytes(audit)
    card_registry_bytes, card_registry_rows = _load_audit_bytes(card_registry)

    audit_errors = validate_audit_rows(
        audit_rows,
        card_registry_rows,
        require_complete=True,
    )
    if audit_errors:
        raise ValueError(
            "Vietnamese audit requires a complete bilingual semantic audit:\n"
            + "\n".join(audit_errors[:100])
        )

    audit_sha256 = sha256_bytes(audit_bytes)
    registry_is_current = bool(semantic_rows) and all(
        row.get("schema_version") == 4
        and row.get("audit_sha256") == audit_sha256
        for row in semantic_rows
    )
    if not registry_is_current:
        semantic_rows = _semantic_rows_from_complete_audit(audit_rows)
        semantic_bytes = canonical_jsonl_bytes(semantic_rows)

    input_hashes = {
        "bilingual_semantic_audit": audit_sha256,
        "card_registry": sha256_bytes(card_registry_bytes),
        "semantic_registry": sha256_bytes(semantic_bytes),
    }
    return (
        semantic_rows,
        audit_rows,
        card_registry_rows,
        input_hashes,
        audit_bytes,
    )


def _reuse_unchanged_source_coverage(existing: dict, fresh: dict) -> None:
    """Carry coverage only for uniquely identical source-sense payloads."""
    existing_sources = {
        sense.get("source_sense_id"): sense
        for sense in existing.get("source_senses") or []
    }
    fresh_sources = {
        sense.get("source_sense_id"): sense
        for sense in fresh.get("source_senses") or []
    }
    existing_coverage = {
        item.get("source_sense_id"): item
        for item in existing.get("source_coverage") or []
    }

    def payload_without_id(source: dict) -> str:
        return json.dumps(
            {
                key: value
                for key, value in source.items()
                if key != "source_sense_id"
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    existing_ids_by_payload: dict[str, list[str]] = {}
    for source_id, source in existing_sources.items():
        existing_ids_by_payload.setdefault(
            payload_without_id(source), []
        ).append(source_id)

    def reused_coverage(item: dict) -> dict:
        source_id = item.get("source_sense_id")
        source = fresh_sources.get(source_id)
        if (
            source_id in existing_coverage
            and source_id in existing_sources
            and existing_sources[source_id] == source
        ):
            return copy.deepcopy(existing_coverage[source_id])
        matching_ids = existing_ids_by_payload.get(
            payload_without_id(source or {}), []
        )
        if len(matching_ids) != 1:
            return copy.deepcopy(item)
        old_source_id = matching_ids[0]
        old_coverage = existing_coverage.get(old_source_id)
        if old_coverage is None:
            return copy.deepcopy(item)
        reused = copy.deepcopy(old_coverage)
        reused["source_sense_id"] = source_id
        return reused

    fresh["source_coverage"] = [
        reused_coverage(item)
        for item in fresh.get("source_coverage") or []
    ]
    semantic_by_id = {
        sense.get("semantic_sense_id"): sense
        for sense in fresh.get("semantic_senses") or []
    }
    for sense in semantic_by_id.values():
        sense["source_sense_ids"] = []
    for coverage in fresh["source_coverage"]:
        if coverage.get("disposition") != "mapped":
            continue
        for target in coverage.get("target_semantic_sense_ids") or []:
            if target in semantic_by_id:
                semantic_by_id[target]["source_sense_ids"].append(
                    coverage["source_sense_id"]
                )
    for sense in semantic_by_id.values():
        sense["source_sense_ids"].sort()

    decisions = {sense.get("decision") for sense in semantic_by_id.values()}
    if decisions:
        if any(
            item.get("disposition") == "pending"
            for item in fresh["source_coverage"]
        ):
            status = "pending"
        elif "uncertain" in decisions:
            status = "uncertain"
        elif "pending" in decisions:
            status = "pending"
        elif "repair_proposed" in decisions:
            status = "repair_proposed"
        else:
            status = "pass"
        existing_coverage_summary = existing.get("coverage") or {}
        fresh["coverage"]["status"] = status
        fresh["coverage"]["reason"] = (
            str(existing_coverage_summary.get("reason") or "")
            if status == existing_coverage_summary.get("status")
            else ""
        )


def _scaffold(args) -> int:
    cards = load_jsonl(args.notes)
    registry = load_jsonl(args.registry)
    oxford = load_jsonl(args.oxford)
    cambridge = load_jsonl(args.cambridge)
    rows = build_audit_rows(cards, registry, oxford, cambridge)
    existing_path = args.existing_audit or (args.audit if args.audit.is_file() else None)
    if existing_path is not None and existing_path.is_file():
        existing_by_guid = {
            row.get("guid"): row for row in load_jsonl(existing_path)
            if isinstance(row, dict) and row.get("guid")
        }
        immutable_fields = (
            "schema_version", "guid", "word", "cefr", "list", "variant", "pos",
        )
        reused_rows = []

        def effective_matches_fresh(effective: dict, fresh: dict) -> bool:
            if any(
                effective.get(field) != fresh.get(field)
                for field in ("definition_en", "definition_vi")
            ):
                return False
            effective_examples = effective.get("examples") or []
            fresh_examples = fresh.get("examples") or []
            if len(effective_examples) != len(fresh_examples):
                return False
            return all(
                expected == actual
                or expected == re.sub(r"\s+\([^()]*\)", "", actual).strip()
                for expected, actual in zip(effective_examples, fresh_examples)
            )

        for row in rows:
            existing = existing_by_guid.get(row["guid"])
            if existing is None or not all(
                existing.get(field) == row.get(field) for field in immutable_fields
            ):
                reused_rows.append(row)
                continue
            existing_effective = []
            existing_semantic = sorted(
                existing.get("semantic_senses") or [], key=lambda item: item.get("order", 0)
            )
            fresh_semantic = sorted(
                row.get("semantic_senses") or [], key=lambda item: item.get("order", 0)
            )
            for sense in existing_semantic:
                proposed = sense.get("proposed") or {}
                current = sense.get("current") or {}
                existing_effective.append(
                    proposed if sense.get("decision") == "repair_proposed" else current
                )
            fresh_current = [
                sense.get("current") or {}
                for sense in fresh_semantic
            ]
            semantic_aligned = len(existing_effective) == len(fresh_current) and all(
                effective_matches_fresh(effective, fresh)
                for effective, fresh in zip(existing_effective, fresh_current)
            )
            if existing.get("current") != row.get("current") and not semantic_aligned:
                reused_rows.append(row)
                continue
            existing_sources = {
                sense.get("source_sense_id"): sense
                for sense in existing.get("source_senses") or []
            }
            fresh_sources = {
                sense.get("source_sense_id"): sense
                for sense in row.get("source_senses") or []
            }
            if existing_sources != fresh_sources:
                if not semantic_aligned:
                    reused_rows.append(row)
                    continue
                migrated = copy.deepcopy(row)
                for old_sense, new_sense, effective in zip(
                    existing_semantic, migrated["semantic_senses"], existing_effective
                ):
                    fresh_order = new_sense["order"]
                    new_sense.clear()
                    new_sense.update(copy.deepcopy(old_sense))
                    new_sense["semantic_sense_id"] = old_sense["semantic_sense_id"]
                    new_sense["order"] = fresh_order
                    new_sense["current"] = copy.deepcopy(effective)
                _reuse_unchanged_source_coverage(existing, migrated)
                reused_rows.append(migrated)
                continue
            reused = copy.deepcopy(existing)
            reused["current"] = copy.deepcopy(row["current"])
            reused["source_fingerprint"] = row["source_fingerprint"]
            reused["source_senses"] = copy.deepcopy(row["source_senses"])
            reused["coverage"]["candidate_source_sense_ids"] = copy.deepcopy(
                row["coverage"]["candidate_source_sense_ids"]
            )
            reused["coverage"]["expected_same_cefr_source_sense_ids"] = copy.deepcopy(
                row["coverage"]["expected_same_cefr_source_sense_ids"]
            )
            reused_rows.append(reused)
        rows = reused_rows
    errors = validate_audit_rows(rows, registry)
    if errors:
        print("Scaffold validation failed:\n" + "\n".join(errors[:30]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(rows))
    print(json.dumps(audit_summary(rows), ensure_ascii=False, sort_keys=True))
    return 0


def _load_complete_vietnamese_review(
    path: Path,
    audit_rows: list[dict],
) -> tuple[bytes, list[dict], list[str]]:
    review_bytes, review_records = _load_audit_bytes(path)
    if not review_records:
        raise ValueError("vietnamese_review_empty")
    if any(not isinstance(record, dict) for record in review_records):
        raise ValueError("vietnamese_review_invalid_record_type")
    errors = validate_vietnamese_review_for_promotion(
        audit_rows,
        review_records[0],
        review_records[1:],
    )
    return review_bytes, review_records, errors


def _load_gate_document(
    path: Path,
    label: str,
    *,
    require_nonempty: bool,
) -> tuple[bytes, list[dict]]:
    if not path.is_file():
        display_label = label.replace("_", " ").capitalize()
        raise ValueError(f"{display_label} not found: {path}")
    payload, rows = _load_audit_bytes(path)
    if require_nonempty and not rows:
        raise ValueError(f"{label}_empty:{path}")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{label}_invalid_record_type:{path}")
    return payload, rows


def _load_promotion_documents(
    args, *, include_gate_reviews: bool = True
) -> dict[str, object]:
    named_paths = {
        "audit": args.audit,
        "card_registry": args.registry,
        "idiom_audit": args.idiom_audit,
        "vietnamese_review": args.vietnamese_review,
        "semantic_policy": args.semantic_policy,
        "deck_audit": args.deck_audit,
        "overrides": args.overrides,
    }
    if include_gate_reviews:
        named_paths.update({
            "definition_review": args.definition_review,
            "sense_merge_review": args.sense_merge_review,
        })
    documents: dict[str, object] = {}
    # Alternate scratch documents are useful for isolated fixtures, but no
    # caller may overwrite or validate canonical production state while
    # bypassing the explicit user wording locks.
    canonical_targets = {
        DEFAULT_AUDIT.resolve(),
        paths.card_registry.resolve(),
        paths.semantic_registry.resolve(),
    }
    command_paths = {
        args.audit.resolve(),
        args.registry.resolve(),
    }
    output_path = getattr(args, "output", None)
    if output_path is not None:
        command_paths.add(output_path.resolve())
    documents["require_user_exact_vi_locks"] = bool(
        canonical_targets.intersection(command_paths)
    )
    required = {
        "audit",
        "card_registry",
        "vietnamese_review",
        "definition_review",
        "sense_merge_review",
    }
    for name, path in named_paths.items():
        payload, rows = _load_gate_document(
            path,
            name,
            require_nonempty=name in required,
        )
        documents[f"{name}_bytes"] = payload
        documents[f"{name}_rows"] = rows
    return documents


def _current_promotion_gate_candidates(args):
    """Build both review queues without depending on the prior registry."""

    documents = _load_promotion_documents(args, include_gate_reviews=False)
    audit_rows = documents["audit_rows"]
    card_registry_rows = documents["card_registry_rows"]
    idiom_rows = documents["idiom_audit_rows"]
    policy_rows = documents["semantic_policy_rows"]
    assert isinstance(audit_rows, list)
    assert isinstance(card_registry_rows, list)
    assert isinstance(idiom_rows, list)
    assert isinstance(policy_rows, list)
    errors = validate_audit_rows(audit_rows, card_registry_rows, require_complete=True)
    errors.extend(
        validate_idiom_audit_rows(
            idiom_rows,
            card_registry_rows,
            require_complete=True,
        )
    )
    errors.extend(validate_policy_rows(policy_rows))
    errors.extend(validate_audit_policy(audit_rows, policy_rows))
    vietnamese_rows = documents["vietnamese_review_rows"]
    assert isinstance(vietnamese_rows, list)
    if vietnamese_rows:
        errors.extend(
            validate_vietnamese_review_for_promotion(
                audit_rows,
                vietnamese_rows[0],
                vietnamese_rows[1:],
            )
        )
        errors.extend(
            validate_vietnamese_user_lock_evidence(
                vietnamese_rows[1:],
                policy_rows,
            )
        )
    if errors:
        raise ValueError(
            "Promotion review scaffold requires complete canonical inputs:\n"
            + "\n".join(errors[:100])
        )

    definition_summary, definition_candidates, merge_summary, merge_candidates = (
        build_promotion_gate_candidates(
            audit_rows,
            card_registry_rows,
            idiom_rows,
            documents["deck_audit_rows"],
            documents["overrides_rows"],
            audit_sha256=sha256_bytes(documents["audit_bytes"]),
            idiom_audit_sha256=sha256_bytes(documents["idiom_audit_bytes"]),
            vietnamese_review_sha256=sha256_bytes(
                documents["vietnamese_review_bytes"]
            ),
            semantic_policy_sha256=sha256_bytes(
                documents["semantic_policy_bytes"]
            ),
            deck_audit_sha256=sha256_bytes(documents["deck_audit_bytes"]),
            non_oxford_non_c2_override_sha256=sha256_bytes(
                documents["overrides_bytes"]
            ),
        )
    )
    requested_scope = getattr(args, "scope", "all")
    if requested_scope != "all":
        definition_summary, definition_candidates = select_definition_audit_scope(
            definition_summary,
            definition_candidates,
            scope=requested_scope,
        )
    return (
        documents,
        definition_summary,
        definition_candidates,
        merge_summary,
        merge_candidates,
    )


def _validate(args) -> int:
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(rows, registry, require_complete=args.require_complete)
    if args.require_complete and not errors:
        try:
            documents = _load_promotion_documents(args)
            promoted = _promote_documents(documents)
            errors.extend(validate_semantic_registry_rows(promoted, registry))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"promotion_gate:{exc}")
    print(json.dumps({**audit_summary(rows), "errors": len(errors)}, ensure_ascii=False, sort_keys=True))
    if errors:
        print("\n".join(errors[:100]), file=sys.stderr)
        return 1
    return 0


def _export_xlsx(args) -> int:
    rows = load_jsonl(args.audit)
    export_workbook(rows, args.xlsx)
    print(args.xlsx)
    return 0


def _import_xlsx(args) -> int:
    rows = load_jsonl(args.audit)
    updated = import_workbook(rows, args.xlsx)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(updated, registry)
    if errors:
        print("Workbook import validation failed:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(updated))
    print(json.dumps(audit_summary(updated), ensure_ascii=False, sort_keys=True))
    return 0


def _report(args) -> int:
    rows = load_jsonl(args.audit)
    summary = audit_summary(rows)
    lines = ["# Bilingual Semantic Audit", "", *[f"- {key}: {value}" for key, value in summary.items()]]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    else:
        print("\n".join(lines))
    return 0


def _apply_review(args) -> int:
    rows = load_jsonl(args.audit)
    decisions = load_jsonl(args.input)
    updated = apply_review_bundle(rows, decisions)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(updated, registry)
    if errors:
        print("Review bundle validation failed:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(updated))
    print(json.dumps(audit_summary(updated), ensure_ascii=False, sort_keys=True))
    return 0


def _promote_documents(documents: dict[str, object]) -> list[dict]:
    audit_rows = documents["audit_rows"]
    card_registry_rows = documents["card_registry_rows"]
    idiom_rows = documents["idiom_audit_rows"]
    vietnamese_rows = documents["vietnamese_review_rows"]
    definition_rows = documents["definition_review_rows"]
    sense_merge_rows = documents["sense_merge_review_rows"]
    return promote_reviewed_semantics(
        audit_rows,
        card_registry_rows,
        idiom_rows,
        vietnamese_rows[0],
        vietnamese_rows[1:],
        policy_rows=documents["semantic_policy_rows"],
        definition_review_summary=definition_rows[0],
        definition_review_rows=definition_rows[1:],
        sense_merge_review_summary=sense_merge_rows[0],
        sense_merge_review_rows=sense_merge_rows[1:],
        deck_audit_rows=documents["deck_audit_rows"],
        non_oxford_non_c2_override_rows=documents["overrides_rows"],
        audit_bytes=documents["audit_bytes"],
        idiom_audit_bytes=documents["idiom_audit_bytes"],
        vietnamese_review_bytes=documents["vietnamese_review_bytes"],
        policy_bytes=documents["semantic_policy_bytes"],
        definition_review_bytes=documents["definition_review_bytes"],
        sense_merge_review_bytes=documents["sense_merge_review_bytes"],
        deck_audit_bytes=documents["deck_audit_bytes"],
        non_oxford_non_c2_override_bytes=documents["overrides_bytes"],
        require_user_exact_vi_locks=bool(
            documents.get("require_user_exact_vi_locks", True)
        ),
    )


def _promote(args) -> int:
    audit_rows = load_jsonl(args.audit)
    card_registry_rows = load_jsonl(args.registry)
    audit_errors = validate_audit_rows(
        audit_rows,
        card_registry_rows,
        require_complete=True,
    )
    if audit_errors:
        print(
            "Semantic registry promotion blocked by incomplete audit:\n"
            + "\n".join(audit_errors[:100]),
            file=sys.stderr,
        )
        return 1
    idiom_rows = load_jsonl(args.idiom_audit)
    idiom_errors = validate_idiom_audit_rows(
        idiom_rows,
        card_registry_rows,
        require_complete=True,
    )
    if idiom_errors:
        print(
            "Semantic registry promotion blocked by incomplete idiom audit:\n"
            + "\n".join(idiom_errors[:100]),
            file=sys.stderr,
        )
        return 1
    try:
        documents = _load_promotion_documents(args)
        promoted = _promote_documents(documents)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Semantic registry promotion failed: {exc}", file=sys.stderr)
        return 1

    registry_errors = validate_semantic_registry_rows(promoted, card_registry_rows)
    if registry_errors:
        print(
            "Semantic registry validation failed:\n"
            + "\n".join(registry_errors[:100]),
            file=sys.stderr,
        )
        return 1

    serialized = serialize_semantic_registry(promoted)
    summary = {
        "audit_sha256": sha256_bytes(documents["audit_bytes"]),
        "cards": len(promoted),
        "definition_review_sha256": sha256_bytes(
            documents["definition_review_bytes"]
        ),
        "idiom_audit_sha256": sha256_bytes(documents["idiom_audit_bytes"]),
        "idioms": idiom_audit_summary(idiom_rows)["occurrences"],
        "semantic_policy_sha256": sha256_bytes(
            documents["semantic_policy_bytes"]
        ),
        "semantic_registry_sha256": sha256_bytes(serialized.encode("utf-8")),
        "sense_merge_review_sha256": sha256_bytes(
            documents["sense_merge_review_bytes"]
        ),
        "senses": sum(len(row.get("senses") or []) for row in promoted),
        "vietnamese_review_sha256": sha256_bytes(
            documents["vietnamese_review_bytes"]
        ),
    }
    if not args.dry_run:
        _write_atomic(args.output, serialized)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _create_manifests(args) -> int:
    output_dir = args.output
    audit_before = args.audit.read_bytes()
    registry_rows = load_jsonl(args.registry)
    with _parallel_snapshot_lock():
        audit_bytes, rows = _load_audit_bytes(args.audit)
        if audit_bytes != audit_before:
            raise RuntimeError("canonical ledger changed while taking snapshot")
        old_summary_path = output_dir / "manifest_summary.json"
        old_created_at = ""
        if old_summary_path.exists():
            try:
                old_summary = json.loads(old_summary_path.read_text(encoding="utf-8"))
                if old_summary.get("ledger", {}).get("sha256") == sha256_bytes(audit_bytes):
                    old_created_at = str(old_summary.get("created_at") or "")
                elif not args.replace:
                    raise RuntimeError("manifest output belongs to a different ledger; use --replace")
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid existing manifest summary: {exc}") from exc
        created_at = args.created_at or old_created_at or utc_now()
        outputs, summary, _ = build_artifacts(
            audit_bytes,
            rows,
            registry_rows,
            scratch_root=paths.root / "scratch",
            created_at=created_at,
        )
        if args.audit.read_bytes() != audit_bytes:
            raise RuntimeError("canonical ledger changed during manifest build")
        if not args.dry_run:
            _write_manifest_outputs(output_dir, outputs)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _validate_manifests(args) -> int:
    audit_bytes, rows = _load_audit_bytes(args.audit)
    registry_rows = load_jsonl(args.registry)
    errors = validate_artifacts(
        audit_bytes,
        rows,
        registry_rows,
        args.input,
        scratch_root=paths.root / "scratch",
    )
    print(json.dumps({"errors": len(errors), "manifest_dir": str(args.input)}, ensure_ascii=False, sort_keys=True))
    if errors:
        print("\n".join(errors[:100]), file=sys.stderr)
        return 1
    return 0


def _definition_audit(args) -> int:
    try:
        _reject_canonical_report_output(args.output)
        _reject_canonical_report_output(args.markdown)
        semantic_bytes, semantic_rows = load_definition_jsonl_bytes(
            args.semantic_registry
        )
        notes_bytes, notes_rows = load_definition_jsonl_bytes(args.notes)
        audit_bytes, audit_rows = load_definition_jsonl_bytes(args.audit)
        card_registry_bytes, card_registry_rows = load_definition_jsonl_bytes(
            args.registry
        )
        summary, candidates = build_definition_audit(
            semantic_rows,
            notes_rows,
            audit_rows,
            card_registry_rows,
            input_hashes={
                "bilingual_semantic_audit": definition_sha256_bytes(audit_bytes),
                "build_notes": definition_sha256_bytes(notes_bytes),
                "card_registry": definition_sha256_bytes(card_registry_bytes),
                "semantic_registry": definition_sha256_bytes(semantic_bytes),
            },
            min_tokens=args.min_tokens,
            scope="long",
        )
        if args.reviews:
            review_bytes, review_rows = load_definition_jsonl_bytes(args.reviews)
            if not review_rows:
                raise ValueError("definition_review_empty")
            review_summary, review_decisions = review_rows[0], review_rows[1:]
            summary, candidates = apply_definition_review_overrides(
                summary,
                candidates,
                review_summary,
                review_decisions,
                review_sha256=definition_sha256_bytes(review_bytes),
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Definition audit failed: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        _write_report_atomic(
            args.output,
            serialize_definition_audit(summary, candidates),
        )
        _write_report_atomic(
            args.markdown,
            render_definition_audit_markdown(summary, candidates),
        )
    print(json.dumps({
        **summary,
        "output": str(args.output),
        "markdown": str(args.markdown),
        "dry_run": args.dry_run,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _definition_review_scaffold(args) -> int:
    try:
        existing_review_rows = None
        if args.output.exists() and not args.replace:
            raise ValueError(
                f"Definition review already exists: {args.output}; use --replace"
            )
        if args.output.exists():
            existing_records = load_jsonl(args.output)
            existing_review_rows = existing_records[1:] if existing_records else []
        _, summary, candidates, _, _ = _current_promotion_gate_candidates(args)
        review_summary, review_rows = scaffold_definition_review(
            summary,
            candidates,
            existing_review_rows=existing_review_rows,
        )
        if not args.dry_run:
            _write_atomic(
                args.output,
                serialize_definition_review(review_summary, review_rows),
            )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Definition review scaffold failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "candidates": len(candidates),
        "candidate_set_sha256": review_summary["candidate_set_sha256"],
        "scope": review_summary["scope"],
        "dry_run": args.dry_run,
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _apply_definition_review(args) -> int:
    try:
        canonical_before = args.review.read_bytes()
        canonical_summary, canonical_rows = _review_records(
            args.review,
            label="definition_review_canonical",
        )
        patch_summary, patch_rows = _review_records(
            args.input,
            label="definition_review_patch",
        )
        _validate_review_patch_size(patch_rows, label="definition_review")
        merged_rows = _merge_review_patch(
            canonical_summary,
            canonical_rows,
            patch_summary,
            patch_rows,
            label="definition_review",
            editable_fields=DEFINITION_REVIEW_EDITABLE_FIELDS,
        )
        _, current_summary, current_candidates, _, _ = (
            _current_promotion_gate_candidates(args)
        )
        if canonical_summary.get("scope") == "long":
            current_summary, current_candidates = select_definition_audit_scope(
                current_summary,
                current_candidates,
                scope="long",
            )
        errors = validate_definition_review(
            current_summary,
            current_candidates,
            canonical_summary,
            merged_rows,
        )
        if errors:
            raise ValueError(
                "Definition review patch produced an invalid canonical ledger:\n"
                + "\n".join(errors[:100])
            )
        serialized = serialize_definition_review(canonical_summary, merged_rows)
        if not args.dry_run:
            if args.review.read_bytes() != canonical_before:
                raise RuntimeError(
                    "canonical Definition review changed while applying patch"
                )
            _write_atomic(args.review, serialized)
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Definition review apply failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "candidates": len(merged_rows),
        "dry_run": args.dry_run,
        "patch_rows": len(patch_rows),
        "review": str(args.review),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _definition_review_create_manifests(args) -> int:
    try:
        summary, rows = _review_records(args.review, label="definition_review")
        _, current_summary, current_candidates, _, _ = (
            _current_promotion_gate_candidates(args)
        )
        if summary.get("scope") == "long":
            current_summary, current_candidates = select_definition_audit_scope(
                current_summary,
                current_candidates,
                scope="long",
            )
        errors = validate_definition_review(
            current_summary,
            current_candidates,
            summary,
            rows,
        )
        if errors:
            raise ValueError(
                "Definition review is stale or invalid:\n"
                + "\n".join(errors[:100])
            )
        outputs, unresolved = _review_manifest_payloads(
            summary,
            rows,
            max_rows=args.max_rows,
            resolved=lambda row: (
                row.get("decision") in {"keep_concise", "keep_explanatory"}
                and row.get("approval") == "approved"
            ),
        )
        if not args.dry_run:
            _write_review_manifest_outputs(
                args.output,
                outputs,
                replace=args.replace,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Definition review manifest creation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "dry_run": args.dry_run,
        "manifest_count": len(outputs),
        "max_rows": args.max_rows,
        "output": str(args.output),
        "unresolved_rows": unresolved,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _sense_merge_review_scaffold(args) -> int:
    try:
        existing_review_rows = None
        if args.output.exists() and not args.replace:
            raise ValueError(
                f"Sense Merge review already exists: {args.output}; use --replace"
            )
        if args.output.exists():
            existing_records = load_jsonl(args.output)
            existing_review_rows = existing_records[1:] if existing_records else []
        _, _, _, summary, candidates = _current_promotion_gate_candidates(args)
        review_summary, review_rows = scaffold_sense_merge_review(
            summary,
            candidates,
            existing_review_rows=existing_review_rows,
        )
        if not args.dry_run:
            _write_atomic(
                args.output,
                serialize_sense_merge_review(review_summary, review_rows),
            )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Sense Merge review scaffold failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "candidates": len(candidates),
        "candidate_set_sha256": review_summary["candidate_set_sha256"],
        "dry_run": args.dry_run,
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _current_vietnamese_audit(args, *, min_tokens: int, scope: str):
    (
        semantic_rows,
        audit_rows,
        card_registry_rows,
        input_hashes,
        audit_bytes,
    ) = _load_vietnamese_audit_inputs(
        semantic_registry=args.semantic_registry,
        audit=args.audit,
        card_registry=args.registry,
    )
    summary, candidates = build_vietnamese_audit(
        semantic_rows,
        audit_rows,
        card_registry_rows,
        min_tokens=min_tokens,
        scope=scope,
        input_hashes=input_hashes,
    )
    return (
        summary,
        candidates,
        semantic_rows,
        audit_rows,
        card_registry_rows,
        input_hashes,
        audit_bytes,
    )


def _vietnamese_selection_args(args) -> tuple[str, int]:
    if args.scope == "all" and args.min_tokens is not None:
        raise ValueError("vietnamese_audit_min_tokens_requires_long_scope")
    return args.scope, (
        args.min_tokens
        if args.min_tokens is not None
        else DEFAULT_VIETNAMESE_MIN_TOKENS
    )


def _vietnamese_audit(args) -> int:
    try:
        _reject_canonical_report_output(args.output)
        _reject_canonical_report_output(args.markdown)
        scope, min_tokens = _vietnamese_selection_args(args)
        summary, candidates, *_ = _current_vietnamese_audit(
            args,
            min_tokens=min_tokens,
            scope=scope,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Vietnamese audit failed: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        _write_report_atomic(
            args.output,
            serialize_vietnamese_audit(summary, candidates),
        )
        _write_report_atomic(
            args.markdown,
            render_vietnamese_audit_markdown(summary, candidates),
        )
    print(json.dumps({
        "candidate_senses": summary["candidate_senses"],
        "cards_scanned": summary["cards_scanned"],
        "dry_run": args.dry_run,
        "markdown": str(args.markdown),
        "min_tokens": summary["min_tokens"],
        "output": str(args.output),
        "scope": summary["scope"],
        "senses_scanned": summary["senses_scanned"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _vietnamese_review_scaffold(args) -> int:
    try:
        existing_review_rows = None
        if args.output.exists() and not args.replace:
            raise ValueError(
                f"Vietnamese review already exists: {args.output}; use --replace"
            )
        existing_path = args.existing_review or (
            args.output if args.output.exists() else None
        )
        if existing_path is not None and existing_path.exists():
            existing_records = load_jsonl(existing_path)
            existing_review_rows = existing_records[1:] if existing_records else []
        scope, min_tokens = _vietnamese_selection_args(args)
        summary, candidates, *_ = _current_vietnamese_audit(
            args,
            min_tokens=min_tokens,
            scope=scope,
        )
        review_summary, review_rows = scaffold_vietnamese_review(
            summary,
            candidates,
            existing_review_rows=existing_review_rows,
        )
        if not args.dry_run:
            _write_atomic(
                args.output,
                serialize_vietnamese_review(review_summary, review_rows),
            )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Vietnamese review scaffold failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({
        "candidates": len(review_rows),
        "dry_run": args.dry_run,
        "min_tokens": review_summary["min_tokens"],
        "output": str(args.output),
        "replaced": bool(args.replace),
        "scope": review_summary["scope"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _vietnamese_review_create_manifests(args) -> int:
    try:
        summary, rows = _review_records(args.review, label="vietnamese_review")
        (
            current_summary,
            current_candidates,
            _,
            _,
            _,
            _,
            _,
        ) = _current_vietnamese_audit(
            args,
            min_tokens=summary.get("min_tokens"),
            scope=summary.get("scope", "long"),
        )
        errors = validate_vietnamese_review(
            current_summary,
            current_candidates,
            summary,
            rows,
            require_complete=False,
        )
        if errors:
            raise ValueError(
                "Vietnamese review is stale or invalid:\n"
                + "\n".join(errors[:100])
            )
        outputs, unresolved = _review_manifest_payloads(
            summary,
            rows,
            max_rows=args.max_rows,
            resolved=lambda row: (
                row.get("decision")
                in {"keep_natural", "keep_explanatory", "rewrite"}
                and row.get("approval") == "approved"
            ),
        )
        if not args.dry_run:
            _write_review_manifest_outputs(
                args.output,
                outputs,
                replace=args.replace,
            )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Vietnamese review manifest creation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "dry_run": args.dry_run,
        "manifest_count": len(outputs),
        "max_rows": args.max_rows,
        "output": str(args.output),
        "unresolved_rows": unresolved,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _apply_vietnamese_review_patch(args) -> int:
    try:
        canonical_before = args.review.read_bytes()
        canonical_summary, canonical_rows = _review_records(
            args.review,
            label="vietnamese_review_canonical",
        )
        patch_summary, patch_rows = _review_records(
            args.input,
            label="vietnamese_review_patch",
        )
        _validate_review_patch_size(patch_rows, label="vietnamese_review")
        merged_rows = _merge_review_patch(
            canonical_summary,
            canonical_rows,
            patch_summary,
            patch_rows,
            label="vietnamese_review",
            editable_fields=VIETNAMESE_REVIEW_EDITABLE_FIELDS,
        )
        (
            current_summary,
            current_candidates,
            _,
            _,
            _,
            _,
            _,
        ) = _current_vietnamese_audit(
            args,
            min_tokens=canonical_summary.get("min_tokens"),
            scope=canonical_summary.get("scope", "long"),
        )
        errors = validate_vietnamese_review(
            current_summary,
            current_candidates,
            canonical_summary,
            merged_rows,
            require_complete=False,
        )
        if errors:
            raise ValueError(
                "Vietnamese review patch produced an invalid canonical ledger:\n"
                + "\n".join(errors[:100])
            )
        serialized = serialize_vietnamese_review(
            canonical_summary,
            merged_rows,
        )
        if not args.dry_run:
            if args.review.read_bytes() != canonical_before:
                raise RuntimeError(
                    "canonical Vietnamese review changed while applying patch"
                )
            _write_atomic(args.review, serialized)
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Vietnamese review patch apply failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "candidates": len(merged_rows),
        "dry_run": args.dry_run,
        "patch_rows": len(patch_rows),
        "review": str(args.review),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _apply_vietnamese_review(args) -> int:
    try:
        review_records = load_jsonl(args.input)
        if not review_records:
            raise ValueError("vietnamese_review_empty")
        # Permit a small, fingerprint-bound patch file containing only review
        # rows.  This keeps long-running all-sense ledgers easy to review while
        # preserving the canonical summary and untouched decisions.  A patch
        # can never add a candidate: exact coverage is still enforced below.
        first_is_summary = review_records[0].get("record_type") == "review_summary"
        declared_count = review_records[0].get("candidate_count")
        is_partial_patch = (
            first_is_summary
            and isinstance(declared_count, int)
            and len(review_records) - 1 < declared_count
        )
        patch_input = review_records[0].get("record_type") == "review" or is_partial_patch
        if patch_input:
            canonical_records = load_jsonl(DEFAULT_VIETNAMESE_REVIEW)
            if not canonical_records:
                raise ValueError("vietnamese_review_canonical_empty")
            review_summary = canonical_records[0]
            existing_rows = {
                str(row.get("candidate_id") or ""): row
                for row in canonical_records[1:]
            }
            patch_rows = review_records[1:] if is_partial_patch else review_records
            for row in patch_rows:
                candidate_id = str(row.get("candidate_id") or "")
                if not candidate_id or candidate_id not in existing_rows:
                    raise ValueError(
                        f"vietnamese_review_patch_unknown_candidate:{candidate_id}"
                    )
                existing_rows[candidate_id] = row
            review_rows = list(existing_rows.values())
        else:
            review_summary, review_rows = review_records[0], review_records[1:]
        min_tokens = review_summary.get("min_tokens")
        scope = review_summary.get("scope", "long")
        (
            _,
            _,
            semantic_rows,
            audit_rows,
            card_registry_rows,
            input_hashes,
            audit_bytes,
        ) = _current_vietnamese_audit(
            args,
            min_tokens=min_tokens,
            scope=scope,
        )
        updated = apply_vietnamese_review(
            semantic_rows,
            audit_rows,
            card_registry_rows,
            review_summary,
            review_rows,
            input_hashes=input_hashes,
            require_complete=True,
        )
        audit_errors = validate_audit_rows(
            updated,
            card_registry_rows,
            require_complete=True,
        )
        if audit_errors:
            raise ValueError(
                "Vietnamese review produced an incomplete semantic audit:\n"
                + "\n".join(audit_errors[:100])
            )
        if not args.dry_run:
            if args.audit.read_bytes() != audit_bytes:
                raise RuntimeError(
                    "bilingual semantic audit changed while applying Vietnamese review"
                )
            _write_atomic(args.audit, serialize_jsonl(updated))
            if patch_input and args.persist_review:
                _write_atomic(
                    DEFAULT_VIETNAMESE_REVIEW,
                    serialize_vietnamese_review(review_summary, review_rows),
                )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Vietnamese review apply failed: {exc}", file=sys.stderr)
        return 1

    rewrites = sum(row.get("decision") == "rewrite" for row in review_rows)
    print(json.dumps({
        **audit_summary(updated),
        "dry_run": args.dry_run,
        "review": str(args.input),
        "persisted_review": bool(
            not args.dry_run and patch_input and args.persist_review
        ),
        "rewrites": rewrites,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _sense_merge_audit(args) -> int:
    try:
        for output in (args.output, args.markdown, args.review_output):
            _reject_canonical_report_output(output)
        if args.bundle_output:
            _reject_canonical_report_output(args.bundle_output)
            if not args.reviews:
                raise ValueError("sense_merge_bundle_requires_reviews")
            if not args.reviewer or not args.reviewed_at or args.approval != "approved":
                raise ValueError(
                    "sense_merge_bundle_requires_reviewer_reviewed_at_and_approved"
                )
        named_paths = (
            ("semantic_registry", args.semantic_registry),
            ("bilingual_semantic_audit", args.audit),
            ("card_registry", args.registry),
            ("deck_audit", args.deck_audit),
            ("non_oxford_non_c2_overrides", args.overrides),
        )
        payloads = {name: path.read_bytes() for name, path in named_paths}
        rows = {
            name: load_sense_merge_jsonl_records(payload)
            for name, payload in payloads.items()
        }
        audit_sha256 = sha256_bytes(payloads["bilingual_semantic_audit"])
        input_errors = validate_audit_rows(
            rows["bilingual_semantic_audit"],
            rows["card_registry"],
            require_complete=True,
        )
        input_errors.extend(validate_semantic_registry_rows(
            rows["semantic_registry"],
            rows["card_registry"],
        ))
        semantic_by_guid = {
            row.get("guid"): row for row in rows["semantic_registry"]
        }
        audit_by_guid = {
            row.get("guid"): row for row in rows["bilingual_semantic_audit"]
        }
        if set(semantic_by_guid) != set(audit_by_guid):
            input_errors.append("sense_merge_registry_audit_guid_mismatch")
        registry_hashes = {
            row.get("audit_sha256") for row in rows["semantic_registry"]
        }
        if registry_hashes != {audit_sha256}:
            input_errors.append("sense_merge_registry_audit_hash_mismatch")
        for guid in sorted(set(semantic_by_guid) & set(audit_by_guid)):
            semantic = semantic_by_guid[guid]
            audit = audit_by_guid[guid]
            if semantic.get("source_fingerprint") != audit.get("source_fingerprint"):
                input_errors.append(f"sense_merge_source_fingerprint_mismatch:{guid}")
            semantic_senses = {
                str(sense.get("semantic_sense_id") or ""): sense
                for sense in semantic.get("senses") or []
            }
            audit_senses = {
                str(sense.get("semantic_sense_id") or ""): sense
                for sense in audit.get("semantic_senses") or []
            }
            if set(semantic_senses) != set(audit_senses):
                input_errors.append(f"sense_merge_semantic_id_mismatch:{guid}")
                continue
            for semantic_id in sorted(semantic_senses):
                if sorted(semantic_senses[semantic_id].get("source_sense_ids") or []) != sorted(
                    audit_senses[semantic_id].get("source_sense_ids") or []
                ):
                    input_errors.append(
                        f"sense_merge_source_mapping_mismatch:{guid}:{semantic_id}"
                    )
        if input_errors:
            raise ValueError(
                "Sense merge audit requires synchronized canonical inputs:\n"
                + "\n".join(input_errors[:100])
            )
        summary, candidates = build_sense_merge_audit(
            rows["semantic_registry"],
            rows["bilingual_semantic_audit"],
            rows["deck_audit"],
            rows["non_oxford_non_c2_overrides"],
            input_hashes=sense_merge_input_hashes(payloads.items()),
        )
        if args.reviews:
            review_records = load_sense_merge_jsonl_records(args.reviews.read_bytes())
            if not review_records:
                raise ValueError("sense_merge_review_empty")
            summary, candidates = apply_sense_merge_reviews(
                summary,
                candidates,
                review_records[0],
                review_records[1:],
            )
        else:
            if args.review_output.exists() and not args.replace_review:
                raise ValueError(
                    f"Sense merge review already exists: {args.review_output}; "
                    "use --replace-review"
                )
            review_summary, review_rows = scaffold_sense_merge_review(
                summary, candidates
            )
            if not args.dry_run:
                _write_report_atomic(
                    args.review_output,
                    serialize_sense_merge_review(review_summary, review_rows),
                )
        bundle = []
        if args.bundle_output:
            bundle = build_sense_merge_review_bundle(
                candidates,
                reviewer=args.reviewer,
                reviewed_at=args.reviewed_at,
            )
            if not args.dry_run:
                _write_report_atomic(args.bundle_output, serialize_jsonl(bundle))
        if not args.dry_run:
            _write_report_atomic(
                args.output,
                serialize_sense_merge_audit(summary, candidates),
            )
            _write_report_atomic(
                args.markdown,
                render_sense_merge_markdown(summary, candidates),
            )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Sense merge audit failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "candidate_cards": summary["candidate_cards"],
        "candidate_set_sha256": summary["candidate_set_sha256"],
        "bundle_cards": len(bundle),
        "bundle_output": str(args.bundle_output) if args.bundle_output else "",
        "decision_counts": summary.get("decision_counts", {}),
        "dry_run": args.dry_run,
        "markdown": str(args.markdown),
        "output": str(args.output),
        "projected_removed_senses": summary.get("projected_removed_senses", 0),
        "review_output": str(args.review_output),
        "reviewed": bool(summary.get("reviewed")),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _add_promotion_input_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_gate_reviews: bool,
) -> None:
    parser.add_argument("--idiom-audit", type=Path, default=DEFAULT_IDIOM_AUDIT)
    parser.add_argument(
        "--vietnamese-review", type=Path, default=DEFAULT_VIETNAMESE_REVIEW
    )
    parser.add_argument(
        "--semantic-policy", type=Path, default=DEFAULT_SEMANTIC_POLICY
    )
    parser.add_argument("--deck-audit", type=Path, default=paths.deck_audit_jsonl)
    parser.add_argument(
        "--overrides", type=Path, default=paths.non_oxford_non_c2_overrides
    )
    if include_gate_reviews:
        parser.add_argument(
            "--definition-review", type=Path, default=DEFAULT_DEFINITION_REVIEW
        )
        parser.add_argument(
            "--sense-merge-review",
            type=Path,
            default=DEFAULT_CANONICAL_SENSE_MERGE_REVIEW,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--registry", type=Path, default=paths.card_registry)
    sub = parser.add_subparsers(dest="command", required=True)

    scaffold = sub.add_parser("scaffold")
    scaffold.add_argument("--notes", type=Path, default=paths.anki_notes_jsonl)
    scaffold.add_argument("--oxford", type=Path, default=paths.oxford_jsonl)
    scaffold.add_argument("--cambridge", type=Path, default=paths.cambridge_jsonl)
    scaffold.add_argument(
        "--existing-audit",
        type=Path,
        help="Reuse reviewed rows only when every immutable semantic input still matches.",
    )
    scaffold.add_argument("--dry-run", action="store_true")
    scaffold.set_defaults(handler=_scaffold)

    validate = sub.add_parser("validate")
    validate.add_argument("--require-complete", action="store_true")
    _add_promotion_input_arguments(validate, include_gate_reviews=True)
    validate.set_defaults(handler=_validate)

    export = sub.add_parser("export-xlsx")
    export.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    export.set_defaults(handler=_export_xlsx)

    import_xlsx = sub.add_parser("import-xlsx")
    import_xlsx.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    import_xlsx.add_argument("--dry-run", action="store_true")
    import_xlsx.set_defaults(handler=_import_xlsx)

    report = sub.add_parser("report")
    report.add_argument("--output", type=Path)
    report.set_defaults(handler=_report)

    apply_review = sub.add_parser("apply-review")
    apply_review.add_argument("--input", type=Path, required=True)
    apply_review.add_argument("--dry-run", action="store_true")
    apply_review.set_defaults(handler=_apply_review)

    promote = sub.add_parser("promote")
    promote.add_argument("--output", type=Path, default=paths.semantic_registry)
    _add_promotion_input_arguments(promote, include_gate_reviews=True)
    promote.add_argument("--dry-run", action="store_true")
    promote.set_defaults(handler=_promote)

    create_manifests = sub.add_parser("create-manifests")
    create_manifests.add_argument("--output", type=Path, default=DEFAULT_MANIFEST_DIR)
    create_manifests.add_argument("--created-at")
    create_manifests.add_argument("--replace", action="store_true")
    create_manifests.add_argument("--dry-run", action="store_true")
    create_manifests.set_defaults(handler=_create_manifests)

    validate_manifests = sub.add_parser("validate-manifests")
    validate_manifests.add_argument("--input", type=Path, default=DEFAULT_MANIFEST_DIR)
    validate_manifests.set_defaults(handler=_validate_manifests)

    definition_audit = sub.add_parser("definition-audit")
    definition_audit.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    definition_audit.add_argument(
        "--notes", type=Path, default=paths.anki_notes_jsonl
    )
    definition_audit.add_argument(
        "--output", type=Path, default=DEFAULT_DEFINITION_AUDIT
    )
    definition_audit.add_argument(
        "--markdown", type=Path, default=DEFAULT_DEFINITION_AUDIT_MARKDOWN
    )
    definition_audit.add_argument("--reviews", type=Path)
    definition_audit.add_argument(
        "--min-tokens",
        type=int,
        default=DEFAULT_DEFINITION_MIN_TOKENS,
    )
    definition_audit.add_argument("--dry-run", action="store_true")
    definition_audit.set_defaults(handler=_definition_audit)

    definition_review = sub.add_parser("definition-review-scaffold")
    _add_promotion_input_arguments(
        definition_review,
        include_gate_reviews=False,
    )
    definition_review.add_argument(
        "--output", type=Path, default=DEFAULT_DEFINITION_REVIEW
    )
    definition_review.add_argument(
        "--scope", choices=("long", "all"), default="all"
    )
    definition_review.add_argument("--replace", action="store_true")
    definition_review.add_argument("--dry-run", action="store_true")
    definition_review.set_defaults(handler=_definition_review_scaffold)

    apply_definition_review = sub.add_parser("apply-definition-review")
    _add_promotion_input_arguments(
        apply_definition_review,
        include_gate_reviews=False,
    )
    apply_definition_review.add_argument(
        "--review",
        type=Path,
        default=DEFAULT_DEFINITION_REVIEW,
        help="Canonical Definition Review ledger to update.",
    )
    apply_definition_review.add_argument("--input", type=Path, required=True)
    apply_definition_review.add_argument("--dry-run", action="store_true")
    apply_definition_review.set_defaults(handler=_apply_definition_review)

    definition_manifests = sub.add_parser(
        "definition-review-create-manifests"
    )
    _add_promotion_input_arguments(
        definition_manifests,
        include_gate_reviews=False,
    )
    definition_manifests.add_argument(
        "--review", type=Path, default=DEFAULT_DEFINITION_REVIEW
    )
    definition_manifests.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DEFINITION_REVIEW_MANIFEST_DIR,
    )
    definition_manifests.add_argument(
        "--max-rows", type=int, default=MAX_REVIEW_MANIFEST_ROWS
    )
    definition_manifests.add_argument("--replace", action="store_true")
    definition_manifests.add_argument("--dry-run", action="store_true")
    definition_manifests.set_defaults(
        handler=_definition_review_create_manifests
    )

    vietnamese_audit = sub.add_parser("vietnamese-audit")
    vietnamese_audit.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    vietnamese_audit.add_argument(
        "--output", type=Path, default=DEFAULT_VIETNAMESE_AUDIT
    )
    vietnamese_audit.add_argument(
        "--markdown", type=Path, default=DEFAULT_VIETNAMESE_AUDIT_MARKDOWN
    )
    vietnamese_audit.add_argument("--scope", choices=("long", "all"), default="long")
    vietnamese_audit.add_argument("--min-tokens", type=int)
    vietnamese_audit.add_argument("--dry-run", action="store_true")
    vietnamese_audit.set_defaults(handler=_vietnamese_audit)

    vietnamese_review_scaffold = sub.add_parser("vietnamese-review-scaffold")
    vietnamese_review_scaffold.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    vietnamese_review_scaffold.add_argument(
        "--output", type=Path, default=DEFAULT_VIETNAMESE_REVIEW
    )
    vietnamese_review_scaffold.add_argument(
        "--scope", choices=("long", "all"), default="all"
    )
    vietnamese_review_scaffold.add_argument("--min-tokens", type=int)
    vietnamese_review_scaffold.add_argument(
        "--existing-review",
        type=Path,
        help="Reuse still-current decisions from this prior fingerprint-bound ledger.",
    )
    vietnamese_review_scaffold.add_argument("--replace", action="store_true")
    vietnamese_review_scaffold.add_argument("--dry-run", action="store_true")
    vietnamese_review_scaffold.set_defaults(handler=_vietnamese_review_scaffold)

    vietnamese_manifests = sub.add_parser(
        "vietnamese-review-create-manifests"
    )
    vietnamese_manifests.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    vietnamese_manifests.add_argument(
        "--review", type=Path, default=DEFAULT_VIETNAMESE_REVIEW
    )
    vietnamese_manifests.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_VIETNAMESE_REVIEW_MANIFEST_DIR,
    )
    vietnamese_manifests.add_argument(
        "--max-rows", type=int, default=MAX_REVIEW_MANIFEST_ROWS
    )
    vietnamese_manifests.add_argument("--replace", action="store_true")
    vietnamese_manifests.add_argument("--dry-run", action="store_true")
    vietnamese_manifests.set_defaults(
        handler=_vietnamese_review_create_manifests
    )

    apply_vietnamese_patch = sub.add_parser(
        "apply-vietnamese-review-patch"
    )
    apply_vietnamese_patch.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    apply_vietnamese_patch.add_argument(
        "--review",
        type=Path,
        default=DEFAULT_VIETNAMESE_REVIEW,
        help="Canonical Vietnamese Naturalness Review ledger to update.",
    )
    apply_vietnamese_patch.add_argument("--input", type=Path, required=True)
    apply_vietnamese_patch.add_argument("--dry-run", action="store_true")
    apply_vietnamese_patch.set_defaults(handler=_apply_vietnamese_review_patch)

    apply_vietnamese_review_parser = sub.add_parser("apply-vietnamese-review")
    apply_vietnamese_review_parser.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    apply_vietnamese_review_parser.add_argument(
        "--input", type=Path, default=DEFAULT_VIETNAMESE_REVIEW
    )
    apply_vietnamese_review_parser.add_argument("--dry-run", action="store_true")
    apply_vietnamese_review_parser.add_argument(
        "--persist-review",
        action="store_true",
        help="Persist a partial/row-only patch into the canonical VI review ledger.",
    )
    apply_vietnamese_review_parser.set_defaults(handler=_apply_vietnamese_review)

    sense_merge_audit = sub.add_parser("sense-merge-audit")
    sense_merge_audit.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    sense_merge_audit.add_argument(
        "--deck-audit", type=Path, default=paths.deck_audit_jsonl
    )
    sense_merge_audit.add_argument(
        "--overrides", type=Path, default=paths.non_oxford_non_c2_overrides
    )
    sense_merge_audit.add_argument(
        "--output", type=Path, default=DEFAULT_SENSE_MERGE_AUDIT
    )
    sense_merge_audit.add_argument(
        "--markdown", type=Path, default=DEFAULT_SENSE_MERGE_AUDIT_MARKDOWN
    )
    sense_merge_audit.add_argument("--reviews", type=Path)
    sense_merge_audit.add_argument("--bundle-output", type=Path)
    sense_merge_audit.add_argument("--reviewer")
    sense_merge_audit.add_argument("--reviewed-at")
    sense_merge_audit.add_argument("--approval", choices=("approved",))
    sense_merge_audit.add_argument(
        "--review-output", type=Path, default=DEFAULT_SENSE_MERGE_REVIEW
    )
    sense_merge_audit.add_argument("--replace-review", action="store_true")
    sense_merge_audit.add_argument("--dry-run", action="store_true")
    sense_merge_audit.set_defaults(handler=_sense_merge_audit)

    sense_merge_review = sub.add_parser("sense-merge-review-scaffold")
    _add_promotion_input_arguments(
        sense_merge_review,
        include_gate_reviews=False,
    )
    sense_merge_review.add_argument(
        "--output", type=Path, default=DEFAULT_CANONICAL_SENSE_MERGE_REVIEW
    )
    sense_merge_review.add_argument("--replace", action="store_true")
    sense_merge_review.add_argument("--dry-run", action="store_true")
    sense_merge_review.set_defaults(handler=_sense_merge_review_scaffold)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
