from __future__ import annotations

import json
from pathlib import Path

from src.deck_builder.build_contracts import BuildNotesResult, BuiltCard
from src.deck_builder.build_validation import (
    CANONICAL_TXT_HEADER,
    serialize_jsonl,
    serialize_txt,
    validate_artifact_paths,
    validate_build_result,
)
from src.deck_builder.registry_build import load_registry_build_inputs
from src.deck_builder.example_audio import plan_cards_example_audio, referenced_example_audio_names


def _card(guid: str = "g1", audio: str = "") -> BuiltCard:
    return BuiltCard(
        guid,
        "English Academic Vocabulary Model",
        "Deck",
        "word",
        "noun",
        "",
        "definition",
        "example",
        "",
        "",
        audio,
        "",
        "Oxford",
        "Oxford",
        "A1",
        "",
        "Source::Oxford CEFR::A1 CEFR::oxford",
        "",
        "",
    )


def _result(cards: list[BuiltCard]) -> BuildNotesResult:
    cards, _ = plan_cards_example_audio(cards)
    return BuildNotesResult(cards, serialize_jsonl(cards), serialize_txt(cards), 0, 0, 0, 0, 0, len(cards), 0)


def _result_with_audio(cards: list[BuiltCard], audio_dir: Path) -> BuildNotesResult:
    result = _result(cards)
    for filename in referenced_example_audio_names(result.built_cards):
        (audio_dir / filename).write_bytes(b"ID3" + b"x" * 509)
    return result


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_registry(path: Path, cards: list[BuiltCard]) -> None:
    rows = [
        {
            "word": card.word,
            "cefr": card.cefr,
            "list": "NO_LIST",
            "variant": "",
            "pos": card.pos,
            "guid": card.guid,
            "status": "active",
            "deck_override": card.deck,
        }
        for card in cards
    ]
    _write_jsonl(path, rows)


def _write_artifacts(tmp_path: Path, cards: list[BuiltCard]) -> tuple[Path, Path, Path, Path]:
    cards, _ = plan_cards_example_audio(cards)
    jsonl_path = tmp_path / "anki_notes.jsonl"
    txt_path = tmp_path / "anki_notes.txt"
    registry_path = tmp_path / "card_registry.jsonl"
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    jsonl_path.write_text(serialize_jsonl(cards), encoding="utf-8")
    txt_path.write_text(serialize_txt(cards), encoding="utf-8")
    _write_registry(registry_path, cards)
    return jsonl_path, txt_path, registry_path, audio_dir


def test_validate_build_result_accepts_valid_result(tmp_path: Path):
    card = _card()
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok
    assert report.card_count == 1


def test_validate_build_result_rejects_single_example_break(tmp_path: Path):
    card = _card()._replace(example="first example<br>second example")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(issue.code == "noncanonical_example_break" for issue in report.issues)


def test_validate_build_result_accepts_double_example_break(tmp_path: Path):
    card = _card()._replace(example="first example<br><br>second example")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok


def test_validate_build_result_rejects_unrenderable_relation_metadata(tmp_path: Path):
    card = _card()._replace(example="The result was clear.", synonyms="plain")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(
        issue.code == "relation_metadata_unrepresented" for issue in report.issues
    )


def test_validate_build_result_accepts_idiom_only_card(tmp_path: Path):
    card = _card()._replace(
        definition="",
        example="",
        idioms="phrase :: meaning :: example",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok


def test_validate_build_result_rejects_more_than_two_idioms(tmp_path: Path):
    card = _card()._replace(
        idioms=(
            "first :: meaning :: example$$"
            "second :: meaning :: example$$"
            "third :: meaning :: example"
        )
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(issue.code == "idiom_limit_exceeded" for issue in report.issues)


def test_validate_artifact_paths_rejects_txt_field_drift(tmp_path: Path):
    card = _card()
    jsonl_path, txt_path, registry_path, audio_dir = _write_artifacts(tmp_path, [card])
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    parts = lines[len(CANONICAL_TXT_HEADER)].split("\t")
    parts[6] = "changed"
    lines[len(CANONICAL_TXT_HEADER)] = "\t".join(parts)
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = validate_artifact_paths(jsonl_path, txt_path, registry_path, audio_dir)

    assert not report.ok
    assert any(issue.code == "artifact_field_mismatch" for issue in report.issues)


def test_validate_artifact_paths_rejects_duplicate_guid(tmp_path: Path):
    first = _card("dup")
    second = _card("dup")._replace(word="word2")
    jsonl_path, txt_path, registry_path, audio_dir = _write_artifacts(tmp_path, [first, second])

    report = validate_artifact_paths(jsonl_path, txt_path, registry_path, audio_dir)

    assert not report.ok
    assert any(issue.code == "duplicate_guid" for issue in report.issues)


def test_validate_artifact_paths_rejects_missing_registry_card(tmp_path: Path):
    card = _card()
    jsonl_path, txt_path, registry_path, audio_dir = _write_artifacts(tmp_path, [card])
    _write_jsonl(registry_path, [])

    report = validate_artifact_paths(jsonl_path, txt_path, registry_path, audio_dir)

    assert not report.ok
    assert any(issue.code in {"unknown_registry_identity", "registry_coverage_order_mismatch"} for issue in report.issues)


def test_validate_artifact_paths_rejects_missing_audio(tmp_path: Path):
    card = _card(audio="[sound:missing.mp3]")
    jsonl_path, txt_path, registry_path, audio_dir = _write_artifacts(tmp_path, [card])

    report = validate_artifact_paths(jsonl_path, txt_path, registry_path, audio_dir)

    assert not report.ok
    assert any(issue.code == "audio_missing_reference" for issue in report.issues)
