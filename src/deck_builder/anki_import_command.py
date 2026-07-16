#!/usr/bin/env python3
"""Import the built APKG into a running Anki instance through AnkiConnect."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from src.config import ProjectPaths
from src.deck_builder.package_command import (
    BACK_TEMPLATE,
    EAVM_FIELD_NAMES,
    EAVM_JSON_TO_FIELD,
    EAVM_MODEL_ID,
    EAVM_MODEL_NAME,
    EAVM_TEMPLATE_NAMES,
    FRONT_TEMPLATE,
    OUTPUT_APKG,
    PRODUCTION_ANSWER_PREFIX,
    PRODUCTION_FRONT_TEMPLATE,
    STYLING_TXT,
    EavmTemplate,
    load_eavm_templates,
)
from src.deck_builder.production import production_eligible
from src.design_css import load_production_css


ANKI_CONNECT_URL = "http://127.0.0.1:8765"
ANKI_CONNECT_API_VERSION = 6
EAVM_FIELDS = EAVM_FIELD_NAMES
ESTABLISHED_EAVM_FIELDS = EAVM_FIELDS[:15]
# Compatibility export for the historical 19-field model without DefinitionVI.
LEGACY_EAVM_FIELDS = EAVM_FIELDS[:19]
ROOT_DECK = "English Academic Vocabulary"
SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")
AUDIO_SRC_RE = re.compile(r"<audio\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)

JSON_TO_ANKI_FIELD: tuple[tuple[str, str], ...] = EAVM_JSON_TO_FIELD
SCHEDULE_FIELDS = (
    "type", "queue", "due", "interval", "factor", "reps", "lapses", "left",
)


@dataclass(frozen=True)
class ExistingCollectionSnapshot:
    """Immutable evidence used to prove migration preservation."""

    note_ids: frozenset[int]
    card_ids: frozenset[int]
    schedules: dict[int, tuple[Any, ...]]
    had_production_template: bool


class AnkiConnectError(RuntimeError):
    """AnkiConnect is unavailable or rejected an action."""


class AnkiConnectClient:
    def __init__(self, url: str = ANKI_CONNECT_URL, timeout: int = 600) -> None:
        self.url = url
        self.timeout = timeout

    def call(self, action: str, **params: Any) -> Any:
        try:
            response = requests.post(
                self.url,
                json={"action": action, "version": ANKI_CONNECT_API_VERSION, "params": params},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AnkiConnectError(f"Could not call AnkiConnect: {exc}") from exc
        if payload.get("error"):
            raise AnkiConnectError(f"AnkiConnect {action} failed: {payload['error']}")
        return payload.get("result")


def _chunks(values: list[int], size: int = 500) -> Iterable[list[int]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _require_not_false(result: Any, action: str) -> None:
    """Treat an explicit AnkiConnect ``false`` as a failed mutation."""

    if result is False or (
        isinstance(result, list) and any(item is False for item in result)
    ):
        raise AnkiConnectError(f"AnkiConnect {action} returned false")


def _template_state(templates: dict[str, Any]) -> str:
    """Classify only the two safe live template layouts."""

    if not isinstance(templates, dict):
        raise AnkiConnectError(
            f"Anki returned malformed EAVM templates payload: {templates!r}"
        )
    for name, content in templates.items():
        if not isinstance(name, str):
            raise AnkiConnectError(
                f"Anki returned non-string EAVM template name: {name!r}"
            )
        if (
            not isinstance(content, dict)
            or not isinstance(content.get("Front"), str)
            or not isinstance(content.get("Back"), str)
        ):
            raise AnkiConnectError(
                f"Anki returned malformed EAVM template {name!r}: {content!r}"
            )
    names = tuple(templates)
    if len(names) == 1:
        name = names[0]
        content = templates[name]
        combined = f"{content.get('Front') or ''}\n{content.get('Back') or ''}"
        if name == EAVM_TEMPLATE_NAMES[1] or "{{type:ProductionAnswer}}" in combined:
            raise AnkiConnectError(
                f"Refusing Production-only EAVM template layout: {list(names)!r}"
            )
        return "legacy"
    if names == EAVM_TEMPLATE_NAMES:
        return "canonical"
    raise AnkiConnectError(
        f"Incompatible EAVM template order/layout: expected one legacy ord0 or "
        f"{list(EAVM_TEMPLATE_NAMES)!r}, got {list(names)!r}"
    )


def _model_contract(client: AnkiConnectClient) -> tuple[bool, tuple[str, ...], str | None]:
    """Validate immutable model identity, field prefix, and template shape."""

    model_ids = client.call("modelNamesAndIds")
    if not isinstance(model_ids, dict):
        raise AnkiConnectError(
            f"Anki returned malformed modelNamesAndIds payload: {model_ids!r}"
        )
    if not all(isinstance(name, str) for name in model_ids):
        raise AnkiConnectError(
            f"Anki returned non-string model names: {model_ids!r}"
        )
    for model_name, model_id in model_ids.items():
        if model_name == EAVM_MODEL_NAME:
            continue
        try:
            colliding_id = int(model_id)
        except (TypeError, ValueError) as exc:
            raise AnkiConnectError(
                f"Anki returned malformed model ID for {model_name!r}: {model_id!r}"
            ) from exc
        if colliding_id == EAVM_MODEL_ID:
            raise AnkiConnectError(
                f"Model ID {EAVM_MODEL_ID} belongs to foreign model {model_name!r}"
            )
    model_names = set(model_ids)
    suffixed = []
    for model_name in sorted(model_names):
        if (
            isinstance(model_name, str)
            and model_name != EAVM_MODEL_NAME
            and model_name.startswith(EAVM_MODEL_NAME)
        ):
            note_ids = client.call("findNotes", query=f'note:"{model_name}"') or []
            if note_ids:
                suffixed.append((model_name, len(note_ids)))
    if suffixed:
        raise AnkiConnectError(
            f"Refusing import while suffixed EAVM notes exist: {suffixed!r}"
        )
    if EAVM_MODEL_NAME not in model_ids:
        return False, (), None
    try:
        live_model_id = int(model_ids[EAVM_MODEL_NAME])
    except (TypeError, ValueError) as exc:
        raise AnkiConnectError(
            f"Existing {EAVM_MODEL_NAME!r} has a malformed model ID: "
            f"{model_ids[EAVM_MODEL_NAME]!r}"
        ) from exc
    if live_model_id != EAVM_MODEL_ID:
        raise AnkiConnectError(
            f"Existing {EAVM_MODEL_NAME!r} has model ID "
            f"{model_ids[EAVM_MODEL_NAME]!r}; expected {EAVM_MODEL_ID}"
        )
    current_fields = tuple(
        client.call("modelFieldNames", modelName=EAVM_MODEL_NAME) or []
    )
    if not (
        len(current_fields) >= len(ESTABLISHED_EAVM_FIELDS)
        and len(current_fields) <= len(EAVM_FIELDS)
        and current_fields == EAVM_FIELDS[:len(current_fields)]
    ):
        raise AnkiConnectError(
            f"Existing {EAVM_MODEL_NAME!r} has an incompatible field contract: "
            f"{list(current_fields)!r}"
        )
    templates = client.call("modelTemplates", modelName=EAVM_MODEL_NAME)
    template_state = _template_state(templates)
    if template_state == "canonical" and current_fields != EAVM_FIELDS:
        raise AnkiConnectError(
            "Canonical EAVM templates require the complete canonical field contract"
        )
    return True, current_fields, template_state


def load_expected_signatures(notes_jsonl: Path) -> Counter[tuple[str, ...]]:
    """Load exact note-field signatures expected after native APKG import."""
    signatures: Counter[tuple[str, ...]] = Counter()
    with notes_jsonl.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL on line {line_number}: {exc}") from exc
            signatures[tuple(str(row.get(key) or "") for key, _ in JSON_TO_ANKI_FIELD)] += 1
    if not signatures:
        raise ValueError("The canonical notes JSONL contains no notes")
    return signatures


def load_expected_media(notes_jsonl: Path) -> set[str]:
    expected: set[str] = set()
    with notes_jsonl.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            for key in (
                "uk_audio", "us_audio", "example_audio_uk", "example_audio_us",
                "idiom_example_audio_uk", "idiom_example_audio_us",
            ):
                value = str(row.get(key) or "")
                expected.update(SOUND_RE.findall(value))
                expected.update(AUDIO_SRC_RE.findall(value))
    return expected


def _identity(word: str, pos: str, cefr: str, tags: Iterable[str]) -> tuple[str, ...]:
    variants = sorted(
        tag for tag in tags
        if tag == "SecondarySense" or tag.startswith("SenseVariant::")
    )
    return word, pos, cefr, *variants


def load_expected_records(notes_jsonl: Path) -> dict[tuple[str, ...], dict[str, Any]]:
    """Index canonical records by stable Card Identity plus reviewed variant tags."""
    records: dict[tuple[str, ...], dict[str, Any]] = {}
    with notes_jsonl.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            tags = [tag for tag in str(row.get("tags") or "").split() if tag]
            identity = _identity(
                str(row.get("word") or ""), str(row.get("pos") or ""),
                str(row.get("cefr") or ""), tags,
            )
            if identity in records:
                raise ValueError(f"Non-unique canonical import identity: {identity!r}")
            records[identity] = {
                "deck": str(row.get("deck") or ""),
                "fields": {
                    field_name: str(row.get(key) or "")
                    for key, field_name in JSON_TO_ANKI_FIELD
                },
                "tags": tags,
                "guid": str(row.get("guid") or ""),
                "production_eligible": production_eligible(
                    row.get("definition_vi"),
                    row.get("example"),
                    row.get("production_answer"),
                ),
            }
    return records


def _field_value(fields: dict[str, Any], name: str) -> str:
    if not isinstance(fields, dict):
        raise AnkiConnectError(f"Anki returned malformed note fields: {fields!r}")
    entry = fields.get(name)
    if entry is None:
        return ""
    if not isinstance(entry, dict):
        raise AnkiConnectError(
            f"Anki returned malformed field {name!r}: {entry!r}"
        )
    return str(entry.get("value") or "")


def _card_schedule(card: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(card.get(name) for name in SCHEDULE_FIELDS)


def _load_cards_info(
    client: AnkiConnectClient,
    card_ids: Iterable[int],
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    ids = list(card_ids)
    if len(ids) != len(set(ids)):
        raise AnkiConnectError("Duplicate card IDs requested from Anki")
    for batch in _chunks(ids):
        for card in client.call("cardsInfo", cards=batch) or []:
            if not isinstance(card, dict) or "cardId" not in card:
                raise AnkiConnectError(
                    f"Anki returned malformed card info: {card!r}"
                )
            try:
                card_id = int(card["cardId"])
            except (TypeError, ValueError) as exc:
                raise AnkiConnectError(
                    f"Anki returned malformed card ID: {card!r}"
                ) from exc
            if card_id in result:
                raise AnkiConnectError(f"Anki returned duplicate card info for {card_id}")
            result[card_id] = card
    if set(result) != set(ids):
        raise AnkiConnectError("Anki did not return info for every expected EAVM card")
    return result


def snapshot_existing_collection(
    client: AnkiConnectClient,
    expected: dict[tuple[str, ...], dict[str, Any]],
    template_state: str,
    current_fields: Iterable[str] | None = None,
) -> ExistingCollectionSnapshot:
    """Reject stray/stale state and capture schedules before any live mutation."""

    # The snapshot is taken *before* field migration so a legacy 15/19/22-field
    # collection can still be upgraded in place.  ``_model_contract`` has
    # already proved that the live fields are an exact canonical prefix; use
    # that prefix as the note payload contract here.  Once the Production
    # template exists the contract is necessarily complete (the model checker
    # rejects a canonical template with missing fields).
    live_fields = tuple(EAVM_FIELDS if current_fields is None else current_fields)
    if not (
        len(live_fields) >= len(ESTABLISHED_EAVM_FIELDS)
        and live_fields == EAVM_FIELDS[:len(live_fields)]
    ):
        raise AnkiConnectError(
            f"Cannot snapshot incompatible EAVM fields: {list(live_fields)!r}"
        )

    note_ids = client.call("findNotes", query=f'note:"{EAVM_MODEL_NAME}"') or []
    if len(note_ids) != len(expected) or len(set(note_ids)) != len(note_ids):
        raise AnkiConnectError(
            f"Existing EAVM model expected {len(expected)} canonical notes, "
            f"found {len(note_ids)}"
        )
    try:
        requested_note_ids = {int(note_id) for note_id in note_ids}
    except (TypeError, ValueError) as exc:
        raise AnkiConnectError(
            f"Anki returned malformed EAVM note IDs: {note_ids!r}"
        ) from exc

    matched: set[tuple[str, ...]] = set()
    card_ids: list[int] = []
    note_targets: dict[int, dict[str, Any]] = {}
    note_live_eligibility: dict[int, bool] = {}
    for batch in _chunks(note_ids):
        for note in client.call("notesInfo", notes=batch) or []:
            if not isinstance(note, dict) or "noteId" not in note:
                raise AnkiConnectError(f"Anki returned malformed note info: {note!r}")
            try:
                note_id = int(note["noteId"])
            except (TypeError, ValueError) as exc:
                raise AnkiConnectError(
                    f"Anki returned malformed note ID: {note!r}"
                ) from exc
            if note.get("modelName") != EAVM_MODEL_NAME:
                raise AnkiConnectError(f"Unexpected model on EAVM note {note_id}")
            fields = note.get("fields") or {}
            if not isinstance(fields, dict):
                raise AnkiConnectError(
                    f"Existing note {note_id} has malformed field payload"
                )
            if set(fields) != set(live_fields):
                raise AnkiConnectError(
                    f"Existing note {note_id} has an incomplete field payload"
                )
            identity = _identity(
                _field_value(fields, "Word"),
                _field_value(fields, "PartOfSpeech"),
                _field_value(fields, "CEFRLevel"),
                note.get("tags") or [],
            )
            target = expected.get(identity)
            if target is None or identity in matched:
                raise AnkiConnectError(
                    f"Existing note did not resolve to one canonical Card Identity: {identity!r}"
                )
            expected_guid = str(target.get("guid") or "")
            live_guid = str(note.get("guid") or "")
            if live_guid and expected_guid and live_guid != expected_guid:
                raise AnkiConnectError(f"GUID mismatch on existing note {identity!r}")
            matched.add(identity)
            note_targets[note_id] = target
            note_live_eligibility[note_id] = production_eligible(
                _field_value(fields, "DefinitionVI"),
                _field_value(fields, "Example"),
                _field_value(fields, "ProductionAnswer"),
            )
            raw_note_cards = note.get("cards") or []
            if not isinstance(raw_note_cards, (list, tuple)):
                raise AnkiConnectError(
                    f"Existing note {note_id} has malformed card list"
                )
            try:
                note_cards = [int(card_id) for card_id in raw_note_cards]
            except (TypeError, ValueError) as exc:
                raise AnkiConnectError(
                    f"Existing note {note_id} has malformed card IDs"
                ) from exc
            if not note_cards or len(note_cards) != len(set(note_cards)):
                raise AnkiConnectError(f"Unexpected card list on EAVM note {note_id}")
            card_ids.extend(note_cards)
    if (
        set(note_targets) != requested_note_ids
        or matched != set(expected)
        or len(card_ids) != len(set(card_ids))
    ):
        raise AnkiConnectError("Existing EAVM notes/cards are not a canonical one-to-one set")

    root_cards = set(
        client.call("findCards", query=f'deck:"{ROOT_DECK}"') or []
    )
    if root_cards != set(card_ids):
        raise AnkiConnectError(
            "Root deck contains stray cards or canonical EAVM cards live outside it"
        )

    cards = _load_cards_info(client, card_ids)
    by_note: dict[int, list[dict[str, Any]]] = {}
    for card in cards.values():
        if card.get("modelName") != EAVM_MODEL_NAME:
            raise AnkiConnectError(f"Unexpected model on card {card.get('cardId')}")
        try:
            note_id = int(card["note"])
            int(card["ord"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AnkiConnectError(f"Anki returned malformed card info: {card!r}") from exc
        if note_id not in note_targets:
            raise AnkiConnectError(f"Stray EAVM card {card.get('cardId')}")
        by_note.setdefault(note_id, []).append(card)

    for note_id, target in note_targets.items():
        note_cards = by_note.get(note_id) or []
        try:
            ords = [int(card["ord"]) for card in note_cards]
        except (KeyError, TypeError, ValueError) as exc:
            raise AnkiConnectError(
                f"Anki returned malformed card ordinal for note {note_id}"
            ) from exc
        if template_state == "legacy":
            expected_ords = [0]
        else:
            if note_live_eligibility[note_id] != target["production_eligible"]:
                raise AnkiConnectError(
                    f"Stale Production eligibility transition on note {note_id}; "
                    "refusing to create or orphan a scheduled card"
                )
            expected_ords = [0, 1] if target["production_eligible"] else [0]
        if sorted(ords) != expected_ords:
            raise AnkiConnectError(
                f"Unexpected card ordinals on note {note_id}: {sorted(ords)!r}"
            )
        if len({str(card.get("deckName") or "") for card in note_cards}) != 1:
            raise AnkiConnectError(
                f"Sibling EAVM cards do not share one deck on note {note_id}"
            )

    return ExistingCollectionSnapshot(
        note_ids=frozenset(int(note_id) for note_id in note_ids),
        card_ids=frozenset(card_ids),
        schedules={card_id: _card_schedule(card) for card_id, card in cards.items()},
        had_production_template=template_state == "canonical",
    )


def validate_local_inputs(
    package_path: Path,
    notes_jsonl: Path,
    audio_dir: Path,
) -> tuple[Counter[tuple[str, ...]], set[str]]:
    """Validate all local import inputs without contacting or mutating Anki."""
    if not package_path.is_file():
        raise ValueError(f"APKG not found: {package_path}")
    if not notes_jsonl.is_file():
        raise ValueError(f"canonical notes JSONL not found: {notes_jsonl}")
    expected = load_expected_signatures(notes_jsonl)
    media = load_expected_media(notes_jsonl)
    invalid = sorted(name for name in media if Path(name).name != name)
    if invalid:
        raise ValueError(f"invalid media filename reference(s): {invalid[:5]}")
    missing = sorted(name for name in media if not (audio_dir / name).is_file())
    if missing:
        raise ValueError(f"referenced media missing from audio/: {missing[:5]}")
    return expected, media


def _live_signature(note: dict[str, Any]) -> tuple[str, ...]:
    if not isinstance(note, dict):
        raise AnkiConnectError(f"Anki returned malformed note: {note!r}")
    fields = note.get("fields") or {}
    return tuple(_field_value(fields, name) for _, name in JSON_TO_ANKI_FIELD)


def sync_example_audio_fields(
    client: AnkiConnectClient,
    expected: Counter[tuple[str, ...]],
) -> int:
    """Populate appended fields on existing notes after native APKG migration."""
    by_established_signature: dict[tuple[str, ...], tuple[str, ...]] = {}
    for signature, count in expected.items():
        base = signature[:len(ESTABLISHED_EAVM_FIELDS)]
        if count != 1 or base in by_established_signature:
            raise AnkiConnectError(
                "Cannot synchronize example audio because the established field "
                "signature is not unique"
            )
        by_established_signature[base] = signature

    note_ids = client.call(
        "findNotes", query=f'deck:"{ROOT_DECK}" note:"{EAVM_MODEL_NAME}"'
    ) or []
    if len(note_ids) != sum(expected.values()):
        raise AnkiConnectError(
            "Cannot synchronize example audio because the live note count does not "
            "match the canonical build"
        )

    actions: list[dict[str, Any]] = []
    matched: set[tuple[str, ...]] = set()
    appended_names = EAVM_FIELDS[len(ESTABLISHED_EAVM_FIELDS):]
    for batch in _chunks(note_ids):
        for note in client.call("notesInfo", notes=batch) or []:
            live = _live_signature(note)
            base = live[:len(ESTABLISHED_EAVM_FIELDS)]
            target = by_established_signature.get(base)
            if target is None or base in matched:
                raise AnkiConnectError(
                    "Cannot synchronize example audio: an existing note did not "
                    "resolve to exactly one canonical 15-field signature"
                )
            matched.add(base)
            desired = target[len(ESTABLISHED_EAVM_FIELDS):]
            if live[len(ESTABLISHED_EAVM_FIELDS):] != desired:
                actions.append({
                    "action": "updateNoteFields",
                    "params": {
                        "note": {
                            "id": note["noteId"],
                            "fields": dict(zip(appended_names, desired)),
                        }
                    },
                })
    if len(matched) != len(by_established_signature):
        raise AnkiConnectError("Not every canonical note was matched during audio-field sync")
    for start in range(0, len(actions), 100):
        _require_not_false(
            client.call("multi", actions=actions[start:start + 100]),
            "multi",
        )
    return len(actions)


def sync_missing_media(
    client: AnkiConnectClient,
    expected_media: set[str],
    audio_dir: Path,
) -> int:
    """Copy package media skipped by Anki's importer into the live collection."""
    remote = set(client.call("getMediaFilesNames", pattern="*") or [])
    missing = sorted(expected_media - remote)
    actions = []
    audio_root = audio_dir.resolve()
    for filename in missing:
        source = (audio_root / filename).resolve()
        if not source.is_relative_to(audio_root) or not source.is_file():
            raise AnkiConnectError(f"Cannot upload missing local media: {source}")
        actions.append({
            "action": "storeMediaFile",
            "params": {"filename": filename, "path": source.as_posix()},
        })
    for start in range(0, len(actions), 100):
        _require_not_false(
            client.call("multi", actions=actions[start:start + 100]),
            "multi",
        )
    return len(actions)


def sync_existing_notes(
    client: AnkiConnectClient,
    notes_jsonl: Path,
) -> int:
    """Update an established deck directly without invoking APKG model import."""
    expected = load_expected_records(notes_jsonl)
    note_ids = client.call(
        "findNotes", query=f'note:"{EAVM_MODEL_NAME}"'
    ) or []
    if len(note_ids) != len(expected):
        raise AnkiConnectError(
            f"Direct sync expected {len(expected)} established notes, found {len(note_ids)}"
        )
    actions: list[dict[str, Any]] = []
    deck_moves: dict[str, list[int]] = {}
    matched: set[tuple[str, ...]] = set()
    for batch in _chunks(note_ids):
        for note in client.call("notesInfo", notes=batch) or []:
            if not isinstance(note, dict) or "noteId" not in note:
                raise AnkiConnectError(f"Anki returned malformed note info: {note!r}")
            if note.get("modelName") != EAVM_MODEL_NAME:
                raise AnkiConnectError(
                    f"Cannot synchronize non-EAVM note {note.get('noteId')!r}"
                )
            fields = note.get("fields") or {}
            if not isinstance(fields, dict):
                raise AnkiConnectError(
                    f"Cannot synchronize note {note.get('noteId')!r} with malformed fields"
                )
            identity = _identity(
                str((fields.get("Word") or {}).get("value") or ""),
                str((fields.get("PartOfSpeech") or {}).get("value") or ""),
                str((fields.get("CEFRLevel") or {}).get("value") or ""),
                note.get("tags") or [],
            )
            target = expected.get(identity)
            if target is None or identity in matched:
                raise AnkiConnectError(
                    f"Existing note did not resolve to one canonical Card Identity: {identity!r}"
                )
            matched.add(identity)
            expected_guid = str(target.get("guid") or "")
            live_guid = str(note.get("guid") or "")
            if live_guid and expected_guid and live_guid != expected_guid:
                raise AnkiConnectError(f"GUID mismatch on existing note {identity!r}")
            current_fields = {
                name: _field_value(fields, name)
                for name in EAVM_FIELDS
            }
            current_tags = sorted(str(tag) for tag in (note.get("tags") or []))
            if current_fields != target["fields"] or current_tags != sorted(target["tags"]):
                actions.append({
                    "action": "updateNote",
                    "params": {"note": {
                        "id": note["noteId"],
                        "fields": target["fields"],
                        "tags": target["tags"],
                    }},
                })
            raw_note_cards = note.get("cards") or []
            if not isinstance(raw_note_cards, (list, tuple)):
                raise AnkiConnectError(
                    f"Cannot synchronize note {note.get('noteId')!r} with malformed cards"
                )
            try:
                note_cards = [int(card_id) for card_id in raw_note_cards]
            except (TypeError, ValueError) as exc:
                raise AnkiConnectError(
                    f"Cannot synchronize note {note.get('noteId')!r} with malformed card IDs"
                ) from exc
            deck_moves.setdefault(target["deck"], []).extend(note_cards)
    if len(matched) != len(expected):
        raise AnkiConnectError("Not every canonical Card Identity matched an established note")
    for start in range(0, len(actions), 100):
        _require_not_false(
            client.call("multi", actions=actions[start:start + 100]),
            "multi",
        )
    for deck, cards in deck_moves.items():
        _require_not_false(
            client.call("changeDeck", cards=cards, deck=deck),
            "changeDeck",
        )
    return len(actions)


def verify_import(
    client: AnkiConnectClient,
    expected: Counter[tuple[str, ...]],
    expected_media: set[str],
    expected_records: dict[tuple[str, ...], dict[str, Any]] | None = None,
    prior: ExistingCollectionSnapshot | None = None,
    templates: tuple[EavmTemplate, ...] | None = None,
    css: str | None = None,
) -> int:
    """Fail closed unless the complete live model, notes, and cards are canonical."""

    model_ids = client.call("modelNamesAndIds")
    if not isinstance(model_ids, dict):
        raise AnkiConnectError(
            f"Anki returned malformed modelNamesAndIds payload: {model_ids!r}"
        )
    for model_name in model_ids:
        if (
            isinstance(model_name, str)
            and model_name != EAVM_MODEL_NAME
            and model_name.startswith(EAVM_MODEL_NAME)
        ):
            suffix_notes = client.call(
                "findNotes", query=f'note:"{model_name}"'
            ) or []
            if suffix_notes:
                raise AnkiConnectError(
                    f"Refusing verification while suffixed EAVM notes exist: "
                    f"{model_name!r} ({len(suffix_notes)})"
                )
    try:
        live_model_id = int(model_ids.get(EAVM_MODEL_NAME))
    except (TypeError, ValueError):
        live_model_id = None
    if live_model_id != EAVM_MODEL_ID:
        raise AnkiConnectError(
            f"Unexpected {EAVM_MODEL_NAME!r} model ID: "
            f"expected {EAVM_MODEL_ID}, got {model_ids.get(EAVM_MODEL_NAME)!r}"
        )
    field_names = client.call("modelFieldNames", modelName=EAVM_MODEL_NAME) or []
    if tuple(field_names) != EAVM_FIELDS:
        raise AnkiConnectError(
            f"Unexpected {EAVM_MODEL_NAME!r} fields: expected {list(EAVM_FIELDS)!r}, got {field_names!r}"
        )

    canonical_templates = load_eavm_templates() if templates is None else templates
    expected_templates = {
        template.name: template.for_anki_connect()
        for template in canonical_templates
    }
    live_templates = client.call("modelTemplates", modelName=EAVM_MODEL_NAME)
    if not isinstance(live_templates, dict):
        raise AnkiConnectError(
            f"Anki returned malformed EAVM templates payload: {live_templates!r}"
        )
    if (
        tuple(live_templates) != EAVM_TEMPLATE_NAMES
        or live_templates != expected_templates
    ):
        raise AnkiConnectError(
            f"Unexpected EAVM template order/content: {list(live_templates)!r}"
        )
    expected_css = css if css is not None else load_production_css(STYLING_TXT)
    styling = client.call("modelStyling", modelName=EAVM_MODEL_NAME)
    if not isinstance(styling, dict):
        raise AnkiConnectError(
            f"Anki returned malformed EAVM styling payload: {styling!r}"
        )
    live_css = styling.get("css")
    if live_css != expected_css:
        raise AnkiConnectError("Unexpected EAVM CSS after import")

    note_ids = client.call(
        "findNotes", query=f'note:"{EAVM_MODEL_NAME}"'
    ) or []
    expected_count = sum(expected.values())
    if len(note_ids) != expected_count or len(set(note_ids)) != len(note_ids):
        raise AnkiConnectError(
            f"Import verification expected {expected_count} notes on {EAVM_MODEL_NAME!r}, "
            f"but Anki returned {len(note_ids)}"
        )
    try:
        requested_note_ids = {int(note_id) for note_id in note_ids}
    except (TypeError, ValueError) as exc:
        raise AnkiConnectError(
            f"Anki returned malformed live note IDs: {note_ids!r}"
        ) from exc
    live_note_info_ids: set[int] = set()
    if prior is not None and requested_note_ids != prior.note_ids:
        raise AnkiConnectError(
            "Established note IDs changed during migration; GUID preservation is not proven"
        )
    live: Counter[tuple[str, ...]] = Counter()
    live_records: dict[tuple[str, ...], tuple[int, dict[str, Any], dict[str, Any]]] = {}
    card_ids: list[int] = []
    for batch in _chunks(note_ids):
        for note in client.call("notesInfo", notes=batch) or []:
            if not isinstance(note, dict):
                raise AnkiConnectError(f"Anki returned malformed note info: {note!r}")
            if expected_records is not None and "noteId" not in note:
                raise AnkiConnectError(f"Anki returned malformed note info: {note!r}")
            if note.get("modelName") != EAVM_MODEL_NAME:
                raise AnkiConnectError(
                    f"Unexpected model on live note {note.get('noteId')!r}"
                )
            fields = note.get("fields") or {}
            if not isinstance(fields, dict):
                raise AnkiConnectError(
                    f"Live note {note.get('noteId')!r} has malformed field payload"
                )
            if expected_records is not None and set(fields) != set(EAVM_FIELDS):
                raise AnkiConnectError(
                    f"Live note {note.get('noteId')!r} has an incomplete field payload"
                )
            live[_live_signature(note)] += 1
            if expected_records is not None:
                identity = _identity(
                    _field_value(fields, "Word"),
                    _field_value(fields, "PartOfSpeech"),
                    _field_value(fields, "CEFRLevel"),
                    note.get("tags") or [],
                )
                target = expected_records.get(identity)
                if target is None or identity in live_records:
                    raise AnkiConnectError(
                        f"Live note did not resolve to one Card Identity: {identity!r}"
                    )
                if sorted(note.get("tags") or []) != sorted(target["tags"]):
                    raise AnkiConnectError(f"Tag mismatch on live note {identity!r}")
                expected_guid = str(target.get("guid") or "")
                live_guid = str(note.get("guid") or "")
                if live_guid and expected_guid and live_guid != expected_guid:
                    raise AnkiConnectError(f"GUID mismatch on live note {identity!r}")
                try:
                    note_id = int(note["noteId"])
                except (TypeError, ValueError) as exc:
                    raise AnkiConnectError(
                        f"Anki returned malformed live note ID: {note!r}"
                    ) from exc
                live_note_info_ids.add(note_id)
                live_records[identity] = (note_id, note, target)
                raw_note_cards = note.get("cards") or []
                if not isinstance(raw_note_cards, (list, tuple)):
                    raise AnkiConnectError(
                        f"Live note {note_id} has malformed card list"
                    )
                try:
                    card_ids.extend(int(card_id) for card_id in raw_note_cards)
                except (TypeError, ValueError) as exc:
                    raise AnkiConnectError(
                        f"Live note {note_id} has malformed card IDs"
                    ) from exc

    if expected_records is not None and live_note_info_ids != requested_note_ids:
        raise AnkiConnectError(
            "Anki did not return info for exactly the requested EAVM notes"
        )

    missing = expected - live
    extra = live - expected
    if missing or extra:
        mismatch_count = sum(missing.values()) + sum(extra.values())
        samples = [signature[0] or "<blank Word>" for signature in list(missing or extra)[:5]]
        raise AnkiConnectError(
            f"Import verification found {mismatch_count} missing/extra/mismatched "
            f"note(s); sample Word values: {samples}"
        )

    if expected_records is not None:
        if set(live_records) != set(expected_records):
            raise AnkiConnectError("Not every canonical Card Identity resolved after import")
        if len(card_ids) != len(set(card_ids)):
            raise AnkiConnectError("Duplicate or stray card IDs returned by canonical notes")
        root_cards = set(
            client.call("findCards", query=f'deck:"{ROOT_DECK}"') or []
        )
        if root_cards != set(card_ids):
            raise AnkiConnectError("Import verification found stray or out-of-root cards")
        cards = _load_cards_info(client, card_ids)
        by_note: dict[int, list[dict[str, Any]]] = {}
        for card in cards.values():
            if card.get("modelName") != EAVM_MODEL_NAME:
                raise AnkiConnectError(f"Unexpected model on card {card.get('cardId')}")
            try:
                note_id = int(card["note"])
                int(card["ord"])
            except (KeyError, TypeError, ValueError) as exc:
                raise AnkiConnectError(
                    f"Anki returned malformed card info: {card!r}"
                ) from exc
            by_note.setdefault(note_id, []).append(card)

        ord0_count = 0
        ord1_count = 0
        production_ids: set[int] = set()
        for identity, (note_id, _note, target) in live_records.items():
            note_cards = by_note.get(note_id) or []
            expected_ords = [0, 1] if target["production_eligible"] else [0]
            try:
                ords = sorted(int(card["ord"]) for card in note_cards)
            except (KeyError, TypeError, ValueError) as exc:
                raise AnkiConnectError(
                    f"Anki returned malformed card ordinal for {identity!r}"
                ) from exc
            if ords != expected_ords:
                raise AnkiConnectError(
                    f"Card ordinal mismatch for {identity!r}: expected "
                    f"{expected_ords!r}, got {ords!r}"
                )
            for card in note_cards:
                if str(card.get("deckName") or "") != target["deck"]:
                    raise AnkiConnectError(
                        f"Card deck mismatch for {identity!r}: {card.get('deckName')!r}"
                    )
                if int(card["ord"]) == 0:
                    ord0_count += 1
                else:
                    ord1_count += 1
                    try:
                        production_ids.add(int(card["cardId"]))
                    except (KeyError, TypeError, ValueError) as exc:
                        raise AnkiConnectError(
                            f"Anki returned malformed card ID: {card!r}"
                        ) from exc
        eligible_count = sum(
            1 for target in expected_records.values() if target["production_eligible"]
        )
        if ord0_count != expected_count or ord1_count != eligible_count:
            raise AnkiConnectError(
                f"Expected {expected_count} Recognition and {eligible_count} Production "
                f"cards, found {ord0_count} and {ord1_count}"
            )

        if prior is not None:
            for card_id, schedule in prior.schedules.items():
                if card_id not in cards or _card_schedule(cards[card_id]) != schedule:
                    raise AnkiConnectError(
                        f"Schedule changed on established card {card_id}"
                    )
            new_production_ids = production_ids - prior.card_ids
            if prior.had_production_template and new_production_ids:
                raise AnkiConnectError("Idempotent migration created unexpected Production cards")
        else:
            new_production_ids = production_ids
        for card_id in new_production_ids:
            card = cards[card_id]
            if (
                card.get("type") != 0
                or card.get("queue") != 0
                or card.get("interval") != 0
                or card.get("factor", 0) != 0
                or card.get("reps") != 0
                or card.get("lapses") != 0
                or card.get("left", 0) != 0
            ):
                raise AnkiConnectError(
                    f"New Production card {card_id} is not active and unreviewed"
                )

    remote_media = set(client.call("getMediaFilesNames", pattern="*") or [])
    missing_media = sorted(expected_media - remote_media)
    if missing_media:
        raise AnkiConnectError(
            f"Import verification found {len(missing_media)} missing media file(s): {missing_media[:5]}"
        )
    return expected_count


def preflight_and_backup(
    client: AnkiConnectClient,
    scratch_dir: Path,
    now: datetime | None = None,
) -> Path | None:
    """Check compatibility and back up an existing live deck before import."""
    api_version = client.call("version")
    if not isinstance(api_version, int) or api_version < ANKI_CONNECT_API_VERSION:
        raise AnkiConnectError(
            f"AnkiConnect API version {api_version!r} is older than required version {ANKI_CONNECT_API_VERSION}"
        )

    model_exists, _fields, _template_state_name = _model_contract(client)
    deck_names = set(client.call("deckNames") or [])
    if model_exists and ROOT_DECK not in deck_names:
        existing_notes = client.call("findNotes", query=f'note:"{EAVM_MODEL_NAME}"') or []
        if existing_notes:
            raise AnkiConnectError(
                f"Existing {EAVM_MODEL_NAME!r} has no {ROOT_DECK!r} deck to back up"
            )
        # An unused, correctly identified model has no schedules or notes to
        # preserve; let the native package importer perform the first install.
        return None
    if model_exists:
        # An identified model with no notes is still live state.  Do not let a
        # native import merge canonical cards into a deck that already carries
        # unrelated cards; that would make rollback/stray-card verification
        # impossible after mutation.
        existing_notes = client.call("findNotes", query=f'note:"{EAVM_MODEL_NAME}"') or []
        if not existing_notes and ROOT_DECK in deck_names:
            root_cards = client.call("findCards", query=f'deck:"{ROOT_DECK}"') or []
            if root_cards:
                raise AnkiConnectError(
                    f"Refusing import into non-empty {ROOT_DECK!r} deck while "
                    f"{EAVM_MODEL_NAME!r} has no notes"
                )
    if not model_exists and ROOT_DECK in deck_names:
        root_cards = client.call("findCards", query=f'deck:"{ROOT_DECK}"') or []
        if root_cards:
            raise AnkiConnectError(
                f"Refusing first import into non-empty {ROOT_DECK!r} deck"
            )
    if ROOT_DECK not in deck_names:
        return None

    scratch_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    backup_path = (scratch_dir / f"pre_import_{stamp}.apkg").resolve()
    result = client.call(
        "exportPackage",
        deck=ROOT_DECK,
        path=backup_path.as_posix(),
        includeSched=True,
    )
    if result is False or not backup_path.is_file():
        raise AnkiConnectError(f"Pre-import backup was not created: {backup_path}")
    return backup_path


def migrate_established_eavm_fields(client: AnkiConnectClient) -> None:
    """Append every missing post-establishment field in canonical order."""
    model_ids = client.call("modelNamesAndIds")
    if not isinstance(model_ids, dict):
        raise AnkiConnectError(
            f"Anki returned malformed modelNamesAndIds payload: {model_ids!r}"
        )
    if EAVM_MODEL_NAME not in model_ids:
        return
    try:
        live_model_id = int(model_ids[EAVM_MODEL_NAME])
    except (TypeError, ValueError):
        live_model_id = None
    if live_model_id != EAVM_MODEL_ID:
        raise AnkiConnectError(
            f"Cannot migrate {EAVM_MODEL_NAME!r} with model ID "
            f"{model_ids[EAVM_MODEL_NAME]!r}"
        )
    current_fields = tuple(
        client.call("modelFieldNames", modelName=EAVM_MODEL_NAME) or []
    )
    if not (
        len(current_fields) >= len(ESTABLISHED_EAVM_FIELDS)
        and current_fields == EAVM_FIELDS[:len(current_fields)]
    ):
        raise AnkiConnectError(
            f"Cannot migrate incompatible {EAVM_MODEL_NAME!r} fields: "
            f"{list(current_fields)!r}"
        )
    start = len(current_fields)
    for index, field_name in enumerate(
        EAVM_FIELDS[start:],
        start=start,
    ):
        result = client.call(
            "modelFieldAdd",
            modelName=EAVM_MODEL_NAME,
            fieldName=field_name,
            index=index,
        )
        _require_not_false(result, "modelFieldAdd")
    migrated = tuple(client.call("modelFieldNames", modelName=EAVM_MODEL_NAME) or [])
    if migrated != EAVM_FIELDS:
        raise AnkiConnectError(
            f"Failed to migrate {EAVM_MODEL_NAME!r} to the expected field contract: "
            f"{list(migrated)!r}"
        )


def sync_model_design(
    client: AnkiConnectClient,
    front_path: Path | None = None,
    back_path: Path | None = None,
    styling_path: Path | None = None,
    production_front_path: Path | None = None,
    production_answer_prefix_path: Path | None = None,
) -> None:
    """Rename legacy ord0 in place, append ord1, and synchronize exact design."""

    canonical = load_eavm_templates(
        front_path or FRONT_TEMPLATE,
        back_path or BACK_TEMPLATE,
        production_front_path or PRODUCTION_FRONT_TEMPLATE,
        production_answer_prefix_path or PRODUCTION_ANSWER_PREFIX,
    )
    expected = {
        template.name: template.for_anki_connect()
        for template in canonical
    }
    current = client.call("modelTemplates", modelName=EAVM_MODEL_NAME) or {}
    state = _template_state(current)
    css = load_production_css(styling_path or STYLING_TXT)

    if state == "legacy":
        legacy_name = next(iter(current))
        if legacy_name != EAVM_TEMPLATE_NAMES[0]:
            result = client.call(
                "modelTemplateRename",
                modelName=EAVM_MODEL_NAME,
                oldTemplateName=legacy_name,
                newTemplateName=EAVM_TEMPLATE_NAMES[0],
            )
            _require_not_false(result, "modelTemplateRename")
        result = client.call("updateModelTemplates", model={
            "name": EAVM_MODEL_NAME,
            "templates": {EAVM_TEMPLATE_NAMES[0]: expected[EAVM_TEMPLATE_NAMES[0]]},
        })
        _require_not_false(result, "updateModelTemplates")
        result = client.call("updateModelStyling", model={"name": EAVM_MODEL_NAME, "css": css})
        _require_not_false(result, "updateModelStyling")
        production = canonical[1]
        result = client.call(
            "modelTemplateAdd",
            modelName=EAVM_MODEL_NAME,
            template={
                "Name": production.name,
                "Front": production.front,
                "Back": production.back,
            },
        )
        _require_not_false(result, "modelTemplateAdd")

    result = client.call("updateModelTemplates", model={
        "name": EAVM_MODEL_NAME,
        "templates": expected,
    })
    _require_not_false(result, "updateModelTemplates")
    result = client.call("updateModelStyling", model={"name": EAVM_MODEL_NAME, "css": css})
    _require_not_false(result, "updateModelStyling")
    updated_templates = client.call("modelTemplates", modelName=EAVM_MODEL_NAME)
    updated_styling = client.call("modelStyling", modelName=EAVM_MODEL_NAME)
    if not isinstance(updated_templates, dict) or not isinstance(updated_styling, dict):
        raise AnkiConnectError("Live EAVM design verification returned malformed data")
    updated_css = updated_styling.get("css")
    if (
        tuple(updated_templates) != EAVM_TEMPLATE_NAMES
        or updated_templates != expected
        or updated_css != css
    ):
        raise AnkiConnectError("Live EAVM template/CSS verification failed after synchronization")


def import_and_verify(
    client: AnkiConnectClient,
    package_path: Path,
    notes_jsonl: Path,
    scratch_dir: Path,
    audio_dir: Path | None = None,
) -> int:
    """Install fresh or migrate live in place while preserving note/card history."""

    if not package_path.is_file():
        raise ValueError(f"APKG not found: {package_path}")
    expected = load_expected_signatures(notes_jsonl)
    expected_records = load_expected_records(notes_jsonl)
    expected_media = load_expected_media(notes_jsonl)
    templates = load_eavm_templates()
    css = load_production_css(STYLING_TXT)
    model_exists, current_fields, template_state = _model_contract(client)
    preflight_and_backup(client, scratch_dir)
    existing_note_ids = (
        client.call("findNotes", query=f'note:"{EAVM_MODEL_NAME}"') or []
        if model_exists else []
    )

    prior: ExistingCollectionSnapshot | None = None
    if not model_exists:
        imported = client.call("importPackage", path=package_path.resolve().as_posix())
        if imported is False:
            raise AnkiConnectError("AnkiConnect importPackage returned false")
    elif not existing_note_ids:
        # Reuse the established model in place even when it is currently
        # empty.  Align fields/templates before import so Anki cannot create a
        # suffixed model or silently retain a legacy ord0 layout.
        migrate_established_eavm_fields(client)
        sync_model_design(client)
        imported = client.call("importPackage", path=package_path.resolve().as_posix())
        if imported is False:
            raise AnkiConnectError("AnkiConnect importPackage returned false")
    else:
        if template_state is None:
            raise AnkiConnectError(
                "Existing EAVM model has no validated template layout"
            )
        prior = snapshot_existing_collection(
            client, expected_records, template_state, current_fields
        )
        migrate_established_eavm_fields(client)
        # Populate the eligibility-driving fields before modelTemplateAdd creates ord1.
        sync_existing_notes(client, notes_jsonl)
        sync_model_design(client)
        # Route both ordinals after template creation; Anki may place a new
        # ordinal in the model's default deck rather than its sibling deck.
        sync_existing_notes(client, notes_jsonl)
    sync_missing_media(client, expected_media, audio_dir or ProjectPaths().audio_dir)
    return verify_import(
        client,
        expected,
        expected_media,
        expected_records,
        prior,
        templates,
        css,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate local inputs without contacting Anki.")
    parser.add_argument("--url", default=ANKI_CONNECT_URL, help="AnkiConnect endpoint.")
    parser.add_argument("--package", type=Path, default=OUTPUT_APKG, help="APKG to import.")
    args = parser.parse_args(argv)

    paths = ProjectPaths()
    package_path = args.package.resolve()
    try:
        expected, _ = validate_local_inputs(
            package_path, paths.anki_notes_jsonl, paths.audio_dir
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(
            f"[dry-run] Would import {package_path} through AnkiConnect and verify "
            f"{sum(expected.values())} notes.",
            file=sys.stderr,
        )
        return 0

    try:
        verified_count = import_and_verify(
            AnkiConnectClient(args.url), package_path, paths.anki_notes_jsonl,
            paths.root / "scratch", paths.audio_dir,
        )
    except (AnkiConnectError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Imported package and verified {verified_count} canonical notes.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
