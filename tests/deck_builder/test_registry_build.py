from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.deck_builder.build_issues import BuildValidationError
from src.deck_builder.build_contracts import BuildNotesPaths
from src.deck_builder.build_notes import build_notes
from src.deck_builder.registry_build import load_registry_build_inputs
from src.deck_builder.idiom_audit import idiom_source_fingerprint


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


def _semantic_row(word: str, *, idioms: list[dict] | None = None) -> dict:
    return {
        "schema_version": 2,
        "guid": f"guid-{word}",
        "word": word,
        "cefr": "A1",
        "list": "NO_LIST",
        "variant": "",
        "pos": "noun",
        "audit_sha256": "a" * 64,
        "source_fingerprint": "b" * 64,
        "idiom_audit_sha256": "c" * 64,
        "idioms": list(idioms or []),
        "senses": [{
            "semantic_sense_id": f"sem_{word}",
            "order": 1,
            "definition_en": "reviewed definition",
            "definition_vi": "nghĩa đã duyệt",
            "examples": ["Reviewed example."],
            "source_sense_ids": [f"ox_{word}"],
            "cambridge_match": "exact",
            "translation_provenance": "cambridge_reference",
        }],
    }


def _build_fixture_paths(tmp_path: Path) -> BuildNotesPaths:
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
    manual_row = _manual_row("word")
    manual_row.update({
        "definition": "legacy definition",
        "example": "Legacy example (former).",
        "collocations": "word choice",
        "ipa": "/wɜːd/",
        "synonyms": "former",
        "antonyms": "",
    })
    _write_jsonl(manual, [manual_row])
    return BuildNotesPaths(
        oxford_jsonl_path=source,
        deck_audit_jsonl_path=audit,
        gamma_verdicts_path=gamma,
        oxford_3000_md=ox3,
        oxford_5000_md=ox5,
        awl_md=awl,
        audio_dir=audio,
        card_registry_path=registry,
        manual_cards_path=manual,
    )


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


def test_semantic_registry_overlays_content_before_audio_and_preserves_metadata(
    tmp_path: Path,
):
    paths = _build_fixture_paths(tmp_path)
    semantic_registry = tmp_path / "semantic_registry.jsonl"
    _write_jsonl(semantic_registry, [_semantic_row("word")])

    legacy_card = build_notes(paths).built_cards[0]
    card = build_notes(paths._replace(
        semantic_registry_path=semantic_registry,
    )).built_cards[0]

    assert card.definition == "reviewed definition (nghĩa đã duyệt)"
    assert card.example == "Reviewed example."
    assert card.example_audio_uk != legacy_card.example_audio_uk
    assert card.example_audio_us != legacy_card.example_audio_us
    assert card.ipa == legacy_card.ipa == "/wɜːd/"
    assert card.collocations == legacy_card.collocations == "word choice"
    assert card.deck == legacy_card.deck
    assert card.tags == legacy_card.tags
    # The reviewed example no longer renders the manual relation annotation.
    assert card.synonyms == ""
    assert card.antonyms == ""


def test_semantic_registry_overlays_manual_idiom_before_audio_planning(tmp_path: Path):
    paths = _build_fixture_paths(tmp_path)
    source_explanation = "you must take risks to achieve something"
    example = "Nothing ventured, nothing gained."
    manual = json.loads(paths.manual_cards_path.read_text(encoding="utf-8"))
    manual["idioms"] = (
        f"nothing ventured, nothing gained :: {source_explanation} :: {example}"
    )
    _write_jsonl(paths.manual_cards_path, [manual])
    idiom = {
        "idiom_id": "idm_" + "1" * 24,
        "order": 1,
        "source_fingerprint": idiom_source_fingerprint(
            "nothing ventured, nothing gained", source_explanation, [example]
        ),
        "phrase_en": "nothing ventured, nothing gained",
        "display_mode": "vi_equivalent",
        "explanation_en": source_explanation,
        "explanation_vi": "Không vào hang cọp, sao bắt được cọp con",
        "examples": [example],
        "translation_provenance": "reviewer_derived",
    }
    semantic_registry = tmp_path / "semantic_registry.jsonl"
    _write_jsonl(semantic_registry, [_semantic_row("word", idioms=[idiom])])

    card = build_notes(paths._replace(
        semantic_registry_path=semantic_registry,
    )).built_cards[0]

    assert card.idioms == manual["idioms"]
    assert card.idiom_meaning_vi == (
        "vi_equivalent :: Không vào hang cọp, sao bắt được cọp con"
    )
    assert card.idiom_example_audio_uk
    assert card.idiom_example_audio_us


def test_semantic_registry_validation_failure_is_a_build_validation_error(
    tmp_path: Path,
):
    paths = _build_fixture_paths(tmp_path)
    semantic_registry = tmp_path / "semantic_registry.jsonl"
    _write_jsonl(semantic_registry, [])

    with pytest.raises(BuildValidationError) as excinfo:
        build_notes(paths._replace(semantic_registry_path=semantic_registry))

    assert any(
        issue.code == "semantic_registry_invalid"
        for issue in excinfo.value.issues
    )


def test_specified_cambridge_source_must_be_readable(tmp_path: Path):
    paths = _build_fixture_paths(tmp_path)._replace(
        cambridge_jsonl_path=tmp_path / "missing-cambridge.jsonl",
    )

    with pytest.raises(BuildValidationError) as excinfo:
        build_notes(paths)

    assert any(
        issue.code == "source_json_unreadable" for issue in excinfo.value.issues
    )
