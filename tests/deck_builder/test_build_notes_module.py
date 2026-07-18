import json
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.build_contracts import BuildNotesPaths
from src.deck_builder.build_issues import BuildValidationError
from src.deck_builder.build_notes import build_notes
from src.deck_builder.build_support import (
    parse_vocab_list,
    _resolve_audio_filename,
    lookup_gloss,
    resolve_primary_record,
)
import tools.build_notes
from src.deck_builder import build_command
from src.deck_builder.example_audio import referenced_example_audio_names


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _manual_row(word: str, cefr: str = "C1", list_name: str = "Oxford_3000") -> dict:
    return {
        "word": word,
        "cefr": cefr,
        "list": list_name,
        "variant": "",
        "definition": "take control",
        "example": "ex",
        "collocations": "",
        "wordfamily": "",
        "ipa": "/ipa/",
        "uk_audio": "",
        "us_audio": "",
        "source1": "Oxford",
        "source2": "Oxford",
        "idioms": "",
        "provenance": {"source": "build_contract_source_gap", "ledger_pos": "verb"},
        "synonyms": "",
        "antonyms": "",
        "tags": f"Source::Oxford CEFR::{cefr} CEFR::oxford {list_name}",
    }


def _registry_row(word: str, guid: str = "guid_conq", deck: str | None = None) -> dict:
    return {
        "word": word,
        "cefr": "C1",
        "list": "Oxford_3000",
        "variant": "",
        "pos": "verb",
        "guid": guid,
        "status": "active",
        "deck_override": deck,
    }


def _semantic_row(word: str = "conquer", guid: str = "guid_conq") -> dict:
    return {
        "schema_version": 4,
        "guid": guid,
        "word": word,
        "cefr": "C1",
        "list": "Oxford_3000",
        "variant": "",
        "pos": "verb",
        "audit_sha256": "a" * 64,
        "source_fingerprint": "b" * 64,
        "idiom_audit_sha256": "c" * 64,
        "vietnamese_review_sha256": "d" * 64,
        "semantic_policy_sha256": "e" * 64,
        "definition_review_sha256": "f" * 64,
        "sense_merge_review_sha256": "0" * 64,
        "idioms": [],
        "senses": [{
            "semantic_sense_id": "sem_conquer",
            "order": 1,
            "definition_en": "take control by force",
            "definition_vi": "chinh phục",
            "examples": ["They conquered the territory."],
            "source_sense_ids": ["ox_conquer"],
            "cambridge_match": "exact",
            "translation_provenance": "cambridge_reference",
        }],
    }


def _collocation_registry_row(word: str = "conquer", guid: str = "guid_conq") -> dict:
    return {
        "schema_version": 2,
        "guid": guid,
        "word": word,
        "cefr": "C1",
        "list": "Oxford_3000",
        "variant": "",
        "audit_sha256": "a" * 64,
        "audit_row_sha256": "b" * 64,
        "idiom_fingerprint": "c" * 64,
        "current_fingerprint": "d" * 64,
        "source_fingerprint": "e" * 64,
        "items": [],
        "empty_reason": "Reviewed: this fixture has no collocations.",
    }


def _setup_canonical_fixture(tmp_path: Path) -> BuildNotesPaths:
    source = tmp_path / "oxford.jsonl"
    source.write_text("", encoding="utf-8")
    gamma = tmp_path / "gamma.json"
    gamma.write_text('{"verdicts":[]}', encoding="utf-8")
    audit = tmp_path / "audit.jsonl"
    audit.write_text("", encoding="utf-8")
    ox3 = tmp_path / "ox3.md"
    ox3.write_text("| **conquer** | verb | C1 |\n", encoding="utf-8")
    ox5 = tmp_path / "ox5.md"
    ox5.write_text("", encoding="utf-8")
    awl = tmp_path / "awl.md"
    awl.write_text("", encoding="utf-8")
    audio = tmp_path / "audio"
    audio.mkdir()
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_jsonl(registry, [_registry_row("conquer")])
    _write_jsonl(manual, [_manual_row("conquer")])
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


def test_build_vocab_parser_normalizes_phrasal_verb(tmp_path: Path):
    path = tmp_path / "awl.md"
    path.write_text("| **derive** | phrasal v., v. | B2 | 1 |  |\n", encoding="utf-8")
    assert parse_vocab_list(path) == {
        ("derive", "phrasal verb", "B2"),
        ("derive", "verb", "B2"),
    }


def test_public_build_notes_uses_registry_manual_payload(tmp_path: Path):
    paths = _setup_canonical_fixture(tmp_path)
    result = build_notes(paths)
    assert result.built_cards_count == 1
    card = result.built_cards[0]
    assert card.guid == "guid_conq"
    assert card.deck == "English Academic Vocabulary::Oxford"
    assert card.definition == "take control"


def test_duplicate_registry_identity_fails_closed(tmp_path: Path):
    paths = _setup_canonical_fixture(tmp_path)
    _write_jsonl(paths.card_registry_path, [
        _registry_row("conquer", "guid1"),
        _registry_row("conquer", "guid2"),
    ])
    try:
        build_notes(paths)
    except BuildValidationError as exc:
        assert any(issue.code == "duplicate_key" for issue in exc.issues)
    else:
        raise AssertionError("duplicate registry identity should fail")


def test_manual_payload_is_preserved_verbatim(tmp_path: Path):
    paths = _setup_canonical_fixture(tmp_path)
    result = build_notes(paths)
    assert result.built_cards[0].example == "ex"
    assert result.built_cards[0].ipa == "/ipa/"


def test_audio_resolution_prefers_dictionary_audio_before_tts():
    available = {"tts_uk_craft.mp3", "oxford_uk_craft.mp3"}
    assert _resolve_audio_filename("craft", "noun", "uk", available) == "[sound:oxford_uk_craft.mp3]"


def test_generated_outputs_are_deterministic(tmp_path: Path):
    paths = _setup_canonical_fixture(tmp_path)
    assert build_notes(paths).jsonl_text == build_notes(paths).jsonl_text
    assert build_notes(paths).txt_text == build_notes(paths).txt_text


def test_lookup_gloss_parenthetical_match_first():
    audit = {
        ("counter (argue against)", "verb", "C1"): "oppose specifically",
        ("counter", "verb", "C1"): "ghost oppose",
    }
    assert lookup_gloss(audit, "counter (argue against)", "verb", "C1", "counter", ["verb"], "C1") == "oppose specifically"


def test_tools_build_notes_cli_dry_run_and_publish(tmp_path: Path, monkeypatch):
    paths = _setup_canonical_fixture(tmp_path)
    review_overrides = tmp_path / "review.jsonl"
    review_overrides.write_text("", encoding="utf-8")
    syn_overrides = tmp_path / "synonyms.jsonl"
    syn_overrides.write_text("", encoding="utf-8")
    ant_overrides = tmp_path / "antonyms.jsonl"
    ant_overrides.write_text("", encoding="utf-8")
    semantic_registry = tmp_path / "semantic_registry.jsonl"
    _write_jsonl(semantic_registry, [_semantic_row()])
    collocation_registry = tmp_path / "collocation_registry.jsonl"
    _write_jsonl(collocation_registry, [_collocation_registry_row()])
    out_jsonl = tmp_path / "anki_notes.jsonl"
    out_txt = tmp_path / "anki_notes.txt"

    monkeypatch.setattr(build_command, "paths_registry", ProjectPaths(tmp_path))
    monkeypatch.setattr(build_command, "OXFORD_3000_MD", paths.oxford_3000_md)
    monkeypatch.setattr(build_command, "OXFORD_5000_MD", paths.oxford_5000_md)
    monkeypatch.setattr(build_command, "AWL_MD", paths.awl_md)
    monkeypatch.setattr(build_command, "AUDIT_JSONL_PATH", paths.deck_audit_jsonl_path)
    monkeypatch.setattr(build_command, "AUDIO_DIR", paths.audio_dir)

    monkeypatch.setattr(sys, "argv", [
        "build_notes.py",
        "--dry-run",
        "--jsonl", str(paths.oxford_jsonl_path),
        "--out-jsonl", str(out_jsonl),
        "--out-txt", str(out_txt),
        "--gamma", str(paths.gamma_verdicts_path),
        "--card-registry", str(paths.card_registry_path),
        "--manual-cards", str(paths.manual_cards_path),
        "--review-overrides", str(review_overrides),
        "--synonym-overrides", str(syn_overrides),
        "--antonym-overrides", str(ant_overrides),
        "--semantic-registry", str(semantic_registry),
        "--collocation-registry", str(collocation_registry),
    ])
    assert tools.build_notes.main() == 0
    assert not out_jsonl.exists()

    result = build_notes(paths._replace(
        semantic_registry_path=semantic_registry,
        collocation_registry_path=collocation_registry,
    ))
    for name in referenced_example_audio_names(result.built_cards):
        (paths.audio_dir / name).write_bytes(b"ID3" + b"x" * 509)

    monkeypatch.setattr(sys, "argv", [
        "build_notes.py",
        "--jsonl", str(paths.oxford_jsonl_path),
        "--out-jsonl", str(out_jsonl),
        "--out-txt", str(out_txt),
        "--gamma", str(paths.gamma_verdicts_path),
        "--card-registry", str(paths.card_registry_path),
        "--manual-cards", str(paths.manual_cards_path),
        "--review-overrides", str(review_overrides),
        "--synonym-overrides", str(syn_overrides),
        "--antonym-overrides", str(ant_overrides),
        "--semantic-registry", str(semantic_registry),
        "--collocation-registry", str(collocation_registry),
    ])
    assert tools.build_notes.main() == 0
    assert out_jsonl.exists()
    assert out_txt.exists()


def test_production_build_cli_fails_closed_without_semantic_registry(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    paths = _setup_canonical_fixture(tmp_path)
    review_overrides = tmp_path / "review.jsonl"
    review_overrides.write_text("", encoding="utf-8")
    missing = tmp_path / "missing_semantic_registry.jsonl"

    monkeypatch.setattr(build_command, "paths_registry", ProjectPaths(tmp_path))
    assert build_command.main([
        "--dry-run",
        "--jsonl", str(paths.oxford_jsonl_path),
        "--gamma", str(paths.gamma_verdicts_path),
        "--card-registry", str(paths.card_registry_path),
        "--manual-cards", str(paths.manual_cards_path),
        "--review-overrides", str(review_overrides),
        "--semantic-registry", str(missing),
    ]) == 1
    assert "Semantic Registry file missing" in capsys.readouterr().err


def test_production_build_cli_fails_closed_without_collocation_registry(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    paths = _setup_canonical_fixture(tmp_path)
    review_overrides = tmp_path / "review.jsonl"
    review_overrides.write_text("", encoding="utf-8")
    semantic_registry = tmp_path / "semantic_registry.jsonl"
    _write_jsonl(semantic_registry, [_semantic_row()])
    missing = tmp_path / "missing_collocation_registry.jsonl"

    monkeypatch.setattr(build_command, "paths_registry", ProjectPaths(tmp_path))
    assert build_command.main([
        "--dry-run",
        "--jsonl", str(paths.oxford_jsonl_path),
        "--gamma", str(paths.gamma_verdicts_path),
        "--card-registry", str(paths.card_registry_path),
        "--manual-cards", str(paths.manual_cards_path),
        "--review-overrides", str(review_overrides),
        "--semantic-registry", str(semantic_registry),
        "--collocation-registry", str(missing),
    ]) == 1
    assert "Collocation Registry file missing" in capsys.readouterr().err


def test_resolve_primary_record_prefers_sole_contributor():
    records = [{"word": "curate", "pos": ["noun"]}, {"word": "curate", "pos": ["verb"]}]
    assert resolve_primary_record(records, [records[1]]) == records[1]
    assert resolve_primary_record(records, [records[0]]) == records[0]


def test_resolve_primary_record_defaults_to_first_without_contributors():
    first = {"word": "test", "pos": ["noun"]}
    second = {"word": "test", "pos": ["verb"]}
    assert resolve_primary_record([first, second], []) is first
