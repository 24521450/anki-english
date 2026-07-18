"""Post-import proof of canonical GUIDs by exporting the live Anki deck.

AnkiConnect ``notesInfo`` deliberately does not expose the note GUID.  The
only supported, read-only boundary that does is an APKG export, whose SQLite
``notes.guid`` column is inspected here.  This module is intentionally
independent of the mutating import orchestration so the archive contract can
be tested with small synthetic exports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Mapping
import zipfile

from src.deck_builder.package_contract import (
    EAVM_FIELD_NAMES,
    EAVM_MODEL_ID,
    EAVM_MODEL_NAME,
)


ROOT_DECK = "English Academic Vocabulary"
SUPPORTED_COLLECTION_ENTRIES = ("collection.anki21", "collection.anki2")
UNSUPPORTED_COLLECTION_ENTRY = "collection.anki21b"


class LiveGuidProofError(ValueError):
    """The live export cannot prove the canonical note/card identity set."""


@dataclass(frozen=True, slots=True)
class LiveGuidProof:
    """Stable evidence emitted after a successful live export inspection."""

    archive_name: str
    archive_sha256: str
    guid_map_sha256: str
    collection_format: str
    note_count: int
    card_count: int

    def as_receipt_payload(self) -> dict[str, object]:
        return {
            "phase": "post_import_export",
            "archive_name": self.archive_name,
            "archive_sha256": self.archive_sha256,
            "guid_map_sha256": self.guid_map_sha256,
            "collection_format": self.collection_format,
            "note_count": self.note_count,
            "card_count": self.card_count,
        }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _target_fields(target: Mapping[str, Any]) -> tuple[str, ...]:
    fields = target.get("fields")
    if not isinstance(fields, Mapping):
        raise LiveGuidProofError("canonical target has no field mapping")
    return tuple(str(fields.get(name) or "") for name in EAVM_FIELD_NAMES)


def _target_tags(target: Mapping[str, Any]) -> set[str]:
    raw = target.get("tags") or []
    if isinstance(raw, str):
        return {tag for tag in raw.split() if tag}
    if not isinstance(raw, (list, tuple, set)):
        raise LiveGuidProofError("canonical target has malformed tags")
    return {str(tag) for tag in raw if str(tag)}


def _expected_guid_targets(
    expected_records: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> dict[str, tuple[tuple[str, ...], Mapping[str, Any]]]:
    by_guid: dict[str, tuple[tuple[str, ...], Mapping[str, Any]]] = {}
    for identity, target in expected_records.items():
        guid = str(target.get("guid") or "")
        if not guid:
            raise LiveGuidProofError(f"canonical target {identity!r} has an empty GUID")
        if guid in by_guid:
            raise LiveGuidProofError(f"canonical GUID is not unique: {guid!r}")
        # Keep the identity in the map even when a test or caller supplied a
        # target without an explicit ``identity`` member.
        by_guid[guid] = (tuple(identity), target)
    if not by_guid:
        raise LiveGuidProofError("canonical target set is empty")
    return by_guid


def _read_json_object(connection: sqlite3.Connection, column: str) -> dict[str, Any]:
    try:
        rows = connection.execute(f"SELECT {column} FROM col").fetchall()
    except sqlite3.DatabaseError as exc:
        raise LiveGuidProofError(f"live export has no readable col.{column}: {exc}") from exc
    if len(rows) != 1 or len(rows[0]) != 1:
        raise LiveGuidProofError(f"live export col.{column} row is missing")
    try:
        value = json.loads(rows[0][0])
    except (TypeError, json.JSONDecodeError) as exc:
        raise LiveGuidProofError(f"live export col.{column} JSON is invalid") from exc
    if not isinstance(value, dict):
        raise LiveGuidProofError(f"live export col.{column} must be an object")
    return value


def _check_models(connection: sqlite3.Connection) -> None:
    models = _read_json_object(connection, "models")
    model = models.get(str(EAVM_MODEL_ID))
    if not isinstance(model, dict):
        raise LiveGuidProofError(
            f"live export is missing canonical model ID {EAVM_MODEL_ID}"
        )
    if model.get("name") != EAVM_MODEL_NAME:
        raise LiveGuidProofError("live export canonical model name mismatch")
    try:
        model_id = int(model.get("id"))
    except (TypeError, ValueError) as exc:
        raise LiveGuidProofError("live export canonical model ID is malformed") from exc
    if model_id != EAVM_MODEL_ID:
        raise LiveGuidProofError("live export canonical model ID mismatch")


def _check_collection_health(connection: sqlite3.Connection) -> None:
    try:
        result = connection.execute("PRAGMA quick_check").fetchall()
    except sqlite3.DatabaseError as exc:
        raise LiveGuidProofError(f"live export SQLite check failed: {exc}") from exc
    if result != [("ok",)]:
        raise LiveGuidProofError(f"live export SQLite integrity failure: {result!r}")


def _validate_collection(
    collection_path: Path,
    expected_records: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> tuple[str, int, int]:
    expected_by_guid = _expected_guid_targets(expected_records)
    try:
        connection = sqlite3.connect(f"file:{collection_path.as_posix()}?mode=ro", uri=True)
    except sqlite3.DatabaseError as exc:
        raise LiveGuidProofError(f"live export collection is not SQLite: {exc}") from exc
    try:
        _check_collection_health(connection)
        _check_models(connection)
        decks = _read_json_object(connection, "decks")
        deck_names: dict[int, str] = {}
        for raw_id, payload in decks.items():
            if not isinstance(payload, dict):
                raise LiveGuidProofError("live export contains malformed deck metadata")
            try:
                deck_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise LiveGuidProofError("live export deck ID is malformed") from exc
            name = payload.get("name")
            if not isinstance(name, str) or not name:
                raise LiveGuidProofError("live export deck name is malformed")
            deck_names[deck_id] = name

        try:
            note_rows = connection.execute(
                "SELECT id, guid, mid, flds, tags FROM notes"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise LiveGuidProofError(f"live export notes table is unreadable: {exc}") from exc
        if len(note_rows) != len(expected_by_guid):
            raise LiveGuidProofError(
                f"live export note count mismatch: expected {len(expected_by_guid)}, "
                f"got {len(note_rows)}"
            )

        note_guid_by_id: dict[int, str] = {}
        seen_guids: set[str] = set()
        map_rows: list[dict[str, object]] = []
        for note_id, guid, model_id, fields_text, tags_text in note_rows:
            if not isinstance(guid, str) or not guid:
                raise LiveGuidProofError("live export contains an empty/non-string note GUID")
            if guid in seen_guids or guid not in expected_by_guid:
                raise LiveGuidProofError(f"live export contains unexpected/duplicate GUID: {guid!r}")
            if int(model_id) != EAVM_MODEL_ID:
                raise LiveGuidProofError(f"live export note {guid!r} uses an unexpected model")
            identity, target = expected_by_guid[guid]
            actual_fields = tuple(str(fields_text or "").split("\x1f"))
            if actual_fields != _target_fields(target):
                raise LiveGuidProofError(f"live export fields do not match GUID {guid!r}")
            actual_tags = {tag for tag in str(tags_text or "").split() if tag}
            if actual_tags != _target_tags(target):
                raise LiveGuidProofError(f"live export tags do not match GUID {guid!r}")
            try:
                note_key = int(note_id)
            except (TypeError, ValueError) as exc:
                raise LiveGuidProofError(f"live export note ID is malformed: {note_id!r}") from exc
            if note_key in note_guid_by_id:
                raise LiveGuidProofError(f"live export has duplicate note ID: {note_key}")
            note_guid_by_id[note_key] = guid
            seen_guids.add(guid)
            map_rows.append({
                "guid": guid,
                "identity": list(identity),
                "fields_sha256": _sha256_bytes(_canonical_json_bytes(actual_fields)),
                "tags": sorted(actual_tags),
            })
        if seen_guids != set(expected_by_guid):
            raise LiveGuidProofError("live export GUID coverage does not match canonical records")

        try:
            card_rows = connection.execute(
                "SELECT id, nid, did, ord FROM cards"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise LiveGuidProofError(f"live export cards table is unreadable: {exc}") from exc
        expected_cards: set[tuple[str, int, str]] = set()
        for guid, (_identity, target) in expected_by_guid.items():
            deck = str(target.get("deck") or "")
            if not deck:
                raise LiveGuidProofError(f"canonical target {guid!r} has no deck")
            for ordinal in (0, 1) if target.get("production_eligible") else (0,):
                expected_cards.add((guid, ordinal, deck))
        actual_cards: set[tuple[str, int, str]] = set()
        for card_id, note_id, deck_id, ordinal in card_rows:
            try:
                note_key = int(note_id)
                deck_key = int(deck_id)
                ord_key = int(ordinal)
                int(card_id)
            except (TypeError, ValueError) as exc:
                raise LiveGuidProofError("live export card identity is malformed") from exc
            guid = note_guid_by_id.get(note_key)
            deck_name = deck_names.get(deck_key)
            if guid is None or deck_name is None:
                raise LiveGuidProofError("live export contains an orphan card")
            card_key = (guid, ord_key, deck_name)
            if card_key in actual_cards:
                raise LiveGuidProofError(f"live export contains duplicate card: {card_key!r}")
            actual_cards.add(card_key)
        if actual_cards != expected_cards:
            missing = sorted(expected_cards - actual_cards)[:5]
            extra = sorted(actual_cards - expected_cards)[:5]
            raise LiveGuidProofError(
                f"live export card/GUID coverage mismatch: missing={missing!r} extra={extra!r}"
            )
        map_rows.sort(key=lambda row: str(row["guid"]))
        return _sha256_bytes(_canonical_json_bytes(map_rows)), len(note_rows), len(card_rows)
    except (sqlite3.DatabaseError, ValueError, TypeError) as exc:
        if isinstance(exc, LiveGuidProofError):
            raise
        raise LiveGuidProofError(f"live export contract check failed: {exc}") from exc
    finally:
        connection.close()


def verify_exported_live_guid_map(
    archive_path: Path,
    expected_records: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> LiveGuidProof:
    """Inspect one exported APKG and return immutable GUID proof metadata."""

    archive_path = Path(archive_path)
    if not archive_path.is_file():
        raise LiveGuidProofError(f"live export was not created: {archive_path}")
    archive_bytes = archive_path.read_bytes()
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise LiveGuidProofError(f"live export is not a valid APKG: {exc}") from exc
    try:
        archive_names = archive.namelist()
        if len(archive_names) != len(set(archive_names)):
            raise LiveGuidProofError("live export contains duplicate archive entry names")
        names = set(archive_names)
        if UNSUPPORTED_COLLECTION_ENTRY in names:
            raise LiveGuidProofError(
                "live export contains unsupported collection.anki21b; refusing fallback"
            )
        collection_name = next(
            (name for name in SUPPORTED_COLLECTION_ENTRIES if name in names),
            "",
        )
        if not collection_name:
            raise LiveGuidProofError(
                "live export contains no supported collection entry"
            )
        with tempfile.TemporaryDirectory(prefix="anki-live-guid-") as temporary:
            collection_path = Path(temporary) / collection_name
            collection_path.write_bytes(archive.read(collection_name))
            guid_map_sha256, note_count, card_count = _validate_collection(
                collection_path, expected_records
            )
    except KeyError as exc:
        raise LiveGuidProofError(f"live export is missing {exc.args[0]!r}") from exc
    finally:
        archive.close()
    return LiveGuidProof(
        archive_name=archive_path.name,
        archive_sha256=_sha256_bytes(archive_bytes),
        guid_map_sha256=guid_map_sha256,
        collection_format=collection_name,
        note_count=note_count,
        card_count=card_count,
    )


def export_and_verify_live_guid_map(
    client: Any,
    scratch_dir: Path,
    expected_records: Mapping[tuple[str, ...], Mapping[str, Any]],
    *,
    now: datetime | None = None,
    deck_name: str = ROOT_DECK,
) -> LiveGuidProof:
    """Export the live deck through AnkiConnect, then verify its GUID map."""

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = Path(scratch_dir) / "release"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"live_guid_proof_{stamp}.apkg"
    result = client.call(
        "exportPackage",
        deck=deck_name,
        path=archive_path.resolve().as_posix(),
        includeSched=True,
    )
    if result is False or not archive_path.is_file():
        raise LiveGuidProofError(f"post-import live export was not created: {archive_path}")
    return verify_exported_live_guid_map(archive_path, expected_records)
