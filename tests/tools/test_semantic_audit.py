import json
import hashlib
from pathlib import Path

from tools.semantic_audit import main


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _promotion_fixture(tmp_path, *, complete):
    notes = tmp_path / "notes.jsonl"
    registry = tmp_path / "registry.jsonl"
    oxford = tmp_path / "oxford.jsonl"
    cambridge = tmp_path / "cambridge.jsonl"
    audit = tmp_path / "audit.jsonl"
    _write_jsonl(notes, [{
        "guid": "g1", "word": "plain", "pos": "adjective", "cefr": "B2",
        "definition": "easy to understand (dễ hiểu)", "example": "The meaning is plain.",
        "idioms": "", "tags": "Oxford_5000 CEFR::B2",
    }])
    _write_jsonl(registry, [{
        "guid": "g1", "word": "plain", "pos": "adjective", "cefr": "B2",
        "list": "Oxford_5000", "variant": "", "status": "active", "deck_override": None,
    }])
    _write_jsonl(oxford, [{
        "word": "plain", "homonym_index": None, "source_files": ["plain.html"],
        "oxford_badge": "B2", "pos_data": [{"pos": "adjective", "definitions": [{
            "sensenum_local": "1", "text": "easy to understand", "cefr": "B2",
            "examples": [{"text": "The meaning is plain."}],
            "register_tags": [], "domain": None,
        }]}],
    }])
    _write_jsonl(cambridge, [])
    assert main([
        "--audit", str(audit), "--registry", str(registry), "scaffold",
        "--notes", str(notes), "--oxford", str(oxford), "--cambridge", str(cambridge),
    ]) == 0

    if complete:
        rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
        card = rows[0]
        sense = card["semantic_senses"][0]
        source_id = card["source_coverage"][0]["source_sense_id"]
        semantic_id = sense["semantic_sense_id"]
        card["coverage"]["status"] = "pass"
        card["coverage"]["reason"] = "Reviewed source coverage is complete."
        card["source_coverage"][0].update({
            "disposition": "mapped",
            "target_semantic_sense_ids": [semantic_id],
            "reason": "Oxford source sense matches the card.",
        })
        sense.update({
            "source_sense_ids": [source_id],
            "checks": {
                "english_semantics": "pass",
                "vietnamese_semantics": "pass",
                "simplicity": "pass",
                "example_pos_alignment": "pass",
            },
            "decision": "pass",
            "cambridge": {
                "url": "",
                "match": "missing",
                "summary": "No Cambridge Vietnamese entry was required.",
                "translation_provenance": "manual_review",
                "accessed_at": "2026-07-15",
            },
            "confidence": "high",
            "review_reason": "Meaning, translation, and example align.",
            "reviewer": "test-reviewer",
            "reviewed_at": "2026-07-15",
            "approval": "",
        })
        _write_jsonl(audit, rows)
    return audit, registry


def _definition_audit_fixture(tmp_path):
    audit = tmp_path / "audit.jsonl"
    card_registry = tmp_path / "card_registry.jsonl"
    semantic_registry = tmp_path / "semantic_registry.jsonl"
    notes = tmp_path / "notes.jsonl"
    source_fingerprint = "b" * 64
    _write_jsonl(audit, [{
        "guid": "g1",
        "word": "uphold",
        "cefr": "C1",
        "pos": "verb",
        "source_fingerprint": source_fingerprint,
        "source_senses": [
            {
                "source_sense_id": "ox-1", "source": "Oxford", "pos": "verb",
                "cefr_original": "C1", "cefr_resolved": "C1", "sensenum_local": "1",
                "definition": "keep a law or principle", "examples": ["We have a duty to uphold the law."],
                "source_files": ["uphold.html"],
            },
            {
                "source_sense_id": "ox-2", "source": "Oxford", "pos": "verb",
                "cefr_original": "C1", "cefr_resolved": "C1", "sensenum_local": "2",
                "definition": "confirm a decision", "examples": ["The court upheld the conviction."],
                "source_files": ["uphold.html"],
            },
        ],
        "source_coverage": [
            {
                "source_sense_id": source_id,
                "disposition": "mapped",
                "target_semantic_sense_ids": ["sem-1"],
                "reason": "Reviewed mapping.",
            }
            for source_id in ("ox-1", "ox-2")
        ],
        "semantic_senses": [{"semantic_sense_id": "sem-1", "decision": "pass"}],
    }])
    audit_sha = hashlib.sha256(audit.read_bytes()).hexdigest()
    _write_jsonl(card_registry, [{
        "guid": "g1", "word": "uphold", "pos": "verb", "cefr": "C1",
        "list": "Oxford_5000", "variant": "", "status": "active",
    }])
    definition_en = "support and keep a principle or law; confirm that a decision is correct"
    definition_vi = "duy trì/bảo vệ nguyên tắc hoặc luật; xác nhận quyết định là đúng"
    examples = ["We have a duty to uphold the law.", "The court upheld the conviction."]
    _write_jsonl(semantic_registry, [{
        "schema_version": 1,
        "guid": "g1", "word": "uphold", "pos": "verb", "cefr": "C1",
        "list": "Oxford_5000", "variant": "", "audit_sha256": audit_sha,
        "source_fingerprint": source_fingerprint,
        "senses": [{
            "semantic_sense_id": "sem-1", "order": 1,
            "definition_en": definition_en, "definition_vi": definition_vi,
            "examples": examples, "source_sense_ids": ["ox-1", "ox-2"],
            "cambridge_match": "exact", "translation_provenance": "manual_review",
        }],
    }])
    _write_jsonl(notes, [{
        "guid": "g1", "word": "uphold", "pos": "verb", "cefr": "C1",
        "definition": f"{definition_en} ({definition_vi})",
        "example": "<br><br>".join(examples),
    }])
    return audit, card_registry, semantic_registry, notes


def test_cli_scaffold_validate_and_export(tmp_path):
    notes = tmp_path / "notes.jsonl"
    registry = tmp_path / "registry.jsonl"
    oxford = tmp_path / "oxford.jsonl"
    cambridge = tmp_path / "cambridge.jsonl"
    audit = tmp_path / "audit.jsonl"
    xlsx = tmp_path / "audit.xlsx"
    _write_jsonl(notes, [{
        "guid": "g1", "word": "plain", "pos": "adjective", "cefr": "B2",
        "definition": "easy to understand (dễ hiểu)", "example": "The meaning is plain.",
        "idioms": "", "tags": "Oxford_5000 CEFR::B2",
    }])
    _write_jsonl(registry, [{
        "guid": "g1", "word": "plain", "pos": "adjective", "cefr": "B2",
        "list": "Oxford_5000", "variant": "", "status": "active", "deck_override": None,
    }])
    _write_jsonl(oxford, [{
        "word": "plain", "homonym_index": None, "source_files": ["plain.html"], "oxford_badge": "B2",
        "pos_data": [{"pos": "adjective", "definitions": [{
            "sensenum_local": "1", "text": "easy to understand", "cefr": "B2",
            "examples": [{"text": "The meaning is plain."}], "register_tags": [], "domain": None,
        }]}],
    }])
    _write_jsonl(cambridge, [])

    assert main([
        "--audit", str(audit), "--registry", str(registry), "scaffold",
        "--notes", str(notes), "--oxford", str(oxford), "--cambridge", str(cambridge),
    ]) == 0
    assert main(["--audit", str(audit), "--registry", str(registry), "validate"]) == 0
    assert main(["--audit", str(audit), "--registry", str(registry), "export-xlsx", "--xlsx", str(xlsx)]) == 0
    assert audit.exists()
    assert xlsx.exists()


def test_cli_promote_dry_run_does_not_write_output(tmp_path, capsys):
    audit, registry = _promotion_fixture(tmp_path, complete=True)
    output = tmp_path / "curated" / "semantic_registry.jsonl"
    capsys.readouterr()

    assert main([
        "--audit", str(audit), "--registry", str(registry), "promote",
        "--output", str(output), "--dry-run",
    ]) == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["cards"] == 1
    assert summary["senses"] == 1
    assert not output.exists()


def test_cli_promote_rejects_incomplete_audit(tmp_path, capsys):
    audit, registry = _promotion_fixture(tmp_path, complete=False)
    output = tmp_path / "semantic_registry.jsonl"
    capsys.readouterr()

    assert main([
        "--audit", str(audit), "--registry", str(registry), "promote",
        "--output", str(output),
    ]) == 1

    captured = capsys.readouterr()
    assert "promotion blocked by incomplete audit" in captured.err
    assert not output.exists()


def test_cli_promote_writes_hashed_deterministic_registry(tmp_path, capsys):
    audit, registry = _promotion_fixture(tmp_path, complete=True)
    output = tmp_path / "semantic_registry.jsonl"
    audit_sha256 = hashlib.sha256(audit.read_bytes()).hexdigest()
    capsys.readouterr()
    command = [
        "--audit", str(audit), "--registry", str(registry), "promote",
        "--output", str(output),
    ]

    assert main(command) == 0
    first_summary = json.loads(capsys.readouterr().out)
    first_payload = output.read_bytes()
    assert first_summary == {
        "audit_sha256": audit_sha256,
        "cards": 1,
        "semantic_registry_sha256": hashlib.sha256(first_payload).hexdigest(),
        "senses": 1,
    }
    assert len(first_payload.decode("utf-8").splitlines()) == 1

    assert main(command) == 0
    second_summary = json.loads(capsys.readouterr().out)
    assert output.read_bytes() == first_payload
    assert second_summary == first_summary


def test_cli_definition_audit_dry_run_and_deterministic_outputs(tmp_path, capsys):
    audit, card_registry, semantic_registry, notes = _definition_audit_fixture(tmp_path)
    output = tmp_path / "scratch" / "definition_audit.jsonl"
    markdown = tmp_path / "scratch" / "definition_audit.md"
    command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "definition-audit",
        "--semantic-registry", str(semantic_registry),
        "--notes", str(notes),
        "--output", str(output),
        "--markdown", str(markdown),
    ]

    assert main([*command, "--dry-run"]) == 0
    dry_summary = json.loads(capsys.readouterr().out)
    assert dry_summary["candidate_senses"] == 1
    assert dry_summary["dry_run"] is True
    assert not output.exists()
    assert not markdown.exists()

    assert main(command) == 0
    first_summary = json.loads(capsys.readouterr().out)
    first_jsonl = output.read_bytes()
    first_markdown = markdown.read_bytes()
    assert first_summary["candidate_senses"] == 1
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert records[1]["word"] == "uphold"
    assert records[1]["recommendation"] == "split"
    markdown_text = markdown.read_text(encoding="utf-8")
    assert "| Proposed example | Semantic reason | Source evidence |" in markdown_text
    assert "ox-1 [Oxford verb#1]" in markdown_text

    assert main(command) == 0
    capsys.readouterr()
    assert output.read_bytes() == first_jsonl
    assert markdown.read_bytes() == first_markdown


def test_cli_definition_audit_rejects_canonical_output_paths(tmp_path, capsys):
    audit, card_registry, semantic_registry, notes = _definition_audit_fixture(tmp_path)
    project_root = Path(__file__).resolve().parents[2]
    forbidden = project_root / "data" / "review" / "definition_audit.jsonl"

    assert main([
        "--audit", str(audit),
        "--registry", str(card_registry),
        "definition-audit",
        "--semantic-registry", str(semantic_registry),
        "--notes", str(notes),
        "--output", str(forbidden),
        "--markdown", str(tmp_path / "report.md"),
    ]) == 1
    assert "must stay outside canonical data directories" in capsys.readouterr().err
    assert not forbidden.exists()
