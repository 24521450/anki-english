from __future__ import annotations

import base64
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.config import ProjectPaths
from src.deck_builder.anki_import_command import (
    EAVM_FIELDS,
    EAVM_MODEL_ID,
    LEGACY_EAVM_FIELDS,
    EAVM_MODEL_NAME,
    EAVM_TEMPLATE_NAMES,
    ROOT_DECK,
    AnkiConnectClient,
    AnkiConnectError,
    ExistingCollectionSnapshot,
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
from src.deck_builder.live_guid_proof import LiveGuidProof
from src.deck_builder.package_archive import (
    PackageArchiveError,
    validate_package_archive as real_validate_package_archive,
)
from src.deck_builder.package_provenance import (
    media_file_map,
    package_provenance_inputs,
    provenance_path_for,
    verified_receipt_path_for,
    write_package_provenance,
)
from src.design_css import load_production_css
import src.deck_builder.anki_import_command as import_module


@pytest.fixture(autouse=True)
def _isolate_archive_validation(monkeypatch: pytest.MonkeyPatch):
    """Archive mechanics have dedicated tests; import tests assert call ordering."""

    monkeypatch.setattr(
        import_module,
        "validate_package_archive",
        lambda *args, **kwargs: None,
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
        "production_answer": "conquer",
        "sense_pos": "verb",
        "idiom_meaning_vi": "",
        "collocation_sources": "",
        "cambridge_url": "https://dictionary.cambridge.org/dictionary/english/conquer",
        "oxford_pos_urls": "https://www.oxfordlearnersdictionaries.com/definition/english/conquer",
    }
    row.update(updates)
    return row


@pytest.mark.parametrize(
    "result",
    [
        False,
        [None, False],
        [{"result": None, "error": "inner failure"}],
        [{"result": False, "error": None}],
    ],
)
def test_mutation_result_rejects_outer_and_nested_failures(result) -> None:
    with pytest.raises(AnkiConnectError):
        import_module._require_not_false(result, "multi")


@pytest.mark.parametrize(
    "result",
    [None, True, [None], [{"result": None, "error": None}]],
)
def test_mutation_result_accepts_raw_v4_and_enveloped_success(result) -> None:
    import_module._require_not_false(result, "multi")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write_test_provenance(
    tmp_path: Path,
    package: Path,
    notes: Path,
    audio_dir: Path,
) -> tuple[Path, dict[str, Path], Path]:
    inputs = package_provenance_inputs(
        ProjectPaths(tmp_path),
        notes_jsonl=notes,
        recognition_front=import_module.FRONT_TEMPLATE,
        recognition_back=import_module.BACK_TEMPLATE,
        production_front=import_module.PRODUCTION_FRONT_TEMPLATE,
        production_answer_prefix=import_module.PRODUCTION_ANSWER_PREFIX,
        styling=import_module.STYLING_TXT,
        design_index=import_module.DESIGN_INDEX,
    )
    design_labels = {
        "recognition_front", "recognition_back", "production_front",
        "production_answer_prefix", "styling", "design_index",
    }
    for label, path in inputs.items():
        if label in design_labels or path == notes:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    media = load_expected_media(notes)
    sidecar = provenance_path_for(package)
    write_package_provenance(
        sidecar,
        package,
        inputs,
        media_file_map(audio_dir / name for name in media),
    )
    return sidecar, inputs, verified_receipt_path_for(package)


def _live_note(row: dict) -> dict:
    key_order = (
        "word", "pos", "ipa", "definition", "example", "collocations", "wordfamily",
        "uk_audio", "us_audio", "source1", "source2", "cefr", "idioms", "synonyms",
        "antonyms", "example_audio_uk", "example_audio_us", "idiom_example_audio_uk",
        "idiom_example_audio_us", "definition_vi", "cambridge_url",
        "oxford_pos_urls", "production_answer", "sense_pos", "idiom_meaning_vi",
        "collocation_sources",
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
    provenance_path, provenance_inputs, receipt_path = _write_test_provenance(
        tmp_path, package, notes, tmp_path / "audio"
    )

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
    monkeypatch.setattr(
        import_module,
        "export_and_verify_live_guid_map",
        lambda *args, **kwargs: LiveGuidProof(
            "fixture.apkg", "a" * 64, "b" * 64, "collection.anki2", 1, 1
        ),
    )
    monkeypatch.setattr(
        import_module, "write_verified_import_receipt",
        lambda *args, **kwargs: calls.append("receipt"),
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
        Client(), package, notes, tmp_path / "scratch", tmp_path / "audio",
        provenance_path=provenance_path,
        provenance_inputs=provenance_inputs,
        receipt_path=receipt_path,
    ) == 1
    assert calls == [
        "findNotes", "migrate", "design", "importPackage", "media", "verify",
        "receipt",
    ]


@pytest.mark.parametrize("has_added_identity", [True, False])
def test_existing_collection_imports_only_when_canonical_identities_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    has_added_identity: bool,
) -> None:
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    notes = tmp_path / "notes.jsonl"
    existing = _row(word="alien", pos="noun", guid="existing-guid")
    added = _row(
        word="alien",
        pos="adjective",
        tags="SecondarySense",
        guid="added-guid",
    )
    rows = [existing, added] if has_added_identity else [existing]
    _write_jsonl(notes, rows)
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    for filename in load_expected_media(notes):
        (audio_dir / filename).write_bytes(filename.encode("utf-8"))
    provenance_path, provenance_inputs, receipt_path = _write_test_provenance(
        tmp_path, package, notes, audio_dir
    )
    calls: list[object] = []
    prior = ExistingCollectionSnapshot(
        note_ids=frozenset({1}),
        card_ids=frozenset({10, 11}),
        schedules={10: (2, 2), 11: (2, 2)},
        had_production_template=True,
        note_identities={1: ("alien", "noun", "C1")},
    )

    monkeypatch.setattr(
        import_module,
        "_model_contract",
        lambda _: (True, tuple(EAVM_FIELDS), "canonical"),
    )
    monkeypatch.setattr(import_module, "preflight_and_backup", lambda *args: None)
    monkeypatch.setattr(
        import_module,
        "snapshot_existing_collection",
        lambda *args: calls.append("snapshot") or prior,
    )
    monkeypatch.setattr(
        import_module,
        "migrate_established_eavm_fields",
        lambda _: calls.append("migrate"),
    )
    monkeypatch.setattr(
        import_module,
        "sync_existing_notes",
        lambda *args, **kwargs: calls.append(
            ("sync", kwargs.get("require_complete", True))
        ) or 0,
    )
    monkeypatch.setattr(
        import_module, "sync_model_design", lambda _: calls.append("design")
    )
    monkeypatch.setattr(
        import_module, "sync_missing_media", lambda *args: calls.append("media") or 0
    )
    monkeypatch.setattr(
        import_module,
        "verify_import",
        lambda *args: calls.append("verify") or len(rows),
    )
    monkeypatch.setattr(
        import_module,
        "export_and_verify_live_guid_map",
        lambda *args, **kwargs: LiveGuidProof(
            "fixture.apkg", "a" * 64, "b" * 64, "collection.anki2", 2, 4
        ),
    )
    monkeypatch.setattr(
        import_module,
        "write_verified_import_receipt",
        lambda *args, **kwargs: calls.append("receipt"),
    )

    class Client:
        def call(self, action, **params):
            if action == "findNotes": return [1]
            if action == "importPackage":
                calls.append("importPackage")
                return None
            raise AssertionError(action)

    assert import_and_verify(
        Client(), package, notes, tmp_path / "scratch", audio_dir,
        provenance_path=provenance_path,
        provenance_inputs=provenance_inputs,
        receipt_path=receipt_path,
    ) == len(rows)
    expected_calls: list[object] = [
        "snapshot", "migrate", ("sync", not has_added_identity), "design"
    ]
    if has_added_identity:
        expected_calls.append("importPackage")
    expected_calls.extend([("sync", True), "media", "verify", "receipt"])
    assert calls == expected_calls


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
    live["fields"].pop("CollocationSources")

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


def test_snapshot_accepts_unique_canonical_identity_subset(tmp_path: Path):
    existing = _row(
        word="alien",
        pos="noun",
        deck="English Academic Vocabulary::Oxford",
    )
    added = _row(
        word="alien",
        pos="adjective",
        tags="SecondarySense",
        deck="English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses",
    )
    notes = tmp_path / "notes.jsonl"
    _write_jsonl(notes, [existing, added])
    live = _live_note(existing)
    live.update({"noteId": 123, "cards": [456, 457], "tags": []})

    class Client:
        def call(self, action, **params):
            if action == "findNotes": return [123]
            if action == "notesInfo": return [live]
            if action == "findCards": return [456, 457]
            if action == "cardsInfo":
                return [
                    {
                        "cardId": card_id,
                        "note": 123,
                        "ord": ordinal,
                        "deckName": existing["deck"],
                        "modelName": EAVM_MODEL_NAME,
                        "type": 2,
                        "queue": 2,
                        "due": 10 + ordinal,
                        "interval": 3,
                        "factor": 2500,
                        "reps": 4,
                        "lapses": 0,
                        "left": 0,
                    }
                    for card_id, ordinal in ((456, 0), (457, 1))
                ]
            raise AssertionError(action)

    snapshot = snapshot_existing_collection(
        Client(), load_expected_records(notes), "canonical"
    )

    assert snapshot.note_ids == frozenset({123})
    assert snapshot.card_ids == frozenset({456, 457})
    assert snapshot.note_identities == {123: ("alien", "noun", "C1")}


def test_snapshot_rejects_identity_outside_canonical_set(tmp_path: Path):
    notes = tmp_path / "notes.jsonl"
    _write_jsonl(notes, [_row(word="alien", pos="noun")])
    live = _live_note(_row(word="intruder", pos="noun"))
    live.update({"noteId": 123, "cards": [456], "tags": []})

    class Client:
        def call(self, action, **params):
            if action == "findNotes": return [123]
            if action == "notesInfo": return [live]
            raise AssertionError(action)

    with pytest.raises(
        AnkiConnectError,
        match="did not resolve to one canonical Card Identity",
    ):
        snapshot_existing_collection(
            Client(), load_expected_records(notes), "canonical"
        )


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


@pytest.mark.parametrize("provenance_state", ["missing", "stale", "stale_ledger"])
def test_import_rejects_invalid_provenance_before_any_anki_call(
    tmp_path: Path, provenance_state: str,
):
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    notes = tmp_path / "notes.jsonl"
    row = _row(uk_audio="", example_audio_uk="", example_audio_us="")
    _write_jsonl(notes, [row])
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    sidecar, inputs, receipt = _write_test_provenance(
        tmp_path, package, notes, audio_dir
    )
    if provenance_state == "missing":
        sidecar.unlink()
    elif provenance_state == "stale":
        package.write_bytes(b"stale package")
    else:
        inputs["semantic_policy_locks"].write_text(
            "changed policy\n", encoding="utf-8"
        )
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            raise AssertionError("AnkiConnect must not be called")

    with pytest.raises(ValueError, match="package provenance"):
        import_and_verify(
            Client(), package, notes, tmp_path / "scratch", audio_dir,
            provenance_path=sidecar,
            provenance_inputs=inputs,
            receipt_path=receipt,
        )
    assert calls == []
    assert not receipt.exists()


def test_failed_import_leaves_no_verified_receipt(tmp_path: Path):
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    notes = tmp_path / "notes.jsonl"
    row = _row(uk_audio="", example_audio_uk="", example_audio_us="")
    _write_jsonl(notes, [row])
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    sidecar, inputs, receipt = _write_test_provenance(
        tmp_path, package, notes, audio_dir
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text("old receipt", encoding="utf-8")

    class Client:
        def call(self, action, **params):
            raise AnkiConnectError("simulated live failure")

    with pytest.raises(AnkiConnectError, match="simulated live failure"):
        import_and_verify(
            Client(), package, notes, tmp_path / "scratch", audio_dir,
            provenance_path=sidecar,
            provenance_inputs=inputs,
            receipt_path=receipt,
        )
    assert not receipt.exists()


def test_live_media_byte_mismatch_leaves_no_verified_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    notes = tmp_path / "notes.jsonl"
    filename = "same-name.mp3"
    row = _row(
        uk_audio=f"[sound:{filename}]",
        example_audio_uk="",
        example_audio_us="",
    )
    _write_jsonl(notes, [row])
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / filename).write_bytes(b"canonical source bytes")
    sidecar, inputs, receipt = _write_test_provenance(
        tmp_path, package, notes, audio_dir
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text("old receipt", encoding="utf-8")

    monkeypatch.setattr(
        import_module,
        "_model_contract",
        lambda _client: (False, (), None),
    )
    monkeypatch.setattr(
        import_module,
        "preflight_and_backup",
        lambda *args, **kwargs: None,
    )

    def verify_live_bytes(
        client, _expected, expected_media, _records, _prior,
        _templates, _css, resolved_audio_dir,
    ):
        import_module._verify_live_media_bytes(
            client, expected_media, resolved_audio_dir
        )
        return 1

    monkeypatch.setattr(import_module, "verify_import", verify_live_bytes)

    class Client:
        def call(self, action, **params):
            if action == "importPackage": return True
            if action == "getMediaFilesNames": return [filename]
            if action == "multi":
                return [{
                    "result": base64.b64encode(b"wrong live bytes").decode("ascii"),
                    "error": None,
                }]
            raise AssertionError(action)

    with pytest.raises(AnkiConnectError, match="bytes do not match canonical source"):
        import_and_verify(
            Client(),
            package,
            notes,
            tmp_path / "scratch",
            audio_dir,
            provenance_path=sidecar,
            provenance_inputs=inputs,
            receipt_path=receipt,
        )
    assert not receipt.exists()


def test_import_rejects_invalid_archive_before_any_anki_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"not an APKG")
    notes = tmp_path / "notes.jsonl"
    row = _row(
        uk_audio="",
        example_audio_uk="",
        example_audio_us="",
        deck="English Academic Vocabulary::C1",
        guid="canonical-guid",
        tags="",
    )
    _write_jsonl(notes, [row])
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    sidecar, inputs, receipt = _write_test_provenance(
        tmp_path, package, notes, audio_dir
    )
    monkeypatch.setattr(
        import_module, "validate_package_archive", real_validate_package_archive
    )
    calls: list[str] = []

    class Client:
        def call(self, action, **params):
            calls.append(action)
            raise AssertionError("AnkiConnect must not be called")

    with pytest.raises(PackageArchiveError, match="invalid APKG archive"):
        import_and_verify(
            Client(),
            package,
            notes,
            tmp_path / "scratch",
            audio_dir,
            provenance_path=sidecar,
            provenance_inputs=inputs,
            receipt_path=receipt,
        )
    assert calls == []
    assert not receipt.exists()


def test_verify_import_checks_fields_notes_and_media(tmp_path: Path):
    row = _row()
    expected = Counter({tuple((field["value"] for field in _live_note(row)["fields"].values())): 1})
    media_payloads = {
        "uk_conquer.mp3": b"canonical headword audio",
        "example_uk_a.mp3": b"canonical example audio",
    }
    for filename, payload in media_payloads.items():
        (tmp_path / filename).write_bytes(payload)

    class Client:
        def call(self, action, **params):
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling": return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
            if action == "findNotes": return [123]
            if action == "notesInfo": return [_live_note(row)]
            if action == "getMediaFilesNames": return ["uk_conquer.mp3", "example_uk_a.mp3"]
            if action == "multi":
                return [
                    {
                        "result": base64.b64encode(
                            media_payloads[item["params"]["filename"]]
                        ).decode("ascii"),
                        "error": None,
                    }
                    for item in params["actions"]
                ]
            raise AssertionError(action)

    assert verify_import(
        Client(),
        expected,
        {"uk_conquer.mp3", "example_uk_a.mp3"},
        audio_dir=tmp_path,
    ) == 1


@pytest.mark.parametrize(
    ("envelope", "message"),
    [
        (
            {
                "result": base64.b64encode(b"wrong live bytes").decode("ascii"),
                "error": None,
            },
            "bytes do not match canonical source",
        ),
        ({"result": "not-base64!", "error": None}, "invalid base64"),
        ({"result": False, "error": None}, "missing during byte verification"),
        ({"result": 123, "error": None}, "malformed live media data"),
        ({"result": None, "error": "read failed"}, "could not retrieve live media"),
        ({"result": "unused"}, "malformed live media data"),
    ],
)
def test_verify_import_rejects_unverified_live_media_bytes(
    tmp_path: Path, envelope: dict, message: str
) -> None:
    row = _row()
    live_note = _live_note(row)
    expected = Counter({
        tuple(field["value"] for field in live_note["fields"].values()): 1
    })
    filename = "same-name.mp3"
    (tmp_path / filename).write_bytes(b"canonical source bytes")

    class Client:
        def call(self, action, **params):
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling": return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
            if action == "findNotes": return [123]
            if action == "notesInfo": return [live_note]
            if action == "getMediaFilesNames": return [filename]
            if action == "multi":
                assert params["actions"] == [{
                    "action": "retrieveMediaFile",
                    "version": import_module.ANKI_CONNECT_API_VERSION,
                    "params": {"filename": filename},
                }]
                return [envelope]
            raise AssertionError(action)

    with pytest.raises(AnkiConnectError, match=message):
        verify_import(
            Client(),
            expected,
            {filename},
            audio_dir=tmp_path,
        )


def test_verify_import_rejects_dirty_new_recognition_card(tmp_path: Path) -> None:
    row = _row(
        deck="English Academic Vocabulary::C1",
        guid="canonical-guid",
        tags="",
    )
    notes = tmp_path / "notes.jsonl"
    _write_jsonl(notes, [row])
    live_note = _live_note(row)
    live_note.update({
        "noteId": 1,
        "guid": row["guid"],
        "cards": [10, 11],
        "tags": [],
    })
    cards = [
        {
            "cardId": 10,
            "note": 1,
            "ord": 0,
            "deckName": row["deck"],
            "modelName": EAVM_MODEL_NAME,
            "type": 0,
            "queue": -1,
            "interval": 0,
            "reps": 0,
            "lapses": 0,
        },
        {
            "cardId": 11,
            "note": 1,
            "ord": 1,
            "deckName": row["deck"],
            "modelName": EAVM_MODEL_NAME,
            "type": 0,
            "queue": 0,
            "interval": 0,
            "reps": 0,
            "lapses": 0,
        },
    ]

    class Client:
        def call(self, action, **params):
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling": return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
            if action == "findNotes": return [1]
            if action == "notesInfo": return [live_note]
            if action == "findCards": return [10, 11]
            if action == "cardsInfo": return cards
            if action == "getMediaFilesNames": return []
            raise AssertionError(action)

    with pytest.raises(AnkiConnectError, match="New card 10 is not active and unreviewed"):
        verify_import(
            Client(),
            load_expected_signatures(notes),
            set(),
            load_expected_records(notes),
            audio_dir=tmp_path,
        )


def test_verify_import_preserves_prior_schedule_and_checks_only_new_card_state(
    tmp_path: Path,
) -> None:
    row = _row(
        deck="English Academic Vocabulary::C1",
        guid="canonical-guid",
        tags="",
    )
    notes = tmp_path / "notes.jsonl"
    _write_jsonl(notes, [row])
    live_note = _live_note(row)
    live_note.update({
        "noteId": 1,
        "guid": row["guid"],
        "cards": [10, 11],
        "tags": [],
    })
    prior_schedule = (2, 2, 10, 3, 2500, 4, 0, 0)
    cards = [
        {
            "cardId": 10,
            "note": 1,
            "ord": 0,
            "deckName": row["deck"],
            "modelName": EAVM_MODEL_NAME,
            "type": prior_schedule[0],
            "queue": prior_schedule[1],
            "due": prior_schedule[2],
            "interval": prior_schedule[3],
            "factor": prior_schedule[4],
            "reps": prior_schedule[5],
            "lapses": prior_schedule[6],
            "left": prior_schedule[7],
        },
        {
            "cardId": 11,
            "note": 1,
            "ord": 1,
            "deckName": row["deck"],
            "modelName": EAVM_MODEL_NAME,
            "type": 0,
            "queue": 0,
            "interval": 0,
            "factor": 0,
            "reps": 0,
            "lapses": 0,
            "left": 0,
        },
    ]
    prior = ExistingCollectionSnapshot(
        note_ids=frozenset({1}),
        card_ids=frozenset({10}),
        schedules={10: prior_schedule},
        had_production_template=False,
    )

    class Client:
        def call(self, action, **params):
            if action == "modelNamesAndIds": return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling": return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
            if action == "findNotes": return [1]
            if action == "notesInfo": return [live_note]
            if action == "findCards": return [10, 11]
            if action == "cardsInfo": return cards
            if action == "getMediaFilesNames": return []
            raise AssertionError(action)

    assert verify_import(
        Client(),
        load_expected_signatures(notes),
        set(),
        load_expected_records(notes),
        prior,
        audio_dir=tmp_path,
    ) == 1


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (None, None),
        ("schedule", "Schedule changed on established card 10"),
        ("note_id", "Established note IDs changed during migration"),
    ],
)
def test_verify_import_allows_only_missing_identity_with_pristine_cards(
    tmp_path: Path, mutation: str | None, error: str | None,
) -> None:
    existing = _row(
        word="alien",
        pos="noun",
        guid="existing-guid",
        deck="English Academic Vocabulary::Oxford",
    )
    added = _row(
        word="alien",
        pos="adjective",
        tags="SecondarySense",
        guid="added-guid",
        deck="English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses",
    )
    notes = tmp_path / "notes.jsonl"
    _write_jsonl(notes, [existing, added])
    live_notes = []
    for note_id, card_ids, row in (
        (1, [10, 11], existing),
        (2, [20, 21], added),
    ):
        note = _live_note(row)
        note.update({
            "noteId": note_id,
            "guid": row["guid"],
            "cards": card_ids,
            "tags": str(row.get("tags") or "").split(),
        })
        live_notes.append(note)
    prior_schedule = (2, 2, 10, 3, 2500, 4, 0, 0)
    cards = [
        {
            "cardId": card_id,
            "note": note_id,
            "ord": ordinal,
            "deckName": row["deck"],
            "modelName": EAVM_MODEL_NAME,
            "type": prior_schedule[0] if note_id == 1 else 0,
            "queue": prior_schedule[1] if note_id == 1 else 0,
            "due": prior_schedule[2] if note_id == 1 else 0,
            "interval": prior_schedule[3] if note_id == 1 else 0,
            "factor": prior_schedule[4] if note_id == 1 else 0,
            "reps": prior_schedule[5] if note_id == 1 else 0,
            "lapses": prior_schedule[6] if note_id == 1 else 0,
            "left": prior_schedule[7] if note_id == 1 else 0,
        }
        for note_id, row, pairs in (
            (1, existing, ((10, 0), (11, 1))),
            (2, added, ((20, 0), (21, 1))),
        )
        for card_id, ordinal in pairs
    ]
    if mutation == "schedule":
        cards[0]["interval"] = 4
    elif mutation == "note_id":
        live_notes[0]["noteId"] = 3
        for card in cards:
            if card["note"] == 1:
                card["note"] = 3
    prior = ExistingCollectionSnapshot(
        note_ids=frozenset({1}),
        card_ids=frozenset({10, 11}),
        schedules={10: prior_schedule, 11: prior_schedule},
        had_production_template=True,
        note_identities={1: ("alien", "noun", "C1")},
    )

    class Client:
        def call(self, action, **params):
            if action == "modelNamesAndIds":
                return {EAVM_MODEL_NAME: EAVM_MODEL_ID}
            if action == "modelFieldNames": return list(EAVM_FIELDS)
            if action == "modelTemplates": return _canonical_templates()
            if action == "modelStyling":
                return {"css": load_production_css(Path("design/EAVM/styling.txt"))}
            if action == "findNotes":
                return [note["noteId"] for note in live_notes]
            if action == "notesInfo":
                requested = set(params["notes"])
                return [note for note in live_notes if note["noteId"] in requested]
            if action == "findCards": return [card["cardId"] for card in cards]
            if action == "cardsInfo":
                requested = set(params["cards"])
                return [card for card in cards if card["cardId"] in requested]
            if action == "getMediaFilesNames": return []
            raise AssertionError(action)

    args = (
        Client(),
        load_expected_signatures(notes),
        set(),
        load_expected_records(notes),
        prior,
    )
    if error is None:
        assert verify_import(*args, audio_dir=tmp_path) == 2
    else:
        with pytest.raises(AnkiConnectError, match=error):
            verify_import(*args, audio_dir=tmp_path)


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
            "CollocationSources": row["collocation_sources"],
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
            if action == "multi":
                nested = params["actions"]
                if nested[0]["action"] == "retrieveMediaFile":
                    return [{
                        "result": base64.b64encode(b"existing").decode("ascii"),
                        "error": None,
                    }]
                return ["missing.mp3"]
            raise AssertionError(action)

    assert sync_missing_media(
        Client(), {"existing.mp3", "missing.mp3"}, tmp_path
    ) == 1
    actions = next(
        params["actions"]
        for action, params in calls
        if action == "multi" and params["actions"][0]["action"] == "storeMediaFile"
    )
    assert actions == [{
        "action": "storeMediaFile",
        "params": {"filename": "missing.mp3", "path": missing.resolve().as_posix()},
    }]


def test_sync_missing_media_overwrites_same_name_with_stale_bytes(tmp_path: Path):
    media = tmp_path / "same-name.mp3"
    media.write_bytes(b"canonical")
    calls = []

    class Client:
        def call(self, action, **params):
            calls.append((action, params))
            if action == "getMediaFilesNames":
                return [media.name]
            if action == "multi":
                nested = params["actions"]
                if nested[0]["action"] == "retrieveMediaFile":
                    return [{
                        "result": base64.b64encode(b"stale").decode("ascii"),
                        "error": None,
                    }]
                return [media.name]
            raise AssertionError(action)

    assert sync_missing_media(Client(), {media.name}, tmp_path) == 1
    store_actions = [
        params["actions"]
        for action, params in calls
        if action == "multi" and params["actions"][0]["action"] == "storeMediaFile"
    ]
    assert store_actions == [[{
        "action": "storeMediaFile",
        "params": {"filename": media.name, "path": media.resolve().as_posix()},
    }]]


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


def test_import_and_verify_uses_absolute_forward_slash_package_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    notes = tmp_path / "notes.jsonl"
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    row = _row(uk_audio="", example_audio_uk="", example_audio_us="")
    _write_jsonl(notes, [row])
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    provenance_path, provenance_inputs, receipt_path = _write_test_provenance(
        tmp_path, package, notes, audio_dir
    )
    monkeypatch.setattr(
        import_module,
        "export_and_verify_live_guid_map",
        lambda *args, **kwargs: LiveGuidProof(
            "fixture.apkg", "a" * 64, "b" * 64, "collection.anki2", 1, 2
        ),
    )
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
                    {"cardId": 10, "note": 1, "ord": 0, "deckName": row.get("deck", ""), "modelName": EAVM_MODEL_NAME,
                     "type": 0, "queue": 0, "interval": 0, "reps": 0, "lapses": 0},
                    {"cardId": 11, "note": 1, "ord": 1, "deckName": row.get("deck", ""), "modelName": EAVM_MODEL_NAME,
                     "type": 0, "queue": 0, "interval": 0, "reps": 0, "lapses": 0},
                ]
            if action == "getMediaFilesNames": return []
            raise AssertionError(action)

    assert import_and_verify(
        Client(), package, notes, tmp_path / "scratch", audio_dir,
        provenance_path=provenance_path,
        provenance_inputs=provenance_inputs,
        receipt_path=receipt_path,
    ) == 1
    import_call = next(call for call in calls if call[0] == "importPackage")
    assert import_call[1]["path"] == package.resolve().as_posix()
    assert receipt_path.is_file()


def test_import_main_stops_before_package_or_anki_when_canonical_guard_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    def reject(_project_paths):
        raise ValueError("semantic authorities disagree")

    monkeypatch.setattr(import_module, "validate_canonical_release_state", reject)

    assert import_module.main([
        "--dry-run",
        "--package",
        str(tmp_path / "missing.apkg"),
    ]) == 1
    assert "semantic authorities disagree" in capsys.readouterr().err


def test_import_main_dry_run_rejects_archive_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"invalid")
    monkeypatch.setattr(
        import_module, "validate_canonical_release_state", lambda _paths: None
    )
    monkeypatch.setattr(
        import_module,
        "validate_local_inputs",
        lambda *args: (Counter({("signature",): 1}), set()),
    )
    monkeypatch.setattr(
        import_module, "validate_package_provenance", lambda *args, **kwargs: None
    )

    def reject(*args, **kwargs):
        raise PackageArchiveError("invalid APKG archive: fixture")

    monkeypatch.setattr(import_module, "validate_package_archive", reject)

    assert import_module.main(["--dry-run", "--package", str(package)]) == 1
    assert "invalid APKG archive" in capsys.readouterr().err
