from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.deck_builder.anki_import_command import (
    EAVM_FIELDS,
    EAVM_MODEL_NAME,
    AnkiConnectClient,
    AnkiConnectError,
    import_and_verify,
    load_expected_media,
    load_expected_signatures,
    preflight_and_backup,
    validate_local_inputs,
    verify_import,
)


def _row(**updates) -> dict:
    row = {
        "word": "conquer", "pos": "verb", "ipa": "/ipa/", "definition": "win",
        "example": "They conquered it.", "collocations": "", "wordfamily": "",
        "uk_audio": "[sound:uk_conquer.mp3]", "us_audio": "", "source1": "Oxford",
        "source2": "", "cefr": "C1", "idioms": "", "synonyms": "", "antonyms": "",
        "example_audio_uk": '<audio preload="none" src="example_uk_a.mp3"></audio>',
        "example_audio_us": '<audio preload="none" src="example_us_a.mp3"></audio>',
        "idiom_example_audio_uk": "", "idiom_example_audio_us": "",
    }
    row.update(updates)
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _live_note(row: dict) -> dict:
    key_order = (
        "word", "pos", "ipa", "definition", "example", "collocations", "wordfamily",
        "uk_audio", "us_audio", "source1", "source2", "cefr", "idioms", "synonyms",
        "antonyms", "example_audio_uk", "example_audio_us", "idiom_example_audio_uk",
        "idiom_example_audio_us",
    )
    return {
        "modelName": EAVM_MODEL_NAME,
        "fields": {name: {"value": str(row.get(key) or "")} for key, name in zip(key_order, EAVM_FIELDS)},
    }


def test_client_allows_long_package_backup_and_import():
    assert AnkiConnectClient().timeout >= 600


def test_load_expected_media_supports_sound_and_html_audio(tmp_path: Path):
    notes = tmp_path / "notes.jsonl"
    _write_jsonl(notes, [_row()])
    assert load_expected_media(notes) == {
        "uk_conquer.mp3", "example_uk_a.mp3", "example_us_a.mp3"
    }


def test_preflight_backs_up_existing_root_deck(tmp_path: Path):
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            if action == "version": return 6
            if action == "modelNames": return [EAVM_MODEL_NAME]
            if action == "modelFieldNames": return list(EAVM_FIELDS[:15])
            if action == "deckNames": return ["English Academic Vocabulary"]
            if action == "exportPackage":
                Path(params["path"]).write_bytes(b"backup")
                return True
            raise AssertionError(action)

    backup = preflight_and_backup(
        Client(), tmp_path, datetime(2026, 7, 13, 4, 5, 6, tzinfo=timezone.utc)
    )
    assert backup == tmp_path / "pre_import_20260713T040506Z.apkg"
    assert calls[-1][0] == "exportPackage"
    assert calls[-1][1]["includeSched"] is True


def test_preflight_allows_first_install_without_backup(tmp_path: Path):
    class Client:
        def call(self, action, **params):
            return {"version": 6, "modelNames": [], "deckNames": []}[action]
    assert preflight_and_backup(Client(), tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_preflight_rejects_prefix_compatible_extra_fields(tmp_path: Path):
    class Client:
        def call(self, action, **params):
            if action == "version": return 6
            if action == "modelNames": return [EAVM_MODEL_NAME]
            if action == "modelFieldNames": return [*EAVM_FIELDS[:15], "Unexpected"]
            raise AssertionError(action)
    with pytest.raises(AnkiConnectError, match="incompatible field contract"):
        preflight_and_backup(Client(), tmp_path)


def test_validate_local_inputs_requires_package_and_all_media(tmp_path: Path):
    notes = tmp_path / "notes.jsonl"
    package = tmp_path / "deck.apkg"
    audio = tmp_path / "audio"
    audio.mkdir()
    _write_jsonl(notes, [_row()])
    with pytest.raises(ValueError, match="APKG not found"):
        validate_local_inputs(package, notes, audio)

    package.write_bytes(b"package")
    with pytest.raises(ValueError, match="referenced media missing"):
        validate_local_inputs(package, notes, audio)

    for name in ("uk_conquer.mp3", "example_uk_a.mp3", "example_us_a.mp3"):
        (audio / name).write_bytes(b"ID3")
    expected, media = validate_local_inputs(package, notes, audio)
    assert sum(expected.values()) == 1
    assert media == {"uk_conquer.mp3", "example_uk_a.mp3", "example_us_a.mp3"}


def test_verify_import_checks_fields_notes_and_media():
    row = _row()
    expected = Counter({tuple((field["value"] for field in _live_note(row)["fields"].values())): 1})

    class Client:
        def call(self, action, **params):
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "findNotes": return [123]
            if action == "notesInfo": return [_live_note(row)]
            if action == "getMediaFilesNames": return ["uk_conquer.mp3", "example_uk_a.mp3"]
            raise AssertionError(action)

    assert verify_import(Client(), expected, {"uk_conquer.mp3", "example_uk_a.mp3"}) == 1


def test_verify_import_fails_on_missing_media():
    row = _row()
    signature = tuple(field["value"] for field in _live_note(row)["fields"].values())

    class Client:
        def call(self, action, **params):
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "findNotes": return [123]
            if action == "notesInfo": return [_live_note(row)]
            if action == "getMediaFilesNames": return []
            raise AssertionError(action)

    with pytest.raises(AnkiConnectError, match="missing media"):
        verify_import(Client(), Counter({signature: 1}), {"missing.mp3"})


def test_verify_import_rejects_duplicate_live_notes():
    row = _row()
    signature = tuple(field["value"] for field in _live_note(row)["fields"].values())

    class Client:
        def call(self, action, **params):
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "findNotes": return [123, 456]
            raise AssertionError(action)

    with pytest.raises(AnkiConnectError, match="expected 1 notes"):
        verify_import(Client(), Counter({signature: 1}), set())


def test_import_and_verify_uses_absolute_forward_slash_package_path(tmp_path: Path):
    notes = tmp_path / "notes.jsonl"
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    row = _row(uk_audio="", example_audio_uk="", example_audio_us="")
    _write_jsonl(notes, [row])
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            if action == "version": return 6
            if action == "modelNames": return []
            if action == "deckNames": return []
            if action == "importPackage": return None
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "findNotes": return [1]
            if action == "notesInfo": return [_live_note(row)]
            if action == "getMediaFilesNames": return []
            raise AssertionError(action)

    assert import_and_verify(Client(), package, notes, tmp_path / "scratch") == 1
    import_call = next(call for call in calls if call[0] == "importPackage")
    assert import_call[1]["path"] == package.resolve().as_posix()
