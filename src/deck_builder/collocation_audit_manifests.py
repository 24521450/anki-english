"""Deterministic whole-card worker manifests for Collocation Audit review."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .collocation_audit import AUDIT_SCHEMA_VERSION, validate_audit_rows


MANIFEST_SCHEMA_VERSION = 1
WORKER_COUNT = 3
OPEN_VALUES = {"pending", "uncertain"}


def canonical_json_bytes(value: object, *, newline: bool = False) -> bytes:
    text = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    return (text + ("\n" if newline else "")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class WorkCard:
    row: dict
    open_current_ids: tuple[str, ...]
    open_candidate_ids: tuple[str, ...]
    weight: int
    fingerprint: str

    @property
    def guid(self) -> str:
        return str(self.row.get("guid") or "")


def work_card(row: dict) -> WorkCard | None:
    current = tuple(
        str(item.get("current_item_id") or "")
        for item in row.get("current_items") or []
        if item.get("decision") in OPEN_VALUES or item.get("approval") != "approved"
    )
    candidates = tuple(
        str(item.get("candidate_id") or "")
        for item in row.get("mandatory_candidates") or []
        if item.get("decision") in OPEN_VALUES or item.get("approval") != "approved"
    )
    empty_open = not row.get("final_items") and row.get("empty_approval") != "approved"
    weight = len(current) + len(candidates) + int(empty_open)
    if not weight:
        return None
    return WorkCard(
        row=row,
        open_current_ids=current,
        open_candidate_ids=candidates,
        weight=weight,
        fingerprint=sha256_bytes(canonical_json_bytes(row)),
    )


def partition_work(cards: Iterable[WorkCard], workers: int = WORKER_COUNT) -> list[list[WorkCard]]:
    if workers != WORKER_COUNT:
        raise ValueError(f"exactly {WORKER_COUNT} workers are supported")
    partitions: list[list[WorkCard]] = [[] for _ in range(workers)]
    totals = [0] * workers
    for card in sorted(cards, key=lambda item: (-item.weight, item.guid)):
        worker = min(range(workers), key=lambda index: (totals[index], index))
        partitions[worker].append(card)
        totals[worker] += card.weight
    return partitions


def _manifest_row(card: WorkCard, *, ledger_sha256: str, worker: int) -> dict:
    row = card.row
    return {
        "audit_schema_version": row.get("schema_version"),
        "card_fingerprint": card.fingerprint,
        "cefr": row.get("cefr", ""),
        "guid": card.guid,
        "ledger_sha256": ledger_sha256,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "open_candidate_ids": list(card.open_candidate_ids),
        "open_current_item_ids": list(card.open_current_ids),
        "pos": row.get("pos", ""),
        "snapshot_id": f"collocation-audit-v{AUDIT_SCHEMA_VERSION}:{ledger_sha256}",
        "source_fingerprint": row.get("source_fingerprint", ""),
        "variant": row.get("variant", ""),
        "weight": card.weight,
        "word": row.get("word", ""),
        "worker": worker,
    }


def build_artifacts(
    audit_bytes: bytes,
    rows: list[dict],
    registry_rows: list[dict],
    *,
    created_at: str,
    workers: int = WORKER_COUNT,
) -> tuple[dict[str, bytes], dict, list[str]]:
    structural_errors = validate_audit_rows(rows, registry_rows)
    if structural_errors:
        raise ValueError("audit_validation_failed:" + "|".join(structural_errors[:20]))
    ledger_sha = sha256_bytes(audit_bytes)
    cards = [card for row in rows if (card := work_card(row)) is not None]
    partitions = partition_work(cards, workers)
    outputs: dict[str, bytes] = {}
    stats: list[dict] = []
    for worker, partition in enumerate(partitions, 1):
        payload = b"".join(
            canonical_json_bytes(
                _manifest_row(card, ledger_sha256=ledger_sha, worker=worker),
                newline=True,
            )
            for card in partition
        )
        name = f"worker_{worker}.jsonl"
        outputs[name] = payload
        stats.append({
            "worker": worker,
            "path": f"scratch/parallel/collocation_manifests/{name}",
            "card_count": len(partition),
            "weight": sum(card.weight for card in partition),
            "sha256": sha256_bytes(payload),
        })
    completed = sorted(
        ({"guid": str(row.get("guid") or ""), "word": row.get("word", ""),
          "reason": "no_open_review_items"}
         for row in rows if work_card(row) is None),
        key=lambda item: item["guid"],
    )
    weights = [item["weight"] for item in stats]
    summary = {
        "created_at": created_at,
        "ledger": {
            "path": "data/review/collocation_audit.jsonl",
            "sha256": ledger_sha,
            "schema_version": AUDIT_SCHEMA_VERSION,
            "size_bytes": len(audit_bytes),
        },
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "snapshot_id": f"collocation-audit-v{AUDIT_SCHEMA_VERSION}:{ledger_sha}",
        "queue": {
            "assigned_card_count": len(cards),
            "assigned_weight": sum(card.weight for card in cards),
            "completed_card_count": len(completed),
        },
        "workers": stats,
        "imbalance": {
            "min_worker_weight": min(weights) if weights else 0,
            "max_worker_weight": max(weights) if weights else 0,
            "difference": max(weights) - min(weights) if weights else 0,
        },
        "exclusions": {"completed": completed},
        "qa": {
            "whole_guid_assignment": True,
            "assigned_guid_count": len({card.guid for card in cards}),
            "duplicate_guid_count": len(cards) - len({card.guid for card in cards}),
        },
        "serialization": {"encoding": "utf-8", "newline": "LF", "sort_keys": True},
    }
    outputs["manifest_summary.json"] = canonical_json_bytes(summary, newline=True)
    return outputs, summary, []


def validate_artifacts(
    audit_bytes: bytes,
    rows: list[dict],
    registry_rows: list[dict],
    manifest_dir: Path,
) -> list[str]:
    summary_path = manifest_dir / "manifest_summary.json"
    if not summary_path.is_file():
        return [f"missing_manifest:{summary_path}"]
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        expected, expected_summary, _ = build_artifacts(
            audit_bytes, rows, registry_rows,
            created_at=str(summary.get("created_at") or ""),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid_manifest_summary:{exc}"]
    errors: list[str] = []
    seen: set[str] = set()
    for worker in range(1, WORKER_COUNT + 1):
        name = f"worker_{worker}.jsonl"
        path = manifest_dir / name
        if not path.is_file():
            errors.append(f"missing_manifest:{path}")
            continue
        actual = path.read_bytes()
        if actual != expected[name]:
            errors.append(f"manifest_bytes_mismatch:{name}")
        try:
            manifest_rows = [json.loads(line) for line in actual.decode("utf-8").splitlines() if line]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid_manifest_json:{name}:{exc}")
            continue
        for item in manifest_rows:
            guid = str(item.get("guid") or "")
            if guid in seen:
                errors.append(f"duplicate_manifest_guid:{guid}")
            seen.add(guid)
            if item.get("worker") != worker:
                errors.append(f"wrong_worker:{guid}")
    for key in ("ledger", "queue", "workers", "imbalance", "exclusions", "qa", "serialization", "snapshot_id", "manifest_schema_version"):
        if summary.get(key) != expected_summary.get(key):
            errors.append(f"manifest_summary_mismatch:{key}")
    return errors
