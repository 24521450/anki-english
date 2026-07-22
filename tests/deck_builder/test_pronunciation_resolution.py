from __future__ import annotations

import hashlib

import pytest

from src.deck_builder.pronunciation_resolution import (
    PronunciationRequest,
    PronunciationResolutionError,
    bind_headword_audio_manifest,
    build_candidate_set,
    index_headword_audio_manifest,
    index_pronunciation_locks,
    index_pronunciation_records,
    select_pronunciation,
)


def _entry(
    entry_id: str,
    pos: str,
    *,
    rank: int = 0,
    headword: str,
    uk: tuple[str | None, str | None] = (None, None),
    us: tuple[str | None, str | None] = (None, None),
) -> dict:
    return {
        "source_file": f"fixture_{headword}.html",
        "dictionary_id": entry_id.split("-", 1)[0],
        "dictionary_rank": rank,
        "entry_id": entry_id,
        "entry_index": 1,
        "headword": headword,
        "pos": [pos],
        "uk": {"ipa": uk[0], "audio_url": uk[1]},
        "us": {"ipa": us[0], "audio_url": us[1]},
    }


def _record(source: str, word: str, *entries: dict) -> dict:
    return {"source": source, "word": word, "pronunciations": list(entries)}


def _request(word: str, pos: str, guid: str = "guid-1") -> PronunciationRequest:
    return PronunciationRequest(guid=guid, word=word, pos=pos)


def _selection_lock(
    request: PronunciationRequest,
    accent: str,
    candidate_set,
    candidate,
) -> dict:
    return {
        "schema_version": 2,
        "guid": request.guid,
        "word": request.word,
        "card_pos": request.pos,
        "accent": accent,
        "decision": "select",
        "candidate_set_fingerprint": candidate_set.fingerprint,
        "selection_fingerprint": candidate.fingerprint,
        "selected_source": candidate.source,
        "selected_dictionary_id": candidate.dictionary_id,
        "selected_entry_id": candidate.entry_id,
        "selected_headword": candidate.headword,
        "selected_pos": list(candidate.pos),
        "selected_ipa": candidate.ipa,
        "selected_audio_url": candidate.audio_url,
        "review_reason": "Fixture candidate was reviewed against its exact entry.",
        "reviewer": "pytest",
        "reviewed_at": "2026-07-22",
    }


def test_diverse_uses_primary_cambridge_dictionary_per_accent():
    records = [
        _record(
            "cambridge",
            "diverse",
            _entry(
                "cald4-1", "adjective", headword="diverse",
                uk=("daɪˈvɜːs", "/uk/diverse.mp3"),
                us=("dɪˈvɝːs", "/us/diverse.mp3"),
            ),
            _entry(
                "cacd-1", "adjective", rank=1, headword="diverse",
                us=("dɪˈvɜrs", "/us/diverse-american.mp3"),
            ),
        )
    ]

    uk = select_pronunciation(_request("diverse", "adjective"), "uk", records)
    us = select_pronunciation(_request("diverse", "adjective"), "us", records)

    assert uk.candidate.ipa == "daɪˈvɜːs"
    assert us.candidate.ipa == "dɪˈvɝːs"


def test_extract_selects_pronunciation_by_pos():
    records = [
        _record(
            "cambridge",
            "extract",
            _entry(
                "cald4-1", "verb", headword="extract",
                uk=("ɪkˈstrækt", "/uk/extract-v.mp3"),
            ),
            _entry(
                "cald4-2", "noun", headword="extract",
                uk=("ˈek.strækt", "/uk/extract-n.mp3"),
            ),
        )
    ]

    selection = select_pronunciation(_request("extract", "noun"), "uk", records)
    assert selection.candidate.ipa == "ˈek.strækt"


@pytest.mark.parametrize("word", ["converse", "sake", "bow"])
def test_same_best_tier_pronunciations_fail_closed_as_ambiguous(word):
    source = "oxford" if word == "bow" else "cambridge"
    records = [
        _record(
            source,
            word,
            _entry(
                "entry-1", "noun", headword=word,
                uk=("first", f"/{word}/first.mp3"),
            ),
            _entry(
                "entry-2", "noun", headword=word,
                uk=("second", f"/{word}/second.mp3"),
            ),
        )
    ]

    with pytest.raises(PronunciationResolutionError, match="ambiguous"):
        select_pronunciation(_request(word, "noun"), "uk", records)


def test_same_payload_from_distinct_entries_remains_ambiguous():
    records = [
        _record(
            "cambridge",
            "duplicate",
            _entry(
                "cald4-1", "noun", headword="duplicate",
                uk=("same", "/uk/shared.mp3"),
            ),
            _entry(
                "cald4-2", "noun", headword="duplicate",
                uk=("same", "/uk/shared.mp3"),
            ),
        )
    ]
    request = _request("duplicate", "noun")
    candidate_set = build_candidate_set(request, "uk", records)

    assert len(candidate_set.best_candidates) == 2
    assert len({candidate.fingerprint for candidate in candidate_set.candidates}) == 2
    with pytest.raises(PronunciationResolutionError, match="ambiguous"):
        select_pronunciation(request, "uk", records)


def test_selection_lock_is_fingerprint_bound_and_cannot_bypass_best_source():
    records = [
        _record(
            "cambridge",
            "sake",
            _entry("cald4-1", "noun", headword="sake", uk=("seɪk", "/uk/sake.mp3")),
            _entry("cald4-2", "noun", headword="sake", uk=("ˈsɑː.ki", "/uk/saki.mp3")),
        ),
        _record(
            "oxford",
            "sake",
            _entry("oxford-1", "noun", headword="sake", uk=("wrong", "/uk/oxford.mp3")),
        ),
    ]
    request = _request("sake", "noun")
    candidate_set = build_candidate_set(request, "uk", records)
    chosen = next(item for item in candidate_set.best_candidates if item.ipa == "ˈsɑː.ki")
    lock = _selection_lock(request, "uk", candidate_set, chosen)

    assert select_pronunciation(request, "uk", records, lock).candidate == chosen

    stale_lock = dict(lock, candidate_set_fingerprint="0" * 64)
    with pytest.raises(PronunciationResolutionError, match="stale"):
        select_pronunciation(request, "uk", records, stale_lock)

    oxford = next(item for item in candidate_set.candidates if item.source == "oxford")
    bypass_lock = dict(lock, selection_fingerprint=oxford.fingerprint)
    with pytest.raises(PronunciationResolutionError, match="best tier"):
        select_pronunciation(request, "uk", records, bypass_lock)


@pytest.mark.parametrize(
    ("field", "stale_value"),
    [
        ("selected_source", "oxford"),
        ("selected_dictionary_id", "cacd"),
        ("selected_entry_id", "cald4-stale"),
        ("selected_headword", "saki"),
        ("selected_pos", ["verb"]),
        ("selected_ipa", "stale"),
        ("selected_audio_url", "/uk/stale.mp3"),
    ],
)
def test_selection_lock_rejects_stale_selected_candidate_metadata(
    field,
    stale_value,
):
    records = [
        _record(
            "cambridge",
            "sake",
            _entry(
                "cald4-1", "noun", headword="sake",
                uk=("ˈsɑː.ki", "/uk/saki.mp3"),
            ),
        )
    ]
    request = _request("sake", "noun")
    candidate_set = build_candidate_set(request, "uk", records)
    chosen = candidate_set.best_candidates[0]
    lock = _selection_lock(request, "uk", candidate_set, chosen)
    lock[field] = stale_value

    with pytest.raises(PronunciationResolutionError, match=field):
        select_pronunciation(request, "uk", records, lock)


@pytest.mark.parametrize(
    "field",
    ["word", "card_pos", "review_reason", "reviewer", "reviewed_at"],
)
def test_lock_index_requires_review_metadata(field):
    records = [
        _record(
            "cambridge",
            "sake",
            _entry(
                "cald4-1", "noun", headword="sake",
                uk=("ˈsɑː.ki", "/uk/saki.mp3"),
            ),
        )
    ]
    request = _request("sake", "noun")
    candidate_set = build_candidate_set(request, "uk", records)
    lock = _selection_lock(
        request, "uk", candidate_set, candidate_set.best_candidates[0]
    )
    lock.pop(field)

    with pytest.raises(PronunciationResolutionError, match=field):
        index_pronunciation_locks([lock])


def test_lock_index_requires_iso_review_date():
    records = [
        _record(
            "cambridge",
            "sake",
            _entry(
                "cald4-1", "noun", headword="sake",
                uk=("ˈsɑː.ki", "/uk/saki.mp3"),
            ),
        )
    ]
    request = _request("sake", "noun")
    candidate_set = build_candidate_set(request, "uk", records)
    lock = _selection_lock(
        request, "uk", candidate_set, candidate_set.best_candidates[0]
    )
    lock["reviewed_at"] = "2026-02-30"

    with pytest.raises(PronunciationResolutionError, match="reviewed_at"):
        index_pronunciation_locks([lock])


def test_each_accent_falls_back_independently_to_oxford():
    records = [
        _record(
            "cambridge",
            "dynamic",
            _entry(
                "cald4-1", "adjective", headword="dynamic",
                uk=("kaɪm", "/cambridge/uk.mp3"),
                us=(None, "/cambridge/us-without-ipa.mp3"),
            ),
        ),
        _record(
            "oxford",
            "dynamic",
            _entry(
                "dynamic_1", "adjective", headword="dynamic",
                uk=("əʊ", "/oxford/uk.mp3"),
                us=("oʊ", "/oxford/us.mp3"),
            ),
        ),
    ]

    uk = select_pronunciation(_request("dynamic", "adjective"), "uk", records)
    us = select_pronunciation(_request("dynamic", "adjective"), "us", records)

    assert uk.candidate.source == "cambridge"
    assert us.candidate.source == "oxford"


def test_no_pronunciation_lock_is_exact_and_stales_when_candidate_appears():
    request = _request("have the floor", "phrase")
    incomplete = [
        _record(
            "cambridge",
            "have the floor",
            _entry(
                "phrase-1", "phrase", headword="have the floor",
                uk=(None, "/generic/not-paired.mp3"),
            ),
        )
    ]
    candidate_set = build_candidate_set(request, "uk", incomplete)
    lock = {
        "schema_version": 2,
        "guid": request.guid,
        "word": request.word,
        "card_pos": request.pos,
        "accent": "uk",
        "decision": "no_pronunciation",
        "candidate_set_fingerprint": candidate_set.fingerprint,
        "review_reason": "Fixture has no complete pronunciation candidate.",
        "reviewer": "pytest",
        "reviewed_at": "2026-07-22",
    }

    selection = select_pronunciation(request, "uk", incomplete, lock)
    assert selection.no_pronunciation
    assert selection.candidate is None

    complete = [
        _record(
            "cambridge",
            "have the floor",
            _entry(
                "phrase-1", "phrase", headword="have the floor",
                uk=("flɔː", "/generic/not-paired.mp3"),
            ),
        )
    ]
    with pytest.raises(PronunciationResolutionError, match="stale"):
        select_pronunciation(request, "uk", complete, lock)


def test_no_pronunciation_lock_cannot_suppress_a_complete_candidate():
    request = _request("diverse", "adjective")
    records = [
        _record(
            "cambridge",
            "diverse",
            _entry(
                "cald4-1", "adjective", headword="diverse",
                uk=("daɪˈvɜːs", "/uk/diverse.mp3"),
            ),
        )
    ]
    candidate_set = build_candidate_set(request, "uk", records)
    lock = {
        "schema_version": 2,
        "guid": request.guid,
        "word": request.word,
        "card_pos": request.pos,
        "accent": "uk",
        "decision": "no_pronunciation",
        "candidate_set_fingerprint": candidate_set.fingerprint,
        "review_reason": "Invalid fixture suppression must fail closed.",
        "reviewer": "pytest",
        "reviewed_at": "2026-07-22",
    }

    with pytest.raises(PronunciationResolutionError, match="complete candidate"):
        select_pronunciation(request, "uk", records, lock)


def test_source_lookup_does_not_use_morphology_or_fuzzy_filenames():
    records = [
        _record(
            "cambridge",
            "diverse",
            _entry("cald4-1", "adjective", headword="diverse", uk=("ipa", "/uk.mp3")),
        )
    ]
    with pytest.raises(PronunciationResolutionError, match="missing"):
        select_pronunciation(_request("diversely", "adverb"), "uk", records)


def test_exact_record_index_preserves_candidate_set_and_fingerprint():
    target = _record(
        "cambridge",
        "diverse",
        _entry(
            "cald4-1", "adjective", headword="diverse",
            uk=("daɪˈvɜːs", "/uk/diverse.mp3"),
        ),
    )
    unrelated = _record(
        "cambridge",
        "diversely",
        _entry(
            "cald4-1", "adverb", headword="diversely",
            uk=("unrelated", "/uk/diversely.mp3"),
        ),
    )
    request = _request("diverse", "adjective")

    full = build_candidate_set(request, "uk", [unrelated, target])
    indexed = index_pronunciation_records([unrelated, target])
    exact = build_candidate_set(request, "uk", indexed["diverse"])

    assert exact == full
    assert set(indexed) == {"diverse", "diversely"}


def test_manifest_binds_selected_source_url_to_exact_local_bytes(tmp_path):
    records = [
        _record(
            "cambridge",
            "diverse",
            _entry(
                "cald4-1", "adjective", headword="diverse",
                uk=("daɪˈvɜːs", "/media/uk/diverse.mp3"),
            ),
        )
    ]
    selection = select_pronunciation(_request("diverse", "adjective"), "uk", records)
    audio_bytes = b"ID3" + b"fixture-audio"
    audio_path = tmp_path / "cambridge_uk_diverse.mp3"
    audio_path.write_bytes(audio_bytes)
    row = {
        "schema_version": 2,
        "selection_fingerprint": selection.candidate.fingerprint,
        "media_fingerprint": selection.candidate.media_fingerprint,
        "source": "cambridge",
        "parent_word": "diverse",
        "dictionary_id": "cald4",
        "entry_id": "cald4-1",
        "headword": "diverse",
        "pos": ["adjective"],
        "accent": "uk",
        "ipa": "daɪˈvɜːs",
        "audio_url": "/media/uk/diverse.mp3",
        "filename": audio_path.name,
        "sha256": hashlib.sha256(audio_bytes).hexdigest(),
        "byte_count": len(audio_bytes),
    }

    manifest = index_headword_audio_manifest([row], audio_dir=tmp_path)
    resolved = bind_headword_audio_manifest(selection, manifest)
    assert resolved.media_filename == audio_path.name
    assert resolved.media_sha256 == row["sha256"]


def _manifest_row(candidate, *, filename="shared.mp3", sha256="0" * 64):
    return {
        "schema_version": 2,
        "selection_fingerprint": candidate.fingerprint,
        "media_fingerprint": candidate.media_fingerprint,
        "source": candidate.source,
        "parent_word": candidate.parent_word,
        "dictionary_id": candidate.dictionary_id,
        "entry_id": candidate.entry_id,
        "headword": candidate.headword,
        "pos": list(candidate.pos),
        "accent": candidate.accent,
        "ipa": candidate.ipa,
        "audio_url": candidate.audio_url,
        "filename": filename,
        "sha256": sha256,
        "byte_count": 123,
    }


def test_manifest_allows_distinct_entry_identities_to_share_exact_media():
    records = [
        _record(
            "cambridge",
            "duplicate",
            _entry(
                "cald4-1", "noun", headword="duplicate",
                uk=("same", "/media/uk/shared.mp3"),
            ),
            _entry(
                "cald4-2", "noun", headword="duplicate",
                uk=("same", "/media/uk/shared.mp3"),
            ),
        )
    ]
    candidates = build_candidate_set(
        _request("duplicate", "noun"), "uk", records
    ).best_candidates

    manifest = index_headword_audio_manifest([
        _manifest_row(candidates[0]),
        _manifest_row(candidates[1]),
    ])

    assert len(manifest) == 2
    assert len({entry.media_fingerprint for entry in manifest.values()}) == 1


def test_manifest_rejects_one_filename_for_distinct_media_fingerprints():
    records = [
        _record(
            "cambridge",
            "duplicate",
            _entry(
                "cald4-1", "noun", headword="duplicate",
                uk=("first", "/media/uk/first.mp3"),
            ),
            _entry(
                "cald4-2", "noun", headword="duplicate",
                uk=("second", "/media/uk/second.mp3"),
            ),
        )
    ]
    candidates = build_candidate_set(
        _request("duplicate", "noun"), "uk", records
    ).best_candidates

    with pytest.raises(PronunciationResolutionError, match="filename collision"):
        index_headword_audio_manifest([
            _manifest_row(candidates[0]),
            _manifest_row(candidates[1]),
        ])


def test_manifest_rejects_multiple_attestations_for_one_media_fingerprint():
    records = [
        _record(
            "cambridge",
            "duplicate",
            _entry(
                "cald4-1", "noun", headword="duplicate",
                uk=("same", "/media/uk/shared.mp3"),
            ),
            _entry(
                "cald4-2", "noun", headword="duplicate",
                uk=("same", "/media/uk/shared.mp3"),
            ),
        )
    ]
    candidates = build_candidate_set(
        _request("duplicate", "noun"), "uk", records
    ).best_candidates

    with pytest.raises(PronunciationResolutionError, match="conflicting bytes"):
        index_headword_audio_manifest([
            _manifest_row(candidates[0], filename="first.mp3"),
            _manifest_row(candidates[1], filename="second.mp3"),
        ])
