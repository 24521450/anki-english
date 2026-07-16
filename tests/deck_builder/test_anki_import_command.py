from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.deck_builder.anki_import_command import (
    EAVM_FIELDS,
    LEGACY_EAVM_FIELDS,
    EAVM_MODEL_NAME,
    AnkiConnectClient,
    AnkiConnectError,
    import_and_verify,
    load_expected_media,
    load_expected_records,
    load_expected_signatures,
    migrate_established_eavm_fields,
    preflight_and_backup,
    sync_example_audio_fields,
    sync_missing_media,
    sync_existing_notes,
    sync_model_design,
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
        "definition_vi": "chiến thắng",
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
        "idiom_example_audio_us", "definition_vi",
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


def test_expected_records_distinguish_reviewed_identity_variants(tmp_path: Path):
    notes = tmp_path / "notes.jsonl"
    _write_jsonl(notes, [
        _row(word="temporal", cefr="UNCLASSIFIED", tags="SenseVariant::general_formal"),
        _row(word="temporal", cefr="UNCLASSIFIED", tags="SenseVariant::anatomy"),
    ])
    assert len(load_expected_records(notes)) == 2


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


def test_preflight_allows_current_19_field_model(tmp_path: Path):
    class Client:
        def call(self, action, **params):
            if action == "version": return 6
            if action == "modelNames": return [EAVM_MODEL_NAME]
            if action == "modelFieldNames": return list(LEGACY_EAVM_FIELDS)
            if action == "deckNames": return []
            raise AssertionError(action)

    assert preflight_and_backup(Client(), tmp_path) is None


def test_preflight_rejects_prefix_compatible_extra_fields(tmp_path: Path):
    class Client:
        def call(self, action, **params):
            if action == "version": return 6
            if action == "modelNames": return [EAVM_MODEL_NAME]
            if action == "modelFieldNames": return [*EAVM_FIELDS[:15], "Unexpected"]
            raise AssertionError(action)
    with pytest.raises(AnkiConnectError, match="incompatible field contract"):
        preflight_and_backup(Client(), tmp_path)


def test_migrate_established_model_appends_all_new_fields_in_order():
    fields = list(EAVM_FIELDS[:15])
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            if action == "modelNames": return [EAVM_MODEL_NAME]
            if action == "modelFieldNames": return list(fields)
            if action == "modelFieldAdd":
                fields.insert(params["index"], params["fieldName"])
                return None
            raise AssertionError(action)

    migrate_established_eavm_fields(Client())

    assert fields == list(EAVM_FIELDS)
    additions = [params for action, params in calls if action == "modelFieldAdd"]
    assert [params["fieldName"] for params in additions] == list(EAVM_FIELDS[15:])
    assert [params["index"] for params in additions] == [15, 16, 17, 18, 19]


def test_migrate_legacy_19_field_model_appends_definition_vi_only():
    fields = list(LEGACY_EAVM_FIELDS)
    additions = []

    class Client:
        def call(self, action, **params):
            if action == "modelNames": return [EAVM_MODEL_NAME]
            if action == "modelFieldNames": return list(fields)
            if action == "modelFieldAdd":
                additions.append(params)
                fields.insert(params["index"], params["fieldName"])
                return None
            raise AssertionError(action)

    migrate_established_eavm_fields(Client())

    assert fields == list(EAVM_FIELDS)
    assert additions == [{
        "modelName": EAVM_MODEL_NAME,
        "fieldName": "DefinitionVI",
        "index": 19,
    }]


def test_sync_model_design_updates_existing_template_name_and_css(tmp_path: Path):
    front = tmp_path / "front.txt"
    back = tmp_path / "back.txt"
    css = tmp_path / "style.txt"
    front.write_text("front {{Word}}", encoding="utf-8")
    back.write_text("back {{ExampleAudioUK}}", encoding="utf-8")
    css.write_text(".example-audio-btn { color: red; }", encoding="utf-8")
    templates = {"Reading Card": {"Front": "old front", "Back": "old back"}}
    styling = {"css": "old css"}

    class Client:
        def call(self, action, **params):
            if action == "modelTemplates": return templates
            if action == "modelStyling": return styling
            if action == "updateModelTemplates":
                templates.update(params["model"]["templates"])
                return None
            if action == "updateModelStyling":
                styling["css"] = params["model"]["css"]
                return None
            raise AssertionError(action)

    sync_model_design(Client(), front, back, css)

    assert templates["Reading Card"]["Back"] == "back {{ExampleAudioUK}}"
    assert styling["css"].strip() == ".example-audio-btn { color: red; }"


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


def test_sync_example_audio_fields_matches_established_signature_and_batches_update():
    row = _row()
    full = tuple(field["value"] for field in _live_note(row)["fields"].values())
    live = _live_note(row)
    live["noteId"] = 123
    for name in EAVM_FIELDS[15:]:
        live["fields"][name]["value"] = ""
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            if action == "findNotes": return [123]
            if action == "notesInfo": return [live]
            if action == "multi": return [None] * len(params["actions"])
            raise AssertionError(action)

    assert sync_example_audio_fields(Client(), Counter({full: 1})) == 1
    actions = next(params["actions"] for action, params in calls if action == "multi")
    assert actions == [{
        "action": "updateNoteFields",
        "params": {"note": {"id": 123, "fields": {
            "ExampleAudioUK": row["example_audio_uk"],
            "ExampleAudioUS": row["example_audio_us"],
            "IdiomExampleAudioUK": "",
            "IdiomExampleAudioUS": "",
            "DefinitionVI": row["definition_vi"],
        }}},
    }]


def test_sync_missing_media_uses_local_paths_and_only_uploads_missing(tmp_path: Path):
    existing = tmp_path / "existing.mp3"
    missing = tmp_path / "missing.mp3"
    existing.write_bytes(b"existing")
    missing.write_bytes(b"missing")
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            if action == "getMediaFilesNames": return ["existing.mp3"]
            if action == "multi": return ["missing.mp3"]
            raise AssertionError(action)

    assert sync_missing_media(
        Client(), {"existing.mp3", "missing.mp3"}, tmp_path
    ) == 1
    actions = next(params["actions"] for action, params in calls if action == "multi")
    assert actions == [{
        "action": "storeMediaFile",
        "params": {"filename": "missing.mp3", "path": missing.resolve().as_posix()},
    }]


def test_sync_existing_notes_updates_all_fields_and_routes_cards(tmp_path: Path):
    notes = tmp_path / "notes.jsonl"
    row = _row(deck="English Academic Vocabulary::Oxford", tags="CEFR::C1")
    _write_jsonl(notes, [row])
    live = _live_note(row)
    live.update({"noteId": 123, "cards": [456], "tags": ["CEFR::C1"]})
    live["fields"]["Definition"]["value"] = "old"
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            if action == "findNotes": return [123]
            if action == "notesInfo": return [live]
            if action == "multi": return [None]
            if action == "changeDeck": return None
            raise AssertionError(action)

    assert sync_existing_notes(Client(), notes) == 1
    update = next(params["actions"][0] for action, params in calls if action == "multi")
    assert update["action"] == "updateNote"
    assert update["params"]["note"]["fields"]["Definition"] == "win"
    assert update["params"]["note"]["fields"]["DefinitionVI"] == "chiến thắng"
    assert ("changeDeck", {"cards": [456], "deck": row["deck"]}) in calls


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
