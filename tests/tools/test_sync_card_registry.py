from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.deck_builder.build_issues import BuildValidationError
from src.deck_builder.card_registry import (
    bootstrap_registry_rows,
    serialize_registry_rows,
    validate_registry_or_raise,
    validate_registry_rows,
)
import tools.sync_card_registry as sync_card_registry


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_bootstrap_registry_rows_canonicalize_awl_and_reviewed_variants(tmp_path: Path):
    notes = tmp_path / "anki_notes.jsonl"
    _write_jsonl(
        notes,
        [
            {
                "guid": "g1",
                "word": "converse",
                "pos": "verb",
                "cefr": "UNCLASSIFIED",
                "deck": "English Academic Vocabulary::AWL 50 Academic Words",
                "tags": "Source::Oxford CEFR::UNCLASSIFIED CEFR::oxford AWL_Coxhead",
            },
            {
                "guid": "g2",
                "word": "converse",
                "pos": "adjective, noun",
                "cefr": "UNCLASSIFIED",
                "deck": "English Academic Vocabulary::AWL 50 Academic Words",
                "tags": "Source::Oxford CEFR::UNCLASSIFIED CEFR::oxford AWL_Coxhead",
            },
        ],
    )

    rows = bootstrap_registry_rows(notes)
    assert rows == [
        {
            "word": "converse",
            "cefr": "UNCLASSIFIED",
            "list": "AWL",
            "variant": "verb",
            "pos": "verb",
            "guid": "g1",
            "status": "active",
            "deck_override": None,
        },
        {
            "word": "converse",
            "cefr": "UNCLASSIFIED",
            "list": "AWL",
            "variant": "adjective, noun",
            "pos": "adjective, noun",
            "guid": "g2",
            "status": "active",
            "deck_override": None,
        },
    ]


def test_validate_registry_rows_rejects_missing_deck_override_for_no_list():
    issues = validate_registry_rows([
        {
            "word": "orphan",
            "cefr": "UNCLASSIFIED",
            "list": "NO_LIST",
            "variant": "",
            "pos": "noun",
            "guid": "g1",
            "status": "active",
            "deck_override": None,
        }
    ])
    assert any(issue.code == "missing_deck_override" for issue in issues)


def test_validate_registry_or_raise_reports_duplicate_guid():
    rows = [
        {
            "word": "a",
            "cefr": "A1",
            "list": "NO_LIST",
            "variant": "",
            "pos": "noun",
            "guid": "dup",
            "status": "active",
            "deck_override": "Deck A",
        },
        {
            "word": "b",
            "cefr": "A1",
            "list": "NO_LIST",
            "variant": "",
            "pos": "noun",
            "guid": "dup",
            "status": "active",
            "deck_override": "Deck B",
        },
    ]
    with pytest.raises(BuildValidationError):
        validate_registry_or_raise(rows)


def test_sync_card_registry_bootstrap_check_and_sync(tmp_path: Path):
    notes = tmp_path / "anki_notes.jsonl"
    registry = tmp_path / "card_registry.jsonl"
    _write_jsonl(
        notes,
        [
            {
                "guid": "g1",
                "word": "converse",
                "pos": "verb",
                "cefr": "UNCLASSIFIED",
                "deck": "English Academic Vocabulary::AWL 50 Academic Words",
                "tags": "Source::Oxford CEFR::UNCLASSIFIED CEFR::oxford AWL_Coxhead",
            }
        ],
    )

    assert sync_card_registry.main([
        "--bootstrap-from-build",
        "--notes-jsonl",
        str(notes),
        "--registry",
        str(registry),
    ]) == 0
    assert registry.exists()

    assert sync_card_registry.main([
        "--check",
        "--registry",
        str(registry),
    ]) == 0

    assert sync_card_registry.main([
        "--sync",
        "--registry",
        str(registry),
    ]) == 0


def test_sync_card_registry_check_ignores_missing_build_output(tmp_path: Path):
    registry = tmp_path / "card_registry.jsonl"
    _write_jsonl(
        registry,
        [
            {
                "word": "x",
                "cefr": "A1",
                "list": "NO_LIST",
                "variant": "",
                "pos": "noun",
                "guid": "g1",
                "status": "active",
                "deck_override": "Deck X",
            }
        ],
    )

    assert sync_card_registry.main(["--check", "--registry", str(registry)]) == 0


def test_sync_card_registry_sync_reports_missing_vocab_identity(tmp_path: Path):
    registry = tmp_path / "card_registry.jsonl"
    _write_jsonl(
        registry,
        [
            {
                "word": "not-in-vocab",
                "cefr": "C1",
                "list": "Oxford_5000",
                "variant": "",
                "pos": "noun",
                "guid": "g1",
                "status": "active",
                "deck_override": None,
            }
        ],
    )

    assert sync_card_registry.main(["--sync", "--registry", str(registry)]) == 0
