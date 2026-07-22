from __future__ import annotations

import json
from pathlib import Path

from tests.deck_builder.test_card_identity_split import (
    _bundle,
    _card,
    _oxford,
    _registry,
    _reviewed_audit,
    _write_jsonl,
)
from tools.card_identity_split import main


def test_cli_apply_review_dry_run_does_not_write(tmp_path: Path):
    registry = tmp_path / "card_registry.jsonl"
    audit = tmp_path / "semantic_audit.jsonl"
    notes = tmp_path / "notes.jsonl"
    oxford = tmp_path / "oxford.jsonl"
    cambridge = tmp_path / "cambridge.jsonl"
    review = tmp_path / "review.jsonl"
    projection = tmp_path / "projection.jsonl"
    _write_jsonl(registry, [_registry()])
    _write_jsonl(audit, [_reviewed_audit()])
    _write_jsonl(notes, [_card()])
    _write_jsonl(oxford, _oxford())
    _write_jsonl(cambridge, [])
    _write_jsonl(review, [_bundle()])
    before = {path: path.read_bytes() for path in (registry, audit, notes)}

    assert main([
        "apply-review",
        "--input",
        str(review),
        "--registry",
        str(registry),
        "--audit",
        str(audit),
        "--notes",
        str(notes),
        "--oxford",
        str(oxford),
        "--cambridge",
        str(cambridge),
        "--projection-output",
        str(projection),
        "--dry-run",
    ]) == 0

    assert {path: path.read_bytes() for path in (registry, audit, notes)} == before
    assert not projection.exists()


def test_cli_apply_review_writes_projection_and_is_idempotent(tmp_path: Path):
    registry = tmp_path / "card_registry.jsonl"
    audit = tmp_path / "semantic_audit.jsonl"
    notes = tmp_path / "notes.jsonl"
    oxford = tmp_path / "oxford.jsonl"
    cambridge = tmp_path / "cambridge.jsonl"
    review = tmp_path / "review.jsonl"
    projection = tmp_path / "projection.jsonl"
    _write_jsonl(registry, [_registry()])
    _write_jsonl(audit, [_reviewed_audit()])
    _write_jsonl(notes, [_card()])
    _write_jsonl(oxford, _oxford())
    _write_jsonl(cambridge, [])
    _write_jsonl(review, [_bundle()])
    command = [
        "apply-review",
        "--input",
        str(review),
        "--registry",
        str(registry),
        "--audit",
        str(audit),
        "--notes",
        str(notes),
        "--oxford",
        str(oxford),
        "--cambridge",
        str(cambridge),
        "--projection-output",
        str(projection),
    ]

    assert main(command) == 0
    first = (registry.read_bytes(), audit.read_bytes(), projection.read_bytes())
    assert len([
        json.loads(line)
        for line in projection.read_text(encoding="utf-8").splitlines()
    ]) == 2

    assert main(command) == 0
    assert (registry.read_bytes(), audit.read_bytes(), projection.read_bytes()) == first
