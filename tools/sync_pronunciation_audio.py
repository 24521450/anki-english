"""Resolve and synchronize all active headword pronunciation media."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Iterable, Mapping
from urllib.parse import unquote, urlsplit

import aiohttp

from src.deck_builder.pronunciation_resolution import (
    HeadwordAudioManifestEntry,
    PronunciationCandidate,
    PronunciationRequest,
    PronunciationResolutionError,
    PronunciationSelection,
    index_headword_audio_manifest,
    index_pronunciation_records,
    index_pronunciation_locks,
    normalize_source_word,
    select_pronunciation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAMBRIDGE_BASE_URL = "https://dictionary.cambridge.org"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
DEFAULT_DOWNLOAD_CONCURRENCY = 8
DEFAULT_REQUESTS_PER_SECOND = 12.0
MAX_AUDIO_BYTES = 2 * 1024 * 1024
_DOWNLOAD_CHUNK_SIZE = 64 * 1024
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9]+")
_OFFICIAL_AUDIO_HOSTS = {
    "cambridge": "dictionary.cambridge.org",
    "oxford": "www.oxfordlearnersdictionaries.com",
}
_OFFICIAL_AUDIO_PATH_PREFIX = "/media/english/"


@dataclass(frozen=True)
class SyncItem:
    candidate: PronunciationCandidate
    filename: str
    existing: HeadwordAudioManifestEntry | None
    needs_download: bool


@dataclass(frozen=True)
class SyncPlan:
    items: tuple[SyncItem, ...]
    no_pronunciation_count: int
    active_card_count: int
    attested_existing_count: int = 0


class _RequestRateLimiter:
    """Global start-rate/cooldown gate shared by every download task."""

    def __init__(self, requests_per_second: float):
        if requests_per_second <= 0:
            raise PronunciationResolutionError(
                "requests per second must be positive"
            )
        self._interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._next_start = 0.0
        self._blocked_until = 0.0

    async def wait(self) -> None:
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            target = max(now, self._next_start, self._blocked_until)
            if target > now:
                await asyncio.sleep(target - now)
            self._next_start = target + self._interval

    async def penalize(self, seconds: float) -> None:
        loop = asyncio.get_running_loop()
        async with self._lock:
            self._blocked_until = max(
                self._blocked_until,
                loop.time() + max(0.0, seconds),
            )


def load_jsonl(path: Path, *, missing_ok: bool = False) -> list[dict]:
    if not path.is_file():
        if missing_ok:
            return []
        raise PronunciationResolutionError(f"required JSONL not found: {path}")
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PronunciationResolutionError(
                    f"invalid JSONL {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise PronunciationResolutionError(
                    f"invalid JSONL object {path}:{line_number}"
                )
            rows.append(row)
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_file_matches(
    entry: HeadwordAudioManifestEntry,
    audio_dir: Path,
) -> bool:
    path = audio_dir / entry.filename
    return (
        path.is_file()
        and path.stat().st_size == entry.byte_count
        and _sha256_file(path) == entry.sha256
    )


def _rebind_manifest_entry(
    candidate: PronunciationCandidate,
    entry: HeadwordAudioManifestEntry,
) -> HeadwordAudioManifestEntry:
    """Bind an existing exact media attestation to a new entry identity."""
    if candidate.media_fingerprint != entry.media_fingerprint:
        raise PronunciationResolutionError(
            "cannot rebind a different pronunciation media fingerprint"
        )
    return HeadwordAudioManifestEntry(
        selection_fingerprint=candidate.fingerprint,
        media_fingerprint=candidate.media_fingerprint,
        source=candidate.source,
        parent_word=candidate.parent_word,
        dictionary_id=candidate.dictionary_id,
        entry_id=candidate.entry_id,
        headword=candidate.headword,
        pos=candidate.pos,
        accent=candidate.accent,
        ipa=candidate.ipa,
        audio_url=candidate.audio_url,
        filename=entry.filename,
        sha256=entry.sha256,
        byte_count=entry.byte_count,
    )


def _slug(word: str) -> str:
    slug = _SAFE_SLUG_RE.sub("_", normalize_source_word(word)).strip("_")
    return slug or "headword"


def allocate_media_filename(
    candidate: PronunciationCandidate,
    used_filenames: Mapping[str, str] | set[str],
) -> str:
    """Allocate a deterministic target name; never infer selection from a name."""
    used = {str(filename).casefold() for filename in used_filenames}
    base = f"{candidate.source}_{candidate.accent}_{_slug(candidate.parent_word)}"
    legacy_name = f"{base}.mp3"
    if legacy_name.casefold() not in used:
        return legacy_name
    digest_name = f"{base}_{candidate.fingerprint[:12]}.mp3"
    if digest_name.casefold() not in used:
        return digest_name
    return f"{base}_{candidate.fingerprint}.mp3"


def build_sync_plan(
    card_rows: Iterable[dict],
    source_records: Iterable[dict],
    lock_rows: Iterable[dict],
    manifest_rows: Iterable[dict],
    audio_dir: Path,
    *,
    attest_existing: bool = False,
) -> SyncPlan:
    records = list(source_records)
    records_by_word = index_pronunciation_records(records)
    top_level_audio: dict[tuple[str, str, str], set[str]] = {}
    if attest_existing:
        # Existing bytes may be adopted only as a migration attestation when
        # the selected candidate is the exact top-level audio advertised by
        # its source record.  Candidate selection still comes from the
        # entry-scoped resolver above; a filename never selects a candidate.
        for record in records:
            source = str(record.get("source") or "").casefold()
            word = normalize_source_word(record.get("word"))
            audio = record.get("audio")
            if source not in {"cambridge", "oxford"} or not word:
                continue
            if not isinstance(audio, Mapping):
                continue
            for accent in ("uk", "us"):
                url = str(audio.get(accent) or "").strip()
                if url:
                    top_level_audio.setdefault(
                        (source, accent, word), set()
                    ).add(url)
    locks = index_pronunciation_locks(lock_rows)
    manifest = index_headword_audio_manifest(manifest_rows)
    manifest_by_media = {
        entry.media_fingerprint: entry for entry in manifest.values()
    }
    active_cards = sorted(
        (row for row in card_rows if row.get("status") == "active"),
        key=lambda row: str(row.get("guid") or ""),
    )
    selected: dict[str, PronunciationSelection] = {}
    no_pronunciation_count = 0
    for row in active_cards:
        guid = str(row.get("guid") or "")
        word = str(row.get("word") or "")
        pos = str(row.get("pos") or "")
        if not guid or not word:
            raise PronunciationResolutionError(
                "active Card Registry row is missing guid/word"
            )
        request = PronunciationRequest(guid=guid, word=word, pos=pos)
        for accent in ("uk", "us"):
            lock = locks.get((guid, accent))
            lookup_word = (
                str(lock.get("source_word") or "")
                if lock is not None and "source_word" in lock
                else word
            )
            selection = select_pronunciation(
                request,
                accent,
                records_by_word.get(normalize_source_word(lookup_word), ()),
                lock,
            )
            if selection.no_pronunciation:
                no_pronunciation_count += 1
                continue
            candidate = selection.candidate
            assert candidate is not None
            selected.setdefault(candidate.fingerprint, selection)

    used_filenames: dict[str, str] = {
        entry.filename: fingerprint for fingerprint, entry in manifest.items()
    }
    media_filenames = {
        entry.media_fingerprint: entry.filename for entry in manifest.values()
    }

    items: list[SyncItem] = []
    attested_existing_count = 0
    for fingerprint, selection in sorted(selected.items()):
        candidate = selection.candidate
        assert candidate is not None
        existing = manifest.get(fingerprint)
        if existing is None:
            media_owner = manifest_by_media.get(candidate.media_fingerprint)
            if media_owner is not None:
                existing = _rebind_manifest_entry(candidate, media_owner)
        if existing is not None:
            filename = existing.filename
        elif candidate.media_fingerprint in media_filenames:
            filename = media_filenames[candidate.media_fingerprint]
        else:
            filename = allocate_media_filename(candidate, used_filenames)
            used_filenames[filename] = fingerprint
            media_filenames[candidate.media_fingerprint] = filename
            if attest_existing and candidate.audio_url in top_level_audio.get(
                (candidate.source, candidate.accent, candidate.parent_word),
                set(),
            ):
                existing_path = audio_dir / filename
                if existing_path.is_file():
                    content = existing_path.read_bytes()
                    if not _valid_mp3(content):
                        raise PronunciationResolutionError(
                            "existing attestation file is not a valid MP3: "
                            f"{filename}"
                        )
                    existing = _entry_for_bytes(candidate, filename, content)
                    attested_existing_count += 1
        if existing is not None:
            manifest_by_media.setdefault(candidate.media_fingerprint, existing)
        items.append(SyncItem(
            candidate=candidate,
            filename=filename,
            existing=existing,
            needs_download=(
                existing is None
                or not _manifest_file_matches(existing, audio_dir)
            ),
        ))
    return SyncPlan(
        items=tuple(items),
        no_pronunciation_count=no_pronunciation_count,
        active_card_count=len(active_cards),
        attested_existing_count=attested_existing_count,
    )


def _absolute_audio_url(candidate: PronunciationCandidate) -> str:
    source = str(candidate.source or "").casefold()
    expected_host = _OFFICIAL_AUDIO_HOSTS.get(source)
    if expected_host is None:
        raise PronunciationResolutionError(
            f"unsupported pronunciation audio source: {candidate.source!r}"
        )

    raw_url = str(candidate.audio_url or "").strip()
    if not raw_url:
        raise PronunciationResolutionError(
            f"invalid {source} audio URL: {candidate.audio_url!r}"
        )

    # Cambridge source records use root-relative media URLs.  Resolve those
    # against the official origin; protocol-relative URLs are deliberately not
    # accepted because they could redirect the downloader to an arbitrary host.
    if raw_url.startswith("/") and not raw_url.startswith("//"):
        if source != "cambridge":
            raise PronunciationResolutionError(
                f"relative {source} audio URL is not allowed: {raw_url!r}"
            )
        absolute_url = CAMBRIDGE_BASE_URL + raw_url
    else:
        absolute_url = raw_url

    try:
        parsed = urlsplit(absolute_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise PronunciationResolutionError(
            f"invalid {source} audio URL: {raw_url!r}"
        ) from exc
    if (
        parsed.scheme.casefold() != "https"
        or hostname is None
        or hostname.casefold() != expected_host
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise PronunciationResolutionError(
            f"non-official {source} audio URL: {raw_url!r}"
        )

    path = unquote(parsed.path)
    path_parts = path.split("/")
    if (
        not path.startswith(_OFFICIAL_AUDIO_PATH_PREFIX)
        or any(part in {".", ".."} for part in path_parts)
        or "\\" in path
        or not path.casefold().endswith(".mp3")
    ):
        raise PronunciationResolutionError(
            f"non-official {source} audio path: {raw_url!r}"
        )
    return absolute_url


def _valid_mp3(content: bytes) -> bool:
    if len(content) < 1000:
        return False
    return content.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"))


async def _read_bounded_response(response: aiohttp.ClientResponse) -> bytes:
    """Read an audio response without allowing an unbounded body allocation."""
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except (TypeError, ValueError) as exc:
            raise PronunciationResolutionError(
                "audio response has an invalid Content-Length"
            ) from exc
        if declared_length < 0 or declared_length > MAX_AUDIO_BYTES:
            raise PronunciationResolutionError(
                "audio response exceeds maximum size "
                f"({MAX_AUDIO_BYTES} bytes)"
            )

    payload = bytearray()
    async for chunk in response.content.iter_chunked(_DOWNLOAD_CHUNK_SIZE):
        if len(payload) + len(chunk) > MAX_AUDIO_BYTES:
            raise PronunciationResolutionError(
                "audio response exceeds maximum size "
                f"({MAX_AUDIO_BYTES} bytes)"
            )
        payload.extend(chunk)
    return bytes(payload)


async def _download_audio(
    candidate: PronunciationCandidate,
    session: aiohttp.ClientSession,
    rate_limiter: _RequestRateLimiter,
) -> bytes:
    url = _absolute_audio_url(candidate)
    if candidate.source == "cambridge":
        referer = "https://dictionary.cambridge.org/dictionary/english/"
    else:
        referer = "https://www.oxfordlearnersdictionaries.com/definition/english/"
    headers = {
        "Accept": "audio/ogg,audio/mpeg,audio/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Range": "bytes=0-",
        "Referer": referer,
        "Sec-Fetch-Dest": "audio",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
    }
    backoff_seconds = 2
    for attempt in range(8):
        await rate_limiter.wait()
        try:
            async with session.get(
                url,
                headers=headers,
                allow_redirects=False,
            ) as response:
                status = response.status
                retry_after_header = response.headers.get("Retry-After")
                content = (
                    await _read_bounded_response(response)
                    if status in {200, 206}
                    else b""
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt == 7:
                raise PronunciationResolutionError(
                    f"failed to download {url}: {exc}"
                ) from exc
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 60)
            continue
        if (status == 429 or status >= 500) and attempt < 7:
            try:
                retry_after = float(retry_after_header or 0)
            except ValueError:
                retry_after = 0
            cooldown = max(retry_after, 30 if status == 429 else backoff_seconds)
            await rate_limiter.penalize(cooldown)
            backoff_seconds = min(backoff_seconds * 2, 60)
            continue
        if status not in {200, 206}:
            raise PronunciationResolutionError(
                f"failed to download {url}: HTTP {status}"
            )
        if not _valid_mp3(content):
            raise PronunciationResolutionError(
                f"downloaded invalid MP3 from {url}"
            )
        return content
    raise PronunciationResolutionError(f"failed to download {url}")


def _entry_for_bytes(
    candidate: PronunciationCandidate,
    filename: str,
    content: bytes,
) -> HeadwordAudioManifestEntry:
    return _entry_for_attestation(
        candidate,
        filename,
        sha256=hashlib.sha256(content).hexdigest(),
        byte_count=len(content),
    )


def _entry_for_attestation(
    candidate: PronunciationCandidate,
    filename: str,
    *,
    sha256: str,
    byte_count: int,
) -> HeadwordAudioManifestEntry:
    return HeadwordAudioManifestEntry(
        selection_fingerprint=candidate.fingerprint,
        media_fingerprint=candidate.media_fingerprint,
        source=candidate.source,
        parent_word=candidate.parent_word,
        dictionary_id=candidate.dictionary_id,
        entry_id=candidate.entry_id,
        headword=candidate.headword,
        pos=candidate.pos,
        accent=candidate.accent,
        ipa=candidate.ipa,
        audio_url=candidate.audio_url,
        filename=filename,
        sha256=sha256,
        byte_count=byte_count,
    )


def _canonical_manifest_text(entries: Iterable[HeadwordAudioManifestEntry]) -> str:
    return "".join(
        json.dumps(
            entry.to_row(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        for entry in sorted(entries, key=lambda item: item.selection_fingerprint)
    )


async def _stage_download_item(
    item: SyncItem,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    rate_limiter: _RequestRateLimiter,
    staging_dir: Path,
    audio_dir: Path,
) -> tuple[HeadwordAudioManifestEntry, tuple[Path | None, Path]]:
    async with semaphore:
        content = await _download_audio(item.candidate, session, rate_limiter)
    temporary_path = staging_dir / item.filename
    with temporary_path.open("wb") as handle:
        handle.write(content)
    entry = _entry_for_bytes(item.candidate, item.filename, content)
    return entry, (temporary_path, audio_dir / item.filename)


async def _stage_downloads(
    items: Iterable[SyncItem],
    staging_dir: Path,
    audio_dir: Path,
    concurrency: int,
    requests_per_second: float,
) -> list[tuple[HeadwordAudioManifestEntry, tuple[Path | None, Path]]]:
    semaphore = asyncio.Semaphore(concurrency)
    rate_limiter = _RequestRateLimiter(requests_per_second)
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(limit=concurrency)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "identity",
    }
    async with aiohttp.ClientSession(
        connector=connector,
        headers=headers,
        timeout=timeout,
    ) as session:
        tasks = [
            asyncio.create_task(
                _stage_download_item(
                    item,
                    session,
                    semaphore,
                    rate_limiter,
                    staging_dir,
                    audio_dir,
                )
            )
            for item in items
        ]
        try:
            return list(await asyncio.gather(*tasks))
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise


def apply_sync_plan(
    plan: SyncPlan,
    audio_dir: Path,
    manifest_path: Path,
    *,
    concurrency: int = DEFAULT_DOWNLOAD_CONCURRENCY,
    requests_per_second: float = DEFAULT_REQUESTS_PER_SECOND,
    resume_staging_dir: Path | None = None,
) -> None:
    if concurrency < 1:
        raise PronunciationResolutionError("download concurrency must be positive")
    audio_dir.mkdir(parents=True, exist_ok=True)
    entries = [
        item.existing
        for item in plan.items
        if not item.needs_download and item.existing is not None
    ]
    pending_items = [item for item in plan.items if item.needs_download]
    download_groups: dict[str, list[SyncItem]] = {}
    for item in pending_items:
        download_groups.setdefault(
            item.candidate.media_fingerprint, []
        ).append(item)
    for media_fingerprint, group in download_groups.items():
        filenames = {item.filename for item in group}
        if len(filenames) != 1:
            raise PronunciationResolutionError(
                "one pronunciation media fingerprint planned multiple filenames: "
                f"{media_fingerprint}"
            )
    pending = [group[0] for group in download_groups.values()]
    staged: list[tuple[HeadwordAudioManifestEntry, tuple[Path | None, Path]]] = []
    if resume_staging_dir is not None:
        resume_staging_dir = Path(resume_staging_dir)
        if not resume_staging_dir.is_dir():
            raise PronunciationResolutionError(
                f"resume staging directory not found: {resume_staging_dir}"
            )
        remaining: list[SyncItem] = []
        for item in pending:
            staged_path = resume_staging_dir / item.filename
            if not staged_path.exists():
                # A previous process may have completed the media move but
                # been interrupted before writing the manifest.  In an
                # explicit resume, recover that destination only after
                # validating its bytes against the current selected item.
                destination = audio_dir / item.filename
                if destination.is_file():
                    content = destination.read_bytes()
                    if not _valid_mp3(content):
                        raise PronunciationResolutionError(
                            "recovered destination is not a valid MP3: "
                            f"{destination}"
                        )
                    staged.append((
                        _entry_for_bytes(item.candidate, item.filename, content),
                        (None, destination),
                    ))
                else:
                    remaining.append(item)
                continue
            if not staged_path.is_file():
                raise PronunciationResolutionError(
                    f"resume staging path is not a file: {staged_path}"
                )
            content = staged_path.read_bytes()
            if not _valid_mp3(content):
                raise PronunciationResolutionError(
                    f"resume staging file is not a valid MP3: {staged_path}"
                )
            staged.append((
                _entry_for_bytes(item.candidate, item.filename, content),
                (staged_path, audio_dir / item.filename),
            ))
        pending = remaining
    with tempfile.TemporaryDirectory(
        dir=audio_dir,
        prefix=".pronunciation-sync-",
    ) as temporary_directory:
        staging_dir = Path(temporary_directory)
        downloaded = asyncio.run(
            _stage_downloads(
                pending,
                staging_dir,
                audio_dir,
                concurrency,
                requests_per_second,
            )
        )
        staged.extend(downloaded)
        for entry, _paths in staged:
            group = download_groups.get(entry.media_fingerprint)
            if not group:
                raise PronunciationResolutionError(
                    "downloaded pronunciation media is absent from the sync plan"
                )
            entries.extend(
                _entry_for_attestation(
                    item.candidate,
                    item.filename,
                    sha256=entry.sha256,
                    byte_count=entry.byte_count,
                )
                for item in group
            )

        # Do not expose any downloaded media until every network operation has
        # succeeded. This prevents a failed run from leaving unmanifested files.
        for _entry, (temporary_path, destination) in staged:
            if temporary_path is not None:
                os.replace(temporary_path, destination)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_text = _canonical_manifest_text(entries)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=manifest_path.parent,
        prefix=f".{manifest_path.name}.",
        suffix=".tmp",
        text=True,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(manifest_text)
        os.replace(temporary_name, manifest_path)
    except Exception:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Download media and write the manifest")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_DOWNLOAD_CONCURRENCY,
        help="Maximum concurrent audio downloads (default: 8)",
    )
    parser.add_argument(
        "--requests-per-second",
        type=float,
        default=DEFAULT_REQUESTS_PER_SECOND,
        help="Global download start-rate limit (default: 12)",
    )
    parser.add_argument(
        "--attest-existing",
        action="store_true",
        help=(
            "Adopt valid existing base-name MP3s only when the selected URL "
            "matches the source record's top-level audio (migration only)."
        ),
    )
    parser.add_argument(
        "--resume-staging",
        type=Path,
        help=(
            "Resume from a prior interrupted staging directory; filenames "
            "must match the current selection plan and contain valid MP3s."
        ),
    )
    parser.add_argument(
        "--card-registry",
        type=Path,
        default=PROJECT_ROOT / "data" / "curated" / "card_registry.jsonl",
    )
    parser.add_argument(
        "--cambridge-jsonl",
        type=Path,
        default=PROJECT_ROOT / "data" / "sources" / "cambridge.jsonl",
    )
    parser.add_argument(
        "--oxford-jsonl",
        type=Path,
        default=PROJECT_ROOT / "data" / "sources" / "oxford.jsonl",
    )
    parser.add_argument(
        "--locks",
        type=Path,
        default=PROJECT_ROOT / "data" / "curated" / "pronunciation_selection_locks.jsonl",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "data" / "sources" / "headword_audio_manifest.jsonl",
    )
    parser.add_argument("--audio-dir", type=Path, default=PROJECT_ROOT / "audio")
    args = parser.parse_args(argv)

    try:
        cards = load_jsonl(args.card_registry)
        source_records = [
            *load_jsonl(args.cambridge_jsonl),
            *load_jsonl(args.oxford_jsonl),
        ]
        locks = load_jsonl(args.locks, missing_ok=True)
        manifest = load_jsonl(args.manifest, missing_ok=True)
        plan = build_sync_plan(
            cards,
            source_records,
            locks,
            manifest,
            args.audio_dir,
            attest_existing=args.attest_existing,
        )
        download_count = sum(item.needs_download for item in plan.items)
        print(
            f"active cards={plan.active_card_count} "
            f"selected media={len(plan.items)} downloads={download_count} "
            f"no_pronunciation={plan.no_pronunciation_count} "
            f"attested_existing={plan.attested_existing_count}"
        )
        for item in plan.items:
            if item.needs_download:
                print(
                    f"[{'APPLY' if args.apply else 'DRY-RUN'}] "
                    f"{item.candidate.source}:{item.candidate.accent}:"
                    f"{item.candidate.parent_word} -> {item.filename}"
                )
        if args.apply:
            apply_sync_plan(
                plan,
                args.audio_dir,
                args.manifest,
                concurrency=args.concurrency,
                requests_per_second=args.requests_per_second,
                resume_staging_dir=args.resume_staging,
            )
    except (OSError, PronunciationResolutionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
