from __future__ import annotations

import asyncio
from dataclasses import replace
import json

import pytest

from src.deck_builder.pronunciation_resolution import PronunciationRequest, build_candidate_set
from tools import sync_pronunciation_audio


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _source_record() -> dict:
    return {
        "source": "cambridge",
        "word": "diverse",
        "pronunciations": [{
            "source_file": "cambridge_diverse.html",
            "dictionary_id": "cald4",
            "dictionary_rank": 0,
            "entry_id": "cald4-1",
            "entry_index": 1,
            "headword": "diverse",
            "pos": ["adjective"],
            "uk": {"ipa": "daɪˈvɜːs", "audio_url": "/media/uk/diverse.mp3"},
            "us": {"ipa": "dɪˈvɝːs", "audio_url": "/media/us/diverse.mp3"},
        }],
    }


def _candidate(url: str, *, source: str = "cambridge"):
    record = _source_record()
    record["source"] = source
    candidate = build_candidate_set(
        PronunciationRequest(guid="g1", word="diverse", pos="adjective"),
        "uk",
        [record],
    ).best_candidates[0]
    return replace(candidate, audio_url=url)


class _ChunkStream:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.iterated = False

    def iter_chunked(self, _size):
        async def _iterate():
            self.iterated = True
            for chunk in self.chunks:
                yield chunk

        return _iterate()


class _Response:
    def __init__(self, *, status=200, headers=None, chunks=()):
        self.status = status
        self.headers = dict(headers or {})
        self.content = _ChunkStream(chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_absolute_audio_url_requires_official_https_host_and_media_path():
    candidate = _candidate(
        "/media/english/uk_pron/d/div/diverse.mp3",
    )
    assert sync_pronunciation_audio._absolute_audio_url(candidate) == (
        "https://dictionary.cambridge.org/media/english/uk_pron/d/div/diverse.mp3"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://dictionary.cambridge.org/media/english/diverse.mp3",
        "https://dictionary.cambridge.org.evil.example/media/english/diverse.mp3",
        "https://dictionary.cambridge.org/media/not-audio/diverse.mp3",
        "https://dictionary.cambridge.org/media/english/../diverse.mp3",
        "https://dictionary.cambridge.org/media/english/diverse.wav",
        "https://dictionary.cambridge.org/media/english/diverse.mp3?redirect=evil",
    ],
)
def test_absolute_audio_url_rejects_untrusted_host_or_path(url):
    with pytest.raises(sync_pronunciation_audio.PronunciationResolutionError):
        sync_pronunciation_audio._absolute_audio_url(_candidate(url))


def test_oxford_audio_requires_its_official_host():
    candidate = _candidate(
        "https://www.oxfordlearnersdictionaries.com/media/english/uk_pron/d/div/diverse.mp3",
        source="oxford",
    )
    assert sync_pronunciation_audio._absolute_audio_url(candidate) == candidate.audio_url
    with pytest.raises(sync_pronunciation_audio.PronunciationResolutionError):
        sync_pronunciation_audio._absolute_audio_url(
            replace(
                candidate,
                audio_url="https://dictionary.cambridge.org/media/english/diverse.mp3",
            )
        )


def test_download_disables_redirects():
    response = _Response(status=302, headers={"Location": "https://evil.example"})
    session = _Session(response)

    with pytest.raises(sync_pronunciation_audio.PronunciationResolutionError, match="HTTP 302"):
        asyncio.run(
            sync_pronunciation_audio._download_audio(
                _candidate("/media/english/uk_pron/d/div/diverse.mp3"),
                session,
                sync_pronunciation_audio._RequestRateLimiter(1000),
            )
        )

    assert session.calls[0][1]["allow_redirects"] is False


def test_bounded_response_rejects_oversized_declared_length_without_streaming():
    response = _Response(
        headers={
            "Content-Length": str(sync_pronunciation_audio.MAX_AUDIO_BYTES + 1),
        },
    )

    with pytest.raises(sync_pronunciation_audio.PronunciationResolutionError, match="maximum size"):
        asyncio.run(sync_pronunciation_audio._read_bounded_response(response))

    assert response.content.iterated is False


def test_bounded_response_rejects_chunked_body_over_limit():
    response = _Response(
        chunks=[
            b"x" * (sync_pronunciation_audio.MAX_AUDIO_BYTES - 3),
            b"xxxx",
        ],
    )

    with pytest.raises(sync_pronunciation_audio.PronunciationResolutionError, match="maximum size"):
        asyncio.run(sync_pronunciation_audio._read_bounded_response(response))


def test_bounded_response_streams_chunks_under_limit():
    response = _Response(headers={"Content-Length": "6"}, chunks=[b"ID", b"3xxx"])

    assert asyncio.run(sync_pronunciation_audio._read_bounded_response(response)) == b"ID3xxx"
    assert response.content.iterated is True


def test_global_sync_dry_run_plans_every_active_accent_without_writes(tmp_path):
    card_registry = tmp_path / "card_registry.jsonl"
    cambridge = tmp_path / "cambridge.jsonl"
    oxford = tmp_path / "oxford.jsonl"
    locks = tmp_path / "locks.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    audio_dir = tmp_path / "audio"
    _write_jsonl(card_registry, [{
        "guid": "g1",
        "word": "diverse",
        "pos": "adjective",
        "status": "active",
    }])
    _write_jsonl(cambridge, [_source_record()])
    _write_jsonl(oxford, [])
    _write_jsonl(locks, [])

    result = sync_pronunciation_audio.main([
        "--card-registry", str(card_registry),
        "--cambridge-jsonl", str(cambridge),
        "--oxford-jsonl", str(oxford),
        "--locks", str(locks),
        "--manifest", str(manifest),
        "--audio-dir", str(audio_dir),
    ])

    assert result == 0
    assert not manifest.exists()
    assert not audio_dir.exists()


def test_global_sync_honors_exact_no_pronunciation_lock(tmp_path):
    card = {"guid": "g1", "word": "diverse", "pos": "adjective", "status": "active"}
    record = _source_record()
    record["pronunciations"][0]["uk"]["ipa"] = None
    candidate_set = build_candidate_set(
        PronunciationRequest(guid="g1", word="diverse", pos="adjective"),
        "uk",
        [record],
    )
    lock = {
        "schema_version": 2,
        "guid": "g1",
        "word": "diverse",
        "card_pos": "adjective",
        "accent": "uk",
        "decision": "no_pronunciation",
        "candidate_set_fingerprint": candidate_set.fingerprint,
        "review_reason": "Fixture UK entry has no same-entry IPA/audio pair.",
        "reviewer": "pytest",
        "reviewed_at": "2026-07-22",
    }

    plan = sync_pronunciation_audio.build_sync_plan(
        [card],
        [record],
        [lock],
        [],
        tmp_path,
    )

    assert plan.no_pronunciation_count == 1
    assert {item.candidate.accent for item in plan.items} == {"us"}


def test_filename_allocation_never_selects_or_reuses_a_colliding_source_name():
    record = _source_record()
    selection = build_candidate_set(
        PronunciationRequest(guid="g1", word="diverse", pos="adjective"),
        "uk",
        [record],
    ).best_candidates[0]

    filename = sync_pronunciation_audio.allocate_media_filename(
        selection,
        {"Cambridge_UK_Diverse.mp3"},
    )

    assert filename == f"cambridge_uk_diverse_{selection.fingerprint[:12]}.mp3"


def test_empty_manifest_bootstraps_canonical_name_over_existing_unowned_file(tmp_path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "cambridge_uk_diverse.mp3").write_bytes(b"legacy-unowned")

    plan = sync_pronunciation_audio.build_sync_plan(
        [{"guid": "g1", "word": "diverse", "pos": "adjective", "status": "active"}],
        [_source_record()],
        [],
        [],
        audio_dir,
    )
    uk_item = next(item for item in plan.items if item.candidate.accent == "uk")

    assert uk_item.filename == "cambridge_uk_diverse.mp3"
    assert uk_item.needs_download


def test_apply_sync_plan_does_not_publish_partial_downloads(tmp_path, monkeypatch):
    plan = sync_pronunciation_audio.build_sync_plan(
        [{"guid": "g1", "word": "diverse", "pos": "adjective", "status": "active"}],
        [_source_record()],
        [],
        [],
        tmp_path / "audio",
    )
    calls = 0

    async def fake_download(candidate, session, rate_limiter):
        nonlocal calls
        calls += 1
        if candidate.accent == "us":
            raise RuntimeError("network interrupted")
        await asyncio.sleep(0)
        return b"ID3" + (b"x" * 1000)

    monkeypatch.setattr(sync_pronunciation_audio, "_download_audio", fake_download)
    audio_dir = tmp_path / "audio"
    manifest = tmp_path / "headword_audio_manifest.jsonl"

    with pytest.raises(RuntimeError, match="network interrupted"):
        sync_pronunciation_audio.apply_sync_plan(plan, audio_dir, manifest)

    assert list(audio_dir.glob("*.mp3")) == []
    assert not manifest.exists()


def test_apply_sync_plan_bounds_async_download_concurrency(tmp_path, monkeypatch):
    plan = sync_pronunciation_audio.build_sync_plan(
        [{"guid": "g1", "word": "diverse", "pos": "adjective", "status": "active"}],
        [_source_record()],
        [],
        [],
        tmp_path / "audio",
    )
    active = 0
    peak = 0

    async def fake_download(candidate, session, rate_limiter):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return b"ID3" + (candidate.accent.encode("ascii") * 600)

    monkeypatch.setattr(sync_pronunciation_audio, "_download_audio", fake_download)
    audio_dir = tmp_path / "audio"
    manifest = tmp_path / "headword_audio_manifest.jsonl"

    sync_pronunciation_audio.apply_sync_plan(
        plan,
        audio_dir,
        manifest,
        concurrency=1,
    )

    assert peak == 1
    assert len(list(audio_dir.glob("*.mp3"))) == 2
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == 2


def test_sync_downloads_shared_media_once_but_manifests_each_entry_identity(
    tmp_path,
    monkeypatch,
):
    record = _source_record()
    adjective = record["pronunciations"][0]
    noun = {
        **adjective,
        "entry_id": "cald4-2",
        "entry_index": 2,
        "pos": ["noun"],
    }
    record["pronunciations"] = [adjective, noun]
    cards = [
        {
            "guid": "g-adjective",
            "word": "diverse",
            "pos": "adjective",
            "status": "active",
        },
        {
            "guid": "g-noun",
            "word": "diverse",
            "pos": "noun",
            "status": "active",
        },
    ]
    audio_dir = tmp_path / "audio"
    manifest = tmp_path / "headword_audio_manifest.jsonl"
    plan = sync_pronunciation_audio.build_sync_plan(
        cards, [record], [], [], audio_dir
    )
    calls = []

    async def fake_download(candidate, session, rate_limiter):
        calls.append(candidate.media_fingerprint)
        return b"ID3" + (candidate.accent.encode("ascii") * 600)

    monkeypatch.setattr(
        sync_pronunciation_audio, "_download_audio", fake_download
    )
    sync_pronunciation_audio.apply_sync_plan(plan, audio_dir, manifest)

    rows = sync_pronunciation_audio.load_jsonl(manifest)
    indexed = sync_pronunciation_audio.index_headword_audio_manifest(
        rows, audio_dir=audio_dir
    )
    assert len(plan.items) == 4
    assert len(calls) == 2
    assert len(indexed) == 4
    assert len(list(audio_dir.glob("*.mp3"))) == 2
