"""Offline validation of the concrete contents of a generated Anki package."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Mapping, Protocol, Sequence
import zipfile

import genanki
from genanki.package import APKG_COL, APKG_SCHEMA

from src.deck_builder.package_contract import (
    EAVM_FIELD_NAMES,
    EAVM_JSON_TO_FIELD,
    EAVM_MODEL_ID,
    EAVM_MODEL_NAME,
    EAVM_REQUIREMENTS_BY_FIELD,
)


class PackageArchiveError(ValueError):
    """The APKG archive does not contain the canonical packaged release."""


class ExpectedTemplate(Protocol):
    name: str
    front: str
    back: str


@dataclass(frozen=True, slots=True)
class PackageArchiveReport:
    note_count: int
    card_count: int
    media_count: int


@dataclass(frozen=True, slots=True)
class _ExpectedNote:
    guid: str
    fields: tuple[str, ...]
    tags: str
    deck_name: str
    deck_id: int
    card_ordinals: tuple[int, ...]


def _deterministic_deck_id(name: str) -> int:
    value = int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:8], 16)
    return (value & 0x7FFFFFFF) or 1


def _expected_card_ordinals(fields: tuple[str, ...]) -> tuple[int, ...]:
    field_index = {name: index for index, name in enumerate(EAVM_FIELD_NAMES)}
    ordinals: list[int] = []
    for ordinal, mode, required_fields in EAVM_REQUIREMENTS_BY_FIELD:
        values = [fields[field_index[name]] for name in required_fields]
        eligible = all(values) if mode == "all" else any(values)
        if eligible:
            ordinals.append(ordinal)
    return tuple(ordinals)


def _load_expected_notes(notes_jsonl: Path) -> dict[str, _ExpectedNote]:
    if not notes_jsonl.is_file():
        raise PackageArchiveError(f"canonical notes JSONL not found: {notes_jsonl}")
    expected: dict[str, _ExpectedNote] = {}
    try:
        with notes_jsonl.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise PackageArchiveError(
                        f"invalid canonical notes JSONL on line {line_number}: {exc}"
                    ) from exc
                if not isinstance(row, dict):
                    raise PackageArchiveError(
                        f"invalid canonical notes JSONL row {line_number}: expected object"
                    )
                guid = row.get("guid")
                deck_name = row.get("deck")
                raw_tags = row.get("tags") or ""
                if not isinstance(guid, str) or not guid:
                    raise PackageArchiveError(
                        f"invalid canonical note GUID on line {line_number}"
                    )
                if guid in expected:
                    raise PackageArchiveError(f"duplicate canonical note GUID: {guid!r}")
                if not isinstance(deck_name, str) or not deck_name:
                    raise PackageArchiveError(
                        f"invalid canonical note deck on line {line_number}"
                    )
                if not isinstance(raw_tags, str):
                    raise PackageArchiveError(
                        f"invalid canonical note tags on line {line_number}"
                    )
                fields: list[str] = []
                for key, _field_name in EAVM_JSON_TO_FIELD:
                    value = row.get(key) or ""
                    if not isinstance(value, str):
                        raise PackageArchiveError(
                            f"invalid canonical note field {key!r} on line {line_number}"
                        )
                    fields.append(value)
                field_tuple = tuple(fields)
                card_ordinals = _expected_card_ordinals(field_tuple)
                if not card_ordinals:
                    raise PackageArchiveError(
                        f"canonical note {guid!r} would generate no cards"
                    )
                tags = [tag.strip() for tag in raw_tags.split() if tag.strip()]
                expected[guid] = _ExpectedNote(
                    guid=guid,
                    fields=field_tuple,
                    tags=" " + " ".join(tags) + " ",
                    deck_name=deck_name,
                    deck_id=_deterministic_deck_id(deck_name),
                    card_ordinals=card_ordinals,
                )
    except OSError as exc:
        raise PackageArchiveError(f"could not read canonical notes JSONL: {exc}") from exc
    if not expected:
        raise PackageArchiveError("canonical notes JSONL contains no notes")
    return expected


def _sha256_stream(handle) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _validate_media_manifest(
    archive: zipfile.ZipFile,
    archive_names: list[str],
    expected_media: Mapping[str, Path],
) -> dict[str, str]:
    if len(archive_names) != len(set(archive_names)):
        raise PackageArchiveError("APKG contains duplicate archive entry names")
    try:
        manifest = json.loads(archive.read("media").decode("utf-8"))
    except KeyError as exc:
        raise PackageArchiveError("APKG is missing its media manifest") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageArchiveError(f"APKG media manifest is invalid: {exc}") from exc
    if not isinstance(manifest, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in manifest.items()
    ):
        raise PackageArchiveError("APKG media manifest must map strings to strings")
    expected_keys = [str(index) for index in range(len(manifest))]
    try:
        actual_keys = sorted(manifest, key=lambda key: int(key))
    except ValueError as exc:
        raise PackageArchiveError("APKG media manifest keys must be numeric") from exc
    if actual_keys != expected_keys:
        raise PackageArchiveError("APKG media manifest keys are not contiguous")
    if len(set(manifest.values())) != len(manifest):
        raise PackageArchiveError("APKG media manifest contains duplicate filenames")

    expected_names = set(expected_media)
    if set(manifest.values()) != expected_names:
        missing = sorted(expected_names - set(manifest.values()))
        extra = sorted(set(manifest.values()) - expected_names)
        raise PackageArchiveError(
            f"APKG media filename set mismatch: missing={missing[:5]!r} extra={extra[:5]!r}"
        )
    expected_archive_names = {"collection.anki2", "media", *manifest.keys()}
    if set(archive_names) != expected_archive_names:
        missing = sorted(expected_archive_names - set(archive_names))
        extra = sorted(set(archive_names) - expected_archive_names)
        raise PackageArchiveError(
            f"APKG archive entry set mismatch: missing={missing[:5]!r} extra={extra[:5]!r}"
        )

    for entry_name in expected_keys:
        filename = manifest[entry_name]
        source_path = Path(expected_media[filename])
        if Path(filename).name != filename or source_path.name != filename:
            raise PackageArchiveError(f"invalid expected media filename: {filename!r}")
        if not source_path.is_file():
            raise PackageArchiveError(f"expected media file not found: {source_path}")
        try:
            with archive.open(entry_name) as packaged, source_path.open("rb") as source:
                packaged_sha256 = _sha256_stream(packaged)
                source_sha256 = _sha256_stream(source)
        except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise PackageArchiveError(
                f"could not read packaged media {filename!r}: {exc}"
            ) from exc
        if packaged_sha256 != source_sha256:
            raise PackageArchiveError(
                f"APKG media bytes do not match source media: {filename!r}"
            )
    return manifest


def _expected_model_requirements() -> list[list[object]]:
    field_index = {name: index for index, name in enumerate(EAVM_FIELD_NAMES)}
    return [
        [ordinal, mode, sorted(field_index[name] for name in required_fields)]
        for ordinal, mode, required_fields in EAVM_REQUIREMENTS_BY_FIELD
    ]


def _without_mod(payload: Mapping[str, object]) -> dict[str, object]:
    """Return stable generator-owned metadata without build-time timestamps."""

    return {key: value for key, value in payload.items() if key != "mod"}


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _expected_model_payload(
    expected_templates: Sequence[ExpectedTemplate],
    expected_css: str,
    expected_deck_id: int,
) -> dict[str, object]:
    """Reproduce genanki's clean model metadata for the pinned contract."""

    model = genanki.Model(
        EAVM_MODEL_ID,
        EAVM_MODEL_NAME,
        fields=[{"name": name} for name in EAVM_FIELD_NAMES],
        templates=[
            {"name": template.name, "qfmt": template.front, "afmt": template.back}
            for template in expected_templates
        ],
        css=expected_css,
    )
    model._req = _expected_model_requirements()
    return model.to_json(timestamp=0, deck_id=expected_deck_id)


def _validate_model(
    models: object,
    expected_templates: Sequence[ExpectedTemplate],
    expected_css: str,
    expected_notes: Mapping[str, _ExpectedNote],
) -> None:
    if not isinstance(models, dict) or set(models) != {str(EAVM_MODEL_ID)}:
        raise PackageArchiveError("APKG must contain exactly the canonical EAVM model")
    model = models[str(EAVM_MODEL_ID)]
    if not isinstance(model, dict):
        raise PackageArchiveError("APKG EAVM model payload is invalid")
    if str(model.get("id")) != str(EAVM_MODEL_ID) or model.get("name") != EAVM_MODEL_NAME:
        raise PackageArchiveError("APKG EAVM model identity mismatch")
    if model.get("type") != 0 or model.get("sortf") != 0:
        raise PackageArchiveError("APKG EAVM model type/sort field mismatch")
    if model.get("css") != expected_css:
        raise PackageArchiveError("APKG EAVM CSS mismatch")
    fields = model.get("flds")
    if not isinstance(fields, list) or len(fields) != len(EAVM_FIELD_NAMES):
        raise PackageArchiveError("APKG EAVM field count mismatch")
    actual_fields: list[tuple[object, object]] = []
    for field in fields:
        if not isinstance(field, dict):
            raise PackageArchiveError("APKG EAVM field payload is invalid")
        actual_fields.append((field.get("ord"), field.get("name")))
    expected_fields = list(enumerate(EAVM_FIELD_NAMES))
    if actual_fields != expected_fields:
        raise PackageArchiveError("APKG EAVM field order/name mismatch")

    templates = model.get("tmpls")
    if not isinstance(templates, list) or len(templates) != len(expected_templates):
        raise PackageArchiveError("APKG EAVM template count mismatch")
    actual_templates: list[tuple[object, object, object, object]] = []
    for template in templates:
        if not isinstance(template, dict):
            raise PackageArchiveError("APKG EAVM template payload is invalid")
        actual_templates.append(
            (
                template.get("ord"),
                template.get("name"),
                template.get("qfmt"),
                template.get("afmt"),
            )
        )
    expected_template_rows = [
        (ordinal, template.name, template.front, template.back)
        for ordinal, template in enumerate(expected_templates)
    ]
    if actual_templates != expected_template_rows:
        raise PackageArchiveError("APKG EAVM template order/content mismatch")
    if model.get("req") != _expected_model_requirements():
        raise PackageArchiveError("APKG EAVM card-generation requirements mismatch")

    ordered_decks: dict[str, int] = {}
    for note in expected_notes.values():
        ordered_decks.setdefault(note.deck_name, note.deck_id)
    expected_model = _expected_model_payload(
        expected_templates,
        expected_css,
        list(ordered_decks.values())[-1],
    )
    if not _is_integer(model.get("mod")):
        raise PackageArchiveError("APKG EAVM model modification timestamp is invalid")
    if _without_mod(model) != _without_mod(expected_model):
        raise PackageArchiveError("APKG EAVM model clean metadata mismatch")


def _load_collection_contract(
    connection: sqlite3.Connection,
) -> tuple[dict[str, object], dict[str, object]]:
    quick_check = connection.execute("PRAGMA quick_check").fetchall()
    if quick_check != [("ok",)]:
        raise PackageArchiveError(f"APKG collection SQLite integrity check failed: {quick_check!r}")
    rows = connection.execute(
        "SELECT models, decks, conf, dconf, tags FROM col"
    ).fetchall()
    if len(rows) != 1:
        raise PackageArchiveError("APKG collection must contain exactly one col row")
    try:
        models, decks, collection_config, deck_configs, tags = (
            json.loads(value) for value in rows[0]
        )
    except (TypeError, json.JSONDecodeError) as exc:
        raise PackageArchiveError(f"APKG collection model/deck JSON is invalid: {exc}") from exc
    if any(
        not isinstance(value, dict)
        for value in (models, decks, collection_config, deck_configs, tags)
    ):
        raise PackageArchiveError("APKG collection metadata JSON must be objects")

    clean = sqlite3.connect(":memory:")
    try:
        clean.executescript(APKG_SCHEMA)
        clean.executescript(APKG_COL)
        clean_row = clean.execute(
            "SELECT decks, conf, dconf, tags FROM col"
        ).fetchone()
    finally:
        clean.close()
    assert clean_row is not None
    clean_decks, clean_collection_config, clean_deck_configs, clean_tags = (
        json.loads(value) for value in clean_row
    )
    if collection_config != clean_collection_config:
        raise PackageArchiveError("APKG collection configuration is not clean")
    if deck_configs != clean_deck_configs:
        raise PackageArchiveError("APKG deck configuration registry is not clean")
    if tags != clean_tags:
        raise PackageArchiveError("APKG collection tag registry is not clean")
    default_deck = decks.get("1")
    clean_default_deck = clean_decks.get("1")
    if not isinstance(default_deck, dict) or not _is_integer(default_deck.get("mod")):
        raise PackageArchiveError("APKG Default deck metadata is invalid")
    if not isinstance(clean_default_deck, dict) or _without_mod(
        default_deck
    ) != _without_mod(clean_default_deck):
        raise PackageArchiveError("APKG Default deck clean metadata mismatch")
    return models, decks


def _validate_decks(decks: dict[str, object], expected: Mapping[str, _ExpectedNote]) -> None:
    expected_decks: dict[int, str] = {}
    for note in expected.values():
        previous = expected_decks.get(note.deck_id)
        if previous is not None and previous != note.deck_name:
            raise PackageArchiveError(
                "canonical deck names collide on one deterministic deck ID: "
                f"{previous!r}, {note.deck_name!r}"
            )
        expected_decks[note.deck_id] = note.deck_name
    actual_decks: dict[int, str] = {}
    actual_payloads: dict[int, dict[str, object]] = {}
    for raw_id, raw_deck in decks.items():
        if not isinstance(raw_deck, dict):
            raise PackageArchiveError("APKG deck payload is invalid")
        try:
            deck_id = int(raw_id)
            payload_id = int(raw_deck.get("id"))
        except (TypeError, ValueError) as exc:
            raise PackageArchiveError("APKG deck identity is invalid") from exc
        deck_name = raw_deck.get("name")
        if payload_id != deck_id or not isinstance(deck_name, str) or not deck_name:
            raise PackageArchiveError("APKG deck identity/name mismatch")
        if deck_id in actual_decks or deck_name in actual_decks.values():
            raise PackageArchiveError("APKG contains duplicate deck identities or names")
        actual_decks[deck_id] = deck_name
        actual_payloads[deck_id] = raw_deck
    if actual_decks.get(1) != "Default":
        raise PackageArchiveError("APKG is missing the canonical Default deck metadata")
    non_default = {key: value for key, value in actual_decks.items() if key != 1}
    if non_default != expected_decks:
        raise PackageArchiveError("APKG deck registry does not match canonical note decks")
    for deck_id, deck_name in expected_decks.items():
        actual_payload = actual_payloads[deck_id]
        expected_payload = genanki.Deck(deck_id, deck_name).to_json()
        if not _is_integer(actual_payload.get("mod")):
            raise PackageArchiveError(
                f"APKG deck modification timestamp is invalid: {deck_name!r}"
            )
        if _without_mod(actual_payload) != _without_mod(expected_payload):
            raise PackageArchiveError(
                f"APKG deck clean metadata mismatch: {deck_name!r}"
            )


def _validate_notes_and_cards(
    connection: sqlite3.Connection,
    expected: Mapping[str, _ExpectedNote],
) -> tuple[int, int]:
    for table_name in ("revlog", "graves"):
        row = connection.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()
        if row != (0,):
            raise PackageArchiveError(
                f"APKG collection contains non-empty {table_name} history"
            )

    note_rows = connection.execute(
        "SELECT id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data "
        "FROM notes"
    ).fetchall()
    if len(note_rows) != len(expected):
        raise PackageArchiveError(
            f"APKG canonical note count mismatch: expected {len(expected)}, got {len(note_rows)}"
        )
    expected_by_note_id: dict[int, _ExpectedNote] = {}
    seen_guids: set[str] = set()
    for (
        note_id,
        guid,
        model_id,
        modified,
        update_sequence,
        tags,
        fields_text,
        sort_field,
        checksum,
        flags,
        data,
    ) in note_rows:
        if not isinstance(guid, str) or guid in seen_guids or guid not in expected:
            raise PackageArchiveError(f"APKG contains an unexpected/duplicate note GUID: {guid!r}")
        if model_id != EAVM_MODEL_ID:
            raise PackageArchiveError(f"APKG note {guid!r} uses a non-canonical model")
        target = expected[guid]
        if not isinstance(fields_text, str) or tuple(fields_text.split("\x1f")) != target.fields:
            raise PackageArchiveError(f"APKG note field mismatch: {guid!r}")
        if tags != target.tags:
            raise PackageArchiveError(f"APKG note tag mismatch: {guid!r}")
        if not _is_integer(modified):
            raise PackageArchiveError(f"APKG note modification timestamp is invalid: {guid!r}")
        if (
            update_sequence,
            sort_field,
            checksum,
            flags,
            data,
        ) != (-1, target.fields[0], 0, 0, ""):
            raise PackageArchiveError(f"APKG note clean metadata mismatch: {guid!r}")
        seen_guids.add(guid)
        expected_by_note_id[int(note_id)] = target
    if seen_guids != set(expected):
        raise PackageArchiveError("APKG canonical GUID coverage mismatch")

    card_rows = connection.execute(
        "SELECT id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, "
        "lapses, left, odue, odid, flags, data FROM cards"
    ).fetchall()
    expected_card_count = sum(len(note.card_ordinals) for note in expected.values())
    if len(card_rows) != expected_card_count:
        raise PackageArchiveError(
            f"APKG canonical card count mismatch: expected {expected_card_count}, got {len(card_rows)}"
        )
    ordinals_by_note: dict[int, list[int]] = {}
    for (
        _card_id,
        note_id,
        deck_id,
        ordinal,
        modified,
        update_sequence,
        card_type,
        queue,
        due,
        interval,
        factor,
        reps,
        lapses,
        left,
        original_due,
        original_deck_id,
        flags,
        data,
    ) in card_rows:
        try:
            note_key = int(note_id)
            deck_key = int(deck_id)
            ordinal_value = int(ordinal)
        except (TypeError, ValueError) as exc:
            raise PackageArchiveError("APKG card identity is invalid") from exc
        target = expected_by_note_id.get(note_key)
        if target is None:
            raise PackageArchiveError("APKG contains a card for an unexpected note")
        if deck_key != target.deck_id:
            raise PackageArchiveError(f"APKG card deck mismatch: {target.guid!r}")
        if not _is_integer(modified):
            raise PackageArchiveError(
                f"APKG card modification timestamp is invalid: {target.guid!r}"
            )
        packaged_state = (
            update_sequence,
            card_type,
            queue,
            due,
            interval,
            factor,
            reps,
            lapses,
            left,
            original_due,
            original_deck_id,
            flags,
            data,
        )
        if packaged_state != (-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""):
            raise PackageArchiveError(
                f"APKG card scheduling/state mismatch: {target.guid!r}"
            )
        ordinals_by_note.setdefault(note_key, []).append(ordinal_value)
    for note_id, target in expected_by_note_id.items():
        actual_ordinals = tuple(sorted(ordinals_by_note.get(note_id, [])))
        if actual_ordinals != target.card_ordinals:
            raise PackageArchiveError(
                f"APKG card ordinal mismatch for {target.guid!r}: "
                f"expected {target.card_ordinals!r}, got {actual_ordinals!r}"
            )
    return len(note_rows), len(card_rows)


def validate_package_archive(
    package_path: Path,
    notes_jsonl: Path,
    expected_media: Mapping[str, Path],
    *,
    expected_templates: Sequence[ExpectedTemplate],
    expected_css: str,
) -> PackageArchiveReport:
    """Validate archive bytes against canonical notes, design, decks, and media."""

    package_path = Path(package_path)
    expected = _load_expected_notes(Path(notes_jsonl))
    try:
        with zipfile.ZipFile(package_path) as archive, tempfile.TemporaryDirectory() as temp_dir:
            archive_names = archive.namelist()
            manifest = _validate_media_manifest(archive, archive_names, expected_media)
            collection_path = Path(temp_dir) / "collection.anki2"
            try:
                with archive.open("collection.anki2") as source, collection_path.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
            except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PackageArchiveError(f"could not read APKG collection: {exc}") from exc

            connection: sqlite3.Connection | None = None
            try:
                uri = f"file:{collection_path.as_posix()}?mode=ro&immutable=1"
                connection = sqlite3.connect(uri, uri=True)
                connection.execute("PRAGMA query_only = ON")
                models, decks = _load_collection_contract(connection)
                _validate_decks(decks, expected)
                _validate_model(models, expected_templates, expected_css, expected)
                note_count, card_count = _validate_notes_and_cards(connection, expected)
            except (sqlite3.DatabaseError, OSError) as exc:
                raise PackageArchiveError(f"invalid APKG collection database: {exc}") from exc
            finally:
                if connection is not None:
                    connection.close()
    except PackageArchiveError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise PackageArchiveError(f"invalid APKG archive: {exc}") from exc
    return PackageArchiveReport(
        note_count=note_count,
        card_count=card_count,
        media_count=len(manifest),
    )
