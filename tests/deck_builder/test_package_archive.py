from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import zipfile

import genanki
import pytest

import src.deck_builder.package_archive as package_archive
from src.deck_builder.package_archive import (
    PackageArchiveError,
    validate_package_archive,
)
from src.deck_builder.package_command import (
    EAVM_FIELD_NAMES,
    EAVM_JSON_TO_FIELD,
    EAVM_MODEL_ID,
    EAVM_MODEL_NAME,
    EavmTemplate,
    configure_genanki_requirements,
    generate_deterministic_id,
)
from src.deck_builder.package_contract import json_value_for_key


CSS = "body { color: #123; }"
TEMPLATES = (
    EavmTemplate("Recognition", "{{Word}}", "{{Definition}}"),
    EavmTemplate(
        "Production (VI -> EN)",
        "{{#DefinitionVI}}{{#Example}}{{#ProductionAnswer}}"
        "{{type:ProductionAnswer}}"
        "{{/ProductionAnswer}}{{/Example}}{{/DefinitionVI}}",
        "{{FrontSide}} {{Definition}}",
    ),
)


def _fixture_package(tmp_path: Path):
    row = {key: "" for key, _field in EAVM_JSON_TO_FIELD}
    row.update(
        {
            "word": "conquer",
            "pos": "verb",
            "definition": "take control",
            "definition_vi": "chinh phục",
            "example": "They conquered it.",
            "production_answer": "conquer",
            "cefr": "C1",
            "deck": "English Academic Vocabulary::C1",
            "guid": "canonical-guid",
            "tags": "C1 academic",
            "uk_audio": "[sound:clip.mp3]",
        }
    )
    notes = tmp_path / "anki_notes.jsonl"
    notes.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    media = tmp_path / "clip.mp3"
    media.write_bytes(b"ID3 canonical audio")

    model = genanki.Model(
        EAVM_MODEL_ID,
        EAVM_MODEL_NAME,
        fields=[{"name": name} for name in EAVM_FIELD_NAMES],
        templates=[template.for_genanki() for template in TEMPLATES],
        css=CSS,
    )
    configure_genanki_requirements(model)
    deck_name = row["deck"]
    deck = genanki.Deck(generate_deterministic_id(deck_name), deck_name)
    deck.add_note(
        genanki.Note(
            model=model,
            fields=[json_value_for_key(row, key) for key, _field in EAVM_JSON_TO_FIELD],
            guid=row["guid"],
            tags=row["tags"].split(),
        )
    )
    package = tmp_path / "deck.apkg"
    writer = genanki.Package(deck)
    writer.media_files = [str(media)]
    writer.write_to_file(package)
    return package, notes, {media.name: media}


def _validate(package: Path, notes: Path, media: dict[str, Path]):
    return validate_package_archive(
        package,
        notes,
        media,
        expected_templates=TEMPLATES,
        expected_css=CSS,
    )


def _archive_entries(package: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(package) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _replace_archive(package: Path, entries: dict[str, bytes]) -> None:
    replacement = package.with_suffix(".replacement.apkg")
    with zipfile.ZipFile(replacement, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    replacement.replace(package)


def _mutate_collection(package: Path, tmp_path: Path, statement) -> None:
    entries = _archive_entries(package)
    collection = tmp_path / "mutated.anki2"
    collection.write_bytes(entries["collection.anki2"])
    connection = sqlite3.connect(collection)
    try:
        statement(connection)
        connection.commit()
    finally:
        connection.close()
    entries["collection.anki2"] = collection.read_bytes()
    _replace_archive(package, entries)


def test_validates_real_genanki_archive_contents(tmp_path: Path) -> None:
    package, notes, media = _fixture_package(tmp_path)

    report = _validate(package, notes, media)

    assert report.note_count == 1
    assert report.card_count == 2
    assert report.media_count == 1


def test_rejects_non_apkg_bytes(tmp_path: Path) -> None:
    package, notes, media = _fixture_package(tmp_path)
    package.write_bytes(b"not a zip archive")

    with pytest.raises(PackageArchiveError, match="invalid APKG archive"):
        _validate(package, notes, media)


def test_rejects_media_manifest_filename_mismatch(tmp_path: Path) -> None:
    package, notes, media = _fixture_package(tmp_path)
    entries = _archive_entries(package)
    entries["media"] = json.dumps({"0": "other.mp3"}).encode("utf-8")
    _replace_archive(package, entries)

    with pytest.raises(PackageArchiveError, match="media filename set mismatch"):
        _validate(package, notes, media)


def test_rejects_packaged_media_byte_mismatch(tmp_path: Path) -> None:
    package, notes, media = _fixture_package(tmp_path)
    entries = _archive_entries(package)
    entries["0"] = b"different audio"
    _replace_archive(package, entries)

    with pytest.raises(PackageArchiveError, match="media bytes do not match"):
        _validate(package, notes, media)


def test_rejects_model_contract_mismatch(tmp_path: Path) -> None:
    package, notes, media = _fixture_package(tmp_path)

    def mutate(connection: sqlite3.Connection) -> None:
        models = json.loads(connection.execute("SELECT models FROM col").fetchone()[0])
        models[str(EAVM_MODEL_ID)]["name"] = "Wrong model"
        connection.execute("UPDATE col SET models = ?", (json.dumps(models),))

    _mutate_collection(package, tmp_path, mutate)

    with pytest.raises(PackageArchiveError, match="model identity mismatch"):
        _validate(package, notes, media)


def test_rejects_note_field_mismatch(tmp_path: Path) -> None:
    package, notes, media = _fixture_package(tmp_path)
    _mutate_collection(
        package,
        tmp_path,
        lambda connection: connection.execute(
            "UPDATE notes SET flds = ?", ("wrong" + "\x1f" * 24,)
        ),
    )

    with pytest.raises(PackageArchiveError, match="note field mismatch"):
        _validate(package, notes, media)


@pytest.mark.parametrize(
    "assignment",
    [
        "usn = 0",
        "sfld = 'tampered sort field'",
        "csum = 1",
        "flags = 1",
        "data = 'dirty'",
    ],
)
def test_rejects_non_clean_packaged_note_metadata(
    tmp_path: Path, assignment: str
) -> None:
    package, notes, media = _fixture_package(tmp_path)
    _mutate_collection(
        package,
        tmp_path,
        lambda connection: connection.execute(
            f"UPDATE notes SET {assignment}"
        ),
    )

    with pytest.raises(PackageArchiveError, match="note clean metadata mismatch"):
        _validate(package, notes, media)


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("model", "latexsvg", True),
        ("field", "rtl", True),
        ("field", "font", "Unexpected Font"),
        ("template", "did", 1),
        ("template", "bqfmt", "unexpected browser template"),
    ],
)
def test_rejects_non_clean_packaged_model_metadata(
    tmp_path: Path, section: str, key: str, value
) -> None:
    package, notes, media = _fixture_package(tmp_path)

    def mutate(connection: sqlite3.Connection) -> None:
        models = json.loads(connection.execute("SELECT models FROM col").fetchone()[0])
        model = models[str(EAVM_MODEL_ID)]
        target = {
            "model": model,
            "field": model["flds"][0],
            "template": model["tmpls"][0],
        }[section]
        target[key] = value
        connection.execute("UPDATE col SET models = ?", (json.dumps(models),))

    _mutate_collection(package, tmp_path, mutate)

    with pytest.raises(PackageArchiveError, match="model clean metadata mismatch"):
        _validate(package, notes, media)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("dyn", 1),
        ("conf", 999),
        ("desc", "unexpected description"),
        ("collapsed", True),
        ("extendRev", 999),
        ("usn", 0),
    ],
)
def test_rejects_non_clean_packaged_deck_metadata(
    tmp_path: Path, key: str, value
) -> None:
    package, notes, media = _fixture_package(tmp_path)

    def mutate(connection: sqlite3.Connection) -> None:
        decks = json.loads(connection.execute("SELECT decks FROM col").fetchone()[0])
        target = next(
            payload for raw_id, payload in decks.items() if int(raw_id) != 1
        )
        target[key] = value
        connection.execute("UPDATE col SET decks = ?", (json.dumps(decks),))

    _mutate_collection(package, tmp_path, mutate)

    with pytest.raises(PackageArchiveError, match="deck clean metadata mismatch"):
        _validate(package, notes, media)


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ("collection_config", "collection configuration is not clean"),
        ("deck_configs", "deck configuration registry is not clean"),
        ("tags", "collection tag registry is not clean"),
        ("default_deck", "Default deck clean metadata mismatch"),
    ],
)
def test_rejects_non_clean_packaged_collection_metadata(
    tmp_path: Path, section: str, message: str
) -> None:
    package, notes, media = _fixture_package(tmp_path)

    def mutate(connection: sqlite3.Connection) -> None:
        if section == "collection_config":
            column = "conf"
            payload = json.loads(
                connection.execute("SELECT conf FROM col").fetchone()[0]
            )
            payload["sortBackwards"] = True
        elif section == "deck_configs":
            column = "dconf"
            payload = json.loads(
                connection.execute("SELECT dconf FROM col").fetchone()[0]
            )
            payload["1"]["new"]["perDay"] = 999
        elif section == "tags":
            column = "tags"
            payload = {"unexpected": 1}
        else:
            column = "decks"
            payload = json.loads(
                connection.execute("SELECT decks FROM col").fetchone()[0]
            )
            payload["1"]["dyn"] = 1
        connection.execute(
            f"UPDATE col SET {column} = ?", (json.dumps(payload),)
        )

    _mutate_collection(package, tmp_path, mutate)

    with pytest.raises(PackageArchiveError, match=message):
        _validate(package, notes, media)


def test_rejects_card_deck_mismatch(tmp_path: Path) -> None:
    package, notes, media = _fixture_package(tmp_path)
    _mutate_collection(
        package,
        tmp_path,
        lambda connection: connection.execute("UPDATE cards SET did = 1"),
    )

    with pytest.raises(PackageArchiveError, match="card deck mismatch"):
        _validate(package, notes, media)


@pytest.mark.parametrize(
    "assignment",
    [
        "usn = 0",
        "type = 2",
        "queue = -1",
        "due = 99",
        "ivl = 3",
        "factor = 2500",
        "reps = 1",
        "lapses = 1",
        "left = 1",
        "odue = 1",
        "odid = 1",
        "flags = 1",
        "data = 'dirty'",
    ],
)
def test_rejects_non_pristine_packaged_card_state(
    tmp_path: Path, assignment: str
) -> None:
    package, notes, media = _fixture_package(tmp_path)
    _mutate_collection(
        package,
        tmp_path,
        lambda connection: connection.execute(
            f"UPDATE cards SET {assignment} WHERE ord = 0"
        ),
    )

    with pytest.raises(PackageArchiveError, match="card scheduling/state mismatch"):
        _validate(package, notes, media)


@pytest.mark.parametrize(
    ("table_name", "statement"),
    [
        (
            "revlog",
            "INSERT INTO revlog VALUES (1, 1, -1, 1, 1, 0, 0, 0, 0)",
        ),
        ("graves", "INSERT INTO graves VALUES (-1, 1, 0)"),
    ],
)
def test_rejects_packaged_history_rows(
    tmp_path: Path, table_name: str, statement: str
) -> None:
    package, notes, media = _fixture_package(tmp_path)
    _mutate_collection(
        package,
        tmp_path,
        lambda connection: connection.execute(statement),
    )

    with pytest.raises(PackageArchiveError, match=f"non-empty {table_name} history"):
        _validate(package, notes, media)


def test_rejects_canonical_deck_id_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package, notes, media = _fixture_package(tmp_path)
    first = json.loads(notes.read_text(encoding="utf-8"))
    second = {**first, "guid": "second-guid", "deck": "A different deck"}
    notes.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in (first, second)),
        encoding="utf-8",
    )
    monkeypatch.setattr(package_archive, "_deterministic_deck_id", lambda _name: 7)

    with pytest.raises(PackageArchiveError, match="collide on one deterministic deck ID"):
        _validate(package, notes, media)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda connection: connection.execute(
                "DELETE FROM cards WHERE id = (SELECT MIN(id) FROM cards)"
            ),
            "card count mismatch",
        ),
        (
            lambda connection: connection.execute(
                "DELETE FROM notes WHERE id = (SELECT MIN(id) FROM notes)"
            ),
            "note count mismatch",
        ),
        (
            lambda connection: connection.execute(
                "INSERT INTO notes "
                "SELECT id + 1000, 'extra-guid', mid, mod, usn, tags, flds, "
                "sfld, csum, flags, data FROM notes LIMIT 1"
            ),
            "note count mismatch",
        ),
        (
            lambda connection: connection.execute(
                "INSERT INTO cards "
                "SELECT id + 1000, nid, did, ord, mod, usn, type, queue, due, "
                "ivl, factor, reps, lapses, left, odue, odid, flags, data "
                "FROM cards LIMIT 1"
            ),
            "card count mismatch",
        ),
    ],
)
def test_rejects_missing_or_extra_canonical_notes_and_cards(
    tmp_path: Path, mutation, message: str
) -> None:
    package, notes, media = _fixture_package(tmp_path)
    _mutate_collection(package, tmp_path, mutation)

    with pytest.raises(PackageArchiveError, match=message):
        _validate(package, notes, media)
