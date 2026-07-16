"""Deterministic parallel manifests for the bilingual semantic audit.

This module is deliberately side-effect free.  The CLI owns locking and file
writes; these helpers only read rows and render canonical bytes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .semantic_audit import load_jsonl, validate_audit_rows


MANIFEST_SCHEMA_VERSION = 1
WORKER_COUNT = 3
OPEN_VALUES = {"pending", "uncertain"}


def canonical_json_bytes(value: object, *, newline: bool = False) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if newline:
        text += "\n"
    return text.encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class WorkCard:
    row: dict
    pending_source_ids: tuple[str, ...]
    pending_semantic_ids: tuple[str, ...]
    weight: int
    weight_basis: str
    fingerprint: str

    @property
    def guid(self) -> str:
        return str(self.row.get("guid") or "")


@dataclass(frozen=True)
class BundleScan:
    completed: tuple[dict, ...]
    reserved: tuple[dict, ...]


def _pending_semantic_ids(row: dict) -> tuple[str, ...]:
    values: list[tuple[int, str]] = []
    for sense in row.get("semantic_senses") or []:
        checks = sense.get("checks") or {}
        if sense.get("decision") in OPEN_VALUES or any(value in OPEN_VALUES for value in checks.values()):
            semantic_id = str(sense.get("semantic_sense_id") or "")
            if semantic_id:
                values.append((int(sense.get("order") or 0), semantic_id))
    return tuple(item[1] for item in sorted(values))


def _pending_source_ids(row: dict) -> tuple[str, ...]:
    source_ids = {str(item.get("source_sense_id") or "") for item in row.get("source_senses") or []}
    candidates = {str(item or "") for item in (row.get("coverage") or {}).get("candidate_source_sense_ids") or []}
    coverage_ids = [str(item.get("source_sense_id") or "") for item in row.get("source_coverage") or []]
    if set(coverage_ids) != candidates or len(coverage_ids) != len(set(coverage_ids)):
        raise ValueError(f"invalid_source_coverage_set:{row.get('guid')}")
    if not set(coverage_ids) <= source_ids:
        raise ValueError(f"unknown_source_coverage_source:{row.get('guid')}")
    return tuple(sorted(
        item["source_sense_id"]
        for item in row.get("source_coverage") or []
        if item.get("disposition") == "pending"
    ))


def work_card(row: dict, *, ledger_sha256: str) -> WorkCard | None:
    pending_source = _pending_source_ids(row)
    pending_semantic = _pending_semantic_ids(row)
    if not pending_source and not pending_semantic:
        return None
    basis = "pending_source_coverage" if pending_source else "pending_semantic_senses"
    weight = len(pending_source) or len(pending_semantic)
    return WorkCard(
        row=row,
        pending_source_ids=pending_source,
        pending_semantic_ids=pending_semantic,
        weight=weight,
        weight_basis=basis,
        fingerprint=sha256_bytes(canonical_json_bytes(row)),
    )


def scan_review_bundles(
    scratch_root: Path,
    rows_by_guid: dict[str, dict],
    open_guids: set[str],
) -> BundleScan:
    completed: list[dict] = []
    reserved: list[dict] = []
    seen: dict[str, str] = {}
    paths = sorted(scratch_root.glob("bilingual_semantic_review_*.jsonl"))
    parallel_root = scratch_root / "parallel"
    if parallel_root.exists():
        paths.extend(sorted(parallel_root.glob("worker_*/*.jsonl")))
    for path in paths:
        try:
            decisions = load_jsonl(path)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid_review_bundle:{path}:{exc}") from exc
        file_guids: set[str] = set()
        for decision in decisions:
            guid = str(decision.get("guid") or "")
            if not guid or guid in file_guids:
                raise ValueError(f"duplicate_or_empty_bundle_guid:{path}:{guid}")
            if guid not in rows_by_guid:
                raise ValueError(f"unknown_bundle_guid:{path}:{guid}")
            if guid in seen:
                raise ValueError(f"bundle_guid_repeated:{guid}:{seen[guid]}:{path}")
            file_guids.add(guid)
            seen[guid] = str(path)
            try:
                display_path = path.relative_to(scratch_root.parent).as_posix()
            except ValueError:
                display_path = path.as_posix()
            item = {"file": display_path, "guid": guid, "word": rows_by_guid[guid].get("word", "")}
            if guid in open_guids:
                item.update({"status": "deferred_existing_bundle", "reason": "avoid_duplicate_review"})
                reserved.append(item)
            else:
                item.update({"status": "completed_or_superseded", "reason": "not_open_in_snapshot"})
                completed.append(item)
    return BundleScan(tuple(completed), tuple(reserved))


def partition_work(cards: Iterable[WorkCard], workers: int = WORKER_COUNT) -> list[list[WorkCard]]:
    if workers != WORKER_COUNT:
        raise ValueError(f"exactly {WORKER_COUNT} workers are supported")
    partitions: list[list[WorkCard]] = [[] for _ in range(workers)]
    totals = [0] * workers
    for card in sorted(cards, key=lambda item: (-item.weight, item.guid)):
        index = min(range(workers), key=lambda worker: (totals[worker], worker))
        partitions[index].append(card)
        totals[index] += card.weight
    return partitions


def manifest_row(card: WorkCard, *, ledger_sha256: str, worker: int) -> dict:
    row = card.row
    return {
        "audit_schema_version": row.get("schema_version", 1),
        "card_fingerprint": card.fingerprint,
        "cefr": row.get("cefr", ""),
        "guid": card.guid,
        "headword": row.get("word", ""),
        "ledger_sha256": ledger_sha256,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "pending_semantic_sense_ids": list(card.pending_semantic_ids),
        "pending_source_sense_ids": list(card.pending_source_ids),
        "pos": row.get("pos", ""),
        "source_fingerprint": row.get("source_fingerprint", ""),
        "snapshot_id": f"audit-v{row.get('schema_version', 1)}:{ledger_sha256}",
        "variant": row.get("variant", ""),
        "weight": card.weight,
        "weight_basis": card.weight_basis,
        "word": row.get("word", ""),
        "worker": worker,
    }


def render_jsonl(rows: Iterable[dict]) -> bytes:
    return b"".join(canonical_json_bytes(row, newline=True) for row in rows)


def build_artifacts(
    audit_bytes: bytes,
    rows: list[dict],
    registry_rows: list[dict],
    *,
    scratch_root: Path,
    created_at: str,
    workers: int = WORKER_COUNT,
    bundle_scan: BundleScan | None = None,
) -> tuple[dict[str, bytes], dict, list[str]]:
    ledger_sha = sha256_bytes(audit_bytes)
    structural_errors = validate_audit_rows(rows, registry_rows)
    if structural_errors:
        raise ValueError("audit_validation_failed:" + "|".join(structural_errors[:20]))
    by_guid = {str(row.get("guid") or ""): row for row in rows}
    all_cards = [card for row in rows if (card := work_card(row, ledger_sha256=ledger_sha)) is not None]
    open_guids = {card.guid for card in all_cards}
    bundles = bundle_scan or scan_review_bundles(scratch_root, by_guid, open_guids)
    reserved_guids = {item["guid"] for item in bundles.reserved}
    assigned = [card for card in all_cards if card.guid not in reserved_guids]
    partitions = partition_work(assigned, workers)
    outputs: dict[str, bytes] = {}
    worker_stats = []
    for worker, partition in enumerate(partitions, 1):
        rows_out = [manifest_row(card, ledger_sha256=ledger_sha, worker=worker) for card in partition]
        payload = render_jsonl(rows_out)
        name = f"worker_{worker}.jsonl"
        outputs[name] = payload
        worker_stats.append({
            "worker": worker,
            "path": f"scratch/parallel/manifests/{name}",
            "card_count": len(partition),
            "weight": sum(card.weight for card in partition),
            "sha256": sha256_bytes(payload),
            "worker_output_dir": f"scratch/parallel/worker_{worker}",
        })
    weights = [item["weight"] for item in worker_stats]
    assigned_weights = [card.weight for card in assigned]
    summary = {
        "created_at": created_at,
        "ledger": {
            "path": "data/review/bilingual_semantic_audit.jsonl",
            "sha256": ledger_sha,
            "schema_version": rows[0].get("schema_version", 1) if rows else 1,
            "size_bytes": len(audit_bytes),
        },
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "snapshot_id": f"audit-v{rows[0].get('schema_version', 1) if rows else 1}:{ledger_sha}",
        "queue": {
            "eligible_card_count_before_reservation": len(all_cards),
            "assigned_card_count": len(assigned),
            "reserved_card_count": len(reserved_guids),
            "eligible_weight_before_reservation": sum(card.weight for card in all_cards),
            "assigned_weight": sum(assigned_weights),
            "card_weight_min": min(assigned_weights) if assigned_weights else 0,
            "card_weight_max": max(assigned_weights) if assigned_weights else 0,
        },
        "workers": worker_stats,
        "imbalance": {
            "min_worker_weight": min(weights) if weights else 0,
            "max_worker_weight": max(weights) if weights else 0,
            "difference": (max(weights) - min(weights)) if weights else 0,
            "percent": ((max(weights) - min(weights)) / sum(weights) * 100) if sum(weights) else 0.0,
        },
        "exclusions": {
            "completed_or_superseded": list(bundles.completed),
            "deferred_existing_bundle": list(bundles.reserved),
        },
        "serialization": {
            "encoding": "utf-8",
            "newline": "LF",
            "sort_keys": True,
            "separators": [",", ":"],
        },
    }
    outputs["manifest_summary.json"] = canonical_json_bytes(summary, newline=True)
    return outputs, summary, []


def _snapshot_bundle_scan(summary: dict, rows_by_guid: dict[str, dict], open_guids: set[str]) -> BundleScan:
    """Restore the bundle exclusions frozen when the manifests were created.

    Worker output bundles are created after the snapshot and must not become new
    reservations when validating that snapshot.
    """
    exclusions = summary.get("exclusions")
    if not isinstance(exclusions, dict):
        raise ValueError("invalid_manifest_exclusions")
    groups = (
        ("completed_or_superseded", "completed_or_superseded", "not_open_in_snapshot", False),
        ("deferred_existing_bundle", "deferred_existing_bundle", "avoid_duplicate_review", True),
    )
    restored: dict[str, tuple[dict, ...]] = {}
    seen: set[str] = set()
    for key, status, reason, must_be_open in groups:
        items = exclusions.get(key)
        if not isinstance(items, list):
            raise ValueError(f"invalid_manifest_exclusions:{key}")
        checked: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"invalid_manifest_exclusion_item:{key}")
            guid = str(item.get("guid") or "")
            if not guid or guid in seen:
                raise ValueError(f"duplicate_or_empty_manifest_exclusion_guid:{guid}")
            if guid not in rows_by_guid:
                raise ValueError(f"unknown_manifest_exclusion_guid:{guid}")
            if (guid in open_guids) != must_be_open:
                raise ValueError(f"stale_manifest_exclusion_status:{guid}")
            if item.get("status") != status or item.get("reason") != reason:
                raise ValueError(f"invalid_manifest_exclusion_status:{guid}")
            if item.get("word") != rows_by_guid[guid].get("word", "") or not item.get("file"):
                raise ValueError(f"invalid_manifest_exclusion_metadata:{guid}")
            seen.add(guid)
            checked.append(item)
        restored[key] = tuple(checked)
    return BundleScan(
        completed=restored["completed_or_superseded"],
        reserved=restored["deferred_existing_bundle"],
    )


def validate_artifacts(
    audit_bytes: bytes,
    rows: list[dict],
    registry_rows: list[dict],
    manifest_dir: Path,
    *,
    scratch_root: Path,
) -> list[str]:
    errors: list[str] = []
    summary_path = manifest_dir / "manifest_summary.json"
    if not summary_path.exists():
        return [f"missing_manifest:{summary_path}"]
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid_summary:{exc}"]
    ledger_sha = sha256_bytes(audit_bytes)
    if summary.get("ledger", {}).get("sha256") != ledger_sha:
        errors.append("stale_ledger_sha256")
    try:
        by_guid = {str(row.get("guid") or ""): row for row in rows}
        open_guids = {
            card.guid
            for row in rows
            if (card := work_card(row, ledger_sha256=ledger_sha)) is not None
        }
        bundle_scan = _snapshot_bundle_scan(summary, by_guid, open_guids)
        outputs, expected_summary, _ = build_artifacts(
            audit_bytes, rows, registry_rows, scratch_root=scratch_root,
            created_at=str(summary.get("created_at") or ""),
            bundle_scan=bundle_scan,
        )
    except ValueError as exc:
        return [str(exc)]
    expected_guids: set[str] = set()
    seen_guids: set[str] = set()
    for worker in range(1, WORKER_COUNT + 1):
        path = manifest_dir / f"worker_{worker}.jsonl"
        if not path.exists():
            errors.append(f"missing_manifest:{path}")
            continue
        actual = path.read_bytes()
        name = path.name
        if outputs.get(name) != actual:
            errors.append(f"manifest_bytes_mismatch:{name}")
        try:
            items = [json.loads(line) for line in actual.decode("utf-8").splitlines() if line.strip()]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid_manifest_json:{name}:{exc}")
            continue
        for item in items:
            guid = str(item.get("guid") or "")
            if guid in seen_guids:
                errors.append(f"duplicate_manifest_guid:{guid}")
            seen_guids.add(guid)
            expected_guids.add(guid)
            if item.get("worker") != worker:
                errors.append(f"wrong_worker:{guid}")
    expected_assigned: set[str] = set()
    for worker in expected_summary["workers"]:
        payload = outputs[f"worker_{worker['worker']}.jsonl"].decode("utf-8")
        expected_assigned.update(
            str(json.loads(line)["guid"])
            for line in payload.splitlines()
            if line.strip()
        )
    if expected_guids != expected_assigned:
        errors.append("manifest_guid_union_mismatch")
    if summary.get("workers") != expected_summary.get("workers"):
        errors.append("worker_summary_mismatch")
    if summary.get("queue") != expected_summary.get("queue"):
        errors.append("queue_summary_mismatch")
    if summary.get("imbalance") != expected_summary.get("imbalance"):
        errors.append("imbalance_summary_mismatch")
    actual_workers = {item.get("worker"): item for item in summary.get("workers") or []}
    for worker in range(1, WORKER_COUNT + 1):
        name = f"worker_{worker}.jsonl"
        expected_hash = next(item["sha256"] for item in expected_summary["workers"] if item["worker"] == worker)
        if actual_workers.get(worker, {}).get("sha256") != expected_hash:
            errors.append(f"manifest_hash_mismatch:{name}")
    return errors
