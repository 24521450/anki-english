"""Hydrate parser regression HTML fixtures for CI.

The default pytest suite expects a small set of Oxford and Cambridge HTML
cache files under data/.cache_html/. On a clean checkout those files are
missing, so CI downloads the exact pages needed by the parser regression
tests and verifies that the parsed output matches the committed golden JSON.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

import requests

from src.scraper.cambridge import parse_cambridge
from src.scraper.oxford import parse_oxford


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OXFORD_CACHE = PROJECT_ROOT / "data" / ".cache_html" / "oxford"
CAMBRIDGE_CACHE = PROJECT_ROOT / "data" / ".cache_html" / "cambridge"
OXFORD_GOLDEN = PROJECT_ROOT / "tests" / "fixtures" / "golden_oxford_v2.json"
CAMBRIDGE_GOLDEN = PROJECT_ROOT / "tests" / "fixtures" / "golden_cambridge_v2.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_oxford(record: dict) -> dict:
    out = copy.deepcopy(record)
    out["source_url"] = None
    out.pop("file", None)
    out.pop("polymorphic_form", None)
    return out


def _normalize_cambridge(record: dict) -> dict:
    out = copy.deepcopy(record)
    out["source_url"] = None
    out.pop("file", None)
    return out


def _fetch(url: str) -> bytes | None:
    resp = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=30,
        allow_redirects=True,
    )
    if resp.status_code != 200:
        return None
    return resp.content


def _write_if_needed(target: Path, content: bytes, force: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        return
    target.write_bytes(content)


def _slug_candidates_from_oxford_filename(filename: str) -> list[str]:
    base = filename.removeprefix("oxford_").removesuffix(".html")
    if base.endswith(")") and "_(" in base:
        base = base.rsplit("_(", 1)[0]

    candidates: list[str] = []

    def add(value: str) -> None:
        if value and value not in candidates:
            candidates.append(value)

    add(base)

    stem = base
    match = re.match(r"^(.*)_(\d+)$", base)
    if match:
        stem = match.group(1)
        add(stem)

    for root in (base, stem):
        for suffix in ("_1", "_2", "_3"):
            add(f"{root}{suffix}")

    return candidates


def _cambridge_candidates_from_filename(filename: str) -> list[str]:
    base = filename.removeprefix("cambridge_").removesuffix(".html")
    candidates: list[str] = []
    for value in (base, base.replace("_", "-"), base.replace("-", "")):
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def _hydrate_oxford_record(record: dict, force: bool) -> str:
    filename = record["file"]
    target = OXFORD_CACHE / filename
    expected = _normalize_oxford(record)

    if target.exists() and not force:
        parsed = parse_oxford(target.read_bytes(), source_files=[filename])
        if parsed is not None and _normalize_oxford(parsed) == expected:
            return f"ok {filename} (already present)"

    for slug in _slug_candidates_from_oxford_filename(filename):
        url = f"https://www.oxfordlearnersdictionaries.com/definition/english/{slug}"
        content = _fetch(url)
        if content is None:
            continue
        parsed = parse_oxford(content, source_files=[filename])
        if parsed is None:
            continue
        if _normalize_oxford(parsed) == expected:
            _write_if_needed(target, content, force)
            return f"ok {filename} <- {url}"

    raise RuntimeError(f"unable to hydrate Oxford fixture {filename}")


def _hydrate_oxford_special(filename: str, force: bool, predicate) -> str:
    target = OXFORD_CACHE / filename
    if target.exists() and not force:
        parsed = parse_oxford(target.read_bytes(), source_files=[filename])
        if parsed is not None and predicate(parsed):
            return f"ok {filename} (already present)"

    for slug in _slug_candidates_from_oxford_filename(filename):
        url = f"https://www.oxfordlearnersdictionaries.com/definition/english/{slug}"
        content = _fetch(url)
        if content is None:
            continue
        parsed = parse_oxford(content, source_files=[filename])
        if parsed is None or not predicate(parsed):
            continue
        _write_if_needed(target, content, force)
        return f"ok {filename} <- {url}"

    raise RuntimeError(f"unable to hydrate Oxford special fixture {filename}")


def _hydrate_cambridge_record(record: dict, force: bool) -> str:
    filename = record["file"]
    target = CAMBRIDGE_CACHE / filename
    expected = _normalize_cambridge(record)

    if target.exists() and not force:
        parsed = parse_cambridge(target.read_bytes(), source_files=[filename])
        if parsed is not None and _normalize_cambridge(parsed) == expected:
            return f"ok {filename} (already present)"

    for slug in _cambridge_candidates_from_filename(filename):
        url = f"https://dictionary.cambridge.org/dictionary/english/{slug}"
        content = _fetch(url)
        if content is None:
            continue
        parsed = parse_cambridge(content, source_files=[filename])
        if parsed is None:
            continue
        if _normalize_cambridge(parsed) == expected:
            _write_if_needed(target, content, force)
            return f"ok {filename} <- {url}"

    raise RuntimeError(f"unable to hydrate Cambridge fixture {filename}")


def _hydrate_cambridge_special(filename: str, force: bool, predicate) -> str:
    target = CAMBRIDGE_CACHE / filename
    if target.exists() and not force:
        parsed = parse_cambridge(target.read_bytes(), source_files=[filename])
        if parsed is not None and predicate(parsed):
            return f"ok {filename} (already present)"

    for slug in _cambridge_candidates_from_filename(filename):
        url = f"https://dictionary.cambridge.org/dictionary/english/{slug}"
        content = _fetch(url)
        if content is None:
            continue
        parsed = parse_cambridge(content, source_files=[filename])
        if parsed is None or not predicate(parsed):
            continue
        _write_if_needed(target, content, force)
        return f"ok {filename} <- {url}"

    raise RuntimeError(f"unable to hydrate Cambridge special fixture {filename}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite existing fixture files")
    args = parser.parse_args()

    oxford = _load_json(OXFORD_GOLDEN)
    cambridge = _load_json(CAMBRIDGE_GOLDEN)

    print(f"Hydrating Oxford fixtures into {OXFORD_CACHE}")
    for record in oxford:
        print(_hydrate_oxford_record(record, args.force))

    print(
        _hydrate_oxford_special(
            "oxford_sick_1_(adj).html",
            args.force,
            lambda rec: rec.get("word") == "sick"
            and rec.get("pos_data")
            and len(rec["pos_data"]) == 1
            and rec["pos_data"][0].get("pos") == "adjective"
            and len(rec["pos_data"][0].get("definitions", [])) == 7,
        )
    )
    print(
        _hydrate_oxford_special(
            "oxford_aggregate_(adj).html",
            args.force,
            lambda rec: rec.get("word") == "aggregate"
            and rec.get("pos_data")
            and len(rec["pos_data"]) == 1
            and rec["pos_data"][0].get("pos") == "adjective"
            and len(rec["pos_data"][0].get("definitions", [])) == 1,
        )
    )
    print(
        _hydrate_oxford_special(
            "oxford_aggregate_(verb).html",
            args.force,
            lambda rec: rec.get("word") == "aggregate"
            and rec.get("pos_data")
            and len(rec["pos_data"]) == 1
            and rec["pos_data"][0].get("pos") == "verb"
            and len(rec["pos_data"][0].get("definitions", [])) == 1,
        )
    )
    print(
        _hydrate_oxford_special(
            "oxford_aggregate_1_(noun).html",
            args.force,
            lambda rec: rec.get("word") == "aggregate"
            and rec.get("pos_data")
            and len(rec["pos_data"]) == 1
            and rec["pos_data"][0].get("pos") == "noun"
            and len(rec["pos_data"][0].get("definitions", [])) == 2,
        )
    )
    print(
        _hydrate_oxford_special(
            "oxford_abolish_(verb).html",
            args.force,
            lambda rec: rec.get("word") == "abolish"
            and rec.get("pos_data")
            and len(rec["pos_data"]) >= 1,
        )
    )

    print(f"Hydrating Cambridge fixtures into {CAMBRIDGE_CACHE}")
    for record in cambridge:
        print(_hydrate_cambridge_record(record, args.force))

    print(
        _hydrate_cambridge_special(
            "cambridge_violation.html",
            args.force,
            lambda rec: rec.get("word") == "violation"
            and "infraction" in rec.get("see_also", [])
            and "misdemeanour" in rec.get("see_also", []),
        )
    )

    print("Parser fixtures ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
