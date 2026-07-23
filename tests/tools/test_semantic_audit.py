import json
import hashlib
import copy
from pathlib import Path

import pytest

from src.deck_builder.idiom_audit import build_audit_rows, serialize_jsonl
from src.deck_builder.semantic_registry import SEMANTIC_REGISTRY_SCHEMA_VERSION
from src.deck_builder.vietnamese_audit import (
    build_vietnamese_audit,
    scaffold_vietnamese_review,
    serialize_vietnamese_review,
)
from tools.semantic_audit import main
from src.deck_builder.canonical_io import canonical_text_sha256


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _add_vietnamese_evidence(row, candidate):
    decision = row["decision"]
    final_vi = row["proposed_vi"] if decision == "rewrite" else row["expected_definition_vi"]
    row["reason_code"] = {
        "keep_natural": "natural_lexical_gloss",
        "keep_explanatory": "necessary_explanation",
        "rewrite": "natural_rewrite",
    }[decision]
    support = (
        candidate.get("examples")
        or candidate.get("source_definitions")
        or [""]
    )[0]
    row["semantic_evidence"] = (
        f'Final VI "{final_vi}" expresses exact Definition EN '
        f'"{candidate["definition_en"]}" in Support "{support}"; '
        f'{row["reason"]}'
    )
    row["lock_id"] = ""


def _vietnamese_candidate_from_registry(registry, review):
    cards = [
        json.loads(line)
        for line in registry.read_text(encoding="utf-8").splitlines()
    ]
    card = next(row for row in cards if row["guid"] == review["guid"])
    sense = next(
        row
        for row in card["senses"]
        if row["semantic_sense_id"] == review["semantic_sense_id"]
    )
    return {
        "definition_en": sense["definition_en"],
        "examples": list(sense.get("examples") or []),
        "source_definitions": [],
    }


def _write_complete_all_vietnamese_review(path, audit, registry):
    audit_rows = [
        json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()
    ]
    registry_rows = [
        json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines()
    ]
    semantic_rows = []
    for card in audit_rows:
        senses = []
        for sense in card.get("semantic_senses") or []:
            content = (
                sense.get("proposed")
                if sense.get("decision") == "repair_proposed"
                else sense.get("current")
            ) or {}
            senses.append({
                "semantic_sense_id": sense["semantic_sense_id"],
                "order": sense["order"],
                "definition_en": content["definition_en"],
                "definition_vi": content["definition_vi"],
                "examples": copy.deepcopy(content["examples"]),
                "source_sense_ids": copy.deepcopy(sense["source_sense_ids"]),
                "cambridge_match": sense["cambridge"]["match"],
                "translation_provenance": sense["cambridge"][
                    "translation_provenance"
                ],
            })
        semantic_rows.append({
            **{
                field: card[field]
                for field in ("guid", "word", "cefr", "list", "variant", "pos")
            },
            "source_fingerprint": card["source_fingerprint"],
            "senses": senses,
        })
    summary, candidates = build_vietnamese_audit(
        semantic_rows,
        audit_rows,
        registry_rows,
        scope="all",
    )
    review_summary, review_rows = scaffold_vietnamese_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    for row in review_rows:
        row.update({
            "decision": "keep_natural",
            "reason": "The gloss directly expresses this reviewed learner meaning without source-shaped expansion.",
            "reviewer": "test-reviewer",
            "reviewed_at": "2026-07-17",
            "approval": "approved",
        })
        _add_vietnamese_evidence(row, candidates_by_id[row["candidate_id"]])
    path.write_text(
        serialize_vietnamese_review(review_summary, review_rows),
        encoding="utf-8",
    )


def _promotion_fixture(tmp_path, *, complete):
    notes = tmp_path / "notes.jsonl"
    registry = tmp_path / "registry.jsonl"
    oxford = tmp_path / "oxford.jsonl"
    cambridge = tmp_path / "cambridge.jsonl"
    audit = tmp_path / "audit.jsonl"
    idiom_audit = tmp_path / "idiom_audit.jsonl"
    vietnamese_review = tmp_path / "vietnamese_review.jsonl"
    idiom_audit.write_text("", encoding="utf-8")
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
        _write_complete_all_vietnamese_review(vietnamese_review, audit, registry)
    return audit, registry, idiom_audit, vietnamese_review


def _promotion_gate_cli_args(tmp_path):
    semantic_policy = tmp_path / "semantic_policy.jsonl"
    definition_review = tmp_path / "definition_review.jsonl"
    sense_merge_review = tmp_path / "sense_merge_review.jsonl"
    deck_audit = tmp_path / "deck_audit.jsonl"
    overrides = tmp_path / "overrides.jsonl"
    empty_set_sha = hashlib.sha256(b"[]").hexdigest()
    semantic_policy.write_text("", encoding="utf-8")
    _write_jsonl(definition_review, [{
        "record_type": "review_summary",
        "schema_version": 3,
        "candidate_count": 0,
        "candidate_set_sha256": empty_set_sha,
    }])
    _write_jsonl(sense_merge_review, [{
        "schema_version": 1,
        "kind": "semantic_sense_merge_review",
        "candidate_set_sha256": empty_set_sha,
        "candidate_cards": 0,
        "input_hashes": {},
    }])
    _write_jsonl(deck_audit, [])
    _write_jsonl(overrides, [])
    return [
        "--semantic-policy", str(semantic_policy),
        "--definition-review", str(definition_review),
        "--sense-merge-review", str(sense_merge_review),
        "--deck-audit", str(deck_audit),
        "--overrides", str(overrides),
    ]


def _promotion_scaffold_cli_args(tmp_path):
    args = _promotion_gate_cli_args(tmp_path)
    excluded = {"--definition-review", "--sense-merge-review"}
    return [
        value
        for index, value in enumerate(args)
        if not (
            value in excluded
            or (index > 0 and args[index - 1] in excluded)
        )
    ]


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
    audit_sha = canonical_text_sha256(audit.read_bytes())
    _write_jsonl(card_registry, [{
        "guid": "g1", "word": "uphold", "pos": "verb", "cefr": "C1",
        "list": "Oxford_5000", "variant": "", "status": "active",
    }])
    definition_en = "support and keep a principle or law; confirm that a decision is correct"
    definition_vi = "duy trì/bảo vệ nguyên tắc hoặc luật; xác nhận quyết định là đúng"
    examples = ["We have a duty to uphold the law.", "The court upheld the conviction."]
    _write_jsonl(semantic_registry, [{
        "schema_version": SEMANTIC_REGISTRY_SCHEMA_VERSION,
        "guid": "g1", "word": "uphold", "pos": "verb", "cefr": "C1",
        "list": "Oxford_5000", "variant": "", "audit_sha256": audit_sha,
        "source_fingerprint": source_fingerprint,
        "senses": [{
            "semantic_sense_id": "sem-1", "order": 1,
            "definition_en": definition_en, "definition_vi": definition_vi,
            "examples": examples, "source_sense_ids": ["ox-1", "ox-2"],
            "cambridge_match": "exact", "translation_provenance": "manual_review",
        }],
        "idiom_audit_sha256": "c" * 64,
        "vietnamese_review_sha256": "d" * 64,
        "semantic_policy_sha256": "e" * 64,
        "definition_review_sha256": "f" * 64,
        "sense_merge_review_sha256": "0" * 64,
        "idioms": [],
    }])
    _write_jsonl(notes, [{
        "guid": "g1", "word": "uphold", "pos": "verb", "cefr": "C1",
        "definition": f"{definition_en} ({definition_vi})",
        "example": "<br><br>".join(examples),
    }])
    return audit, card_registry, semantic_registry, notes


def _vietnamese_audit_fixture(
    tmp_path,
    *,
    definition_vi="người hoặc đội có cơ hội thắng cuộc",
    schema_version=1,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    audit, card_registry, _, _ = _promotion_fixture(tmp_path, complete=True)
    audit_rows = [
        json.loads(line)
        for line in audit.read_text(encoding="utf-8").splitlines()
    ]
    card = audit_rows[0]
    sense = card["semantic_senses"][0]
    sense["current"]["definition_vi"] = definition_vi
    _write_jsonl(audit, audit_rows)

    semantic_registry = tmp_path / "semantic_registry.jsonl"
    registry_sense = {
        "semantic_sense_id": sense["semantic_sense_id"],
        "order": sense["order"],
        "definition_en": sense["current"]["definition_en"],
        "definition_vi": definition_vi,
        "examples": copy.deepcopy(sense["current"]["examples"]),
        "source_sense_ids": copy.deepcopy(sense["source_sense_ids"]),
        "cambridge_match": sense["cambridge"]["match"],
        "translation_provenance": sense["cambridge"]["translation_provenance"],
    }
    semantic_card = {
        "schema_version": schema_version,
        "guid": card["guid"],
        "word": card["word"],
        "cefr": card["cefr"],
        "list": card["list"],
        "variant": card["variant"],
        "pos": card["pos"],
        "audit_sha256": canonical_text_sha256(audit.read_bytes()),
        "source_fingerprint": card["source_fingerprint"],
        "senses": [registry_sense],
    }
    if schema_version >= 2:
        semantic_card.update({"idiom_audit_sha256": "c" * 64, "idioms": []})
    if schema_version >= 3:
        semantic_card["vietnamese_review_sha256"] = "d" * 64
    if schema_version >= 4:
        semantic_card.update({
            "semantic_policy_sha256": "e" * 64,
            "definition_review_sha256": "f" * 64,
            "sense_merge_review_sha256": "0" * 64,
        })
    _write_jsonl(semantic_registry, [semantic_card])
    return audit, card_registry, semantic_registry


def _complete_vietnamese_review(
    path,
    semantic_registry,
    *,
    proposed_vi="đối thủ nặng ký",
):
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    for row in rows[1:]:
        row.update({
            "decision": "rewrite",
            "proposed_vi": proposed_vi,
            "reason": "Prefer a concise, idiomatic Vietnamese gloss.",
            "reviewer": "test-reviewer",
            "reviewed_at": "2026-07-16",
            "approval": "approved",
        })
        _add_vietnamese_evidence(
            row,
            _vietnamese_candidate_from_registry(semantic_registry, row),
        )
    _write_jsonl(path, rows)
    return rows


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

    reviewed = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
    reviewed["coverage"] = {
        **reviewed["coverage"],
        "status": "reviewed",
        "reason": "Exact source sense reviewed for this test.",
    }
    reviewed["source_coverage"][0].update({
        "disposition": "mapped",
        "target_semantic_sense_ids": [reviewed["semantic_senses"][0]["semantic_sense_id"]],
        "reason": "Exact source meaning maps to the displayed sense.",
    })
    reviewed["semantic_senses"][0].update({
        "decision": "pass",
        "checks": {key: "pass" for key in reviewed["semantic_senses"][0]["checks"]},
        "confidence": "high",
        "review_reason": "Definition and example match the exact source sense.",
        "reviewer": "test-reviewer",
        "reviewed_at": "2026-07-23",
        "approval": "approved",
    })
    reviewed["semantic_senses"][0]["source_sense_ids"] = [
        reviewed["source_senses"][0]["source_sense_id"]
    ]
    reviewed["semantic_senses"][0]["cambridge"].update({
        "match": "missing",
        "summary": "No Cambridge record is present in this fixture.",
        "translation_provenance": "reviewer_derived",
        "accessed_at": "2026-07-23",
    })
    _write_jsonl(audit, [reviewed])
    assert main([
        "--audit", str(audit), "--registry", str(registry), "scaffold",
        "--notes", str(notes), "--oxford", str(oxford), "--cambridge", str(cambridge),
    ]) == 0
    assert json.loads(audit.read_text(encoding="utf-8").splitlines()[0]) == reviewed


def test_cli_promote_dry_run_does_not_write_output(tmp_path, capsys):
    audit, registry, idiom_audit, vietnamese_review = _promotion_fixture(
        tmp_path, complete=True
    )
    output = tmp_path / "curated" / "semantic_registry.jsonl"
    capsys.readouterr()

    assert main([
        "--audit", str(audit), "--registry", str(registry), "promote",
        "--idiom-audit", str(idiom_audit),
        "--vietnamese-review", str(vietnamese_review),
        *_promotion_gate_cli_args(tmp_path),
        "--output", str(output), "--dry-run",
    ]) == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["cards"] == 1
    assert summary["senses"] == 1
    assert not output.exists()


def test_cli_promote_rejects_incomplete_audit(tmp_path, capsys):
    audit, registry, idiom_audit, vietnamese_review = _promotion_fixture(
        tmp_path, complete=False
    )
    output = tmp_path / "semantic_registry.jsonl"
    capsys.readouterr()

    assert main([
        "--audit", str(audit), "--registry", str(registry), "promote",
        "--idiom-audit", str(idiom_audit),
        "--vietnamese-review", str(vietnamese_review),
        *_promotion_gate_cli_args(tmp_path),
        "--output", str(output),
    ]) == 1

    captured = capsys.readouterr()
    assert "promotion blocked by incomplete audit" in captured.err
    assert not output.exists()


def test_cli_promote_rejects_incomplete_idiom_audit(tmp_path, capsys):
    audit, registry, idiom_audit, vietnamese_review = _promotion_fixture(
        tmp_path, complete=True
    )
    registry_rows = [
        json.loads(line)
        for line in registry.read_text(encoding="utf-8").splitlines()
    ]
    pending = build_audit_rows([{
        "guid": "g1",
        "word": "plain",
        "cefr": "B2",
        "pos": "adjective",
        "idioms": "plain sailing :: easy to do",
        "source1": "Oxford",
    }], registry_rows)
    idiom_audit.write_text(serialize_jsonl(pending), encoding="utf-8")
    output = tmp_path / "semantic_registry.jsonl"
    capsys.readouterr()

    assert main([
        "--audit", str(audit), "--registry", str(registry), "promote",
        "--idiom-audit", str(idiom_audit),
        "--vietnamese-review", str(vietnamese_review),
        *_promotion_gate_cli_args(tmp_path),
        "--output", str(output),
    ]) == 1

    captured = capsys.readouterr()
    assert "promotion blocked by incomplete idiom audit" in captured.err
    assert not output.exists()


def test_cli_validate_require_complete_fails_closed_on_vietnamese_review(
    tmp_path,
    capsys,
):
    audit, registry, idiom_audit, vietnamese_review = _promotion_fixture(
        tmp_path, complete=True
    )
    command = [
        "--audit", str(audit),
        "--registry", str(registry),
        "validate",
        "--require-complete",
        "--idiom-audit", str(idiom_audit),
        "--vietnamese-review", str(vietnamese_review),
        *_promotion_gate_cli_args(tmp_path),
    ]
    capsys.readouterr()

    assert main(command) == 0
    capsys.readouterr()

    records = [
        json.loads(line)
        for line in vietnamese_review.read_text(encoding="utf-8").splitlines()
    ]
    records[0]["scope"] = "long"
    _write_jsonl(vietnamese_review, records)
    assert main(command) == 1
    assert "scope_must_be_all" in capsys.readouterr().err


def test_cli_promote_rejects_missing_pending_and_stale_vietnamese_review(
    tmp_path,
    capsys,
):
    audit, registry, idiom_audit, vietnamese_review = _promotion_fixture(
        tmp_path, complete=True
    )
    output = tmp_path / "semantic_registry.jsonl"
    command = [
        "--audit", str(audit), "--registry", str(registry), "promote",
        "--idiom-audit", str(idiom_audit),
        "--vietnamese-review", str(vietnamese_review),
        *_promotion_gate_cli_args(tmp_path),
        "--output", str(output),
    ]
    original = vietnamese_review.read_bytes()
    capsys.readouterr()

    vietnamese_review.unlink()
    assert main(command) == 1
    assert "Vietnamese review" in capsys.readouterr().err
    assert not output.exists()

    vietnamese_review.write_bytes(original)
    records = [
        json.loads(line)
        for line in vietnamese_review.read_text(encoding="utf-8").splitlines()
    ]
    records[1].update({"decision": "pending", "approval": ""})
    _write_jsonl(vietnamese_review, records)
    assert main(command) == 1
    assert "open_or_invalid_decision" in capsys.readouterr().err
    assert not output.exists()

    vietnamese_review.write_bytes(original)
    records = [
        json.loads(line)
        for line in vietnamese_review.read_text(encoding="utf-8").splitlines()
    ]
    records[1]["context_fingerprint"] = "0" * 64
    _write_jsonl(vietnamese_review, records)
    assert main(command) == 1
    assert "stale_context" in capsys.readouterr().err
    assert not output.exists()


def test_cli_promote_writes_hashed_deterministic_registry(tmp_path, capsys):
    audit, registry, idiom_audit, vietnamese_review = _promotion_fixture(
        tmp_path, complete=True
    )
    output = tmp_path / "semantic_registry.jsonl"
    audit_sha256 = canonical_text_sha256(audit.read_bytes())
    idiom_audit_sha256 = canonical_text_sha256(idiom_audit.read_bytes())
    vietnamese_review_sha256 = canonical_text_sha256(
        vietnamese_review.read_bytes()
    )
    capsys.readouterr()
    command = [
        "--audit", str(audit), "--registry", str(registry), "promote",
        "--idiom-audit", str(idiom_audit),
        "--vietnamese-review", str(vietnamese_review),
        *_promotion_gate_cli_args(tmp_path),
        "--output", str(output),
    ]
    semantic_policy_sha256 = canonical_text_sha256(
        (tmp_path / "semantic_policy.jsonl").read_bytes()
    )
    definition_review_sha256 = canonical_text_sha256(
        (tmp_path / "definition_review.jsonl").read_bytes()
    )
    sense_merge_review_sha256 = canonical_text_sha256(
        (tmp_path / "sense_merge_review.jsonl").read_bytes()
    )

    assert main(command) == 0
    first_summary = json.loads(capsys.readouterr().out)
    first_payload = output.read_bytes()
    assert first_summary == {
        "audit_sha256": audit_sha256,
        "cards": 1,
        "definition_review_sha256": definition_review_sha256,
        "idiom_audit_sha256": idiom_audit_sha256,
        "idioms": 0,
        "semantic_policy_sha256": semantic_policy_sha256,
        "semantic_registry_sha256": hashlib.sha256(first_payload).hexdigest(),
        "sense_merge_review_sha256": sense_merge_review_sha256,
        "senses": 1,
        "vietnamese_review_sha256": vietnamese_review_sha256,
    }
    promoted_row = json.loads(first_payload)
    assert promoted_row["vietnamese_review_sha256"] == vietnamese_review_sha256
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


@pytest.mark.parametrize(
    ("command_name", "summary_kind"),
    [
        ("definition-review-scaffold", "review_summary"),
        ("sense-merge-review-scaffold", "semantic_sense_merge_review"),
    ],
)
def test_cli_promotion_gate_scaffolds_are_deterministic_and_replace_guarded(
    tmp_path,
    capsys,
    command_name,
    summary_kind,
):
    audit, registry, idiom_audit, vietnamese_review = _promotion_fixture(
        tmp_path, complete=True
    )
    capsys.readouterr()
    output = tmp_path / f"{command_name}.jsonl"
    base = [
        "--audit", str(audit),
        "--registry", str(registry),
        command_name,
        "--idiom-audit", str(idiom_audit),
        "--vietnamese-review", str(vietnamese_review),
        *_promotion_scaffold_cli_args(tmp_path),
        "--output", str(output),
    ]

    assert main([*base, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["candidates"] == 0
    assert not output.exists()

    assert main(base) == 0
    capsys.readouterr()
    first = output.read_bytes()
    summary = json.loads(first.decode("utf-8").splitlines()[0])
    assert summary.get("record_type", summary.get("kind")) == summary_kind

    assert main(base) == 1
    assert "use --replace" in capsys.readouterr().err
    assert output.read_bytes() == first

    assert main([*base, "--replace"]) == 0
    capsys.readouterr()
    assert output.read_bytes() == first


def test_cli_vietnamese_audit_is_deterministic_and_honours_threshold(tmp_path, capsys):
    audit, card_registry, semantic_registry = _vietnamese_audit_fixture(tmp_path)
    output = tmp_path / "scratch" / "vietnamese_audit.jsonl"
    markdown = tmp_path / "scratch" / "vietnamese_audit.md"
    command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "vietnamese-audit",
        "--semantic-registry", str(semantic_registry),
        "--output", str(output),
        "--markdown", str(markdown),
        "--min-tokens", "8",
    ]
    capsys.readouterr()

    assert main([*command, "--dry-run"]) == 0
    dry_summary = json.loads(capsys.readouterr().out)
    assert dry_summary["candidate_senses"] == 1
    assert not output.exists()
    assert not markdown.exists()

    assert main(command) == 0
    capsys.readouterr()
    first_jsonl = output.read_bytes()
    first_markdown = markdown.read_bytes()
    report_rows = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert report_rows[0]["candidate_senses"] == 1
    assert report_rows[1]["vi_token_count"] == 8

    assert main(command) == 0
    capsys.readouterr()
    assert output.read_bytes() == first_jsonl
    assert markdown.read_bytes() == first_markdown

    above_boundary = tmp_path / "scratch" / "above_boundary.jsonl"
    assert main([
        *command[:-4],
        "--output", str(above_boundary),
        "--markdown", str(tmp_path / "scratch" / "above_boundary.md"),
        "--min-tokens", "9",
    ]) == 0
    boundary_summary = json.loads(capsys.readouterr().out)
    assert boundary_summary["candidate_senses"] == 0

    assert main([*command[:-2], "--scope", "all", "--dry-run"]) == 0
    all_summary = json.loads(capsys.readouterr().out)
    assert all_summary["scope"] == "all"
    assert all_summary["candidate_senses"] == 1

    assert main([
        *command[:-2],
        "--scope", "all",
        "--min-tokens", "9",
        "--dry-run",
    ]) == 1
    assert "min_tokens_requires_long_scope" in capsys.readouterr().err


def test_cli_vietnamese_audit_uses_complete_audit_when_registry_is_legacy_or_stale(
    tmp_path,
    capsys,
):
    audit, card_registry, semantic_registry = _vietnamese_audit_fixture(
        tmp_path / "v2",
        schema_version=2,
    )
    command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "vietnamese-audit",
        "--semantic-registry", str(semantic_registry),
        "--output", str(tmp_path / "report.jsonl"),
        "--markdown", str(tmp_path / "report.md"),
        "--dry-run",
    ]
    capsys.readouterr()

    assert main(command) == 0
    capsys.readouterr()
    registry_rows = [
        json.loads(line)
        for line in semantic_registry.read_text(encoding="utf-8").splitlines()
    ]
    registry_rows[0]["audit_sha256"] = "0" * 64
    _write_jsonl(semantic_registry, registry_rows)

    assert main(command) == 0
    assert json.loads(capsys.readouterr().out)["candidate_senses"] == 1


def test_cli_vietnamese_review_scaffold_is_deterministic_and_replace_guarded(
    tmp_path,
    capsys,
):
    audit, card_registry, semantic_registry = _vietnamese_audit_fixture(tmp_path)
    review = tmp_path / "review.jsonl"
    command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "vietnamese-review-scaffold",
        "--semantic-registry", str(semantic_registry),
        "--output", str(review),
    ]
    capsys.readouterr()

    dry_review = tmp_path / "dry_review.jsonl"
    assert main([*command[:-2], "--output", str(dry_review), "--dry-run"]) == 0
    capsys.readouterr()
    assert not dry_review.exists()

    assert main(command) == 0
    capsys.readouterr()
    first = review.read_bytes()
    records = [
        json.loads(line)
        for line in review.read_text(encoding="utf-8").splitlines()
    ]
    assert records[0]["scope"] == "all"
    assert main(command) == 1
    assert "use --replace" in capsys.readouterr().err
    assert review.read_bytes() == first

    assert main([*command, "--replace"]) == 0
    capsys.readouterr()
    assert review.read_bytes() == first

    records[1].update({
        "decision": "keep_natural",
        "reason": "The gloss directly expresses this reviewed learner meaning without source-shaped expansion.",
        "reviewer": "test-reviewer",
        "reviewed_at": "2026-07-17",
        "approval": "approved",
    })
    _add_vietnamese_evidence(
        records[1],
        _vietnamese_candidate_from_registry(semantic_registry, records[1]),
    )
    _write_jsonl(review, records)
    assert main([*command, "--replace"]) == 0
    capsys.readouterr()
    refreshed = [
        json.loads(line)
        for line in review.read_text(encoding="utf-8").splitlines()
    ]
    assert refreshed[1] == records[1]


def test_cli_vietnamese_review_scaffold_can_reuse_a_separate_prior_ledger(
    tmp_path,
    capsys,
):
    audit, card_registry, semantic_registry = _vietnamese_audit_fixture(tmp_path)
    prior = tmp_path / "prior-review.jsonl"
    output = tmp_path / "current-review.jsonl"
    base = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "vietnamese-review-scaffold",
        "--semantic-registry", str(semantic_registry),
    ]

    assert main([*base, "--output", str(prior)]) == 0
    capsys.readouterr()
    records = [json.loads(line) for line in prior.read_text(encoding="utf-8").splitlines()]
    records[1].update({
        "decision": "keep_natural",
        "reason": "The gloss directly expresses this reviewed learner meaning without source-shaped expansion.",
        "reviewer": "test-reviewer",
        "reviewed_at": "2026-07-23",
        "approval": "approved",
    })
    _add_vietnamese_evidence(
        records[1],
        _vietnamese_candidate_from_registry(semantic_registry, records[1]),
    )
    _write_jsonl(prior, records)

    assert main([
        *base,
        "--output", str(output),
        "--existing-review", str(prior),
    ]) == 0
    capsys.readouterr()
    refreshed = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert refreshed[1] == records[1]


def test_cli_apply_vietnamese_review_failures_are_transactional(tmp_path, capsys):
    audit, card_registry, semantic_registry = _vietnamese_audit_fixture(tmp_path)
    review = tmp_path / "review.jsonl"
    scaffold_command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "vietnamese-review-scaffold",
        "--semantic-registry", str(semantic_registry),
        "--output", str(review),
    ]
    assert main(scaffold_command) == 0
    capsys.readouterr()
    scaffold_bytes = review.read_bytes()
    audit_before = audit.read_bytes()
    apply_command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "apply-vietnamese-review",
        "--semantic-registry", str(semantic_registry),
        "--input", str(review),
    ]

    assert main(apply_command) == 1
    assert "review_open_decision" in capsys.readouterr().err
    assert audit.read_bytes() == audit_before

    review.write_bytes(scaffold_bytes)
    rows = _complete_vietnamese_review(review, semantic_registry)
    rows[0]["inputs"]["semantic_registry"] = "0" * 64
    _write_jsonl(review, rows)
    assert main(apply_command) == 1
    assert "review_stale_inputs" in capsys.readouterr().err
    assert audit.read_bytes() == audit_before

    review.write_bytes(scaffold_bytes)
    _complete_vietnamese_review(
        review,
        semantic_registry,
        proposed_vi="không | hợp lệ",
    )
    assert main(apply_command) == 1
    assert "review_invalid_proposed_vi" in capsys.readouterr().err
    assert audit.read_bytes() == audit_before


def test_cli_apply_vietnamese_review_changes_only_vi_and_review_metadata(
    tmp_path,
    capsys,
):
    audit, card_registry, semantic_registry = _vietnamese_audit_fixture(
        tmp_path,
        schema_version=2,
    )
    review = tmp_path / "review.jsonl"
    scaffold_command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "vietnamese-review-scaffold",
        "--semantic-registry", str(semantic_registry),
        "--output", str(review),
    ]
    assert main(scaffold_command) == 0
    capsys.readouterr()
    _complete_vietnamese_review(review, semantic_registry)

    before_rows = [
        json.loads(line)
        for line in audit.read_text(encoding="utf-8").splitlines()
    ]
    audit_before = audit.read_bytes()
    registry_rows = [
        json.loads(line)
        for line in semantic_registry.read_text(encoding="utf-8").splitlines()
    ]
    apply_command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "apply-vietnamese-review",
        "--semantic-registry", str(semantic_registry),
        "--input", str(review),
    ]

    assert main([*apply_command, "--dry-run"]) == 0
    dry_summary = json.loads(capsys.readouterr().out)
    assert dry_summary["rewrites"] == 1
    assert audit.read_bytes() == audit_before

    assert main(apply_command) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["rewrites"] == 1
    after_rows = [
        json.loads(line)
        for line in audit.read_text(encoding="utf-8").splitlines()
    ]

    expected_rows = copy.deepcopy(before_rows)
    expected_card = expected_rows[0]
    expected_sense = expected_card["semantic_senses"][0]
    registry_sense = registry_rows[0]["senses"][0]
    expected_sense["proposed"] = {
        "definition_en": registry_sense["definition_en"],
        "definition_vi": "đối thủ nặng ký",
        "examples": registry_sense["examples"],
    }
    expected_sense["checks"]["vietnamese_semantics"] = "repair"
    expected_sense["checks"]["simplicity"] = "repair"
    expected_sense.update({
        "decision": "repair_proposed",
        "review_reason": "Prefer a concise, idiomatic Vietnamese gloss.",
        "reviewer": "test-reviewer",
        "reviewed_at": "2026-07-16",
        "approval": "approved",
    })
    expected_card["coverage"]["status"] = "repair_proposed"
    assert after_rows == expected_rows
    assert after_rows[0]["source_coverage"] == before_rows[0]["source_coverage"]
    assert after_rows[0]["semantic_senses"][0]["source_sense_ids"] == registry_sense[
        "source_sense_ids"
    ]


def test_cli_sense_merge_audit_writes_report_and_fingerprint_scaffold(
    tmp_path,
    capsys,
):
    output = tmp_path / "audit.jsonl"
    markdown = tmp_path / "audit.md"
    review = tmp_path / "review.jsonl"
    command = [
        "sense-merge-audit",
        "--output", str(output),
        "--markdown", str(markdown),
        "--review-output", str(review),
    ]

    assert main(command) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["candidate_cards"] > 0
    assert summary["reviewed"] is False
    assert output.exists() and markdown.exists() and review.exists()
    report_rows = [
        json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()
    ]
    review_rows = [
        json.loads(line) for line in review.read_text(encoding="utf-8").splitlines()
    ]
    assert report_rows[0]["candidate_set_sha256"] == review_rows[0][
        "candidate_set_sha256"
    ]
    assert len(report_rows) == len(review_rows) == summary["candidate_cards"] + 1

    review_before = review.read_bytes()
    assert main(command) == 1
    assert "use --replace-review" in capsys.readouterr().err
    assert review.read_bytes() == review_before


def test_cli_sense_merge_audit_writes_approved_review_bundle(tmp_path, capsys):
    output = tmp_path / "audit.jsonl"
    markdown = tmp_path / "audit.md"
    review = tmp_path / "review.jsonl"
    bundle = tmp_path / "bundle.jsonl"
    scaffold_command = [
        "sense-merge-audit",
        "--output", str(output),
        "--markdown", str(markdown),
        "--review-output", str(review),
    ]
    assert main(scaffold_command) == 0
    capsys.readouterr()

    candidates = [
        json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()
    ][1:]
    reviews = [
        json.loads(line) for line in review.read_text(encoding="utf-8").splitlines()
    ]
    for row in reviews[1:]:
        row.update({
            "decision": "keep_separate",
            "confidence": "high",
            "reason": "The reviewed learner meanings remain distinct.",
        })
    candidate = candidates[0]
    candidate_review = next(
        row
        for row in reviews[1:]
        if row["candidate_id"] == candidate["candidate_id"]
    )
    candidate_review.update({
        "decision": "merge_candidate",
        "merge_groups": [{
            "semantic_sense_ids": [
                sense["semantic_sense_id"] for sense in candidate["senses"][:2]
            ],
            "definition_en": "one reviewed learner meaning",
            "definition_vi": "một nghĩa đã duyệt",
        }],
    })
    _write_jsonl(review, reviews)

    assert main([
        "sense-merge-audit",
        "--output", str(output),
        "--markdown", str(markdown),
        "--review-output", str(review),
        "--reviews", str(review),
        "--bundle-output", str(bundle),
        "--reviewer", "test-reviewer",
        "--reviewed-at", "2026-07-17",
        "--approval", "approved",
    ]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["bundle_cards"] == 1
    bundle_rows = [
        json.loads(line) for line in bundle.read_text(encoding="utf-8").splitlines()
    ]
    assert bundle_rows[0]["guid"] == candidate["guid"]
    assert bundle_rows[0]["remove_senses"]


def test_cli_sense_merge_bundle_requires_explicit_approval(tmp_path, capsys):
    assert main([
        "sense-merge-audit",
        "--bundle-output", str(tmp_path / "bundle.jsonl"),
        "--dry-run",
    ]) == 1
    assert "bundle_requires_reviews" in capsys.readouterr().err


def test_cli_sense_merge_audit_rejects_canonical_report_output(capsys):
    forbidden = Path(__file__).resolve().parents[2] / "data" / "review" / "forbidden.jsonl"

    assert main(["sense-merge-audit", "--output", str(forbidden), "--dry-run"]) == 1
    assert "report-only output" in capsys.readouterr().err
    assert not forbidden.exists()


def test_cli_sense_merge_audit_rejects_stale_registry_audit_pair(tmp_path, capsys):
    audit, card_registry, semantic_registry = _vietnamese_audit_fixture(
        tmp_path,
        schema_version=4,
    )
    deck_audit = tmp_path / "deck_audit.jsonl"
    overrides = tmp_path / "overrides.jsonl"
    _write_jsonl(deck_audit, [])
    _write_jsonl(overrides, [])
    command = [
        "--audit", str(audit),
        "--registry", str(card_registry),
        "sense-merge-audit",
        "--semantic-registry", str(semantic_registry),
        "--deck-audit", str(deck_audit),
        "--overrides", str(overrides),
        "--output", str(tmp_path / "audit-output.jsonl"),
        "--markdown", str(tmp_path / "audit-output.md"),
        "--review-output", str(tmp_path / "review-output.jsonl"),
        "--dry-run",
    ]

    assert main(command) == 0
    capsys.readouterr()

    registry_rows = [
        json.loads(line)
        for line in semantic_registry.read_text(encoding="utf-8").splitlines()
    ]
    registry_rows[0]["audit_sha256"] = "0" * 64
    _write_jsonl(semantic_registry, registry_rows)

    assert main(command) == 1
    assert "registry_audit_hash_mismatch" in capsys.readouterr().err
