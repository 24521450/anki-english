from __future__ import annotations

from pathlib import Path

import pytest

from tools.sync_anki_media import (
    collect_audio_references,
    missing_media_files,
    upload_missing_media,
)


def _note(word: str, uk: str = "", us: str = "") -> dict:
    return {
        "fields": {
            "Word": {"value": word},
            "AudioUK": {"value": uk},
            "AudioUS": {"value": us},
        }
    }


def test_collect_audio_references_deduplicates_files_and_tracks_words():
    references = collect_audio_references([
        _note("offset", "[sound:uk_offset.mp3]", "[sound:us_offset.mp3]"),
        _note("offset", "[sound:uk_offset.mp3]"),
    ])

    assert references == {
        "uk_offset.mp3": {"offset"},
        "us_offset.mp3": {"offset"},
    }


def test_collect_audio_references_rejects_paths_in_sound_fields():
    with pytest.raises(ValueError, match="Invalid Anki media filename"):
        collect_audio_references([_note("bad", "[sound:../bad.mp3]")])


def test_missing_media_files_returns_only_remote_gaps_and_local_gaps(tmp_path: Path):
    (tmp_path / "present.mp3").write_bytes(b"audio")
    references = {"present.mp3": {"present"}, "missing.mp3": {"missing"}}

    missing_remote, missing_local = missing_media_files(references, set(), tmp_path)

    assert missing_remote == ["missing.mp3", "present.mp3"]
    assert missing_local == ["missing.mp3"]


def test_upload_missing_media_only_stores_requested_files(tmp_path: Path):
    for filename in ("uk.mp3", "us.mp3"):
        (tmp_path / filename).write_bytes(b"audio")

    calls = []

    class Client:
        def call(self, action: str, **params):
            calls.append((action, params))

    upload_missing_media(Client(), ["uk.mp3", "us.mp3"], tmp_path)

    assert calls == [
        ("storeMediaFile", {"filename": "uk.mp3", "path": str(tmp_path / "uk.mp3"), "deleteExisting": False}),
        ("storeMediaFile", {"filename": "us.mp3", "path": str(tmp_path / "us.mp3"), "deleteExisting": False}),
    ]


def test_upload_missing_media_is_idempotent_for_an_empty_plan(tmp_path: Path):
    calls = []

    class Client:
        def call(self, action: str, **params):
            calls.append((action, params))

    upload_missing_media(Client(), [], tmp_path)

    assert calls == []
