#!/usr/bin/env python3
"""Import the built APKG into a running Anki instance through AnkiConnect."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from src.config import ProjectPaths
from src.deck_builder.package_command import EAVM_FIELD_NAMES, EAVM_MODEL_NAME, OUTPUT_APKG


ANKI_CONNECT_URL = "http://127.0.0.1:8765"
ANKI_CONNECT_API_VERSION = 6
EAVM_FIELDS = EAVM_FIELD_NAMES
ESTABLISHED_EAVM_FIELDS = EAVM_FIELDS[:15]
ROOT_DECK = "English Academic Vocabulary"
SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")
AUDIO_SRC_RE = re.compile(r"<audio\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)

JSON_TO_ANKI_FIELD: tuple[tuple[str, str], ...] = (
    ("word", "Word"),
    ("pos", "PartOfSpeech"),
    ("ipa", "IPA"),
    ("definition", "Definition"),
    ("example", "Example"),
    ("collocations", "Collocations"),
    ("wordfamily", "WordFamily"),
    ("uk_audio", "AudioUK"),
    ("us_audio", "AudioUS"),
    ("source1", "AudioSource"),
    ("source2", "Source"),
    ("cefr", "CEFRLevel"),
    ("idioms", "Idioms"),
    ("synonyms", "Synonyms"),
    ("antonyms", "Antonyms"),
    ("example_audio_uk", "ExampleAudioUK"),
    ("example_audio_us", "ExampleAudioUS"),
    ("idiom_example_audio_uk", "IdiomExampleAudioUK"),
    ("idiom_example_audio_us", "IdiomExampleAudioUS"),
)


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
    fields = note.get("fields") or {}
    return tuple(str((fields.get(name) or {}).get("value") or "") for _, name in JSON_TO_ANKI_FIELD)


def verify_import(
    client: AnkiConnectClient,
    expected: Counter[tuple[str, ...]],
    expected_media: set[str],
) -> int:
    """Fail closed unless the canonical note type and every expected note resolve."""
    field_names = client.call("modelFieldNames", modelName=EAVM_MODEL_NAME) or []
    if tuple(field_names) != EAVM_FIELDS:
        raise AnkiConnectError(
            f"Unexpected {EAVM_MODEL_NAME!r} fields: expected {list(EAVM_FIELDS)!r}, got {field_names!r}"
        )

    note_ids = client.call(
        "findNotes", query=f'deck:"{ROOT_DECK}" note:"{EAVM_MODEL_NAME}"'
    ) or []
    expected_count = sum(expected.values())
    if len(note_ids) != expected_count:
        raise AnkiConnectError(
            f"Import verification expected {expected_count} notes in {ROOT_DECK!r}, "
            f"but Anki returned {len(note_ids)}"
        )
    live: Counter[tuple[str, ...]] = Counter()
    for batch in _chunks(note_ids):
        for note in client.call("notesInfo", notes=batch) or []:
            if note.get("modelName") == EAVM_MODEL_NAME:
                live[_live_signature(note)] += 1

    missing = expected - live
    if missing:
        missing_count = sum(missing.values())
        samples = [signature[0] or "<blank Word>" for signature in list(missing)[:5]]
        raise AnkiConnectError(
            f"Import verification found {missing_count} missing/mismatched note(s); sample Word values: {samples}"
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

    model_names = set(client.call("modelNames") or [])
    if EAVM_MODEL_NAME in model_names:
        current_fields = tuple(client.call("modelFieldNames", modelName=EAVM_MODEL_NAME) or [])
        if current_fields not in (ESTABLISHED_EAVM_FIELDS, EAVM_FIELDS):
            raise AnkiConnectError(
                f"Existing {EAVM_MODEL_NAME!r} has an incompatible field contract: "
                f"{list(current_fields)!r}"
            )

    if ROOT_DECK not in set(client.call("deckNames") or []):
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


def import_and_verify(
    client: AnkiConnectClient,
    package_path: Path,
    notes_jsonl: Path,
    scratch_dir: Path,
) -> int:
    """Import through Anki's native package importer, then verify canonical fields."""
    expected = load_expected_signatures(notes_jsonl)
    expected_media = load_expected_media(notes_jsonl)
    preflight_and_backup(client, scratch_dir)
    # AnkiConnect importPackage delegates to Anki's APKG importer. The stable
    # note GUIDs and model ID inside the package provide update-in-place semantics.
    client.call("importPackage", path=package_path.resolve().as_posix())
    return verify_import(client, expected, expected_media)


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
            AnkiConnectClient(args.url), package_path, paths.anki_notes_jsonl, paths.root / "scratch"
        )
    except (AnkiConnectError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Imported package and verified {verified_count} canonical notes.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
