"""Hydrate parser regression HTML fixtures for CI.

The default pytest suite expects a small set of Oxford and Cambridge HTML
cache files under data/.cache_html/. On a clean checkout those files are
missing, so CI downloads every fixture declared in the parser fixture manifest
and verifies either its committed golden record or its semantic assertions.
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
MANIFEST_PATH = PROJECT_ROOT / "tests" / "fixtures" / "parser_fixture_manifest.json"

CACHE_DIRECTORIES = {
    "oxford": OXFORD_CACHE,
    "cambridge": CAMBRIDGE_CACHE,
}
SLUG_STRATEGIES = {
    "oxford": "oxford_filename_v1",
    "cambridge": "cambridge_filename_v1",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_fixture_filename(owner: str, source: str, filename: object) -> str:
    if not isinstance(filename, str) or not filename:
        raise ValueError(f"{owner}: fixture filename must be a non-empty string")
    if Path(filename).name != filename:
        raise ValueError(f"{owner}: fixture filename must be a basename: {filename!r}")
    if not filename.endswith(".html"):
        raise ValueError(f"{owner}: fixture filename must end with '.html': {filename!r}")
    prefix = f"{source}_"
    if not filename.startswith(prefix):
        raise ValueError(
            f"{owner}: {source} fixture filename must start with {prefix!r}: "
            f"{filename!r}"
        )
    return filename


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("parser fixture manifest must use schema_version 1")

    golden_sets = manifest.get("golden_sets")
    special_fixtures = manifest.get("special_fixtures")
    if not isinstance(golden_sets, list) or not isinstance(special_fixtures, list):
        raise ValueError("parser fixture manifest requires golden_sets and special_fixtures lists")

    ids: set[str] = set()
    targets: dict[tuple[str, str], str] = {}

    def register_target(owner: str, source: str, filename: object) -> None:
        valid_filename = _validate_fixture_filename(owner, source, filename)
        key = (source, valid_filename)
        previous_owner = targets.get(key)
        if previous_owner is not None:
            raise ValueError(
                f"duplicate parser fixture target {source}/{valid_filename}: "
                f"{previous_owner} and {owner}"
            )
        targets[key] = owner

    for item in [*golden_sets, *special_fixtures]:
        fixture_id = item.get("id")
        source = item.get("source")
        strategy = item.get("slug_strategy")
        if not isinstance(fixture_id, str) or not fixture_id:
            raise ValueError("every parser fixture entry requires a non-empty id")
        if fixture_id in ids:
            raise ValueError(f"duplicate parser fixture id: {fixture_id}")
        ids.add(fixture_id)
        if source not in CACHE_DIRECTORIES:
            raise ValueError(f"unsupported parser fixture source: {source!r}")
        if strategy != SLUG_STRATEGIES[source]:
            raise ValueError(
                f"{fixture_id}: slug_strategy must be {SLUG_STRATEGIES[source]!r}"
            )

    for golden_set in golden_sets:
        records = golden_set.get("records")
        if not isinstance(records, str) or not records:
            raise ValueError(f"{golden_set['id']}: golden set requires records")
        records_path = PROJECT_ROOT / records
        if not records_path.is_file():
            raise ValueError(f"{golden_set['id']}: missing golden records {records}")
        loaded_records = _load_json(records_path)
        if not isinstance(loaded_records, list):
            raise ValueError(f"{golden_set['id']}: golden records must be a list")
        for index, record in enumerate(loaded_records, 1):
            if not isinstance(record, dict):
                raise ValueError(
                    f"{golden_set['id']}: golden record {index} must be an object"
                )
            register_target(
                f"{golden_set['id']}: golden record {index}",
                golden_set["source"],
                record.get("file"),
            )

    for fixture in special_fixtures:
        source = fixture["source"]
        register_target(fixture["id"], source, fixture.get("filename"))

        assertions = fixture.get("assertions")
        if not isinstance(assertions, dict):
            raise ValueError(f"{fixture['id']}: special fixture requires assertions")
        if not isinstance(assertions.get("word"), str) or not assertions["word"]:
            raise ValueError(f"{fixture['id']}: assertions require word")
        pos_sections = assertions.get("pos_sections")
        if not isinstance(pos_sections, list) or not pos_sections:
            raise ValueError(f"{fixture['id']}: assertions require pos_sections")
        for section in pos_sections:
            if not isinstance(section.get("pos"), str):
                raise ValueError(f"{fixture['id']}: every POS section requires pos")
            count = section.get("definition_count")
            if not isinstance(count, int) or count < 0:
                raise ValueError(
                    f"{fixture['id']}: every POS section requires definition_count"
                )
        if not isinstance(assertions.get("required_idioms"), list):
            raise ValueError(f"{fixture['id']}: assertions require required_idioms")
        if not isinstance(assertions.get("required_see_also"), list):
            raise ValueError(f"{fixture['id']}: assertions require required_see_also")
        opal = assertions.get("opal")
        if "opal" in assertions and (
            not isinstance(opal, dict)
            or not opal
            or any(not isinstance(pos, str) or not pos for pos in opal)
            or any(value not in (["W"], ["S"], ["W", "S"]) for value in opal.values())
        ):
            raise ValueError(
                f"{fixture['id']}: assertions.opal must use canonical POS membership"
            )

    return manifest


def golden_records(source: str, manifest: dict | None = None) -> list[dict]:
    manifest = manifest or load_manifest()
    records: list[dict] = []
    for golden_set in manifest["golden_sets"]:
        if golden_set["source"] == source:
            records.extend(_load_json(PROJECT_ROOT / golden_set["records"]))
    return records


def special_fixtures(source: str | None = None, manifest: dict | None = None) -> list[dict]:
    manifest = manifest or load_manifest()
    fixtures = manifest["special_fixtures"]
    if source is not None:
        fixtures = [item for item in fixtures if item["source"] == source]
    return fixtures


def special_fixture(fixture_id: str, manifest: dict | None = None) -> dict:
    for fixture in special_fixtures(manifest=manifest):
        if fixture["id"] == fixture_id:
            return fixture
    raise KeyError(f"undeclared parser fixture id: {fixture_id}")


def declared_fixture_filenames(source: str, manifest: dict | None = None) -> set[str]:
    manifest = manifest or load_manifest()
    return {
        *(record["file"] for record in golden_records(source, manifest)),
        *(fixture["filename"] for fixture in special_fixtures(source, manifest)),
    }


def fixture_path(source: str, filename: str, manifest: dict | None = None) -> Path:
    if source not in CACHE_DIRECTORIES:
        raise KeyError(f"unsupported parser fixture source: {source}")
    if filename not in declared_fixture_filenames(source, manifest):
        raise KeyError(f"undeclared parser fixture: {source}/{filename}")
    return CACHE_DIRECTORIES[source] / filename


def special_fixture_path(fixture_id: str, manifest: dict | None = None) -> Path:
    fixture = special_fixture(fixture_id, manifest)
    return fixture_path(fixture["source"], fixture["filename"], manifest)


def _normalize_oxford(record: dict) -> dict:
    out = copy.deepcopy(record)
    out["source_url"] = None
    out.pop("file", None)
    out.pop("polymorphic_form", None)
    for pos_data in out.get("pos_data") or []:
        pos_data.pop("source_url", None)
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


def _slug_candidates(filename: str, strategy: str) -> list[str]:
    if strategy == "oxford_filename_v1":
        return _slug_candidates_from_oxford_filename(filename)
    if strategy == "cambridge_filename_v1":
        return _cambridge_candidates_from_filename(filename)
    raise ValueError(f"unsupported parser fixture slug strategy: {strategy}")


def _fixture_url(source: str, slug: str) -> str:
    if source == "oxford":
        return f"https://www.oxfordlearnersdictionaries.com/definition/english/{slug}"
    if source == "cambridge":
        return f"https://dictionary.cambridge.org/dictionary/english/{slug}"
    raise ValueError(f"unsupported parser fixture source: {source}")


def _hydrate_oxford_record(
    record: dict,
    force: bool,
    slug_strategy: str = "oxford_filename_v1",
) -> str:
    filename = record["file"]
    target = OXFORD_CACHE / filename
    expected = _normalize_oxford(record)

    if target.exists() and not force:
        parsed = parse_oxford(target.read_bytes(), source_files=[filename])
        if parsed is not None and _normalize_oxford(parsed) == expected:
            return f"ok {filename} (already present)"

    for slug in _slug_candidates(filename, slug_strategy):
        url = _fixture_url("oxford", slug)
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


def _hydrate_cambridge_record(
    record: dict,
    force: bool,
    slug_strategy: str = "cambridge_filename_v1",
) -> str:
    filename = record["file"]
    target = CAMBRIDGE_CACHE / filename
    expected = _normalize_cambridge(record)

    if target.exists() and not force:
        parsed = parse_cambridge(target.read_bytes(), source_files=[filename])
        if parsed is not None and _normalize_cambridge(parsed) == expected:
            return f"ok {filename} (already present)"

    for slug in _slug_candidates(filename, slug_strategy):
        url = _fixture_url("cambridge", slug)
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


def matches_semantic_assertions(record: dict, assertions: dict) -> bool:
    actual_sections = [
        {
            "pos": section.get("pos"),
            "definition_count": len(section.get("definitions") or []),
        }
        for section in record.get("pos_data") or []
    ]
    actual_idioms = {
        (item.get("phrase"), item.get("pos")) for item in record.get("idioms") or []
    }
    required_idioms = {
        (item.get("phrase"), item.get("pos"))
        for item in assertions["required_idioms"]
    }
    actual_see_also = set(record.get("see_also") or [])
    return (
        record.get("word") == assertions["word"]
        and actual_sections == assertions["pos_sections"]
        and required_idioms <= actual_idioms
        and set(assertions["required_see_also"]) <= actual_see_also
        and ("opal" not in assertions or record.get("opal") == assertions["opal"])
    )


def _hydrate_special_fixture(fixture: dict, force: bool) -> str:
    source = fixture["source"]
    filename = fixture["filename"]
    target = CACHE_DIRECTORIES[source] / filename
    parser = parse_oxford if source == "oxford" else parse_cambridge

    if target.exists() and not force:
        parsed = parser(target.read_bytes(), source_files=[filename])
        if parsed is not None and matches_semantic_assertions(parsed, fixture["assertions"]):
            return f"ok {filename} (already present)"

    for slug in _slug_candidates(filename, fixture["slug_strategy"]):
        url = _fixture_url(source, slug)
        content = _fetch(url)
        if content is None:
            continue
        parsed = parser(content, source_files=[filename])
        if parsed is None or not matches_semantic_assertions(parsed, fixture["assertions"]):
            continue
        _write_if_needed(target, content, force)
        return f"ok {filename} <- {url}"

    raise RuntimeError(f"unable to hydrate {source} special fixture {filename}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite existing fixture files")
    args = parser.parse_args()

    manifest = load_manifest()
    for source in ("oxford", "cambridge"):
        print(f"Hydrating {source.title()} fixtures into {CACHE_DIRECTORIES[source]}")
        hydrate_record = (
            _hydrate_oxford_record if source == "oxford" else _hydrate_cambridge_record
        )
        for golden_set in manifest["golden_sets"]:
            if golden_set["source"] != source:
                continue
            for record in _load_json(PROJECT_ROOT / golden_set["records"]):
                print(
                    hydrate_record(
                        record,
                        args.force,
                        slug_strategy=golden_set["slug_strategy"],
                    )
                )
        for fixture in special_fixtures(source, manifest):
            print(_hydrate_special_fixture(fixture, args.force))

    print("Parser fixtures ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
