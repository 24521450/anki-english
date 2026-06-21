"""Schema validation: all 3 JSONL files pass their respective schemas.

Run with: pytest tests/test_schema_validation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

PROJECT_ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
OXFORD_SCHEMA = json.loads((PROJECT_ROOT / "data" / "schema" / "oxford_record.schema.json").read_text(encoding="utf-8"))
CAMBRIDGE_SCHEMA = json.loads((PROJECT_ROOT / "data" / "schema" / "cambridge_record.schema.json").read_text(encoding="utf-8"))


def _validate(jsonl_path: Path, schema: dict) -> list[tuple[int, str, str]]:
    """Validate each line of jsonl against schema. Returns list of (line, word, error_msg)."""
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[tuple[int, str, str]] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            rec = json.loads(line)
            for err in validator.iter_errors(rec):
                errors.append((i, rec.get("word", "?"), err.message))
                break
    return errors


def test_oxford_merged_validates():
    errors = _validate(PROJECT_ROOT / "data" / "oxford_merged.jsonl", OXFORD_SCHEMA)
    assert not errors, f"Oxford merged has {len(errors)} schema errors. First 5: {errors[:5]}"


def test_cambridge_full_validates():
    errors = _validate(PROJECT_ROOT / "data" / "cambridge_full.jsonl", CAMBRIDGE_SCHEMA)
    assert not errors, f"Cambridge full has {len(errors)} schema errors. First 5: {errors[:5]}"


# -----------------------------------------------------------------------------
# v3 cleanup: $schema field removed (placeholder URL non-resolvable).
# Schema must NOT require it, and MUST NOT declare it as a property.
# -----------------------------------------------------------------------------

def test_oxford_schema_does_not_require_dollar_schema():
    assert "$schema" not in OXFORD_SCHEMA.get("required", []), (
        "Oxford schema still lists '$schema' in required. v3 removed this field; "
        "the real contract is data/schema/oxford_record.schema.json itself."
    )
    assert "$schema" not in (OXFORD_SCHEMA.get("properties") or {}), (
        "Oxford schema still declares '$schema' in properties. v3 removed this field."
    )


def test_cambridge_schema_does_not_require_dollar_schema():
    assert "$schema" not in CAMBRIDGE_SCHEMA.get("required", []), (
        "Cambridge schema still lists '$schema' in required. v3 removed this field."
    )
    assert "$schema" not in (CAMBRIDGE_SCHEMA.get("properties") or {}), (
        "Cambridge schema still declares '$schema' in properties. v3 removed this field."
    )


# -----------------------------------------------------------------------------
# v3.1 cleanup: oxford_full.jsonl removed.
# - Parser output goes directly into the merge layer; no intermediate file.
# - Schema validation only runs against oxford_merged.jsonl (Cambridge stays
#   separate because it has no merge step).
# - Determinism is verified by SHA-256 of oxford_merged.jsonl across runs
#   (see tools/_check_determinism.py).
# -----------------------------------------------------------------------------

def test_oxford_full_jsonl_does_not_exist():
    """oxford_full.jsonl was removed in v3.1 — the intermediate unmerged file
    is no longer written by _run_full_cache.py."""
    assert not (PROJECT_ROOT / "data" / "oxford_full.jsonl").exists(), (
        "data/oxford_full.jsonl should not exist after v3.1 cleanup. "
        "If you just ran _run_full_cache.py, the pipeline still writes the "
        "unmerged file. Remove OXFORD_OUT from tools/_run_full_cache.py."
    )


def test_inspect_phrasal_files_uses_merged_source():
    """The deprecated phrasal-files inspector must read oxford_merged.jsonl,
    not the removed oxford_full.jsonl. It uses `fname in source_files` to
    find the phrasal-verb record; merged records preserve source_files list."""
    from pathlib import Path
    inspector = (PROJECT_ROOT / "tools" / "_inspect_phrasal_files.py").read_text(encoding="utf-8")
    assert "oxford_full.jsonl" not in inspector, (
        "tools/_inspect_phrasal_files.py still references oxford_full.jsonl (removed in v3.1). "
        "Update it to read oxford_merged.jsonl."
    )
    assert "oxford_merged.jsonl" in inspector, (
        "tools/_inspect_phrasal_files.py must read oxford_merged.jsonl after v3.1 cleanup."
    )


def test_check_determinism_tool_exists_and_reads_merged():
    """tools/_check_determinism.py must exist and reference oxford_merged.jsonl
    (replaces the v3.0 --oxford-only flag SHA-256 check that was tied to the
    now-removed oxford_full.jsonl)."""
    from pathlib import Path
    det = PROJECT_ROOT / "tools" / "_check_determinism.py"
    assert det.exists(), (
        "tools/_check_determinism.py must exist after v3.1 cleanup. "
        "It replaces the --oxford-only flag's SHA-256 check."
    )
    src = det.read_text(encoding="utf-8")
    assert "oxford_merged.jsonl" in src, (
        "tools/_check_determinism.py must compare oxford_merged.jsonl SHA-256 across runs."
    )
    assert "sha256" in src.lower(), (
        "tools/_check_determinism.py must use SHA-256 to verify byte-identical output."
    )


# -----------------------------------------------------------------------------
# v3 round-trip: a fresh parser output (no $schema) validates against the
# updated schema. This is the green-path proof for the cleanup.
# -----------------------------------------------------------------------------

def test_fresh_oxford_parser_output_validates():
    """Build a record via the parser and validate against the schema."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.scraper.oxford import parse_oxford
    html_path = next((PROJECT_ROOT / "data" / ".cache_html" / "oxford").glob("oxford_abolish_*.html"))
    raw = html_path.read_bytes()
    rec = parse_oxford(raw, source_files=[html_path.name])
    assert rec is not None, f"Parser returned None for {html_path.name}"
    assert "$schema" not in rec, "Parser still emits '$schema'"
    jsonschema.Draft202012Validator(OXFORD_SCHEMA).validate(rec)  # raises if invalid


def test_fresh_cambridge_parser_output_validates():
    """Build a Cambridge record via the parser and validate against the schema."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.scraper.cambridge import parse_cambridge
    html_path = next((PROJECT_ROOT / "data" / ".cache_html" / "cambridge").glob("cambridge_violation.html"))
    raw = html_path.read_bytes()
    rec = parse_cambridge(raw, source_files=[html_path.name])
    assert rec is not None, f"Parser returned None for {html_path.name}"
    assert "$schema" not in rec, "Parser still emits '$schema'"
    jsonschema.Draft202012Validator(CAMBRIDGE_SCHEMA).validate(rec)  # raises if invalid
