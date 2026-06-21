"""Generate v2 golden fixtures for Oxford + Cambridge parsers.

Run from project root:
    python -m tools._make_golden_v2

Reads 5 random HTML files from each source's .cache_html/<source>/, parses them,
normalizes whitespace, writes:
    tests/fixtures/golden_oxford_v2.json
    tests/fixtures/golden_cambridge_v2.json

Sample files: random.seed(99) for reproducibility.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from typing import Any

from lxml import html as lxml_html

# Make src/ importable
PROJECT_ROOT = r"C:\Users\admin\Downloads\ankideck"
sys.path.insert(0, PROJECT_ROOT)

from src.scraper.oxford import parse_oxford  # noqa: E402
from src.scraper.cambridge import parse_cambridge  # noqa: E402

OXFORD_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")
CAMBRIDGE_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "cambridge")
OXFORD_OUT = os.path.join(PROJECT_ROOT, "tests", "fixtures", "golden_oxford_v2.json")
CAMBRIDGE_OUT = os.path.join(PROJECT_ROOT, "tests", "fixtures", "golden_cambridge_v2.json")


def _normalize_for_golden(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize fields that vary between runs (CSRF, source_url) for stable golden.

    Strategy: set to None where values are inherently non-deterministic.
    """
    record = json.loads(json.dumps(record))  # deep copy
    if "source_url" in record:
        record["source_url"] = None  # derived from filename, not test target
    return record


def _pick_random_files(directory: str, n: int, seed: int = 99) -> list[str]:
    random.seed(seed)
    files = [f for f in os.listdir(directory) if f.endswith(".html")]
    return random.sample(files, n)


def generate_oxford() -> list[dict]:
    files = _pick_random_files(OXFORD_DIR, 5)
    print(f"Oxford sample: {files}")
    out = []
    for f in files:
        path = os.path.join(OXFORD_DIR, f)
        with open(path, "rb") as fh:
            raw = fh.read()
        record = parse_oxford(raw, source_files=[f])
        if record is None:
            print(f"  SKIP {f}: non-word page (no h1.headword)")
            continue
        record = _normalize_for_golden(record)
        record["file"] = f
        record["polymorphic_form"] = _polymorphic_form(f)
        out.append(record)
    return out


def generate_cambridge() -> list[dict]:
    files = _pick_random_files(CAMBRIDGE_DIR, 5)
    print(f"Cambridge sample: {files}")
    out = []
    for f in files:
        path = os.path.join(CAMBRIDGE_DIR, f)
        with open(path, "rb") as fh:
            raw = fh.read()
        record = parse_cambridge(raw, source_files=[f])
        record = _normalize_for_golden(record)
        record["file"] = f
        out.append(record)
    return out


def _polymorphic_form(name: str) -> str:
    base = name.removesuffix(".html")
    if "_(" in base:
        head = base.split("_(")[0]
        if head.rsplit("_", 1)[-1].isdigit():
            return "indexed_pos"
        return "pos_suffix"
    return "main_page"


def main() -> int:
    oxford = generate_oxford()
    cambridge = generate_cambridge()

    with open(OXFORD_OUT, "w", encoding="utf-8") as f:
        json.dump(oxford, f, indent=2, ensure_ascii=False)
    with open(CAMBRIDGE_OUT, "w", encoding="utf-8") as f:
        json.dump(cambridge, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(oxford)} Oxford records to {OXFORD_OUT}")
    print(f"Wrote {len(cambridge)} Cambridge records to {CAMBRIDGE_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
