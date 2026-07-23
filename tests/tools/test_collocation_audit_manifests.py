import json

from src.deck_builder.collocation_audit import build_audit_rows, serialize_audit_rows
from src.deck_builder.collocation_audit_manifests import (
    build_artifacts,
    validate_artifacts,
)
from tests.deck_builder.test_collocation_audit import _inputs, _note, _registry


def test_collocation_manifests_are_deterministic_and_keep_whole_guid(tmp_path):
    oxford, cambridge, semantic = _inputs()
    rows = build_audit_rows([_note()], _registry(), semantic, oxford, cambridge)
    audit_bytes = serialize_audit_rows(rows).encode("utf-8")

    first, first_summary, errors = build_artifacts(
        audit_bytes, rows, _registry(), created_at="2026-07-22T00:00:00Z"
    )
    second, second_summary, _ = build_artifacts(
        audit_bytes, rows, _registry(), created_at="2026-07-22T00:00:00Z"
    )

    assert errors == []
    assert first == second
    assert first_summary == second_summary
    assigned = []
    for worker in range(1, 4):
        assigned.extend(
            json.loads(line)["guid"]
            for line in first[f"worker_{worker}.jsonl"].decode().splitlines()
        )
    assert assigned == ["g1"]
    assert first_summary["qa"] == {
        "whole_guid_assignment": True,
        "assigned_guid_count": 1,
        "duplicate_guid_count": 0,
    }

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    for name, payload in first.items():
        (manifest_dir / name).write_bytes(payload)
    assert validate_artifacts(audit_bytes, rows, _registry(), manifest_dir) == []


def test_collocation_manifest_validation_detects_stale_worker_bytes(tmp_path):
    oxford, cambridge, semantic = _inputs()
    rows = build_audit_rows([_note()], _registry(), semantic, oxford, cambridge)
    audit_bytes = serialize_audit_rows(rows).encode("utf-8")
    outputs, _, _ = build_artifacts(
        audit_bytes, rows, _registry(), created_at="2026-07-22T00:00:00Z"
    )
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    for name, payload in outputs.items():
        (manifest_dir / name).write_bytes(payload)
    (manifest_dir / "worker_1.jsonl").write_bytes(b"{}\n")

    errors = validate_artifacts(audit_bytes, rows, _registry(), manifest_dir)

    assert "manifest_bytes_mismatch:worker_1.jsonl" in errors
