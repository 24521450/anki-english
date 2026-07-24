"""Plan, fetch, build, and validate Cambridge English–Vietnamese evidence."""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import aiohttp
import jsonschema

from src.config import ProjectPaths
from src.scraper.cambridge_english_vietnamese import (
    CambridgeEnglishVietnameseParseError,
    build_lookup_plan,
    parse_snapshot,
    serialize_rows,
    validate_snapshot_rows,
)

DEFAULT_CONCURRENCY = 2
DEFAULT_REQUEST_DELAY = 1.0
DEFAULT_MAX_ATTEMPTS = 8
DEFAULT_BACKOFF_BASE = 5.0
DEFAULT_BACKOFF_MAX = 180.0
MAX_RETRY_AFTER = 600.0
_CACHE_METADATA_KEYS = {
    "lookup_headword",
    "requested_url",
    "response_url",
    "http_status",
    "html_sha256",
}
_LEGACY_CACHE_METADATA_KEYS = {
    "requested_url",
    "response_url",
    "http_status",
}


class _RequestPacer:
    """Enforce one shared request cadence and shared server cooldown."""

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            delay = self._next_request_at - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_request_at = loop.time() + self.interval

    async def defer(self, delay: float) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            self._next_request_at = max(
                self._next_request_at,
                loop.time() + delay,
            )


def _retry_after_seconds(
    headers: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> float | None:
    raw = headers.get("Retry-After")
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        seconds = (retry_at - current).total_seconds()
    seconds = max(0.0, seconds)
    if seconds > MAX_RETRY_AFTER:
        raise RuntimeError(
            f"Retry-After {seconds:.1f}s exceeds operational maximum "
            f"{MAX_RETRY_AFTER:.1f}s"
        )
    return seconds


def _retry_delay(
    attempt: int,
    headers: Mapping[str, str],
    *,
    backoff_base: float,
    backoff_max: float,
) -> float:
    exponential = min(backoff_max, backoff_base * (2 ** (attempt - 1)))
    retry_after = _retry_after_seconds(headers)
    return max(exponential, retry_after or 0.0)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def build_plan(registry_path: Path) -> list[dict[str, Any]]:
    """Group every active Card Identity under its explicit normalized lookup."""
    return build_lookup_plan(_load_jsonl(registry_path))


def _cache_path(cache_dir: Path, lookup_headword: str) -> Path:
    from hashlib import sha256

    digest = sha256(lookup_headword.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"cambridge_english_vietnamese_{digest}.html"


def _metadata_path(cache_path: Path) -> Path:
    return cache_path.with_suffix(".http.json")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _cache_metadata(
    item: dict[str, Any],
    *,
    response_url: str,
    http_status: int,
    body: bytes,
) -> dict[str, Any]:
    return {
        "lookup_headword": item["lookup_headword"],
        "requested_url": item["requested_url"],
        "response_url": response_url,
        "http_status": http_status,
        "html_sha256": hashlib.sha256(body).hexdigest(),
    }


def _publish_cache_pair(
    cache_path: Path,
    item: dict[str, Any],
    *,
    response_url: str,
    http_status: int,
    body: bytes,
) -> None:
    metadata_path = _metadata_path(cache_path)
    # Metadata is invalidated first. A crash can leave an incomplete pair that
    # must be refetched, but can never expose new HTML under old metadata.
    _atomic_write(metadata_path, b'{"state":"publishing"}\n')
    _atomic_write(cache_path, body)
    metadata = _cache_metadata(
        item,
        response_url=response_url,
        http_status=http_status,
        body=body,
    )
    _atomic_write(
        metadata_path,
        (json.dumps(metadata, sort_keys=True) + "\n").encode("utf-8"),
    )


def _validate_cache_pair(
    cache_path: Path,
    item: dict[str, Any],
    *,
    allow_legacy_migration: bool,
) -> tuple[bytes, dict[str, Any]]:
    metadata_path = _metadata_path(cache_path)
    if not cache_path.exists() or not metadata_path.exists():
        raise ValueError(f"incomplete cache pair for {item['lookup_headword']!r}")
    body = cache_path.read_bytes()
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"invalid cache metadata for {item['lookup_headword']!r}"
        ) from exc
    keys = set(metadata)
    if keys == _LEGACY_CACHE_METADATA_KEYS and allow_legacy_migration:
        if (
            not isinstance(metadata["requested_url"], str)
            or metadata["requested_url"] != item["requested_url"]
        ):
            raise ValueError(
                f"legacy requested URL mismatch for {item['lookup_headword']!r}"
            )
        if not isinstance(metadata["response_url"], str):
            raise ValueError(
                f"invalid legacy response URL for {item['lookup_headword']!r}"
            )
        if type(metadata["http_status"]) is not int or metadata["http_status"] not in {
            200,
            404,
        }:
            raise ValueError(
                f"invalid legacy HTTP status for {item['lookup_headword']!r}"
            )
        # Parsing proves the legacy response URL, canonical relation, body, and
        # lookup before the unchanged body receives a cryptographic binding.
        parse_snapshot(
            body,
            lookup_headword=item["lookup_headword"],
            coverage_requests=item["coverage_requests"],
            cache_file=cache_path.name,
            response_url=str(metadata["response_url"]),
            http_status=int(metadata["http_status"]),
        )
        metadata = _cache_metadata(
            item,
            response_url=str(metadata["response_url"]),
            http_status=int(metadata["http_status"]),
            body=body,
        )
        _atomic_write(
            metadata_path,
            (json.dumps(metadata, sort_keys=True) + "\n").encode("utf-8"),
        )
    elif keys != _CACHE_METADATA_KEYS:
        raise ValueError(
            f"partial or unsupported cache metadata for "
            f"{item['lookup_headword']!r}: {sorted(keys)!r}"
        )

    if (
        not isinstance(metadata["lookup_headword"], str)
        or metadata["lookup_headword"] != item["lookup_headword"]
    ):
        raise ValueError(f"cache lookup mismatch for {item['lookup_headword']!r}")
    if (
        not isinstance(metadata["requested_url"], str)
        or metadata["requested_url"] != item["requested_url"]
    ):
        raise ValueError(
            f"cache requested URL mismatch for {item['lookup_headword']!r}"
        )
    if not isinstance(metadata["response_url"], str):
        raise ValueError(f"invalid cached response URL for {item['lookup_headword']!r}")
    if type(metadata["http_status"]) is not int or metadata["http_status"] not in {
        200,
        404,
    }:
        raise ValueError(f"invalid cached HTTP status for {item['lookup_headword']!r}")
    digest = hashlib.sha256(body).hexdigest()
    if (
        not isinstance(metadata["html_sha256"], str)
        or metadata["html_sha256"] != digest
    ):
        raise ValueError(f"cache HTML digest mismatch for {item['lookup_headword']!r}")
    parse_snapshot(
        body,
        lookup_headword=item["lookup_headword"],
        coverage_requests=item["coverage_requests"],
        cache_file=cache_path.name,
        response_url=str(metadata["response_url"]),
        http_status=int(metadata["http_status"]),
    )
    return body, metadata


async def _fetch_one(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    item: dict[str, Any],
    cache_dir: Path,
    *,
    pacer: _RequestPacer | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    backoff_max: float = DEFAULT_BACKOFF_MAX,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> str:
    cache_path = _cache_path(cache_dir, item["lookup_headword"])
    if cache_path.exists() or _metadata_path(cache_path).exists():
        try:
            _validate_cache_pair(
                cache_path,
                item,
                allow_legacy_migration=True,
            )
            return "cached"
        except (CambridgeEnglishVietnameseParseError, ValueError) as exc:
            print(
                f"refetching invalid cache pair for "
                f"{item['lookup_headword']!r}: {exc}",
                file=sys.stderr,
                flush=True,
            )
    async with semaphore:
        for attempt in range(1, max_attempts + 1):
            if pacer is not None:
                await pacer.wait()
            try:
                async with session.get(item["requested_url"]) as response:
                    body = await response.read()
                    if response.status == 429 or response.status >= 500:
                        if attempt == max_attempts:
                            raise RuntimeError(
                                f"transient HTTP {response.status} after "
                                f"{max_attempts} attempts for {item['requested_url']}"
                            )
                        delay = _retry_delay(
                            attempt,
                            getattr(response, "headers", {}),
                            backoff_base=backoff_base,
                            backoff_max=backoff_max,
                        )
                        print(
                            f"retry {attempt}/{max_attempts - 1}: HTTP "
                            f"{response.status} for {item['lookup_headword']!r}; "
                            f"waiting {delay:.1f}s",
                            file=sys.stderr,
                            flush=True,
                        )
                        if pacer is not None:
                            await pacer.defer(delay)
                        await sleep(delay)
                        continue
                    if response.status not in {200, 404}:
                        raise RuntimeError(
                            f"unexpected HTTP {response.status} for "
                            f"{item['requested_url']}"
                        )
                    # Validate response/canonical provenance before publishing.
                    parse_snapshot(
                        body,
                        lookup_headword=item["lookup_headword"],
                        coverage_requests=item["coverage_requests"],
                        cache_file=cache_path.name,
                        response_url=str(response.url),
                        http_status=response.status,
                    )
                    _publish_cache_pair(
                        cache_path,
                        item,
                        response_url=str(response.url),
                        http_status=response.status,
                        body=body,
                    )
                    return "fetched"
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == max_attempts:
                    raise RuntimeError(
                        f"transient fetch failure after {max_attempts} attempts "
                        f"for {item['requested_url']}: {exc}"
                    ) from exc
                delay = min(backoff_max, backoff_base * (2 ** (attempt - 1)))
                print(
                    f"retry {attempt}/{max_attempts - 1}: {type(exc).__name__} "
                    f"for {item['lookup_headword']!r}; waiting {delay:.1f}s",
                    file=sys.stderr,
                    flush=True,
                )
                if pacer is not None:
                    await pacer.defer(delay)
                await sleep(delay)
        raise AssertionError("unreachable")


async def fetch_plan(
    plan: list[dict[str, Any]],
    cache_dir: Path,
    *,
    concurrency: int,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    backoff_max: float = DEFAULT_BACKOFF_MAX,
) -> list[str]:
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {
        "User-Agent": "anki-english-source-snapshot/1.0",
        "Accept-Language": "en",
    }
    semaphore = asyncio.Semaphore(concurrency)
    pacer = _RequestPacer(request_delay)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        tasks = [
            asyncio.create_task(_fetch_one(
                session,
                semaphore,
                item,
                cache_dir,
                pacer=pacer,
                max_attempts=max_attempts,
                backoff_base=backoff_base,
                backoff_max=backoff_max,
            ))
            for item in plan
        ]
        results: list[str] = []
        total = len(tasks)
        for completed in asyncio.as_completed(tasks):
            results.append(await completed)
            count = len(results)
            if count % 25 == 0 or count == total:
                print(
                    f"progress: {count}/{total} lookups complete "
                    f"({results.count('fetched')} fetched, "
                    f"{results.count('cached')} cached)",
                    file=sys.stderr,
                    flush=True,
                )
        return results


def build_rows(
    plan: list[dict[str, Any]],
    cache_dir: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in plan:
        cache_path = _cache_path(cache_dir, item["lookup_headword"])
        try:
            body, metadata = _validate_cache_pair(
                cache_path,
                item,
                allow_legacy_migration=False,
            )
        except ValueError as exc:
            raise FileNotFoundError(str(exc)) from exc
        rows.append(parse_snapshot(
            body,
            lookup_headword=item["lookup_headword"],
            coverage_requests=item["coverage_requests"],
            cache_file=cache_path.name,
            response_url=str(metadata["response_url"]),
            http_status=int(metadata["http_status"]),
        ))
    return rows


def validate_rows(
    rows: list[dict[str, Any]],
    *,
    schema_path: Path,
    plan: list[dict[str, Any]] | None = None,
) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for row in rows:
        validator.validate(row)
    validate_snapshot_rows(rows, expected_plan=plan)


def _parser() -> argparse.ArgumentParser:
    defaults = ProjectPaths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path, default=defaults.card_registry,
    )
    parser.add_argument(
        "--source", type=Path, default=defaults.cambridge_english_vietnamese_jsonl,
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=defaults.cambridge_english_vietnamese_cache_dir,
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=defaults.root / "data" / "schema" / "cambridge_english_vietnamese_record.schema.json",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan")
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    fetch.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY)
    fetch.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    fetch.add_argument("--backoff-base", type=float, default=DEFAULT_BACKOFF_BASE)
    fetch.add_argument("--backoff-max", type=float, default=DEFAULT_BACKOFF_MAX)
    build = subparsers.add_parser("build")
    build_mode = build.add_mutually_exclusive_group(required=True)
    build_mode.add_argument("--check", action="store_true")
    build_mode.add_argument("--apply", action="store_true")
    subparsers.add_parser("validate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        plan = build_plan(args.registry)
        if args.command == "plan":
            sys.stdout.write(serialize_rows(plan))
            return 0
        if args.command == "fetch":
            if args.concurrency < 1:
                raise ValueError("--concurrency must be at least 1")
            if args.request_delay < 0:
                raise ValueError("--request-delay must not be negative")
            if args.max_attempts < 1:
                raise ValueError("--max-attempts must be at least 1")
            if args.backoff_base <= 0 or args.backoff_max <= 0:
                raise ValueError("backoff delays must be positive")
            if args.backoff_base > args.backoff_max:
                raise ValueError("--backoff-base must not exceed --backoff-max")
            results = asyncio.run(
                fetch_plan(
                    plan,
                    args.cache_dir,
                    concurrency=args.concurrency,
                    request_delay=args.request_delay,
                    max_attempts=args.max_attempts,
                    backoff_base=args.backoff_base,
                    backoff_max=args.backoff_max,
                )
            )
            print(
                f"Cambridge English–Vietnamese cache: "
                f"{results.count('fetched')} fetched, {results.count('cached')} cached"
            )
            return 0
        if args.command == "build":
            rows = build_rows(plan, args.cache_dir)
            validate_rows(rows, schema_path=args.schema, plan=plan)
            payload = serialize_rows(rows).encode("utf-8")
            if args.check:
                if not args.source.exists() or args.source.read_bytes() != payload:
                    print(f"Snapshot is missing or stale: {args.source}", file=sys.stderr)
                    return 1
                print(f"Snapshot is current: {args.source}")
                return 0
            _atomic_write(args.source, payload)
            print(f"Wrote {len(rows)} rows: {args.source}")
            return 0
        if args.command == "validate":
            rows = _load_jsonl(args.source)
            validate_rows(rows, schema_path=args.schema, plan=plan)
            print(f"Validated {len(rows)} rows: {args.source}")
            return 0
    except (
        CambridgeEnglishVietnameseParseError,
        FileNotFoundError,
        jsonschema.ValidationError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
