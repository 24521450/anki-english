import json
from pathlib import Path

import pytest

import tools.semantic_audit as semantic_audit_cli
from src.deck_builder.semantic_audit_manifests import (
    build_artifacts,
    partition_work,
    validate_artifacts,
    work_card,
)


def _sense(guid: str, source_id: str = "ox-1") -> dict:
    return {
        "schema_version": 1,
        "guid": guid,
        "word": "sample",
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "noun",
        "current": {"definition": "a thing", "example": "A sample.", "idioms": ""},
        "source_fingerprint": "source-fingerprint",
        "source_senses": [{"source_sense_id": source_id}],
        "coverage": {"status": "pending", "reason": "", "candidate_source_sense_ids": [source_id]},
        "source_coverage": [{
            "source_sense_id": source_id,
            "disposition": "pending",
            "target_semantic_sense_ids": [],
            "reason": "",
        }],
        "semantic_senses": [{
            "semantic_sense_id": f"sem-{guid}",
            "order": 1,
            "source_sense_ids": [],
            "current": {"definition_en": "a thing", "definition_vi": "một vật", "examples": ["A sample."]},
            "checks": {"english_semantics": "pending", "vietnamese_semantics": "pending", "simplicity": "pending", "example_pos_alignment": "pending"},
            "decision": "pending",
            "proposed": {"definition_en": "", "definition_vi": "", "examples": []},
            "cambridge": {"url": "", "match": "pending", "summary": "", "translation_provenance": ""},
            "confidence": "", "review_reason": "", "reviewer": "", "reviewed_at": "", "approval": "",
        }],
    }


def _registry(guid: str = "g1") -> dict:
    return {"guid": guid, "word": "sample", "cefr": "C1", "list": "Oxford_5000", "variant": "", "pos": "noun", "status": "active"}


def test_work_card_prioritizes_pending_source_and_is_idiom_validator_compatible():
    row = _sense("g1")
    card = work_card(row, ledger_sha256="ledger")
    assert card is not None
    assert card.pending_source_ids == ("ox-1",)
    assert card.pending_semantic_ids == ("sem-g1",)
    assert card.weight == 1
    assert card.weight_basis == "pending_source_coverage"

    idiom = _sense("g2", "cam-1")
    idiom["semantic_senses"] = []
    idiom["current"] = {"definition": "", "example": "", "idioms": "for example"}
    idiom["coverage"].update({"status": "not_applicable", "reason": "idiom_only"})
    idiom_card = work_card(idiom, ledger_sha256="ledger")
    assert idiom_card is not None
    assert idiom_card.weight == 1


def test_partition_is_guid_deterministic_and_balances_weight():
    rows = []
    for guid, weight in [("z", 5), ("a", 4), ("b", 3), ("c", 2), ("d", 1)]:
        row = _sense(guid)
        row["source_coverage"] = [
            {"source_sense_id": f"ox-{index}", "disposition": "pending", "target_semantic_sense_ids": [], "reason": ""}
            for index in range(weight)
        ]
        row["source_senses"] = [{"source_sense_id": f"ox-{index}"} for index in range(weight)]
        row["coverage"]["candidate_source_sense_ids"] = [f"ox-{index}" for index in range(weight)]
        rows.append(work_card(row, ledger_sha256="ledger"))
    partitions = partition_work([item for item in rows if item is not None])
    assert [[item.guid for item in part] for part in partitions] == [["z"], ["a", "d"], ["b", "c"]]
    assert [sum(item.weight for item in part) for part in partitions] == [5, 5, 5]


def test_build_and_validate_manifest_artifacts_are_byte_stable(tmp_path: Path):
    audit_path = tmp_path / "audit.jsonl"
    rows = [_sense("g1")]
    audit_bytes = (json.dumps(rows[0], separators=(",", ":")) + "\n").encode("utf-8")
    audit_path.write_bytes(audit_bytes)
    registry = [_registry("g1")]
    outputs1, summary1, errors = build_artifacts(audit_bytes, rows, registry, scratch_root=tmp_path / "scratch", created_at="2026-01-01T00:00:00Z")
    outputs2, summary2, _ = build_artifacts(audit_bytes, rows, registry, scratch_root=tmp_path / "scratch", created_at="2026-01-01T00:00:00Z")
    assert errors == []
    assert outputs1 == outputs2
    assert summary1 == summary2
    manifest_dir = tmp_path / "scratch" / "parallel" / "manifests"
    manifest_dir.mkdir(parents=True)
    for name, payload in outputs1.items():
        (manifest_dir / name).write_bytes(payload)
    assert validate_artifacts(audit_bytes, rows, registry, manifest_dir, scratch_root=tmp_path / "scratch") == []
    (manifest_dir / "worker_1.jsonl").write_bytes(b"{}\n")
    assert "manifest_bytes_mismatch:worker_1.jsonl" in validate_artifacts(audit_bytes, rows, registry, manifest_dir, scratch_root=tmp_path / "scratch")


def test_manifest_validation_ignores_worker_bundles_created_after_snapshot(tmp_path: Path):
    rows = [_sense("g1")]
    audit_bytes = (json.dumps(rows[0], separators=(",", ":")) + "\n").encode("utf-8")
    registry = [_registry("g1")]
    scratch = tmp_path / "scratch"
    outputs, _, _ = build_artifacts(
        audit_bytes,
        rows,
        registry,
        scratch_root=scratch,
        created_at="2026-01-01T00:00:00Z",
    )
    manifest_dir = scratch / "parallel" / "manifests"
    manifest_dir.mkdir(parents=True)
    for name, payload in outputs.items():
        (manifest_dir / name).write_bytes(payload)

    worker_dir = scratch / "parallel" / "worker_1"
    worker_dir.mkdir(parents=True)
    (worker_dir / "review_bundle.jsonl").write_text(
        json.dumps({"guid": "g1"}) + "\n",
        encoding="utf-8",
    )

    assert validate_artifacts(
        audit_bytes,
        rows,
        registry,
        manifest_dir,
        scratch_root=scratch,
    ) == []


def test_parallel_lock_blocks_canonical_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    lock = tmp_path / "parallel.lock"
    lock.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(semantic_audit_cli, "PARALLEL_LOCK", lock)
    with pytest.raises(RuntimeError, match="canonical ledger write blocked"):
        semantic_audit_cli._write_atomic(tmp_path / "audit.jsonl", "{}\n")
