"""Audit Oxford OPAL metadata against the canonical HTML cache.

The detector in this module intentionally does not call the production Oxford
parser.  It is a differential guard for the raw page markers that feed the
parser, merge layer, and final ``data/sources/oxford.jsonl`` artifact.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from src.config import ProjectPaths


OPAL_ORDER = ("W", "S")
VALID_MEMBERSHIPS = {("W",), ("S",), ("W", "S")}


_H1_TAG_RE = re.compile(rb"<h1\b[^>]*>", re.IGNORECASE)
_CONTAINER_TAG_RE = re.compile(rb"<(?:div|span)\b[^>]*>", re.IGNORECASE)
_DIV_BOUNDARY_RE = re.compile(rb"</?div\b[^>]*>", re.IGNORECASE)
_SPAN_RE = re.compile(rb"<span\b[^>]*>.*?</span\s*>", re.IGNORECASE | re.DOTALL)
_ATTR_RE = re.compile(rb"([:\w-]+)\s*=\s*(['\"])(.*?)\2", re.DOTALL)
_HTML_TAG_RE = re.compile(rb"<[^>]+>")


def _attributes(tag: bytes) -> dict[str, str]:
    start_tag = tag.split(b">", 1)[0]
    return {
        match.group(1).decode("ascii", errors="ignore").casefold():
        html.unescape(match.group(3).decode("utf-8", errors="ignore"))
        for match in _ATTR_RE.finditer(start_tag)
    }


def _has_class(attributes: dict[str, str], name: str) -> bool:
    return name in attributes.get("class", "").split()


def _element_text(element: bytes) -> str:
    return " ".join(
        html.unescape(_HTML_TAG_RE.sub(b" ", element).decode("utf-8", errors="ignore")).split()
    )


def _leading_text(element: bytes) -> str:
    content = element.split(b">", 1)[1] if b">" in element else b""
    value = content.split(b"<", 1)[0]
    return " ".join(html.unescape(value.decode("utf-8", errors="ignore")).split())


def _complete_div(data: bytes, start: int) -> bytes:
    depth = 0
    for match in _DIV_BOUNDARY_RE.finditer(data, start):
        if match.group().startswith(b"</"):
            depth -= 1
            if depth == 0:
                return data[start:match.end()]
        else:
            depth += 1
    return b""


def _direct_symbols_region(webtop_region: bytes) -> bytes:
    depth = 0
    for match in _DIV_BOUNDARY_RE.finditer(webtop_region):
        if match.group().startswith(b"</"):
            depth -= 1
            continue
        if depth == 1 and _has_class(_attributes(match.group()), "symbols"):
            return _complete_div(webtop_region, match.start())
        depth += 1
    return b""


def inspect_cached_page(html_bytes: bytes) -> dict[str, tuple[str, ...]] | None:
    """Return raw POS-scoped OPAL membership from one cached Oxford page."""
    headword_match = next(
        (
            match
            for match in _H1_TAG_RE.finditer(html_bytes)
            if _has_class(_attributes(match.group()), "headword")
        ),
        None,
    )
    if headword_match is None:
        return None

    codes: set[str] = set()
    headword = _attributes(headword_match.group())
    if headword.get("opal_written", "").casefold() == "y":
        codes.add("W")
    if headword.get("opal_spoken", "").casefold() == "y":
        codes.add("S")

    window_start = max(0, headword_match.start() - 4096)
    webtop_matches = [
        match
        for match in _CONTAINER_TAG_RE.finditer(html_bytes, window_start, headword_match.start())
        if _has_class(_attributes(match.group()), "webtop")
    ]
    if not webtop_matches:
        raise ValueError("headword has no scoped Oxford webtop")
    webtop_start = webtop_matches[-1].start()
    webtop_region = html_bytes[webtop_start:headword_match.end() + 8192]
    spans = list(_SPAN_RE.finditer(webtop_region))
    symbols_region = _direct_symbols_region(webtop_region)
    for symbol_match in _SPAN_RE.finditer(symbols_region):
        symbol = _attributes(symbol_match.group())
        if not _has_class(symbol, "opal_symbol"):
            continue
        marker = symbol.get("href", "").casefold()
        label = _element_text(symbol_match.group()).upper()
        if marker.startswith("opal_written::") or label == "OPAL W":
            codes.add("W")
        if marker.startswith("opal_spoken::") or label == "OPAL S":
            codes.add("S")
    if not codes:
        return None

    positions: list[str] = []
    for pos_match in spans:
        attributes = _attributes(pos_match.group())
        if not _has_class(attributes, "pos"):
            continue
        # Oxford's parser uses the POS span's direct text node for a sense
        # section.  Combined headings such as ``adjective<span>,</span>
        # adverb`` therefore correctly scope this page to ``adjective``.
        pos = (_leading_text(pos_match.group()) or _element_text(pos_match.group())).casefold()
        if pos:
            positions.append(pos)
            break
    if not positions:
        raise ValueError("OPAL marker has no scoped Oxford entry POS")

    ordered = tuple(code for code in OPAL_ORDER if code in codes)
    return {pos: ordered for pos in positions}


def _validate_actual(value: object) -> dict[str, tuple[str, ...]] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise ValueError("opal must be null or a non-empty POS object")
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_pos, raw_codes in value.items():
        if not isinstance(raw_pos, str) or not raw_pos.strip():
            raise ValueError("opal POS keys must be non-empty strings")
        if not isinstance(raw_codes, list) or tuple(raw_codes) not in VALID_MEMBERSHIPS:
            raise ValueError(f"invalid OPAL membership for POS {raw_pos!r}: {raw_codes!r}")
        normalized[raw_pos.strip().casefold()] = tuple(raw_codes)
    return normalized


def _merge_page_memberships(
    target: dict[str, set[str]],
    page_memberships: dict[str, tuple[str, ...]] | None,
) -> None:
    for pos, codes in (page_memberships or {}).items():
        target.setdefault(pos, set()).update(codes)


def _freeze_memberships(values: dict[str, set[str]]) -> dict[str, tuple[str, ...]] | None:
    if not values:
        return None
    return {
        pos: tuple(code for code in OPAL_ORDER if code in codes)
        for pos, codes in values.items()
    }


@dataclass(frozen=True)
class AuditReport:
    records: int
    referenced_files: int
    labelled_pages: int
    expected_opal_records: int
    issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def audit_oxford_opal(oxford_jsonl: Path, cache_dir: Path) -> AuditReport:
    issues: list[str] = []
    referenced: set[str] = set()
    parsed_records: list[tuple[int, dict, list[str]]] = []
    records = 0

    for line_number, line in enumerate(oxford_jsonl.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        records += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"line {line_number}: invalid JSON: {exc}")
            continue
        word = str(record.get("word") or "?")
        source_names: list[str] = []
        for raw_name in record.get("source_files") or []:
            name = str(raw_name)
            if Path(name).name != name:
                issues.append(f"line {line_number} {word}: unsafe source file {name!r}")
                continue
            referenced.add(name)
            source_names.append(name)
        parsed_records.append((line_number, record, source_names))

    cache_paths = {path.name: path for path in cache_dir.glob("oxford_*.html")}
    for name in referenced:
        path = cache_dir / name
        if path.is_file():
            cache_paths.setdefault(name, path)

    def inspect_path(path: Path):
        try:
            return path.name, inspect_cached_page(path.read_bytes()), None
        except (OSError, ValueError) as exc:
            return path.name, None, str(exc)

    page_cache: dict[str, dict[str, tuple[str, ...]] | None] = {}
    page_errors: dict[str, str] = {}
    worker_count = min(32, max(4, (os.cpu_count() or 4) * 2))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        for name, membership, error in executor.map(inspect_path, cache_paths.values()):
            page_cache[name] = membership
            if error is not None:
                page_errors[name] = error
                issues.append(f"{name}: cannot inspect OPAL markers: {error}")

    expected_opal_records = 0
    for line_number, record, source_names in parsed_records:
        word = str(record.get("word") or "?")
        expected_parts: dict[str, set[str]] = {}
        source_error = False
        for name in source_names:
            if name not in cache_paths:
                issues.append(f"line {line_number} {word}: missing cache file {name}")
                source_error = True
                continue
            if name in page_errors:
                source_error = True
                continue
            _merge_page_memberships(expected_parts, page_cache[name])
        expected = _freeze_memberships(expected_parts)
        if expected is not None:
            expected_opal_records += 1
        if source_error:
            continue
        try:
            actual = _validate_actual(record.get("opal"))
        except ValueError as exc:
            issues.append(f"line {line_number} {word}: {exc}")
            continue
        if actual != expected:
            if expected is not None and actual is None:
                kind = "missing"
            elif expected is None and actual is not None:
                kind = "extra"
            else:
                kind = "mismatch"
            issues.append(
                f"line {line_number} {word}: {kind} OPAL metadata; "
                f"expected={expected!r} actual={actual!r}"
            )

    labelled_pages = 0
    for name in sorted(cache_paths):
        if name not in page_errors and page_cache[name] is not None:
            labelled_pages += 1
            if name not in referenced:
                issues.append(f"{name}: labelled OPAL cache file is not referenced by Oxford JSONL")

    return AuditReport(
        records=records,
        referenced_files=len(referenced),
        labelled_pages=labelled_pages,
        expected_opal_records=expected_opal_records,
        issues=tuple(issues),
    )


def main(argv: list[str] | None = None) -> int:
    paths = ProjectPaths()
    parser = argparse.ArgumentParser(description="Compare Oxford OPAL JSONL metadata with raw cache markers.")
    parser.add_argument("--oxford-jsonl", type=Path, default=paths.oxford_jsonl)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=paths.root / "data" / ".cache_html" / "oxford",
    )
    args = parser.parse_args(argv)
    try:
        report = audit_oxford_opal(args.oxford_jsonl, args.cache_dir)
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Oxford records: {report.records}")
    print(f"Referenced cache files: {report.referenced_files}")
    print(f"OPAL-labelled cache files: {report.labelled_pages}")
    print(f"Records expected to carry OPAL: {report.expected_opal_records}")
    if report.issues:
        print(f"OPAL audit failed with {len(report.issues)} issue(s):", file=sys.stderr)
        for issue in report.issues[:50]:
            print(f"- {issue}", file=sys.stderr)
        if len(report.issues) > 50:
            print(f"- ... {len(report.issues) - 50} more", file=sys.stderr)
        return 1
    print("OPAL audit passed: cache markers and Oxford JSONL agree exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
