#!/usr/bin/env python3
"""Synchronize missing local audio files into the live Anki collection."""
from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import requests

from src.config import ProjectPaths


ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DEFAULT_DECK = "English Academic Vocabulary"
SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")


class AnkiConnectError(RuntimeError):
    """AnkiConnect did not return a successful response."""


class AnkiConnectClient:
    def __init__(self, url: str = ANKI_CONNECT_URL) -> None:
        self.url = url

    def call(self, action: str, **params):
        try:
            response = requests.post(
                self.url,
                json={"action": action, "version": 6, "params": params},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise AnkiConnectError(f"Could not call AnkiConnect: {exc}") from exc

        if payload.get("error"):
            raise AnkiConnectError(f"AnkiConnect {action} failed: {payload['error']}")
        return payload.get("result")


def _valid_media_name(name: str) -> bool:
    return bool(name) and Path(name).name == name and "/" not in name and "\\" not in name


def collect_audio_references(notes: Iterable[dict]) -> dict[str, set[str]]:
    """Map each referenced media filename to the live note headwords using it."""
    references: dict[str, set[str]] = {}
    for note in notes:
        fields = note.get("fields") or {}
        word = ((fields.get("Word") or {}).get("value") or "").strip() or "<unknown>"
        for field_name in ("AudioUK", "AudioUS"):
            value = ((fields.get(field_name) or {}).get("value") or "").strip()
            for name in SOUND_RE.findall(value):
                if not _valid_media_name(name):
                    raise ValueError(f"Invalid Anki media filename {name!r} on {word}")
                references.setdefault(name, set()).add(word)
    return references


def missing_media_files(
    references: dict[str, set[str]],
    remote_media: set[str],
    audio_dir: Path,
) -> tuple[list[str], list[str]]:
    """Return missing remote files and references not available in the repo."""
    missing_remote = sorted(name for name in references if name not in remote_media)
    missing_local = [name for name in missing_remote if not (audio_dir / name).is_file()]
    return missing_remote, missing_local


def _chunks(values: list[int], size: int = 500) -> Iterable[list[int]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def load_deck_notes(client: AnkiConnectClient, deck: str) -> list[dict]:
    note_ids = client.call("findNotes", query=f'deck:"{deck}"') or []
    notes: list[dict] = []
    for batch in _chunks(note_ids):
        notes.extend(client.call("notesInfo", notes=batch) or [])
    return notes


def upload_missing_media(
    client: AnkiConnectClient,
    filenames: Iterable[str],
    audio_dir: Path,
) -> None:
    for filename in filenames:
        client.call(
            "storeMediaFile",
            filename=filename,
            path=str(audio_dir / filename),
            deleteExisting=False,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Upload missing audio into Anki.")
    parser.add_argument("--deck", default=DEFAULT_DECK, help="Anki deck search root.")
    parser.add_argument("--url", default=ANKI_CONNECT_URL, help="AnkiConnect endpoint.")
    args = parser.parse_args(argv)

    paths = ProjectPaths()
    client = AnkiConnectClient(args.url)
    try:
        notes = load_deck_notes(client, args.deck)
        references = collect_audio_references(notes)
        remote_media = set(client.call("getMediaFilesNames", pattern="*") or [])
        missing_remote, missing_local = missing_media_files(references, remote_media, paths.audio_dir)
    except (AnkiConnectError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Deck notes: {len(notes)}")
    print(f"Referenced audio files: {len(references)}")
    print(f"Missing from Anki media: {len(missing_remote)}")
    if missing_remote:
        print("  " + "\n  ".join(missing_remote))

    if missing_local:
        print("Error: referenced audio missing from local audio/: " + ", ".join(missing_local), file=sys.stderr)
        return 1
    if not args.apply:
        print("Dry run only. Re-run with --apply to upload missing files.")
        return 0
    if not missing_remote:
        print("Anki media is already synchronized.")
        return 0

    try:
        upload_missing_media(client, missing_remote, paths.audio_dir)
        updated_media = set(client.call("getMediaFilesNames", pattern="*") or [])
    except AnkiConnectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    remaining = sorted(name for name in missing_remote if name not in updated_media)
    if remaining:
        print("Error: Anki media upload verification failed: " + ", ".join(remaining), file=sys.stderr)
        return 1

    print(f"Uploaded and verified {len(missing_remote)} audio file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
