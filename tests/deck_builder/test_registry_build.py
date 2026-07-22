from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from src.deck_builder.build_issues import BuildValidationError
from src.deck_builder.build_contracts import BuildNotesPaths, BuiltCard
from src.deck_builder.build_notes import build_notes
from src.deck_builder.registry_build import (
    _apply_pronunciation_authorities,
    load_registry_build_inputs,
)
from src.deck_builder.idiom_audit import idiom_source_fingerprint
from src.deck_builder.pronunciation_resolution import (
    pronunciation_media_fingerprint,
    selection_fingerprint,
)


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
        "schema_version": 4,
        "guid": f"guid-{word}",
        "word": word,
        "cefr": "A1",
        "list": "NO_LIST",
        "variant": "",
        "pos": "noun",
        "audit_sha256": "a" * 64,
        "source_fingerprint": "b" * 64,
        "idiom_audit_sha256": "c" * 64,
        "vietnamese_review_sha256": "d" * 64,
        "semantic_policy_sha256": "e" * 64,
        "definition_review_sha256": "f" * 64,
        "sense_merge_review_sha256": "0" * 64,
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


def _collocation_registry_row(word: str) -> dict:
    return {
        "schema_version": 2,
        "guid": f"guid-{word}",
        "word": word,
        "cefr": "A1",
        "list": "NO_LIST",
        "variant": "",
        "audit_sha256": "a" * 64,
        "audit_row_sha256": "b" * 64,
        "idiom_fingerprint": "c" * 64,
        "current_fingerprint": "d" * 64,
        "source_fingerprint": "e" * 64,
        "items": [
            {
                "text": "on the word",
                "order": 1,
                "source": "oxford",
                "evidence_ids": ["evidence-1"],
            },
            {
                "text": "word choice",
                "order": 2,
                "source": "curated",
                "evidence_ids": [],
            },
        ],
        "empty_reason": "",
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
        allow_legacy_pronunciation_for_tests=True,
    )


def test_pronunciation_authorities_replace_manual_ipa_audio_and_bind_media(
    tmp_path: Path,
):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    media = b"authoritative pronunciation bytes"
    filename = "cambridge_uk_word.mp3"
    (audio_dir / filename).write_bytes(media)
    fingerprint = selection_fingerprint(
        "cambridge",
        "word",
        "uk",
        "wɜːd",
        "/media/uk.mp3",
        dictionary_id="word",
        entry_id="entry-1",
        headword="word",
        pos=["noun"],
    )
    source_records = [{
        "schema_version": 3,
        "source": "cambridge",
        "word": "word",
        "pronunciations": [{
            "source_file": "cambridge_word.html",
            "dictionary_id": "word",
            "dictionary_rank": 0,
            "entry_id": "entry-1",
            "entry_index": 1,
            "headword": "word",
            "pos": ["noun"],
            "uk": {"ipa": "wɜːd", "audio_url": "/media/uk.mp3"},
            "us": {"ipa": "wɝːd", "audio_url": "/media/us.mp3"},
        }],
    }]
    us_fingerprint = selection_fingerprint(
        "cambridge",
        "word",
        "us",
        "wɝːd",
        "/media/us.mp3",
        dictionary_id="word",
        entry_id="entry-1",
        headword="word",
        pos=["noun"],
    )
    us_filename = "cambridge_us_word.mp3"
    (audio_dir / us_filename).write_bytes(media)
    manifest = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest, [
        {
            "schema_version": 2,
            "selection_fingerprint": fingerprint,
            "media_fingerprint": pronunciation_media_fingerprint(
                "cambridge", "word", "uk", "wɜːd", "/media/uk.mp3"
            ),
            "source": "cambridge",
            "parent_word": "word",
            "dictionary_id": "word",
            "entry_id": "entry-1",
            "headword": "word",
            "pos": ["noun"],
            "accent": "uk",
            "ipa": "wɜːd",
            "audio_url": "/media/uk.mp3",
            "filename": filename,
            "sha256": hashlib.sha256(media).hexdigest(),
            "byte_count": len(media),
        },
        {
            "schema_version": 2,
            "selection_fingerprint": us_fingerprint,
            "media_fingerprint": pronunciation_media_fingerprint(
                "cambridge", "word", "us", "wɝːd", "/media/us.mp3"
            ),
            "source": "cambridge",
            "parent_word": "word",
            "dictionary_id": "word",
            "entry_id": "entry-1",
            "headword": "word",
            "pos": ["noun"],
            "accent": "us",
            "ipa": "wɝːd",
            "audio_url": "/media/us.mp3",
            "filename": us_filename,
            "sha256": hashlib.sha256(media).hexdigest(),
            "byte_count": len(media),
        },
    ])
    locks = tmp_path / "locks.jsonl"
    locks.write_text("", encoding="utf-8")
    card = BuiltCard(
        guid="guid-word",
        notetype="English Academic Vocabulary Model",
        deck="Deck",
        word="word",
        pos="noun",
        ipa="/legacy/",
        definition="definition",
        example="example",
        collocations="",
        wordfamily="",
        uk_audio="[sound:legacy_uk.mp3]",
        us_audio="[sound:legacy_us.mp3]",
        source1="Oxford",
        source2="Oxford",
        cefr="A1",
        idioms="",
        tags="Source::Oxford Audio::Legacy",
        synonyms="",
        antonyms="",
    )

    [resolved] = _apply_pronunciation_authorities(
        [card],
        source_records=source_records,
        locks_path=locks,
        manifest_path=manifest,
        audio_dir=audio_dir,
    )

    assert resolved.ipa == "UK: /wɜːd/ | US: /wɝːd/"
    assert resolved.uk_audio == f"[sound:{filename}]"
    assert resolved.us_audio == f"[sound:{us_filename}]"
    assert "Audio::Legacy" not in resolved.tags
    assert resolved.tags.endswith("Audio::Cambridge")


def test_registry_builder_fails_closed_without_pronunciation_authorities(
    tmp_path: Path,
):
    paths = _build_fixture_paths(tmp_path)._replace(
        allow_legacy_pronunciation_for_tests=False,
    )

    with pytest.raises(BuildValidationError) as excinfo:
        build_notes(paths)

    assert any(
        issue.code == "pronunciation_authority_incomplete"
        for issue in excinfo.value.issues
    )


def test_pronunciation_authorities_reject_lock_for_inactive_guid(tmp_path: Path):
    locks = tmp_path / "locks.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    _write_jsonl(locks, [{
        "schema_version": 2,
        "guid": "retired-guid",
        "word": "retired",
        "card_pos": "noun",
        "accent": "uk",
        "decision": "no_pronunciation",
        "candidate_set_fingerprint": "0" * 64,
        "review_reason": "The retired fixture had no complete candidate.",
        "reviewer": "pytest",
        "reviewed_at": "2026-07-22",
    }])
    manifest.write_text("", encoding="utf-8")

    with pytest.raises(BuildValidationError) as excinfo:
        _apply_pronunciation_authorities(
            [],
            source_records=[],
            locks_path=locks,
            manifest_path=manifest,
            audio_dir=audio_dir,
        )

    assert any(
        issue.code == "pronunciation_authority_invalid"
        and "inactive GUID/accent" in issue.message
        for issue in excinfo.value.issues
    )


def test_pronunciation_authorities_reject_unselected_manifest_row(
    tmp_path: Path,
):
    locks = tmp_path / "locks.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    locks.write_text("", encoding="utf-8")
    media = b"manifest bytes"
    filename = "cambridge_uk_unused.mp3"
    (audio_dir / filename).write_bytes(media)
    fingerprint = selection_fingerprint(
        "cambridge",
        "unused",
        "uk",
        "ipa",
        "/media/unused.mp3",
        dictionary_id="cald4",
        entry_id="cald4-1",
        headword="unused",
        pos=["noun"],
    )
    _write_jsonl(manifest, [{
        "schema_version": 2,
        "selection_fingerprint": fingerprint,
        "media_fingerprint": pronunciation_media_fingerprint(
            "cambridge", "unused", "uk", "ipa", "/media/unused.mp3"
        ),
        "source": "cambridge",
        "parent_word": "unused",
        "dictionary_id": "cald4",
        "entry_id": "cald4-1",
        "headword": "unused",
        "pos": ["noun"],
        "accent": "uk",
        "ipa": "ipa",
        "audio_url": "/media/unused.mp3",
        "filename": filename,
        "sha256": hashlib.sha256(media).hexdigest(),
        "byte_count": len(media),
    }])

    with pytest.raises(BuildValidationError) as excinfo:
        _apply_pronunciation_authorities(
            [],
            source_records=[],
            locks_path=locks,
            manifest_path=manifest,
            audio_dir=audio_dir,
        )

    assert any(
        issue.code == "pronunciation_authority_invalid"
        and "unselected rows" in issue.message
        for issue in excinfo.value.issues
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
        allow_legacy_pronunciation_for_tests=True,
    ))

    assert result.built_cards_count == 1
    assert result.built_cards[0].definition == "definition"


def test_registry_build_serializes_accordingly_opal_written_tag(tmp_path: Path):
    paths = _build_fixture_paths(tmp_path)
    registry_row = _registry_row("accordingly")
    registry_row.update({"cefr": "C1", "pos": "adverb", "guid": "guid-accordingly"})
    manual_row = _manual_row("accordingly")
    manual_row.update({
        "cefr": "C1",
        "provenance": {
            "source": "build_contract_source_gap",
            "ledger_pos": "adverb",
        },
    })
    source_row = {
        "word": "accordingly",
        "source": "oxford",
        "source_files": ["oxford_accordingly_(adv).html"],
        "pos": ["adverb"],
        "pos_data": [{"pos": "adverb", "definitions": []}],
        "opal": {"adverb": ["W"]},
    }
    _write_jsonl(paths.card_registry_path, [registry_row])
    _write_jsonl(paths.manual_cards_path, [manual_row])
    _write_jsonl(paths.oxford_jsonl_path, [source_row])

    result = build_notes(paths)
    serialized = json.loads(result.jsonl_text)

    assert result.built_cards[0].tags.endswith("OPAL_W")
    assert serialized["word"] == "accordingly"
    assert serialized["tags"].endswith("OPAL_W")


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


def test_collocation_registry_is_the_final_collocation_owner(tmp_path: Path):
    paths = _build_fixture_paths(tmp_path)
    collocation_registry = tmp_path / "collocation_registry.jsonl"
    _write_jsonl(collocation_registry, [_collocation_registry_row("word")])

    card = build_notes(paths._replace(
        collocation_registry_path=collocation_registry,
    )).built_cards[0]

    assert card.collocations == "on the word|word choice"
    assert card.collocation_sources == "oxford|curated"


def test_collocation_registry_requires_exact_active_guid_coverage(tmp_path: Path):
    paths = _build_fixture_paths(tmp_path)
    collocation_registry = tmp_path / "collocation_registry.jsonl"
    _write_jsonl(collocation_registry, [])

    with pytest.raises(BuildValidationError) as excinfo:
        build_notes(paths._replace(collocation_registry_path=collocation_registry))

    assert any(
        issue.code == "collocation_registry_invalid"
        and "missing_collocation_registry_guid:guid-word" in issue.message
        for issue in excinfo.value.issues
    )


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
