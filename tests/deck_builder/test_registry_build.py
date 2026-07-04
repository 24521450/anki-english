from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.deck_builder.build_issues import BuildValidationError
from src.deck_builder.registry_build import load_registry_build_inputs


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _registry_row(word: str, status: str = "active") -> dict:
    return {
        "word": word,
        "cefr": "A1",
        "list": "NO_LIST",
        "variant": "",
        "pos": "noun",
        "guid": f"guid-{word}",
        "status": status,
        "deck_override": "Deck",
    }


def _manual_row(word: str) -> dict:
    return {
        "word": word,
        "cefr": "A1",
        "list": "NO_LIST",
        "variant": "",
        "definition": "definition",
        "example": "",
        "collocations": "",
        "wordfamily": "",
        "ipa": "",
        "uk_audio": "",
        "us_audio": "",
        "source1": "Oxford",
        "source2": "Oxford",
        "idioms": "",
        "provenance": {"source": "build_contract_source_gap", "ledger_pos": "noun"},
    }


def test_load_registry_build_inputs_rejects_unknown_manual_key(tmp_path: Path):
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_jsonl(registry, [_registry_row("known")])
    _write_jsonl(manual, [_manual_row("unknown")])

    with pytest.raises(BuildValidationError) as excinfo:
        load_registry_build_inputs(registry, manual)

    assert any(issue.code == "manual_unknown_registry_key" for issue in excinfo.value.issues)


def test_load_registry_build_inputs_rejects_retired_manual_key(tmp_path: Path):
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_jsonl(registry, [_registry_row("old", status="retired")])
    _write_jsonl(manual, [_manual_row("old")])

    with pytest.raises(BuildValidationError) as excinfo:
        load_registry_build_inputs(registry, manual)

    assert any(issue.code == "manual_retired_registry_key" for issue in excinfo.value.issues)


def test_load_registry_build_inputs_keeps_active_file_order(tmp_path: Path):
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_jsonl(registry, [_registry_row("first"), _registry_row("old", "retired"), _registry_row("second")])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)

    assert [target.identity.word for target in inputs.targets] == ["first", "second"]


def test_public_build_notes_uses_registry_without_txt(tmp_path: Path):
    from src.deck_builder.build_contracts import BuildNotesPaths
    from src.deck_builder.build_notes import build_notes

    source = tmp_path / "oxford.jsonl"
    source.write_text("", encoding="utf-8")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    gamma = tmp_path / "gamma.json"
    audit = tmp_path / "audit.jsonl"
    ox3 = tmp_path / "ox3.md"
    ox5 = tmp_path / "ox5.md"
    awl = tmp_path / "awl.md"
    audio = tmp_path / "audio"
    audio.mkdir()
    gamma.write_text('{"verdicts":[]}', encoding="utf-8")
    audit.write_text("", encoding="utf-8")
    ox3.write_text("", encoding="utf-8")
    ox5.write_text("", encoding="utf-8")
    awl.write_text("", encoding="utf-8")
    _write_jsonl(registry, [_registry_row("word")])
    _write_jsonl(manual, [_manual_row("word")])

    result = build_notes(BuildNotesPaths(
        oxford_jsonl_path=source,
        deck_audit_jsonl_path=audit,
        gamma_verdicts_path=gamma,
        oxford_3000_md=ox3,
        oxford_5000_md=ox5,
        awl_md=awl,
        audio_dir=audio,
        card_registry_path=registry,
        manual_cards_path=manual,
    ))

    assert result.built_cards_count == 1
    assert result.built_cards[0].definition == "definition"
