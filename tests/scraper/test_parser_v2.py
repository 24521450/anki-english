"""Pytest v2: 5 Oxford + 5 Cambridge records, parser self-consistent.

Strategy: re-parse the same HTML files used to generate the golden, normalize
whitespace, deep-equal against the saved JSON. Any divergence = parser change
or golden staleness.

If a test fails, do NOT edit the golden to make it pass. Investigate which
field changed and fix the parser (or regenerate golden if the change is
intentional).
"""
from __future__ import annotations

import json
import os
import re
import sys

from pathlib import Path
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, PROJECT_ROOT)

import pytest  # noqa: E402

from src.scraper.oxford import parse_oxford  # noqa: E402
from src.scraper.cambridge import parse_cambridge  # noqa: E402

OXFORD_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")
CAMBRIDGE_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "cambridge")
OXFORD_GOLDEN = os.path.join(PROJECT_ROOT, "tests", "fixtures", "golden_oxford_v2.json")
CAMBRIDGE_GOLDEN = os.path.join(PROJECT_ROOT, "tests", "fixtures", "golden_cambridge_v2.json")


def _normalize_ws(obj):
    """Recursively collapse all whitespace runs to single space in all string values."""
    if isinstance(obj, dict):
        return {k: _normalize_ws(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_ws(v) for v in obj]
    if isinstance(obj, str):
        return re.sub(r"\s+", " ", obj).strip()
    return obj


def _load_golden(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_oxford_record(filename: str) -> dict:
    path = os.path.join(OXFORD_DIR, filename)
    with open(path, "rb") as f:
        raw = f.read()
    record = parse_oxford(raw, source_files=[filename])
    record["source_url"] = None  # not test target
    # Canonical POS provenance was added after the frozen v2 golden fixture.
    for pos_data in record["pos_data"]:
        pos_data.pop("source_url", None)
    return record


def _parse_cambridge_record(filename: str) -> dict:
    path = os.path.join(CAMBRIDGE_DIR, filename)
    with open(path, "rb") as f:
        raw = f.read()
    record = parse_cambridge(raw, source_files=[filename])
    record["source_url"] = None
    return record


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def oxford_golden():
    return _load_golden(OXFORD_GOLDEN)


@pytest.fixture(scope="module")
def cambridge_golden():
    return _load_golden(CAMBRIDGE_GOLDEN)


# -----------------------------------------------------------------------------
# Oxford tests
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("record", _load_golden(OXFORD_GOLDEN), ids=lambda r: r["file"])
def test_oxford_parser_consistent(record, oxford_golden):
    filename = record["file"]
    parsed = _parse_oxford_record(filename)
    assert parsed is not None, f"Oxford golden file {filename} unexpectedly parsed to None"
    expected = {k: v for k, v in record.items() if k not in ("file", "polymorphic_form")}

    parsed_norm = _normalize_ws(parsed)
    expected_norm = _normalize_ws(expected)
    if parsed_norm != expected_norm:
        # Show first diff for diagnostics
        from deepdiff import DeepDiff
        diff = DeepDiff(expected_norm, parsed_norm, ignore_order=True, verbose_level=2)
        pytest.fail(f"Oxford parse mismatch for {filename}:\n{diff}")


def test_oxford_parser_returns_none_for_non_word_page():
    raw = b"<html><body><p>No headword here</p></body></html>"
    parsed = parse_oxford(raw, source_files=["synthetic_non_word.html"])
    assert parsed is None


def test_oxford_parser_attaches_trusted_canonical_url_to_each_pos_section():
    raw = b"""
    <html><head><link rel="canonical"
      href="https://www.oxfordlearnersdictionaries.com/definition/english/torture_1"></head>
    <body><h1 class="headword">torture</h1><div class="top-container">
      <div class="top-g"><span class="pos">noun</span></div>
      <ol class="sense_single"><li class="sense"><span class="def">pain</span></li></ol>
    </div></body></html>
    """
    parsed = parse_oxford(raw)
    assert parsed["source_url"] is None
    assert parsed["pos_data"][0]["source_url"] == (
        "https://www.oxfordlearnersdictionaries.com/definition/english/torture_1"
    )


def test_oxford_parser_rejects_untrusted_canonical_url():
    raw = b"""
    <html><head><link rel="canonical"
      href="https://example.com/definition/english/torture_1"></head>
    <body><h1 class="headword">torture</h1><div class="top-container">
      <div class="top-g"><span class="pos">noun</span></div>
      <ol class="sense_single"><li class="sense"><span class="def">pain</span></li></ol>
    </div></body></html>
    """
    assert parse_oxford(raw)["pos_data"][0]["source_url"] is None


def test_oxford_parser_rejects_conflicting_valid_canonical_urls():
    raw = b"""
    <html><head>
      <link rel="canonical" href="https://www.oxfordlearnersdictionaries.com/definition/english/torture_1">
      <link rel="canonical" href="https://www.oxfordlearnersdictionaries.com/definition/english/torture_2">
    </head><body><h1 class="headword">torture</h1><div class="top-container">
      <div class="top-g"><span class="pos">noun</span></div>
      <ol class="sense_single"><li class="sense"><span class="def">pain</span></li></ol>
    </div></body></html>
    """
    assert parse_oxford(raw)["pos_data"][0]["source_url"] is None


# -----------------------------------------------------------------------------
# Cambridge tests
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("record", _load_golden(CAMBRIDGE_GOLDEN), ids=lambda r: r["file"])
def test_cambridge_parser_consistent(record, cambridge_golden):
    filename = record["file"]
    parsed = _parse_cambridge_record(filename)
    expected = {k: v for k, v in record.items() if k not in ("file",)}
    parsed_norm = _normalize_ws(parsed)
    expected_norm = _normalize_ws(expected)
    if parsed_norm != expected_norm:
        from deepdiff import DeepDiff
        diff = DeepDiff(expected_norm, parsed_norm, ignore_order=True, verbose_level=2)
        pytest.fail(f"Cambridge parse mismatch for {filename}:\n{diff}")


# -----------------------------------------------------------------------------
# Schema sanity: structure
# -----------------------------------------------------------------------------

def test_oxford_schema_required_fields(oxford_golden):
    required = {"word", "source", "source_url", "source_files", "pos", "register_tags",
               "oxford_lists", "opal", "awl", "audio", "see_also", "pos_data",
               "verb_forms", "idioms"}
    for rec in oxford_golden:
        missing = required - set(rec.keys())
        assert not missing, f"Oxford record {rec.get('file', '?')} missing fields: {missing}"


def test_cambridge_schema_required_fields(cambridge_golden):
    required = {"word", "source", "source_url", "source_files", "pos", "register_tags",
               "oxford_lists", "opal", "awl", "audio", "see_also", "pos_data",
               "verb_forms", "idioms"}
    for rec in cambridge_golden:
        missing = required - set(rec.keys())
        assert not missing, f"Cambridge record {rec.get('file', '?')} missing fields: {missing}"


# -----------------------------------------------------------------------------
# $schema field: removed in v3 (placeholder URL was non-resolvable, no tooling
# fetched it). Records must NOT carry the field; schema must NOT require it.
# -----------------------------------------------------------------------------

def test_oxford_parser_does_not_emit_schema_field():
    """Oxford parser must not emit the $schema key in its output (v3 cleanup)."""
    filename = oxford_golden.__self__ if False else None
    recs = _load_golden(OXFORD_GOLDEN)
    # Pick a real word page (not None-returning non-word page)
    candidates = [r for r in recs if r.get("word")]
    assert candidates, "No Oxford word records in golden fixture to test"
    filename = candidates[0]["file"]
    parsed = _parse_oxford_record(filename)
    assert parsed is not None, f"Parser returned None for {filename}"
    assert "$schema" not in parsed, (
        f"Oxford parser still emits '$schema' key for {filename}. "
        f"v3 removed this field (placeholder URL was non-resolvable)."
    )


def test_cambridge_parser_does_not_emit_schema_field():
    """Cambridge parser must not emit the $schema key in its output (v3 cleanup)."""
    recs = _load_golden(CAMBRIDGE_GOLDEN)
    candidates = [r for r in recs if r.get("word")]
    assert candidates, "No Cambridge word records in golden fixture to test"
    filename = candidates[0]["file"]
    parsed = _parse_cambridge_record(filename)
    assert parsed is not None, f"Parser returned None for {filename}"
    assert "$schema" not in parsed, (
        f"Cambridge parser still emits '$schema' key for {filename}. "
        f"v3 removed this field (placeholder URL was non-resolvable)."
    )


def test_audio_has_uk_and_us(oxford_golden, cambridge_golden):
    for rec in oxford_golden + cambridge_golden:
        assert "uk" in rec["audio"], f"{rec.get('file', '?')}: audio missing 'uk'"
        assert "us" in rec["audio"], f"{rec.get('file', '?')}: audio missing 'us'"


def test_pos_data_definitions_have_required_fields(oxford_golden, cambridge_golden):
    required = {"n", "sensenum_local", "text", "register_tags", "cefr", "topics",
                "collocations", "examples", "is_phrase", "is_idiom"}
    for rec in oxford_golden + cambridge_golden:
        for pd in rec["pos_data"]:
            for d in pd["definitions"]:
                missing = required - set(d.keys())
                assert not missing, f"{rec.get('file', '?')} def missing: {missing}"


def test_examples_have_text_and_cf(oxford_golden, cambridge_golden):
    for rec in oxford_golden + cambridge_golden:
        for pd in rec["pos_data"]:
            for d in pd["definitions"]:
                for ex in d["examples"]:
                    assert "text" in ex, f"{rec.get('file', '?')} ex missing text"
                    assert "cf" in ex, f"{rec.get('file', '?')} ex missing cf"
