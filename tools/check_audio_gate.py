#!/usr/bin/env python3
"""Validate canonical audio references against tracked dictionary audio."""
from __future__ import annotations

import sys

from src.config import ProjectPaths
from src.deck_builder.build_validation import validate_artifact_paths


def main() -> int:
    paths = ProjectPaths()
    report = validate_artifact_paths(
        paths.anki_notes_jsonl,
        paths.anki_notes_txt,
        paths.card_registry,
        paths.audio_dir,
    )

    if report.ok:
        print(
            f"[OK] audio gate passed: cards={report.card_count} "
            f"jsonl_sha256={report.jsonl_sha256} txt_sha256={report.txt_sha256}",
        )
        return 0

    print("Error: audio gate failed", file=sys.stderr)
    print(report.error_text(), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
