"""Entry-scoped pronunciation selection and headword-media binding."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence


ACCENTS = frozenset({"uk", "us"})
SOURCE_RANK = {"cambridge": 0, "oxford": 1}
LOCK_DECISIONS = frozenset({"select", "no_pronunciation"})
PRONUNCIATION_LOCK_SCHEMA_VERSION = 2
HEADWORD_AUDIO_MANIFEST_SCHEMA_VERSION = 2
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DISPLAY_QUALIFIER_RE = re.compile(r"\s*\([^)]*\)\s*$")
_SPACE_RE = re.compile(r"\s+")
_POS_ALIASES = {
    "phrasal verb": "verb",
    "linking verb": "verb",
}
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PronunciationResolutionError(ValueError):
    """Raised when pronunciation evidence cannot be resolved exactly."""


@dataclass(frozen=True)
class PronunciationRequest:
    guid: str
    word: str
    pos: str | Sequence[str]
    source_word: str | None = None


@dataclass(frozen=True)
class PronunciationCandidate:
    source: str
    parent_word: str
    accent: str
    ipa: str
    audio_url: str
    source_file: str
    dictionary_id: str
    dictionary_rank: int
    entry_id: str
    entry_index: int
    headword: str
    pos: tuple[str, ...]
    tier: tuple[int, int, int, int]

    @property
    def fingerprint(self) -> str:
        return selection_fingerprint(
            self.source,
            self.parent_word,
            self.accent,
            self.ipa,
            self.audio_url,
            dictionary_id=self.dictionary_id,
            entry_id=self.entry_id,
            headword=self.headword,
            pos=self.pos,
        )

    @property
    def media_fingerprint(self) -> str:
        return pronunciation_media_fingerprint(
            self.source,
            self.parent_word,
            self.accent,
            self.ipa,
            self.audio_url,
        )


@dataclass(frozen=True)
class PronunciationCandidateSet:
    source_word: str
    accent: str
    candidates: tuple[PronunciationCandidate, ...]
    best_candidates: tuple[PronunciationCandidate, ...]
    fingerprint: str


@dataclass(frozen=True)
class PronunciationSelection:
    accent: str
    candidate_set_fingerprint: str
    candidate: PronunciationCandidate | None
    decision: str
    automatic: bool

    @property
    def no_pronunciation(self) -> bool:
        return self.decision == "no_pronunciation"


@dataclass(frozen=True)
class HeadwordAudioManifestEntry:
    selection_fingerprint: str
    media_fingerprint: str
    source: str
    parent_word: str
    dictionary_id: str
    entry_id: str
    headword: str
    pos: tuple[str, ...]
    accent: str
    ipa: str
    audio_url: str
    filename: str
    sha256: str
    byte_count: int

    def to_row(self) -> dict[str, object]:
        return {
            "schema_version": HEADWORD_AUDIO_MANIFEST_SCHEMA_VERSION,
            "selection_fingerprint": self.selection_fingerprint,
            "media_fingerprint": self.media_fingerprint,
            "source": self.source,
            "parent_word": self.parent_word,
            "dictionary_id": self.dictionary_id,
            "entry_id": self.entry_id,
            "headword": self.headword,
            "pos": list(self.pos),
            "accent": self.accent,
            "ipa": self.ipa,
            "audio_url": self.audio_url,
            "filename": self.filename,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True)
class ResolvedPronunciation:
    accent: str
    source: str
    ipa: str
    audio_url: str
    selection_fingerprint: str
    media_filename: str
    media_sha256: str
    no_pronunciation: bool = False


def _canonical_sha256(payload: object) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_source_word(value: object) -> str:
    text = _DISPLAY_QUALIFIER_RE.sub("", str(value or "").casefold()).strip()
    return _SPACE_RE.sub(" ", text)


def normalize_ipa(value: object) -> str:
    text = str(value or "").strip()
    while len(text) >= 2 and text.startswith("/") and text.endswith("/"):
        text = text[1:-1].strip()
    return text


def index_pronunciation_records(
    source_records: Iterable[dict],
) -> dict[str, tuple[dict, ...]]:
    """Index records by exact normalized source word while preserving order."""
    indexed: dict[str, list[dict]] = {}
    for record in source_records:
        source = str(record.get("source") or "").casefold()
        source_word = normalize_source_word(record.get("word"))
        if source not in SOURCE_RANK or not source_word:
            continue
        indexed.setdefault(source_word, []).append(record)
    return {word: tuple(records) for word, records in indexed.items()}


def _normalize_pos(value: str | Sequence[str]) -> tuple[str, ...]:
    raw_parts: list[str] = []
    values = [value] if isinstance(value, str) else list(value)
    for item in values:
        raw_parts.extend(re.split(r"\s*[,/]\s*", str(item or "")))
    normalized: list[str] = []
    for part in raw_parts:
        pos = _SPACE_RE.sub(" ", part.casefold().replace("_", " ")).strip()
        pos = _POS_ALIASES.get(pos, pos)
        if pos and pos not in normalized:
            normalized.append(pos)
    return tuple(normalized)


def pronunciation_media_fingerprint(
    source: str,
    parent_word: str,
    accent: str,
    ipa: str,
    audio_url: str,
) -> str:
    """Return the v1-compatible IPA/audio payload key, not entry identity."""
    source = source.casefold().strip()
    accent = accent.casefold().strip()
    if source not in SOURCE_RANK or accent not in ACCENTS:
        raise PronunciationResolutionError(
            f"invalid pronunciation source/accent: {source!r}/{accent!r}"
        )
    return _canonical_sha256({
        "schema_version": 1,
        "source": source,
        "parent_word": normalize_source_word(parent_word),
        "accent": accent,
        "ipa": normalize_ipa(ipa),
        "audio_url": str(audio_url or "").strip(),
    })


def selection_fingerprint(
    source: str,
    parent_word: str,
    accent: str,
    ipa: str,
    audio_url: str,
    *,
    dictionary_id: str,
    entry_id: str,
    headword: str,
    pos: str | Sequence[str],
) -> str:
    source = source.casefold().strip()
    accent = accent.casefold().strip()
    dictionary_id = str(dictionary_id or "").strip()
    entry_id = str(entry_id or "").strip()
    if source not in SOURCE_RANK or accent not in ACCENTS:
        raise PronunciationResolutionError(
            f"invalid pronunciation source/accent: {source!r}/{accent!r}"
        )
    if not dictionary_id or not entry_id:
        raise PronunciationResolutionError(
            "pronunciation selection is missing dictionary/entry identity"
        )
    return _canonical_sha256({
        "schema_version": 2,
        "source": source,
        "parent_word": normalize_source_word(parent_word),
        "dictionary_id": dictionary_id,
        "entry_id": entry_id,
        "headword": normalize_source_word(headword),
        "pos": list(_normalize_pos(pos)),
        "accent": accent,
        "ipa": normalize_ipa(ipa),
        "audio_url": str(audio_url or "").strip(),
    })


def _pos_rank(
    request_pos: tuple[str, ...],
    candidate_pos: tuple[str, ...],
) -> int | None:
    request_set = set(request_pos)
    candidate_set = set(candidate_pos)
    if candidate_set == request_set:
        return 0
    if request_set and candidate_set & request_set:
        return 1
    if not candidate_set:
        return 2
    if not request_set:
        return 1
    return None


def build_candidate_set(
    request: PronunciationRequest,
    accent: str,
    source_records: Iterable[dict],
    *,
    source_word: str | None = None,
) -> PronunciationCandidateSet:
    accent = accent.casefold().strip()
    if accent not in ACCENTS:
        raise PronunciationResolutionError(f"invalid accent: {accent!r}")
    lookup_word = normalize_source_word(
        source_word or request.source_word or request.word
    )
    request_pos = _normalize_pos(request.pos)
    by_fingerprint: dict[str, PronunciationCandidate] = {}

    for record in source_records:
        source = str(record.get("source") or "").casefold()
        if source not in SOURCE_RANK:
            continue
        parent_word = normalize_source_word(record.get("word"))
        if parent_word != lookup_word:
            continue
        if "pronunciations" not in record:
            raise PronunciationResolutionError(
                f"source record {source}:{parent_word} is missing v3 pronunciations"
            )
        entries = record.get("pronunciations")
        if not isinstance(entries, list):
            raise PronunciationResolutionError(
                f"source record {source}:{parent_word} has invalid pronunciations"
            )
        for entry in entries:
            if not isinstance(entry, dict):
                raise PronunciationResolutionError(
                    f"source record {source}:{parent_word} has invalid pronunciation entry"
                )
            payload = entry.get(accent)
            if not isinstance(payload, dict):
                continue
            ipa = normalize_ipa(payload.get("ipa"))
            audio_url = str(payload.get("audio_url") or "").strip()
            if not ipa or not audio_url:
                continue
            candidate_pos = _normalize_pos(entry.get("pos") or [])
            pos_rank = _pos_rank(request_pos, candidate_pos)
            if pos_rank is None:
                continue
            dictionary_rank = entry.get("dictionary_rank")
            entry_index = entry.get("entry_index")
            if (
                isinstance(dictionary_rank, bool)
                or not isinstance(dictionary_rank, int)
                or dictionary_rank < 0
                or isinstance(entry_index, bool)
                or not isinstance(entry_index, int)
                or entry_index < 1
            ):
                raise PronunciationResolutionError(
                    f"source record {source}:{parent_word} has invalid pronunciation rank"
                )
            headword = normalize_source_word(entry.get("headword"))
            dictionary_id = str(entry.get("dictionary_id") or "").strip()
            entry_id = str(entry.get("entry_id") or "").strip()
            if not dictionary_id or not entry_id:
                raise PronunciationResolutionError(
                    f"source record {source}:{parent_word} has invalid entry identity"
                )
            headword_rank = 0 if headword == lookup_word else 1
            candidate = PronunciationCandidate(
                source=source,
                parent_word=parent_word,
                accent=accent,
                ipa=ipa,
                audio_url=audio_url,
                source_file=str(entry.get("source_file") or ""),
                dictionary_id=dictionary_id,
                dictionary_rank=dictionary_rank,
                entry_id=entry_id,
                entry_index=entry_index,
                headword=headword,
                pos=candidate_pos,
                tier=(SOURCE_RANK[source], dictionary_rank, headword_rank, pos_rank),
            )
            previous = by_fingerprint.get(candidate.fingerprint)
            if previous is None or (
                candidate.tier,
                candidate.source_file,
                candidate.entry_index,
                candidate.entry_id,
            ) < (
                previous.tier,
                previous.source_file,
                previous.entry_index,
                previous.entry_id,
            ):
                by_fingerprint[candidate.fingerprint] = candidate

    candidates = tuple(sorted(
        by_fingerprint.values(),
        key=lambda item: (
            item.tier,
            item.fingerprint,
            item.source_file,
            item.entry_index,
            item.entry_id,
        ),
    ))
    best_tier = candidates[0].tier if candidates else None
    best_candidates = tuple(
        item for item in candidates if item.tier == best_tier
    )
    set_fingerprint = _canonical_sha256({
        "schema_version": 2,
        "guid": request.guid,
        "source_word": lookup_word,
        "accent": accent,
        "pos": list(request_pos),
        "candidates": [
            {"selection_fingerprint": item.fingerprint, "tier": list(item.tier)}
            for item in candidates
        ],
    })
    return PronunciationCandidateSet(
        source_word=lookup_word,
        accent=accent,
        candidates=candidates,
        best_candidates=best_candidates,
        fingerprint=set_fingerprint,
    )


def select_pronunciation(
    request: PronunciationRequest,
    accent: str,
    source_records: Iterable[dict],
    lock: Mapping[str, object] | None = None,
) -> PronunciationSelection:
    if (
        lock is not None
        and lock.get("schema_version") != PRONUNCIATION_LOCK_SCHEMA_VERSION
    ):
        raise PronunciationResolutionError("invalid pronunciation lock schema")
    lock_source_word = None
    if lock is not None and "source_word" in lock:
        lock_source_word = str(lock.get("source_word") or "").strip()
        if not lock_source_word:
            raise PronunciationResolutionError("pronunciation lock source_word is empty")
    candidate_set = build_candidate_set(
        request,
        accent,
        source_records,
        source_word=lock_source_word,
    )

    if lock is not None:
        lock_guid = str(lock.get("guid") or "")
        lock_accent = str(lock.get("accent") or "").casefold()
        if lock_guid != request.guid or lock_accent != candidate_set.accent:
            raise PronunciationResolutionError(
                "pronunciation lock does not match request GUID/accent"
            )
        if normalize_source_word(lock.get("word")) != normalize_source_word(
            request.word
        ):
            raise PronunciationResolutionError(
                "pronunciation lock word does not match request"
            )
        if _normalize_pos(str(lock.get("card_pos") or "")) != _normalize_pos(
            request.pos
        ):
            raise PronunciationResolutionError(
                "pronunciation lock card_pos does not match request"
            )
        decision = str(lock.get("decision") or "")
        if decision not in LOCK_DECISIONS:
            raise PronunciationResolutionError(
                f"invalid pronunciation lock decision: {decision!r}"
            )
        expected_set = str(lock.get("candidate_set_fingerprint") or "")
        if expected_set != candidate_set.fingerprint:
            raise PronunciationResolutionError(
                "stale pronunciation lock candidate-set fingerprint"
            )
        if decision == "no_pronunciation":
            if "selection_fingerprint" in lock or any(
                field in lock for field in _SELECTED_LOCK_FIELDS
            ):
                raise PronunciationResolutionError(
                    "no_pronunciation lock has selected candidate fields"
                )
            if candidate_set.candidates:
                raise PronunciationResolutionError(
                    "no_pronunciation lock cannot suppress a complete candidate"
                )
            return PronunciationSelection(
                accent=candidate_set.accent,
                candidate_set_fingerprint=candidate_set.fingerprint,
                candidate=None,
                decision=decision,
                automatic=False,
            )
        selected_fingerprint = str(lock.get("selection_fingerprint") or "")
        selected = next(
            (
                item
                for item in candidate_set.best_candidates
                if item.fingerprint == selected_fingerprint
            ),
            None,
        )
        if selected is None:
            if any(
                item.fingerprint == selected_fingerprint
                for item in candidate_set.candidates
            ):
                raise PronunciationResolutionError(
                    "pronunciation lock cannot bypass the best tier"
                )
            raise PronunciationResolutionError(
                "stale pronunciation lock selection fingerprint"
            )
        _validate_selected_lock_candidate(lock, selected)
        return PronunciationSelection(
            accent=candidate_set.accent,
            candidate_set_fingerprint=candidate_set.fingerprint,
            candidate=selected,
            decision=decision,
            automatic=False,
        )

    if not candidate_set.best_candidates:
        raise PronunciationResolutionError(
            f"missing complete pronunciation for {request.guid}:{candidate_set.accent}"
        )
    if len(candidate_set.best_candidates) != 1:
        raise PronunciationResolutionError(
            "ambiguous pronunciation for "
            f"{request.guid}:{candidate_set.accent}; "
            f"candidate_set_fingerprint={candidate_set.fingerprint}"
        )
    return PronunciationSelection(
        accent=candidate_set.accent,
        candidate_set_fingerprint=candidate_set.fingerprint,
        candidate=candidate_set.best_candidates[0],
        decision="select",
        automatic=True,
    )


_SELECTED_LOCK_FIELDS = (
    "selected_source",
    "selected_dictionary_id",
    "selected_entry_id",
    "selected_headword",
    "selected_pos",
    "selected_ipa",
    "selected_audio_url",
)
_LOCK_REVIEW_FIELDS = (
    "word",
    "card_pos",
    "review_reason",
    "reviewer",
    "reviewed_at",
)


def _validate_selected_lock_candidate(
    lock: Mapping[str, object],
    candidate: PronunciationCandidate,
) -> None:
    expected = selected_candidate_metadata(candidate)
    actual = {
        "selected_source": str(lock.get("selected_source") or "").casefold().strip(),
        "selected_dictionary_id": str(
            lock.get("selected_dictionary_id") or ""
        ).strip(),
        "selected_entry_id": str(lock.get("selected_entry_id") or "").strip(),
        "selected_headword": normalize_source_word(lock.get("selected_headword")),
        "selected_pos": list(
            _normalize_pos(lock.get("selected_pos"))
            if isinstance(lock.get("selected_pos"), (str, list, tuple))
            else ()
        ),
        "selected_ipa": normalize_ipa(lock.get("selected_ipa")),
        "selected_audio_url": str(lock.get("selected_audio_url") or "").strip(),
    }
    for field in _SELECTED_LOCK_FIELDS:
        if actual[field] != expected[field]:
            raise PronunciationResolutionError(
                f"stale pronunciation lock {field}"
            )


def selected_candidate_metadata(
    candidate: PronunciationCandidate,
) -> dict[str, object]:
    return {
        "selected_source": candidate.source,
        "selected_dictionary_id": candidate.dictionary_id,
        "selected_entry_id": candidate.entry_id,
        "selected_headword": candidate.headword,
        "selected_pos": list(candidate.pos),
        "selected_ipa": candidate.ipa,
        "selected_audio_url": candidate.audio_url,
    }


def index_pronunciation_locks(
    rows: Iterable[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    result: dict[tuple[str, str], Mapping[str, object]] = {}
    for row_number, row in enumerate(rows, start=1):
        if row.get("schema_version") != PRONUNCIATION_LOCK_SCHEMA_VERSION:
            raise PronunciationResolutionError(
                f"invalid pronunciation lock schema at row {row_number}"
            )
        guid = str(row.get("guid") or "")
        accent = str(row.get("accent") or "").casefold()
        decision = str(row.get("decision") or "")
        fingerprint = str(row.get("candidate_set_fingerprint") or "")
        if not guid or accent not in ACCENTS or decision not in LOCK_DECISIONS:
            raise PronunciationResolutionError(
                f"invalid pronunciation lock at row {row_number}"
            )
        for field in _LOCK_REVIEW_FIELDS:
            if not isinstance(row.get(field), str) or not str(row[field]).strip():
                raise PronunciationResolutionError(
                    f"invalid pronunciation lock {field} at row {row_number}"
                )
        reviewed_at = str(row["reviewed_at"])
        try:
            valid_reviewed_at = (
                bool(_ISO_DATE_RE.fullmatch(reviewed_at))
                and date.fromisoformat(reviewed_at).isoformat() == reviewed_at
            )
        except ValueError:
            valid_reviewed_at = False
        if not valid_reviewed_at:
            raise PronunciationResolutionError(
                f"invalid pronunciation lock reviewed_at at row {row_number}"
            )
        if not _HEX_SHA256_RE.fullmatch(fingerprint):
            raise PronunciationResolutionError(
                f"invalid candidate-set fingerprint at row {row_number}"
            )
        if decision == "select" and not _HEX_SHA256_RE.fullmatch(
            str(row.get("selection_fingerprint") or "")
        ):
            raise PronunciationResolutionError(
                f"invalid selection fingerprint at row {row_number}"
            )
        if decision == "select":
            missing = [field for field in _SELECTED_LOCK_FIELDS if field not in row]
            if missing:
                raise PronunciationResolutionError(
                    f"missing selected pronunciation fields at row {row_number}: "
                    + ",".join(missing)
                )
            if not isinstance(row.get("selected_pos"), list):
                raise PronunciationResolutionError(
                    f"invalid selected_pos at row {row_number}"
                )
            for field in (
                "selected_source",
                "selected_dictionary_id",
                "selected_entry_id",
                "selected_ipa",
                "selected_audio_url",
            ):
                if not isinstance(row.get(field), str) or not str(row[field]).strip():
                    raise PronunciationResolutionError(
                        f"invalid {field} at row {row_number}"
                    )
            if row.get("selected_source") not in SOURCE_RANK:
                raise PronunciationResolutionError(
                    f"invalid selected_source at row {row_number}"
                )
            if not isinstance(row.get("selected_headword"), str):
                raise PronunciationResolutionError(
                    f"invalid selected_headword at row {row_number}"
                )
        elif "selection_fingerprint" in row or any(
            field in row for field in _SELECTED_LOCK_FIELDS
        ):
            raise PronunciationResolutionError(
                f"no_pronunciation lock has selected candidate fields at row {row_number}"
            )
        key = (guid, accent)
        if key in result:
            raise PronunciationResolutionError(
                f"duplicate pronunciation lock for {guid}:{accent}"
            )
        result[key] = row
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def index_headword_audio_manifest(
    rows: Iterable[Mapping[str, object]],
    *,
    audio_dir: Path | None = None,
) -> dict[str, HeadwordAudioManifestEntry]:
    result: dict[str, HeadwordAudioManifestEntry] = {}
    filename_owners: dict[str, HeadwordAudioManifestEntry] = {}
    media_owners: dict[str, HeadwordAudioManifestEntry] = {}
    for row_number, row in enumerate(rows, start=1):
        if row.get("schema_version") != HEADWORD_AUDIO_MANIFEST_SCHEMA_VERSION:
            raise PronunciationResolutionError(
                f"invalid headword audio manifest schema at row {row_number}"
            )
        source = str(row.get("source") or "").casefold()
        parent_word = normalize_source_word(row.get("parent_word"))
        dictionary_id = str(row.get("dictionary_id") or "").strip()
        entry_id = str(row.get("entry_id") or "").strip()
        headword = normalize_source_word(row.get("headword"))
        raw_pos = row.get("pos")
        if not isinstance(raw_pos, list):
            raise PronunciationResolutionError(
                f"invalid headword audio manifest POS at row {row_number}"
            )
        pos = _normalize_pos(raw_pos)
        accent = str(row.get("accent") or "").casefold()
        ipa = normalize_ipa(row.get("ipa"))
        audio_url = str(row.get("audio_url") or "").strip()
        if not dictionary_id or not entry_id or not ipa or not audio_url:
            raise PronunciationResolutionError(
                f"incomplete headword audio manifest row {row_number}"
            )
        fingerprint = str(row.get("selection_fingerprint") or "")
        media_fingerprint = str(row.get("media_fingerprint") or "")
        expected_media_fingerprint = pronunciation_media_fingerprint(
            source, parent_word, accent, ipa, audio_url
        )
        if media_fingerprint != expected_media_fingerprint:
            raise PronunciationResolutionError(
                f"stale headword audio media fingerprint at row {row_number}"
            )
        expected = selection_fingerprint(
            source,
            parent_word,
            accent,
            ipa,
            audio_url,
            dictionary_id=dictionary_id,
            entry_id=entry_id,
            headword=headword,
            pos=pos,
        )
        if fingerprint != expected:
            raise PronunciationResolutionError(
                f"stale headword audio manifest fingerprint at row {row_number}"
            )
        filename = str(row.get("filename") or "")
        if (
            not filename
            or Path(filename).name != filename
            or not filename.casefold().endswith(".mp3")
        ):
            raise PronunciationResolutionError(
                f"invalid headword audio filename at row {row_number}"
            )
        sha256 = str(row.get("sha256") or "").casefold()
        byte_count = row.get("byte_count")
        if (
            not _HEX_SHA256_RE.fullmatch(sha256)
            or isinstance(byte_count, bool)
            or not isinstance(byte_count, int)
            or byte_count < 0
        ):
            raise PronunciationResolutionError(
                f"invalid headword audio digest at row {row_number}"
            )
        if fingerprint in result:
            raise PronunciationResolutionError(
                f"duplicate headword audio fingerprint: {fingerprint}"
            )
        entry = HeadwordAudioManifestEntry(
            selection_fingerprint=fingerprint,
            media_fingerprint=media_fingerprint,
            source=source,
            parent_word=parent_word,
            dictionary_id=dictionary_id,
            entry_id=entry_id,
            headword=headword,
            pos=pos,
            accent=accent,
            ipa=ipa,
            audio_url=audio_url,
            filename=filename,
            sha256=sha256,
            byte_count=byte_count,
        )
        filename_key = filename.casefold()
        previous_entry = filename_owners.get(filename_key)
        if previous_entry is not None and (
            previous_entry.media_fingerprint,
            previous_entry.filename,
            previous_entry.sha256,
            previous_entry.byte_count,
        ) != (
            entry.media_fingerprint,
            entry.filename,
            entry.sha256,
            entry.byte_count,
        ):
            raise PronunciationResolutionError(
                f"headword audio filename collision: {filename}"
            )
        previous_media = media_owners.get(media_fingerprint)
        if previous_media is not None and (
            previous_media.filename,
            previous_media.sha256,
            previous_media.byte_count,
        ) != (
            entry.filename,
            entry.sha256,
            entry.byte_count,
        ):
            raise PronunciationResolutionError(
                "headword audio media fingerprint has conflicting bytes: "
                f"{media_fingerprint}"
            )
        if audio_dir is not None:
            media_path = Path(audio_dir) / filename
            if not media_path.is_file():
                raise PronunciationResolutionError(
                    f"headword audio file missing: {filename}"
                )
            if media_path.stat().st_size != byte_count or _sha256_file(media_path) != sha256:
                raise PronunciationResolutionError(
                    f"headword audio file is stale: {filename}"
                )
        result[fingerprint] = entry
        filename_owners[filename_key] = entry
        media_owners[media_fingerprint] = entry
    return result


def bind_headword_audio_manifest(
    selection: PronunciationSelection,
    manifest: Mapping[str, HeadwordAudioManifestEntry],
) -> ResolvedPronunciation:
    if selection.no_pronunciation:
        return ResolvedPronunciation(
            accent=selection.accent,
            source="",
            ipa="",
            audio_url="",
            selection_fingerprint="",
            media_filename="",
            media_sha256="",
            no_pronunciation=True,
        )
    candidate = selection.candidate
    if candidate is None:
        raise PronunciationResolutionError("selected pronunciation has no candidate")
    entry = manifest.get(candidate.fingerprint)
    if entry is None:
        raise PronunciationResolutionError(
            f"headword audio manifest is missing {candidate.fingerprint}"
        )
    if (
        entry.source != candidate.source
        or entry.parent_word != candidate.parent_word
        or entry.dictionary_id != candidate.dictionary_id
        or entry.entry_id != candidate.entry_id
        or entry.headword != candidate.headword
        or entry.pos != candidate.pos
        or entry.accent != candidate.accent
        or entry.ipa != candidate.ipa
        or entry.audio_url != candidate.audio_url
    ):
        raise PronunciationResolutionError(
            f"headword audio manifest is stale for {candidate.fingerprint}"
        )
    return ResolvedPronunciation(
        accent=candidate.accent,
        source=candidate.source,
        ipa=candidate.ipa,
        audio_url=candidate.audio_url,
        selection_fingerprint=candidate.fingerprint,
        media_filename=entry.filename,
        media_sha256=entry.sha256,
    )
