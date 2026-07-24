import json

import pytest

from src.deck_builder.collocation_audit import (
    apply_review_bundle,
    collocation_final_item_id,
    load_jsonl,
    serialize_audit_rows,
)
from src.deck_builder.simplify_senses import _flatten_senses
from src.deck_builder.source_sense_identity import source_sense_id
from tools.collocation_audit import main


def _write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fixture_files(tmp_path):
    registry_path = tmp_path / "card_registry.jsonl"
    notes_path = tmp_path / "notes.jsonl"
    semantic_path = tmp_path / "semantic.jsonl"
    oxford_path = tmp_path / "oxford.jsonl"
    cambridge_path = tmp_path / "cambridge.jsonl"
    registry = [{
        "guid": "g1",
        "word": "curriculum",
        "cefr": "B2",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "noun",
        "status": "active",
        "deck_override": None,
    }]
    note = {
        "guid": "g1",
        "word": "curriculum",
        "cefr": "B2",
        "pos": "noun",
        "collocations": "school curriculum",
    }
    oxford = {
        "word": "curriculum",
        "homonym_index": None,
        "source": "oxford",
        "source_files": ["oxford_curriculum.html"],
        "pos_data": [{
            "pos": "noun",
            "definitions": [{
                "n": 1,
                "sensenum_local": None,
                "text": "subjects taught in school",
                "cefr": "B2",
                "register_tags": [],
                "topics": [],
                "collocations": {},
                "collocation_evidence": [],
                "examples": [],
                "is_phrase": False,
                "is_idiom": False,
            }],
        }],
    }
    source_id = source_sense_id(oxford, _flatten_senses(oxford)[0])
    semantic = [{
        "schema_version": 4,
        "guid": "g1",
        "word": "curriculum",
        "cefr": "B2",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "noun",
        "senses": [{
            "semantic_sense_id": "sem_1",
            "order": 1,
            "source_sense_ids": [source_id],
        }],
    }]
    _write_jsonl(registry_path, registry)
    _write_jsonl(notes_path, [note])
    _write_jsonl(semantic_path, semantic)
    _write_jsonl(oxford_path, [oxford])
    _write_jsonl(cambridge_path, [])
    return registry_path, notes_path, semantic_path, oxford_path, cambridge_path


def _scaffold_args(audit, fixture_paths, *tail):
    registry, notes, semantic, oxford, cambridge = fixture_paths
    return [
        "--audit", str(audit),
        "--registry", str(registry),
        "scaffold",
        "--notes", str(notes),
        "--semantic-registry", str(semantic),
        "--oxford", str(oxford),
        "--cambridge", str(cambridge),
        *tail,
    ]


def _current_args(fixture_paths):
    _, notes, semantic, oxford, cambridge = fixture_paths
    return [
        "--notes", str(notes),
        "--semantic-registry", str(semantic),
        "--oxford", str(oxford),
        "--cambridge", str(cambridge),
    ]


def _complete(row):
    current = row["current_items"][0]
    final_id = collocation_final_item_id(row["guid"], current["text"])
    row["final_items"] = [{
        "final_item_id": final_id,
        "text": current["text"],
        "order": 1,
        "source": "curated",
        "evidence_ids": [],
        "current_item_ids": [current["current_item_id"]],
    }]
    current.update({
        "decision": "keep_curated",
        "target_final_item_ids": [final_id],
        "reason": "Retain the reviewed current school curriculum pattern.",
        "reviewer": "reviewer",
        "reviewed_at": "2026-07-18",
        "approval": "approved",
    })


def test_cli_scaffold_validate_promote_and_reuse_review(tmp_path):
    fixture_paths = _fixture_files(tmp_path)
    audit = tmp_path / "audit.jsonl"
    output = tmp_path / "registry.jsonl"

    assert main(_scaffold_args(audit, fixture_paths)) == 0
    registry_path = fixture_paths[0]
    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "validate",
        *_current_args(fixture_paths),
        "--require-complete",
    ]) == 1

    rows = load_jsonl(audit)
    _complete(rows[0])
    audit.write_text(serialize_audit_rows(rows), encoding="utf-8")
    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "validate",
        *_current_args(fixture_paths),
        "--require-complete",
    ]) == 0

    assert main(_scaffold_args(audit, fixture_paths)) == 0
    assert load_jsonl(audit)[0]["current_items"][0]["decision"] == "keep_curated"

    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "promote",
        *_current_args(fixture_paths),
        "--output", str(output),
        "--dry-run",
    ]) == 0
    assert not output.exists()
    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "promote",
        *_current_args(fixture_paths),
        "--output", str(output),
    ]) == 0
    promoted = load_jsonl(output)
    assert promoted[0]["items"] == [{
        "evidence_ids": [],
        "order": 1,
        "source": "curated",
        "text": "school curriculum",
    }]


def test_apply_review_bundle_is_fingerprint_bound_and_transactional(tmp_path):
    fixture_paths = _fixture_files(tmp_path)
    audit = tmp_path / "audit.jsonl"
    assert main(_scaffold_args(audit, fixture_paths)) == 0
    rows = load_jsonl(audit)
    row = rows[0]
    _complete(row)
    bundle = [json.loads(json.dumps(row))]
    bundle[0]["current_items"][0]["reviewer"] = "bundle-reviewer"
    updated = apply_review_bundle(rows, bundle)
    assert updated[0]["current_items"][0]["reviewer"] == "bundle-reviewer"

    stale = json.loads(json.dumps(bundle[0]))
    stale["input_fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="Stale review bundle fingerprint"):
        apply_review_bundle(rows, [stale])

    immutable = json.loads(json.dumps(bundle[0]))
    immutable["source_evidence"] = [{"unexpected": "mutation"}]
    with pytest.raises(ValueError, match="Immutable review inputs changed"):
        apply_review_bundle(rows, [immutable])


def test_cli_export_import_and_report_are_non_destructive_in_dry_run(tmp_path):
    fixture_paths = _fixture_files(tmp_path)
    audit = tmp_path / "audit.jsonl"
    workbook = tmp_path / "audit.xlsx"
    report = tmp_path / "report.md"
    assert main(_scaffold_args(audit, fixture_paths)) == 0
    registry_path = fixture_paths[0]
    before = audit.read_bytes()

    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "export-xlsx",
        *_current_args(fixture_paths),
        "--xlsx", str(workbook),
    ]) == 0
    assert workbook.is_file()
    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "import-xlsx",
        *_current_args(fixture_paths),
        "--xlsx", str(workbook),
        "--dry-run",
    ]) == 0
    assert audit.read_bytes() == before

    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "report",
        *_current_args(fixture_paths),
        "--output", str(report),
        "--dry-run",
    ]) == 0
    assert not report.exists()


def test_cli_validate_fails_when_ledger_is_missing(tmp_path, capsys):
    fixture_paths = _fixture_files(tmp_path)
    assert main([
        "--audit", str(tmp_path / "missing.jsonl"),
        "--registry", str(fixture_paths[0]),
        "validate",
    ]) == 1
    assert "No such file or directory" in capsys.readouterr().err


def test_cli_validate_and_promote_fail_when_source_evidence_changes(tmp_path, capsys):
    fixture_paths = _fixture_files(tmp_path)
    audit = tmp_path / "audit.jsonl"
    output = tmp_path / "registry.jsonl"
    assert main(_scaffold_args(audit, fixture_paths)) == 0
    rows = load_jsonl(audit)
    _complete(rows[0])
    audit.write_text(serialize_audit_rows(rows), encoding="utf-8")

    oxford_path = fixture_paths[3]
    oxford = load_jsonl(oxford_path)
    oxford[0]["pos_data"][0]["definitions"][0]["collocation_evidence"] = [{
        "text": "on the curriculum",
        "source": "oxford",
        "origin": "oxford_collocations_snippet",
        "evidence_kind": "supporting",
        "example_index": None,
        "example_text": None,
        "container_index": 1,
        "item_index": 1,
        "category": None,
        "truncated": False,
        "full_entry_url": None,
    }]
    _write_jsonl(oxford_path, oxford)
    registry_path = fixture_paths[0]

    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "validate",
        *_current_args(fixture_paths),
        "--require-complete",
    ]) == 1
    assert "stale_collocation_audit_projection" in capsys.readouterr().err
    assert main([
        "--audit", str(audit),
        "--registry", str(registry_path),
        "promote",
        *_current_args(fixture_paths),
        "--output", str(output),
    ]) == 1
    assert not output.exists()


def test_cli_create_and_validate_whole_guid_manifests(tmp_path):
    fixture_paths = _fixture_files(tmp_path)
    audit = tmp_path / "audit.jsonl"
    manifests = tmp_path / "manifests"
    assert main(_scaffold_args(audit, fixture_paths)) == 0

    assert main([
        "--audit", str(audit),
        "--registry", str(fixture_paths[0]),
        "create-manifests",
        "--output", str(manifests),
        "--created-at", "2026-07-22T00:00:00Z",
    ]) == 0
    assert main([
        "--audit", str(audit),
        "--registry", str(fixture_paths[0]),
        "validate-manifests",
        "--input", str(manifests),
    ]) == 0
