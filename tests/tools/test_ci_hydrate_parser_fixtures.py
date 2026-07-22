import copy
import fnmatch
import json
import re
from pathlib import Path

import pytest

from tools import ci_hydrate_parser_fixtures as hydrator


def _golden_set(tmp_path: Path, fixture_id: str, records: list[dict]) -> dict:
    records_name = f"{fixture_id}.json"
    (tmp_path / records_name).write_text(
        json.dumps(records),
        encoding="utf-8",
    )
    return {
        "id": fixture_id,
        "source": "oxford",
        "records": records_name,
        "slug_strategy": "oxford_filename_v1",
    }


def _special_fixture(fixture_id: str, filename: str) -> dict:
    return {
        "id": fixture_id,
        "source": "oxford",
        "filename": filename,
        "slug_strategy": "oxford_filename_v1",
        "assertions": {
            "word": "fixture",
            "pos_sections": [{"pos": "noun", "definition_count": 1}],
            "required_idioms": [],
            "required_see_also": [],
        },
    }


def _write_manifest(
    tmp_path: Path,
    monkeypatch,
    *,
    golden_sets: list[dict],
    special_fixtures: list[dict],
) -> Path:
    monkeypatch.setattr(hydrator, "PROJECT_ROOT", tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "golden_sets": golden_sets,
            "special_fixtures": special_fixtures,
        }),
        encoding="utf-8",
    )
    return path


def test_hydrate_oxford_ignores_pos_source_url(tmp_path, monkeypatch):
    record = {
        "file": "oxford_linger_(verb).html",
        "word": "linger",
        "source_url": None,
        "pos_data": [
            {
                "pos": "verb",
                "definitions": [],
                "register_tags": [],
            }
        ],
    }
    parsed = copy.deepcopy(record)
    parsed["source_url"] = (
        "https://www.oxfordlearnersdictionaries.com/definition/english/linger"
    )
    parsed["pos_data"][0]["source_url"] = parsed["source_url"]

    monkeypatch.setattr(hydrator, "OXFORD_CACHE", tmp_path)
    monkeypatch.setattr(hydrator, "_fetch", lambda _url: b"valid Oxford HTML")
    monkeypatch.setattr(hydrator, "parse_oxford", lambda *_args, **_kwargs: parsed)

    result = hydrator._hydrate_oxford_record(record, force=False)

    assert result.startswith("ok oxford_linger_(verb).html <- ")
    assert (tmp_path / record["file"]).read_bytes() == b"valid Oxford HTML"


def test_manifest_is_the_fixture_catalog():
    manifest = hydrator.load_manifest()

    assert manifest["golden_sets"]
    assert manifest["special_fixtures"]
    assert all(item["slug_strategy"] for item in manifest["golden_sets"])
    assert all(item["assertions"] for item in manifest["special_fixtures"])


@pytest.mark.parametrize(
    ("entry_kind", "invalid_kind", "error"),
    [
        ("golden", "traversal", "must be a basename"),
        ("special", "traversal", "must be a basename"),
        ("golden", "absolute", "must be a basename"),
        ("special", "absolute", "must be a basename"),
        ("golden", "wrong_prefix", "must start with 'oxford_'"),
        ("special", "wrong_prefix", "must start with 'oxford_'"),
        ("golden", "wrong_extension", "must end with '.html'"),
        ("special", "wrong_extension", "must end with '.html'"),
    ],
)
def test_manifest_rejects_unsafe_fixture_targets(
    tmp_path,
    monkeypatch,
    entry_kind,
    invalid_kind,
    error,
):
    filenames = {
        "traversal": "../oxford_escape.html",
        "absolute": str((tmp_path / "oxford_absolute.html").resolve()),
        "wrong_prefix": "cambridge_wrong.html",
        "wrong_extension": "oxford_wrong.txt",
    }
    filename = filenames[invalid_kind]
    golden_sets = []
    special_fixtures = []
    if entry_kind == "golden":
        golden_sets.append(_golden_set(tmp_path, "golden", [{"file": filename}]))
    else:
        special_fixtures.append(_special_fixture("special", filename))
    manifest_path = _write_manifest(
        tmp_path,
        monkeypatch,
        golden_sets=golden_sets,
        special_fixtures=special_fixtures,
    )

    with pytest.raises(ValueError, match=re.escape(error)):
        hydrator.load_manifest(manifest_path)


@pytest.mark.parametrize(
    "duplicate_layout",
    ["within_golden", "across_golden", "within_special", "golden_special"],
)
def test_manifest_rejects_duplicate_fixture_targets(
    tmp_path,
    monkeypatch,
    duplicate_layout,
):
    filename = "oxford_duplicate.html"
    golden_sets = []
    special_fixtures = []
    if duplicate_layout == "within_golden":
        golden_sets.append(
            _golden_set(tmp_path, "golden-a", [{"file": filename}, {"file": filename}])
        )
    elif duplicate_layout == "across_golden":
        golden_sets.extend([
            _golden_set(tmp_path, "golden-a", [{"file": filename}]),
            _golden_set(tmp_path, "golden-b", [{"file": filename}]),
        ])
    elif duplicate_layout == "within_special":
        special_fixtures.extend([
            _special_fixture("special-a", filename),
            _special_fixture("special-b", filename),
        ])
    else:
        golden_sets.append(_golden_set(tmp_path, "golden-a", [{"file": filename}]))
        special_fixtures.append(_special_fixture("special-a", filename))
    manifest_path = _write_manifest(
        tmp_path,
        monkeypatch,
        golden_sets=golden_sets,
        special_fixtures=special_fixtures,
    )

    with pytest.raises(
        ValueError,
        match=r"duplicate parser fixture target oxford/oxford_duplicate\.html",
    ):
        hydrator.load_manifest(manifest_path)


def test_fixture_path_rejects_undeclared_ignored_cache_file():
    undeclared = "oxford_" + "not-reviewed_(noun).html"
    with pytest.raises(KeyError, match="undeclared parser fixture"):
        hydrator.fixture_path("oxford", undeclared)


def test_multipos_fixture_predicate_checks_idiom_owner_pos():
    assertions = {
        "word": "stack",
        "pos_sections": [{"pos": "noun", "definition_count": 6}],
        "required_idioms": [{"phrase": "blow your top", "pos": "noun"}],
        "required_see_also": [],
    }
    record = {
        "word": "stack",
        "pos_data": [{"pos": "noun", "definitions": [{}, {}, {}, {}, {}, {}]}],
        "idioms": [{"phrase": "blow your top", "pos": "noun"}],
    }

    assert hydrator.matches_semantic_assertions(record, assertions)
    record["idioms"][0]["pos"] = "verb"
    assert not hydrator.matches_semantic_assertions(record, assertions)


def test_fixture_predicate_checks_exact_optional_opal_membership():
    assertions = {
        "word": "accordingly",
        "pos_sections": [{"pos": "adverb", "definition_count": 2}],
        "required_idioms": [],
        "required_see_also": [],
        "opal": {"adverb": ["W"]},
    }
    record = {
        "word": "accordingly",
        "pos_data": [{"pos": "adverb", "definitions": [{}, {}]}],
        "idioms": [],
        "see_also": [],
        "opal": {"adverb": ["W"]},
    }

    assert hydrator.matches_semantic_assertions(record, assertions)
    record["opal"] = {"adverb": ["S"]}
    assert not hydrator.matches_semantic_assertions(record, assertions)


def test_manifest_rejects_noncanonical_opal_assertion(tmp_path, monkeypatch):
    fixture = _special_fixture("opal", "oxford_opal_(adv).html")
    fixture["assertions"]["opal"] = {"adverb": ["S", "W"]}
    manifest_path = _write_manifest(
        tmp_path,
        monkeypatch,
        golden_sets=[],
        special_fixtures=[fixture],
    )

    with pytest.raises(
        ValueError,
        match="assertions.opal must use canonical POS membership",
    ):
        hydrator.load_manifest(manifest_path)


def test_default_tests_only_reference_declared_ignored_cache_fixtures():
    declared = {
        source: hydrator.declared_fixture_filenames(source)
        for source in ("oxford", "cambridge")
    }
    fixture_pattern = re.compile(r"['\"]((?:oxford|cambridge)_[^'\"]*\.html)['\"]")
    undeclared: list[str] = []
    guard_path = hydrator.PROJECT_ROOT / "tests" / "tools" / Path(__file__).name

    for path in sorted((hydrator.PROJECT_ROOT / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if ".cache_html" not in text or path == guard_path:
            continue
        patterns = fixture_pattern.findall(text)
        if not patterns:
            undeclared.append(
                f"{path.relative_to(hydrator.PROJECT_ROOT)}: direct cache directory scan"
            )
            continue
        for pattern in patterns:
            source = pattern.split("_", 1)[0]
            if not any(fnmatch.fnmatchcase(filename, pattern) for filename in declared[source]):
                undeclared.append(f"{path.relative_to(hydrator.PROJECT_ROOT)}: {pattern}")

    assert not undeclared, (
        "ignored parser cache fixtures must be declared in "
        "tests/fixtures/parser_fixture_manifest.json:\n" + "\n".join(undeclared)
    )
