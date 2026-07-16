from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from src.deck_builder.build_contracts import BuildNotesResult, BuiltCard
from src.deck_builder.build_publisher import (
    PublishFault,
    publish_build_result_transactional,
    recover_publish_transactions,
)
from src.deck_builder.build_validation import serialize_jsonl, serialize_txt, sha256_file
from src.deck_builder.registry_build import load_registry_build_inputs


def _card(guid: str, word: str, definition: str) -> BuiltCard:
    return BuiltCard(
        guid,
        "English Academic Vocabulary Model",
        "Deck",
        word,
        "noun",
        "",
        definition,
        "",
        "",
        "",
        "",
        "",
        "Oxford",
        "Oxford",
        "A1",
        "",
        "Source::Oxford CEFR::A1 CEFR::oxford",
        "",
        "",
        cambridge_url=f"https://dictionary.cambridge.org/dictionary/english/{word}",
        oxford_pos_urls=f"https://www.oxfordlearnersdictionaries.com/definition/english/{word}_1",
    )


def _result(cards: list[BuiltCard]) -> BuildNotesResult:
    return BuildNotesResult(cards, serialize_jsonl(cards), serialize_txt(cards), 0, 0, 0, 0, 0, len(cards), 0)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _setup(tmp_path: Path):
    old_card = _card("g1", "word", "old")
    new_card = _card("g1", "word", "new")
    jsonl_path = tmp_path / "anki_notes.jsonl"
    txt_path = tmp_path / "anki_notes.txt"
    registry_path = tmp_path / "card_registry.jsonl"
    manual_path = tmp_path / "manual_cards.jsonl"
    audio_dir = tmp_path / "audio"
    staging_dir = tmp_path / ".staging"
    audio_dir.mkdir()
    jsonl_path.write_text(serialize_jsonl([old_card]), encoding="utf-8")
    txt_path.write_text(serialize_txt([old_card]), encoding="utf-8")
    _write_jsonl(registry_path, [{
        "word": "word",
        "cefr": "A1",
        "list": "NO_LIST",
        "variant": "",
        "pos": "noun",
        "guid": "g1",
        "status": "active",
        "deck_override": "Deck",
    }])
    _write_jsonl(manual_path, [])
    registry_inputs = load_registry_build_inputs(registry_path, manual_path)
    return old_card, new_card, jsonl_path, txt_path, registry_path, registry_inputs, audio_dir, staging_dir


def _hash_pair(jsonl_path: Path, txt_path: Path) -> tuple[str, str]:
    return sha256_file(jsonl_path), sha256_file(txt_path)


def test_transactional_publish_commits_pair(tmp_path: Path):
    _, new_card, jsonl_path, txt_path, registry_path, registry_inputs, audio_dir, staging_dir = _setup(tmp_path)

    report = publish_build_result_transactional(
        _result([new_card]),
        jsonl_path,
        txt_path,
        registry_inputs,
        registry_path,
        audio_dir,
        staging_dir,
    )

    assert report.ok
    assert "new" in jsonl_path.read_text(encoding="utf-8")
    assert "new" in txt_path.read_text(encoding="utf-8")
    assert not any(staging_dir.glob("txn-*"))
    assert not (staging_dir / "publish.lock").exists()


@pytest.mark.parametrize("fault_at", [
    "staged_write",
    "staged_validation",
    "backup_creation",
    "after_jsonl_replace",
    "after_txt_replace",
    "hash_verification",
    "journal_update",
])
def test_transactional_publish_fault_restores_old_pair(tmp_path: Path, fault_at: str):
    _, new_card, jsonl_path, txt_path, registry_path, registry_inputs, audio_dir, staging_dir = _setup(tmp_path)
    old_hashes = _hash_pair(jsonl_path, txt_path)

    with pytest.raises(PublishFault):
        publish_build_result_transactional(
            _result([new_card]),
            jsonl_path,
            txt_path,
            registry_inputs,
            registry_path,
            audio_dir,
            staging_dir,
            fault_at=fault_at,
        )

    assert _hash_pair(jsonl_path, txt_path) == old_hashes


@pytest.mark.parametrize("state", ["prepared", "jsonl_replaced", "txt_replaced"])
def test_recover_publish_transactions_restores_precommitted_states(tmp_path: Path, state: str):
    old_card, new_card, jsonl_path, txt_path, _, _, _, staging_dir = _setup(tmp_path)
    old_hashes = _hash_pair(jsonl_path, txt_path)
    txn_dir = staging_dir / "txn-test"
    old_dir = txn_dir / "old"
    old_dir.mkdir(parents=True)
    (txn_dir / "new").mkdir()
    shutil.copy2(jsonl_path, old_dir / "anki_notes.jsonl")
    shutil.copy2(txt_path, old_dir / "anki_notes.txt")
    staged_jsonl = serialize_jsonl([new_card])
    staged_txt = serialize_txt([new_card])
    (txn_dir / "new" / "anki_notes.jsonl").write_text(staged_jsonl, encoding="utf-8")
    (txn_dir / "new" / "anki_notes.txt").write_text(staged_txt, encoding="utf-8")

    if state in {"jsonl_replaced", "txt_replaced"}:
        jsonl_path.write_text(staged_jsonl, encoding="utf-8")
    if state == "txt_replaced":
        txt_path.write_text(staged_txt, encoding="utf-8")

    journal = {
        "schema_version": 1,
        "transaction_id": "txn-test",
        "state": state,
        "targets": {
            "anki_notes.jsonl": str(jsonl_path),
            "anki_notes.txt": str(txt_path),
        },
        "old": {
            "anki_notes.jsonl": {"exists": True, "sha256": old_hashes[0]},
            "anki_notes.txt": {"exists": True, "sha256": old_hashes[1]},
        },
        "staged": {
            "anki_notes.jsonl": {"sha256": "unused"},
            "anki_notes.txt": {"sha256": "unused"},
        },
    }
    (txn_dir / "journal.json").write_text(json.dumps(journal), encoding="utf-8")

    recover_publish_transactions(staging_dir)

    assert _hash_pair(jsonl_path, txt_path) == old_hashes
    assert not txn_dir.exists()


def test_recover_publish_transactions_removes_stale_lock_without_journal(tmp_path: Path):
    staging_dir = tmp_path / ".staging"
    staging_dir.mkdir()
    lock = staging_dir / "publish.lock"
    lock.write_text(str(os.getpid()), encoding="utf-8")
    (staging_dir / "txn-empty").mkdir()

    recover_publish_transactions(staging_dir)

    assert not lock.exists()
    assert not (staging_dir / "txn-empty").exists()
