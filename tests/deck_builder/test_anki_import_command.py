from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.deck_builder.anki_import_command import (
    EAVM_FIELDS,
    EAVM_MODEL_ID,
    LEGACY_EAVM_FIELDS,
    EAVM_MODEL_NAME,
    EAVM_TEMPLATE_NAMES,
    ROOT_DECK,
    AnkiConnectClient,
    AnkiConnectError,
    import_and_verify,
    load_expected_media,
    load_expected_records,
    load_expected_signatures,
    migrate_established_eavm_fields,
    preflight_and_backup,
    snapshot_existing_collection,
    sync_example_audio_fields,
    sync_missing_media,
    sync_existing_notes,
    sync_model_design,
    validate_local_inputs,
    verify_import,
)
from src.deck_builder.package_command import load_eavm_templates
from src.design_css import load_production_css
import src.deck_builder.anki_import_command as import_module


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
        "production_answer": "conquer",
        "sense_pos": "verb",
        "idiom_meaning_vi": "",
        "cambridge_url": "https://dictionary.cambridge.org/dictionary/english/conquer",
        "oxford_pos_urls": "https://www.oxfordlearnersdictionaries.com/definition/english/conquer",
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
        "idiom_example_audio_us", "definition_vi", "cambridge_url",
        "oxford_pos_urls", "production_answer", "sense_pos", "idiom_meaning_vi",
    )
    return {
        "modelName": EAVM_MODEL_NAME,
        "fields": {name: {"value": str(row.get(key) or "")} for key, name in zip(key_order, EAVM_FIELDS)},
    }


def _canonical_templates() -> dict[str, dict[str, str]]:
    return {
        template.name: template.for_anki_connect()
        for template in load_eavm_templates()
    }


def _legacy_templates() -> dict[str, dict[str, str]]:
    return {"Card 1": {"Front": "{{Word}}", "Back": "{{Definition}}"}}


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
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS[:15])
            if action == "modelTemplates": return _legacy_templates()
            if action == "deckNames": return ["English Academic Vocabulary"]
            if action == "findNotes": return [1]
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
            return {"version": 6, "modelNamesAndIds": {}, "deckNames": []}[action]
    assert preflight_and_backup(Client(), tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_preflight_rejects_stray_root_cards_when_model_has_no_notes(tmp_path: Path):
    class Client:
        def call(self, action, **params):
            if action == "version": return 6
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS[:15])
            if action == "modelTemplates": return _legacy_templates()
            if action == "deckNames": return [ROOT_DECK]
            if action == "findNotes": return []
            if action == "findCards": return [999]
            raise AssertionError(action)

    with pytest.raises(AnkiConnectError, match="non-empty"):
        preflight_and_backup(Client(), tmp_path)


def test_preflight_rejects_model_id_collision_under_foreign_name(tmp_path: Path):
    class Client:
        def call(self, action, **params):
            if action == "version": return 6
            if action == "modelNamesAndIds": return {"Foreign model": EAVM_MODEL_ID}
            raise AssertionError(action)

    with pytest.raises(AnkiConnectError, match="foreign model"):
        preflight_and_backup(Client(), tmp_path)


def test_empty_existing_model_is_aligned_before_native_import(tmp_path: Path, monkeypatch):
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    notes = tmp_path / "notes.jsonl"
    notes.write_text("{}\n", encoding="utf-8")
    calls: list[str] = []
    expected = Counter({("sig",): 1})
    records = {
        ("id",): {
            "deck": "Deck", "fields": {}, "tags": [], "guid": "",
            "production_eligible": False,
        }
    }

    monkeypatch.setattr(import_module, "load_expected_signatures", lambda _: expected)
    monkeypatch.setattr(import_module, "load_expected_records", lambda _: records)
    monkeypatch.setattr(import_module, "load_expected_media", lambda _: set())
    monkeypatch.setattr(import_module, "load_eavm_templates", lambda: ())
    monkeypatch.setattr(import_module, "load_production_css", lambda _: "css")
    monkeypatch.setattr(
        import_module, "_model_contract",
        lambda _: (True, tuple(EAVM_FIELDS[:15]), "legacy"),
    )
    monkeypatch.setattr(import_module, "preflight_and_backup", lambda *args: None)
    monkeypatch.setattr(
        import_module, "migrate_established_eavm_fields",
        lambda _: calls.append("migrate"),
    )
    monkeypatch.setattr(
        import_module, "sync_model_design",
        lambda _: calls.append("design"),
    )
    monkeypatch.setattr(
        import_module, "sync_missing_media",
        lambda *args: calls.append("media") or 0,
    )
    monkeypatch.setattr(
        import_module, "verify_import",
        lambda *args: calls.append("verify") or 1,
    )

    class Client:
        def call(self, action, **params):
            calls.append(action)
            if action == "findNotes":
                return []
            if action == "importPackage":
                return None
            raise AssertionError(action)

    assert import_module.import_and_verify(
        Client(), package, notes, tmp_path / "scratch", tmp_path / "audio"
    ) == 1
    assert calls == ["findNotes", "migrate", "design", "importPackage", "media", "verify"]


@pytest.mark.parametrize("field_count", [15, 19, 20, 21, 22])
def test_preflight_allows_canonical_field_prefixes(tmp_path: Path, field_count: int):
    class Client:
        def call(self, action, **params):
            if action == "version": return 6
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS[:field_count])
            if action == "modelTemplates": return _legacy_templates()
            if action == "deckNames": return []
            if action == "findNotes": return []
            raise AssertionError(action)

    assert preflight_and_backup(Client(), tmp_path) is None


@pytest.mark.parametrize("missing_tail", [1, 2])
def test_preflight_allows_previous_complete_fields_with_production_templates(
    tmp_path: Path, missing_tail: int,
):
    class Client:
        def call(self, action, **params):
            if action == "version": return 6
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS[:-missing_tail])
            if action == "modelTemplates": return _canonical_templates()
            if action == "deckNames": return []
            if action == "findNotes": return []
            raise AssertionError(action)

    assert preflight_and_backup(Client(), tmp_path) is None


def test_preflight_rejects_prefix_compatible_extra_fields(tmp_path: Path):
    class Client:
        def call(self, action, **params):
            if action == "version": return 6
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return [*EAVM_FIELDS[:15], "Unexpected"]
            if action == "modelTemplates": return _legacy_templates()
            raise AssertionError(action)
    with pytest.raises(AnkiConnectError, match="incompatible field contract"):
        preflight_and_backup(Client(), tmp_path)


def test_migrate_established_model_appends_all_new_fields_in_order():
    fields = list(EAVM_FIELDS[:15])
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(fields)
            if action == "modelFieldAdd":
                fields.insert(params["index"], params["fieldName"])
                return None
            raise AssertionError(action)

    migrate_established_eavm_fields(Client())

    assert fields == list(EAVM_FIELDS)
    additions = [params for action, params in calls if action == "modelFieldAdd"]
    assert [params["fieldName"] for params in additions] == list(EAVM_FIELDS[15:])
    assert [params["index"] for params in additions] == list(
        range(15, len(EAVM_FIELDS))
    )


def test_migrate_legacy_19_field_model_appends_remaining_fields():
    fields = list(LEGACY_EAVM_FIELDS)
    additions = []

    class Client:
        def call(self, action, **params):
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(fields)
            if action == "modelFieldAdd":
                additions.append(params)
                fields.insert(params["index"], params["fieldName"])
                return None
            raise AssertionError(action)

    migrate_established_eavm_fields(Client())

    assert fields == list(EAVM_FIELDS)
    assert additions == [
        {"modelName": EAVM_MODEL_NAME, "fieldName": field_name, "index": index}
        for index, field_name in enumerate(EAVM_FIELDS[19:], start=19)
    ]


@pytest.mark.parametrize(
    "field_count", [20, 21, len(EAVM_FIELDS) - 2, len(EAVM_FIELDS) - 1]
)
def test_migrate_partial_current_model_appends_only_missing_fields(field_count: int):
    fields = list(EAVM_FIELDS[:field_count])
    additions = []

    class Client:
        def call(self, action, **params):
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(fields)
            if action == "modelFieldAdd":
                additions.append(params)
                fields.insert(params["index"], params["fieldName"])
                return None
            raise AssertionError(action)

    migrate_established_eavm_fields(Client())

    assert fields == list(EAVM_FIELDS)
    assert [params["fieldName"] for params in additions] == list(EAVM_FIELDS[field_count:])


def test_snapshot_accepts_legacy_prefix_before_field_migration(tmp_path: Path):
    """The pre-migration schedule snapshot must handle the old field count."""
    row = _row(deck="English Academic Vocabulary::Oxford")
    notes = tmp_path / "notes.jsonl"
    _write_jsonl(notes, [row])
    expected = load_expected_records(notes)
    live = _live_note(row)
    live["noteId"] = 123
    live["cards"] = [456]
    live["tags"] = []
    live["fields"].pop("ProductionAnswer")
    live["fields"].pop("SensePOS")
    live["fields"].pop("IdiomMeaningVI")

    class Client:
        def call(self, action, **params):
            if action == "findNotes":
                return [123]
            if action == "notesInfo":
                return [live]
            if action == "findCards":
                return [456]
            if action == "cardsInfo":
                return [{
                    "cardId": 456,
                    "note": 123,
                    "ord": 0,
                    "deckName": row["deck"],
                    "modelName": EAVM_MODEL_NAME,
                    "type": 2,
                    "queue": 2,
                    "due": 10,
                    "interval": 3,
                    "factor": 2500,
                    "reps": 4,
                    "lapses": 0,
                    "left": 0,
                }]
            raise AssertionError(action)

    snapshot = snapshot_existing_collection(
        Client(), expected, "legacy", EAVM_FIELDS[:22]
    )
    assert snapshot.note_ids == frozenset({123})
    assert snapshot.card_ids == frozenset({456})
    assert snapshot.schedules[456][:2] == (2, 2)


def test_sync_model_design_updates_existing_template_name_and_css(tmp_path: Path):
    front = tmp_path / "front.txt"
    back = tmp_path / "back.txt"
    production_front = tmp_path / "production-front.txt"
    production_prefix = tmp_path / "production-prefix.txt"
    css = tmp_path / "style.txt"
    front.write_text("front {{Word}}", encoding="utf-8")
    back.write_text("back {{ExampleAudioUK}}", encoding="utf-8")
    production_front.write_text("{{type:ProductionAnswer}}", encoding="utf-8")
    production_prefix.write_text("{{FrontSide}}", encoding="utf-8")
    css.write_text(".example-audio-btn { color: red; }", encoding="utf-8")
    templates = {"Reading Card": {"Front": "old front", "Back": "old back"}}
    styling = {"css": "old css"}

    class Client:
        def call(self, action, **params):
            if action == "modelTemplates": return templates
            if action == "modelStyling": return styling
            if action == "modelTemplateRename":
                templates[EAVM_TEMPLATE_NAMES[0]] = templates.pop(
                    params["oldTemplateName"]
                )
                return None
            if action == "modelTemplateAdd":
                template = params["template"]
                templates[template["Name"]] = {
                    "Front": template["Front"], "Back": template["Back"]
                }
                return None
            if action == "updateModelTemplates":
                templates.clear()
                templates.update(params["model"]["templates"])
                return None
            if action == "updateModelStyling":
                styling["css"] = params["model"]["css"]
                return None
            raise AssertionError(action)

    sync_model_design(
        Client(), front, back, css, production_front, production_prefix
    )

    assert tuple(templates) == EAVM_TEMPLATE_NAMES
    assert templates["Recognition"]["Back"] == "back {{ExampleAudioUK}}"
    assert templates[EAVM_TEMPLATE_NAMES[1]]["Front"] == "{{type:ProductionAnswer}}"
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
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling": return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
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
            "CambridgeURL": row["cambridge_url"],
            "OxfordPOSURLs": row["oxford_pos_urls"],
            "ProductionAnswer": row["production_answer"],
            "SensePOS": row["sense_pos"],
            "IdiomMeaningVI": row["idiom_meaning_vi"],
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
    assert update["params"]["note"]["fields"]["CambridgeURL"] == row["cambridge_url"]
    assert update["params"]["note"]["fields"]["OxfordPOSURLs"] == row["oxford_pos_urls"]
    assert update["params"]["note"]["fields"]["SensePOS"] == row["sense_pos"]
    assert update["params"]["note"]["fields"]["IdiomMeaningVI"] == ""
    assert ("changeDeck", {"cards": [456], "deck": row["deck"]}) in calls


def test_verify_import_fails_on_missing_media():
    row = _row()
    signature = tuple(field["value"] for field in _live_note(row)["fields"].values())

    class Client:
        def call(self, action, **params):
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling": return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
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
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling": return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
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
    imported = False

    class Client:
        def call(self, action, **params):
            nonlocal imported
            calls.append((action, params))
            if action == "version": return 6
            if action == "modelNamesAndIds":
                return {EAVM_MODEL_NAME: EAVM_MODEL_ID} if imported else {}
            if action == "deckNames": return []
            if action == "importPackage":
                imported = True
                return None
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling": return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
            if action == "findNotes": return [1]
            if action == "notesInfo":
                note = _live_note(row)
                note.update({"noteId": 1, "cards": [10, 11], "tags": []})
                return [note]
            if action == "findCards": return [10, 11]
            if action == "cardsInfo":
                return [
                    {"cardId": 10, "note": 1, "ord": 0, "deckName": row.get("deck", ""), "modelName": EAVM_MODEL_NAME},
                    {"cardId": 11, "note": 1, "ord": 1, "deckName": row.get("deck", ""), "modelName": EAVM_MODEL_NAME,
                     "type": 0, "queue": 0, "interval": 0, "reps": 0, "lapses": 0},
                ]
            if action == "getMediaFilesNames": return []
            raise AssertionError(action)

    assert import_and_verify(Client(), package, notes, tmp_path / "scratch") == 1
    import_call = next(call for call in calls if call[0] == "importPackage")
    assert import_call[1]["path"] == package.resolve().as_posix()
