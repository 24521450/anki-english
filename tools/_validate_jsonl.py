"""Validate canonical Oxford, Cambridge, and Cambridge English–Vietnamese JSONL.

Run with: python -m tools._validate_jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

from src.config import ProjectPaths

paths = ProjectPaths()
PROJECT_ROOT = paths.root
OXFORD_SCHEMA = PROJECT_ROOT / "data" / "schema" / "oxford_record.schema.json"
CAMBRIDGE_SCHEMA = PROJECT_ROOT / "data" / "schema" / "cambridge_record.schema.json"
CAMBRIDGE_ENGLISH_VIETNAMESE_SCHEMA = (
    PROJECT_ROOT
    / "data"
    / "schema"
    / "cambridge_english_vietnamese_record.schema.json"
)
OXFORD_MERGED = paths.oxford_jsonl
CAMBRIDGE_FULL = paths.cambridge_jsonl
CAMBRIDGE_ENGLISH_VIETNAMESE = paths.cambridge_english_vietnamese_jsonl


def validate_file(jsonl_path: Path, schema_path: Path, label: str) -> tuple[int, list[tuple[int, str, str]]]:
    """Validate each line of jsonl_path against schema_path. Returns (total, errors)."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    total = 0
    errors: list[tuple[int, str, str]] = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            total += 1
            rec = json.loads(line)
            for err in validator.iter_errors(rec):
                errors.append((i, rec.get("word", "?"), err.message))
                # Only collect first error per record to keep output focused
                break

    print(f"\n=== {label} ===")
    print(f"File:    {jsonl_path}")
    print(f"Schema:  {schema_path}")
    print(f"Records: {total}")
    print(f"Errors:  {len(errors)}")
    if errors:
        for i, word, msg in errors[:20]:
            print(f"  [line {i}] {word}: {msg}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
    return total, errors


def main() -> int:
    grand_total = 0
    grand_errors = 0

    # 1) Oxford merged (Phase 7b output — must validate)
    t, e = validate_file(OXFORD_MERGED, OXFORD_SCHEMA, "Oxford merged (Phase 7b)")
    grand_total += t
    grand_errors += len(e)

    # 2) Cambridge full (1 source per word, no merge)
    t, e = validate_file(CAMBRIDGE_FULL, CAMBRIDGE_SCHEMA, "Cambridge full")
    grand_total += t
    grand_errors += len(e)

    # 3) Cambridge English–Vietnamese supporting translation evidence
    t, e = validate_file(
        CAMBRIDGE_ENGLISH_VIETNAMESE,
        CAMBRIDGE_ENGLISH_VIETNAMESE_SCHEMA,
        "Cambridge English–Vietnamese snapshot",
    )
    grand_total += t
    grand_errors += len(e)

    print(f"\n=== GRAND TOTAL ===")
    print(f"Records validated: {grand_total}")
    print(f"Errors:            {grand_errors}")
    return 0 if grand_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
